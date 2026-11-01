# SAMAY

Galaxy Watch / OneUI-style desktop clock for Debian 13 LXQt with a modern glassmorphism interface and dynamic opacity control.

- **Language:** Python 3.10+
- **GUI:** GTK 3 only (`gi.repository Gtk/Gdk/Pango/PangoCairo`)
- **Deps:** only the explicitly allowed Python packages: `requests`, `pytz`, `python-dateutil`
- **Assets:** all UI is drawn with Cairo. No background images.
- **Compositor support:** RGBA visual for transparency/blur where the desktop supports it.

## Run

```bash
python3 samay/main.py
# or
python3 -m samay
```

## First-time setup on the target machine

On the real Debian/Ubuntu desktop, install the GTK 3 runtime and Cairo bindings. A helper script is included:

```bash
./install-gtk3.sh
```

This installs:

- `python3-gi`
- `libgtk-3-0`, `gir1.2-gtk-3.0`, `libgtk-3-common`
- `python3-cairo`
- `libnotify-bin`, `libcanberra-gtk3-0`

## Python dependencies

Python packages are vendored inside `samay/vendor` so the app can be run from a copy of the source without modifying the system Python. The vendored packages are:

- `requests`
- `pytz`
- `python-dateutil`

GTK 3 bindings are **system packages** on the target machine.

## Features

### Window, traffic lights, opacity slider

- Size 960x640, centered, resizable, min 800x500
- `set_decorated(False)` with custom clean header
- RGBA visual for transparency
- Default opacity 0.90
- Top bar 45px with custom traffic lights on left (close/minimize/maximize) and opacity slider on right
- Opacity slider: 0.40 to 1.00, default 0.90, real-time
- Minimize → `iconify()`, maximize → toggle fullscreen, close → `Gtk.main_quit()`
- Draggable via top bar with `begin_move_drag()`
- Rounded corners via GTK 3 CSS `border-radius: 18px`

### Navigation

Left sidebar 220px with vertical tabs and emoji icons:

- ⏰ Clock
- ⏳ Countdown
- ⏱️ Stopwatch
- 🌍 World Clock
- ⏰ Alarm
- 📅 Calendar

Selected tab: `rgba(255,255,255,0.15)` with 12px rounded corners.

### Clock

- Analog clock drawn with Cairo, ~280px diameter, hour/minute/second hands and ticks
- Digital below: `HH:MM:SS AM/PM`, bold, white
- Weather widget top-right: temperature °C, city name, weather icon drawn with Cairo
- Weather from Open-Meteo, no key needed
- Location from ip-api.com once per app start
- Weather cache 30 minutes, max 5 API calls per hour

### Live background

Full-window Cairo background that changes with weather day/night:

- Day scene: light blue → pale blue gradient, sun, clouds
- Night scene: dark blue → black gradient, moon, stars
- Weather particle overlays: clear, rain (falling lines), thunderstorm (rain + flashes), snow, hailstorm
- Animation via 33ms timer (~30fps), low-CPU particles

### Countdown

- HH:MM:SS picker (3 `Gtk.SpinButton`)
- Circular progress bar (Cairo)
- Start/Pause/Reset with keyboard shortcuts

### Stopwatch

- Display `00:00:00.000`
- Start/Stop, Lap, Reset
- Lap list in a scrolled window
- Max 100 laps, export to `~/.samay/laps.csv`

### World Clock

- Default cities: Delhi, Tokyo, London, New York, Dubai + Add
- Each row: city, time, offset, day/night icon
- Search-add using `pytz.all_timezones`
- Saved to `~/.samay/world.json`

### Alarm

- Time picker + repeat checkboxes + sound selector + label
- Stored in `~/.samay/alarms.json`
- Checked every second, triggers sound + notification on match

### Calendar (Indian)

- Monthly grid view
- Indian festivals from `data/indian_festivals_2026.json` first
- Monthly fallback check to Nager.at or Calendarific if cache older than 30 days
- Cache saved to `~/.samay/calendar_cache.json`
- Indian holidays shown with orange dot and tooltips

### App Menu & Desktop Integration (LXQt)

Install a `.desktop` file to add Samay to the LXQt Application Menu:

```ini
[Desktop Entry]
Type=Application
Name=Samay
Comment=Galaxy Watch Style Desktop Clock
Exec=python3 /path/to/samay/main.py
Icon=utilities-clock
Categories=Utility;Clock;
Terminal=false
```

Install either system-wide at `/usr/share/applications/samay.desktop` or for the current user at `~/.local/share/applications/samay.desktop`.

## Dev helper

```bash
./bin/develop
```

This prints the run and desktop-integration snippets with the correct paths for this checkout.

## Project structure

```
samay/
  main.py        # public entrypoint
  app.py         # core app logic + window + modules
  __init__.py    # package marker
  __main__.py    # run as `python3 -m samay`
  pyproject.toml
  vendor/        # vendored pip deps
  data/
    indian_festivals_2026.json
  ui/
    samay.css
    README.md
    __init__.py
    graphical_ui.py
  modules/
    __init__.py
    __main__.py
gtk_helpers.py   # GTK enablement shim for offline tooling
bin/develop       # dev helper script
install-gtk3.sh   # one-time host setup
```

## Note on this snapshot

This snapshot was created in a cloud sandbox that did not include the GTK 3 typelibs, so full live execution could not be verified here. The code is written against GTK 3 and expects a target machine with `gir1.2-gtk-3.0` and friends installed. The vendored Python deps are included so the app can be run from source once the system GTK runtime is in place.
