from typing import Optional, Tuple

from PySide6.QtCore import QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QColor, QMouseEvent, QPainter, QPen
from PySide6.QtWidgets import QWidget


class TimelineWidget(QWidget):
    seekRequested = Signal(int)
    trimChanged = Signal(int, int)
    viewChanged = Signal(int, int)

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setMinimumHeight(44)
        self.setFocusPolicy(Qt.StrongFocus)

        self._duration_ms = 0
        self._view_start_ms = 0
        self._view_end_ms = 0
        self._fps: Optional[float] = None
        self._annotations_visible = True
        self._position_ms = 0
        self._trim_in_ms = 0
        self._trim_out_ms = 0
        self._drag_mode: Optional[str] = None
        self._selected_target: Optional[str] = None
        self._view_drag_origin_x = 0.0
        self._view_drag_initial_range = (0, 0)
        self._pending_view_range: Optional[Tuple[int, int]] = None

    def set_frame_rate(self, fps: Optional[float]) -> None:
        self._fps = fps if fps and fps > 0 else None
        self.update()

    def set_annotations_visible(self, visible: bool) -> None:
        self._annotations_visible = visible
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
            or start_ms > self._trim_in_ms
            or end_ms < self._trim_out_ms
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
        return QRectF(margin, 28.0, max(10.0, self.width() - (margin * 2.0)), 6.0)

    def _trim_label(self, value_ms: int) -> str:
        total_ms = max(value_ms, 0)
        hours = total_ms // 3_600_000
        minutes = (total_ms % 3_600_000) // 60_000
        seconds = (total_ms % 60_000) // 1000
        millis = total_ms % 1000
        time_text = f"{hours:02d}:{minutes:02d}:{seconds:02d}.{millis:03d}"
        if self._fps is None:
            return time_text
        frame = max(0, int(round((value_ms / 1000.0) * self._fps)))
        return f"{time_text}  x{frame}"

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
        painter.drawLine(int(x), int(track.top() - 5), int(x), int(track.bottom() + 5))
        painter.setBrush(color)
        painter.setPen(Qt.NoPen)
        painter.drawEllipse(QPointF(x, track.center().y()), 4.0, 4.0)

    def paintEvent(self, _event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)

        track = self._track_rect()
        base_color = QColor("#2a2f38")
        keep_color = QColor("#5b6472")
        playhead_color = QColor("#d6d9e0")
        handle_color = QColor("#f8d94a")
        selected_color = QColor("#fff4a3")

        painter.setPen(Qt.NoPen)
        painter.setBrush(base_color)
        painter.drawRoundedRect(track, 3.0, 3.0)

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
            keep_rect = QRectF(
                keep_left,
                track.top(),
                max(2.0, keep_right - keep_left),
                track.height(),
            )
            painter.setBrush(keep_color)
            painter.drawRoundedRect(keep_rect, 3.0, 3.0)

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
            painter.drawLine(
                int(play_x), int(track.top() - 8), int(play_x), int(track.bottom() + 8)
            )

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if self._duration_ms <= 0:
            return

        point = event.position()
        track = self._track_rect()
        view_start_x = track.left()
        view_end_x = track.right()
        viewport_hit_rect = QRectF(
            track.left(),
            track.center().y() - 3.0,
            track.width(),
            (track.bottom() + 8.0) - (track.center().y() - 3.0),
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
