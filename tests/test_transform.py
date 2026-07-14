# SPDX-License-Identifier: BSD-3-Clause

import pytest

from cropbox.models.crop_rect import CropRect
from cropbox.models.transform import TransformState


@pytest.mark.parametrize("rotation", [0, 90, 180, 270])
@pytest.mark.parametrize("flip_horizontal", [False, True])
@pytest.mark.parametrize("flip_vertical", [False, True])
def test_crop_mapping_round_trips(rotation, flip_horizontal, flip_vertical) -> None:
    transform = TransformState(
        rotation=rotation,
        flip_horizontal=flip_horizontal,
        flip_vertical=flip_vertical,
    )
    crop = CropRect(x=100, y=50, width=640, height=360)

    mapped = transform.map_rect(crop, 1920, 1080)

    assert transform.unmap_rect(mapped, 1920, 1080) == crop


def test_rotation_swaps_output_dimensions() -> None:
    transform = TransformState(rotation=90, resize_width=1280, resize_height=720)

    assert transform.output_size(1920, 1080) == (720, 1280)


def test_resize_changes_preview_canvas_aspect() -> None:
    transform = TransformState(resize_width=800, resize_height=800)
    crop = CropRect(x=100, y=50, width=800, height=400)

    assert transform.preview_canvas_size(1600, 900, crop) == (1600.0, 1800.0)
