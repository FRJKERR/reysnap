"""ReySnap – entry point.

Creates the :class:`QApplication`, enforces single-instance via
:class:`QSharedMemory`, and hands control to :class:`ReySnapApp`.
"""

import os
import sys
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QSharedMemory

from . import __app_name__, __version__
from .app import ReySnapApp


def main() -> int:
    """Application entry point.  Returns an exit code."""

    # ------------------------------------------------------------------
    # Single-instance guard – one ReySnap process per user UID.
    # ------------------------------------------------------------------
    shared_memory = QSharedMemory(f"reysnap_single_instance_{os.getuid()}")
    if not shared_memory.create(1):
        # On Linux the segment can survive a crash; attach+detach frees
        # a stale one, after which create() succeeds again.
        shared_memory.attach()
        shared_memory.detach()
        if not shared_memory.create(1):
            # Genuinely already running – exit gracefully.
            print(
                f"{__app_name__} ya está en ejecución.",
                file=sys.stderr,
            )
            return 1

    # ------------------------------------------------------------------
    # High-DPI scaling (Qt 6 defaults to on, but we set explicitly for
    # older environments / Flatpak containers).
    # ------------------------------------------------------------------
    os.environ.setdefault("QT_ENABLE_HIGHDPI_SCALING", "1")
    os.environ.setdefault("QT_AUTO_SCREEN_SCALE_FACTOR", "1")

    # ------------------------------------------------------------------
    # QApplication
    # ------------------------------------------------------------------
    app = QApplication(sys.argv)
    app.setApplicationName(__app_name__)
    app.setApplicationVersion(__version__)
    app.setApplicationDisplayName(__app_name__)
    app.setQuitOnLastWindowClosed(False)  # tray keeps us alive

    # ------------------------------------------------------------------
    # Core application
    # ------------------------------------------------------------------
    reysnap = ReySnapApp(app)  # noqa: F841 – prevents GC

    return app.exec()


if __name__ == "__main__":
    sys.exit(main())