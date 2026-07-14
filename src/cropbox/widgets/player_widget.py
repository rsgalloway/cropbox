from typing import Optional

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QImage, QPaintEvent, QPainter
from PySide6.QtWidgets import QWidget


class PlayerWidget(QWidget):
    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._frame = QImage()
        self._rotation = 0
        self._flip_horizontal = False
        self._flip_vertical = False
        self._canvas_aspect_ratio: Optional[float] = None
        self.setMinimumHeight(360)

    def set_frame(self, frame: QImage) -> None:
        self._frame = frame
        self.update()

    def clear(self) -> None:
        self._frame = QImage()
        self.update()

    def set_transform(
        self,
        rotation: int,
        flip_horizontal: bool,
        flip_vertical: bool,
        canvas_aspect_ratio: Optional[float],
    ) -> None:
        self._rotation = rotation % 360
        self._flip_horizontal = flip_horizontal
        self._flip_vertical = flip_vertical
        self._canvas_aspect_ratio = canvas_aspect_ratio
        self.update()

    def paintEvent(self, _event: QPaintEvent) -> None:
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor("#000000"))

        if self._frame.isNull():
            return

        image_ratio = self._frame.width() / float(max(1, self._frame.height()))
        canvas_ratio = self._canvas_aspect_ratio or (
            1.0 / image_ratio if self._rotation in {90, 270} else image_ratio
        )
        widget_ratio = self.width() / float(max(1, self.height()))
        if canvas_ratio >= widget_ratio:
            target_width = float(self.width())
            target_height = target_width / canvas_ratio
        else:
            target_height = float(self.height())
            target_width = target_height * canvas_ratio
        target = QRectF(
            (self.width() - target_width) / 2.0,
            (self.height() - target_height) / 2.0,
            target_width,
            target_height,
        )

        pre_width = target.height() if self._rotation in {90, 270} else target.width()
        pre_height = target.width() if self._rotation in {90, 270} else target.height()

        painter.setRenderHint(QPainter.SmoothPixmapTransform, True)
        painter.setClipRect(target)
        painter.translate(target.center())
        painter.scale(
            -1.0 if self._flip_horizontal else 1.0,
            -1.0 if self._flip_vertical else 1.0,
        )
        painter.rotate(self._rotation)
        painter.scale(
            pre_width / float(max(1, self._frame.width())),
            pre_height / float(max(1, self._frame.height())),
        )
        painter.translate(-self._frame.width() / 2.0, -self._frame.height() / 2.0)
        painter.drawImage(0, 0, self._frame)
