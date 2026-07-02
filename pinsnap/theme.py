"""PinSnap – application theming (system / light / dark).

Qt does not switch palettes automatically when the user picks a theme
in Preferences, so this module owns that: ``apply_theme`` swaps the
application style and palette at runtime.  "system" restores whatever
style/palette the app started with.
"""

from __future__ import annotations

import logging

from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QApplication

logger = logging.getLogger(__name__)

ACCENT = QColor("#0891B2")

# Captured on first call so "system" can restore the startup look.
_original: dict = {}


def _dark_palette() -> QPalette:
    p = QPalette()
    window = QColor(45, 45, 48)
    base = QColor(30, 30, 30)
    text = QColor(230, 230, 230)
    disabled = QColor(128, 128, 128)

    p.setColor(QPalette.ColorRole.Window, window)
    p.setColor(QPalette.ColorRole.WindowText, text)
    p.setColor(QPalette.ColorRole.Base, base)
    p.setColor(QPalette.ColorRole.AlternateBase, window)
    p.setColor(QPalette.ColorRole.ToolTipBase, base)
    p.setColor(QPalette.ColorRole.ToolTipText, text)
    p.setColor(QPalette.ColorRole.Text, text)
    p.setColor(QPalette.ColorRole.Button, window)
    p.setColor(QPalette.ColorRole.ButtonText, text)
    p.setColor(QPalette.ColorRole.BrightText, QColor(255, 80, 80))
    p.setColor(QPalette.ColorRole.Link, ACCENT)
    p.setColor(QPalette.ColorRole.Highlight, ACCENT)
    p.setColor(QPalette.ColorRole.HighlightedText, QColor(255, 255, 255))
    p.setColor(QPalette.ColorRole.PlaceholderText, disabled)

    for role in (
        QPalette.ColorRole.WindowText,
        QPalette.ColorRole.Text,
        QPalette.ColorRole.ButtonText,
    ):
        p.setColor(QPalette.ColorGroup.Disabled, role, disabled)
    p.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.Highlight, QColor(80, 80, 80))

    return p


def apply_theme(app: QApplication, theme: str) -> None:
    """Apply ``"system"``, ``"light"`` or ``"dark"`` to the whole app."""
    if not _original:
        _original["style"] = app.style().objectName()
        _original["palette"] = QPalette(app.palette())

    if theme == "dark":
        app.setStyle("Fusion")
        app.setPalette(_dark_palette())
    elif theme == "light":
        # Fusion's standard palette is a consistent light look on any distro
        app.setStyle("Fusion")
        app.setPalette(app.style().standardPalette())
    else:  # system
        app.setStyle(_original["style"])
        app.setPalette(_original["palette"])

    logger.debug("Theme applied: %s", theme)
