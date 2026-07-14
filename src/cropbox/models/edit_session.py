from dataclasses import dataclass, field
from typing import Optional

from cropbox.models.crop_rect import CropRect
from cropbox.models.media_info import MediaInfo
from cropbox.models.trim_range import TrimRange
from cropbox.models.transform import TransformState


@dataclass
class EditSession:
    media: MediaInfo
    crop: Optional[CropRect]
    trim: TrimRange
    transform: TransformState = field(default_factory=TransformState)
