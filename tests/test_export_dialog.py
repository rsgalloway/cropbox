from cropbox.widgets.export_dialog import ExportDialog


def test_fit_size_preserves_landscape_aspect_ratio() -> None:
    assert ExportDialog._fit_size((1920, 1080), (1280, 720)) == (1280, 720)


def test_fit_size_preserves_portrait_aspect_ratio() -> None:
    assert ExportDialog._fit_size((1080, 1920), (1920, 1080)) == (608, 1080)


def test_fit_size_produces_even_dimensions() -> None:
    width, height = ExportDialog._fit_size((1001, 777), (854, 480))
    assert width % 2 == 0
    assert height % 2 == 0
    assert width <= 854
    assert height <= 480
