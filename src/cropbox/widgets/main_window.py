from pathlib import Path
from typing import Dict, List, Optional

from PySide6.QtCore import QEvent, Qt, QUrl
from PySide6.QtGui import QAction, QActionGroup, QIcon, QImage, QKeySequence, QMovie, QShortcut
from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer, QVideoFrame, QVideoSink
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMenu,
    QMessageBox,
    QStyle,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from cropbox import __version__
from cropbox.media.commands import build_export_command
from cropbox.media.dependencies import missing_media_tools
from cropbox.media.exporter import Exporter
from cropbox.media.probe import ProbeError, probe_media
from cropbox.models.crop_rect import CropRect
from cropbox.models.edit_session import EditSession
from cropbox.models.trim_range import TrimRange
from cropbox.widgets.crop_overlay import CropOverlay
from cropbox.widgets.player_widget import PlayerWidget
from cropbox.widgets.timeline import TimelineWidget


def _format_time(seconds: float) -> str:
    total_ms = max(int(seconds * 1000), 0)
    hours = total_ms // 3_600_000
    minutes = (total_ms % 3_600_000) // 60_000
    secs = (total_ms % 60_000) // 1000
    millis = total_ms % 1000
    return f"{hours:02d}:{minutes:02d}:{secs:02d}.{millis:03d}"


def _parse_time_to_ms(value: str) -> Optional[int]:
    text = value.strip()
    if not text:
        return None

    try:
        if ":" not in text:
            return max(0, int(round(float(text) * 1000.0)))

        parts = text.split(":")
        if len(parts) > 3:
            return None

        seconds = float(parts[-1])
        minutes = int(parts[-2]) if len(parts) >= 2 else 0
        hours = int(parts[-3]) if len(parts) == 3 else 0
        total_seconds = seconds + (minutes * 60) + (hours * 3600)
        return max(0, int(round(total_seconds * 1000.0)))
    except ValueError:
        return None


class TrimValueDialog(QDialog):
    def __init__(
        self,
        title: str,
        current_ms: int,
        fps: Optional[float],
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setModal(True)
        self.resize(520, 220)

        self._fps = fps
        self._value_ms: Optional[int] = None

        self.time_edit = QLineEdit(_format_time(current_ms / 1000.0), self)
        self.frame_edit = QLineEdit(self)
        if fps and fps > 0:
            frame_value = int(round((current_ms / 1000.0) * fps))
            self.frame_edit.setText(str(frame_value))
        else:
            self.frame_edit.setPlaceholderText("Frame entry unavailable")
            self.frame_edit.setEnabled(False)

        self.error_label = QLabel("", self)
        self.error_label.setStyleSheet("color: #ff8a8a;")
        self.error_label.setWordWrap(True)

        form_layout = QFormLayout()
        form_layout.addRow("Time", self.time_edit)
        form_layout.addRow("Frame", self.frame_edit)

        hint_label = QLabel(
            "Enter a time like 00:01:23.456 or seconds like 83.456. "
            "If a frame number is provided, it takes precedence.",
            self,
        )
        hint_label.setWordWrap(True)

        buttons = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel,
            Qt.Horizontal,
            self,
        )
        buttons.accepted.connect(self._accept)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addLayout(form_layout)
        layout.addWidget(hint_label)
        layout.addWidget(self.error_label)
        layout.addWidget(buttons)

    def value_ms(self) -> Optional[int]:
        return self._value_ms

    def _accept(self) -> None:
        frame_text = self.frame_edit.text().strip()
        if frame_text:
            if not self._fps or self._fps <= 0:
                self.error_label.setText(
                    "Frame entry is unavailable because frame rate is unknown."
                )
                return
            try:
                frame_number = int(frame_text)
            except ValueError:
                self.error_label.setText("Frame number must be a whole number.")
                return
            self._value_ms = max(0, int(round((frame_number * 1000.0) / self._fps)))
            self.accept()
            return

        time_ms = _parse_time_to_ms(self.time_edit.text())
        if time_ms is None:
            self.error_label.setText("Enter a valid time like 00:01:23.456 or 83.456.")
            return

        self._value_ms = time_ms
        self.accept()


class MainWindow(QMainWindow):
    PLAYBACK_SPEEDS = (
        ("3x", 3.0),
        ("2x", 2.0),
        ("1x", 1.0),
        ("0.75x", 0.75),
        ("0.5x", 0.5),
        ("0.25x", 0.25),
    )

    def __init__(
        self,
        initial_media_path: Optional[Path] = None,
        initial_trim: Optional[TrimRange] = None,
        initial_crop: Optional[CropRect] = None,
    ) -> None:
        super().__init__()
        self.setWindowTitle("Cropbox")
        self.resize(1200, 760)

        self._media_player = QMediaPlayer(self)
        self._audio_output = QAudioOutput(self)
        self._video_sink = QVideoSink(self)
        self._audio_output.setMuted(True)
        self._media_player.setAudioOutput(self._audio_output)
        self._media_player.setVideoSink(self._video_sink)
        self._exporter = Exporter()

        self._session: Optional[EditSession] = None
        self._duration_ms = 0
        self._fps: Optional[float] = None
        self._loop_playback = True
        self._gif_movie: Optional[QMovie] = None
        self._gif_position_ms = 0
        self._playback_rate = 1.0
        self._missing_tools = missing_media_tools()
        self._playback_speed_actions: Dict[float, QAction] = {}
        self._initial_trim = initial_trim
        self._initial_crop = initial_crop

        self._build_ui()
        self._build_menus()
        self._wire_signals()
        self._update_controls_for_session()
        self._warn_missing_media_tools()

        if initial_media_path is not None:
            self._load_media(initial_media_path)

    def _build_ui(self) -> None:
        central = QWidget(self)
        central.setObjectName("mainContent")
        self.setCentralWidget(central)

        self.video_container = QWidget(self)
        video_layout = QVBoxLayout(self.video_container)
        video_layout.setContentsMargins(0, 0, 0, 0)

        self.video_frame = QWidget(self.video_container)
        self.video_frame.setObjectName("videoFrame")
        video_layout.addWidget(self.video_frame)

        self.video_widget = PlayerWidget(self.video_frame)
        self.video_widget.setGeometry(self.video_frame.rect())

        self.video_container.installEventFilter(self)
        self.video_frame.installEventFilter(self)
        self.video_container.setContextMenuPolicy(Qt.CustomContextMenu)

        self.crop_overlay = CropOverlay(self.video_frame)
        self.crop_overlay.setGeometry(self.video_frame.rect())
        self.crop_overlay.raise_()
        self.crop_overlay.hide()

        self.timeline_widget = TimelineWidget(self)

        self.play_button = QToolButton(self)
        self.play_button.setIcon(self.style().standardIcon(QStyle.SP_MediaPlay))
        self.play_button.setToolTip("Play/Pause (Space)")

        self.mute_button = QToolButton(self)
        self.mute_button.setToolTip("Toggle mute")
        self.mute_button.setAutoRaise(False)

        self.position_label = QLabel("00:00:00.000", self)

        transport_row = QHBoxLayout()
        transport_row.addWidget(self.timeline_widget, stretch=1)
        transport_row.addSpacing(10)
        transport_row.addWidget(self.position_label)
        transport_row.addWidget(self.mute_button)
        transport_row.addWidget(self.play_button)

        layout = QVBoxLayout(central)
        layout.addWidget(self.video_container, stretch=1)
        layout.addLayout(transport_row)

        self.video_frame.setStyleSheet(
            """
            QWidget#videoFrame {
                background-color: #050608;
                border-radius: 10px;
            }
            """
        )
        self._update_mute_button()

    def _build_menus(self) -> None:
        file_menu = self.menuBar().addMenu("File")
        edit_menu = self.menuBar().addMenu("Edit")
        help_menu = self.menuBar().addMenu("Help")
        playback_speed_menu = QMenu("Playback Speed", self)

        open_action = QAction("Open", self)
        open_action.setShortcut(QKeySequence.Open)
        open_action.triggered.connect(self.open_media)

        save_as_action = QAction("Export", self)
        save_as_action.setShortcut(QKeySequence.SaveAs)
        save_as_action.triggered.connect(self.save_as)

        quit_action = QAction("Quit", self)
        quit_action.setShortcut(QKeySequence.Quit)
        quit_action.triggered.connect(self.close)

        self.set_trim_in_action = QAction("Set Trim In", self)
        self.set_trim_in_action.triggered.connect(self.show_trim_in_dialog)

        self.set_trim_out_action = QAction("Set Trim Out", self)
        self.set_trim_out_action.triggered.connect(self.show_trim_out_dialog)

        self.reset_trim_action = QAction("Reset Trim", self)
        self.reset_trim_action.triggered.connect(self.reset_trim)

        self.create_crop_action = QAction("Create Crop", self)
        self.create_crop_action.triggered.connect(self.create_crop)

        self.reset_crop_action = QAction("Reset Crop", self)
        self.reset_crop_action.triggered.connect(self.reset_crop)

        self.loop_playback_action = QAction("Loop Playback", self)
        self.loop_playback_action.setCheckable(True)
        self.loop_playback_action.setChecked(True)
        self.loop_playback_action.toggled.connect(self._set_loop_playback)

        self.playback_speed_group = QActionGroup(self)
        self.playback_speed_group.setExclusive(True)
        for label, rate in self.PLAYBACK_SPEEDS:
            action = QAction(label, self)
            action.setCheckable(True)
            if rate == self._playback_rate:
                action.setChecked(True)
            action.triggered.connect(
                lambda checked=False, selected_rate=rate: self.set_playback_rate(selected_rate)
            )
            self.playback_speed_group.addAction(action)
            playback_speed_menu.addAction(action)
            self._playback_speed_actions[rate] = action

        about_action = QAction("About Cropbox", self)
        about_action.triggered.connect(self.show_about_dialog)
        install_ffmpeg_action = QAction("Install FFmpeg", self)
        install_ffmpeg_action.triggered.connect(self.show_ffmpeg_install_dialog)

        file_menu.addAction(open_action)
        file_menu.addAction(save_as_action)
        file_menu.addSeparator()
        file_menu.addAction(quit_action)

        edit_menu.addAction(self.set_trim_in_action)
        edit_menu.addAction(self.set_trim_out_action)
        edit_menu.addAction(self.reset_trim_action)
        edit_menu.addSeparator()
        edit_menu.addAction(self.create_crop_action)
        edit_menu.addAction(self.reset_crop_action)
        edit_menu.addSeparator()
        edit_menu.addMenu(playback_speed_menu)
        edit_menu.addSeparator()
        edit_menu.addAction(self.loop_playback_action)

        help_menu.addAction(install_ffmpeg_action)
        help_menu.addSeparator()
        help_menu.addAction(about_action)

        QShortcut(QKeySequence(Qt.Key_Space), self, activated=self.toggle_play_pause)
        QShortcut(QKeySequence(Qt.Key_Left), self, activated=lambda: self.step_frame(-1))
        QShortcut(QKeySequence(Qt.Key_Right), self, activated=lambda: self.step_frame(1))
        QShortcut(
            QKeySequence(Qt.SHIFT | Qt.Key_Left),
            self,
            activated=lambda: self._nudge_trim_handle(-1),
        )
        QShortcut(
            QKeySequence(Qt.SHIFT | Qt.Key_Right),
            self,
            activated=lambda: self._nudge_trim_handle(1),
        )

    def _wire_signals(self) -> None:
        self.play_button.clicked.connect(self.toggle_play_pause)
        self.mute_button.clicked.connect(self.toggle_mute)
        self.timeline_widget.seekRequested.connect(self._seek_from_timeline)
        self.timeline_widget.trimChanged.connect(self._timeline_trim_changed)
        self.crop_overlay.cropChanged.connect(self._overlay_crop_changed)
        self.video_container.customContextMenuRequested.connect(self._show_video_context_menu)
        self._video_sink.videoFrameChanged.connect(self._on_video_frame_changed)

        self._media_player.positionChanged.connect(self._on_position_changed)
        self._media_player.durationChanged.connect(self._on_duration_changed)
        self._media_player.playbackStateChanged.connect(self._on_playback_state_changed)

        self._exporter.finished.connect(self._on_export_finished)
        self._exporter.failed.connect(self._on_export_failed)

    def _update_controls_for_session(self) -> None:
        enabled = self._session is not None
        self.play_button.setEnabled(enabled)
        self.timeline_widget.setEnabled(enabled)
        self.set_trim_in_action.setEnabled(enabled)
        self.set_trim_out_action.setEnabled(enabled)
        self.reset_trim_action.setEnabled(enabled)
        self.create_crop_action.setEnabled(enabled)
        self.reset_crop_action.setEnabled(enabled)
        self.loop_playback_action.setEnabled(enabled)
        self.mute_button.setEnabled(enabled)

    def _warn_missing_media_tools(self) -> None:
        if not self._missing_tools:
            return
        QMessageBox.warning(
            self,
            "Missing Media Tools",
            (
                "Cropbox requires ffmpeg and ffprobe for probing and export.\n\n"
                f"Missing: {', '.join(self._missing_tools)}\n\n"
                "Use Help -> Install FFmpeg for installation guidance."
            ),
        )

    def _check_media_tools(self, tools: Optional[List[str]] = None) -> bool:
        current_missing = set(missing_media_tools())
        if tools is not None:
            current_missing = {tool for tool in current_missing if tool in tools}
        if not current_missing:
            self._missing_tools = []
            return True

        QMessageBox.warning(
            self,
            "Missing Media Tools",
            (
                f"Cropbox requires {', '.join(sorted(current_missing))} for this action.\n\n"
                "Use Help -> Install FFmpeg for installation guidance."
            ),
        )
        return False

    def open_media(self) -> None:
        if not self._check_media_tools(["ffprobe"]):
            return
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Open Media",
            "",
            "Media Files (*.mp4 *.mov *.mkv *.webm *.gif);;All Files (*)",
        )
        if not file_path:
            return
        self._load_media(Path(file_path))

    def _is_gif_media(self, path: Path) -> bool:
        return path.suffix.lower() == ".gif"

    def _is_gif_mode(self) -> bool:
        return self._gif_movie is not None

    def _set_play_icon(self, is_playing: bool) -> None:
        if is_playing:
            self.play_button.setIcon(self.style().standardIcon(QStyle.SP_MediaPause))
        else:
            self.play_button.setIcon(self.style().standardIcon(QStyle.SP_MediaPlay))

    def _update_mute_button(self) -> None:
        is_muted = self._audio_output.isMuted()
        self.mute_button.setIcon(QIcon())
        self.mute_button.setText("Muted" if is_muted else "Audio")
        self.mute_button.setToolTip("Unmute" if is_muted else "Mute")

    def _apply_playback_rate(self) -> None:
        self._media_player.setPlaybackRate(self._playback_rate)
        if self._gif_movie is not None:
            self._gif_movie.setSpeed(int(round(self._playback_rate * 100.0)))

    def _stop_gif_movie(self) -> None:
        if self._gif_movie is None:
            return
        self._gif_movie.stop()
        self._gif_movie.deleteLater()
        self._gif_movie = None
        self._gif_position_ms = 0

    def _frame_to_position_ms(self, frame_number: int) -> int:
        if self._gif_movie is not None:
            frame_count = self._gif_movie.frameCount()
            if frame_count > 1 and self._duration_ms > 0:
                return int(round((frame_number / float(frame_count - 1)) * self._duration_ms))
        if self._fps and self._fps > 0:
            return int(round((frame_number * 1000.0) / self._fps))
        return self._gif_position_ms

    def _position_to_frame(self, position_ms: int) -> int:
        if self._gif_movie is not None:
            frame_count = self._gif_movie.frameCount()
            if frame_count > 1 and self._duration_ms > 0:
                ratio = max(0.0, min(float(position_ms) / float(self._duration_ms), 1.0))
                return int(round(ratio * (frame_count - 1)))
        if self._fps and self._fps > 0:
            return max(0, int(round((position_ms / 1000.0) * self._fps)))
        return 0

    def _current_position_ms(self) -> int:
        if self._is_gif_mode():
            return self._gif_position_ms
        return self._media_player.position()

    def _seek_gif(self, position_ms: int) -> None:
        if self._gif_movie is None:
            return
        clamped = max(0, min(position_ms, self._duration_ms))
        frame_number = self._position_to_frame(clamped)
        if not self._gif_movie.jumpToFrame(frame_number):
            self._gif_position_ms = clamped
            self.position_label.setText(_format_time(clamped / 1000.0))
            self.timeline_widget.set_position(clamped)

    def _load_gif_movie(self, path: Path) -> None:
        self._stop_gif_movie()
        movie = QMovie(str(path))
        movie.setCacheMode(QMovie.CacheAll)
        movie.frameChanged.connect(self._on_gif_frame_changed)
        movie.start()
        if not movie.isValid():
            movie.deleteLater()
            raise ProbeError("Qt could not decode this GIF for playback.")
        movie.setPaused(True)
        movie.jumpToFrame(0)
        self._gif_movie = movie
        self._gif_position_ms = 0
        self._set_play_icon(False)
        self._apply_playback_rate()

    def _load_media(self, path: Path) -> None:
        if not path.exists():
            QMessageBox.critical(self, "Open Failed", f"File not found:\n{path}")
            return

        try:
            media_info = probe_media(path)
        except ProbeError as exc:
            QMessageBox.critical(self, "Open Failed", str(exc))
            return

        trim = TrimRange(0.0, max(media_info.duration, 0.0))
        self._session = EditSession(
            media=media_info,
            crop=CropRect(x=0, y=0, width=media_info.width, height=media_info.height),
            trim=trim,
        )
        self._apply_initial_edit_options()
        self._fps = media_info.frame_rate
        self._duration_ms = max(int(media_info.duration * 1000), 0)

        initial_trim = self._session.trim.normalized()
        trim_in_ms = max(int(initial_trim.start * 1000), 0)
        trim_out_ms = max(int(initial_trim.end * 1000), 0)
        self.timeline_widget.set_duration(self._duration_ms)
        self.timeline_widget.set_trim_range(trim_in_ms, trim_out_ms)
        self.timeline_widget.set_position(trim_in_ms)

        self.crop_overlay.set_source_size(media_info.width, media_info.height)
        self.crop_overlay.set_crop_rect(self._session.crop)
        self.crop_overlay.show()
        self.video_widget.clear()

        self._media_player.stop()
        self._media_player.setSource(QUrl())

        if self._is_gif_media(path):
            self._load_gif_movie(path)
        else:
            self._stop_gif_movie()
            self._media_player.setSource(QUrl.fromLocalFile(str(path)))
            self._media_player.setPosition(trim_in_ms)
            self._media_player.pause()
            self._apply_playback_rate()

        if self._is_gif_mode():
            self._seek_gif(trim_in_ms)

        self._audio_output.setMuted(True)
        self._update_mute_button()
        if not media_info.has_audio:
            self.mute_button.setEnabled(False)

        self._refresh_trim_labels()
        self._update_controls_for_session()
        self._sync_video_overlay_geometry()

    def _apply_initial_edit_options(self) -> None:
        if self._session is None:
            return

        media = self._session.media
        if self._initial_trim is not None:
            normalized = self._initial_trim.normalized()
            start = max(0.0, min(normalized.start, media.duration))
            end = max(start, min(normalized.end, media.duration))
            self._session.trim = TrimRange(start=start, end=end)
            self._initial_trim = None

        if self._initial_crop is not None:
            crop = self._initial_crop
            x = max(0, min(crop.x, max(media.width - 1, 0)))
            y = max(0, min(crop.y, max(media.height - 1, 0)))
            max_width = max(media.width - x, 1)
            max_height = max(media.height - y, 1)
            width = max(1, min(crop.width, max_width))
            height = max(1, min(crop.height, max_height))
            self._session.crop = CropRect(x=x, y=y, width=width, height=height)
            self._initial_crop = None

    def save_as(self) -> None:
        if self._session is None:
            QMessageBox.information(self, "No Media", "Open a media file first.")
            return
        if not self._check_media_tools(["ffmpeg"]):
            return

        output_path, _ = QFileDialog.getSaveFileName(
            self,
            "Save As",
            self._session.media.path.with_suffix(".mp4").as_posix(),
            "Video Files (*.mp4 *.mov *.gif)",
        )
        if not output_path:
            return

        normalized = self._session.trim.normalized()
        command = build_export_command(
            input_path=self._session.media.path,
            output_path=Path(output_path),
            trim_start=normalized.start,
            trim_end=normalized.end,
            crop=self._effective_crop_for_export(),
            playback_rate=self._playback_rate,
            has_audio=self._session.media.has_audio,
        )
        self._exporter.start(command, Path(output_path))

    def _effective_crop_for_export(self) -> Optional[CropRect]:
        if self._session is None:
            return None
        crop = self._session.crop
        if crop is None:
            return None
        if (
            crop.x == 0
            and crop.y == 0
            and crop.width == self._session.media.width
            and crop.height == self._session.media.height
        ):
            return None
        return crop

    def reset_crop(self) -> None:
        if self._session is None:
            return
        self._session.crop = CropRect(
            x=0,
            y=0,
            width=self._session.media.width,
            height=self._session.media.height,
        )
        self.crop_overlay.set_crop_rect(self._session.crop)

    def create_crop(self) -> None:
        if self._session is None:
            return

        media = self._session.media
        crop_width = max(2, int(media.width * 0.8))
        crop_height = max(2, int(media.height * 0.8))
        crop_x = max(0, (media.width - crop_width) // 2)
        crop_y = max(0, (media.height - crop_height) // 2)

        self._session.crop = CropRect(
            x=crop_x,
            y=crop_y,
            width=crop_width,
            height=crop_height,
        )
        self.crop_overlay.set_crop_rect(self._session.crop)
        self.crop_overlay.show()

    def _set_loop_playback(self, enabled: bool) -> None:
        self._loop_playback = enabled

    def set_playback_rate(self, rate: float) -> None:
        self._playback_rate = rate
        self._apply_playback_rate()
        action = self._playback_speed_actions.get(rate)
        if action is not None and not action.isChecked():
            action.setChecked(True)

    def _show_trim_value_dialog(self, title: str, current_ms: int) -> Optional[int]:
        dialog = TrimValueDialog(title, current_ms, self._fps, self)
        if dialog.exec() != QDialog.Accepted:
            return None
        return dialog.value_ms()

    def show_trim_in_dialog(self) -> None:
        if self._session is None:
            return
        trim_in_ms, trim_out_ms = self.timeline_widget.trim_range()
        value = self._show_trim_value_dialog("Set Trim In", trim_in_ms)
        if value is None:
            return
        self.timeline_widget.set_trim_range(min(value, trim_out_ms), trim_out_ms)
        self._timeline_trim_changed(*self.timeline_widget.trim_range())

    def show_trim_out_dialog(self) -> None:
        if self._session is None:
            return
        trim_in_ms, trim_out_ms = self.timeline_widget.trim_range()
        value = self._show_trim_value_dialog("Set Trim Out", trim_out_ms)
        if value is None:
            return
        self.timeline_widget.set_trim_range(trim_in_ms, max(value, trim_in_ms))
        self._timeline_trim_changed(*self.timeline_widget.trim_range())

    def set_trim_in_to_position(self) -> None:
        if self._session is None:
            return
        trim_in, trim_out = self.timeline_widget.trim_range()
        current = self._current_position_ms()
        self.timeline_widget.set_trim_range(min(current, trim_out), trim_out)
        self._timeline_trim_changed(*self.timeline_widget.trim_range())

    def set_trim_out_to_position(self) -> None:
        if self._session is None:
            return
        trim_in, trim_out = self.timeline_widget.trim_range()
        current = self._current_position_ms()
        self.timeline_widget.set_trim_range(trim_in, max(current, trim_in))
        self._timeline_trim_changed(*self.timeline_widget.trim_range())

    def reset_trim(self) -> None:
        if self._session is None:
            return
        self.timeline_widget.set_trim_range(0, self._duration_ms)
        self._timeline_trim_changed(0, self._duration_ms)

    def toggle_play_pause(self) -> None:
        if self._session is None:
            return

        trim_in_ms, trim_out_ms = self.timeline_widget.trim_range()
        current = self._current_position_ms()
        if current < trim_in_ms or current > trim_out_ms:
            if self._is_gif_mode():
                self._seek_gif(trim_in_ms)
            else:
                self._media_player.setPosition(trim_in_ms)

        if self._is_gif_mode():
            if self._gif_movie is None:
                return
            if self._gif_movie.state() == QMovie.MovieState.Running:
                self._gif_movie.setPaused(True)
                self._set_play_icon(False)
            else:
                if self._gif_movie.state() != QMovie.MovieState.Running:
                    self._gif_movie.start()
                self._gif_movie.setPaused(False)
                self._set_play_icon(True)
            return

        if self._media_player.playbackState() == QMediaPlayer.PlayingState:
            self._media_player.pause()
        else:
            self._media_player.play()

    def toggle_mute(self) -> None:
        if self._session is None or not self._session.media.has_audio:
            return
        muted = not self._audio_output.isMuted()
        self._audio_output.setMuted(muted)
        self._update_mute_button()

    def step_frame(self, direction: int) -> None:
        if self._session is None:
            return
        if self._fps and self._fps > 0:
            step_ms = max(int(round(1000.0 / self._fps)), 1)
        else:
            step_ms = 33

        trim_in_ms, trim_out_ms = self.timeline_widget.trim_range()
        new_position = self._current_position_ms() + (step_ms * direction)
        new_position = max(trim_in_ms, min(new_position, trim_out_ms))
        if self._is_gif_mode():
            self._seek_gif(new_position)
        else:
            self._media_player.setPosition(new_position)

    def _nudge_trim_handle(self, direction: int) -> None:
        if self._session is None:
            return

        if self._fps and self._fps > 0:
            step_ms = max(int(round(1000.0 / self._fps)), 1)
        else:
            step_ms = 33

        if self.timeline_widget.has_selected_trim_handle():
            if self.timeline_widget.nudge_selected(step_ms * direction):
                self._timeline_trim_changed(*self.timeline_widget.trim_range())

    def _seek_from_timeline(self, value: int) -> None:
        trim_in_ms, trim_out_ms = self.timeline_widget.trim_range()
        clamped = max(trim_in_ms, min(value, trim_out_ms))
        if self._is_gif_mode():
            self._seek_gif(clamped)
        else:
            self._media_player.setPosition(clamped)

    def _timeline_trim_changed(self, trim_in_ms: int, trim_out_ms: int) -> None:
        if self._session is None:
            return
        self._session.trim = TrimRange(
            start=trim_in_ms / 1000.0,
            end=trim_out_ms / 1000.0,
        )
        current = self._current_position_ms()
        if current < trim_in_ms or current > trim_out_ms:
            if self._is_gif_mode():
                self._seek_gif(trim_in_ms)
            else:
                self._media_player.setPosition(trim_in_ms)
        self._refresh_trim_labels()

    def _overlay_crop_changed(self, x: int, y: int, width: int, height: int) -> None:
        if self._session is None:
            return
        self._session.crop = CropRect(x=x, y=y, width=width, height=height)

    def _show_video_context_menu(self, pos) -> None:
        menu = QMenu(self)
        menu.addAction(self.set_trim_in_action)
        menu.addAction(self.set_trim_out_action)
        menu.addAction(self.reset_trim_action)
        menu.addSeparator()
        menu.addAction(self.create_crop_action)
        menu.addAction(self.reset_crop_action)
        menu.addSeparator()
        menu.addAction(self.loop_playback_action)
        menu.exec(self.video_container.mapToGlobal(pos))

    def show_about_dialog(self) -> None:
        QMessageBox.about(
            self,
            "About Cropbox",
            (
                f"<b>Cropbox</b><br>"
                f"Version {__version__}<br><br>"
                "A lightweight media crop and trim tool for quickly previewing, "
                "trimming, cropping, and exporting clips.<br><br>"
                'Repository: <a href="https://github.com/rsgalloway/cropbox">'
                "github.com/rsgalloway/cropbox</a>"
            ),
        )

    def show_ffmpeg_install_dialog(self) -> None:
        QMessageBox.information(
            self,
            "Install FFmpeg",
            (
                "Cropbox requires ffmpeg and ffprobe for probing and export.\n\n"
                "Ubuntu/Debian:\n"
                "  sudo apt install ffmpeg\n\n"
                "macOS with Homebrew:\n"
                "  brew install ffmpeg\n\n"
                "Windows:\n"
                "  Install FFmpeg and make sure ffmpeg.exe and ffprobe.exe are on PATH."
            ),
        )

    def _sync_video_overlay_geometry(self) -> None:
        frame_rect = self.video_frame.rect()
        self.video_widget.setGeometry(frame_rect)
        self.crop_overlay.setGeometry(frame_rect)
        self.crop_overlay.raise_()

    def eventFilter(self, watched, event) -> bool:
        if watched in {self.video_container, self.video_frame} and event.type() in {
            QEvent.Resize,
            QEvent.Show,
        }:
            self._sync_video_overlay_geometry()
            self.crop_overlay.update()
        return super().eventFilter(watched, event)

    def _on_video_frame_changed(self, frame: QVideoFrame) -> None:
        if self._is_gif_mode():
            return
        image = frame.toImage()
        if image.isNull():
            return
        if image.format() != QImage.Format_RGB32:
            image = image.convertToFormat(QImage.Format_RGB32)
        self.video_widget.set_frame(image)

    def _on_gif_frame_changed(self, frame_number: int) -> None:
        if self._gif_movie is None:
            return

        image = self._gif_movie.currentImage()
        if not image.isNull():
            if image.format() != QImage.Format_RGB32:
                image = image.convertToFormat(QImage.Format_RGB32)
            self.video_widget.set_frame(image)

        position = self._frame_to_position_ms(frame_number)
        trim_in_ms, trim_out_ms = self.timeline_widget.trim_range()
        if self._gif_movie.state() == QMovie.MovieState.Running:
            if position < trim_in_ms:
                self._seek_gif(trim_in_ms)
                return
            if position >= trim_out_ms:
                if self._loop_playback and trim_out_ms > trim_in_ms:
                    self._seek_gif(trim_in_ms)
                else:
                    self._gif_movie.setPaused(True)
                    self._set_play_icon(False)
                    position = trim_out_ms

        self._gif_position_ms = position
        self.position_label.setText(_format_time(position / 1000.0))
        self.timeline_widget.set_position(position)

    def _refresh_trim_labels(self) -> None:
        return

    def _on_position_changed(self, position: int) -> None:
        trim_in_ms, trim_out_ms = self.timeline_widget.trim_range()
        if (
            self._session is not None
            and self._media_player.playbackState() == QMediaPlayer.PlayingState
        ):
            if position < trim_in_ms:
                self._media_player.setPosition(trim_in_ms)
                return
            if position >= trim_out_ms:
                if self._loop_playback and trim_out_ms > trim_in_ms:
                    self._media_player.setPosition(trim_in_ms)
                else:
                    self._media_player.pause()
                    self._media_player.setPosition(trim_out_ms)
                return

        self.position_label.setText(_format_time(position / 1000.0))
        self.timeline_widget.set_position(position)

    def _on_duration_changed(self, duration: int) -> None:
        if duration <= 0:
            return
        self._duration_ms = duration
        self.timeline_widget.set_duration(duration)

        if self._session is not None:
            in_value, out_value = self.timeline_widget.trim_range()
            if out_value == 0:
                self.timeline_widget.set_trim_range(in_value, duration)
                self._timeline_trim_changed(in_value, duration)

    def _on_playback_state_changed(self, state: QMediaPlayer.PlaybackState) -> None:
        self._set_play_icon(state == QMediaPlayer.PlayingState)

    def _on_export_finished(self, output_path: Path) -> None:
        QMessageBox.information(self, "Export Complete", f"Saved to:\n{output_path}")

    def _on_export_failed(self, message: str) -> None:
        QMessageBox.critical(self, "Export Failed", message)
