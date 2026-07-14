from pathlib import Path
from typing import List, Optional, Tuple

from cropbox.models.crop_rect import CropRect
from cropbox.models.transform import TransformState


def _build_crop_filter(crop: CropRect) -> str:
    return "crop={w}:{h}:{x}:{y}".format(
        w=crop.width,
        h=crop.height,
        x=crop.x,
        y=crop.y,
    )


def _build_scale_filter(output_size: Tuple[int, int]) -> str:
    return f"scale={output_size[0]}:{output_size[1]}:flags=lanczos"


def _build_gif_filter(
    crop: Optional[CropRect],
    transform: Optional[TransformState],
    output_size: Optional[Tuple[int, int]],
    colors: int,
) -> str:
    video_chain = "[0:v]"
    filters = _build_video_filters(crop, transform, output_size)
    if filters:
        video_chain += ",".join(filters)
        video_chain += ","
    video_chain += f"split[v0][v1];[v0]palettegen=max_colors={colors}[p];" "[v1][p]paletteuse[vout]"
    return video_chain


def _build_transform_filters(transform: Optional[TransformState]) -> List[str]:
    if transform is None:
        return []

    filters: List[str] = []
    if transform.resize_width is not None and transform.resize_height is not None:
        filters.append(_build_scale_filter((transform.resize_width, transform.resize_height)))

    rotation = transform.normalized_rotation()
    if rotation == 90:
        filters.append("transpose=clock")
    elif rotation == 180:
        filters.extend(["hflip", "vflip"])
    elif rotation == 270:
        filters.append("transpose=cclock")

    if transform.flip_horizontal:
        filters.append("hflip")
    if transform.flip_vertical:
        filters.append("vflip")
    return filters


def _build_video_filters(
    crop: Optional[CropRect],
    transform: Optional[TransformState],
    output_size: Optional[Tuple[int, int]],
) -> List[str]:
    filters: List[str] = []
    if crop is not None:
        filters.append(_build_crop_filter(crop))
    filters.extend(_build_transform_filters(transform))
    if output_size is not None:
        filters.append(_build_scale_filter(output_size))
    has_edit_resize = bool(
        transform and transform.resize_width is not None and transform.resize_height is not None
    )
    if has_edit_resize or output_size is not None:
        filters.append("setsar=1")
    return filters


def _build_atempo_filters(playback_rate: float) -> List[str]:
    rate = playback_rate
    filters: List[str] = []

    while rate > 2.0:
        filters.append("atempo=2.0")
        rate /= 2.0

    while rate < 0.5:
        filters.append("atempo=0.5")
        rate /= 0.5

    filters.append(f"atempo={rate:.3f}")
    return filters


def build_export_command(
    input_path: Path,
    output_path: Path,
    trim_start: float,
    trim_end: float,
    crop: Optional[CropRect],
    playback_rate: float = 1.0,
    has_audio: bool = True,
    output_size: Optional[Tuple[int, int]] = None,
    crf: int = 23,
    gif_colors: int = 256,
    transform: Optional[TransformState] = None,
    source_is_still_image: bool = False,
) -> List[str]:
    suffix = output_path.suffix.lower()
    command: List[str] = ["ffmpeg", "-hide_banner", "-y"]
    if not source_is_still_image:
        command.extend(
            [
                "-ss",
                f"{trim_start:.3f}",
                "-to",
                f"{trim_end:.3f}",
            ]
        )
    command.extend(["-i", str(input_path)])

    if suffix == ".gif":
        gif_filter = _build_gif_filter(crop, transform, output_size, gif_colors)
        if playback_rate != 1.0:
            gif_filter = gif_filter.replace("[0:v]", f"[0:v]setpts=PTS/{playback_rate:.3f},", 1)
        command.extend(
            [
                "-filter_complex",
                gif_filter,
                "-map",
                "[vout]",
                "-an",
                "-loop",
                "0",
                str(output_path),
            ]
        )
        return command

    if suffix == ".png":
        filters = _build_video_filters(crop, transform, output_size)
        if filters:
            command.extend(["-vf", ",".join(filters)])
        command.append("-an")
        if source_is_still_image:
            command.extend(["-frames:v", "1"])
        else:
            command.extend(["-start_number", "1"])
        command.append(str(output_path))
        return command

    filters = _build_video_filters(crop, transform, output_size)
    if playback_rate != 1.0:
        filters.append(f"setpts=PTS/{playback_rate:.3f}")

    if filters:
        command.extend(["-vf", ",".join(filters)])

    if has_audio and playback_rate != 1.0:
        command.extend(["-filter:a", ",".join(_build_atempo_filters(playback_rate))])

    command.extend(["-c:v", "libx264", "-crf", str(crf), "-pix_fmt", "yuv420p"])
    if not has_audio:
        command.append("-an")
    if suffix in {".mp4", ".mov"}:
        if has_audio:
            command.extend(["-c:a", "aac"])
        command.extend(["-movflags", "+faststart"])
    else:
        if has_audio:
            command.extend(["-c:a", "aac"])

    command.append(str(output_path))
    return command
