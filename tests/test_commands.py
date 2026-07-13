from pathlib import Path

from cropbox.media.commands import build_export_command
from cropbox.models.crop_rect import CropRect


def test_build_export_command_with_crop_mp4() -> None:
    command = build_export_command(
        input_path=Path("input.mp4"),
        output_path=Path("output.mp4"),
        trim_start=1.5,
        trim_end=4.25,
        crop=CropRect(x=10, y=20, width=200, height=100),
    )

    assert command[0] == "ffmpeg"
    assert command[1] == "-hide_banner"
    assert "-vf" in command
    assert "crop=200:100:10:20" in command
    assert "-c:v" in command
    assert "libx264" in command


def test_build_export_command_gif_disables_audio() -> None:
    command = build_export_command(
        input_path=Path("input.mp4"),
        output_path=Path("output.gif"),
        trim_start=0.0,
        trim_end=2.0,
        crop=None,
    )

    assert "-filter_complex" in command
    assert "[0:v]split[v0][v1];[v0]palettegen[p];[v1][p]paletteuse[vout]" in command
    assert "-map" in command
    assert "[vout]" in command
    assert "-an" in command
    assert "-loop" in command
    assert command[-1] == "output.gif"


def test_build_export_command_gif_with_crop_uses_filter_complex_crop() -> None:
    command = build_export_command(
        input_path=Path("input.mp4"),
        output_path=Path("output.gif"),
        trim_start=0.0,
        trim_end=2.0,
        crop=CropRect(x=10, y=20, width=200, height=100),
    )

    assert "-filter_complex" in command
    assert (
        "[0:v]crop=200:100:10:20,split[v0][v1];[v0]palettegen[p];[v1][p]paletteuse[vout]"
        in command
    )
