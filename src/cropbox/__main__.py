# SPDX-License-Identifier: BSD-3-Clause

import argparse
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from cropbox.models.crop_rect import CropRect
from cropbox.models.trim_range import TrimRange


LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True)
class InitialPosition:
    time_seconds: Optional[float] = None
    frame: Optional[int] = None


def _parse_time_value(value: str) -> float:
    text = value.strip()
    if not text:
        raise ValueError("time value cannot be empty")

    if ":" not in text:
        return max(0.0, float(text))

    parts = text.split(":")
    if len(parts) > 3:
        raise ValueError("time value must be in SS, MM:SS, or HH:MM:SS form")

    seconds = float(parts[-1])
    minutes = int(parts[-2]) if len(parts) >= 2 else 0
    hours = int(parts[-3]) if len(parts) == 3 else 0
    return max(0.0, seconds + (minutes * 60) + (hours * 3600))


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="cropbox")
    parser.add_argument("media", nargs="?", help="Optional media path to open on launch")
    parser.add_argument(
        "-o",
        "--out",
        type=Path,
        help="Export directly to MP4, MOV, or GIF without opening the UI",
    )
    parser.add_argument(
        "-f",
        "--force",
        action="store_true",
        help="Overwrite an existing --out file",
    )
    parser.add_argument(
        "--trim-in",
        dest="trim_in",
        help="Initial trim-in time in seconds or HH:MM:SS.mmm format",
    )
    parser.add_argument(
        "--trim-out",
        dest="trim_out",
        help="Initial trim-out time in seconds or HH:MM:SS.mmm format",
    )
    parser.add_argument(
        "--crop",
        nargs=4,
        metavar=("X", "Y", "WIDTH", "HEIGHT"),
        type=int,
        help="Initial crop rectangle in source pixels",
    )
    position_group = parser.add_mutually_exclusive_group()
    position_group.add_argument(
        "--current-time",
        dest="current_time",
        help="Initial current time in seconds or HH:MM:SS.mmm format",
    )
    position_group.add_argument(
        "--current-frame",
        dest="current_frame",
        type=int,
        help="Initial current frame number",
    )
    return parser


def _build_initial_trim(
    args: argparse.Namespace, parser: argparse.ArgumentParser
) -> Optional[TrimRange]:
    if args.trim_in is None and args.trim_out is None:
        return None

    try:
        trim_in = _parse_time_value(args.trim_in) if args.trim_in is not None else 0.0
        trim_out = _parse_time_value(args.trim_out) if args.trim_out is not None else trim_in
    except ValueError as exc:
        parser.error(str(exc))
        return None

    return TrimRange(start=trim_in, end=trim_out)


def _build_initial_crop(
    args: argparse.Namespace, parser: argparse.ArgumentParser
) -> Optional[CropRect]:
    if args.crop is None:
        return None

    x, y, width, height = args.crop
    if width <= 0 or height <= 0:
        parser.error("crop width and height must be positive integers")
        return None
    if x < 0 or y < 0:
        parser.error("crop x and y must be zero or greater")
        return None
    return CropRect(x=x, y=y, width=width, height=height)


def _build_initial_position(
    args: argparse.Namespace, parser: argparse.ArgumentParser
) -> Optional[InitialPosition]:
    if args.current_time is None and args.current_frame is None:
        return None

    if args.current_time is not None:
        try:
            return InitialPosition(time_seconds=_parse_time_value(args.current_time))
        except ValueError as exc:
            parser.error(str(exc))
            return None

    if args.current_frame < 0:
        parser.error("current frame must be zero or greater")
        return None
    return InitialPosition(frame=args.current_frame)


def main() -> int:
    parser = _build_parser()
    args = parser.parse_args()
    if args.media is None and (
        args.out is not None
        or args.trim_in is not None
        or args.trim_out is not None
        or args.crop
        or args.current_time is not None
        or args.current_frame is not None
    ):
        parser.error(
            "media path is required when using --out, --trim-in, --trim-out, --crop, "
            "--current-time, or --current-frame"
        )
    if args.force and args.out is None:
        parser.error("--force can only be used with --out")

    initial_trim = _build_initial_trim(args, parser)
    initial_crop = _build_initial_crop(args, parser)
    initial_position = _build_initial_position(args, parser)
    if args.out is not None:
        if initial_position is not None:
            parser.error("--current-time and --current-frame are only supported for UI launch")
        from cropbox.logging_utils import configure_logging
        from cropbox.media.headless import HeadlessExportError, export_media

        configure_logging()
        trim_start = initial_trim.start if initial_trim is not None else 0.0
        trim_end = _parse_time_value(args.trim_out) if args.trim_out is not None else None
        try:
            return export_media(
                input_path=Path(args.media),
                output_path=args.out,
                trim_start=trim_start,
                trim_end=trim_end,
                crop=initial_crop,
                force=args.force,
            )
        except HeadlessExportError as exc:
            LOGGER.error("%s", exc)
            return 1

    from cropbox.app import main as run_app

    return run_app(
        initial_media=args.media,
        initial_trim=initial_trim,
        initial_crop=initial_crop,
        initial_position=initial_position,
    )


if __name__ == "__main__":
    raise SystemExit(main())
