"""ReySnap – screen colour picker.

:class:`ColorPicker` presents a fullscreen, translucent overlay.
Moving the mouse shows a magnified view with the colour under the
cursor.  Clicking picks the colour and emits :attr:`color_picked`.
"""

from __future__ import annotations

import logging

from PySide6.QtCore import QPoint, QRect, Qt, Signal, QTimer
from PySide6.QtGui import QColor, QCursor, QGuiApplication, QImage, QPainter, QPen, QPixmap
from PySide6.QtWidgets import QApplication, QWidget

from ..i18n import tr

logger = logging.getLogger(__name__)

_MAGNIFY_RADIUS = 80  # half-size of the magnifier circle in pixels
_MAGNIFY_ZOOM = 8  # zoom factor for the magnified view
_GRID_SIZE = 11  # odd number – pixel grid around cursor
_INNER_RADIUS = 4  # center pixel highlight radius
_COLOR_BAR_H = 40  # bottom info bar height


class ColorPicker(QWidget):
    """Fullscreen colour picker overlay.

    Signals
    -------
    color_picked(QColor)
        Emitted when the user clicks to pick a colour.
    """

    color_picked = Signal(QColor)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
            | Qt.WindowType.BypassWindowManagerHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setCursor(Qt.CursorShape.CrossCursor)
        self.setMouseTracking(True)

        self._screen_pixmap: QPixmap | None = None
        self._current_color = QColor()
        self._pos = QPoint()

        # Timer to update the display
        self._timer = QTimer(self)
        self._timer.setInterval(16)  # ~60 fps
        self._timer.timeout.connect(self._refresh_color)
        self._timer.start()

    def showEvent(self, event) -> None:
        super().showEvent(event)
        # BypassWindowManagerHint means the WM ignores fullscreen requests
        # and never assigns keyboard focus: set the geometry and grab the
        # keyboard ourselves.
        screen = QGuiApplication.screenAt(QCursor.pos()) or QGuiApplication.primaryScreen()
        if screen:
            self.setGeometry(screen.geometry())
        # Grab the screen beneath us
        self._grab_screen()
        self.activateWindow()
        self.raise_()
        self.grabKeyboard()

    def closeEvent(self, event) -> None:
        self.releaseKeyboard()
        super().closeEvent(event)

    def _grab_screen(self) -> None:
        """Capture the current screen content."""
        screen = QGuiApplication.screenAt(QCursor.pos())
        if screen is None:
            screen = QGuiApplication.primaryScreen()
        if screen:
            geo = screen.geometry()
            self._screen_pixmap = screen.grabWindow(0, geo.x(), geo.y(), geo.width(), geo.height())
            self._screen_offset = geo.topLeft()
        else:
            self._screen_pixmap = QPixmap()
            self._screen_offset = QPoint()

    def _refresh_color(self) -> None:
        self._pos = QCursor.pos()
        self.update()

    # ------------------------------------------------------------------
    # Painting
    # ------------------------------------------------------------------

    def paintEvent(self, event) -> None:
        if self._screen_pixmap is None or self._screen_pixmap.isNull():
            return

        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Dim the whole screen
        p.fillRect(self.rect(), QColor(0, 0, 0, 120))

        # Sample colour under cursor
        local_pos = self._pos - self._screen_offset
        if self._screen_pixmap.rect().contains(local_pos):
            img = self._screen_pixmap.toImage()
            self._current_color = QColor(img.pixel(local_pos))

        # Magnifier position – top-left of the magnifier circle
        mx = self._pos.x() - _MAGNIFY_RADIUS
        my = self._pos.y() - _MAGNIFY_RADIUS

        # Draw magnified pixel grid
        self._draw_magnifier(p, mx, my)

        # Draw bottom info bar
        self._draw_info_bar(p)

        p.end()

    def _draw_magnifier(self, p: QPainter, mx: int, my: int) -> None:
        """Draw the magnifying glass with pixel grid."""
        if self._screen_pixmap is None:
            return

        img = self._screen_pixmap.toImage()
        grid_half = _GRID_SIZE // 2
        cursor_local = self._pos - self._screen_offset
        cell = _MAGNIFY_RADIUS * 2 / _GRID_SIZE

        # Clip to magnifier circle
        from PySide6.QtGui import QRegion, QPainterPath
        clip_path = QPainterPath()
        clip_path.addEllipse(mx, my, _MAGNIFY_RADIUS * 2, _MAGNIFY_RADIUS * 2)
        p.save()
        p.setClipPath(clip_path)

        # Dark background
        p.fillRect(int(mx), int(my), _MAGNIFY_RADIUS * 2, _MAGNIFY_RADIUS * 2, QColor(30, 30, 30))

        # Draw each pixel
        for row in range(-grid_half, grid_half + 1):
            for col in range(-grid_half, grid_half + 1):
                sx = cursor_local.x() + col
                sy = cursor_local.y() + row
                if img.rect().contains(sx, sy):
                    pixel_color = QColor(img.pixel(sx, sy))
                else:
                    pixel_color = QColor(0, 0, 0, 0)
                px = mx + (col + grid_half) * cell
                py = my + (row + grid_half) * cell
                p.fillRect(int(px), int(py), int(cell) + 1, int(cell) + 1, pixel_color)

        # Grid lines
        p.setPen(QPen(QColor(255, 255, 255, 40), 0.5))
        for i in range(_GRID_SIZE + 1):
            # Vertical
            lx = mx + i * cell
            p.drawLine(int(lx), int(my), int(lx), int(my + _MAGNIFY_RADIUS * 2))
            # Horizontal
            ly = my + i * cell
            p.drawLine(int(mx), int(ly), int(mx + _MAGNIFY_RADIUS * 2), int(ly))

        p.restore()

        # Circle border
        pen = QPen(QColor("#0891B2"), 3)
        p.setPen(pen)
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawEllipse(int(mx), int(my), _MAGNIFY_RADIUS * 2, _MAGNIFY_RADIUS * 2)

        # Center crosshair
        center = _MAGNIFY_RADIUS
        p.setPen(QPen(QColor(255, 255, 255, 180), 1))
        p.drawLine(mx + center - _INNER_RADIUS, my + center, mx + center + _INNER_RADIUS, my + center)
        p.drawLine(mx + center, my + center - _INNER_RADIUS, mx + center, my + center + _INNER_RADIUS)

    def _draw_info_bar(self, p: QPainter) -> None:
        """Draw the colour information bar at the bottom of the screen."""
        bar_rect = QRect(0, self.height() - _COLOR_BAR_H, self.width(), _COLOR_BAR_H)
        p.fillRect(bar_rect, QColor(20, 20, 20, 220))

        # Colour swatch
        swatch_size = _COLOR_BAR_H - 16
        swatch_rect = QRect(20, bar_rect.y() + 8, swatch_size, swatch_size)
        p.fillRect(swatch_rect, self._current_color)
        p.setPen(QPen(QColor(255, 255, 255, 120), 1))
        p.drawRect(swatch_rect)

        # Text
        p.setPen(QColor(255, 255, 255))
        font = p.font()
        font.setPointSize(12)
        font.setBold(True)
        p.setFont(font)
        hex_str = self._current_color.name().upper()
        rgb_str = (
            f"RGB({self._current_color.red()}, "
            f"{self._current_color.green()}, "
            f"{self._current_color.blue()})"
        )
        hsl_str = (
            f"HSL({self._current_color.hue()}, "
            f"{self._current_color.saturation()}%, "
            f"{self._current_color.lightness()}%)"
        )
        text = f"{hex_str}    {rgb_str}    {hsl_str}"
        p.drawText(swatch_rect.right() + 16, bar_rect.y() + _COLOR_BAR_H // 2 + 5, text)

        # Hint
        font.setBold(False)
        font.setPointSize(10)
        p.setFont(font)
        p.setPen(QColor(255, 255, 255, 150))
        hint = tr("Clic para copiar · Esc para cancelar")
        p.drawText(
            self.width() - p.fontMetrics().horizontalAdvance(hint) - 20,
            bar_rect.y() + _COLOR_BAR_H // 2 + 4,
            hint,
        )

    # ------------------------------------------------------------------
    # Input
    # ------------------------------------------------------------------

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._timer.stop()
            color = QColor(self._current_color)
            self.color_picked.emit(color)
            self.close()
        elif event.button() == Qt.MouseButton.RightButton:
            self._timer.stop()
            self.close()

    def keyPressEvent(self, event) -> None:
        if event.key() in (Qt.Key.Key_Escape, Qt.Key.Key_Return):
            self._timer.stop()
            self.close()
        super().keyPressEvent(event)