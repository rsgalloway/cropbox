from pathlib import Path

from cropbox.media.commands import build_export_command
from cropbox.models.crop_rect import CropRect
from cropbox.models.transform import TransformState


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


def test_build_export_command_with_playback_rate_adds_video_and_audio_filters() -> None:
    command = build_export_command(
        input_path=Path("input.mp4"),
        output_path=Path("output.mp4"),
        trim_start=1.5,
        trim_end=4.25,
        crop=None,
        playback_rate=3.0,
        has_audio=True,
    )

    assert "-vf" in command
    assert "setpts=PTS/3.000" in command
    assert "-filter:a" in command
    assert "atempo=2.0,atempo=1.500" in command


def test_build_export_command_gif_disables_audio() -> None:
    command = build_export_command(
        input_path=Path("input.mp4"),
        output_path=Path("output.gif"),
        trim_start=0.0,
        trim_end=2.0,
        crop=None,
    )

    assert "-filter_complex" in command
    assert (
        "[0:v]split[v0][v1];[v0]palettegen=max_colors=256[p];" "[v1][p]paletteuse[vout]" in command
    )
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
        "[0:v]crop=200:100:10:20,split[v0][v1];"
        "[v0]palettegen=max_colors=256[p];[v1][p]paletteuse[vout]" in command
    )


def test_build_export_command_gif_with_playback_rate_uses_setpts() -> None:
    command = build_export_command(
        input_path=Path("input.mp4"),
        output_path=Path("output.gif"),
        trim_start=0.0,
        trim_end=2.0,
        crop=None,
        playback_rate=0.5,
    )

    assert "-filter_complex" in command
    assert (
        "[0:v]setpts=PTS/0.500,split[v0][v1];"
        "[v0]palettegen=max_colors=256[p];[v1][p]paletteuse[vout]" in command
    )


def test_build_export_command_adds_scale_quality_and_disables_audio() -> None:
    command = build_export_command(
        input_path=Path("input.mp4"),
        output_path=Path("output.mp4"),
        trim_start=0.0,
        trim_end=2.0,
        crop=CropRect(x=10, y=20, width=1920, height=1080),
        has_audio=False,
        output_size=(1280, 720),
        crf=18,
    )

    assert "crop=1920:1080:10:20,scale=1280:720:flags=lanczos,setsar=1" in command
    assert command[command.index("-crf") + 1] == "18"
    assert "-an" in command
    assert "-c:a" not in command


def test_build_export_command_gif_adds_scale_and_palette_colors() -> None:
    command = build_export_command(
        input_path=Path("input.mp4"),
        output_path=Path("output.gif"),
        trim_start=0.0,
        trim_end=2.0,
        crop=None,
        output_size=(640, 360),
        gif_colors=64,
    )

    assert (
        "[0:v]scale=640:360:flags=lanczos,setsar=1,split[v0][v1];"
        "[v0]palettegen=max_colors=64[p];[v1][p]paletteuse[vout]" in command
    )


def test_build_export_command_adds_edit_transforms_in_pipeline_order() -> None:
    command = build_export_command(
        input_path=Path("input.mp4"),
        output_path=Path("output.mp4"),
        trim_start=0.0,
        trim_end=2.0,
        crop=CropRect(x=10, y=20, width=800, height=600),
        transform=TransformState(
            rotation=90,
            flip_horizontal=True,
            resize_width=640,
            resize_height=480,
        ),
        output_size=(320, 240),
    )

    assert (
        "crop=800:600:10:20,scale=640:480:flags=lanczos,"
        "transpose=clock,hflip,scale=320:240:flags=lanczos,setsar=1" in command
    )


def test_build_gif_export_adds_rotation_and_flip_before_palette() -> None:
    command = build_export_command(
        input_path=Path("input.mp4"),
        output_path=Path("output.gif"),
        trim_start=0.0,
        trim_end=2.0,
        crop=None,
        transform=TransformState(rotation=270, flip_vertical=True),
    )

    assert (
        "[0:v]transpose=cclock,vflip,split[v0][v1];"
        "[v0]palettegen=max_colors=256[p];[v1][p]paletteuse[vout]" in command
    )


def test_build_export_command_png_sequence_disables_audio_and_sets_start_number() -> None:
    command = build_export_command(
        input_path=Path("input.mp4"),
        output_path=Path("frames.%08d.png"),
        trim_start=0.0,
        trim_end=2.0,
        crop=None,
        has_audio=True,
    )

    assert "-an" in command
    assert "-start_number" in command
    assert command[-1] == "frames.%08d.png"


def test_build_export_command_png_still_writes_single_frame() -> None:
    command = build_export_command(
        input_path=Path("input.png"),
        output_path=Path("output.png"),
        trim_start=0.0,
        trim_end=0.0,
        crop=CropRect(x=10, y=20, width=200, height=100),
        source_is_still_image=True,
    )

    assert "-ss" not in command
    assert "-frames:v" in command
    assert "crop=200:100:10:20" in command
    assert command[-1] == "output.png"
