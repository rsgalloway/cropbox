from typing import List, Optional, Tuple

from PySide6.QtCore import QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QColor, QMouseEvent, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QWidget

from cropbox.models.crop_rect import CropRect


class CropOverlay(QWidget):
    cropChanged = Signal(int, int, int, int)

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setMouseTracking(True)

        self._source_width = 0
        self._source_height = 0
        self._crop: Optional[CropRect] = None
        self._drag_mode: Optional[str] = None
        self._last_point = QPointF(0.0, 0.0)
        self._line_width = 2.0
        self._handle_size = 8.0

    def set_source_size(self, width: int, height: int) -> None:
        self._source_width = max(0, width)
        self._source_height = max(0, height)
        if self._source_width > 0 and self._source_height > 0:
            self._crop = CropRect(0, 0, self._source_width, self._source_height)
        else:
            self._crop = None
        self.update()

    def set_crop_rect(self, crop: Optional[CropRect]) -> None:
        self._crop = crop
        self.update()

    def crop_rect(self) -> Optional[CropRect]:
        return self._crop

    def _display_rect(self) -> QRectF:
        if self._source_width <= 0 or self._source_height <= 0:
            return QRectF()

        widget_w = float(max(1, self.width()))
        widget_h = float(max(1, self.height()))
        source_ratio = float(self._source_width) / float(self._source_height)
        view_ratio = widget_w / widget_h

        if source_ratio >= view_ratio:
            width = widget_w
            height = width / source_ratio
            x = 0.0
            y = (widget_h - height) / 2.0
        else:
            height = widget_h
            width = height * source_ratio
            x = (widget_w - width) / 2.0
            y = 0.0
        return QRectF(x, y, width, height)

    def _crop_to_display_rect(self) -> QRectF:
        display = self._display_rect()
        if (
            self._crop is None
            or display.isNull()
            or self._source_width <= 0
            or self._source_height <= 0
        ):
            return QRectF()

        scale_x = display.width() / float(self._source_width)
        scale_y = display.height() / float(self._source_height)
        return QRectF(
            display.left() + (self._crop.x * scale_x),
            display.top() + (self._crop.y * scale_y),
            max(2.0, self._crop.width * scale_x),
            max(2.0, self._crop.height * scale_y),
        )

    def _is_full_frame_crop(self) -> bool:
        if self._crop is None:
            return False
        return (
            self._crop.x == 0
            and self._crop.y == 0
            and self._crop.width == self._source_width
            and self._crop.height == self._source_height
        )

    def _pixel_delta_to_source_delta(self, delta_x: float, delta_y: float) -> Tuple[int, int]:
        display = self._display_rect()
        if display.width() <= 0 or display.height() <= 0:
            return 0, 0

        scale_x = float(self._source_width) / display.width()
        scale_y = float(self._source_height) / display.height()
        return int(round(delta_x * scale_x)), int(round(delta_y * scale_y))

    def paintEvent(self, _event) -> None:
        if self._crop is None:
            return

        crop_display = self._crop_to_display_rect()
        if crop_display.isNull():
            return

        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)

        line_color = QColor("#ffd84d")
        shadow_color = QColor(0, 0, 0, 200)
        dim_color = QColor(0, 0, 0, 110)
        inset = self._line_width / 2.0
        draw_rect = crop_display.adjusted(inset, inset, -inset, -inset)
        if self._is_full_frame_crop():
            draw_rect = draw_rect.adjusted(4.0, 4.0, -4.0, -4.0)
        if draw_rect.width() < 2.0 or draw_rect.height() < 2.0:
            return

        outer_path = QPainterPath()
        outer_path.addRect(QRectF(self.rect()))
        inner_path = QPainterPath()
        inner_path.addRect(draw_rect)
        painter.fillPath(outer_path.subtracted(inner_path), dim_color)

        painter.setPen(QPen(shadow_color, self._line_width + 1.5))
        painter.setBrush(Qt.NoBrush)
        painter.drawRect(draw_rect)

        painter.setPen(QPen(line_color, self._line_width))
        painter.setBrush(Qt.NoBrush)
        painter.drawRect(draw_rect)

        painter.setPen(QPen(QColor(255, 216, 77, 140), 1.0))
        third_width = draw_rect.width() / 3.0
        third_height = draw_rect.height() / 3.0
        for index in (1, 2):
            x = draw_rect.left() + (third_width * index)
            y = draw_rect.top() + (third_height * index)
            painter.drawLine(QPointF(x, draw_rect.top()), QPointF(x, draw_rect.bottom()))
            painter.drawLine(QPointF(draw_rect.left(), y), QPointF(draw_rect.right(), y))

        painter.setBrush(line_color)
        for point in self._handle_points(draw_rect):
            painter.drawRect(
                QRectF(
                    point.x() - (self._handle_size / 2.0),
                    point.y() - (self._handle_size / 2.0),
                    self._handle_size,
                    self._handle_size,
                )
            )

    def _handle_points(self, rect: QRectF) -> List[QPointF]:
        return [
            rect.topLeft(),
            QPointF(rect.center().x(), rect.top()),
            rect.topRight(),
            QPointF(rect.left(), rect.center().y()),
            QPointF(rect.right(), rect.center().y()),
            rect.bottomLeft(),
            QPointF(rect.center().x(), rect.bottom()),
            rect.bottomRight(),
        ]

    def _handle_rects(self, rect: QRectF) -> List[Tuple[str, QRectF]]:
        half_size = self._handle_size / 2.0
        return [
            (
                "top_left",
                QRectF(
                    rect.left() - half_size,
                    rect.top() - half_size,
                    self._handle_size,
                    self._handle_size,
                ),
            ),
            (
                "top",
                QRectF(
                    rect.center().x() - half_size,
                    rect.top() - half_size,
                    self._handle_size,
                    self._handle_size,
                ),
            ),
            (
                "top_right",
                QRectF(
                    rect.right() - half_size,
                    rect.top() - half_size,
                    self._handle_size,
                    self._handle_size,
                ),
            ),
            (
                "left",
                QRectF(
                    rect.left() - half_size,
                    rect.center().y() - half_size,
                    self._handle_size,
                    self._handle_size,
                ),
            ),
            (
                "right",
                QRectF(
                    rect.right() - half_size,
                    rect.center().y() - half_size,
                    self._handle_size,
                    self._handle_size,
                ),
            ),
            (
                "bottom_left",
                QRectF(
                    rect.left() - half_size,
                    rect.bottom() - half_size,
                    self._handle_size,
                    self._handle_size,
                ),
            ),
            (
                "bottom",
                QRectF(
                    rect.center().x() - half_size,
                    rect.bottom() - half_size,
                    self._handle_size,
                    self._handle_size,
                ),
            ),
            (
                "bottom_right",
                QRectF(
                    rect.right() - half_size,
                    rect.bottom() - half_size,
                    self._handle_size,
                    self._handle_size,
                ),
            ),
        ]

    def _edge_hit(self, point: QPointF, rect: QRectF) -> Optional[str]:
        for mode, handle_rect in self._handle_rects(rect):
            if handle_rect.contains(point):
                return mode

        threshold = 10.0

        near_left = (
            abs(point.x() - rect.left()) <= threshold and rect.top() <= point.y() <= rect.bottom()
        )
        near_right = (
            abs(point.x() - rect.right()) <= threshold and rect.top() <= point.y() <= rect.bottom()
        )
        near_top = (
            abs(point.y() - rect.top()) <= threshold and rect.left() <= point.x() <= rect.right()
        )
        near_bottom = (
            abs(point.y() - rect.bottom()) <= threshold and rect.left() <= point.x() <= rect.right()
        )

        if near_left:
            return "left"
        if near_right:
            return "right"
        if near_top:
            return "top"
        if near_bottom:
            return "bottom"
        if rect.contains(point):
            return "move"
        return None

    def _update_cursor(self, point: QPointF) -> None:
        rect = self._crop_to_display_rect()
        mode = self._edge_hit(point, rect)
        if mode in {"top_left", "bottom_right"}:
            self.setCursor(Qt.SizeFDiagCursor)
            return
        if mode in {"top_right", "bottom_left"}:
            self.setCursor(Qt.SizeBDiagCursor)
            return
        if mode in {"left", "right"}:
            self.setCursor(Qt.SizeHorCursor)
            return
        if mode in {"top", "bottom"}:
            self.setCursor(Qt.SizeVerCursor)
            return
        if mode == "move":
            self.setCursor(Qt.SizeAllCursor)
            return
        self.setCursor(Qt.ArrowCursor)

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if self._crop is None:
            return
        if event.button() == Qt.RightButton:
            event.ignore()
            return

        crop_display = self._crop_to_display_rect()
        self._drag_mode = self._edge_hit(event.position(), crop_display)
        self._last_point = event.position()

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if self._crop is None:
            return
        if self._drag_mode is None:
            self._update_cursor(event.position())
            return

        delta = event.position() - self._last_point
        delta_x, delta_y = self._pixel_delta_to_source_delta(delta.x(), delta.y())

        min_size = 2
        max_x = self._source_width
        max_y = self._source_height

        x = self._crop.x
        y = self._crop.y
        width = self._crop.width
        height = self._crop.height

        if self._drag_mode == "move":
            x = max(0, min(x + delta_x, max_x - width))
            y = max(0, min(y + delta_y, max_y - height))
        elif self._drag_mode in {"left", "top_left", "bottom_left"}:
            new_x = max(0, min(x + delta_x, x + width - min_size))
            width = width + (x - new_x)
            x = new_x
        elif self._drag_mode in {"right", "top_right", "bottom_right"}:
            width = max(min_size, min(width + delta_x, max_x - x))
        if self._drag_mode in {"top", "top_left", "top_right"}:
            new_y = max(0, min(y + delta_y, y + height - min_size))
            height = height + (y - new_y)
            y = new_y
        elif self._drag_mode in {"bottom", "bottom_left", "bottom_right"}:
            height = max(min_size, min(height + delta_y, max_y - y))

        self._crop = CropRect(x=x, y=y, width=width, height=height)
        self._last_point = event.position()
        self.cropChanged.emit(self._crop.x, self._crop.y, self._crop.width, self._crop.height)
        self.update()

    def mouseReleaseEvent(self, _event: QMouseEvent) -> None:
        self._drag_mode = None
        self.setCursor(Qt.ArrowCursor)
