# SPDX-License-Identifier: BSD-3-Clause

import pytest

from cropbox import __version__
from cropbox.__main__ import (
    _build_initial_position,
    _build_initial_crop,
    _build_initial_trim,
    InitialPosition,
    _build_parser,
    _parse_time_value,
)


def test_parse_time_value_seconds() -> None:
    assert _parse_time_value("12.5") == 12.5


def test_parse_time_value_hms() -> None:
    assert _parse_time_value("00:01:02.500") == 62.5


def test_build_initial_trim_from_args() -> None:
    parser = _build_parser()
    args = parser.parse_args(["input.mp4", "--trim-in", "1.25", "--trim-out", "00:00:02.500"])
    trim = _build_initial_trim(args, parser)

    assert trim is not None
    assert trim.start == 1.25
    assert trim.end == 2.5


def test_build_initial_crop_from_args() -> None:
    parser = _build_parser()
    args = parser.parse_args(["input.mp4", "--crop", "10", "20", "300", "200"])
    crop = _build_initial_crop(args, parser)

    assert crop is not None
    assert crop.x == 10
    assert crop.y == 20
    assert crop.width == 300
    assert crop.height == 200


def test_parser_accepts_headless_output_options() -> None:
    parser = _build_parser()
    args = parser.parse_args(["input.mp4", "-o", "output.mp4", "--force"])

    assert str(args.out) == "output.mp4"
    assert args.force is True


def test_build_initial_position_from_time_args() -> None:
    parser = _build_parser()
    args = parser.parse_args(["input.mp4", "--current-time", "00:00:02.500"])
    position = _build_initial_position(args, parser)

    assert position == InitialPosition(time_seconds=2.5)


def test_build_initial_position_from_frame_args() -> None:
    parser = _build_parser()
    args = parser.parse_args(["input.mp4", "--current-frame", "42"])
    position = _build_initial_position(args, parser)

    assert position == InitialPosition(frame=42)


def test_parser_version_flag_prints_version(capsys) -> None:
    parser = _build_parser()

    with pytest.raises(SystemExit) as exc_info:
        parser.parse_args(["--version"])

    assert exc_info.value.code == 0
    captured = capsys.readouterr()
    assert captured.out.strip() == f"cropbox {__version__}"
