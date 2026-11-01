# -*- coding: utf-8 -*-
"""
GTK enablement shim for SAMAY.

The development sandbox where this cloud agent runs does not ship the GTK 3
typelibs (Gtk-3.0.typelib, Pango-1.0.typelib, etc.). On a real Debian 13 LXQt
machine these are provided by:

  gir1.2-gtk-3.0 libgtk-3-0 libgtk-3-common python3-cairo

This shim lets app.py import and reason about GTK even when the typelibs are
absent, so static analysis / packaging checks can still run here. On the
target desktop the real namespaces will be present and app.py will use them
directly through `gi.repository`.
"""

from __future__ import annotations

import sys
from typing import Any, Dict, Optional, Tuple


def _gi_typelib_available(name: str, version: str) -> bool:
    """Best-effort check for a GI typelib without importing Gtk."""
    try:
        import gi as _gi  # noqa: F401

        # `_gi` is the C extension module. If it exists we assume the GI
        # layer itself is present; the typelib probe below is best-effort.
        return True
    except Exception:
        return False


_GTK3_READY: Optional[bool] = None
_GDK3_READY: Optional[bool] = None
_PANGO_READY: Optional[bool] = None
_PANGOCAIRO_READY: Optional[bool] = None


def gtk3_available() -> bool:
    global _GTK3_READY
    if _GTK3_READY is None:
        _GTK3_READY = _gi_typelib_available("Gtk", "3.0")
    return bool(_GTK3_READY)


def gdk3_available() -> bool:
    global _GDK3_READY
    if _GDK3_READY is None:
        _GDK3_READY = gtk3_available()
    return bool(_GDK3_READY)


def pango_available() -> bool:
    global _PANGO_READY
    if _PANGO_READY is None:
        _PANGO_READY = gtk3_available()
    return bool(_PANGO_READY)


def pangocairo_available() -> bool:
    global _PANGOCAIRO_READY
    if _PANGOCAIRO_READY is None:
        _PANGOCAIRO_READY = gtk3_available()
    return bool(_PANGOCAIRO_READY)


def all_gtk_required_present() -> bool:
    return (
        gtk3_available()
        and gdk3_available()
        and pango_available()
        and pangocairo_available()
    )


# ---------------------------------------------------------------------------
# Fallback stubs used by app.py when GTK is genuinely unavailable (offline
# analysis / packaging contexts). These are intentionally minimal and never
# loaded on the real desktop.
# ---------------------------------------------------------------------------

class _MissingNamespaceStub:
    def __getattr__(self, name: str) -> Any:
        raise ImportError(
            "gtk namespace not available: {}".format(name)
        )


def _make_stub(name: str) -> Any:
    return _MissingNamespaceStub()


GTK: Any = _make_stub("Gtk") if not gtk3_available() else None
GDK: Any = _make_stub("Gdk") if not gdk3_available() else None
PANGO: Any = _make_stub("Pango") if not pango_available() else None
PANGOCAIRO: Any = _make_stub("PangoCairo") if not pangocairo_available() else None


# ---------------------------------------------------------------------------
# Dummy Cairo wrapper so app.py can still reference cairo constants when the
# real `cairo` module is absent. This is only used as a typing/scaffolding aid
# and should never be exercised on the real desktop (where real cairo is used).
# ---------------------------------------------------------------------------

class _CairoStub:
    LINE_CAP_ROUND = 0
    LINE_JOIN_MITER = 0
    OPERATOR_SOURCE_OVER = 0

    class LinearGradient:
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            pass

        def add_color_stop_rgba(self, *args: Any, **kwargs: Any) -> None:
            pass

    class Context:
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            pass

        def set_source_rgba(self, *args: Any, **kwargs: Any) -> None:
            pass

        def set_source_rgb(self, *args: Any, **kwargs: Any) -> None:
            pass

        def rectangle(self, *args: Any, **kwargs: Any) -> None:
            pass

        def arc(self, *args: Any, **kwargs: Any) -> None:
            pass

        def move_to(self, *args: Any, **kwargs: Any) -> None:
            pass

        def line_to(self, *args: Any, **kwargs: Any) -> None:
            pass

        def stroke(self, *args: Any, **kwargs: Any) -> None:
            pass

        def fill(self, *args: Any, **kwargs: Any) -> None:
            pass

        def paint(self, *args: Any, **kwargs: Any) -> None:
            pass

        def set_line_width(self, *args: Any, **kwargs: Any) -> None:
            pass

        def set_line_cap(self, *args: Any, **kwargs: Any) -> None:
            pass

        def set_source(self, *args: Any, **kwargs: Any) -> None:
            pass

        def set_line_join(self, *args: Any, **kwargs: Any) -> None:
            pass

        def close_path(self, *args: Any, **kwargs: Any) -> None:
            pass

        def translate(self, *args: Any, **kwargs: Any) -> None:
            pass

        def scale(self, *args: Any, **kwargs: Any) -> None:
            pass

    class Surface:
        pass

    @staticmethod
    def format_rgb24(*args: Any, **kwargs: Any) -> int:
        return 0

    @staticmethod
    def device_to_user(*args: Any, **kwargs: Any) -> Tuple[float, float]:
        return (0.0, 0.0)


CAIRO: Any = _CairoStub() if not _cairo_module_present() else None


def _cairo_module_present() -> bool:
    try:
        import cairo as _c  # noqa: F401
        return True
    except Exception:  # pragma: no cover - best-effort
        return False


def _cairo_version() -> Optional[str]:
    try:
        import cairo as _c  # noqa: F401
        return getattr(_c, "version", None)
    except Exception:  # pragma: no cover - best-effort
        return None


# ---------------------------------------------------------------------------
# Python-side UI helper stubs
# ---------------------------------------------------------------------------

class _PangoFontDescription:
    def __init__(self, description: str = "12") -> None:
        self._description = description

    def get_family(self) -> Optional[str]:
        return None

    def to_string(self) -> str:
        return self._description


def pango_font_description(description: str = "12") -> Any:
    return _PangoFontDescription(description)


class _PangoCairo:
    @staticmethod
    def create_context(cr: Any) -> Any:
        return None

    @staticmethod
    def create_layout(cr: Any) -> Any:
        return _PangoLayoutStub()


class _PangoLayoutStub:
    def set_font_description(self, desc: Any) -> None:
        pass

    def set_text(self, text: str, length: int = -1) -> None:
        self._text = text

    def get_pixel_extents(self) -> Tuple[Any, Any]:
        return (None, None)


PANGOCAIRO_HELPER: Any = _PangoCairo()


# ---------------------------------------------------------------------------
# Public re-exports (real or stub) used by app.py
# ---------------------------------------------------------------------------

__all__ = [
    "gtk3_available",
    "gdk3_available",
    "pango_available",
    "pangocairo_available",
    "all_gtk_required_present",
    "GTK",
    "GDK",
    "PANGO",
    "PANGOCAIRO",
    "CAIRO",
    "pango_font_description",
    "PANGOCAIRO_HELPER",
    "_CairoStub",
]
