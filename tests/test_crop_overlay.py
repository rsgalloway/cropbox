# SPDX-License-Identifier: BSD-3-Clause

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtWidgets import QApplication

from cropbox.models.crop_rect import CropRect
from cropbox.widgets.crop_overlay import CropOverlay


@pytest.fixture(scope="module")
def application():
    app = QApplication.instance() or QApplication([])
    yield app


def _overlay() -> CropOverlay:
    overlay = CropOverlay()
    overlay.set_source_size(1920, 1080)
    return overlay


def test_corner_resize_preserves_aspect_ratio(application) -> None:
    overlay = _overlay()
    crop = CropRect(x=200, y=100, width=800, height=400)

    resized = overlay._resize_with_aspect_ratio(crop, "bottom_right", 200, 20, 2.0)

    assert resized == CropRect(x=200, y=100, width=1000, height=500)


def test_left_edge_resize_preserves_ratio_around_vertical_center(application) -> None:
    overlay = _overlay()
    crop = CropRect(x=400, y=300, width=800, height=400)

    resized = overlay._resize_with_aspect_ratio(crop, "left", -200, 0, 2.0)

    assert resized == CropRect(x=200, y=250, width=1000, height=500)


def test_bottom_edge_resize_keeps_top_edge_anchored(application) -> None:
    overlay = _overlay()
    crop = CropRect(x=400, y=300, width=800, height=400)

    resized = overlay._resize_with_aspect_ratio(crop, "bottom", 0, 100, 2.0)

    assert resized == CropRect(x=300, y=300, width=1000, height=500)


def test_aspect_resize_stays_inside_source_bounds(application) -> None:
    overlay = _overlay()
    crop = CropRect(x=200, y=100, width=800, height=400)

    resized = overlay._resize_with_aspect_ratio(crop, "top_left", -1000, -1000, 2.0)

    assert resized.x >= 0
    assert resized.y >= 0
    assert resized.x + resized.width <= 1920
    assert resized.y + resized.height <= 1080
    assert resized.width / resized.height == 2.0
