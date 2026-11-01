# SAMAY UI Assets

SAMAY’s interface is fully Cairo-drawn. There are no image assets required at runtime, so the UI bundle stays well under the 50 MB ceiling.

## What is drawn

- **Header bar:** 45px tall, RGBA glass with custom traffic light buttons (red/yellow/green 14px circles) and a compact opacity slider on the right.
- **Sidebar:** 220px vertical tabs with emoji icons, selected state uses `rgba(255,255,255,0.15)` with 12px rounded corners.
- **Live background:** Full-window gradient sky (day/night), sun, moon, stars, and weather particles (rain, snow, thunderstorm) drawn with Cairo.
- **Clock module:** 280px-ish analog clock face with ticks and hands, digital HH:MM:SS AM/PM below.
- **Weather widget:** Temperature, city name, and a Cairo-drawn weather icon determined by Open-Meteo WMO weather codes.

## Transparency model

- The window uses an RGBA visual so the system compositor (picom, LXQt compositor, KWin, etc) can apply blur and alpha.
- Default opacity is 0.90. The slider lets the user adjust from 0.40 to 1.00 in real time.
- Rounded corners are expressed via GTK 3 CSS `border-radius: 18px` on the window.

## Styling reference

See `samay/ui/samay.css` for the CSS classes used by the chrome and widgets. This file is for documentation/extension; the runtime currently sets most styling programmatically and through inline CSS.

## Asset registry (current)

| Path | Purpose |
|------|----------|
| `samay/ui/samay.css` | CSS reference for SAMAY chrome and widgets |
| `samay/ui/README.md` | This file |

There are no bitmap, font, or icon files shipped in this directory.
