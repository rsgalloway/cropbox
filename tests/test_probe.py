from pathlib import Path
from subprocess import CompletedProcess

from cropbox.media.probe import probe_media


def test_probe_media_treats_gif_as_timed_media(monkeypatch) -> None:
    def fake_run(command, capture_output, text, check):
        assert command[-1] == "clip.gif"
        assert capture_output is True
        assert text is True
        assert check is True
        return CompletedProcess(
            command,
            0,
            stdout=(
                '{"streams":[{"codec_type":"video","codec_name":"gif","width":320,'
                '"height":180,"avg_frame_rate":"12/1","duration":"2.500"}],'
                '"format":{"format_name":"gif","duration":"2.500"}}'
            ),
        )

    monkeypatch.setattr("cropbox.media.probe.subprocess.run", fake_run)

    info = probe_media(Path("clip.gif"))

    assert info.video_codec == "gif"
    assert info.container == "gif"
    assert info.duration == 2.5
    assert info.frame_rate == 12.0
    assert info.width == 320
    assert info.height == 180
    assert info.is_still_image is False
