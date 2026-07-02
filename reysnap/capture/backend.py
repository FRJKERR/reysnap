"""ReySnap capture backend abstraction.

Provides :func:`get_capture_backend` which returns the best available
backend for the current desktop environment.
"""

from __future__ import annotations

import logging
import subprocess
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Optional

from PySide6.QtGui import QPixmap

logger = logging.getLogger(__name__)


class CaptureBackend(ABC):
    """Interface that every capture backend must implement."""

    @abstractmethod
    def capture_screen(self, region: Optional[tuple] = None) -> QPixmap:
        """Capture the full screen or *region* (x, y, w, h).

        Returns a :class:`QPixmap` with the captured image.
        """
        ...

    @abstractmethod
    def get_screen_geometry(self) -> tuple:
        """Return ``(x, y, width, height)`` of the full virtual screen."""
        ...


# ------------------------------------------------------------------
# X11 / Xlib backend (primary on most Linux desktops)
# ------------------------------------------------------------------

class XlibCaptureBackend(CaptureBackend):
    """Screen capture using python-xlib (X11 only)."""

    def capture_screen(self, region: Optional[tuple] = None) -> QPixmap:
        try:
            from Xlib import display, X
        except ImportError:
            logger.error("python-xlib is not installed")
            return QPixmap()

        dpy = display.Display()
        root = dpy.screen().root

        if region is not None:
            x, y, w, h = region
        else:
            x, y, w, h = self.get_screen_geometry()

        try:
            raw = root.get_image(x, y, w, h, X.ZPixmap, 0xFFFFFFFF)
        except Exception:
            logger.exception("X11 get_image failed for region %s", (x, y, w, h))
            dpy.close()
            return QPixmap()

        # Convert X11 image data to a QImage → QPixmap.  The GetImage
        # reply carries no stride field; derive bytes-per-line from the
        # buffer size so any row padding is accounted for.
        from PySide6.QtGui import QImage

        data = raw.data if isinstance(raw.data, bytes) else bytes(raw.data, "latin-1")
        if h <= 0 or len(data) < h:
            dpy.close()
            return QPixmap()
        stride = len(data) // h
        fmt = QImage.Format.Format_RGB32
        qimg = QImage(data, w, h, stride, fmt)
        pixmap = QPixmap.fromImage(qimg.copy())  # .copy() to detach data

        dpy.close()
        return pixmap

    def get_screen_geometry(self) -> tuple:
        try:
            from Xlib import display
        except ImportError:
            from PySide6.QtGui import QGuiApplication
            screen = QGuiApplication.primaryScreen().geometry()
            return (screen.x(), screen.y(), screen.width(), screen.height())

        dpy = display.Display()
        screen = dpy.screen()
        geo = (0, 0, screen.width_in_pixels, screen.height_in_pixels)
        dpy.close()
        return geo


# ------------------------------------------------------------------
# Grim (Wayland / wlroots) backend
# ------------------------------------------------------------------

class GrimCaptureBackend(CaptureBackend):
    """Screen capture using the ``grim`` CLI tool (Wayland)."""

    def capture_screen(self, region: Optional[tuple] = None) -> QPixmap:
        if region:
            x, y, w, h = region
            args = [str(x), str(y), str(w), str(h)]
        else:
            args = []

        try:
            result = subprocess.run(
                ["grim", *args, "-"],
                capture_output=True,
                timeout=10,
            )
            if result.returncode != 0:
                logger.error("grim failed: %s", result.stderr.decode(errors="replace"))
                return QPixmap()

            pixmap = QPixmap()
            pixmap.loadFromData(result.stdout)
            return pixmap
        except FileNotFoundError:
            logger.error("grim not found – install it for Wayland support")
            return QPixmap()
        except subprocess.TimeoutExpired:
            logger.error("grim timed out")
            return QPixmap()

    def get_screen_geometry(self) -> tuple:
        from PySide6.QtGui import QGuiApplication
        screen = QGuiApplication.primaryScreen().geometry()
        return (screen.x(), screen.y(), screen.width(), screen.height())


# ------------------------------------------------------------------
# Fallback: Qt screenshots (works anywhere Qt works, but may include
# the selector window itself in the capture).
# ------------------------------------------------------------------

class QtCaptureBackend(CaptureBackend):
    """Fallback backend using :meth:`QScreen.grabWindow`."""

    def capture_screen(self, region: Optional[tuple] = None) -> QPixmap:
        from PySide6.QtGui import QGuiApplication

        screen = QGuiApplication.primaryScreen()
        if screen is None:
            return QPixmap()

        # Grab the root window (0) – entire virtual desktop
        pixmap = screen.grabWindow(0, *region) if region else screen.grabWindow(0)
        return pixmap

    def get_screen_geometry(self) -> tuple:
        from PySide6.QtGui import QGuiApplication
        geo = QGuiApplication.primaryScreen().geometry()
        return (geo.x(), geo.y(), geo.width(), geo.height())


# ------------------------------------------------------------------
# Factory
# ------------------------------------------------------------------

def _detect_wayland() -> bool:
    """Best-effort Wayland detection."""
    import os
    return os.environ.get("WAYLAND_DISPLAY") is not None or (
        os.environ.get("XDG_SESSION_TYPE", "").lower() == "wayland"
    )


def _grim_available() -> bool:
    """Check whether the ``grim`` binary is on ``$PATH``."""
    from shutil import which
    return which("grim") is not None


def get_capture_backend() -> CaptureBackend:
    """Return the best available capture backend.

    Priority:
    1. ``grim`` (Wayland)
    2. ``XlibCaptureBackend`` (X11)
    3. ``QtCaptureBackend`` (universal fallback)
    """
    if _detect_wayland() and _grim_available():
        logger.info("Using grim (Wayland) capture backend")
        return GrimCaptureBackend()

    try:
        from Xlib import display  # noqa: F401
        logger.info("Using Xlib capture backend")
        return XlibCaptureBackend()
    except ImportError:
        pass

    logger.info("Using Qt fallback capture backend")
    return QtCaptureBackend()