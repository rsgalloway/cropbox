from typing import List, Optional, Tuple

from PySide6.QtCore import QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QColor, QImage, QMouseEvent, QPainter, QPen, QWheelEvent
from PySide6.QtWidgets import QWidget


class TimelineWidget(QWidget):
    seekRequested = Signal(int)
    trimChanged = Signal(int, int)
    viewChanged = Signal(int, int)
    thumbnailGeometryChanged = Signal()

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setMinimumHeight(44)
        self.setFocusPolicy(Qt.StrongFocus)

        self._duration_ms = 0
        self._view_start_ms = 0
        self._view_end_ms = 0
        self._fps: Optional[float] = None
        self._annotations_visible = True
        self._show_frame_values = False
        self._position_ms = 0
        self._trim_in_ms = 0
        self._trim_out_ms = 0
        self._drag_mode: Optional[str] = None
        self._selected_target: Optional[str] = None
        self._view_drag_origin_x = 0.0
        self._view_drag_initial_range = (0, 0)
        self._pending_view_range: Optional[Tuple[int, int]] = None
        self._thumbnail_job_id = 0
        self._thumbnail_range = (0, 0)
        self._thumbnail_positions: List[int] = []
        self._thumbnails: List[Optional[QImage]] = []

    def set_frame_rate(self, fps: Optional[float]) -> None:
        self._fps = fps if fps and fps > 0 else None
        self.update()

    def set_annotations_visible(self, visible: bool) -> None:
        self._annotations_visible = visible
        self.update()

    def set_show_frame_values(self, show_frames: bool) -> None:
        self._show_frame_values = show_frames
        self.update()

    def set_duration(self, duration_ms: int) -> None:
        previous_duration = self._duration_ms
        was_full_view = self._view_start_ms == 0 and self._view_end_ms in {
            0,
            previous_duration,
        }
        duration = max(0, duration_ms)
        self._duration_ms = duration
        if was_full_view:
            self._view_start_ms = 0
            self._view_end_ms = duration
        else:
            self._view_start_ms = max(0, min(self._view_start_ms, duration))
            self._view_end_ms = max(self._view_start_ms, min(self._view_end_ms, duration))
        self._trim_in_ms = max(0, min(self._trim_in_ms, duration))
        self._trim_out_ms = max(self._trim_in_ms, min(self._trim_out_ms or duration, duration))
        self._position_ms = max(self._trim_in_ms, min(self._position_ms, self._trim_out_ms))
        self._ensure_view_contains_trim()
        self.update()

    def set_position(self, position_ms: int) -> None:
        self._position_ms = self._clamp_to_trim(position_ms)
        self.update()

    def position(self) -> int:
        return self._position_ms

    def set_trim_range(self, trim_in_ms: int, trim_out_ms: int) -> None:
        in_value = max(0, min(trim_in_ms, self._duration_ms))
        out_value = max(in_value, min(trim_out_ms, self._duration_ms))
        self._trim_in_ms = in_value
        self._trim_out_ms = out_value
        self._position_ms = self._clamp_to_trim(self._position_ms)
        self._ensure_view_contains_trim()
        self.update()

    def trim_range(self) -> Tuple[int, int]:
        return self._trim_in_ms, self._trim_out_ms

    def set_view_range(self, start_ms: int, end_ms: int) -> bool:
        if (
            start_ms < 0
            or end_ms > self._duration_ms
            or end_ms - start_ms < self._minimum_view_span_ms()
        ):
            return False
        self._view_start_ms = start_ms
        self._view_end_ms = end_ms
        self.viewChanged.emit(start_ms, end_ms)
        self.update()
        return True

    def reset_view_range(self) -> None:
        self._view_start_ms = 0
        self._view_end_ms = self._duration_ms
        self.viewChanged.emit(self._view_start_ms, self._view_end_ms)
        self.update()

    def view_range(self) -> Tuple[int, int]:
        return self._view_start_ms, self._view_end_ms

    def selected_target(self) -> Optional[str]:
        return self._selected_target

    def has_selected_trim_handle(self) -> bool:
        return self._selected_target in {"trim_in", "trim_out"}

    def clear_thumbnails(self) -> None:
        self._thumbnail_job_id = 0
        self._thumbnail_range = (0, 0)
        self._thumbnail_positions = []
        self._thumbnails = []
        self.update()

    def set_thumbnail_request(
        self,
        job_id: int,
        start_ms: int,
        end_ms: int,
        positions_ms: List[int],
    ) -> None:
        self._thumbnail_job_id = job_id
        self._thumbnail_range = (start_ms, end_ms)
        self._thumbnail_positions = list(positions_ms)
        self._thumbnails = [None] * len(positions_ms)
        self.update()

    def set_thumbnail(
        self,
        job_id: int,
        index: int,
        position_ms: int,
        image: QImage,
    ) -> None:
        if job_id != self._thumbnail_job_id:
            return
        if self._thumbnail_range != self.view_range():
            return
        if not (0 <= index < len(self._thumbnails)):
            return
        if self._thumbnail_positions[index] != position_ms:
            return
        self._thumbnails[index] = image
        self.update()

    def zoom_view(self, anchor_ms: int, zoom_in: bool) -> bool:
        if self._duration_ms <= 0:
            return False

        current_start, current_end = self.view_range()
        trim_start, trim_end = self.trim_range()
        current_span = current_end - current_start
        minimum_span = self._minimum_view_span_ms()
        sync_trim_with_view = (current_start, current_end) == self.trim_range()
        if current_span <= 0:
            return False

        trim_span = trim_end - trim_start
        if (
            zoom_in
            and trim_span >= minimum_span
            and trim_span < current_span
            and current_start <= trim_start
            and current_end >= trim_end
        ):
            current_start = trim_start
            current_end = trim_end
            current_span = trim_span

        zoom_factor = 0.85 if zoom_in else 1.15
        target_span = int(round(current_span * zoom_factor))
        target_span = max(minimum_span, min(target_span, self._duration_ms))
        if target_span == current_span:
            return False

        anchor = max(current_start, min(anchor_ms, current_end))
        if current_span <= 0:
            anchor_ratio = 0.5
        else:
            anchor_ratio = (anchor - current_start) / float(current_span)

        start_ms = int(round(anchor - (target_span * anchor_ratio)))
        end_ms = start_ms + target_span

        if start_ms < 0:
            end_ms -= start_ms
            start_ms = 0
        if end_ms > self._duration_ms:
            start_ms -= end_ms - self._duration_ms
            end_ms = self._duration_ms

        if end_ms - start_ms < minimum_span:
            return False
        if sync_trim_with_view:
            self._view_start_ms = start_ms
            self._view_end_ms = end_ms
            self._trim_in_ms = start_ms
            self._trim_out_ms = end_ms
            self._position_ms = self._clamp_to_trim(self._position_ms)
            self.viewChanged.emit(start_ms, end_ms)
            self.trimChanged.emit(start_ms, end_ms)
            self.update()
            return True
        return self.set_view_range(start_ms, end_ms)

    def nudge_selected_view_handle(self, delta_ms: int) -> bool:
        if self._duration_ms <= 0 or delta_ms == 0:
            return False

        if self._selected_target == "view_start":
            start_ms = max(
                0,
                min(self._view_start_ms + delta_ms, self._trim_in_ms),
            )
            if start_ms != self._view_start_ms:
                self.set_view_range(start_ms, self._view_end_ms)
            return True

        if self._selected_target == "view_end":
            end_ms = min(
                self._duration_ms,
                max(self._view_end_ms + delta_ms, self._trim_out_ms),
            )
            if end_ms != self._view_end_ms:
                self.set_view_range(self._view_start_ms, end_ms)
            return True

        return False

    def nudge_selected(self, delta_ms: int) -> bool:
        if self._duration_ms <= 0 or delta_ms == 0:
            return False

        if self._selected_target == "trim_in":
            new_trim_in = max(0, min(self._trim_in_ms + delta_ms, self._trim_out_ms))
            if new_trim_in == self._trim_in_ms:
                return True
            self._trim_in_ms = new_trim_in
            self._position_ms = self._clamp_to_trim(self._position_ms)
            self._ensure_view_contains_trim()
            self.trimChanged.emit(self._trim_in_ms, self._trim_out_ms)
            self.update()
            return True

        if self._selected_target == "trim_out":
            new_trim_out = max(
                self._trim_in_ms, min(self._trim_out_ms + delta_ms, self._duration_ms)
            )
            if new_trim_out == self._trim_out_ms:
                return True
            self._trim_out_ms = new_trim_out
            self._position_ms = self._clamp_to_trim(self._position_ms)
            self._ensure_view_contains_trim()
            self.trimChanged.emit(self._trim_in_ms, self._trim_out_ms)
            self.update()
            return True

        if self._selected_target == "playhead":
            new_position = self._clamp_to_trim(self._position_ms + delta_ms)
            if new_position == self._position_ms:
                return True
            self._position_ms = new_position
            self.seekRequested.emit(self._position_ms)
            self.update()
            return True

        return False

    def _track_rect(self) -> QRectF:
        margin = 10.0
        top = 20.0
        bottom_margin = 6.0
        return QRectF(
            margin,
            top,
            max(10.0, self.width() - (margin * 2.0)),
            max(8.0, self.height() - top - bottom_margin),
        )

    def thumbnail_request_geometry(self) -> Tuple[int, int, int]:
        track = self._track_rect()
        thumb_height = max(8, int(track.height()))
        thumb_width = max(12, int(round(thumb_height * 1.8)))
        count = max(1, int(track.width() // max(thumb_width, 1)))
        count = min(count, 48)
        return thumb_width, thumb_height, count

    def _trim_label(self, value_ms: int) -> str:
        if self._show_frame_values and self._fps is not None:
            frame = max(0, int(round((value_ms / 1000.0) * self._fps)))
            return f"x{frame}"
        total_ms = max(value_ms, 0)
        hours = total_ms // 3_600_000
        minutes = (total_ms % 3_600_000) // 60_000
        seconds = (total_ms % 60_000) // 1000
        millis = total_ms % 1000
        return f"{hours:02d}:{minutes:02d}:{seconds:02d}.{millis:03d}"

    def _clamp_to_trim(self, value_ms: int) -> int:
        return max(self._trim_in_ms, min(value_ms, self._trim_out_ms))

    def _minimum_view_span_ms(self) -> int:
        if self._fps and self._fps > 0:
            return max(1, int(round(1000.0 / self._fps)))
        return 1

    def _ensure_view_contains_trim(self) -> None:
        start_ms = min(self._view_start_ms, self._trim_in_ms)
        end_ms = max(self._view_end_ms, self._trim_out_ms)
        start_ms = max(0, start_ms)
        end_ms = min(self._duration_ms, end_ms)
        if (start_ms, end_ms) == (self._view_start_ms, self._view_end_ms):
            return
        self._view_start_ms = start_ms
        self._view_end_ms = end_ms
        self.viewChanged.emit(start_ms, end_ms)

    def _is_visible(self, value_ms: int) -> bool:
        return self._view_start_ms <= value_ms <= self._view_end_ms

    def _x_from_ms(self, value_ms: int) -> float:
        track = self._track_rect()
        view_duration = self._view_end_ms - self._view_start_ms
        if view_duration <= 0:
            return track.left()
        ratio = float(value_ms - self._view_start_ms) / float(view_duration)
        return track.left() + (track.width() * ratio)

    def _ms_from_x(self, x: float) -> int:
        track = self._track_rect()
        view_duration = self._view_end_ms - self._view_start_ms
        if view_duration <= 0 or track.width() <= 0:
            return 0
        clamped_x = max(track.left(), min(x, track.right()))
        ratio = (clamped_x - track.left()) / track.width()
        return self._view_start_ms + int(round(ratio * view_duration))

    def _distance_to_handle(self, point: QPointF, handle_x: float) -> float:
        return abs(point.x() - handle_x)

    def _draw_handle(
        self,
        painter: QPainter,
        track: QRectF,
        x: float,
        color: QColor,
    ) -> None:
        painter.setPen(QPen(color, 2))
        painter.drawLine(int(x), int(track.top()), int(x), int(track.bottom()))
        painter.setBrush(color)
        painter.setPen(Qt.NoPen)
        painter.drawEllipse(QPointF(x, track.center().y()), 4.0, 4.0)

    def paintEvent(self, _event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)

        track = self._track_rect()
        base_color = QColor("#2a2f38")
        outside_trim_color = QColor(14, 18, 24, 128)
        playhead_color = QColor("#d6d9e0")
        handle_color = QColor("#f8d94a")
        selected_color = QColor("#fff4a3")

        painter.setPen(Qt.NoPen)
        painter.setBrush(base_color)
        painter.drawRoundedRect(track, 3.0, 3.0)
        self._draw_thumbnails(painter, track)

        in_visible = self._is_visible(self._trim_in_ms)
        out_visible = self._is_visible(self._trim_out_ms)
        playhead_visible = self._is_visible(self._position_ms)
        in_x = self._x_from_ms(self._trim_in_ms)
        out_x = self._x_from_ms(self._trim_out_ms)

        if self._annotations_visible and (in_visible or out_visible):
            painter.setPen(QColor("#dbe2e8"))
            label_font = painter.font()
            label_font.setPixelSize(11)
            painter.setFont(label_font)
            if in_visible:
                painter.drawText(
                    QRectF(10.0, 1.0, max(0.0, self.width() - 20.0), 20.0),
                    Qt.AlignLeft | Qt.AlignVCenter,
                    self._trim_label(self._trim_in_ms),
                )
            if out_visible:
                painter.drawText(
                    QRectF(10.0, 1.0, max(0.0, self.width() - 20.0), 20.0),
                    Qt.AlignRight | Qt.AlignVCenter,
                    self._trim_label(self._trim_out_ms),
                )

        visible_trim_start = max(self._trim_in_ms, self._view_start_ms)
        visible_trim_end = min(self._trim_out_ms, self._view_end_ms)
        if visible_trim_start <= visible_trim_end:
            keep_left = self._x_from_ms(visible_trim_start)
            keep_right = self._x_from_ms(visible_trim_end)
            left_dim_rect = QRectF(
                track.left(),
                track.top(),
                max(0.0, keep_left - track.left()),
                track.height(),
            )
            right_dim_rect = QRectF(
                keep_right,
                track.top(),
                max(0.0, track.right() - keep_right),
                track.height(),
            )
            painter.setPen(Qt.NoPen)
            painter.setBrush(outside_trim_color)
            if left_dim_rect.width() > 0:
                painter.drawRect(left_dim_rect)
            if right_dim_rect.width() > 0:
                painter.drawRect(right_dim_rect)

        pending_start, pending_end = self._pending_view_range or self.view_range()
        viewport_handle_color = QColor("#4a535d")
        selected_viewport_color = QColor("#7a858f")
        self._draw_handle(
            painter,
            track,
            self._x_from_ms(pending_start),
            (
                selected_viewport_color
                if self._selected_target == "view_start"
                else viewport_handle_color
            ),
        )
        self._draw_handle(
            painter,
            track,
            self._x_from_ms(pending_end),
            (
                selected_viewport_color
                if self._selected_target == "view_end"
                else viewport_handle_color
            ),
        )

        in_pen_color = selected_color if self._selected_target == "trim_in" else handle_color
        out_pen_color = selected_color if self._selected_target == "trim_out" else handle_color
        if in_visible:
            self._draw_handle(painter, track, in_x, in_pen_color)
        if out_visible:
            self._draw_handle(painter, track, out_x, out_pen_color)

        play_x = self._x_from_ms(self._position_ms)
        if playhead_visible:
            if self._selected_target == "playhead":
                playhead_color = selected_color
            painter.setPen(QPen(playhead_color, 2))
            painter.drawLine(int(play_x), int(track.top()), int(play_x), int(track.bottom()))

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self.thumbnailGeometryChanged.emit()

    def _draw_thumbnails(self, painter: QPainter, track: QRectF) -> None:
        if not self._thumbnails:
            return

        tile_count = len(self._thumbnails)
        tile_width = track.width() / float(max(tile_count, 1))
        for index, image in enumerate(self._thumbnails):
            left = track.left() + (tile_width * index)
            tile_rect = QRectF(left, track.top(), tile_width, track.height())
            if image is None or image.isNull():
                shade = QColor("#313743" if index % 2 == 0 else "#363d49")
                painter.fillRect(tile_rect, shade)
                continue
            painter.drawImage(tile_rect, image)

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if self._duration_ms <= 0:
            return

        point = event.position()
        track = self._track_rect()
        view_start_x = track.left()
        view_end_x = track.right()
        viewport_hit_rect = QRectF(
            track.left(),
            track.top(),
            track.width(),
            track.height(),
        )
        if viewport_hit_rect.contains(point):
            start_distance = self._distance_to_handle(point, view_start_x)
            end_distance = self._distance_to_handle(point, view_end_x)
            if min(start_distance, end_distance) <= 14.0:
                self._drag_mode = "view_start" if start_distance <= end_distance else "view_end"
                self._selected_target = self._drag_mode
                self._view_drag_origin_x = point.x()
                self._view_drag_initial_range = self.view_range()
                self._pending_view_range = self.view_range()
                self.setFocus(Qt.MouseFocusReason)
                self.update()
                return

        in_x = self._x_from_ms(self._trim_in_ms)
        out_x = self._x_from_ms(self._trim_out_ms)
        play_x = self._x_from_ms(self._position_ms)

        threshold = 8.0
        if (
            self._is_visible(self._trim_in_ms)
            and self._distance_to_handle(point, in_x) <= threshold
        ):
            self._drag_mode = "trim_in"
            self._selected_target = "trim_in"
            self.setFocus(Qt.MouseFocusReason)
            self.update()
            return
        if (
            self._is_visible(self._trim_out_ms)
            and self._distance_to_handle(point, out_x) <= threshold
        ):
            self._drag_mode = "trim_out"
            self._selected_target = "trim_out"
            self.setFocus(Qt.MouseFocusReason)
            self.update()
            return
        if (
            self._is_visible(self._position_ms)
            and self._distance_to_handle(point, play_x) <= threshold
        ):
            self._drag_mode = "playhead"
            self._selected_target = "playhead"
            self.setFocus(Qt.MouseFocusReason)
            self.update()
            return

        self._drag_mode = "playhead"
        self._selected_target = "playhead"
        self._position_ms = self._clamp_to_trim(self._ms_from_x(point.x()))
        self.seekRequested.emit(self._position_ms)
        self.setFocus(Qt.MouseFocusReason)
        self.update()

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if self._drag_mode is None:
            return

        if self._drag_mode in {"view_start", "view_end"}:
            track = self._track_rect()
            initial_start, initial_end = self._view_drag_initial_range
            initial_duration = initial_end - initial_start
            if track.width() <= 0 or initial_duration <= 0:
                return
            delta_ratio = (event.position().x() - self._view_drag_origin_x) / track.width()
            delta_ms = int(round(delta_ratio * initial_duration))
            if self._drag_mode == "view_start":
                value = max(0, min(initial_start + delta_ms, self._trim_in_ms))
                self._pending_view_range = (value, initial_end)
            else:
                value = min(
                    self._duration_ms,
                    max(initial_end + delta_ms, self._trim_out_ms),
                )
                self._pending_view_range = (initial_start, value)
            self.update()
            return

        value = self._ms_from_x(event.position().x())

        if self._drag_mode == "trim_in":
            self._trim_in_ms = min(value, self._trim_out_ms)
            self._position_ms = self._clamp_to_trim(self._position_ms)
            self.trimChanged.emit(self._trim_in_ms, self._trim_out_ms)
            self.update()
            return

        if self._drag_mode == "trim_out":
            self._trim_out_ms = max(value, self._trim_in_ms)
            self._position_ms = self._clamp_to_trim(self._position_ms)
            self.trimChanged.emit(self._trim_in_ms, self._trim_out_ms)
            self.update()
            return

        if self._drag_mode == "playhead":
            self._position_ms = self._clamp_to_trim(value)
            self.seekRequested.emit(self._position_ms)
            self.update()

    def mouseReleaseEvent(self, _event: QMouseEvent) -> None:
        drag_mode = self._drag_mode
        pending_view_range = self._pending_view_range
        self._drag_mode = None
        self._pending_view_range = None
        if drag_mode in {"view_start", "view_end"} and pending_view_range is not None:
            if pending_view_range != self.view_range():
                self.set_view_range(*pending_view_range)
            else:
                self.update()

    def wheelEvent(self, event: QWheelEvent) -> None:
        angle_delta = event.angleDelta().y()
        if angle_delta == 0 or self._duration_ms <= 0:
            event.ignore()
            return

        anchor_ms = self._ms_from_x(event.position().x())
        if self.zoom_view(anchor_ms, zoom_in=angle_delta > 0):
            event.accept()
            return
        event.ignore()
