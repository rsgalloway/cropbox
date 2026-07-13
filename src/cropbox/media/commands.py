from pathlib import Path
from typing import List, Optional, Tuple

from cropbox.models.crop_rect import CropRect


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
    output_size: Optional[Tuple[int, int]],
    colors: int,
) -> str:
    video_chain = "[0:v]"
    if crop is not None:
        video_chain += _build_crop_filter(crop)
        video_chain += ","
    if output_size is not None:
        video_chain += _build_scale_filter(output_size)
        video_chain += ","
    video_chain += f"split[v0][v1];[v0]palettegen=max_colors={colors}[p];" "[v1][p]paletteuse[vout]"
    return video_chain


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
) -> List[str]:
    suffix = output_path.suffix.lower()
    command: List[str] = [
        "ffmpeg",
        "-hide_banner",
        "-y",
        "-ss",
        f"{trim_start:.3f}",
        "-to",
        f"{trim_end:.3f}",
        "-i",
        str(input_path),
    ]

    if suffix == ".gif":
        gif_filter = _build_gif_filter(crop, output_size, gif_colors)
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

    filters = []
    if crop is not None:
        filters.append(_build_crop_filter(crop))
    if output_size is not None:
        filters.append(_build_scale_filter(output_size))
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
