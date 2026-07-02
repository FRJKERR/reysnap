"""PinSnap – image annotation editor.

:class:`AnnotationEditor` is a QMainWindow that lets the user draw
arrows, rectangles, ellipses, freehand, text, and highlights on a
screenshot.  It provides a toolbar and emits ``save_requested`` and
``pin_requested`` signals.
"""

from __future__ import annotations

import logging
import math
from enum import Enum, auto
from typing import List, Optional

from PySide6.QtCore import (
    QLineF,
    QPoint,
    QRect,
    QRectF,
    QSize,
    Qt,
    Signal,
)
from PySide6.QtGui import (
    QAction,
    QActionGroup,
    QBrush,
    QColor,
    QFont,
    QFontMetrics,
    QGuiApplication,
    QImage,
    QKeySequence,
    QPainter,
    QPen,
    QPixmap,
)
from PySide6.QtWidgets import (
    QColorDialog,
    QComboBox,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QScrollArea,
    QSpinBox,
    QToolBar,
    QVBoxLayout,
    QWidget,
)

from ..config import AppConfig

logger = logging.getLogger(__name__)


# ------------------------------------------------------------------
# Tool enumeration
# ------------------------------------------------------------------

class Tool(Enum):
    SELECT = auto()
    ARROW = auto()
    RECT = auto()
    ELLIPSE = auto()
    LINE = auto()
    FREEHAND = auto()
    TEXT = auto()
    HIGHLIGHT = auto()
    BLUR = auto()
    CROP = auto()


# ------------------------------------------------------------------
# Annotation item – stores a single drawn element
# ------------------------------------------------------------------

class AnnotationItem:
    """Base class for a single annotation element."""

    def __init__(self, tool: Tool, color: QColor, pen_width: int = 2):
        self.tool = tool
        self.color = color
        self.pen_width = pen_width

    def paint(self, painter: QPainter) -> None:
        raise NotImplementedError


class ArrowItem(AnnotationItem):
    def __init__(self, start: QPoint, end: QPoint, color: QColor, width: int = 2):
        super().__init__(Tool.ARROW, color, width)
        self.start = start
        self.end = end

    def paint(self, painter: QPainter) -> None:
        pen = QPen(self.color, self.pen_width, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap)
        painter.setPen(pen)
        painter.drawLine(self.start, self.end)
        # Arrowhead
        self._draw_arrowhead(painter)

    def _draw_arrowhead(self, painter: QPainter) -> None:
        line = QLineF(self.start, self.end)
        if line.length() < 1:
            return
        angle = line.angle()
        arrow_size = max(10, self.pen_width * 4)
        tip = line.p2()
        from PySide6.QtCore import QPointF
        from PySide6.QtGui import QPolygonF
        # Two wing points at ±25° from the shaft, arrow_size pixels back from the tip
        wing1 = QPointF(
            tip.x() - arrow_size * math.cos(math.radians(angle - 25)),
            tip.y() + arrow_size * math.sin(math.radians(angle - 25)),
        )
        wing2 = QPointF(
            tip.x() - arrow_size * math.cos(math.radians(angle + 25)),
            tip.y() + arrow_size * math.sin(math.radians(angle + 25)),
        )
        polygon = QPolygonF([tip, wing1, wing2])
        painter.setBrush(QBrush(self.color))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawPolygon(polygon)


class RectItem(AnnotationItem):
    def __init__(self, rect: QRect, color: QColor, width: int = 2, fill: bool = False):
        super().__init__(Tool.RECT, color, width)
        self.rect = rect
        self.fill = fill

    def paint(self, painter: QPainter) -> None:
        pen = QPen(self.color, self.pen_width)
        painter.setPen(pen)
        if self.fill:
            fill_color = QColor(self.color)
            fill_color.setAlpha(40)
            painter.setBrush(QBrush(fill_color))
        else:
            painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRect(self.rect)


class EllipseItem(AnnotationItem):
    def __init__(self, rect: QRect, color: QColor, width: int = 2, fill: bool = False):
        super().__init__(Tool.ELLIPSE, color, width)
        self.rect = rect
        self.fill = fill

    def paint(self, painter: QPainter) -> None:
        pen = QPen(self.color, self.pen_width)
        painter.setPen(pen)
        if self.fill:
            fill_color = QColor(self.color)
            fill_color.setAlpha(40)
            painter.setBrush(QBrush(fill_color))
        else:
            painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawEllipse(self.rect)


class LineItem(AnnotationItem):
    def __init__(self, start: QPoint, end: QPoint, color: QColor, width: int = 2):
        super().__init__(Tool.LINE, color, width)
        self.start = start
        self.end = end

    def paint(self, painter: QPainter) -> None:
        pen = QPen(self.color, self.pen_width, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap)
        painter.setPen(pen)
        painter.drawLine(self.start, self.end)


class FreehandItem(AnnotationItem):
    def __init__(self, points: List[QPoint], color: QColor, width: int = 2):
        super().__init__(Tool.FREEHAND, color, width)
        self.points = points

    def paint(self, painter: QPainter) -> None:
        if len(self.points) < 2:
            return
        pen = QPen(self.color, self.pen_width, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin)
        painter.setPen(pen)
        from PySide6.QtGui import QPolygonF
        painter.drawPolyline(QPolygonF([p.toPointF() for p in self.points]))


class TextItem(AnnotationItem):
    def __init__(self, pos: QPoint, text: str, color: QColor, font_size: int = 16):
        super().__init__(Tool.TEXT, color)
        self.pos = pos
        self.text = text
        self.font_size = font_size

    def paint(self, painter: QPainter) -> None:
        font = QFont("Sans", self.font_size)
        font.setBold(True)
        painter.setFont(font)
        painter.setPen(QPen(self.color))
        fm = QFontMetrics(font)
        bg_rect = QRectF(self.pos, QSize(fm.horizontalAdvance(self.text), fm.height()))
        painter.fillRect(bg_rect.adjusted(-4, -2, 4, 2), QColor(255, 255, 255, 200))
        painter.drawText(self.pos, self.text)


class NumberItem(AnnotationItem):
    """Numbered balloon (red circle with a white number) for tutorials."""

    def __init__(self, pos: QPoint, number: int, color: QColor = QColor("#E81123"), radius: int = 14):
        super().__init__(Tool.SELECT, color)
        self.pos = pos
        self.number = number
        self.radius = radius

    def paint(self, painter: QPainter) -> None:
        r = self.radius
        # Soft drop shadow so the balloon reads on any background
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(0, 0, 0, 70))
        painter.drawEllipse(self.pos + QPoint(1, 2), r, r)
        # Balloon
        painter.setBrush(QBrush(self.color))
        painter.setPen(QPen(QColor(255, 255, 255, 230), 2))
        painter.drawEllipse(self.pos, r, r)
        # Number
        font = QFont("Sans", max(8, int(r * 0.9)))
        font.setBold(True)
        painter.setFont(font)
        painter.setPen(QPen(QColor(255, 255, 255)))
        text_rect = QRectF(
            self.pos.x() - r, self.pos.y() - r, r * 2, r * 2
        )
        painter.drawText(text_rect, Qt.AlignmentFlag.AlignCenter, str(self.number))


class HighlightItem(AnnotationItem):
    def __init__(self, rect: QRect, color: QColor = QColor("#FFFF00")):
        super().__init__(Tool.HIGHLIGHT, color)
        self.rect = rect

    def paint(self, painter: QPainter) -> None:
        c = QColor(self.color)
        c.setAlpha(80)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(c))
        painter.drawRect(self.rect)


# ------------------------------------------------------------------
# Canvas widget – the drawing surface
# ------------------------------------------------------------------

class AnnotationCanvas(QWidget):
    """Widget that draws the base image and all annotation items on top."""

    def __init__(self, pixmap: QPixmap, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._base_pixmap = pixmap
        self._items: List[AnnotationItem] = []
        # Temp item being drawn right now
        self._temp_item: Optional[AnnotationItem] = None
        self.setMinimumSize(pixmap.size())
        self.setMouseTracking(True)

    @property
    def items(self) -> List[AnnotationItem]:
        return list(self._items)

    def add_item(self, item: AnnotationItem) -> None:
        self._items.append(item)
        self.update()

    def undo(self) -> None:
        if self._items:
            self._items.pop()
            self.update()

    def clear_all(self) -> None:
        self._items.clear()
        self.update()

    def set_temp_item(self, item: Optional[AnnotationItem]) -> None:
        self._temp_item = item
        self.update()

    def render_final(self) -> QPixmap:
        """Return a QPixmap with the base image and all annotations composited."""
        result = QPixmap(self._base_pixmap.size())
        result.fill(Qt.GlobalColor.transparent)
        p = QPainter(result)
        p.drawPixmap(0, 0, self._base_pixmap)
        for item in self._items:
            item.paint(p)
        p.end()
        return result

    def paintEvent(self, event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.drawPixmap(0, 0, self._base_pixmap)
        for item in self._items:
            item.paint(p)
        if self._temp_item:
            self._temp_item.paint(p)
        p.end()

    def sizeHint(self) -> QSize:
        return self._base_pixmap.size()


# ------------------------------------------------------------------
# Text input dialog (inline)
# ------------------------------------------------------------------

class _TextInputDialog(QWidget):
    """Small floating text-input that commits on Enter."""

    text_committed = Signal(str)

    def __init__(self, pos: QPoint, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.move(pos)
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._edit = _SingleLineEdit(self)
        self._edit.setFont(QFont("Sans", 16))
        self._edit.setFixedSize(300, 36)
        self._edit.returnPressed.connect(self._commit)
        self._edit.escapePressed.connect(self._cancel)
        self._layout.addWidget(self._edit)
        self.show()
        self._edit.setFocus()

    def _commit(self) -> None:
        text = self._edit.text().strip()
        if text:
            self.text_committed.emit(text)
        self.close()

    def _cancel(self) -> None:
        self.close()


class _SingleLineEdit(QWidget):
    """Single-line text editor that supports Escape."""

    escapePressed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        from PySide6.QtWidgets import QLineEdit
        layout = QHBoxLayout(self)
        layout.setContentsMargins(2, 2, 2, 2)
        self._line = QLineEdit()
        self._line.setFrame(False)
        self._line.setStyleSheet(
            "QLineEdit { background: white; border: 2px solid #0891B2; border-radius: 4px; padding: 2px 6px; }"
        )
        layout.addWidget(self._line)
        self._line.returnPressed.connect(self.returnPressed.emit)
        self.setFocusProxy(self._line)

    def text(self) -> str:
        return self._line.text()

    def setFont(self, font):
        self._line.setFont(font)

    def setFixedSize(self, w, h):
        super().setFixedSize(w, h)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape:
            self.escapePressed.emit()
            event.accept()
        else:
            super().keyPressEvent(event)


# ------------------------------------------------------------------
# Main editor window
# ------------------------------------------------------------------

class AnnotationEditor(QMainWindow):
    """Full-featured image annotation editor.

    Signals
    -------
    save_requested(QPixmap, str | None)
        Emitted when the user clicks Save.  Carries the composited
        pixmap and an optional path.
    pin_requested(QPixmap)
        Emitted when the user clicks Pin.
    """

    save_requested = Signal(QPixmap, object)  # QPixmap, str|None
    pin_requested = Signal(QPixmap)

    def __init__(self, pixmap: QPixmap, config: AppConfig, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._config = config
        self._current_tool = Tool.ARROW
        self._color = QColor("#FF0000")
        self._pen_width = 3
        self._font_size = 16
        self._drawing = False
        self._start_pos = QPoint()
        self._freehand_points: List[QPoint] = []
        self._text_dialog: Optional[_TextInputDialog] = None

        # Canvas
        self._canvas = AnnotationCanvas(pixmap)
        scroll_area = _ScrollArea()
        scroll_area.setWidget(self._canvas)
        self.setCentralWidget(scroll_area)

        self._build_toolbar()

        # Mouse tracking on canvas
        self._canvas.setMouseTracking(True)
        self._canvas.mousePressEvent = self._on_mouse_press
        self._canvas.mouseMoveEvent = self._on_mouse_move
        self._canvas.mouseReleaseEvent = self._on_mouse_release
        self._canvas.keyPressEvent = self._on_key

        self.setWindowTitle("PinSnap – Anotación")
        self.resize(min(pixmap.width() + 80, 1400), min(pixmap.height() + 120, 900))
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

    # ------------------------------------------------------------------
    # Toolbar
    # ------------------------------------------------------------------

    def _build_toolbar(self) -> None:
        tb = QToolBar("Herramientas")
        tb.setMovable(False)
        self.addToolBar(tb)

        # Tool group
        ag = QActionGroup(self)
        ag.setExclusive(True)

        tools = [
            ("A", Tool.SELECT, "Seleccionar (V)"),
            ("→", Tool.ARROW, "Flecha (A)"),
            ("□", Tool.RECT, "Rectángulo (R)"),
            ("○", Tool.ELLIPSE, "Elipse (O)"),
            ("╱", Tool.LINE, "Línea (L)"),
            ("✎", Tool.FREEHAND, "Lápiz (P)"),
            ("T", Tool.TEXT, "Texto (T)"),
            ("▮", Tool.HIGHLIGHT, "Resaltador (H)"),
        ]
        shortcuts_map = {
            Tool.SELECT: "V", Tool.ARROW: "A", Tool.RECT: "R",
            Tool.ELLIPSE: "O", Tool.LINE: "L", Tool.FREEHAND: "P",
            Tool.TEXT: "T", Tool.HIGHLIGHT: "H",
        }
        for label, tool, tooltip in tools:
            act = QAction(label, self)
            act.setCheckable(True)
            act.setToolTip(tooltip)
            act.setShortcut(QKeySequence(shortcuts_map[tool]))
            act.setData(tool)
            act.triggered.connect(lambda checked, t=tool: self._set_tool(t))
            ag.addAction(act)
            tb.addAction(act)
            if tool == Tool.ARROW:
                act.setChecked(True)

        tb.addSeparator()

        # Colour picker
        self._color_btn = QAction("🎨", self)
        self._color_btn.setToolTip("Color")
        self._color_btn.triggered.connect(self._pick_color)
        tb.addAction(self._color_btn)

        # Pen width
        tb.addWidget(QLabel("  Ancho: "))
        self._width_spin = QSpinBox()
        self._width_spin.setRange(1, 30)
        self._width_spin.setValue(self._pen_width)
        self._width_spin.setFixedWidth(50)
        self._width_spin.valueChanged.connect(lambda v: setattr(self, "_pen_width", v))
        tb.addWidget(self._width_spin)

        # Font size (for text tool)
        tb.addWidget(QLabel("  Fuente: "))
        self._font_spin = QSpinBox()
        self._font_spin.setRange(8, 120)
        self._font_spin.setValue(self._font_size)
        self._font_spin.setFixedWidth(50)
        self._font_spin.valueChanged.connect(lambda v: setattr(self, "_font_size", v))
        tb.addWidget(self._font_spin)

        tb.addSeparator()

        # Undo
        act_undo = QAction("↩ Deshacer", self)
        act_undo.setShortcut(QKeySequence.StandardKey.Undo)
        act_undo.triggered.connect(self._canvas.undo)
        tb.addAction(act_undo)

        # Clear all
        act_clear = QAction("🗑 Borrar todo", self)
        act_clear.triggered.connect(self._canvas.clear_all)
        tb.addAction(act_clear)

        tb.addSeparator()

        # Save
        act_save = QAction("💾 Guardar", self)
        act_save.setShortcut(QKeySequence.StandardKey.Save)
        act_save.triggered.connect(self._on_save)
        tb.addAction(act_save)

        # Pin
        act_pin = QAction("📌 Anclar", self)
        act_pin.triggered.connect(self._on_pin)
        tb.addAction(act_pin)

        # Close
        act_close = QAction("✖ Cerrar", self)
        act_close.setShortcut(QKeySequence.StandardKey.Close)
        act_close.triggered.connect(self.close)
        tb.addAction(act_close)

    # ------------------------------------------------------------------
    # Tool / colour helpers
    # ------------------------------------------------------------------

    def _set_tool(self, tool: Tool) -> None:
        self._current_tool = tool

    def _pick_color(self) -> None:
        color = QColorDialog.getColor(self._color, self, "Seleccionar color")
        if color.isValid():
            self._color = color

    # ------------------------------------------------------------------
    # Mouse events (routed from canvas)
    # ------------------------------------------------------------------

    def _on_mouse_press(self, event) -> None:
        if event.button() != Qt.MouseButton.LeftButton:
            return
        pos = event.position().toPoint()

        if self._current_tool == Tool.TEXT:
            self._show_text_input(pos)
            return

        self._drawing = True
        self._start_pos = pos
        self._freehand_points = [pos]

    def _on_mouse_move(self, event) -> None:
        if not self._drawing:
            return
        pos = event.position().toPoint()
        temp = self._make_item(self._start_pos, pos)
        self._canvas.set_temp_item(temp)

        if self._current_tool == Tool.FREEHAND:
            self._freehand_points.append(pos)

    def _on_mouse_release(self, event) -> None:
        if not self._drawing:
            return
        self._drawing = False
        pos = event.position().toPoint()
        item = self._make_item(self._start_pos, pos)
        self._canvas.set_temp_item(None)
        if item:
            self._canvas.add_item(item)

    def _on_key(self, event) -> None:
        if event.key() == Qt.Key.Key_Escape:
            self._canvas.set_temp_item(None)
            self._drawing = False

    # ------------------------------------------------------------------
    # Item factory
    # ------------------------------------------------------------------

    def _make_item(self, start: QPoint, end: QPoint) -> Optional[AnnotationItem]:
        rect = QRect(start, end).normalized()
        tool = self._current_tool

        if tool == Tool.ARROW:
            if (start - end).manhattanLength() < 3:
                return None
            return ArrowItem(start, end, self._color, self._pen_width)
        elif tool == Tool.RECT:
            if not rect.isValid() or rect.width() < 3:
                return None
            return RectItem(rect, self._color, self._pen_width, fill=False)
        elif tool == Tool.ELLIPSE:
            if not rect.isValid() or rect.width() < 3:
                return None
            return EllipseItem(rect, self._color, self._pen_width, fill=False)
        elif tool == Tool.LINE:
            if (start - end).manhattanLength() < 3:
                return None
            return LineItem(start, end, self._color, self._pen_width)
        elif tool == Tool.FREEHAND:
            pts = list(self._freehand_points)
            if len(pts) < 2:
                return None
            return FreehandItem(pts, self._color, self._pen_width)
        elif tool == Tool.HIGHLIGHT:
            if not rect.isValid():
                return None
            return HighlightItem(rect, self._color)
        return None

    # ------------------------------------------------------------------
    # Text input
    # ------------------------------------------------------------------

    def _show_text_input(self, pos: QPoint) -> None:
        global_pos = self._canvas.mapToGlobal(pos)
        self._text_dialog = _TextInputDialog(global_pos)
        self._text_dialog.text_committed.connect(lambda text: self._commit_text(pos, text))

    def _commit_text(self, pos: QPoint, text: str) -> None:
        item = TextItem(pos, text, self._color, self._font_size)
        self._canvas.add_item(item)

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------

    def _on_save(self) -> None:
        pixmap = self._canvas.render_final()
        self.save_requested.emit(pixmap, None)
        self.close()

    def _on_pin(self) -> None:
        pixmap = self._canvas.render_final()
        self.pin_requested.emit(pixmap)
        self.close()


class _ScrollArea(QScrollArea):
    """Minimal scroll area around the annotation canvas."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWidgetResizable(False)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)