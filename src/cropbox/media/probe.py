import json
import subprocess
from pathlib import Path
from typing import Any, Dict, Optional

from cropbox.models.media_info import MediaInfo


class ProbeError(RuntimeError):
    pass


def _parse_frame_rate(value: Optional[str]) -> Optional[float]:
    if not value or value == "0/0":
        return None
    if "/" in value:
        numerator_str, denominator_str = value.split("/", 1)
        denominator = float(denominator_str)
        if denominator == 0:
            return None
        return float(numerator_str) / denominator
    return float(value)


def _probe_still_image(path: Path) -> Optional[MediaInfo]:
    from PySide6.QtGui import QImageReader

    reader = QImageReader(str(path))
    if not reader.canRead():
        return None
    size = reader.size()
    image_format = bytes(reader.format()).decode("ascii", errors="ignore").lower() or None
    return MediaInfo(
        path=path,
        duration=0.0,
        width=max(size.width(), 0),
        height=max(size.height(), 0),
        frame_rate=None,
        video_codec=image_format,
        audio_codec=None,
        container=image_format,
        has_audio=False,
        is_still_image=True,
    )


def probe_media(path: Path) -> MediaInfo:
    image_info = _probe_still_image(path)
    if image_info is not None:
        return image_info

    cmd = [
        "ffprobe",
        "-v",
        "error",
        "-show_streams",
        "-show_format",
        "-print_format",
        "json",
        str(path),
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
    except FileNotFoundError as exc:
        raise ProbeError("ffprobe not found. Please install ffmpeg/ffprobe.") from exc
    except subprocess.CalledProcessError as exc:
        message = (exc.stderr or exc.stdout or "Unknown ffprobe error").strip()
        raise ProbeError(message) from exc

    data: Dict[str, Any] = json.loads(result.stdout)
    streams = data.get("streams", [])
    fmt = data.get("format", {})

    video_stream = next((stream for stream in streams if stream.get("codec_type") == "video"), None)
    audio_stream = next((stream for stream in streams if stream.get("codec_type") == "audio"), None)

    if video_stream is None:
        raise ProbeError("No video stream found in file.")

    duration = float(fmt.get("duration") or video_stream.get("duration") or 0.0)
    frame_rate = _parse_frame_rate(
        video_stream.get("avg_frame_rate") or video_stream.get("r_frame_rate")
    )
    width = int(video_stream.get("width") or 0)
    height = int(video_stream.get("height") or 0)
    container = fmt.get("format_name")

    return MediaInfo(
        path=path,
        duration=duration,
        width=width,
        height=height,
        frame_rate=frame_rate,
        video_codec=video_stream.get("codec_name"),
        audio_codec=audio_stream.get("codec_name") if audio_stream else None,
        container=container,
        has_audio=audio_stream is not None,
        is_still_image=False,
    )
