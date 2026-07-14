# SPDX-License-Identifier: BSD-3-Clause

from cropbox.widgets.resize_dialog import ResizeDialog


def test_fit_resize_preserves_aspect_ratio() -> None:
    assert ResizeDialog._fit_size((1920, 1080), (854, 480)) == (852, 480)


def test_fit_resize_handles_portrait_source() -> None:
    assert ResizeDialog._fit_size((1080, 1920), (1280, 720)) == (404, 720)
