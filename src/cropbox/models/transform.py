# SPDX-License-Identifier: BSD-3-Clause

from dataclasses import dataclass
from typing import Optional, Tuple

from cropbox.models.crop_rect import CropRect


@dataclass
class TransformState:
    rotation: int = 0
    flip_horizontal: bool = False
    flip_vertical: bool = False
    resize_width: Optional[int] = None
    resize_height: Optional[int] = None

    def normalized_rotation(self) -> int:
        return self.rotation % 360

    def is_identity(self) -> bool:
        return (
            self.normalized_rotation() == 0
            and not self.flip_horizontal
            and not self.flip_vertical
            and self.resize_width is None
            and self.resize_height is None
        )

    def rotated_size(self, width: int, height: int) -> Tuple[int, int]:
        if self.normalized_rotation() in {90, 270}:
            return height, width
        return width, height

    def output_size(self, width: int, height: int) -> Tuple[int, int]:
        resized_width = self.resize_width or width
        resized_height = self.resize_height or height
        return self.rotated_size(resized_width, resized_height)

    def preview_canvas_size(
        self,
        source_width: int,
        source_height: int,
        crop: CropRect,
    ) -> Tuple[float, float]:
        if self.resize_width is None or self.resize_height is None:
            width = float(source_width)
            height = float(source_height)
        else:
            width = source_width * (self.resize_width / float(max(1, crop.width)))
            height = source_height * (self.resize_height / float(max(1, crop.height)))
        if self.normalized_rotation() in {90, 270}:
            return height, width
        return width, height

    def map_rect(self, rect: CropRect, width: int, height: int) -> CropRect:
        rotation = self.normalized_rotation()
        if rotation == 90:
            mapped = CropRect(
                x=height - rect.y - rect.height,
                y=rect.x,
                width=rect.height,
                height=rect.width,
            )
        elif rotation == 180:
            mapped = CropRect(
                x=width - rect.x - rect.width,
                y=height - rect.y - rect.height,
                width=rect.width,
                height=rect.height,
            )
        elif rotation == 270:
            mapped = CropRect(
                x=rect.y,
                y=width - rect.x - rect.width,
                width=rect.height,
                height=rect.width,
            )
        else:
            mapped = CropRect(rect.x, rect.y, rect.width, rect.height)

        mapped_width, mapped_height = self.rotated_size(width, height)
        if self.flip_horizontal:
            mapped.x = mapped_width - mapped.x - mapped.width
        if self.flip_vertical:
            mapped.y = mapped_height - mapped.y - mapped.height
        return mapped

    def unmap_rect(self, rect: CropRect, width: int, height: int) -> CropRect:
        mapped_width, mapped_height = self.rotated_size(width, height)
        x = rect.x
        y = rect.y
        if self.flip_horizontal:
            x = mapped_width - x - rect.width
        if self.flip_vertical:
            y = mapped_height - y - rect.height

        rotation = self.normalized_rotation()
        if rotation == 90:
            return CropRect(
                x=y,
                y=height - x - rect.width,
                width=rect.height,
                height=rect.width,
            )
        if rotation == 180:
            return CropRect(
                x=width - x - rect.width,
                y=height - y - rect.height,
                width=rect.width,
                height=rect.height,
            )
        if rotation == 270:
            return CropRect(
                x=width - y - rect.height,
                y=x,
                width=rect.height,
                height=rect.width,
            )
        return CropRect(x, y, rect.width, rect.height)
