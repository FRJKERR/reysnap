"""PinSnap – pinned screenshot window.

:class:`PinWindow` displays a screenshot as an always-on-top, frameless
overlay that can be freely moved, resized, scrolled, and closed.
"""

from __future__ import annotations

import logging

from PySide6.QtCore import (
    QPoint,
    QRect,
    QSize,
    Qt,
    Signal,
)
from PySide6.QtGui import (
    QColor,
    QCursor,
    QMouseEvent,
    QPainter,
    QPixmap,
)
from PySide6.QtWidgets import (
    QApplication,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from ..config import AppConfig

logger = logging.getLogger(__name__)

# Sizing thresholds
_MIN_SIZE = 80
_EDGE_SIZE = 8  # pixels from edge for resize handles
_CORNER_SIZE = 16  # pixels in corners for diagonal resize


class _PinnedImageWidget(QWidget):
    """Renders the pinned pixmap, handling optional border."""

    def __init__(self, pixmap: QPixmap, show_border: bool = True, parent: QWidget | None = None):
        super().__init__(parent)
        self._pixmap = pixmap
        self._show_border = show_border
        self.setFixedSize(pixmap.size())

    def paintEvent(self, event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        p.drawPixmap(0, 0, self._pixmap)
        if self._show_border:
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(Qt.BrushStyle.NoBrush)
            pen = p.pen()
            pen.setColor(QColor(255, 255, 255, 80))
            pen.setWidth(1)
            p.setPen(pen)
            p.drawRect(0, 0, self.width() - 1, self.height() - 1)
        p.end()

    def pixmap(self) -> QPixmap:
        return self._pixmap


class PinWindow(QWidget):
    """Always-on-top, frameless window displaying a pinned screenshot.

    Features:
    * Draggable by clicking anywhere on the image
    * Resizable from edges and corners
    * Scrollable when shrunk smaller than the image
    * Close on middle-click or ``Esc``
    * Opacity controlled by config

    Signals
    -------
    closed()
        Emitted just before the window is closed.
    """

    closed = Signal()

    def __init__(self, pixmap: QPixmap, config: AppConfig, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._config = config
        self._original_pixmap = pixmap

        # Window flags
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, False)

        # Opacity
        opacity_pct = config.pin_opacity
        self.setWindowOpacity(opacity_pct / 100.0)

        # Layout: scroll area containing the image
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self._scroll = QScrollArea()
        self._scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self._scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)

        self._image_widget = _PinnedImageWidget(pixmap, show_border=config.pin_border)
        self._scroll.setWidget(self._image_widget)
        layout.addWidget(self._scroll)

        # Initial size – the image size, capped at 80 % of screen
        screen = QApplication.primaryScreen()
        screen_geo = screen.availableGeometry() if screen else QRect(0, 0, 1920, 1080)
        max_w = int(screen_geo.width() * 0.8)
        max_h = int(screen_geo.height() * 0.8)
        w = min(pixmap.width(), max_w)
        h = min(pixmap.height(), max_h)
        self.resize(w, h)

        # Center on screen
        self.move(
            screen_geo.x() + (screen_geo.width() - w) // 2,
            screen_geo.y() + (screen_geo.height() - h) // 2,
        )

        # Interaction state
        self._dragging = False
        self._resizing = False
        self._resize_edge: int = 0  # bitmask
        self._drag_offset = QPoint()
        self._cursor_override = False

        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self._update_cursor_shape(QCursor.pos())

    # ------------------------------------------------------------------
    # Cursor & resize-edge detection
    # ------------------------------------------------------------------

    def _detect_edge(self, pos: QPoint) -> int:
        """Return a bitmask indicating which edges/corners the cursor is near.

        Bit 0 = left, 1 = right, 2 = top, 3 = bottom
        """
        w, h = self.width(), self.height()
        edge = 0
        if pos.x() < _EDGE_SIZE:
            edge |= 0b0001  # left
        elif pos.x() > w - _EDGE_SIZE:
            edge |= 0b0010  # right
        if pos.y() < _EDGE_SIZE:
            edge |= 0b0100  # top
        elif pos.y() > h - _EDGE_SIZE:
            edge |= 0b1000  # bottom
        return edge

    def _edge_cursor(self, edge: int) -> Qt.CursorShape:
        if edge in (0b0001, 0b0010):
            return Qt.CursorShape.SizeHorCursor
        if edge in (0b0100, 0b1000):
            return Qt.CursorShape.SizeVerCursor
        if edge in (0b0101, 0b1010):
            return Qt.CursorShape.SizeFDiagCursor
        if edge in (0b0110, 0b1001):
            return Qt.CursorShape.SizeBDiagCursor
        return Qt.CursorShape.ArrowCursor

    def _update_cursor_shape(self, global_pos: QPoint) -> None:
        local = self.mapFromGlobal(global_pos)
        edge = self._detect_edge(local)
        if edge:
            self.setCursor(self._edge_cursor(edge))
            self._cursor_override = True
        elif self._cursor_override:
            self.unsetCursor()
            self._cursor_override = False

    # ------------------------------------------------------------------
    # Mouse events
    # ------------------------------------------------------------------

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.MiddleButton:
            self.close()
            return
        if event.button() != Qt.MouseButton.LeftButton:
            return

        local_pos = event.position().toPoint()
        edge = self._detect_edge(local_pos)
        if edge:
            self._resizing = True
            self._resize_edge = edge
            self._resize_start_geo = self.geometry()
            self._resize_start_pos = event.globalPosition().toPoint()
        else:
            self._dragging = True
            self._drag_offset = event.globalPosition().toPoint() - self.pos()

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        global_pos = event.globalPosition().toPoint()

        if self._resizing and self._resize_start_geo is not None:
            delta = global_pos - self._resize_start_pos
            geo = QRect(self._resize_start_geo)
            edge = self._resize_edge

            if edge & 0b0001:  # left
                new_left = geo.left() + delta.x()
                if self._resize_start_geo.right() - new_left >= _MIN_SIZE:
                    geo.setLeft(new_left)
            if edge & 0b0010:  # right
                new_right = geo.right() + delta.x()
                if new_right - geo.left() >= _MIN_SIZE:
                    geo.setRight(new_right)
            if edge & 0b0100:  # top
                new_top = geo.top() + delta.y()
                if self._resize_start_geo.bottom() - new_top >= _MIN_SIZE:
                    geo.setTop(new_top)
            if edge & 0b1000:  # bottom
                new_bottom = geo.bottom() + delta.y()
                if new_bottom - geo.top() >= _MIN_SIZE:
                    geo.setBottom(new_bottom)

            self.setGeometry(geo)
        elif self._dragging:
            self.move(global_pos - self._drag_offset)
        else:
            self._update_cursor_shape(global_pos)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        self._dragging = False
        self._resizing = False
        self._resize_start_geo = None

    def mouseDoubleClickEvent(self, event: QMouseEvent) -> None:
        """Double-click toggles between actual size and fit-to-window."""
        if event.button() == Qt.MouseButton.LeftButton:
            img_w = self._original_pixmap.width()
            img_h = self._original_pixmap.height()
            if self.width() == img_w and self.height() == img_h:
                # Fit to 80% of screen
                screen = QApplication.primaryScreen()
                sg = screen.availableGeometry() if screen else QRect(0, 0, 1920, 1080)
                self.resize(min(img_w, int(sg.width() * 0.8)), min(img_h, int(sg.height() * 0.8)))
            else:
                self.resize(img_w, img_h)

    def keyPressEvent(self, event) -> None:
        if event.key() == Qt.Key.Key_Escape:
            self.close()
        elif event.key() == Qt.Key.Key_Plus or event.key() == Qt.Key.Key_Equal:
            self.resize(int(self.width() * 1.1), int(self.height() * 1.1))
        elif event.key() == Qt.Key.Key_Minus:
            self.resize(int(self.width() * 0.9), int(self.height() * 0.9))
        else:
            super().keyPressEvent(event)

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def closeEvent(self, event) -> None:
        self.closed.emit()
        logger.debug("Pin window closed")
        super().closeEvent(event)