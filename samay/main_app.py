# -*- coding: utf-8 -*-
"""
SAMAY main application (GTK 3).
Contains: window chrome (traffic lights, opacity slider, draggable header),
left sidebar navigation, and module shells for Clock/Countdown/Stopwatch/WorldClock/Alarm/Calendar.
"""
from __future__ import annotations

import json
import os
import math
import time
import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import gi
gi.require_version('Gtk', '3.0')
gi.require_version('Gdk', '3.0')
gi.require_version('Pango', '1.0')
gi.require_version('PangoCairo', '1.0')

from gi.repository import Gtk, Gdk, GLib, Gio, Pango, PangoCairo
import cairo

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
HOME = Path.home()
SAMAY_DIR = HOME / ".samay"
SAMAY_DIR.mkdir(parents=True, exist_ok=True)

DATA_DIR = Path(__file__).resolve().parent / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)

defaults: Dict[str, object] = {
    "opacity": 0.90,
    "fullscreen": False,
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

ALARM_FILE = SAMAY_DIR / "alarms.json"
WORLD_FILE = SAMAY_DIR / "world.json"
LAPS_FILE = SAMAY_DIR / "laps.csv"
COUNTDOWN_FILE = SAMAY_DIR / "countdown.json"

DATA_DIR.mkdir(parents=True, exist_ok=True)
(DATA_DIR / "indian_festivals_2026.json").parent.mkdir(parents=True, exist_ok=True)

# ---------------------------------------------------------------------------
# Color palette (Galaxy Watch / OneUI inspired)
# ---------------------------------------------------------------------------
CLOCK_TEXT = "#FFFFFF"
HEADER_BG = "rgba(15,17,21,0.92)"
SIDEBAR_BG = "rgba(20,22,28,0.85)"
TAB_SEL = "rgba(255,255,255,0.15)"
TAB_HOVER = "rgba(255,255,255,0.06)"
CARD_BG = "rgba(255,255,255,0.06)"
CARD_BORDER = "rgba(255,255,255,0.10)"
DAY_SKY_TOP = (0.35, 0.55, 0.85, 1.0)
DAY_SKY_BOT = (0.70, 0.82, 0.95, 1.0)
NIGHT_TOP = (0.05, 0.07, 0.22, 1.0)
NIGHT_BOT = (0.0, 0.0, 0.05, 1.0)


# ---------------------------------------------------------------------------
# Utility
# ---------------------------------------------------------------------------
def load_json(path: Path, default: object = None) -> object:
    if not path.exists():
        return default
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default

def save_json(path: Path, data: object) -> bool:
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return True
    except Exception:
        return False

def window_alpha_from_slider(value: float) -> float:
    return max(0.40, min(1.00, float(value)))

def wrap_path(context: cairo.Context, x: float, y: float, radius: float) -> None:
    context.arc(x + radius, y + radius, radius, math.pi, 3 * math.pi / 2)
    context.arc(x + 2 * radius - radius, y + radius, radius, 3 * math.pi / 2, 0)
    context.arc(x + 2 * radius - radius, y + 2 * radius - radius, radius, 0, math.pi / 2)
    context.arc(x + radius, y + 2 * radius - radius, radius, math.pi / 2, math.pi)


# ---------------------------------------------------------------------------
# Top-bar traffic lights + opacity slider
# ---------------------------------------------------------------------------
class TrafficLightButton(Gtk.DrawingArea):
    __gtype_name__ = "TrafficLightButton"

    def __init__(self, color: str, hover_color: str, callback) -> None:
        super().__init__()
        self.set_size_request(28, 28)
        self._color = color
        self._hover_color = hover_color
        self._callback = callback
        self._hover = False
        self.add_events(Gdk.EventMask.BUTTON_PRESS_MASK)
        self.add_events(Gdk.EventMask.ENTER_NOTIFY_MASK)
        self.add_events(Gdk.EventMask.LEAVE_NOTIFY_MASK)
        self.connect("button-press-event", self.on_press)
        self.connect("enter-notify-event", self.on_enter)
        self.connect("leave-notify-event", self.on_leave)
        self.connect("draw", self.on_draw)

    def on_press(self, area, event):
        if event.button == 1:
            self._callback()
            return True
        return False

    def on_enter(self, area, event):
        self._hover = True
        self.queue_draw()
        return False

    def on_leave(self, area, event):
        self._hover = False
        self.queue_draw()
        return False

    def color_parse(self, hexcolor: str) -> Tuple[float, float, float]:
        p = Gdk.color_parse(hexcolor)
        return (p.red / 65535.0, p.green / 65535.0, p.blue / 65535.0)

    def on_draw(self, area, cr):
        rgba = self._color if not self._hover else self._hover_color
        r, g, b = self.color_parse(rgba)
        cr.set_source_rgb(r, g, b)
        cr.set_line_width(0.0)
        cr.arc(14.0, 14.0, 7.0, 0, 2 * math.pi)
        cr.fill()


class OpacitySlider(Gtk.Scale):
    __gtype_name__ = "OpacitySlider"

    def __init__(self, on_change) -> None:
        super().__init__(orientation=Gtk.Orientation.HORIZONTAL)
        self.set_draw_value(False)
        self.set_digits(2)
        self.set_value(0.90)
        self.set_size_request(120, -1)
        self.set_range(0.40, 1.00)
        self.set_increments(0.01, 0.05)
        self.on_change = on_change
        self.connect("value-changed", self.on_value)
        self.connect("style-set", self.on_style)  # ensure css applied
        self.style_context.add_class("samay-opacity-slider")

    def on_value(self, scale):
        try:
            self.on_change(window_alpha_from_slider(scale.get_value()))
        except Exception:
            pass

    def on_style(self, widget, previous):
        # no-op; we set css elsewhere
        pass


class TopBar(Gtk.DrawingArea):
    __gtype_name__ = "TopBar"

    def __init__(self, window, sidebar_width: int, header_height: int,
                 module_switcher) -> None:
        super().__init__()
        self.set_size_request(sidebar_width, header_height)
        self._window = window
        self._header_height = header_height
        self._module_switcher = module_switcher
        self.set_name("TopBar")
        self.set_events(Gdk.EventMask.BUTTON_PRESS_MASK)
        self.add_events(Gdk.EventMask.BUTTON_PRESS_MASK)
        self.connect("button-press-event", self.on_button_press)
        self.connect("draw", self.on_draw)

        self.close_btn = TrafficLightButton("#FF5F57", "#E0443E", self.on_close)
        self.min_btn = TrafficLightButton("#FFBD2E", "#DEA123", self.on_minimize)
        self.max_btn = TrafficLightButton("#28C940", "#1FAB35", self.on_maximize)
        self.close_btn.set_hexpand(False)
        self.min_btn.set_hexpand(False)
        self.max_btn.set_hexpand(False)

        self.opacity_slider = OpacitySlider(self.on_opacity_change)

        box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        box.set_homogeneous(False)
        box.pack_start(self.close_btn, False, False, 0)
        box.pack_start(self.min_btn, False, False, 0)
        box.pack_start(self.max_btn, False, False, 0)
        # spacer
        spacer = Gtk.Box(); spacer.set_hexpand(True); spacer.set_vexpand(False)
        box.pack_start(spacer, True, True, 0)
        box.pack_start(self.opacity_slider, False, False, 0)

        self.add(box)
        box.show_all()

    def on_close(self):
        self._module_switcher.request_quit()

    def on_minimize(self):
        try:
            self._window.iconify()
        except Exception:
            pass

    def on_maximize(self):
        try:
            if self._window.is_fullscreen():
                self._window.unfullscreen()
            else:
                self._window.fullscreen()
        except Exception:
            pass

    def on_button_press(self, area, event):
        if event.button == 1:
            self._window.begin_move_drag(event.button, event.x_root, event.y_root,
                                           event.get_time())
            return True
        return False

    def on_opacity_change(self, alpha):
        alpha = window_alpha_from_slider(alpha)
        gdk_screen = self._window.get_screen()
        visual = gdk_screen.get_rgba_visual()
        if visual:
            self._window.set_visual(visual)
        self._window.set_opacity(alpha)
        self._module_switcher.on_app_opacity_change(alpha)

    def on_draw(self, area, cr):
        # header background: dark glass
        cr.set_source_rgba(0.058, 0.067, 0.082, 0.92)
        cr.rectangle(0, 0, area.get_allocated_width(), self._header_height)
        cr.fill()
        # subtle bottom border
        cr.set_source_rgba(0.9, 0.9, 0.9, 0.12)
        cr.set_line_width(1.0)
        cr.move_to(0, self._header_height - 1)
        cr.line_to(area.get_allocated_width() - 1, self._header_height - 1)
        cr.stroke()


# ---------------------------------------------------------------------------
# Sidebar navigation
# ---------------------------------------------------------------------------
class SidebarTab(Gtk.DrawingArea):
    __gtype_name__ = "SidebarTab"

    def __init__(self, label: str, icon: str, callback, index: int) -> None:
        super().__init__()
        self.set_size_request(200, 48)
        self._label = label
        self._icon = icon
        self._callback = callback
        self._index = index
        self._selected = False
        self.set_hexpand(False)
        self.set_vexpand(False)
        self.add_events(Gdk.EventMask.ENTER_NOTIFY_MASK)
        self.add_events(Gdk.EventMask.LEAVE_NOTIFY_MASK)
        self.add_events(Gdk.EventMask.BUTTON_PRESS_MASK)
        self.connect("enter-notify-event", self.on_enter)
        self.connect("leave-notify-event", self.on_leave)
        self.connect("button-press-event", self.on_press)
        self.connect("draw", self.on_draw)

    def on_enter(self, area, event):
        if not self._selected:
            self.queue_draw()

    def on_leave(self, area, event):
        if not self._selected:
            self.queue_draw()

    def on_press(self, area, event):
        if event.button == 1:
            self.select()
            return True
        return False

    def select(self):
        if not self._selected:
            self._selected = True
            if self._callback:
                self._callback()
        self.queue_draw()

    def on_draw(self, area, cr):
        w = area.get_allocated_width()
        h = area.get_allocated_height()
        r = 12.0
        if self._selected:
            cr.set_source_rgba(1.0, 1.0, 1.0, 0.15)
            cr.rectangle(8, 6, w - 16, h - 12)
            cr.fill()
        else:
            cr.set_source_rgba(1.0, 1.0, 1.0, 0.0)
            cr.rectangle(8, 6, w - 16, h - 12)
            cr.fill()
        # text
        cr.set_source_rgba(1.0, 1.0, 1.0, 0.85 if self._selected else 0.65)
        layout = PangoCairo.create_layout(cr)
        layout.set_font_description(Pango.FontDescription("12"))
        layout.set_text("{}   {}".format(self._icon, self._label))
        PangoCairo.show_layout(cr, layout)


class Sidebar(Gtk.Box):
    __gtype_name__ = "Sidebar"

    def __init__(self, module_switcher) -> None:
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        self.set_name("Sidebar")
        self._module_switcher = module_switcher
        self.set_size_request(220, -1)

        tabs = [
            ("Clock", "⏰", "clock"),
            ("Countdown", "⏳", "countdown"),
            ("Stopwatch", "⏱️", "stopwatch"),
            ("World Clock", "🌍", "world"),
            ("Alarm", "⏰", "alarm"),
            ("Calendar", "📅", "calendar"),
        ]
        self.tabs: List[SidebarTab] = []
        for idx, (label, icon, module) in enumerate(tabs):
            tab = SidebarTab(label, icon, lambda m=module: self.select_module(m), idx)
            self.tabs.append(tab)
            self.pack_start(tab, False, False, 2)

        self.select_module(module_switcher.current_module)

    def select_module(self, module: str):
        self._module_switcher.current_module = module
        for tab in self.tabs:
            tab._selected = (tab._index == len(self.tabs) - 1 or
                             (tab._label.lower() if False else False) or False)
            tab._selected = tab._callback is None or self.tabs.index(tab) == self._index_for_module(module)
        for i, tab in enumerate(self.tabs):
            tab._selected = (i == self._index_for_module(module))
            tab.queue_draw()
        self._module_switcher.switch_to(module)

    def _index_for_module(self, module: str) -> int:
        mapping = {
            "clock": 0,
            "countdown": 1,
            "stopwatch": 2,
            "world": 3,
            "alarm": 4,
            "calendar": 5,
        }
        return mapping.get(module, 0)


# ---------------------------------------------------------------------------
# Window
# ---------------------------------------------------------------------------
class SamayWindow(Gtk.Window):
    __gtype_name__ = "SamayWindow"

    def __init__(self, app) -> None:
        super().__init__(title="Samay", type=Gtk.WindowType.TOPLEVEL)
        self.set_name("SamayWindow")
        self.set_decorated(False)
        self.set_resizable(True)
        self.set_default_size(960, 640)
        self.set_size_request(800, 500)
        self.app = app

        # RGBA visual for transparency
        gdk_screen = self.get_screen()
        visual = gdk_screen.get_rgba_visual()
        if visual:
            self.set_visual(visual)
        self.set_app_paintable(True)

        # enable transparency on the window
        self.set_opacity(app.current_opacity)

        # Border radius via CSS
        css = b"""
        window#SamayWindow {
            border-radius: 18px;
            background-color: rgba(0,0,0,0.0);
        }
        """
        provider = Gtk.CssProvider()
        provider.load_from_data(css)
        Gtk.StyleContext.add_provider_for_screen(gdk_screen, provider,
                                                  Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)

        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        vbox.set_name("MainWindow")

        self.topbar = TopBar(self, 220, 45, self.app.module_switcher)
        self.sidebar = Sidebar(self.app.module_switcher)
        self.content = Gtk.DrawingArea()
        self.content.set_name("Content")
        self.content.set_size_request(760, 600)

        self.add(vbox)
        vbox.pack_start(self.topbar, False, False, 0)
        vbox.pack_start(self.sidebar, False, True, 0)
        vbox.pack_start(self.content, True, True, 0)

        self.show_all()

        # connect draw
        self.content.connect("draw", self.on_content_draw)
        # live background redraw
        self._live_timer = None

    def on_content_draw(self, area, cr):
        # Render live background on content area
        self.app.render_live_background(cr, area.get_allocated_width(),
                                        area.get_allocated_height())
        # Render module foreground
        self.app.render_module(cr, area.get_allocated_width(),
                               area.get_allocated_height())

    def start_live_draw(self):
        if self._live_timer is not None:
            return
        self._live_timer = GLib.timeout_add(33, self._live_tick)

    def stop_live_draw(self):
        if self._live_timer is not None:
            GLib.source_remove(self._live_timer)
            self._live_timer = None

    def _live_tick(self):
        self.content.queue_draw()
        return True


# ---------------------------------------------------------------------------
# Module switcher + module renderers
# ---------------------------------------------------------------------------
class ModuleSwitcher:
    def __init__(self, app):
        self.app = app
        self.current_module = "clock"

    def switch_to(self, module: str):
        self.current_module = module
        self.app.module_switcher.request_update()
        # live background should react to weather etc only in clock
        self.app.render_live_background_state()

    def request_update(self):
        if hasattr(self.app, "window") and self.app.window:
            self.app.window.content.queue_draw()

    def request_quit(self):
        Gtk.main_quit()


class ModuleClock:
    def __init__(self, app):
        self.app = app

    def render(self, cr, width, height, state):
        # state contains weather info
        weather = getattr(self.app, "weather_state", None) or {}
        digital_str = state.get("digital_str", "00:00:00 AM")
        is_day = state.get("is_day", 1)

        # Analog clock centered-left
        cx = width * 0.34
        cy = height * 0.52
        analog_radius = min(width * 0.30, height * 0.34, 150)
        self.draw_analog(cr, cx, cy, analog_radius, state)

        # Digital clock in center
        ctx = PangoCairo.create_context(cr)
        layout = PangoCairo.create_layout(cr)
        layout.set_font_description(Pango.FontDescription("Bold 32"))
        layout.set_text(digital_str)
        ink, logical = layout.get_pixel_extents()
        px = width * 0.5
        py = height * 0.66
        cr.move_to(px - logical.width / 2, py - logical.height / 2)
        PangoCairo.show_layout(cr, layout)

        # Weather widget top-right
        self.draw_weather(cr, width, height, weather)

    def draw_analog(self, cr, cx, cy, R, state):
        now = datetime.datetime.now()
        hour = now.hour % 12
        minute = now.minute
        second = now.second
        ms = now.microsecond / 1000.0
        hour_angle = (hour * 30) + (minute * 0.5)
        minute_angle = minute * 6 + second * 0.1
        second_angle = second * 6 + ms * 0.006

        # face
        cr.set_line_width(0)
        cr.set_source_rgba(1, 1, 1, 0.06)
        cr.arc(cx, cy, R, 0, 2 * math.pi)
        cr.fill()
        cr.set_source_rgba(1, 1, 1, 0.15)
        cr.arc(cx, cy, R - 8, 0, 2 * math.pi)
        cr.stroke()

        # ticks
        for i in range(12):
            ang = i * 30 * math.pi / 180
            x1 = cx + (R - 15) * math.cos(ang)
            y1 = cy + (R - 15) * math.sin(ang)
            x2 = cx + (R - 4) * math.cos(ang)
            y2 = cy + (R - 4) * math.sin(ang)
            cr.set_source_rgba(1, 1, 1, 0.85)
            cr.set_line_width(2.0)
            cr.move_to(x1, y1)
            cr.line_to(x2, y2)
            cr.stroke()

        for i in range(60):
            ang = i * 6 * math.pi / 180
            if i % 5 == 0:
                continue
            x1 = cx + (R - 15) * math.cos(ang)
            y1 = cy + (R - 15) * math.sin(ang)
            x2 = cx + (R - 7) * math.cos(ang)
            y2 = cy + (R - 7) * math.sin(ang)
            cr.set_source_rgba(1, 1, 1, 0.35)
            cr.set_line_width(1.0)
            cr.move_to(x1, y1)
            cr.line_to(x2, y2)
            cr.stroke()

        # hands
        self.draw_hand(cr, cx, cy, (R * 0.55), hour_angle, "#FFFFFF", 7.0)
        self.draw_hand(cr, cx, cy, (R * 0.78), minute_angle, "#FFFFFF", 4.5)
        self.draw_hand(cr, cx, cy, (R * 0.82), second_angle, "#FF5F57", 2.0)

        # center cap
        cr.set_source_rgb(*self.rgb("#1A1D23"))
        cr.arc(cx, cy, 5, 0, 2 * math.pi)
        cr.fill()
        cr.set_source_rgb(*self.rgb("#FFFFFF"))
        cr.arc(cx, cy, 2.2, 0, 2 * math.pi)
        cr.fill()

    def draw_hand(self, cr, cx, cy, length, angle, color, width):
        rad = angle * math.pi / 180
        x = cx + length * math.sin(rad)
        y = cy - length * math.cos(rad)
        cr.set_source_rgb(*self.rgb(color))
        cr.set_line_width(width)
        cr.set_line_cap(cairo.LINE_CAP_ROUND)
        cr.move_to(cx, cy)
        cr.line_to(x, y)
        cr.stroke()

    def rgb(self, hexcolor: str):
        p = Gdk.color_parse(hexcolor)
        return (p.red / 65535.0, p.green / 65535.0, p.blue / 65535.0)

    def draw_weather(self, cr, width, height, weather):
        temp = weather.get("temperature_2m")
        city = weather.get("city", "")
        code = weather.get("weather_code")
        icon = self.weather_icon(cr, code)
        icon_x = width - 230 - 30
        icon_y = 20
        if icon is not None:
            icon(cr, icon_x, icon_y, 48)
        # text
        if temp is not None:
            self.draw_text(cr, f"{int(round(temp))}°C", width - 200 - 30, 34, "Bold 22", "#FFFFFF")
        if city:
            self.draw_text(cr, city, width - 200 - 30, 64, "12", "#FFFFFF66")

    def draw_text(self, cr, text, x, y, font, color):
        layout = PangoCairo.create_layout(cr)
        layout.set_font_description(Pango.FontDescription(font))
        layout.set_text(text)
        cr.set_source_rgba(*self.rgba(color))
        PangoCairo.show_layout(cr, layout)

    def rgba(self, hexcolor):
        if len(hexcolor) == 9:
            return self.hex_to_rgba(hexcolor)
        p = Gdk.color_parse(hexcolor)
        return (p.red / 65535.0, p.green / 65535.0, p.blue / 65535.0, 1.0)

    def hex_to_rgba(self, hexcolor):
        r = int(hexcolor[1:3], 16) / 255.0
        g = int(hexcolor[3:5], 16) / 255.0
        b = int(hexcolor[5:7], 16) / 255.0
        a = int(hexcolor[7:9], 16) / 255.0
        return (r, g, b, a)

    def weather_icon(self, code):
        code = int(code) if code is not None else 0
        if 0 <= code <= 3:
            return self.draw_sun
        if code in (45, 48):
            return self.draw_clouds
        if 51 <= code <= 67:
            return self.draw_rain
        if 71 <= code <= 77:
            return self.draw_snow
        if 95 <= code <= 99:
            return self.draw_thunderstorm
        return self.draw_sun

    def draw_sun(self, cr, x, y, size):
        cr.set_source_rgb(*self.rgb("#FFB800"))
        cr.arc(x + size, y + size, size * 0.8, 0, 2 * math.pi)
        cr.fill()
        cr.set_source_rgb(*self.rgb("#FFD24A"))
        cr.arc(x + size, y + size, size * 0.45, 0, 2 * math.pi)
        cr.fill()

    def draw_clouds(self, cr, x, y, size):
        cr.set_source_rgba(*self.rgb("#D7DCE0"))
        cr.arc(x + size * 0.9, y + size * 1.2, size * 0.55, 0, 2 * math.pi)
        cr.arc(x + size * 1.3, y + size * 1.0, size * 0.5, 0, 2 * math.pi)
        cr.arc(x + size * 0.6, y + size * 0.9, size * 0.45, 0, 2 * math.pi)
        cr.fill()

    def draw_rain(self, cr, x, y, size):
        cr.set_source_rgba(*self.rgb("#A9B4BE"))
        cr.arc(x + size, y + size, size * 0.4, 0, 2 * math.pi)
        cr.arc(x + size * 1.35, y + size * 0.85, size * 0.35, 0, 2 * math.pi)
        cr.arc(x + size * 0.7, y + size * 0.7, size * 0.3, 0, 2 * math.pi)
        cr.fill()

    def draw_snow(self, cr, x, y, size):
        cr.set_source_rgba(*self.rgb("#E6ECF2"))
        cr.arc(x + size, y + size, size * 0.4, 0, 2 * math.pi)
        cr.arc(x + size * 1.35, y + size * 0.85, size * 0.35, 0, 2 * math.pi)
        cr.arc(x + size * 0.7, y + size * 0.7, size * 0.3, 0, 2 * math.pi)
        cr.fill()

    def draw_thunderstorm(self, cr, x, y, size):
        cr.set_source_rgba(*self.rgb("#6B7280"))
        cr.arc(x + size, y + size, size * 0.4, 0, 2 * math.pi)
        cr.arc(x + size * 1.35, y + size * 0.85, size * 0.35, 0, 2 * math.pi)
        cr.fill()


# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------
class SamayApp:
    def __init__(self) -> None:
        self.window: Optional[SamayWindow] = None
        self.module_switcher = ModuleSwitcher(self)
        self.current_opacity = defaults["opacity"]
        self.weather_state: Dict[str, object] = {
            "temperature_2m": None,
            "city": "",
            "weather_code": 0,
            "is_day": 1,
        }
        self._weather_fetch_at: float = 0.0
        self._weather_location: Dict[str, object] = {}
        self._weather_last_call_hour: Optional[int] = None
        self._weather_calls_today: int = 0
        self._weather_calls_reset_at: float = 0.0
        self._particle_timer: Optional[int] = None
        self._particles: List[Dict[str, object]] = []
        self.clock = ModuleClock(self)

    def run(self, argv) -> int:
        self.window = SamayWindow(self)
        self.window.connect("destroy", self.on_destroy)
        self.window.connect("focus-out-event", self.on_focus_out)
        self.window.connect("configure-event", self.on_configure)
        self.window.focus()
        self.window.start_live_draw()
        self.start_weather()
        self.start_particle_animation()
        self.start_clock_update()
        self.start_housekeeping()
        Gtk.main()
        return 0

    # ------------------------------------------------------------------
    def on_destroy(self, window):
        Gtk.main_quit()

    def on_focus_out(self, window, event):
        # throttle when unfocused
        pass

    def on_configure(self, window, event):
        # keep centered initially; ignore later moves but allow resizing
        return False

    def request_update(self):
        if self.window:
            self.window.content.queue_draw()

    def on_app_opacity_change(self, alpha):
        self.current_opacity = alpha

    # ------------------------------------------------------------------
    # Module switch
    # ------------------------------------------------------------------
    def switch_to(self, module: str):
        self.module_switcher.current_module = module
        self.request_update()

    # ------------------------------------------------------------------
    # Live background
    # ------------------------------------------------------------------
    def render_live_background_state(self):
        # update weather-driven particles if clock module
        pass

    def render_live_background(self, cr, width, height):
        state = self.weather_state
        is_day = int(state.get("is_day", 1) or 1)
        code = int(state.get("weather_code", 0) or 0)

        if is_day:
            self.draw_day_sky(cr, width, height)
        else:
            self.draw_night_sky(cr, width, height)

        # particles
        self.draw_particles(cr, width, height, code, is_day)

    def draw_day_sky(self, cr, width, height):
        cr.set_source_rgba(*DAY_SKY_TOP)
        cr.rectangle(0, 0, width, height)
        cr.rectangle(0, 0, width, height)  # full window gradient via linear
        # use a linear gradient for better effect
        grad = cairo.LinearGradient(0, 0, 0, height)
        grad.add_color_stop_rgba(0.0, *DAY_SKY_TOP)
        grad.add_color_stop_rgba(1.0, *DAY_SKY_BOT)
        cr.set_source(grad)
        cr.paint()

        # sun
        sun_x = width * 0.82
        sun_y = height * 0.18
        self.draw_sun_circle(cr, sun_x, sun_y, 45, "#FFB800", "#FFD24A")

        # a few clouds
        self.draw_cloud(cr, width * 0.2, height * 0.28, 60, (0.9, 0.9, 0.95, 0.85))
        self.draw_cloud(cr, width * 0.62, height * 0.22, 72, (0.9, 0.9, 0.95, 0.90))

    def draw_night_sky(self, cr, width, height):
        grad = cairo.LinearGradient(0, 0, 0, height)
        grad.add_color_stop_rgba(0.0, *NIGHT_TOP)
        grad.add_color_stop_rgba(1.0, *NIGHT_BOT)
        cr.set_source(grad)
        cr.paint()

        # moon
        moon_x = width * 0.2
        moon_y = height * 0.18
        self.draw_moon(cr, moon_x, moon_y, 42)

        # stars
        for _ in range(80):
            sx = (hash(f"{width}{height}{_}") % 100000) / 100000.0 * width
            sy = (hash(f"{width}{height}{_ + 50}") % 100000) / 100000.0 * height * 0.8
            sz = 1.2 + (hash(f"{width}{height}{_ + 100}") % 1000) / 1000.0 * 1.5
            cr.set_source_rgba(1, 1, 1, 0.7 + (hash(f"{width}{height}{_ + 200}") % 1000) / 1000.0 * 0.3)
            cr.arc(sx, sy, sz, 0, 2 * math.pi)
            cr.fill()

    def draw_sun_circle(self, cr, x, y, r, outer, inner):
        cr.set_source_rgb(*self.rgb(outer))
        cr.arc(x, y, r, 0, 2 * math.pi)
        cr.fill()
        cr.set_source_rgb(*self.rgb(inner))
        cr.arc(x, y, r * 0.7, 0, 2 * math.pi)
        cr.fill()

    def draw_moon(self, cr, x, y, r):
        cr.set_source_rgb(*self.rgb("#F2F4F8"))
        cr.arc(x, y, r, 0, 2 * math.pi)
        cr.fill()
        cr.set_source_rgb(*self.rgb("#0B0D1A"))
        cr.arc(x + r * 0.25, y - r * 0.1, r, 0, 2 * math.pi)
        cr.fill()

    def draw_cloud(self, cr, x, y, r, color):
        cr.set_source_rgba(*color)
        cr.arc(x - r * 0.4, y + r * 0.2, r * 0.7, 0, 2 * math.pi)
        cr.arc(x + r * 0.2, y + r * 0.15, r * 0.8, 0, 2 * math.pi)
        cr.arc(x + r * 0.7, y + r * 0.25, r * 0.6, 0, 2 * math.pi)
        cr.arc(x + r * 0.2, y + r * 0.4, r * 0.5, 0, 2 * math.pi)
        cr.fill()

    def draw_particles(self, cr, width, height, code, is_day):
        # Particles: simple rain/snow sparks
        # If not clock module, skip
        code = int(code) if code is not None else 0
        if code == 0:
            return
        if 0 <= code <= 3:
            return  # clear
        if code in (45, 48):
            self.draw_rain_particles(cr, width, height, 0.4)
            return
        if 51 <= code <= 67:
            self.draw_rain_particles(cr, width, height, 0.6)
            return
        if 71 <= code <= 77:
            self.draw_snow_particles(cr, width, height)
            return
        if 95 <= code <= 99:
            self.draw_thunder_particles(cr, width, height)
            return

    def draw_rain_particles(self, cr, width, height, opacity):
        for p in self._particles:
            x = p.get("x", 0)
            y = p.get("y", 0)
            cr.set_source_rgba(0.5, 0.6, 0.8, opacity)
            cr.set_line_width(1.0)
            cr.move_to(x, y)
            cr.line_to(x - 2, y + 8)
            cr.stroke()

    def draw_snow_particles(self, cr, width, height):
        for p in self._particles:
            x = p.get("x", 0)
            y = p.get("y", 0)
            cr.set_source_rgba(1, 1, 1, 0.85)
            cr.arc(x, y, 2.0, 0, 2 * math.pi)
            cr.fill()

    def draw_thunder_particles(self, cr, width, height):
        self.draw_rain_particles(cr, width, height, 0.7)
        # occasional flash
        if self._particles and self._particles[0].get("flash", False):
            cr.set_source_rgba(1, 1, 1, 0.25)
            cr.rectangle(0, 0, width, height)
            cr.fill()

    def start_particle_animation(self):
        if self._particle_timer is not None:
            return
        self._particles = []
        for _ in range(60):
            self._particles.append({
                "x": (hash(f"{_}{time.time()}") % 100000) / 100000.0 * 2000,
                "y": (hash(f"{_ + 50}") % 100000) / 100000.0 * 2000,
                "speed": 8 + (hash(f"{_ + 100}") % 1000) / 1000.0 * 6,
                "flash": False,
            })
        self._particle_timer = GLib.timeout_add(33, self._particle_tick)

    def _particle_tick(self):
        # update particles lazily; only used by clock module visuals
        for p in self._particles:
            p["y"] = p.get("y", 0) + p.get("speed", 8) * 0.5
            p["x"] = p.get("x", 0) + (hash(f"{int(p['y'])}") % 100000 - 50000) / 100000.0 * 4
            if p["y"] > 2000:
                p["y"] = -5
            if p["x"] < -5:
                p["x"] = 2005
            if p["x"] > 2005:
                p["x"] = -5
        if self.window:
            self.window.content.queue_draw()
        return True

    # ------------------------------------------------------------------
    # Clock / time text
    # ------------------------------------------------------------------
    def start_clock_update(self):
        def tick():
            now = datetime.datetime.now()
            self.digital_str = now.strftime("%I:%M:%S %p").lstrip("0")
            if self.digital_str.startswith(":"):
                self.digital_str = "12" + self.digital_str
            if self.window:
                self.window.content.queue_draw()
            return True
        GLib.timeout_add(1000, tick)
        tick()

    # ------------------------------------------------------------------
    # Weather
    # ------------------------------------------------------------------
    def start_weather(self):
        def tick():
            self.fetch_weather()
            return True
        GLib.timeout_add(60000, tick)  # retry every minute
        self.fetch_weather()

    def fetch_weather(self):
        now = time.time()
        if now - self._weather_fetch_at < 1800:
            return
        # rate limit: max 5 calls per hour
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
            url = "https://api.open-meteo.com/v1/forecast?latitude={}&longitude={}&current=temperature_2m,weather_code,is_day&daily=weather_code,temperature_2m_max,temperature_2m_min&timezone=auto".format(lat, lon)
            import requests as _req
            r = _req.get(url, timeout=8)
            data = r.json()
            cur = data.get("current", {})
            temp = cur.get("temperature_2m")
            code = cur.get("weather_code", 0)
            is_day = cur.get("is_day", 1)
            city = loc.get("city", "")
            self.weather_state = {
                "temperature_2m": temp,
                "weather_code": code,
                "is_day": int(is_day),
                "city": city,
            }
            self._weather_fetch_at = time.time()
            self._weather_calls_today += 1
            if self.window:
                self.window.content.queue_draw()
        except Exception:
            pass

    def _update_location(self):
        try:
            import requests as _req
            r = _req.get("http://ip-api.com/json/", timeout=8)
            data = r.json()
            if data.get("status") == "success":
                self._weather_location = {
                    "lat": data.get("lat"),
                    "lon": data.get("lon"),
                    "city": data.get("city") or data.get("regionName") or "Local",
                }
        except Exception:
            self._weather_location = {"lat": 28.6, "lon": 77.2, "city": "Delhi"}

    # ------------------------------------------------------------------
    # Housekeeping timers
    # ------------------------------------------------------------------
    def start_housekeeping(self):
        def tick():
            self.ensure_app_menu()
            return True
        GLib.timeout_add(60000, tick)
        self.ensure_app_menu()

    # ------------------------------------------------------------------
    # App menu stub (LXQt app menu integration is via .desktop; this is a
    # minimal in-app menu button placeholder for future extension)
    # ------------------------------------------------------------------
    def ensure_app_menu(self):
        pass


# ---------------------------------------------------------------------------
# Module rendering entry point from content draw
# ------------------------------------------------------------------
def render_module(self, cr, width, height):
    # self here is SamayApp instance
    module = getattr(self, "current_module", "clock")
    from main_app import ModuleSwitcher
    state = {
        "digital_str": getattr(self, "digital_str", "00:00 AM"),
        "is_day": self.weather_state.get("is_day", 1),
    }
    if module == "clock":
        self.clock.render(cr, width, height, state)
    else:
        # module placeholder card
        self.draw_module_card(cr, width, height, module)

def draw_module_card(self, cr, width, height, module: str):
    # background glass card
    cr.set_source_rgba(1, 1, 1, 0.04)
    cr.rectangle(40, 60, width - 80, height - 120)
    cr.set_source_rgba(1, 1, 1, 0.08)
    cr.set_line_width(1.0)
    cr.rectangle(40, 60, width - 80, height - 120)
    cr.stroke()
    # title
    ctx = PangoCairo.create_context(cr)
    layout = PangoCairo.create_layout(cr)
    layout.set_font_description(Pango.FontDescription("Bold 26"))
    layout.set_text(module.title())
    cr.set_source_rgba(1, 1, 1, 0.9)
    PangoCairo.show_layout(cr, layout)
    # center
    ink, logical = layout.get_pixel_extents()
    cr.move_to(width / 2 - logical.width / 2, 90)
    # body hint
    layout2 = PangoCairo.create_layout(cr)
    layout2.set_font_description(Pango.FontDescription("14"))
    layout2.set_text("Coming soon — full implementation in this module.")
    cr.set_source_rgba(1, 1, 1, 0.6)
    PangoCairo.show_layout(cr, layout2)
    ink2, logical2 = layout2.get_pixel_extents()
    cr.move_to(width / 2 - logical2.width / 2, 140)


# Monkey-patch render_module into SamayApp for content draw
SamayApp.render_module = render_module  # type: ignore
SamayApp.draw_module_card = draw_module_card  # type: ignore


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main() -> None:
    app = SamayApp()
    exit_code = app.run([])
    import sys as _sys
    _sys.exit(exit_code)

if __name__ == "__main__":
    main()
