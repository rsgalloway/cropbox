import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtCore import QPoint, Qt
from PySide6.QtGui import QColor, QImage
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from cropbox.widgets.timeline import TimelineWidget


@pytest.fixture(scope="module")
def application():
    app = QApplication.instance() or QApplication([])
    yield app


def test_view_range_changes_mapping_without_changing_trim(application) -> None:
    timeline = TimelineWidget()
    timeline.resize(1000, 44)
    timeline.set_duration(100_000)
    timeline.set_trim_range(20_000, 40_000)
    timeline.set_position(30_000)

    assert timeline.set_view_range(10_000, 50_000)
    assert timeline.view_range() == (10_000, 50_000)
    assert timeline.trim_range() == (20_000, 40_000)
    assert timeline.position() == 30_000
    assert timeline._ms_from_x(timeline._track_rect().left()) == 10_000
    assert timeline._ms_from_x(timeline._track_rect().right()) == 50_000


def test_view_range_can_exclude_trim(application) -> None:
    timeline = TimelineWidget()
    timeline.set_duration(100_000)
    timeline.set_trim_range(20_000, 40_000)

    assert timeline.set_view_range(30_000, 50_000)
    assert timeline.set_view_range(10_000, 30_000)
    assert timeline.view_range() == (10_000, 30_000)


def test_expanding_trim_expands_view(application) -> None:
    timeline = TimelineWidget()
    timeline.set_duration(100_000)
    timeline.set_trim_range(30_000, 70_000)
    assert timeline.set_view_range(20_000, 80_000)

    timeline.set_trim_range(10_000, 90_000)
    assert timeline.trim_range() == (10_000, 90_000)
    assert timeline.view_range() == (10_000, 90_000)


def test_view_range_rejects_invalid_values_and_resets(application) -> None:
    timeline = TimelineWidget()
    timeline.set_duration(100_000)
    timeline.set_trim_range(20_000, 40_000)
    assert timeline.set_view_range(20_000, 40_000)

    assert not timeline.set_view_range(40_000, 20_000)
    assert not timeline.set_view_range(-1, 40_000)
    assert not timeline.set_view_range(20_000, 100_001)
    assert timeline.view_range() == (20_000, 40_000)

    timeline.reset_view_range()
    assert timeline.view_range() == (0, 100_000)
    assert timeline.trim_range() == (20_000, 40_000)


def test_view_handle_commits_only_on_mouse_release(application) -> None:
    timeline = TimelineWidget()
    timeline.resize(1000, 44)
    timeline.set_duration(100_000)
    timeline.set_trim_range(20_000, 80_000)
    timeline.show()
    application.processEvents()

    view_events = []
    timeline.viewChanged.connect(lambda start, end: view_events.append((start, end)))
    track = timeline._track_rect()
    start = QPoint(int(track.left()), int(track.bottom()))
    target = QPoint(int(track.left() + (track.width() * 0.1)), int(track.bottom()))

    QTest.mousePress(timeline, Qt.LeftButton, Qt.NoModifier, start)
    QTest.mouseMove(timeline, target)
    application.processEvents()

    assert timeline.view_range() == (0, 100_000)
    assert view_events == []

    QTest.mouseRelease(timeline, Qt.LeftButton, Qt.NoModifier, target)
    application.processEvents()

    assert 9_500 <= timeline.view_range()[0] <= 10_500
    assert timeline.view_range()[1] == 100_000
    assert len(view_events) == 1
    timeline.close()


def test_right_view_handle_has_larger_target_and_keyboard_nudging(application) -> None:
    timeline = TimelineWidget()
    timeline.resize(1000, 44)
    timeline.set_duration(100_000)
    timeline.set_trim_range(20_000, 80_000)
    timeline.show()
    application.processEvents()

    track = timeline._track_rect()
    near_right_handle = QPoint(int(track.right() - 10), int(track.center().y()))
    QTest.mouseClick(timeline, Qt.LeftButton, Qt.NoModifier, near_right_handle)

    assert timeline.selected_target() == "view_end"
    assert timeline.nudge_selected_view_handle(-1_000)
    assert timeline.view_range() == (0, 99_000)
    assert timeline.nudge_selected_view_handle(1_000)
    assert timeline.view_range() == (0, 100_000)
    timeline.close()


def test_thumbnail_request_geometry_scales_with_widget_size(application) -> None:
    timeline = TimelineWidget()
    timeline.resize(1000, 44)

    thumb_width, thumb_height, count = timeline.thumbnail_request_geometry()

    assert thumb_width >= 12
    assert thumb_height >= 8
    assert count >= 1


def test_thumbnail_updates_ignore_stale_jobs(application) -> None:
    timeline = TimelineWidget()
    timeline.resize(1000, 44)
    timeline.set_duration(100_000)
    timeline.set_trim_range(0, 100_000)
    timeline.set_thumbnail_request(2, 0, 100_000, [25_000, 75_000])

    frame = QImage(32, 18, QImage.Format_RGB32)
    frame.fill(QColor("#ffffff"))
    timeline.set_thumbnail(1, 0, 25_000, frame)

    assert timeline._thumbnails[0] is None


def test_zoom_view_keeps_anchor_and_respects_trim(application) -> None:
    timeline = TimelineWidget()
    timeline.set_duration(100_000)
    timeline.set_trim_range(20_000, 80_000)

    assert timeline.zoom_view(50_000, zoom_in=True)
    start_ms, end_ms = timeline.view_range()

    assert 20_000 < start_ms < 50_000
    assert 50_000 < end_ms < 80_000
    assert (end_ms - start_ms) < 100_000

    previous_range = timeline.view_range()
    assert timeline.zoom_view(50_000, zoom_in=False)
    assert timeline.view_range()[0] <= previous_range[0]
    assert timeline.view_range()[1] >= previous_range[1]


def test_expanding_trim_still_expands_view_when_needed(application) -> None:
    timeline = TimelineWidget()
    timeline.set_duration(100_000)
    timeline.set_trim_range(20_000, 40_000)
    assert timeline.set_view_range(25_000, 35_000)

    timeline.set_trim_range(10_000, 90_000)

    assert timeline.view_range() == (10_000, 90_000)


def test_zoom_view_updates_trim_when_trim_matches_view(application) -> None:
    timeline = TimelineWidget()
    timeline.set_duration(100_000)
    timeline.set_trim_range(0, 100_000)
    timeline.set_position(50_000)

    assert timeline.zoom_view(50_000, zoom_in=True)

    assert timeline.trim_range() == timeline.view_range()
    assert timeline.trim_range()[0] > 0
    assert timeline.trim_range()[1] < 100_000
