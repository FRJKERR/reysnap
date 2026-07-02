"""PinSnap – system tray icon and context menu.

Because PinSnap does not ship with an external icon file, a simple
camera+pin icon is procedurally drawn with :class:`QPainter`.
"""

import logging

from PySide6.QtCore import QObject, Qt, Signal
from PySide6.QtGui import (
    QAction,
    QBrush,
    QColor,
    QConicalGradient,
    QCursor,
    QFont,
    QIcon,
    QPainter,
    QPen,
    QPixmap,
)
from PySide6.QtWidgets import QMenu, QSystemTrayIcon, QWidget

from .i18n import tr

logger = logging.getLogger(__name__)

# The brand colour – a dark teal/cyan that is legible on both light
# and dark system-tray backgrounds.
_BRAND_COLOR = QColor("#0891B2")
_BRAND_COLOR_LIGHT = QColor("#22D3EE")


def _generate_tray_icon(size: int = 64) -> QIcon:
    """Create a QIcon by drawing a camera shape with a pin overlay.

    The icon uses :data:`_BRAND_COLOR` as the fill and white for
    highlights so it remains visible on most tray backgrounds.
    """
    pm = QPixmap(size, size)
    pm.fill(QColor(0, 0, 0, 0))  # transparent background

    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing, True)

    # --- Circle background ---
    bg_gradient = QConicalGradient(size / 2, size / 2, 0)
    bg_gradient.setColorAt(0.0, _BRAND_COLOR)
    bg_gradient.setColorAt(1.0, _BRAND_COLOR.darker(130))
    p.setBrush(QBrush(bg_gradient))
    p.setPen(QPen(QColor(255, 255, 255, 60), 2))
    p.drawRoundedRect(2, 2, size - 4, size - 4, 12, 12)

    # --- Camera body (rounded rectangle) ---
    cam_x, cam_y = 10, 18
    cam_w, cam_h = size - 20, size - 28
    p.setBrush(QBrush(QColor(255, 255, 255, 220)))
    p.setPen(QPen(QColor(255, 255, 255, 255), 1.5))
    p.drawRoundedRect(cam_x, cam_y, cam_w, cam_h, 4, 4)

    # --- Camera lens (circle) ---
    cx, cy = size // 2, cam_y + cam_h // 2 + 1
    lens_r = cam_h // 2 - 6
    p.setBrush(QBrush(_BRAND_COLOR))
    p.setPen(QPen(QColor(255, 255, 255, 180), 1.5))
    p.drawEllipse(cx - lens_r, cy - lens_r, lens_r * 2, lens_r * 2)

    # --- Lens inner circle ---
    inner_r = lens_r - 4
    p.setBrush(QBrush(QColor(255, 255, 255, 120)))
    p.setPen(Qt.PenStyle.NoPen)
    p.drawEllipse(cx - inner_r, cy - inner_r, inner_r * 2, inner_r * 2)

    # --- Camera flash bump (top centre) ---
    bump_w, bump_h = 14, 6
    bx = (size - bump_w) // 2
    p.setBrush(QBrush(QColor(255, 255, 255, 220)))
    p.drawRoundedRect(bx, cam_y - bump_h + 2, bump_w, bump_h, 2, 2)

    # --- Pin (small red circle top-right) ---
    pin_cx, pin_cy = size - 16, 14
    pin_r = 7
    p.setBrush(QBrush(QColor("#EF4444")))  # red
    p.setPen(QPen(QColor(255, 255, 255, 200), 1.5))
    p.drawEllipse(pin_cx - pin_r, pin_cy - pin_r, pin_r * 2, pin_r * 2)

    # Pin highlight
    p.setBrush(QBrush(QColor(255, 255, 255, 120)))
    p.setPen(Qt.PenStyle.NoPen)
    p.drawEllipse(pin_cx - 3, pin_cy - 4, 5, 4)

    p.end()

    return QIcon(pm)


class SystemTray(QObject):
    """System tray icon and context menu for PinSnap.

    Signals
    -------
    capture_requested()
    pin_requested()
    annotate_requested()
    color_picker_requested()
    ruler_requested()
    preferences_requested()
    quit_requested()
    """

    capture_requested = Signal()
    pin_requested = Signal()
    annotate_requested = Signal()
    color_picker_requested = Signal()
    ruler_requested = Signal()
    preferences_requested = Signal()
    quit_requested = Signal()

    def __init__(self, app_controller: QObject, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._app = app_controller

        self._icon: QIcon = _generate_tray_icon()
        self._tray: QSystemTrayIcon = QSystemTrayIcon(self._icon, parent)

        self._menu: QMenu = QMenu(parent)
        self._build_menu()
        self._tray.setContextMenu(self._menu)

        # Left-click also opens the menu
        self._tray.activated.connect(self._on_activated)

    # ------------------------------------------------------------------
    # Public
    # ------------------------------------------------------------------

    def show(self) -> None:
        """Show the tray icon."""
        if not self._tray.isVisible():
            self._tray.show()

    def hide(self) -> None:
        """Hide the tray icon temporarily (e.g. during screenshot)."""
        self._tray.hide()

    # ------------------------------------------------------------------
    # Menu construction
    # ------------------------------------------------------------------

    def _build_menu(self) -> None:
        """Populate the context menu (emoji labels, no theme icons)."""
        m = self._menu

        entries = [
            ("📷", "Capturar pantalla", self.capture_requested),
            ("📌", "Anclar captura", self.pin_requested),
            ("✏️", "Anotar imagen", self.annotate_requested),
            ("🔍", "Selector de color", self.color_picker_requested),
            ("📏", "Regla", self.ruler_requested),
            None,
            ("⚙️", "Preferencias", self.preferences_requested),
            None,
            ("🚪", "Salir", self.quit_requested),
        ]
        for entry in entries:
            if entry is None:
                m.addSeparator()
                continue
            emoji, label, signal = entry
            action = QAction(f"{emoji}  {tr(label)}", m)
            action.triggered.connect(signal.emit)
            m.addAction(action)

    def retranslate(self) -> None:
        """Rebuild the menu in the current language."""
        self._menu.clear()
        self._build_menu()

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _on_activated(self, reason: QSystemTrayIcon.ActivationReason) -> None:
        """Handle left-click on the tray icon."""
        if reason == QSystemTrayIcon.ActivationReason.Trigger:
            # popup() (unlike exec()) closes when clicking outside,
            # matching the native right-click behaviour
            self._menu.popup(QCursor.pos())