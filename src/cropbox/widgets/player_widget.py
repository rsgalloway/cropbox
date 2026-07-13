from typing import Optional

from PySide6.QtCore import QRect, Qt
from PySide6.QtGui import QColor, QImage, QPaintEvent, QPainter
from PySide6.QtWidgets import QWidget


class PlayerWidget(QWidget):
    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._frame = QImage()
        self.setMinimumHeight(360)

    def set_frame(self, frame: QImage) -> None:
        self._frame = frame
        self.update()

    def clear(self) -> None:
        self._frame = QImage()
        self.update()

    def paintEvent(self, _event: QPaintEvent) -> None:
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor("#000000"))

        if self._frame.isNull():
            return

        scaled = self._frame.scaled(self.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation)
        x = (self.width() - scaled.width()) // 2
        y = (self.height() - scaled.height()) // 2
        painter.drawImage(QRect(x, y, scaled.width(), scaled.height()), scaled)
