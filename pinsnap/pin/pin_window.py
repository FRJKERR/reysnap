"""PinSnap – pinned screenshot window.

:class:`PinWindow` displays a screenshot as an always-on-top, frameless
floating image, replicating PixPin's documented pin interactions:

* Mouse wheel        → zoom in/out (5 %–500 %)
* Ctrl + wheel       → opacity up/down
* Middle click       → restore original size and opacity
* Drag               → move; edge drag → uniform (aspect-keeping) zoom
* Double click / Esc / Ctrl+W → close
* ``L``              → lock (ignore move/zoom/opacity changes)
* ``T``              → toggle always-on-top
* Right click        → context menu (copy, save, lock, opacity, …)
* Border colour reflects state: accent = active, grey = inactive,
  orange = locked.
"""

from __future__ import annotations

import logging

from PySide6.QtCore import QPoint, QRect, Qt, Signal
from PySide6.QtGui import (
    QAction,
    QColor,
    QCursor,
    QGuiApplication,
    QMouseEvent,
    QPainter,
    QPixmap,
)
from PySide6.QtWidgets import (
    QApplication,
    QFileDialog,
    QMenu,
    QWidget,
)

from ..config import AppConfig
from ..i18n import tr

logger = logging.getLogger(__name__)

_MIN_ZOOM = 0.05
_MAX_ZOOM = 5.0
_ZOOM_STEP = 1.1          # wheel step factor
_OPACITY_STEP = 5         # percent per wheel step
_EDGE_SIZE = 8            # px near an edge that trigger resize-zoom

_BORDER_ACTIVE = QColor("#0891B2")   # accent – focused
_BORDER_INACTIVE = QColor(128, 128, 128, 180)
_BORDER_LOCKED = QColor("#F59E0B")   # orange – locked


class PinWindow(QWidget):
    """Always-on-top, frameless floating image (PixPin-style pin).

    Signals
    -------
    closed()
        Emitted just before the window is closed.
    """

    closed = Signal()

    def __init__(self, pixmap: QPixmap, config: AppConfig, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._config = config
        self._pixmap = pixmap
        self._zoom = 1.0
        self._locked = False
        self._on_top = True
        self._show_border = config.pin_border
        self._opacity = max(10, min(100, config.pin_opacity))

        self._apply_window_flags()
        self.setWindowOpacity(self._opacity / 100.0)
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

        # Initial size: image size capped at 80 % of the screen
        screen = QApplication.primaryScreen()
        screen_geo = screen.availableGeometry() if screen else QRect(0, 0, 1920, 1080)
        if pixmap.width() > 0 and pixmap.height() > 0:
            max_zoom_w = screen_geo.width() * 0.8 / pixmap.width()
            max_zoom_h = screen_geo.height() * 0.8 / pixmap.height()
            self._zoom = min(1.0, max_zoom_w, max_zoom_h)
        self._apply_zoom(center_on_cursor=False)

        # Centre on screen
        self.move(
            screen_geo.x() + (screen_geo.width() - self.width()) // 2,
            screen_geo.y() + (screen_geo.height() - self.height()) // 2,
        )

        # Interaction state
        self._dragging = False
        self._drag_offset = QPoint()
        self._resizing = False
        self._resize_start_zoom = 1.0
        self._resize_start_pos = QPoint()
        self._resize_anchor = QPoint()

    # ------------------------------------------------------------------
    # Window flags / state helpers
    # ------------------------------------------------------------------

    def _apply_window_flags(self) -> None:
        flags = Qt.WindowType.FramelessWindowHint | Qt.WindowType.Tool
        if self._on_top:
            flags |= Qt.WindowType.WindowStaysOnTopHint
        visible = self.isVisible()
        self.setWindowFlags(flags)
        if visible:
            self.show()

    def _border_color(self) -> QColor:
        if self._locked:
            return _BORDER_LOCKED
        if self.isActiveWindow():
            return _BORDER_ACTIVE
        return _BORDER_INACTIVE

    def _scaled_size(self):
        return (
            max(1, round(self._pixmap.width() * self._zoom)),
            max(1, round(self._pixmap.height() * self._zoom)),
        )

    def _apply_zoom(self, center_on_cursor: bool = True) -> None:
        """Resize the window to match the current zoom factor."""
        old_geo = self.geometry()
        w, h = self._scaled_size()
        if center_on_cursor and self.isVisible():
            # Keep the point under the cursor stable while zooming
            cursor = self.mapFromGlobal(QCursor.pos())
            if old_geo.width() > 0 and old_geo.height() > 0:
                fx = cursor.x() / old_geo.width()
                fy = cursor.y() / old_geo.height()
            else:
                fx = fy = 0.5
            new_x = self.x() - round(fx * (w - old_geo.width()))
            new_y = self.y() - round(fy * (h - old_geo.height()))
            self.setGeometry(new_x, new_y, w, h)
        else:
            self.resize(w, h)
        self.update()

    # ------------------------------------------------------------------
    # Painting
    # ------------------------------------------------------------------

    def paintEvent(self, event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        p.drawPixmap(self.rect(), self._pixmap)
        if self._show_border:
            p.setPen(self._border_color())
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawRect(0, 0, self.width() - 1, self.height() - 1)
        p.end()

    # Repaint the border when the active-window state changes
    def focusInEvent(self, event) -> None:
        self.update()
        super().focusInEvent(event)

    def focusOutEvent(self, event) -> None:
        self.update()
        super().focusOutEvent(event)

    # ------------------------------------------------------------------
    # Zoom / opacity
    # ------------------------------------------------------------------

    def wheelEvent(self, event) -> None:
        if self._locked:
            return
        steps = event.angleDelta().y() / 120.0
        if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            # Opacity
            self._opacity = max(10, min(100, round(self._opacity + steps * _OPACITY_STEP)))
            self.setWindowOpacity(self._opacity / 100.0)
        else:
            # Zoom
            factor = _ZOOM_STEP ** steps
            self._zoom = max(_MIN_ZOOM, min(_MAX_ZOOM, self._zoom * factor))
            self._apply_zoom()

    def _reset(self) -> None:
        """Middle click – restore original size and configured opacity."""
        if self._locked:
            return
        self._zoom = 1.0
        self._opacity = max(10, min(100, self._config.pin_opacity))
        self.setWindowOpacity(self._opacity / 100.0)
        self._apply_zoom(center_on_cursor=False)

    # ------------------------------------------------------------------
    # Mouse events
    # ------------------------------------------------------------------

    def _near_edge(self, pos: QPoint) -> bool:
        return (
            pos.x() < _EDGE_SIZE
            or pos.x() > self.width() - _EDGE_SIZE
            or pos.y() < _EDGE_SIZE
            or pos.y() > self.height() - _EDGE_SIZE
        )

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.MiddleButton:
            self._reset()
            return
        if event.button() != Qt.MouseButton.LeftButton:
            return
        if self._locked:
            return

        pos = event.position().toPoint()
        if self._near_edge(pos):
            # Edge drag zooms uniformly (PixPin keeps the aspect ratio)
            self._resizing = True
            self._resize_start_zoom = self._zoom
            self._resize_start_pos = event.globalPosition().toPoint()
            self._resize_anchor = self.geometry().topLeft()
        else:
            self._dragging = True
            self._drag_offset = event.globalPosition().toPoint() - self.pos()

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        global_pos = event.globalPosition().toPoint()

        if self._resizing:
            delta = global_pos - self._resize_start_pos
            base_w = self._pixmap.width() * self._resize_start_zoom
            if base_w > 0:
                factor = (base_w + delta.x() + delta.y()) / base_w
                self._zoom = max(_MIN_ZOOM, min(_MAX_ZOOM, self._resize_start_zoom * factor))
                w, h = self._scaled_size()
                self.setGeometry(self._resize_anchor.x(), self._resize_anchor.y(), w, h)
        elif self._dragging:
            self.move(global_pos - self._drag_offset)
        else:
            pos = event.position().toPoint()
            if not self._locked and self._near_edge(pos):
                self.setCursor(Qt.CursorShape.SizeFDiagCursor)
            else:
                self.unsetCursor()

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        self._dragging = False
        self._resizing = False

    def mouseDoubleClickEvent(self, event: QMouseEvent) -> None:
        """Double click closes the pin (PixPin behaviour)."""
        if event.button() == Qt.MouseButton.LeftButton and not self._locked:
            self.close()

    # ------------------------------------------------------------------
    # Context menu
    # ------------------------------------------------------------------

    def contextMenuEvent(self, event) -> None:
        menu = QMenu(self)

        act_copy = QAction(tr("Copiar imagen"), menu)
        act_copy.triggered.connect(self._copy_to_clipboard)
        menu.addAction(act_copy)

        act_save = QAction(tr("Guardar como…"), menu)
        act_save.triggered.connect(self._save_as)
        menu.addAction(act_save)

        menu.addSeparator()

        act_lock = QAction(tr("Bloquear"), menu)
        act_lock.setCheckable(True)
        act_lock.setChecked(self._locked)
        act_lock.triggered.connect(self._toggle_lock)
        menu.addAction(act_lock)

        act_top = QAction(tr("Siempre visible"), menu)
        act_top.setCheckable(True)
        act_top.setChecked(self._on_top)
        act_top.triggered.connect(self._toggle_on_top)
        menu.addAction(act_top)

        act_border = QAction(tr("Mostrar borde"), menu)
        act_border.setCheckable(True)
        act_border.setChecked(self._show_border)
        act_border.triggered.connect(self._toggle_border)
        menu.addAction(act_border)

        opacity_menu = menu.addMenu(tr("Opacidad"))
        for pct in (100, 90, 75, 50, 25):
            act = QAction(f"{pct} %", opacity_menu)
            act.setCheckable(True)
            act.setChecked(self._opacity == pct)
            act.triggered.connect(lambda _=False, v=pct: self._set_opacity(v))
            opacity_menu.addAction(act)

        act_reset = QAction(tr("Tamaño original (100 %)"), menu)
        act_reset.triggered.connect(self._reset)
        menu.addAction(act_reset)

        menu.addSeparator()

        act_close = QAction(tr("Cerrar") + "\tEsc", menu)
        act_close.triggered.connect(self.close)
        menu.addAction(act_close)

        menu.exec(event.globalPos())

    # ------------------------------------------------------------------
    # Context-menu actions
    # ------------------------------------------------------------------

    def _copy_to_clipboard(self) -> None:
        QGuiApplication.clipboard().setPixmap(self._pixmap)
        logger.debug("Pin copied to clipboard")

    def _save_as(self) -> None:
        path, _ = QFileDialog.getSaveFileName(
            self,
            tr("Guardar imagen anclada"),
            str(self._config.save_directory / "pinsnap_pin.png"),
            "PNG (*.png);;JPEG (*.jpg);;BMP (*.bmp);;WebP (*.webp)",
        )
        if path:
            self._pixmap.save(path)

    def _toggle_lock(self) -> None:
        self._locked = not self._locked
        self.update()

    def _toggle_on_top(self) -> None:
        self._on_top = not self._on_top
        self._apply_window_flags()

    def _toggle_border(self) -> None:
        self._show_border = not self._show_border
        self.update()

    def _set_opacity(self, pct: int) -> None:
        self._opacity = max(10, min(100, pct))
        self.setWindowOpacity(self._opacity / 100.0)

    # ------------------------------------------------------------------
    # Keyboard
    # ------------------------------------------------------------------

    def keyPressEvent(self, event) -> None:
        key = event.key()
        mods = event.modifiers()

        if key == Qt.Key.Key_Escape:
            self.close()
        elif key == Qt.Key.Key_W and mods & Qt.KeyboardModifier.ControlModifier:
            self.close()
        elif key == Qt.Key.Key_C and mods & Qt.KeyboardModifier.ControlModifier:
            self._copy_to_clipboard()
        elif key == Qt.Key.Key_S and mods & Qt.KeyboardModifier.ControlModifier:
            self._save_as()
        elif key == Qt.Key.Key_L:
            self._toggle_lock()
        elif key == Qt.Key.Key_T:
            self._toggle_on_top()
        elif key in (Qt.Key.Key_Plus, Qt.Key.Key_Equal) and not self._locked:
            self._zoom = min(_MAX_ZOOM, self._zoom * _ZOOM_STEP)
            self._apply_zoom(center_on_cursor=False)
        elif key == Qt.Key.Key_Minus and not self._locked:
            self._zoom = max(_MIN_ZOOM, self._zoom / _ZOOM_STEP)
            self._apply_zoom(center_on_cursor=False)
        else:
            super().keyPressEvent(event)

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def pixmap(self) -> QPixmap:
        return self._pixmap

    def closeEvent(self, event) -> None:
        self.closed.emit()
        logger.debug("Pin window closed")
        super().closeEvent(event)
