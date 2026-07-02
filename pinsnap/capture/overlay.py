"""PinSnap – PixPin-style capture overlay.

A single fullscreen surface that handles the whole capture flow the
way PixPin/Snipaste do:

1. The screen is frozen (captured once via the backend) and shown as
   the overlay background, so the overlay itself never appears in the
   final screenshot.
2. Before dragging, the window under the cursor is highlighted and a
   pixel magnifier follows the mouse (position + colour readout).
   A single click selects the highlighted window.
3. After selecting, the region can be moved and resized with handles,
   and a toolbar attached below the selection offers annotation tools
   (rectangle, ellipse, arrow, pen, marker, text), undo, and the final
   actions: pin, copy, save, cancel — all without leaving the overlay.

The composited result (crop + annotations) is delivered through the
``finished(action, pixmap)`` signal, where *action* is ``"copy"``,
``"pin"`` or ``"save"``.
"""

from __future__ import annotations

import logging
from enum import Enum, auto
from typing import List, Optional

from PySide6.QtCore import QPoint, QRect, QSize, Qt, Signal
from PySide6.QtGui import (
    QColor,
    QCursor,
    QFont,
    QIcon,
    QImage,
    QKeyEvent,
    QMouseEvent,
    QPainter,
    QPen,
    QPixmap,
)
from PySide6.QtWidgets import QHBoxLayout, QLineEdit, QToolButton, QWidget

from ..annotation.editor import (
    AnnotationItem,
    ArrowItem,
    EllipseItem,
    FreehandItem,
    NumberItem,
    RectItem,
    TextItem,
)
from .backend import CaptureBackend

logger = logging.getLogger(__name__)

# Selection handle hit area (logical px)
_HANDLE = 6
_MIN_SEL = 8

# Magnifier
_MAG_GRID = 13          # odd – pixels sampled around the cursor
_MAG_CELL = 9           # on-screen size of one magnified pixel
_MAG_OFFSET = 24        # distance from the cursor

_ACCENT = QColor("#0891B2")

_PALETTE = [
    "#E81123", "#FF8C00", "#FFD400", "#16C60C",
    "#0078D7", "#886CE4", "#000000", "#FFFFFF",
]
_WIDTHS = [2, 4, 6]


class _Tool(Enum):
    NONE = auto()
    RECT = auto()
    ELLIPSE = auto()
    ARROW = auto()
    PEN = auto()
    MARKER = auto()
    TEXT = auto()
    NUMBER = auto()


class _State(Enum):
    PICKING = auto()    # nothing selected yet – window highlight + magnifier
    DRAGGING = auto()   # rubber-band drag in progress
    SELECTED = auto()   # region fixed – annotate / adjust / act


# ----------------------------------------------------------------------
# X11 window enumeration (for window auto-detection before dragging)
# ----------------------------------------------------------------------

def _list_x11_window_rects() -> List[QRect]:
    """Return top-level window rects in stacking order (bottom → top).

    Physical (X11) pixel coordinates.  Empty list on Wayland or error.
    """
    try:
        from Xlib import X, display
    except ImportError:
        return []

    rects: List[QRect] = []
    try:
        dpy = display.Display()
        root = dpy.screen().root
        for win in root.query_tree().children:
            try:
                attrs = win.get_attributes()
                if attrs.map_state != X.IsViewable:
                    continue
                geo = win.get_geometry()
                if geo.width < 20 or geo.height < 20:
                    continue
                rects.append(QRect(geo.x, geo.y, geo.width, geo.height))
            except Exception:
                continue
        dpy.close()
    except Exception:
        logger.debug("X11 window enumeration failed", exc_info=True)
        return []
    return rects


# ----------------------------------------------------------------------
# Procedural toolbar icons (white line art on transparent background)
# ----------------------------------------------------------------------

def _make_icon(kind: str, size: int = 20) -> QIcon:
    pm = QPixmap(size, size)
    pm.fill(Qt.GlobalColor.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    pen = QPen(QColor(235, 235, 235), 1.6)
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
    p.setPen(pen)
    p.setBrush(Qt.BrushStyle.NoBrush)
    m = 4  # margin

    if kind == "rect":
        p.drawRect(m, m + 1, size - 2 * m, size - 2 * m - 2)
    elif kind == "ellipse":
        p.drawEllipse(m, m + 1, size - 2 * m, size - 2 * m - 2)
    elif kind == "arrow":
        p.drawLine(m, size - m, size - m, m)
        p.drawLine(size - m, m, size - m - 6, m + 1)
        p.drawLine(size - m, m, size - m - 1, m + 6)
    elif kind == "pen":
        p.drawLine(m, size - m, size - m - 2, m + 2)
        p.drawLine(m, size - m, m + 3, size - m - 1)
    elif kind == "marker":
        pen.setWidth(5)
        pen.setColor(QColor(235, 235, 100, 180))
        p.setPen(pen)
        p.drawLine(m, size - m - 2, size - m, m + 2)
    elif kind == "text":
        f = QFont("Sans", int(size * 0.62))
        f.setBold(True)
        p.setFont(f)
        p.drawText(pm.rect(), Qt.AlignmentFlag.AlignCenter, "T")
    elif kind == "number":
        p.drawEllipse(m - 1, m - 1, size - 2 * m + 2, size - 2 * m + 2)
        f = QFont("Sans", int(size * 0.5))
        f.setBold(True)
        p.setFont(f)
        p.drawText(pm.rect(), Qt.AlignmentFlag.AlignCenter, "1")
    elif kind == "undo":
        p.drawArc(m, m + 2, size - 2 * m, size - 2 * m - 2, 30 * 16, 220 * 16)
        p.drawLine(m, m + 4, m + 5, m + 2)
        p.drawLine(m, m + 4, m + 4, m + 9)
    elif kind == "pin":
        # simple push-pin: head circle + needle
        p.setBrush(QColor(235, 235, 235))
        p.drawEllipse(size // 2 - 4, m, 8, 8)
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawLine(size // 2, m + 8, size // 2, size - m)
    elif kind == "copy":
        p.drawRect(m + 3, m + 3, size - 2 * m - 3, size - 2 * m - 3)
        p.drawRect(m, m, size - 2 * m - 3, size - 2 * m - 3)
    elif kind == "save":
        p.drawRect(m, m, size - 2 * m, size - 2 * m)
        p.drawLine(m + 3, m, m + 3, m + 5)
        p.drawLine(size - m - 3, m, size - m - 3, m + 5)
        p.drawRect(m + 4, size // 2 + 1, size - 2 * m - 8, size - m - (size // 2 + 1))
    elif kind == "close":
        p.drawLine(m + 1, m + 1, size - m - 1, size - m - 1)
        p.drawLine(size - m - 1, m + 1, m + 1, size - m - 1)
    elif kind == "check":
        p.drawLine(m, size // 2 + 1, size // 2 - 1, size - m - 1)
        p.drawLine(size // 2 - 1, size - m - 1, size - m, m + 1)

    p.end()
    return QIcon(pm)


class _TextEdit(QLineEdit):
    """Inline text input for the TEXT tool (Esc cancels)."""

    cancelled = Signal()

    def keyPressEvent(self, event: QKeyEvent) -> None:
        if event.key() == Qt.Key.Key_Escape:
            self.cancelled.emit()
            return
        super().keyPressEvent(event)


# ----------------------------------------------------------------------
# The overlay
# ----------------------------------------------------------------------

class CaptureOverlay(QWidget):
    """Fullscreen frozen-screen capture editor (PixPin-style flow).

    Signals
    -------
    finished(str, QPixmap)
        Emitted with ``"copy"``, ``"pin"`` or ``"save"`` and the final
        composited image.  The overlay closes itself afterwards.
    cancelled()
        Emitted when the user aborts (Esc / close button).
    """

    finished = Signal(str, QPixmap)
    cancelled = Signal()

    def __init__(
        self,
        backend: CaptureBackend,
        default_action: str = "copy",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._backend = backend
        self._default_action = default_action

        # Freeze the screen *before* the overlay is shown.
        self._snapshot: QPixmap = backend.capture_screen()
        if self._snapshot.isNull():
            logger.warning("Backend returned null snapshot; falling back to Qt grab")
            from PySide6.QtGui import QGuiApplication
            screen = QGuiApplication.primaryScreen()
            self._snapshot = screen.grabWindow(0) if screen else QPixmap()
        self._snapshot_img: QImage = self._snapshot.toImage()

        # Window auto-detection (gathered now, before our window maps)
        self._window_rects = _list_x11_window_rects()

        self._state = _State.PICKING
        self._sel = QRect()               # selection, logical coords
        self._drag_origin = QPoint()
        self._hover_window: Optional[QRect] = None
        self._cursor_pos = QCursor.pos()

        # Selection adjustment
        self._moving = False
        self._resizing = False
        self._resize_edges = 0            # bitmask L=1 R=2 T=4 B=8
        self._adjust_start = QPoint()
        self._sel_start = QRect()

        # Annotation state
        self._tool = _Tool.NONE
        self._color = QColor(_PALETTE[0])
        self._pen_width = _WIDTHS[1]
        self._items: List[AnnotationItem] = []
        self._temp_item: Optional[AnnotationItem] = None
        self._drawing = False
        self._draw_start = QPoint()
        self._freehand: List[QPoint] = []
        self._text_edit: Optional[_TextEdit] = None

        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
            | Qt.WindowType.BypassWindowManagerHint
        )
        self.setCursor(Qt.CursorShape.CrossCursor)
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

        self._build_toolbar()

    # ------------------------------------------------------------------
    # Toolbar
    # ------------------------------------------------------------------

    _TB_STYLE = """
    QWidget#pinsnap_tb {
        background: #2D2D30;
        border: 1px solid #3F3F46;
        border-radius: 6px;
    }
    QToolButton {
        background: transparent;
        border: none;
        border-radius: 4px;
        padding: 3px;
    }
    QToolButton:hover { background: #3E3E42; }
    QToolButton:checked { background: #0891B2; }
    """

    def _build_toolbar(self) -> None:
        self._toolbar = QWidget(self)
        self._toolbar.setObjectName("pinsnap_tb")
        self._toolbar.setStyleSheet(self._TB_STYLE)
        lay = QHBoxLayout(self._toolbar)
        lay.setContentsMargins(6, 4, 6, 4)
        lay.setSpacing(2)

        self._tool_buttons: dict[_Tool, QToolButton] = {}
        for kind, tool, tip in [
            ("rect", _Tool.RECT, "Rectángulo (R)"),
            ("ellipse", _Tool.ELLIPSE, "Elipse (E)"),
            ("arrow", _Tool.ARROW, "Flecha (A)"),
            ("pen", _Tool.PEN, "Lápiz (P)"),
            ("marker", _Tool.MARKER, "Marcador (M)"),
            ("text", _Tool.TEXT, "Texto (T)"),
            ("number", _Tool.NUMBER, "Globos numerados (N)"),
        ]:
            btn = QToolButton(self._toolbar)
            btn.setIcon(_make_icon(kind))
            btn.setIconSize(QSize(20, 20))
            btn.setCheckable(True)
            btn.setToolTip(tip)
            btn.clicked.connect(lambda checked, t=tool: self._on_tool_clicked(t, checked))
            lay.addWidget(btn)
            self._tool_buttons[tool] = btn

        undo = QToolButton(self._toolbar)
        undo.setIcon(_make_icon("undo"))
        undo.setIconSize(QSize(20, 20))
        undo.setToolTip("Deshacer (Ctrl+Z)")
        undo.clicked.connect(self._undo)
        lay.addWidget(undo)

        sep = QWidget(self._toolbar)
        sep.setFixedSize(1, 20)
        sep.setStyleSheet("background:#3F3F46;")
        lay.addWidget(sep)

        for kind, tip, slot in [
            ("pin", "Anclar a la pantalla (F3)", lambda: self._finish("pin")),
            ("save", "Guardar como… (Ctrl+S)", lambda: self._finish("save")),
            ("close", "Cancelar (Esc)", self._cancel),
            ("check", "Copiar y cerrar (Enter)", lambda: self._finish("copy")),
        ]:
            btn = QToolButton(self._toolbar)
            btn.setIcon(_make_icon(kind))
            btn.setIconSize(QSize(20, 20))
            btn.setToolTip(tip)
            btn.clicked.connect(slot)
            lay.addWidget(btn)

        self._toolbar.adjustSize()
        self._toolbar.hide()

        # --- Options row (colours + stroke widths), shown with a tool ---
        self._options = QWidget(self)
        self._options.setObjectName("pinsnap_tb")
        self._options.setStyleSheet(self._TB_STYLE)
        opt_lay = QHBoxLayout(self._options)
        opt_lay.setContentsMargins(8, 5, 8, 5)
        opt_lay.setSpacing(4)

        self._width_buttons: List[QToolButton] = []
        for w in _WIDTHS:
            btn = QToolButton(self._options)
            btn.setCheckable(True)
            btn.setChecked(w == self._pen_width)
            btn.setFixedSize(22, 22)
            btn.setToolTip(f"Grosor {w}px")
            pm = QPixmap(18, 18)
            pm.fill(Qt.GlobalColor.transparent)
            pp = QPainter(pm)
            pp.setRenderHint(QPainter.RenderHint.Antialiasing)
            pp.setBrush(QColor(235, 235, 235))
            pp.setPen(Qt.PenStyle.NoPen)
            r = 1 + w
            pp.drawEllipse(QPoint(9, 9), r, r)
            pp.end()
            btn.setIcon(QIcon(pm))
            btn.clicked.connect(lambda _=False, ww=w: self._set_width(ww))
            opt_lay.addWidget(btn)
            self._width_buttons.append(btn)

        sep2 = QWidget(self._options)
        sep2.setFixedSize(1, 18)
        sep2.setStyleSheet("background:#3F3F46;")
        opt_lay.addWidget(sep2)

        self._color_buttons: List[QToolButton] = []
        for c in _PALETTE:
            btn = QToolButton(self._options)
            btn.setCheckable(True)
            btn.setChecked(QColor(c) == self._color)
            btn.setFixedSize(20, 20)
            btn.setToolTip(c)
            btn.setStyleSheet(
                f"QToolButton {{ background:{c}; border:1px solid #555; border-radius:3px; }}"
                "QToolButton:checked { border:2px solid #0891B2; }"
            )
            btn.clicked.connect(lambda _=False, cc=c: self._set_color(cc))
            opt_lay.addWidget(btn)
            self._color_buttons.append(btn)

        self._options.adjustSize()
        self._options.hide()

    def _on_tool_clicked(self, tool: _Tool, checked: bool) -> None:
        if checked:
            self._tool = tool
            for t, btn in self._tool_buttons.items():
                btn.setChecked(t == tool)
        else:
            self._tool = _Tool.NONE
        self._options.setVisible(self._tool is not _Tool.NONE)
        self._reposition_toolbar()
        self._update_cursor()

    def _set_width(self, w: int) -> None:
        self._pen_width = w
        for btn, ww in zip(self._width_buttons, _WIDTHS):
            btn.setChecked(ww == w)

    def _set_color(self, c: str) -> None:
        self._color = QColor(c)
        for btn, cc in zip(self._color_buttons, _PALETTE):
            btn.setChecked(cc == c)

    # ------------------------------------------------------------------
    # Geometry helpers
    # ------------------------------------------------------------------

    def _scale(self) -> float:
        """Physical (snapshot) pixels per logical (widget) pixel."""
        if self.width() <= 0:
            return 1.0
        return self._snapshot.width() / self.width()

    def _to_logical(self, phys: QRect) -> QRect:
        s = self._scale()
        if s == 1.0:
            return QRect(phys)
        return QRect(
            round(phys.x() / s), round(phys.y() / s),
            round(phys.width() / s), round(phys.height() / s),
        )

    def _to_physical(self, logical: QRect) -> QRect:
        s = self._scale()
        rect = QRect(
            round(logical.x() * s), round(logical.y() * s),
            round(logical.width() * s), round(logical.height() * s),
        )
        return rect.intersected(self._snapshot.rect())

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def showEvent(self, event) -> None:
        super().showEvent(event)
        from PySide6.QtGui import QGuiApplication
        screen = QGuiApplication.primaryScreen()
        if screen:
            self.setGeometry(screen.geometry())
        self.activateWindow()
        self.raise_()
        self.setFocus()
        # BypassWindowManagerHint means the WM won't give us keyboard
        # focus on its own – take it explicitly.
        self.grabKeyboard()

    def closeEvent(self, event) -> None:
        self.releaseKeyboard()
        super().closeEvent(event)

    # ------------------------------------------------------------------
    # Finishing
    # ------------------------------------------------------------------

    def _render_result(self) -> QPixmap:
        """Crop the frozen snapshot to the selection and burn annotations in."""
        phys = self._to_physical(self._sel.normalized())
        crop = self._snapshot.copy(phys)
        if self._items:
            p = QPainter(crop)
            p.setRenderHint(QPainter.RenderHint.Antialiasing)
            s = self._scale()
            p.scale(s, s)
            p.translate(-self._sel.x(), -self._sel.y())
            for item in self._items:
                item.paint(p)
            p.end()
        return crop

    def _finish(self, action: str) -> None:
        if self._state is not _State.SELECTED or self._sel.isEmpty():
            return
        self._commit_text()
        pixmap = self._render_result()
        self.hide()
        self.finished.emit(action, pixmap)
        self.close()

    def _cancel(self) -> None:
        self.hide()
        self.cancelled.emit()
        self.close()

    # ------------------------------------------------------------------
    # Painting
    # ------------------------------------------------------------------

    def paintEvent(self, event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Frozen screen as background (scaled to logical size)
        if not self._snapshot.isNull():
            p.drawPixmap(self.rect(), self._snapshot)

        if self._state is _State.PICKING:
            self._paint_picking(p)
        else:
            self._paint_selection(p)

        if self._state in (_State.PICKING, _State.DRAGGING):
            self._paint_magnifier(p)

        p.end()

    def _paint_picking(self, p: QPainter) -> None:
        p.fillRect(self.rect(), QColor(0, 0, 0, 90))

        hover = self._hover_window
        if hover and not hover.isEmpty():
            # Re-brighten the hovered window and outline it
            phys = self._to_physical(hover)
            p.drawPixmap(hover, self._snapshot, phys)
            pen = QPen(_ACCENT, 2)
            p.setPen(pen)
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawRect(hover.adjusted(1, 1, -1, -1))
            self._paint_size_badge(p, hover)
        else:
            p.setPen(QColor(255, 255, 255, 210))
            f = p.font()
            f.setPointSize(13)
            p.setFont(f)
            p.drawText(
                self.rect(),
                Qt.AlignmentFlag.AlignCenter,
                "Arrastre para seleccionar una región · clic = ventana · Esc para cancelar",
            )

    def _paint_selection(self, p: QPainter) -> None:
        sel = self._sel.normalized()

        # Dim everything outside the selection
        dim = QColor(0, 0, 0, 110)
        p.fillRect(QRect(0, 0, self.width(), sel.top()), dim)
        p.fillRect(QRect(0, sel.bottom() + 1, self.width(), self.height() - sel.bottom() - 1), dim)
        p.fillRect(QRect(0, sel.top(), sel.left(), sel.height()), dim)
        p.fillRect(QRect(sel.right() + 1, sel.top(), self.width() - sel.right() - 1, sel.height()), dim)

        # Annotations (clipped to the selection)
        p.save()
        p.setClipRect(sel)
        for item in self._items:
            item.paint(p)
        if self._temp_item:
            self._temp_item.paint(p)
        p.restore()

        # Border + handles
        pen = QPen(_ACCENT, 2)
        p.setPen(pen)
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawRect(sel)

        if self._state is _State.SELECTED:
            p.setBrush(QColor(255, 255, 255))
            p.setPen(QPen(_ACCENT, 1))
            for hx, hy in self._handle_points(sel):
                p.drawRect(hx - _HANDLE // 2, hy - _HANDLE // 2, _HANDLE, _HANDLE)

        self._paint_size_badge(p, sel)

    @staticmethod
    def _handle_points(sel: QRect):
        cx = sel.center().x()
        cy = sel.center().y()
        return [
            (sel.left(), sel.top()), (cx, sel.top()), (sel.right(), sel.top()),
            (sel.left(), cy), (sel.right(), cy),
            (sel.left(), sel.bottom()), (cx, sel.bottom()), (sel.right(), sel.bottom()),
        ]

    def _paint_size_badge(self, p: QPainter, rect: QRect) -> None:
        s = self._scale()
        label = f"{round(rect.width() * s)} × {round(rect.height() * s)}"
        f = p.font()
        f.setPointSize(9)
        f.setBold(True)
        p.setFont(f)
        fm = p.fontMetrics()
        w = fm.horizontalAdvance(label) + 12
        h = fm.height() + 4

        x = rect.left()
        y = rect.top() - h - 4
        if y < 0:
            y = rect.top() + 4
        x = min(x, self.width() - w - 4)

        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(25, 25, 25, 215))
        p.drawRoundedRect(x, y, w, h, 3, 3)
        p.setPen(QColor(255, 255, 255))
        p.drawText(QRect(x, y, w, h), Qt.AlignmentFlag.AlignCenter, label)

    def _paint_magnifier(self, p: QPainter) -> None:
        if self._snapshot_img.isNull():
            return

        pos = self.mapFromGlobal(self._cursor_pos)
        s = self._scale()
        px = round(pos.x() * s)
        py = round(pos.y() * s)

        size = _MAG_GRID * _MAG_CELL
        info_h = 34
        total_h = size + info_h

        mx = pos.x() + _MAG_OFFSET
        my = pos.y() + _MAG_OFFSET
        if mx + size > self.width():
            mx = pos.x() - _MAG_OFFSET - size
        if my + total_h > self.height():
            my = pos.y() - _MAG_OFFSET - total_h

        half = _MAG_GRID // 2
        center_color = QColor(255, 255, 255)

        # Pixel grid
        for row in range(_MAG_GRID):
            for col in range(_MAG_GRID):
                sx = px + col - half
                sy = py + row - half
                if 0 <= sx < self._snapshot_img.width() and 0 <= sy < self._snapshot_img.height():
                    c = QColor(self._snapshot_img.pixel(sx, sy))
                else:
                    c = QColor(40, 40, 40)
                if row == half and col == half:
                    center_color = QColor(c)
                p.fillRect(mx + col * _MAG_CELL, my + row * _MAG_CELL, _MAG_CELL, _MAG_CELL, c)

        # Centre pixel highlight
        p.setPen(QPen(_ACCENT, 1))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawRect(mx + half * _MAG_CELL, my + half * _MAG_CELL, _MAG_CELL, _MAG_CELL)

        # Frame
        p.setPen(QPen(QColor(60, 60, 60), 1))
        p.drawRect(mx, my, size, size)

        # Info panel
        panel = QRect(mx, my + size, size, info_h)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(25, 25, 25, 230))
        p.drawRect(panel)

        f = p.font()
        f.setPointSize(8)
        f.setBold(False)
        p.setFont(f)
        p.setPen(QColor(255, 255, 255))
        p.drawText(panel.adjusted(6, 2, -6, -info_h // 2),
                   Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                   f"({px}, {py})")
        p.drawText(panel.adjusted(6, info_h // 2, -6, -2),
                   Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                   center_color.name().upper())
        swatch = QRect(panel.right() - 22, panel.top() + 9, 16, 16)
        p.setBrush(center_color)
        p.setPen(QPen(QColor(255, 255, 255, 120), 1))
        p.drawRect(swatch)

    # ------------------------------------------------------------------
    # Window highlight
    # ------------------------------------------------------------------

    def _window_at(self, pos: QPoint) -> Optional[QRect]:
        """Topmost detected window containing *pos* (logical coords)."""
        s = self._scale()
        phys = QPoint(round(pos.x() * s), round(pos.y() * s))
        for rect in reversed(self._window_rects):
            if rect.contains(phys):
                logical = self._to_logical(rect).intersected(self.rect())
                if not logical.isEmpty():
                    return logical
        return None

    # ------------------------------------------------------------------
    # Toolbar placement
    # ------------------------------------------------------------------

    def _reposition_toolbar(self) -> None:
        if self._state is not _State.SELECTED:
            self._toolbar.hide()
            self._options.hide()
            return

        sel = self._sel.normalized()
        tb = self._toolbar
        tb.adjustSize()
        opt = self._options
        opt.adjustSize()

        gap = 8
        x = min(max(sel.right() - tb.width(), 4), self.width() - tb.width() - 4)
        y = sel.bottom() + gap
        rows_h = tb.height() + (opt.height() + 4 if self._tool is not _Tool.NONE else 0)
        if y + rows_h > self.height() - 4:
            y = sel.top() - gap - rows_h
        if y < 4:
            y = min(sel.bottom() - rows_h - gap, self.height() - rows_h - 4)
            x = min(x, sel.right() - tb.width() - gap)
            x = max(x, 4)

        tb.move(x, y)
        tb.show()
        tb.raise_()

        if self._tool is not _Tool.NONE:
            ox = min(max(x + tb.width() - opt.width(), 4), self.width() - opt.width() - 4)
            opt.move(ox, y + tb.height() + 4)
            opt.show()
            opt.raise_()
        else:
            opt.hide()

    # ------------------------------------------------------------------
    # Selection hit-testing
    # ------------------------------------------------------------------

    def _edges_at(self, pos: QPoint) -> int:
        """Bitmask of selection edges near *pos* (L=1 R=2 T=4 B=8)."""
        sel = self._sel.normalized()
        near = _HANDLE + 2
        edges = 0
        on_x = sel.left() - near <= pos.x() <= sel.right() + near
        on_y = sel.top() - near <= pos.y() <= sel.bottom() + near
        if abs(pos.x() - sel.left()) <= near and on_y:
            edges |= 1
        if abs(pos.x() - sel.right()) <= near and on_y:
            edges |= 2
        if abs(pos.y() - sel.top()) <= near and on_x:
            edges |= 4
        if abs(pos.y() - sel.bottom()) <= near and on_x:
            edges |= 8
        return edges

    def _update_cursor(self) -> None:
        pos = self.mapFromGlobal(QCursor.pos())
        if self._state is not _State.SELECTED:
            self.setCursor(Qt.CursorShape.CrossCursor)
            return
        edges = self._edges_at(pos)
        if edges in (1, 2):
            self.setCursor(Qt.CursorShape.SizeHorCursor)
        elif edges in (4, 8):
            self.setCursor(Qt.CursorShape.SizeVerCursor)
        elif edges in (5, 10):
            self.setCursor(Qt.CursorShape.SizeFDiagCursor)
        elif edges in (6, 9):
            self.setCursor(Qt.CursorShape.SizeBDiagCursor)
        elif self._sel.normalized().contains(pos):
            if self._tool is _Tool.NONE:
                self.setCursor(Qt.CursorShape.SizeAllCursor)
            else:
                self.setCursor(Qt.CursorShape.CrossCursor)
        else:
            self.setCursor(Qt.CursorShape.ArrowCursor)

    # ------------------------------------------------------------------
    # Mouse handling
    # ------------------------------------------------------------------

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() != Qt.MouseButton.LeftButton:
            if event.button() == Qt.MouseButton.RightButton:
                # Right-click: clear selection, or cancel from picking state
                if self._state is _State.SELECTED:
                    self._reset_to_picking()
                else:
                    self._cancel()
            return

        pos = event.position().toPoint()
        self._commit_text()

        if self._state is _State.PICKING:
            self._drag_origin = pos
            self._state = _State.DRAGGING
            self._sel = QRect(pos, pos)
            self.update()
            return

        if self._state is _State.SELECTED:
            sel = self._sel.normalized()
            edges = self._edges_at(pos)
            if edges and self._tool is _Tool.NONE:
                self._resizing = True
                self._resize_edges = edges
                self._adjust_start = pos
                self._sel_start = QRect(sel)
            elif sel.contains(pos):
                if self._tool is _Tool.NONE:
                    self._moving = True
                    self._adjust_start = pos
                    self._sel_start = QRect(sel)
                elif self._tool is _Tool.TEXT:
                    self._open_text_edit(pos)
                elif self._tool is _Tool.NUMBER:
                    # Auto-increment: the next number follows the count of
                    # balloons already placed, so undo re-uses the number.
                    number = 1 + sum(1 for it in self._items if isinstance(it, NumberItem))
                    radius = 10 + self._pen_width * 2
                    self._items.append(NumberItem(pos, number, self._color, radius))
                    self.update()
                else:
                    self._drawing = True
                    self._draw_start = pos
                    self._freehand = [pos]
            # Clicks outside the selection are ignored (PixPin keeps the
            # selection; use right-click or Esc to discard it).

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        pos = event.position().toPoint()
        self._cursor_pos = event.globalPosition().toPoint()

        if self._state is _State.PICKING:
            self._hover_window = self._window_at(pos)
            self.update()
            return

        if self._state is _State.DRAGGING:
            self._sel = QRect(self._drag_origin, pos)
            self.update()
            return

        # SELECTED
        if self._resizing:
            self._apply_resize(pos)
        elif self._moving:
            delta = pos - self._adjust_start
            moved = self._sel_start.translated(delta)
            moved.moveLeft(max(0, min(moved.left(), self.width() - moved.width())))
            moved.moveTop(max(0, min(moved.top(), self.height() - moved.height())))
            self._sel = moved
            self._reposition_toolbar()
            self.update()
        elif self._drawing:
            self._update_temp_item(pos)
        else:
            self._update_cursor()

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        if event.button() != Qt.MouseButton.LeftButton:
            return
        pos = event.position().toPoint()

        if self._state is _State.DRAGGING:
            sel = QRect(self._drag_origin, pos).normalized()
            if sel.width() <= _MIN_SEL and sel.height() <= _MIN_SEL:
                # Treat as click → select the highlighted window (if any)
                win = self._window_at(pos)
                if win:
                    self._sel = QRect(win)
                    self._enter_selected()
                else:
                    self._reset_to_picking()
            else:
                self._sel = sel
                self._enter_selected()
            return

        if self._state is _State.SELECTED:
            if self._resizing or self._moving:
                self._resizing = False
                self._moving = False
                self._sel = self._sel.normalized()
                self._reposition_toolbar()
            elif self._drawing:
                self._drawing = False
                if self._temp_item is not None:
                    self._items.append(self._temp_item)
                    self._temp_item = None
                self.update()

    def mouseDoubleClickEvent(self, event: QMouseEvent) -> None:
        if (
            event.button() == Qt.MouseButton.LeftButton
            and self._state is _State.SELECTED
            and self._tool is _Tool.NONE
            and self._sel.normalized().contains(event.position().toPoint())
        ):
            self._finish(self._default_action)

    def _enter_selected(self) -> None:
        self._sel = self._sel.normalized().intersected(self.rect())
        self._state = _State.SELECTED
        self._hover_window = None
        self._reposition_toolbar()
        self._update_cursor()
        self.update()

    def _reset_to_picking(self) -> None:
        self._state = _State.PICKING
        self._sel = QRect()
        self._items.clear()
        self._temp_item = None
        self._tool = _Tool.NONE
        for btn in self._tool_buttons.values():
            btn.setChecked(False)
        self._reposition_toolbar()
        self.setCursor(Qt.CursorShape.CrossCursor)
        self.update()

    def _apply_resize(self, pos: QPoint) -> None:
        delta = pos - self._adjust_start
        sel = QRect(self._sel_start)
        e = self._resize_edges
        if e & 1:
            sel.setLeft(min(sel.left() + delta.x(), sel.right() - _MIN_SEL))
        if e & 2:
            sel.setRight(max(sel.right() + delta.x(), sel.left() + _MIN_SEL))
        if e & 4:
            sel.setTop(min(sel.top() + delta.y(), sel.bottom() - _MIN_SEL))
        if e & 8:
            sel.setBottom(max(sel.bottom() + delta.y(), sel.top() + _MIN_SEL))
        self._sel = sel.intersected(self.rect())
        self._reposition_toolbar()
        self.update()

    # ------------------------------------------------------------------
    # Annotation drawing
    # ------------------------------------------------------------------

    def _update_temp_item(self, pos: QPoint) -> None:
        start = self._draw_start
        if self._tool is _Tool.RECT:
            self._temp_item = RectItem(QRect(start, pos).normalized(), self._color, self._pen_width)
        elif self._tool is _Tool.ELLIPSE:
            self._temp_item = EllipseItem(QRect(start, pos).normalized(), self._color, self._pen_width)
        elif self._tool is _Tool.ARROW:
            self._temp_item = ArrowItem(start, pos, self._color, self._pen_width)
        elif self._tool is _Tool.PEN:
            self._freehand.append(pos)
            self._temp_item = FreehandItem(list(self._freehand), self._color, self._pen_width)
        elif self._tool is _Tool.MARKER:
            self._freehand.append(pos)
            marker_color = QColor(self._color)
            marker_color.setAlpha(110)
            self._temp_item = FreehandItem(list(self._freehand), marker_color, self._pen_width * 4)
        self.update()

    def _undo(self) -> None:
        if self._items:
            self._items.pop()
            self.update()

    # ------------------------------------------------------------------
    # Text tool
    # ------------------------------------------------------------------

    def _open_text_edit(self, pos: QPoint) -> None:
        self._commit_text()
        edit = _TextEdit(self)
        edit.setStyleSheet(
            "QLineEdit { background: rgba(255,255,255,235); color: #111;"
            f" border: 2px solid {_ACCENT.name()}; border-radius: 4px; padding: 2px 6px; }}"
        )
        edit.setFont(QFont("Sans", 10 + self._pen_width * 2))
        edit.move(pos)
        edit.setFixedWidth(min(260, self.width() - pos.x() - 8))
        edit.show()
        edit.setFocus()
        edit.returnPressed.connect(self._commit_text)
        edit.cancelled.connect(self._discard_text)
        self._text_edit = edit
        # The line edit needs real keyboard events
        self.releaseKeyboard()

    def _commit_text(self) -> None:
        edit = self._text_edit
        if edit is None:
            return
        self._text_edit = None
        text = edit.text().strip()
        if text:
            font_size = 10 + self._pen_width * 2
            item_pos = edit.pos() + QPoint(4, edit.height() - 8)
            self._items.append(TextItem(item_pos, text, self._color, font_size))
        edit.deleteLater()
        self.grabKeyboard()
        self.update()

    def _discard_text(self) -> None:
        edit = self._text_edit
        if edit is None:
            return
        self._text_edit = None
        edit.deleteLater()
        self.grabKeyboard()

    # ------------------------------------------------------------------
    # Keyboard
    # ------------------------------------------------------------------

    def keyPressEvent(self, event: QKeyEvent) -> None:
        key = event.key()
        mods = event.modifiers()

        if key == Qt.Key.Key_Escape:
            if self._text_edit is not None:
                self._discard_text()
            elif self._tool is not _Tool.NONE:
                self._on_tool_clicked(self._tool, False)
            elif self._state is _State.SELECTED:
                self._reset_to_picking()
            else:
                self._cancel()
        elif key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            self._finish(self._default_action)
        elif key == Qt.Key.Key_F3:
            self._finish("pin")
        elif key == Qt.Key.Key_C and mods & Qt.KeyboardModifier.ControlModifier:
            self._finish("copy")
        elif key == Qt.Key.Key_S and mods & Qt.KeyboardModifier.ControlModifier:
            self._finish("save")
        elif key == Qt.Key.Key_Z and mods & Qt.KeyboardModifier.ControlModifier:
            self._undo()
        elif self._state is _State.SELECTED:
            tool_keys = {
                Qt.Key.Key_R: _Tool.RECT,
                Qt.Key.Key_E: _Tool.ELLIPSE,
                Qt.Key.Key_A: _Tool.ARROW,
                Qt.Key.Key_P: _Tool.PEN,
                Qt.Key.Key_M: _Tool.MARKER,
                Qt.Key.Key_T: _Tool.TEXT,
                Qt.Key.Key_N: _Tool.NUMBER,
            }
            try:
                tool = tool_keys.get(Qt.Key(key))
            except ValueError:
                tool = None
            if tool is not None:
                self._on_tool_clicked(tool, self._tool is not tool)
            else:
                super().keyPressEvent(event)
        else:
            super().keyPressEvent(event)
