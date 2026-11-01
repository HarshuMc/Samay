#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SAMAY — Galaxy Watch / OneUI-style desktop clock for Debian 13 LXQt.

Run:
  python3 /path/to/samay/main.py
Or:
  python3 -m samay
"""

import sys
import os
from pathlib import Path

# ----------------------------------------------------------------------
# Path bootstrap so this venv can still reach gi + vendor deps
# ----------------------------------------------------------------------
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, "/usr/lib/python3/dist-packages")
sys.path.insert(0, os.path.join(HERE, "vendor"))

# ----------------------------------------------------------------------
# gi + GTK3 bootstrap (requires GTK 3 runtime installed on the host)
# ----------------------------------------------------------------------
import gi  # noqa: E402
gi.require_version('Gtk', '3.0')  # noqa: E402
gi.require_version('Gdk', '3.0')  # noqa: E402
gi.require_version('Pango', '1.0')  # noqa: E402
gi.require_version('PangoCairo', '1.0')  # noqa: E402

try:
    import cairo  # noqa: F401
except ImportError:  # pragma: no cover - runtime-only guard
    cairo = None  # type: ignore[assignment]

from gi.repository import (  # noqa: E402
    Gtk,  # noqa: F401
    Gdk,  # noqa: F401
    GLib,  # noqa: F401
    Gio,  # noqa: F401
    Pango,  # noqa: F401
    PangoCairo,  # noqa: F401
)

# ----------------------------------------------------------------------
# Optional, explicitly allowed pip deps (shipped inside ./vendor)
# ----------------------------------------------------------------------
try:  # noqa: F401
    import requests  # noqa: F401
except Exception:  # pragma: no cover - runtime-only guard
    requests = None  # type: ignore[assignment]
try:  # noqa: F401
    import pytz  # noqa: F401
except Exception:  # pragma: no cover - runtime-only guard
    pytz = None  # type: ignore[assignment]
try:  # noqa: F401
    import dateutil  # noqa: F401
except Exception:  # pragma: no cover - runtime-only guard
    dateutil = None  # type: ignore[assignment]

# ----------------------------------------------------------------------
# Application singleton
# ----------------------------------------------------------------------
from app import SamayApp, main  # noqa: E402

if __name__ == "__main__":
    sys.exit(main())
