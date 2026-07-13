from dataclasses import dataclass


@dataclass
class CropRect:
    x: int
    y: int
    width: int
    height: int
