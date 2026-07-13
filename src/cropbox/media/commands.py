from pathlib import Path
from typing import List, Optional

from cropbox.models.crop_rect import CropRect


def _build_crop_filter(crop: CropRect) -> str:
    return "crop={w}:{h}:{x}:{y}".format(
        w=crop.width,
        h=crop.height,
        x=crop.x,
        y=crop.y,
    )


def _build_gif_filter(crop: Optional[CropRect]) -> str:
    video_chain = "[0:v]"
    if crop is not None:
        video_chain += _build_crop_filter(crop)
        video_chain += ","
    video_chain += "split[v0][v1];[v0]palettegen[p];[v1][p]paletteuse[vout]"
    return video_chain


def build_export_command(
    input_path: Path,
    output_path: Path,
    trim_start: float,
    trim_end: float,
    crop: Optional[CropRect],
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
        command.extend(
            [
                "-filter_complex",
                _build_gif_filter(crop),
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

    if filters:
        command.extend(["-vf", ",".join(filters)])

    command.extend(["-c:v", "libx264", "-pix_fmt", "yuv420p"])
    if suffix in {".mp4", ".mov"}:
        command.extend(["-c:a", "aac", "-movflags", "+faststart"])
    else:
        command.extend(["-c:a", "aac"])

    command.append(str(output_path))
    return command
