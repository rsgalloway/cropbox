from typing import Optional, Tuple

from PySide6.QtCore import QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QColor, QMouseEvent, QPainter, QPen
from PySide6.QtWidgets import QWidget


class TimelineWidget(QWidget):
    seekRequested = Signal(int)
    trimChanged = Signal(int, int)

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setMinimumHeight(44)
        self.setFocusPolicy(Qt.StrongFocus)

        self._duration_ms = 0
        self._fps: Optional[float] = None
        self._annotations_visible = True
        self._position_ms = 0
        self._trim_in_ms = 0
        self._trim_out_ms = 0
        self._drag_mode: Optional[str] = None
        self._selected_target: Optional[str] = None

    def set_frame_rate(self, fps: Optional[float]) -> None:
        self._fps = fps if fps and fps > 0 else None
        self.update()

    def set_annotations_visible(self, visible: bool) -> None:
        self._annotations_visible = visible
        self.update()

    def set_duration(self, duration_ms: int) -> None:
        duration = max(0, duration_ms)
        self._duration_ms = duration
        self._trim_in_ms = max(0, min(self._trim_in_ms, duration))
        self._trim_out_ms = max(self._trim_in_ms, min(self._trim_out_ms or duration, duration))
        self._position_ms = max(self._trim_in_ms, min(self._position_ms, self._trim_out_ms))
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
        self.update()

    def trim_range(self) -> Tuple[int, int]:
        return self._trim_in_ms, self._trim_out_ms

    def selected_target(self) -> Optional[str]:
        return self._selected_target

    def has_selected_trim_handle(self) -> bool:
        return self._selected_target in {"trim_in", "trim_out"}

    def nudge_selected(self, delta_ms: int) -> bool:
        if self._duration_ms <= 0 or delta_ms == 0:
            return False

        if self._selected_target == "trim_in":
            new_trim_in = max(0, min(self._trim_in_ms + delta_ms, self._trim_out_ms))
            if new_trim_in == self._trim_in_ms:
                return True
            self._trim_in_ms = new_trim_in
            self._position_ms = self._clamp_to_trim(self._position_ms)
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

    def _x_from_ms(self, value_ms: int) -> float:
        track = self._track_rect()
        if self._duration_ms <= 0:
            return track.left()
        ratio = float(value_ms) / float(self._duration_ms)
        return track.left() + (track.width() * ratio)

    def _ms_from_x(self, x: float) -> int:
        track = self._track_rect()
        if self._duration_ms <= 0 or track.width() <= 0:
            return 0
        clamped_x = max(track.left(), min(x, track.right()))
        ratio = (clamped_x - track.left()) / track.width()
        return int(round(ratio * self._duration_ms))

    def _distance_to_handle(self, point: QPointF, handle_x: float) -> float:
        return abs(point.x() - handle_x)

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

        in_x = self._x_from_ms(self._trim_in_ms)
        out_x = self._x_from_ms(self._trim_out_ms)

        if self._annotations_visible:
            painter.setPen(QColor("#dbe2e8"))
            label_font = painter.font()
            label_font.setPixelSize(11)
            painter.setFont(label_font)
            painter.drawText(
                QRectF(10.0, 1.0, max(0.0, self.width() - 20.0), 20.0),
                Qt.AlignLeft | Qt.AlignVCenter,
                self._trim_label(self._trim_in_ms),
            )
            painter.drawText(
                QRectF(10.0, 1.0, max(0.0, self.width() - 20.0), 20.0),
                Qt.AlignRight | Qt.AlignVCenter,
                self._trim_label(self._trim_out_ms),
            )

        keep_rect = QRectF(in_x, track.top(), max(2.0, out_x - in_x), track.height())
        painter.setBrush(keep_color)
        painter.drawRoundedRect(keep_rect, 3.0, 3.0)

        in_pen_color = selected_color if self._selected_target == "trim_in" else handle_color
        out_pen_color = selected_color if self._selected_target == "trim_out" else handle_color
        painter.setPen(QPen(in_pen_color, 2))
        painter.drawLine(int(in_x), int(track.top() - 5), int(in_x), int(track.bottom() + 5))
        painter.setPen(QPen(out_pen_color, 2))
        painter.drawLine(int(out_x), int(track.top() - 5), int(out_x), int(track.bottom() + 5))

        painter.setBrush(in_pen_color)
        painter.setPen(Qt.NoPen)
        painter.drawEllipse(QPointF(in_x, track.center().y()), 4.0, 4.0)
        painter.setBrush(out_pen_color)
        painter.drawEllipse(QPointF(out_x, track.center().y()), 4.0, 4.0)

        play_x = self._x_from_ms(self._position_ms)
        if self._selected_target == "playhead":
            playhead_color = selected_color
        painter.setPen(QPen(playhead_color, 2))
        painter.drawLine(int(play_x), int(track.top() - 8), int(play_x), int(track.bottom() + 8))

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if self._duration_ms <= 0:
            return

        point = event.position()
        in_x = self._x_from_ms(self._trim_in_ms)
        out_x = self._x_from_ms(self._trim_out_ms)
        play_x = self._x_from_ms(self._position_ms)

        threshold = 8.0
        if self._distance_to_handle(point, in_x) <= threshold:
            self._drag_mode = "trim_in"
            self._selected_target = "trim_in"
            self.setFocus(Qt.MouseFocusReason)
            self.update()
            return
        if self._distance_to_handle(point, out_x) <= threshold:
            self._drag_mode = "trim_out"
            self._selected_target = "trim_out"
            self.setFocus(Qt.MouseFocusReason)
            self.update()
            return
        if self._distance_to_handle(point, play_x) <= threshold:
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
        self._drag_mode = None
