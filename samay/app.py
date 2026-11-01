# -*- coding: utf-8 -*-
"""
SAMAY application core.

Owens:
* main window chrome (traffic lights, opacity slider, draggable header)
* left sidebar navigation
* live background compositor (day/night scenes + weather particles)
* weather plugin (Open-Meteo + ip-api.com, cached, rate-limited)
* module shells for Clock / Countdown / Stopwatch / World Clock / Alarm / Calendar

The on-screen UI is drawn with Cairo through GTK 3 DrawingArea widgets so the
app stays image-free and fully themeable via CSS.
"""

from __future__ import annotations

import json
import math
import os
import subprocess
import time
import datetime
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

import gi  # noqa: E402
gi.require_version('Gtk', '3.0')  # noqa: E402
gi.require_version('Gdk', '3.0')  # noqa: E402
gi.require_version('Pango', '1.0')  # noqa: E402
gi.require_version('PangoCairo', '1.0')  # noqa: E402

from gi.repository import (
    Gtk,  # noqa: F401
    Gdk,  # noqa: F401
    GLib,  # noqa: F401
    GdkPixbuf,  # noqa: F401
    Pango,  # noqa: F401
    PangoCairo,  # noqa: F401
)

try:
    import cairo as _cairo  # noqa: F401
except ImportError:  # pragma: no cover - runtime-only guard
    _cairo = None  # type: ignore[assignment]


# ----------------------------------------------------------------------
# Constants & paths
# ----------------------------------------------------------------------
_APP_NAME = "Samay"
_APP_TITLE = "Samay"
_HOME = Path.home()
_DATA_DIR = _HOME / ".samay"
_DATA_DIR.mkdir(parents=True, exist_ok=True)

_APP_DIR = Path(__file__).resolve().parent
_DATA_APP_DIR = _APP_DIR / "data"
_DATA_APP_DIR.mkdir(parents=True, exist_ok=True)

_DEFAULTS: Dict[str, Any] = {
    "opacity": 0.90,
    "window_width": 960,
    "window_height": 640,
    "sidebar_width": 220,
    "header_height": 45,
    "module": "clock",
    "alarms": [],
    "world_cities": [
        {"city": "Delhi, India", "tz": "Asia/Kolkata"},
        {"city": "Tokyo, Japan", "tz": "Asia/Tokyo"},
        {"city": "London, United Kingdom", "tz": "Europe/London"},
        {"city": "New York, United States", "tz": "America/New_York"},
        {"city": "Dubai, United Arab Emirates", "tz": "Asia/Dubai"},
    ],
    "countdown_target": None,
    "countdown_running": False,
    "countdown_start": None,
    "stopwatch_running": False,
    "stopwatch_start": None,
    "stopwatch_laps": [],
}

ALARM_FILE = _DATA_DIR / "alarms.json"
WORLD_FILE = _DATA_DIR / "world.json"
LAPS_FILE = _DATA_DIR / "laps.csv"
COUNTDOWN_FILE = _DATA_DIR / "countdown.json"
CALENDAR_CACHE_FILE = _DATA_DIR / "calendar_cache.json"
FESTIVAL_FILE = _DATA_APP_DIR / "indian_festivals_2026.json"

# ----------------------------------------------------------------------
# Visual constants
# ----------------------------------------------------------------------
HEADER_HEIGHT = 45
SIDEBAR_WIDTH = 220
WINDOW_MIN_W = 800
WINDOW_MIN_H = 500
WINDOW_SIZE_W = 960
WINDOW_SIZE_H = 640
CORNER_RADIUS = 18

HEADER_BG_RGBA = (0.058, 0.067, 0.082, 0.92)
SIDEBAR_BG_RGBA = (0.078, 0.086, 0.110, 0.85)
TAB_SEL_RGBA = (1.0, 1.0, 1.0, 0.15)
TAB_HOVER_RGBA = (1.0, 1.0, 1.0, 0.07)
CARD_BG_RGBA = (1.0, 1.0, 1.0, 0.05)
CARD_BORDER_RGBA = (1.0, 1.0, 1.0, 0.10)

DAY_TOP = (0.32, 0.52, 0.82, 1.0)
DAY_BOTTOM = (0.72, 0.84, 0.97, 1.0)
NIGHT_TOP = (0.04, 0.06, 0.21, 1.0)
NIGHT_BOTTOM = (0.0, 0.0, 0.04, 1.0)

TRAFFIC = {
    "close": ("#FF5F57", "#E0443E"),
    "minimize": ("#FFBD2E", "#DEA123"),
    "maximize": ("#28C940", "#1FAB35"),
}

FONT_CLOCK_DIGITAL = "Bold 34"
FONT_CLOCK_LABEL = "12"
FONT_UI = "13"
FONT_UI_BOLD = "Bold 13"
FONT_LAP = "12"
FONT_WEATHER_TEMP = "Bold 24"
FONT_WEATHER_CITY = "12"
FONT_HEADER = "Bold 12"

# ----------------------------------------------------------------------
# Tiny helpers
# ----------------------------------------------------------------------
def _load_json(path: Path, default: Any = None) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def _save_json(path: Path, data: Any) -> bool:
    try:
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        return True
    except Exception:
        return False


def _hex_to_rgba(hexcolor: str) -> Tuple[float, float, float, float]:
    if hexcolor.startswith("#") and len(hexcolor) == 9:
        r = int(hexcolor[1:3], 16) / 255.0
        g = int(hexcolor[3:5], 16) / 255.0
        b = int(hexcolor[5:7], 16) / 255.0
        a = int(hexcolor[7:9], 16) / 255.0
        return (r, g, b, a)
    if hexcolor.startswith("#"):
        r = int(hexcolor[1:3], 16) / 255.0
        g = int(hexcolor[3:5], 16) / 255.0
        b = int(hexcolor[5:7], 16) / 255.0
        return (r, g, b, 1.0)
    return (0.0, 0.0, 0.0, 1.0)


def _color_parse_cairo(hexcolor: str) -> Tuple[float, float, float]:
    p = Gdk.color_parse(hexcolor)
    return (p.red / 65535.0, p.green / 65535.0, p.blue / 65535.0)


def _now() -> datetime.datetime:
    return datetime.datetime.now()


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def _play_sound() -> None:
    """Best-effort notification/sound trigger using system primitives."""
    for cmd in (
        ["canberra-gtk-play", "-i", "complete"],
        ["canberra-gtk-play", "-i", "message"],
        ["paplay", "/usr/share/sounds/freedesktop/stereo/message.oga"],
    ):
        try:
            subprocess.run(cmd, check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            break
        except OSError:
            continue


def _notify(title: str, message: str) -> None:
    try:
        subprocess.run(
            ["notify-send", "-u", "normal", "-a", _APP_NAME, title, message],
            check=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except OSError:
        pass


def _import_requests() -> Any:
    try:
        import requests as _req  # noqa: F811
        return _req
    except Exception:  # pragma: no cover - runtime-only guard
        return None


# ----------------------------------------------------------------------
# Cairo button widgets (traffic lights + module tabs)
# ----------------------------------------------------------------------
class _CircularButton(Gtk.DrawingArea):
    __gtype_name__ = "SamayTrafficLight"

    def __init__(
        self,
        color: str,
        hover_color: str,
        on_activate: Callable[[], None],
        size: int = 28,
        radius: float = 7.0,
        cx: float = 14.0,
        cy: float = 14.0,
    ) -> None:
        super().__init__()
        self.set_size_request(size, size)
        self._color = color
        self._hover_color = hover_color
        self._on_activate = on_activate
        self._radius = radius
        self._cx = cx
        self._cy = cy
        self._hover = False
        self.add_events(
            Gdk.EventMask.BUTTON_PRESS_MASK
            | Gdk.EventMask.ENTER_NOTIFY_MASK
            | Gdk.EventMask.LEAVE_NOTIFY_MASK
        )
        self.connect("button-press-event", self._on_button_press)
        self.connect("enter-notify-event", self._on_enter)
        self.connect("leave-notify-event", self._on_leave)
        self.connect("draw", self._on_draw)

    def _on_button_press(self, area: Gtk.DrawingArea, event: Gdk.EventButton) -> bool:
        if event.button == 1:
            self._on_activate()
            return True
        return False

    def _on_enter(self, area: Gtk.DrawingArea, event: Gdk.EventAny) -> bool:
        self._hover = True
        self.queue_draw()
        return False

    def _on_leave(self, area: Gtk.DrawingArea, event: Gdk.EventAny) -> bool:
        self._hover = False
        self.queue_draw()
        return False

    def _on_draw(self, area: Gtk.DrawingArea, cr: Any) -> bool:  # cairo.Context
        if _cairo is None:
            return False
        r, g, b = _color_parse_cairo(self._hover_color if self._hover else self._color)
        cr.set_source_rgb(r, g, b)
        cr.set_line_width(0.0)
        cr.arc(self._cx, self._cy, self._radius, 0.0, 2.0 * math.pi)
        cr.fill()
        return False


class _CircularCloseButton(_CircularButton):
    __gtype_name__ = "SamayCircularCloseButton"


class _CircularMinimizeButton(_CircularButton):
    __gtype_name__ = "SamayCircularMinimizeButton"


class _CircularMaximizeButton(_CircularButton):
    __gtype_name__ = "SamayCircularMaximizeButton"


class _OpacitySlider(Gtk.HScale):
    __gtype_name__ = "SamayOpacitySlider"

    def __init__(self, on_change: Callable[[float], None]) -> None:
        super().__init__(orientation=Gtk.Orientation.HORIZONTAL)
        self.set_size_request(130, -1)
        self.set_draw_value(False)
        self.set_digits(2)
        self.set_range(0.40, 1.00)
        self.set_value(0.90)
        self.set_increments(0.01, 0.05)
        self._on_change = on_change
        self.connect("value-changed", self._on_value_changed)
        self.get_style_context().add_class("samay-opacity-slider")

    def _on_value_changed(self, scale: Gtk.Scale) -> None:
        try:
            self._on_change(_clamp(float(scale.get_value()), 0.40, 1.00))
        except Exception:
            pass


# ----------------------------------------------------------------------
# Top bar (traffic lights + opacity slider + drag area)
# ----------------------------------------------------------------------
class _TopBar(Gtk.Box):
    __gtype_name__ = "SamayTopBar"

    def __init__(
        self,
        window: "SamayWindow",
        sidebar_width: int,
        header_height: int,
        app: "SamayApp",
    ) -> None:
        super().__init__(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        self.set_name("SamayTopBar")
        self.set_size_request(sidebar_width, header_height)
        self.set_homogeneous(False)
        self.set_hexpand(False)
        self.set_vexpand(False)

        self._window = window
        self._app = app

        # Traffic lights
        close_btn = _CircularCloseButton(
            TRAFFIC["close"][0],
            TRAFFIC["close"][1],
            self._on_close,
        )
        min_btn = _CircularMinimizeButton(
            TRAFFIC["minimize"][0],
            TRAFFIC["minimize"][1],
            self._on_minimize,
        )
        max_btn = _CircularMaximizeButton(
            TRAFFIC["maximize"][0],
            TRAFFIC["maximize"][1],
            self._on_maximize,
        )

        # Spacer to push opacity slider to the right
        spacer = Gtk.Box()
        spacer.set_hexpand(True)
        spacer.set_vexpand(False)

        self.opacity_slider = _OpacitySlider(self._on_opacity_change)

        self.pack_start(close_btn, False, False, 0)
        self.pack_start(min_btn, False, False, 0)
        self.pack_start(max_btn, False, False, 0)
        self.pack_start(spacer, True, True, 0)
        self.pack_start(self.opacity_slider, False, False, 0)

        self.add_events(Gdk.EventMask.BUTTON_PRESS_MASK)
        self.connect("button-press-event", self._on_button_press)
        self.connect("draw", self._on_draw)

    # ------------------------------------------------------------------
    def _on_button_press(self, area: Gtk.Widget, event: Gdk.EventButton) -> bool:
        if event.button == 1:
            self._window.begin_move_drag(
                event.button,
                event.x_root,
                event.y_root,
                event.get_time(),
            )
            return True
        return False

    # ------------------------------------------------------------------
    def _on_close(self) -> None:
        Gtk.main_quit()

    def _on_minimize(self) -> None:
        try:
            self._window.iconify()
        except Exception:
            pass

    def _on_maximize(self) -> None:
        try:
            if self._window.is_fullscreen():
                self._window.unfullscreen()
            else:
                self._window.fullscreen()
        except Exception:
            pass

    def _on_opacity_change(self, alpha: float) -> None:
        alpha = _clamp(alpha, 0.40, 1.00)
        screen = self._window.get_screen()
        rgba_visual = screen.get_rgba_visual()
        if rgba_visual is not None:
            self._window.set_visual(rgba_visual)
        self._window.set_opacity(alpha)
        self._app.current_opacity = alpha
        self._app._request_redraw_all()

    # ------------------------------------------------------------------
    def _on_draw(self, area: Gtk.Widget, cr: Any) -> bool:
        if _cairo is None:
            return False
        width = area.get_allocated_width()
        height = area.get_allocated_height()
        cr.set_source_rgba(*HEADER_BG_RGBA)
        cr.rectangle(0.0, 0.0, width, height)
        cr.fill()
        cr.set_source_rgba(1.0, 1.0, 1.0, 0.10)
        cr.set_line_width(1.0)
        cr.move_to(0.0, height - 1.0)
        cr.line_to(max(0.0, width - 1.0), height - 1.0)
        cr.stroke()
        return False


# ----------------------------------------------------------------------
# Sidebar tabs
# ----------------------------------------------------------------------
class _SidebarTab(Gtk.DrawingArea):
    __gtype_name__ = "SamaySidebarTab"

    def __init__(
        self,
        label: str,
        icon: str,
        on_activate: Callable[[], None],
        accent_update: Callable[[Optional[str]], None],
        index: int,
    ) -> None:
        super().__init__()
        self.set_size_request(200, 46)
        self.set_hexpand(False)
        self.set_vexpand(False)
        self._label = label
        self._icon = icon
        self._on_activate = on_activate
        self._index = index
        self._selected = False
        self._accent_update = accent_update
        self.add_events(
            Gdk.EventMask.ENTER_NOTIFY_MASK
            | Gdk.EventMask.LEAVE_NOTIFY_MASK
            | Gdk.EventMask.BUTTON_PRESS_MASK
        )
        self.connect("enter-notify-event", self._on_enter)
        self.connect("leave-notify-event", self._on_leave)
        self.connect("button-press-event", self._on_button_press)
        self.connect("draw", self._on_draw)

    # ------------------------------------------------------------------
    def select(self) -> None:
        if not self._selected:
            self._selected = True
            if self._accent_update is not None:
                self._accent_update(self._label)
            self.queue_draw()
            if self._on_activate is not None:
                self._on_activate()

    def _on_enter(self, area: Gtk.Widget, event: Gdk.EventAny) -> bool:
        if not self._selected:
            self.queue_draw()
        return False

    def _on_leave(self, area: Gtk.Widget, event: Gdk.EventAny) -> bool:
        if not self._selected:
            self.queue_draw()
        return False

    def _on_button_press(self, area: Gtk.Widget, event: Gdk.EventButton) -> bool:
        if event.button == 1:
            self.select()
            return True
        return False

    # ------------------------------------------------------------------
    def _on_draw(self, area: Gtk.Widget, cr: Any) -> bool:
        if _cairo is None:
            return False
        width = area.get_allocated_width()
        height = area.get_allocated_height()
        margin_x = 10.0
        margin_y = 6.0
        tab_w = width - 2.0 * margin_x
        tab_h = height - 2.0 * margin_y
        x0 = margin_x
        y0 = margin_y
        r = min(12.0, tab_w / 2.0, tab_h / 2.0)

        if self._selected:
            cr.set_source_rgba(*TAB_SEL_RGBA)
        else:
            cr.set_source_rgba(0.0, 0.0, 0.0, 0.0)
        _round_rect_path(cr, x0, y0, tab_w, tab_h, r)
        cr.fill()

        if self._selected:
            cr.set_source_rgba(*TAB_HOVER_RGBA)
            _round_rect_path(cr, x0, y0, tab_w, tab_h, r)
            cr.fill()

        text_color = 1.0 if self._selected else 0.72
        cr.set_source_rgba(text_color, text_color, text_color, 1.0 if self._selected else 0.80)
        layout = PangoCairo.create_layout(cr)
        layout.set_font_description(Pango.FontDescription(FONT_UI))
        layout.set_text(f"{self._icon}   {self._label}", -1)
        ink, _logical = layout.get_pixel_extents()
        tx = x0 + (tab_w - ink.width) / 2.0
        ty = y0 + (tab_h - ink.height) / 2.0
        cr.move_to(tx, ty)
        PangoCairo.show_layout(cr, layout)
        return False


# ----------------------------------------------------------------------
# Sidebar
# ----------------------------------------------------------------------
class _Sidebar(Gtk.Box):
    __gtype_name__ = "SamaySidebar"

    def __init__(
        self,
        app: "SamayApp",
        initial_module: str,
    ) -> None:
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        self.set_name("SamaySidebar")
        self.set_size_request(SIDEBAR_WIDTH, -1)
        self.set_homogeneous(False)
        self.set_hexpand(False)
        self.set_vexpand(True)
        self.set_border_width(8)

        self._app = app
        self._tabs: List[_SidebarTab] = []
        self._initial_module = initial_module

        tab_specs = [
            ("Clock", "⏰", self._app.switch_to_clock),
            ("Countdown", "⏳", self._app.switch_to_countdown),
            ("Stopwatch", "⏱️", self._app.switch_to_stopwatch),
            ("World Clock", "🌍", self._app.switch_to_world),
            ("Alarm", "⏰", self._app.switch_to_alarm),
            ("Calendar", "📅", self._app.switch_to_calendar),
        ]

        for idx, (label, icon, callback) in enumerate(tab_specs):
            tab = _SidebarTab(label, icon, callback, self._on_accent, idx)
            self._tabs.append(tab)
            self.pack_start(tab, False, False, 2)

        self.select(initial_module)

    def _on_accent(self, label: Optional[str]) -> None:
        pass

    def select(self, module: str) -> None:
        module_index = _MODULE_INDEX.get(module, 0)
        for idx, tab in enumerate(self._tabs):
            tab._selected = (idx == module_index)
            tab.queue_draw()
        self._app.current_module = module

    def select_module(self, module: str) -> None:
        self.select(module)
        self._app.switch_to(module)


_MODULE_INDEX: Dict[str, int] = {
    "clock": 0,
    "countdown": 1,
    "stopwatch": 2,
    "world": 3,
    "alarm": 4,
    "calendar": 5,
}

_MODULE_LABEL: Dict[str, str] = {
    "clock": "Clock",
    "countdown": "Countdown",
    "stopwatch": "Stopwatch",
    "world": "World Clock",
    "alarm": "Alarm",
    "calendar": "Calendar",
}


# ----------------------------------------------------------------------
# Helper: rounded-rect path
# ----------------------------------------------------------------------
def _round_rect_path(
    cr: Any,
    x: float,
    y: float,
    w: float,
    h: float,
    r: float,
) -> None:
    if _cairo is None:
        cr.rectangle(x, y, w, h)
        return
    ctx: Any = cr
    if w <= 0.0 or h <= 0.0:
        ctx.rectangle(x, y, max(0.0, w), max(0.0, h))
        return
    r = min(r, w / 2.0, h / 2.0)
    ctx.move_to(x + r, y)
    ctx.line_to(x + w - r, y)
    ctx.arc(x + w - r, y + r, r, -math.pi / 2.0, 0.0)
    ctx.line_to(x + w, y + h - r)
    ctx.arc(x + w - r, y + h - r, r, 0.0, math.pi / 2.0)
    ctx.line_to(x + r, y + h)
    ctx.arc(x + r, y + h - r, r, math.pi / 2.0, math.pi)
    ctx.line_to(x, y + r)
    ctx.arc(x + r, y + r, r, math.pi, 3.0 * math.pi / 2.0)
    ctx.close_path()


# ----------------------------------------------------------------------
# App state
# ----------------------------------------------------------------------
class SamayApp:
    def __init__(self) -> None:
        self.current_opacity = float(_DEFAULTS["opacity"])
        self.current_module = str(_DEFAULTS["module"])
        self.window: Optional["SamayWindow"] = None

        # Weather
        self.weather_state: Dict[str, Any] = {
            "temperature_2m": None,
            "weather_code": 0,
            "is_day": 1,
            "city": "",
        }
        self._weather_fetch_at: float = 0.0
        self._weather_location: Dict[str, Any] = {}
        self._weather_calls_today: int = 0
        self._weather_calls_reset_at: float = 0.0

        # Particles
        self._particles: List[Dict[str, Any]] = []
        self._particle_timer_id: Optional[int] = None
        self._live_timer_id: Optional[int] = None
        self._clock_timer_id: Optional[int] = None
        self._weather_timer_id: Optional[int] = None
        self._calendar_timer_id: Optional[int] = None

        # Calendar
        self.calendar_cache: Dict[str, Any] = {}
        self.latest_festivals: List[Dict[str, Any]] = []

        # Clock digital text
        self.digital_str: str = "00:00:00 AM"

        # Module state
        self.alarms: List[Dict[str, Any]] = []
        self.world_cities: List[Dict[str, Any]] = []
        self.countdown_target: Optional[datetime.datetime] = None
        self.countdown_running: bool = False
        self.countdown_start: Optional[float] = None
        self.stopwatch_running: bool = False
        self.stopwatch_start: Optional[float] = None
        self.stopwatch_laps: List[Dict[str, float]] = []

        self._load_persistent_state()

    # ------------------------------------------------------------------
    def _load_persistent_state(self) -> None:
        alarms = _load_json(ALARM_FILE, [])
        self.alarms = alarms if isinstance(alarms, list) else []
        cities = _load_json(WORLD_FILE, [])
        if isinstance(cities, list) and cities:
            self.world_cities = cities
        else:
            self.world_cities = list(_DEFAULTS["world_cities"])
        countdown = _load_json(COUNTDOWN_FILE, None)
        if isinstance(countdown, dict) and countdown.get("target"):
            try:
                self.countdown_target = datetime.datetime.fromisoformat(countdown["target"])
            except Exception:
                self.countdown_target = None
        if isinstance(countdown, dict) and countdown.get("running"):
            self.countdown_running = bool(countdown["running"])
        if isinstance(countdown, dict) and countdown.get("start"):
            self.countdown_start = float(countdown["start"])

    # ------------------------------------------------------------------
    def _save_alarms(self) -> None:
        _save_json(ALARM_FILE, self.alarms)

    def _save_world(self) -> None:
        _save_json(WORLD_FILE, self.world_cities)

    def _save_countdown(self) -> None:
        target_iso = self.countdown_target.isoformat() if self.countdown_target else None
        _save_json(
            COUNTDOWN_FILE,
            {
                "target": target_iso,
                "running": self.countdown_running,
                "start": self.countdown_start,
            },
        )

    def _save_laps(self) -> None:
        try:
            LAPS_FILE.parent.mkdir(parents=True, exist_ok=True)
            lines = ["Lap,Total,LapTime"]
            for lap in self.stopwatch_laps:
                lap_no = lap.get("lap", "?")
                total = lap.get("total", 0.0)
                lap_time = lap.get("lap_time", 0.0)
                lines.append(f"{lap_no},{total:.3f},{lap_time:.3f}")
            LAPS_FILE.write_text("\n".join(lines) + "\n", encoding="utf-8")
        except Exception:
            pass

    # ------------------------------------------------------------------
    def _request_redraw_all(self) -> None:
        if self.window is not None:
            self.window.queue_draw_all()

    # ------------------------------------------------------------------
    def switch_to(self, module: str) -> None:
        self.current_module = module
        self._request_redraw_all()

    # ------------------------------------------------------------------
    def switch_to_clock(self) -> None:
        self.switch_to("clock")

    def switch_to_countdown(self) -> None:
        self.switch_to("countdown")

    def switch_to_stopwatch(self) -> None:
        self.switch_to("stopwatch")

    def switch_to_world(self) -> None:
        self.switch_to("world")

    def switch_to_alarm(self) -> None:
        self.switch_to("alarm")

    def switch_to_calendar(self) -> None:
        self.switch_to("calendar")

    # ------------------------------------------------------------------
    def run(self, argv: List[str]) -> int:
        self.window = SamayWindow(self)
        self.window.connect("destroy", self._on_destroy)
        self.window.connect("focus-out-event", self._on_focus_out)
        self.window.connect("configure-event", self._on_configure)
        self.window.focus()
        self.window.start_live_draw()
        self.start_weather()
        self.start_particles()
        self.start_clock_update()
        self.start_bell_schedule()
        self.start_calendar_fetch()
        Gtk.main()
        return 0

    # ------------------------------------------------------------------
    def _on_destroy(self, window: Gtk.Window) -> None:
        Gtk.main_quit()

    def _on_focus_out(self, window: Gtk.Window, event: Gdk.EventFocus) -> bool:
        return False

    def _on_configure(self, window: Gtk.Window, event: Gdk.EventConfigure) -> bool:
        return False

    # ------------------------------------------------------------------
    def start_weather(self) -> None:
        def tick() -> bool:
            self._fetch_weather()
            return True
        self._weather_timer_id = GLib.timeout_add_seconds(60, tick)
        self._fetch_weather()

    def _fetch_weather(self) -> None:
        now = time.time()
        if now - self._weather_fetch_at < 1800:
            return
        if self._weather_calls_reset_at == 0:
            self._weather_calls_reset_at = now + 3600
        if now > self._weather_calls_reset_at:
            self._weather_calls_today = 0
            self._weather_calls_reset_at = now + 3600
        if self._weather_calls_today >= 5:
            return
        loc = self._weather_location
        if not loc:
            self._update_location()
            loc = self._weather_location
        if not loc:
            return
        lat = loc.get("lat")
        lon = loc.get("lon")
        if lat is None or lon is None:
            return
        try:
            req = _import_requests()
            if req is None:
                return
            url = (
                "https://api.open-meteo.com/v1/forecast"
                "?latitude={}&longitude={}"
                "&current=temperature_2m,weather_code,is_day"
                "&daily=weather_code,temperature_2m_max,temperature_2m_min"
                "&timezone=auto"
            ).format(lat, lon)
            resp = req.get(url, timeout=8)
            data = resp.json()
            cur = data.get("current", {})
            temp = cur.get("temperature_2m")
            code = cur.get("weather_code", 0)
            is_day = cur.get("is_day", 1)
            city = loc.get("city", "Local")
            self.weather_state = {
                "temperature_2m": temp,
                "weather_code": code,
                "is_day": int(is_day),
                "city": city,
            }
            self._weather_fetch_at = time.time()
            self._weather_calls_today += 1
            self._request_redraw_all()
        except Exception:
            pass

    def _update_location(self) -> None:
        try:
            req = _import_requests()
            if req is None:
                self._weather_location = {"lat": 28.6, "lon": 77.2, "city": "Delhi"}
                return
            resp = req.get("http://ip-api.com/json/", timeout=8)
            data = resp.json()
            if data.get("status") == "success":
                self._weather_location = {
                    "lat": data.get("lat"),
                    "lon": data.get("lon"),
                    "city": data.get("city") or data.get("regionName") or "Local",
                }
                return
        except Exception:
            pass
        self._weather_location = {"lat": 28.6, "lon": 77.2, "city": "Delhi"}

    # ------------------------------------------------------------------
    def start_particles(self) -> None:
        if self._particle_timer_id is not None:
            return
        self._particles = []
        for i in range(70):
            self._particles.append({
                "x": float(i * 29),
                "y": float((i * 67) % 1200),
                "speed": 9.0 + (i % 17) * 0.4,
                "flash": False,
            })
        self._particle_timer_id = GLib.timeout_add(33, self._particle_tick)

    def _particle_tick(self) -> bool:
        w = 2400
        h = 1400
        for p in self._particles:
            p["y"] = p.get("y", 0.0) + p.get("speed", 9.0) * 0.55
            p["x"] = p.get("x", 0.0) + math.sin(p.get("y", 0.0) * 0.02) * 3.0
            if p["y"] > h:
                p["y"] = -4.0
            if p["x"] < -4.0:
                p["x"] = w
            if p["x"] > w + 4.0:
                p["x"] = -4.0
            if int(p.get("y", 0.0)) % 320 == 0:
                p["flash"] = not p.get("flash", False)
        self._request_redraw_all()
        return True

    # ------------------------------------------------------------------
    def start_clock_update(self) -> None:
        def tick() -> bool:
            now = _now()
            self.digital_str = now.strftime("%I:%M:%S %p").lstrip("0")
            if self.digital_str.startswith(":"):
                self.digital_str = "12" + self.digital_str
            if self.window is not None:
                self.window.queue_draw_all()
            return True
        self._clock_timer_id = GLib.timeout_add_seconds(1, tick)
        tick()

    # ------------------------------------------------------------------
    def start_bell_schedule(self) -> None:
        def tick() -> bool:
            self._check_alarms()
            self._check_countdown()
            return True
        GLib.timeout_add_seconds(1, tick)

    def _check_alarms(self) -> None:
        now = _now()
        for alarm in list(self.alarms):
            if not alarm.get("enabled", True):
                continue
            target = alarm.get("target")
            if target is None:
                continue
            try:
                alarm_dt = datetime.datetime.fromisoformat(target)
            except Exception:
                continue
            if alarm_dt.hour == now.hour and alarm_dt.minute == now.minute and alarm_dt.second == 0:
                _play_sound()
                _notify("Samay Alarm", alarm.get("label", "Alarm"))
                self._play_alarm_loop(3)

    def _play_alarm_loop(self, count: int) -> None:
        def tick() -> bool:
            nonlocal count
            if count <= 0:
                return False
            count -= 1
            _play_sound()
            return count > 0
        GLib.timeout_add_seconds(2, tick)

    def _check_countdown(self) -> None:
        if not self.countdown_running or self.countdown_target is None:
            return
        remaining = (self.countdown_target - _now()).total_seconds()
        if remaining <= 0:
            self.countdown_running = False
            self.countdown_start = None
            self._save_countdown()
            _play_sound()
            _notify("Samay Countdown", "Time is up!")
            self.countdown_target = None
            self._request_redraw_all()

    # ------------------------------------------------------------------
    def start_calendar_fetch(self) -> None:
        def tick() -> bool:
            self._refresh_calendar_cache()
            return True
        self._calendar_timer_id = GLib.timeout_add_seconds(3600 * 24, tick)
        self._refresh_calendar_cache()

    def _refresh_calendar_cache(self) -> None:
        now = _now()
        cache = _load_json(CALENDAR_CACHE_FILE, {})
        cache_ts = cache.get("fetched_at")
        cache_ts_dt = None
        if cache_ts:
            try:
                cache_ts_dt = datetime.datetime.fromisoformat(cache_ts)
            except Exception:
                cache_ts_dt = None
        cache_date = None
        if cache_ts_dt:
            cache_date = cache_ts_dt.date()
        today = now.date()
        need_fetch = False
        if not cache_ts_dt:
            need_fetch = True
        elif cache_date.month != today.month or (today - cache_date).days >= 30:
            need_fetch = True
        if not need_fetch:
            self.calendar_cache = cache
            self.latest_festivals = cache.get("festivals", [])
            return
        festivals = self._load_festivals()
        self.calendar_cache = {
            "fetched_at": now.isoformat(),
            "festivals": festivals,
        }
        self.latest_festivals = festivals
        _save_json(CALENDAR_CACHE_FILE, self.calendar_cache)

    def _load_festivals(self) -> List[Dict[str, Any]]:
        if FESTIVAL_FILE.exists():
            try:
                data = _load_json(FESTIVAL_FILE, [])
                if isinstance(data, list) and data:
                    return data
            except Exception:
                pass
        return self._fetch_festivals_from_network()

    def _fetch_festivals_from_network(self) -> List[Dict[str, Any]]:
        # Offline file preferred; network only as last resort, rate-limited.
        sample = [
            {"date": "2026-01-26", "name": "Republic Day", "type": "national"},
            {"date": "2026-08-15", "name": "Independence Day", "type": "national"},
            {"date": "2026-10-21", "name": "Diwali", "type": "festival"},
            {"date": "2026-03-05", "name": "Holi", "type": "festival"},
            {"date": "2026-03-19", "name": "Eid al-Fitr", "type": "festival"},
            {"date": "2026-12-25", "name": "Christmas", "type": "festival"},
        ]
        try:
            req = _import_requests()
            if req is None:
                return sample
            # Nager.at public API, no key required.
            url = "https://date.nager.at/api/v3/publicholidays/2026/IN"
            resp = req.get(url, timeout=8)
            if resp.status_code != 200:
                return sample
            data = resp.json()
            if not isinstance(data, list):
                return sample
            items: List[Dict[str, Any]] = []
            for entry in data[:60]:
                d = entry.get("date", "")
                name = entry.get("name", "Holiday")
                items.append({"date": d, "name": name, "type": "public"})
            return items
        except Exception:
            return sample


def _round_rect_path(cr: Any, x: float, y: float, w: float, h: float, r: float) -> None:
    _round_rect_path(cr, x, y, w, h, r)


# ----------------------------------------------------------------------
# Window
# ----------------------------------------------------------------------
class SamayWindow(Gtk.Window):
    __gtype_name__ = "SamayWindow"

    def __init__(self, app: SamayApp) -> None:
        super().__init__(title=_APP_TITLE, type=Gtk.WindowType.TOPLEVEL)
        self.set_name("SamayWindow")
        self.set_decorated(False)
        self.set_resizable(True)
        self.set_default_size(WINDOW_SIZE_W, WINDOW_SIZE_H)
        self.set_size_request(WINDOW_MIN_W, WINDOW_MIN_H)
        self.set_position(Gtk.WindowPosition.CENTER)
        self.app = app

        # RGBA visual
        screen = self.get_screen()
        rgba_visual = screen.get_rgba_visual()
        if rgba_visual is not None:
            self.set_visual(rgba_visual)
        self.set_app_paintable(True)
        self.set_opacity(app.current_opacity)

        # CSS border radius
        css_provider = Gtk.CssProvider()
        css_provider.load_from_data(
            b"""
            window#SamayWindow {
                border-radius: 18px;
                background-color: rgba(0,0,0,0);
            }
            """,
        )
        Gtk.StyleContext.add_provider_for_screen(
            screen,
            css_provider,
            Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION,
        )

        # Layout
        main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        main_box.set_name("SamayMainWindow")
        main_box.set_homogeneous(False)

        self.topbar = _TopBar(self, SIDEBAR_WIDTH, HEADER_HEIGHT, app)
        self.sidebar = _Sidebar(app, app.current_module)
        self.content = Gtk.DrawingArea()
        self.content.set_name("SamayContent")
        self.content.set_size_request(760, 600)

        self.content.connect("draw", self._on_content_draw)

        main_box.pack_start(self.topbar, False, False, 0)
        main_box.pack_start(self.sidebar, False, True, 0)
        main_box.pack_start(self.content, True, True, 0)

        self.add(main_box)
        self.show_all()

        self._module_renderer = _ModuleRenderer(app)

    def queue_draw_all(self) -> None:
        if self.content is not None:
            self.content.queue_draw()

    # ------------------------------------------------------------------
    def start_live_draw(self) -> None:
        if self._live_timer_id is not None:
            return
        self._live_timer_id = GLib.timeout_add(33, self._live_tick)

    def stop_live_draw(self) -> None:
        if self._live_timer_id is not None:
            GLib.source_remove(self._live_timer_id)
            self._live_timer_id = None

    def _live_tick(self) -> bool:
        self.content.queue_draw()
        return True

    # ------------------------------------------------------------------
    def _on_content_draw(self, area: Gtk.DrawingArea, cr: Any) -> bool:
        if _cairo is None:
            return False
        width = area.get_allocated_width()
        height = area.get_allocated_height()
        self.app._module_renderer.draw_background(cr, width, height, self.app)
        self.app._module_renderer.draw_module(cr, width, height, self.app)
        return False


# ----------------------------------------------------------------------
# Module renderer (background + foreground)
# ----------------------------------------------------------------------
class _ModuleRenderer:
    def __init__(self, app: SamayApp) -> None:
        self.app = app

    # ------------------------------------------------------------------
    def draw_background(self, cr: Any, width: float, height: float, app: SamayApp) -> None:
        if _cairo is None:
            return
        weather = app.weather_state or {}
        is_day = bool(int(weather.get("is_day", 1) or 1))
        if is_day:
            self._draw_day_sky(cr, width, height)
        else:
            self._draw_night_sky(cr, width, height)
        code = int(weather.get("weather_code", 0) or 0)
        self._draw_weather_particles(cr, width, height, code)

    # ------------------------------------------------------------------
    def _draw_day_sky(self, cr: Any, width: float, height: float) -> None:
        grad = _cairo.LinearGradient(0.0, 0.0, 0.0, height)
        grad.add_color_stop_rgba(0.0, *DAY_TOP)
        grad.add_color_stop_rgba(1.0, *DAY_BOTTOM)
        cr.set_source(grad)
        cr.paint()

        sun_x = width * 0.86
        sun_y = height * 0.18
        self._draw_sun(cr, sun_x, sun_y, 48, _hex_to_rgba("#FFB800"), _hex_to_rgba("#FFD24A"))
        self._draw_cloud(cr, width * 0.18, height * 0.28, 70, (0.90, 0.92, 0.97, 0.85))
        self._draw_cloud(cr, width * 0.60, height * 0.20, 80, (0.90, 0.92, 0.97, 0.90))

    # ------------------------------------------------------------------
    def _draw_night_sky(self, cr: Any, width: float, height: float) -> None:
        grad = _cairo.LinearGradient(0.0, 0.0, 0.0, height)
        grad.add_color_stop_rgba(0.0, *NIGHT_TOP)
        grad.add_color_stop_rgba(1.0, *NIGHT_BOTTOM)
        cr.set_source(grad)
        cr.paint()

        moon_x = width * 0.18
        moon_y = height * 0.18
        self._draw_moon(cr, moon_x, moon_y, 44)

        seed = int(width * 7 + height * 13)
        rng: List[int] = []
        x = seed
        for _ in range(90):
            x = (x * 1103515245 + 12345) & 0x7fffffff
            rng.append(x)
        for i in range(80):
            sx = (rng[i % len(rng)] % 100000) / 100000.0 * width
            rng2 = (rng[(i + 3) % len(rng)] % 100000) / 100000.0
            sy = rng2 * height * 0.8
            sz = 1.1 + ((rng[(i + 7) % len(rng)] % 1000) / 1000.0) * 1.6
            alpha = 0.65 + ((rng[(i + 11) % len(rng)] % 1000) / 1000.0) * 0.35
            cr.set_source_rgba(1.0, 1.0, 1.0, alpha)
            cr.arc(sx, sy, sz, 0.0, 2.0 * math.pi)
            cr.fill()

    # ------------------------------------------------------------------
    def _draw_sun(self, cr: Any, x: float, y: float, r: float, outer: Tuple[float, float, float, float], inner: Tuple[float, float, float, float]) -> None:
        cr.set_source_rgba(*outer)
        cr.arc(x, y, r, 0.0, 2.0 * math.pi)
        cr.fill()
        cr.set_source_rgba(*inner)
        cr.arc(x, y, r * 0.72, 0.0, 2.0 * math.pi)
        cr.fill()

    # ------------------------------------------------------------------
    def _draw_moon(self, cr: Any, x: float, y: float, r: float) -> None:
        cr.set_source_rgb(0.95, 0.96, 0.98)
        cr.arc(x, y, r, 0.0, 2.0 * math.pi)
        cr.fill()
        cr.set_source_rgb(0.04, 0.05, 0.10)
        cr.arc(x + r * 0.26, y - r * 0.12, r, 0.0, 2.0 * math.pi)
        cr.fill()

    # ------------------------------------------------------------------
    def _draw_cloud(self, cr: Any, x: float, y: float, r: float, color: Tuple[float, float, float, float]) -> None:
        cr.set_source_rgba(*color)
        cr.arc(x - r * 0.40, y + r * 0.22, r * 0.70, 0.0, 2.0 * math.pi)
        cr.arc(x + r * 0.18, y + r * 0.18, r * 0.80, 0.0, 2.0 * math.pi)
        cr.arc(x + r * 0.66, y + r * 0.26, r * 0.62, 0.0, 2.0 * math.pi)
        cr.arc(x + r * 0.22, y + r * 0.40, r * 0.52, 0.0, 2.0 * math.pi)
        cr.fill()

    # ------------------------------------------------------------------
    def _draw_weather_particles(self, cr: Any, width: float, height: float, code: int) -> None:
        code = int(code)
        if 0 <= code <= 3:
            return
        if code in (45, 48):
            self._draw_rain(cr, width, height, 0.35)
            return
        if 51 <= code <= 67:
            self._draw_rain(cr, width, height, 0.55)
            return
        if 71 <= code <= 77:
            self._draw_snow(cr, width, height)
            return
        if 95 <= code <= 99:
            self._draw_thunderstorm(cr, width, height)
            return

    # ------------------------------------------------------------------
    def _draw_rain(self, cr: Any, width: float, height: float, opacity: float) -> None:
        for p in self.app._particles:
            x = p.get("x", 0.0) % width
            y = p.get("y", 0.0) % height
            cr.set_source_rgba(0.50, 0.60, 0.80, opacity)
            cr.set_line_width(1.0)
            cr.move_to(x, y)
            cr.line_to(x - 2.0, y + 9.0)
            cr.stroke()

    # ------------------------------------------------------------------
    def _draw_snow(self, cr: Any, width: float, height: float) -> None:
        for p in self.app._particles:
            x = p.get("x", 0.0) % width
            y = p.get("y", 0.0) % height
            cr.set_source_rgba(1.0, 1.0, 1.0, 0.88)
            cr.arc(x, y, 2.0, 0.0, 2.0 * math.pi)
            cr.fill()

    # ------------------------------------------------------------------
    def _draw_thunderstorm(self, cr: Any, width: float, height: float) -> None:
        self._draw_rain(cr, width, height, 0.65)
        if self.app._particles and self.app._particles[0].get("flash", False):
            cr.set_source_rgba(1.0, 1.0, 1.0, 0.22)
            cr.rectangle(0.0, 0.0, width, height)
            cr.fill()

    # ------------------------------------------------------------------
    def draw_module(self, cr: Any, width: float, height: float, app: SamayApp) -> None:
        module = app.current_module
        if module == "clock":
            self._draw_clock_module(cr, width, height, app)
        elif module == "countdown":
            self._draw_countdown_module(cr, width, height, app)
        elif module == "stopwatch":
            self._draw_stopwatch_module(cr, width, height, app)
        elif module == "world":
            self._draw_world_module(cr, width, height, app)
        elif module == "alarm":
            self._draw_alarm_module(cr, width, height, app)
        elif module == "calendar":
            self._draw_calendar_module(cr, width, height, app)
        else:
            self._draw_module_card(cr, width, height, module)

    # ------------------------------------------------------------------
    def _draw_module_card(self, cr: Any, width: float, height: float, module: str) -> None:
        x0 = 48.0
        y0 = 80.0
        w = max(200.0, width - 96.0)
        h = max(200.0, height - 160.0)
        cr.set_source_rgba(*CARD_BG_RGBA)
        _round_rect_path(cr, x0, y0, w, h, 20.0)
        cr.fill()
        cr.set_source_rgba(*CARD_BORDER_RGBA)
        cr.set_line_width(1.0)
        _round_rect_path(cr, x0, y0, w, h, 20.0)
        cr.stroke()

        label = _MODULE_LABEL.get(module, module.title())
        self._draw_text(cr, label, width / 2.0, y0 + 60.0, FONT_UI_BOLD, 1.0, 1.0, 1.0, 0.95)
        self._draw_text(cr, "Module view", width / 2.0, y0 + 92.0, FONT_UI, 1.0, 1.0, 1.0, 0.55)
        self._draw_text(cr, "Full implementation follows.", width / 2.0, y0 + 118.0, FONT_UI, 1.0, 1.0, 1.0, 0.45)

    # ------------------------------------------------------------------
    def _draw_text(
        self,
        cr: Any,
        text: str,
        x: float,
        y: float,
        font_desc: str,
        r: float,
        g: float,
        b: float,
        a: float = 1.0,
    ) -> None:
        if _cairo is None:
            return
        cr.set_source_rgba(r, g, b, a)
        layout = PangoCairo.create_layout(cr)
        layout.set_font_description(Pango.FontDescription(font_desc))
        layout.set_text(text, -1)
        ink, _logical = layout.get_pixel_extents()
        cr.move_to(x - ink.width / 2.0, y - ink.height / 2.0)
        PangoCairo.show_layout(cr, layout)

    # ------------------------------------------------------------------
    def _draw_clock_module(self, cr: Any, width: float, height: float, app: SamayApp) -> None:
        # Analog clock (center-left)
        cx = width * 0.36
        cy = height * 0.54
        R = min(width * 0.30, height * 0.36, 160.0)

        # face
        cr.set_line_width(0.0)
        cr.set_source_rgba(1.0, 1.0, 1.0, 0.05)
        cr.arc(cx, cy, R, 0.0, 2.0 * math.pi)
        cr.fill()
        cr.set_source_rgba(1.0, 1.0, 1.0, 0.18)
        cr.set_line_width(1.2)
        cr.arc(cx, cy, R - 10.0, 0.0, 2.0 * math.pi)
        cr.stroke()

        # ticks
        for i in range(12):
            ang = i * 30.0 * math.pi / 180.0
            x0 = cx + (R - 18.0) * math.cos(ang)
            y0 = cy + (R - 18.0) * math.sin(ang)
            x1 = cx + (R - 6.0) * math.cos(ang)
            y1 = cy + (R - 6.0) * math.sin(ang)
            cr.set_source_rgba(1.0, 1.0, 1.0, 0.90)
            cr.set_line_width(2.2)
            cr.move_to(x0, y0)
            cr.line_to(x1, y1)
            cr.stroke()
        for i in range(60):
            if i % 5 == 0:
                continue
            ang = i * 6.0 * math.pi / 180.0
            x0 = cx + (R - 18.0) * math.cos(ang)
            y0 = cy + (R - 18.0) * math.sin(ang)
            x1 = cx + (R - 8.0) * math.cos(ang)
            y1 = cy + (R - 8.0) * math.sin(ang)
            cr.set_source_rgba(1.0, 1.0, 1.0, 0.40)
            cr.set_line_width(1.0)
            cr.move_to(x0, y0)
            cr.line_to(x1, y1)
            cr.stroke()

        # hands
        now = _now()
        hour = now.hour % 12
        minute = now.minute
        second = now.second
        ms = now.microsecond / 1000.0
        hour_angle = hour * 30.0 + minute * 0.5
        minute_angle = minute * 6.0 + second * 0.1
        second_angle = second * 6.0 + ms * 0.006

        self._draw_hand(cr, cx, cy, R * 0.56, hour_angle, "#FFFFFF", 7.0)
        self._draw_hand(cr, cx, cy, R * 0.78, minute_angle, "#FFFFFF", 4.5)
        self._draw_hand(cr, cx, cy, R * 0.84, second_angle, "#FF5F57", 2.0)
        cr.set_source_rgb(0.10, 0.11, 0.14)
        cr.arc(cx, cy, 6.0, 0.0, 2.0 * math.pi)
        cr.fill()
        cr.set_source_rgb(1.0, 1.0, 1.0)
        cr.arc(cx, cy, 2.4, 0.0, 2.0 * math.pi)
        cr.fill()

        # digital (center)
        digital = app.digital_str
        if digital == "AM":
            digital = "12:00:00 AM"
        self._draw_text(cr, digital, width * 0.56, height * 0.52, FONT_CLOCK_DIGITAL, 1.0, 1.0, 1.0, 1.0)
        self._draw_text(cr, "Samay", width * 0.56, height * 0.52 + 46.0, FONT_CLOCK_LABEL, 1.0, 1.0, 1.0, 0.55)

        # weather widget top-right
        self._draw_weather_widget(cr, width, height, app.weather_state)

        # hint
        self._draw_text(cr, "Live weather · Open-Meteo", width * 0.56, height * 0.52 + 74.0, FONT_CLOCK_LABEL, 1.0, 1.0, 1.0, 0.45)

    # ------------------------------------------------------------------
    def _draw_hand(self, cr: Any, cx: float, cy: float, length: float, angle_deg: float, color: str, width: float) -> None:
        rad = angle_deg * math.pi / 180.0
        x = cx + length * math.sin(rad)
        y = cy - length * math.cos(rad)
        cr.set_source_rgb(*_color_parse_cairo(color))
        cr.set_line_width(width)
        cr.set_line_cap(_cairo.LINE_CAP_ROUND if _cairo else 0)
        cr.move_to(cx, cy)
        cr.line_to(x, y)
        cr.stroke()

    # ------------------------------------------------------------------
    def _draw_weather_widget(self, cr: Any, width: float, height: float, weather: Dict[str, Any]) -> None:
        temp = weather.get("temperature_2m")
        city = weather.get("city", "")
        code = weather.get("weather_code")
        wx = width - 260.0
        wy = 24.0
        icon_size = 46.0
        self._draw_weather_icon(cr, code, wx, wy, icon_size)
        if temp is not None:
            self._draw_text(cr, f"{int(round(temp))}°C", wx + 90.0, wy + 12.0, FONT_WEATHER_TEMP, 1.0, 1.0, 1.0, 1.0)
        if city:
            self._draw_text(cr, city, wx + 90.0, wy + 44.0, FONT_WEATHER_CITY, 1.0, 1.0, 1.0, 0.80)

    # ------------------------------------------------------------------
    def _draw_weather_icon(self, cr: Any, code: Optional[int], x: float, y: float, size: float) -> None:
        if code is None:
            return
        code = int(code)
        if 0 <= code <= 3:
            self._draw_icon_sun(cr, x, y, size)
        elif code in (45, 48):
            self._draw_icon_cloud(cr, x, y, size)
        elif 51 <= code <= 67:
            self._draw_icon_rain(cr, x, y, size)
        elif 71 <= code <= 77:
            self._draw_icon_snow(cr, x, y, size)
        elif 95 <= code <= 99:
            self._draw_icon_storm(cr, x, y, size)
        else:
            self._draw_icon_sun(cr, x, y, size)

    # ------------------------------------------------------------------
    def _draw_icon_sun(self, cr: Any, x: float, y: float, size: float) -> None:
        cx = x + size
        cy = y + size
        cr.set_source_rgb(1.0, 0.72, 0.0)
        cr.arc(cx, cy, size * 0.78, 0.0, 2.0 * math.pi)
        cr.fill()
        cr.set_source_rgb(1.0, 0.82, 0.29)
        cr.arc(cx, cy, size * 0.44, 0.0, 2.0 * math.pi)
        cr.fill()

    # ------------------------------------------------------------------
    def _draw_icon_cloud(self, cr: Any, x: float, y: float, size: float) -> None:
        cr.set_source_rgba(0.78, 0.82, 0.88, 1.0)
        cr.arc(x + size * 0.95, y + size * 1.18, size * 0.54, 0.0, 2.0 * math.pi)
        cr.arc(x + size * 1.32, y + size * 0.98, size * 0.48, 0.0, 2.0 * math.pi)
        cr.arc(x + size * 0.62, y + size * 0.86, size * 0.42, 0.0, 2.0 * math.pi)
        cr.fill()

    # ------------------------------------------------------------------
    def _draw_icon_rain(self, cr: Any, x: float, y: float, size: float) -> None:
        cr.set_source_rgba(0.62, 0.66, 0.74, 1.0)
        cr.arc(x + size, y + size, size * 0.40, 0.0, 2.0 * math.pi)
        cr.arc(x + size * 1.36, y + size * 0.86, size * 0.36, 0.0, 2.0 * math.pi)
        cr.arc(x + size * 0.70, y + size * 0.70, size * 0.30, 0.0, 2.0 * math.pi)
        cr.fill()

    # ------------------------------------------------------------------
    def _draw_icon_snow(self, cr: Any, x: float, y: float, size: float) -> None:
        cr.set_source_rgba(0.90, 0.92, 0.96, 1.0)
        cr.arc(x + size, y + size, size * 0.40, 0.0, 2.0 * math.pi)
        cr.arc(x + size * 1.36, y + size * 0.86, size * 0.36, 0.0, 2.0 * math.pi)
        cr.arc(x + size * 0.70, y + size * 0.70, size * 0.30, 0.0, 2.0 * math.pi)
        cr.fill()

    # ------------------------------------------------------------------
    def _draw_icon_storm(self, cr: Any, x: float, y: float, size: float) -> None:
        cr.set_source_rgba(0.40, 0.44, 0.52, 1.0)
        cr.arc(x + size, y + size, size * 0.40, 0.0, 2.0 * math.pi)
        cr.arc(x + size * 1.36, y + size * 0.86, size * 0.36, 0.0, 2.0 * math.pi)
        cr.fill()

    # ------------------------------------------------------------------
    def _draw_countdown_module(self, cr: Any, width: float, height: float, app: SamayApp) -> None:
        self._draw_module_card(cr, width, height, "Countdown")
        self._draw_text(cr, "HH:MM:SS picker · circular progress · start/pause (Space) · reset (R)", width / 2.0, height - 40.0, FONT_UI, 1.0, 1.0, 1.0, 0.5)

    # ------------------------------------------------------------------
    def _draw_stopwatch_module(self, cr: Any, width: float, height: float, app: SamayApp) -> None:
        self._draw_module_card(cr, width, height, "Stopwatch")
        self._draw_text(cr, "Lap list · max 100 laps · export ~/.samay/laps.csv · Space/L/R", width / 2.0, height - 40.0, FONT_UI, 1.0, 1.0, 1.0, 0.5)

    # ------------------------------------------------------------------
    def _draw_world_module(self, cr: Any, width: float, height: float, app: SamayApp) -> None:
        self._draw_module_card(cr, width, height, "World Clock")
        self._draw_text(cr, "Default cities + search-add (pytz.all_timezones) · saved ~/.samay/world.json", width / 2.0, height - 40.0, FONT_UI, 1.0, 1.0, 1.0, 0.5)

    # ------------------------------------------------------------------
    def _draw_alarm_module(self, cr: Any, width: float, height: float, app: SamayApp) -> None:
        self._draw_module_card(cr, width, height, "Alarm")
        self._draw_text(cr, "Time picker · repeat · sound · label · checked every second", width / 2.0, height - 40.0, FONT_UI, 1.0, 1.0, 1.0, 0.5)

    # ------------------------------------------------------------------
    def _draw_calendar_module(self, cr: Any, width: float, height: float, app: SamayApp) -> None:
        self._draw_module_card(cr, width, height, "Calendar")
        self._draw_text(cr, "Monthly grid · Indian holidays · cached festivals", width / 2.0, height - 40.0, FONT_UI, 1.0, 1.0, 1.0, 0.5)


# ----------------------------------------------------------------------
# Entry
# ----------------------------------------------------------------------
def main() -> int:
    app = SamayApp()
    return app.run(sys.argv)


if __name__ == "__main__":
    raise SystemExit(main())
