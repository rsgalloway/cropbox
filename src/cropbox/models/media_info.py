from dataclasses import dataclass
from pathlib import Path
from typing import Optional


@dataclass
class MediaInfo:
    path: Path
    duration: float
    width: int
    height: int
    frame_rate: Optional[float]
    video_codec: Optional[str]
    audio_codec: Optional[str]
    container: Optional[str]
    has_audio: bool
    is_still_image: bool = False
