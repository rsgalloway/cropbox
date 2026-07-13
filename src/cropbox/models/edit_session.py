from dataclasses import dataclass
from typing import Optional

from cropbox.models.crop_rect import CropRect
from cropbox.models.media_info import MediaInfo
from cropbox.models.trim_range import TrimRange


@dataclass
class EditSession:
    media: MediaInfo
    crop: Optional[CropRect]
    trim: TrimRange
