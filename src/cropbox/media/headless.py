# SPDX-License-Identifier: BSD-3-Clause

import logging
import subprocess
from pathlib import Path
from typing import Optional

from cropbox.media.commands import build_export_command
from cropbox.media.dependencies import missing_media_tools
from cropbox.media.probe import ProbeError, probe_media
from cropbox.models.crop_rect import CropRect


LOGGER = logging.getLogger(__name__)
SUPPORTED_OUTPUT_SUFFIXES = {".gif", ".mov", ".mp4", ".png"}


class HeadlessExportError(RuntimeError):
    pass


def export_media(
    input_path: Path,
    output_path: Path,
    trim_start: float,
    trim_end: Optional[float],
    crop: Optional[CropRect],
    force: bool = False,
) -> int:
    input_path = input_path.expanduser()
    output_path = output_path.expanduser()

    if not input_path.is_file():
        raise HeadlessExportError(f"Input media does not exist: {input_path}")
    if input_path.resolve() == output_path.resolve():
        raise HeadlessExportError("Input and output paths must be different")
    if output_path.suffix.lower() not in SUPPORTED_OUTPUT_SUFFIXES:
        supported = ", ".join(sorted(SUPPORTED_OUTPUT_SUFFIXES))
        raise HeadlessExportError(f"Output must use one of these extensions: {supported}")
    if not output_path.parent.is_dir():
        raise HeadlessExportError(f"Output directory does not exist: {output_path.parent}")
    if output_path.exists() and not force:
        raise HeadlessExportError(
            f"Output already exists: {output_path} (use --force to overwrite)"
        )

    missing = missing_media_tools()
    if missing:
        raise HeadlessExportError("Required media tools were not found: " + ", ".join(missing))

    try:
        media_info = probe_media(input_path)
    except ProbeError as exc:
        raise HeadlessExportError(f"Could not inspect input media: {exc}") from exc

    if media_info.is_still_image:
        resolved_end = 0.0
        if trim_start > 0.0 or (trim_end is not None and trim_end > 0.0):
            raise HeadlessExportError("Trim settings are not supported for still images")
    else:
        resolved_end = media_info.duration if trim_end is None else trim_end
        if resolved_end <= trim_start:
            raise HeadlessExportError("Trim-out must be greater than trim-in")
        if trim_start >= media_info.duration:
            raise HeadlessExportError("Trim-in must be before the end of the media")
        if resolved_end > media_info.duration:
            raise HeadlessExportError(
                f"Trim-out exceeds media duration ({media_info.duration:.3f} seconds)"
            )

    if crop is not None and (
        crop.x + crop.width > media_info.width or crop.y + crop.height > media_info.height
    ):
        raise HeadlessExportError(
            f"Crop rectangle exceeds source dimensions " f"({media_info.width}x{media_info.height})"
        )

    command = build_export_command(
        input_path=input_path,
        output_path=output_path,
        trim_start=trim_start,
        trim_end=resolved_end,
        crop=crop,
        has_audio=media_info.has_audio,
        source_is_still_image=media_info.is_still_image,
    )
    LOGGER.info("Starting headless export: %s", " ".join(command))
    try:
        result = subprocess.run(command)
    except OSError as exc:
        raise HeadlessExportError(f"Could not start ffmpeg: {exc}") from exc

    if result.returncode != 0:
        LOGGER.error("ffmpeg exited with status %d", result.returncode)
    else:
        LOGGER.info("Export finished: %s", output_path)
    return result.returncode
