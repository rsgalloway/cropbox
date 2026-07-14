# SPDX-License-Identifier: BSD-3-Clause

from pathlib import Path
from subprocess import CompletedProcess

import pytest

from cropbox.media.headless import HeadlessExportError, export_media
from cropbox.models.crop_rect import CropRect
from cropbox.models.media_info import MediaInfo


def _media_info(path: Path) -> MediaInfo:
    return MediaInfo(
        path=path,
        duration=10.0,
        width=1920,
        height=1080,
        frame_rate=24.0,
        video_codec="h264",
        audio_codec="aac",
        container="mov,mp4",
        has_audio=True,
        is_still_image=False,
    )


def test_export_media_runs_ffmpeg_without_qt(tmp_path: Path, monkeypatch) -> None:
    input_path = tmp_path / "input.mp4"
    input_path.touch()
    output_path = tmp_path / "output.mp4"
    captured = {}

    monkeypatch.setattr("cropbox.media.headless.missing_media_tools", lambda: [])
    monkeypatch.setattr("cropbox.media.headless.probe_media", _media_info)

    def fake_run(command):
        captured["command"] = command
        return CompletedProcess(command, 0)

    monkeypatch.setattr("cropbox.media.headless.subprocess.run", fake_run)

    result = export_media(
        input_path=input_path,
        output_path=output_path,
        trim_start=2.0,
        trim_end=None,
        crop=CropRect(x=10, y=20, width=640, height=360),
    )

    assert result == 0
    command = captured["command"]
    assert command[command.index("-to") + 1] == "10.000"
    assert "crop=640:360:10:20" in command


def test_export_media_refuses_existing_output_without_force(tmp_path: Path) -> None:
    input_path = tmp_path / "input.mp4"
    output_path = tmp_path / "output.mp4"
    input_path.touch()
    output_path.touch()

    with pytest.raises(HeadlessExportError, match="--force"):
        export_media(input_path, output_path, 0.0, None, None)


def test_export_media_rejects_crop_outside_source(tmp_path: Path, monkeypatch) -> None:
    input_path = tmp_path / "input.mp4"
    input_path.touch()
    monkeypatch.setattr("cropbox.media.headless.missing_media_tools", lambda: [])
    monkeypatch.setattr("cropbox.media.headless.probe_media", _media_info)

    with pytest.raises(HeadlessExportError, match="source dimensions"):
        export_media(
            input_path,
            tmp_path / "output.mp4",
            0.0,
            None,
            CropRect(x=1800, y=0, width=640, height=360),
        )


def test_export_media_returns_ffmpeg_failure_status(tmp_path: Path, monkeypatch) -> None:
    input_path = tmp_path / "input.mp4"
    input_path.touch()
    monkeypatch.setattr("cropbox.media.headless.missing_media_tools", lambda: [])
    monkeypatch.setattr("cropbox.media.headless.probe_media", _media_info)
    monkeypatch.setattr(
        "cropbox.media.headless.subprocess.run",
        lambda command: CompletedProcess(command, 7),
    )

    assert export_media(input_path, tmp_path / "output.gif", 0.0, 5.0, None) == 7


def test_export_media_allows_png_output(tmp_path: Path, monkeypatch) -> None:
    input_path = tmp_path / "input.mp4"
    input_path.touch()
    output_path = tmp_path / "frames.%08d.png"
    captured = {}

    monkeypatch.setattr("cropbox.media.headless.missing_media_tools", lambda: [])
    monkeypatch.setattr("cropbox.media.headless.probe_media", _media_info)

    def fake_run(command):
        captured["command"] = command
        return CompletedProcess(command, 0)

    monkeypatch.setattr("cropbox.media.headless.subprocess.run", fake_run)

    result = export_media(input_path, output_path, 0.0, 1.0, None)

    assert result == 0
    assert captured["command"][-1] == str(output_path)


def test_export_media_rejects_trim_for_still_images(tmp_path: Path, monkeypatch) -> None:
    input_path = tmp_path / "input.png"
    input_path.touch()

    monkeypatch.setattr("cropbox.media.headless.missing_media_tools", lambda: [])
    monkeypatch.setattr(
        "cropbox.media.headless.probe_media",
        lambda path: MediaInfo(
            path=path,
            duration=0.0,
            width=1920,
            height=1080,
            frame_rate=None,
            video_codec="png",
            audio_codec=None,
            container="png",
            has_audio=False,
            is_still_image=True,
        ),
    )

    with pytest.raises(HeadlessExportError, match="still images"):
        export_media(input_path, tmp_path / "output.png", 1.0, None, None)
