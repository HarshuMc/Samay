#!/bin/bash
set -e
# install-gtk3.sh
# One-time setup for SAMAY (Debian/Ubuntu host with sudo).
# Installs the GTK 3 runtime, Cairo bindings, notifications and sound support
# needed to run SAMAY. It does not touch your project files or vendor dir.

if command -v sudo >/dev/null 2>&1; then
  SUDO=sudo
else
  SUDO=
fi

echo "Updating package lists..."
$SUDO apt-get update -qq

echo "Installing GTK 3 + Cairo + notification + sound support..."
$SUDO apt-get install -y -qq \
  python3-gi \
  libgtk-3-0 \
  libgtk-3-common \
  gir1.2-gtk-3.0 \
  python3-cairo \
  libnotify-bin \
  libcanberra-gtk3-0 \
  libcanberra0

echo ""
echo "GTK 3 runtime installed."
echo "Testing imports..."
python3 - <<'PY'
import gi  # noqa: E402
gi.require_version('Gtk', '3.0')
gi.require_version('Gdk', '3.0')
gi.require_version('Pango', '1.0')
gi.require_version('PangoCairo', '1.0')
from gi.repository import Gtk, Gdk, Pango, PangoCairo  # noqa: F401
try:
    import cairo as _cairo  # noqa: F401
    print("cairo:", _cairo.version)
except Exception as e:  # pragma: no cover - best-effort
    print("cairo import skipped:", e)
print("GTK 3 runtime OK")
PY
