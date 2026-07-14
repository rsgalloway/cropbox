# SPDX-License-Identifier: BSD-3-Clause

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtCore import QPoint
from PySide6.QtGui import QColor, QImage, QPainter
from PySide6.QtWidgets import QApplication

from cropbox.widgets.player_widget import PlayerWidget


@pytest.fixture(scope="module")
def application():
    app = QApplication.instance() or QApplication([])
    yield app


def _quadrant_frame() -> QImage:
    frame = QImage(100, 100, QImage.Format_RGB32)
    painter = QPainter(frame)
    painter.fillRect(0, 0, 50, 50, QColor("#ff0000"))
    painter.fillRect(50, 0, 50, 50, QColor("#00ff00"))
    painter.fillRect(0, 50, 50, 50, QColor("#0000ff"))
    painter.fillRect(50, 50, 50, 50, QColor("#ffff00"))
    painter.end()
    return frame


def _render(widget: PlayerWidget) -> QImage:
    output = QImage(widget.size(), QImage.Format_RGB32)
    output.fill(QColor("#000000"))
    painter = QPainter(output)
    widget.render(painter, QPoint())
    painter.end()
    return output


def test_rotate_right_preview_is_clockwise(application) -> None:
    widget = PlayerWidget()
    widget.setMinimumHeight(0)
    widget.resize(200, 200)
    widget.set_frame(_quadrant_frame())
    widget.set_transform(90, False, False, 1.0)

    output = _render(widget)

    assert output.pixelColor(50, 50) == QColor("#0000ff")
    assert output.pixelColor(150, 50) == QColor("#ff0000")
    assert output.pixelColor(50, 150) == QColor("#ffff00")
    assert output.pixelColor(150, 150) == QColor("#00ff00")


def test_horizontal_flip_preview(application) -> None:
    widget = PlayerWidget()
    widget.setMinimumHeight(0)
    widget.resize(200, 200)
    widget.set_frame(_quadrant_frame())
    widget.set_transform(0, True, False, 1.0)

    output = _render(widget)

    assert output.pixelColor(50, 50) == QColor("#00ff00")
    assert output.pixelColor(150, 50) == QColor("#ff0000")
