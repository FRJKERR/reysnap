"""ReySnap – on-screen ruler / measurement tool.

:class:`RulerTool` is a fullscreen overlay.  Click and drag to
measure a distance in pixels.  The ruler displays width, height,
and diagonal length in real time.
"""

from __future__ import annotations

import math
import logging

from PySide6.QtCore import QPoint, QRect, Qt, Signal
from PySide6.QtGui import (
    QBrush,
    QColor,
    QCursor,
    QFont,
    QGuiApplication,
    QPainter,
    QPen,
    QPixmap,
)
from PySide6.QtWidgets import QWidget

from ..i18n import tr

logger = logging.getLogger(__name__)


class RulerTool(QWidget):
    """Fullscreen ruler overlay.

    The user clicks a start point and drags to an end point.
    A ruler line is drawn with dimension annotations.

    Signals
    -------
    measurement_taken(int, int, float)
        Emitted with ``(dx, dy, distance)`` in pixels.
    """

    measurement_taken = Signal(int, int, float)

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

        self._start: QPoint | None = None
        self._end: QPoint | None = None
        self._measuring = False

        self._bg_pixmap: QPixmap | None = None

    def showEvent(self, event) -> None:
        super().showEvent(event)
        # BypassWindowManagerHint means the WM ignores fullscreen requests
        # and never assigns keyboard focus: set the geometry and grab the
        # keyboard ourselves.
        screen = QGuiApplication.primaryScreen()
        if screen:
            self.setGeometry(screen.geometry())
            self._bg_pixmap = screen.grabWindow(0)
        self.activateWindow()
        self.raise_()
        self.grabKeyboard()

    def closeEvent(self, event) -> None:
        self.releaseKeyboard()
        super().closeEvent(event)

    # ------------------------------------------------------------------
    # Painting
    # ------------------------------------------------------------------

    def paintEvent(self, event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Dim background
        if self._bg_pixmap and not self._bg_pixmap.isNull():
            p.drawPixmap(0, 0, self._bg_pixmap)
            p.fillRect(self.rect(), QColor(0, 0, 0, 100))

        if self._start and self._end:
            self._draw_ruler(p)

        if not self._measuring and not self._start:
            # Hint
            p.setPen(QColor(255, 255, 255, 200))
            font = p.font()
            font.setPointSize(14)
            p.setFont(font)
            p.drawText(
                self.rect(),
                Qt.AlignmentFlag.AlignCenter,
                tr("Haga clic y arrastre para medir · Esc para cancelar"),
            )

        p.end()

    def _draw_ruler(self, p: QPainter) -> None:
        start = self._start
        end = self._end
        dx = end.x() - start.x()
        dy = end.y() - start.y()
        distance = math.sqrt(dx * dx + dy * dy)
        angle = math.degrees(math.atan2(dy, dx))

        # Main line
        pen = QPen(QColor("#0891B2"), 2, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap)
        p.setPen(pen)
        p.drawLine(start, end)

        # Endpoints
        for pt in (start, end):
            p.setPen(QPen(QColor("#0891B2"), 2))
            p.setBrush(QBrush(QColor("#0891B2")))
            p.drawEllipse(pt, 4, 4)

        # Guide lines (dashed, to axes)
        dash_pen = QPen(QColor(255, 255, 255, 80), 1, Qt.PenStyle.DashLine)
        p.setPen(dash_pen)
        p.setBrush(Qt.BrushStyle.NoBrush)
        # Horizontal guide
        p.drawLine(start, QPoint(end.x(), start.y()))
        # Vertical guide
        p.drawLine(QPoint(end.x(), start.y()), end)

        # Dimension labels
        p.setPen(QColor(255, 255, 255))
        font = p.font()
        font.setPointSize(11)
        font.setBold(True)
        p.setFont(font)

        # Width label (horizontal, above the horizontal guide)
        w_label = f"{abs(dx)} px"
        fm = p.fontMetrics()
        w_mid_x = (start.x() + end.x()) // 2
        w_y = start.y() - 12
        p.fillRect(
            w_mid_x - fm.horizontalAdvance(w_label) // 2 - 4,
            w_y - fm.ascent() - 2,
            fm.horizontalAdvance(w_label) + 8,
            fm.height() + 4,
            QColor(0, 0, 0, 180),
        )
        p.drawText(w_mid_x - fm.horizontalAdvance(w_label) // 2, w_y, w_label)

        # Height label (vertical, right of the vertical guide)
        h_label = f"{abs(dy)} px"
        h_x = end.x() + 10
        h_mid_y = (start.y() + end.y()) // 2
        p.save()
        p.translate(h_x, h_mid_y)
        p.rotate(90)
        p.fillRect(
            -fm.horizontalAdvance(h_label) // 2 - 4,
            -fm.ascent() - 2,
            fm.horizontalAdvance(h_label) + 8,
            fm.height() + 4,
            QColor(0, 0, 0, 180),
        )
        p.drawText(-fm.horizontalAdvance(h_label) // 2, 0, h_label)
        p.restore()

        # Diagonal distance label (at midpoint of the line)
        d_label = f"{distance:.1f} px"
        mid_x = (start.x() + end.x()) // 2
        mid_y = (start.y() + end.y()) // 2
        # Offset the label perpendicular to the line
        if distance > 0:
            nx = -dy / distance * 20
            ny = dx / distance * 20
        else:
            nx, ny = 0, -20
        lx = int(mid_x + nx)
        ly = int(mid_y + ny)

        # Background
        p.fillRect(
            lx - fm.horizontalAdvance(d_label) // 2 - 6,
            ly - fm.ascent() - 4,
            fm.horizontalAdvance(d_label) + 12,
            fm.height() + 8,
            QColor("#0891B2"),
        )
        p.setPen(QColor(255, 255, 255))
        p.drawText(lx - fm.horizontalAdvance(d_label) // 2, ly, d_label)

        # Angle
        angle_label = f"{angle:.1f}°"
        p.setPen(QColor(255, 255, 255, 200))
        font.setBold(False)
        font.setPointSize(10)
        p.setFont(font)
        p.drawText(
            lx - p.fontMetrics().horizontalAdvance(angle_label) // 2,
            ly + p.fontMetrics().height() + 2,
            angle_label,
        )

    # ------------------------------------------------------------------
    # Input
    # ------------------------------------------------------------------

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._start = event.position().toPoint()
            self._end = event.position().toPoint()
            self._measuring = True
            self.update()

    def mouseMoveEvent(self, event) -> None:
        if self._measuring and self._start:
            self._end = event.position().toPoint()
            self.update()

    def mouseReleaseEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton and self._measuring:
            self._measuring = False
            if self._start and self._end:
                dx = abs(self._end.x() - self._start.x())
                dy = abs(self._end.y() - self._start.y())
                dist = math.sqrt(dx * dx + dy * dy)
                self.measurement_taken.emit(dx, dy, dist)
            # Keep showing the result until user clicks again or presses Esc
            self.update()

    def keyPressEvent(self, event) -> None:
        if event.key() == Qt.Key.Key_Escape:
            self.close()
        elif event.key() == Qt.Key.Key_Space:
            # Reset for a new measurement
            self._start = None
            self._end = None
            self._measuring = False
            self.update()
        else:
            super().keyPressEvent(event)