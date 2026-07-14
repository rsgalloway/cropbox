from typing import Dict, Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QDockWidget,
    QFormLayout,
    QGroupBox,
    QLabel,
    QLineEdit,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)


class InfoPanel(QDockWidget):
    valueSubmitted = Signal(str, str)

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__("Info", parent)
        self.setObjectName("infoPanel")
        self.setMinimumWidth(280)

        content = QWidget(self)
        layout = QVBoxLayout(content)
        layout.setContentsMargins(10, 10, 10, 10)

        self._fields: Dict[str, QLineEdit] = {}
        self._metadata_labels: Dict[str, QLabel] = {}
        layout.addWidget(
            self._create_group(
                "Playback",
                (
                    ("Current Time", "current_time"),
                    ("Current Frame", "current_frame"),
                    ("Playback FPS", "playback_fps"),
                ),
            )
        )
        layout.addWidget(
            self._create_group(
                "Trim",
                (
                    ("In Time", "trim_in_time"),
                    ("In Frame", "trim_in_frame"),
                    ("Out Time", "trim_out_time"),
                    ("Out Frame", "trim_out_frame"),
                ),
            )
        )
        layout.addWidget(
            self._create_group(
                "Timeline View",
                (
                    ("Start Time", "timeline_start_time"),
                    ("Start Frame", "timeline_start_frame"),
                    ("End Time", "timeline_end_time"),
                    ("End Frame", "timeline_end_frame"),
                ),
            )
        )
        layout.addWidget(
            self._create_group(
                "Crop",
                (
                    ("X", "crop_x"),
                    ("Y", "crop_y"),
                    ("Width", "crop_width"),
                    ("Height", "crop_height"),
                ),
            )
        )
        layout.addWidget(
            self._create_metadata_group(
                "Source",
                (
                    ("Type", "source_type"),
                    ("Container", "source_container"),
                    ("Video Codec", "source_video_codec"),
                    ("Audio Codec", "source_audio_codec"),
                    ("Duration", "source_duration"),
                    ("Frame Rate", "source_frame_rate"),
                ),
            )
        )

        self.source_size_label = QLabel("Source: -", content)
        layout.addWidget(self.source_size_label)
        layout.addStretch(1)

        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setFrameShape(QScrollArea.NoFrame)
        scroll.setWidget(content)
        self.setWidget(scroll)
        self.set_fields_enabled(False)

    def _create_group(self, title: str, rows) -> QGroupBox:
        group = QGroupBox(title, self)
        form = QFormLayout(group)
        for label, key in rows:
            field = QLineEdit(group)
            field.returnPressed.connect(
                lambda submitted_key=key, edit=field: self.valueSubmitted.emit(
                    submitted_key, edit.text()
                )
            )
            self._fields[key] = field
            form.addRow(label, field)
        return group

    def _create_metadata_group(self, title: str, rows) -> QGroupBox:
        group = QGroupBox(title, self)
        form = QFormLayout(group)
        for label, key in rows:
            value_label = QLabel("-", group)
            value_label.setWordWrap(True)
            value_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
            self._metadata_labels[key] = value_label
            form.addRow(label, value_label)
        return group

    def set_fields_enabled(self, enabled: bool) -> None:
        for field in self._fields.values():
            field.setEnabled(enabled)

    def set_field_enabled(self, key: str, enabled: bool) -> None:
        field = self._fields.get(key)
        if field is not None:
            field.setEnabled(enabled)

    def set_values(self, values: Dict[str, str], force: bool = False) -> None:
        for key, value in values.items():
            field = self._fields.get(key)
            if field is None or (field.hasFocus() and not force):
                continue
            field.setText(value)
            self.set_invalid(key, False)

    def crop_values(self) -> Dict[str, str]:
        return {
            key: self._fields[key].text().strip()
            for key in ("crop_x", "crop_y", "crop_width", "crop_height")
        }

    def set_invalid(self, key: str, invalid: bool) -> None:
        field = self._fields.get(key)
        if field is None:
            return
        field.setStyleSheet("border: 1px solid #d65c5c;" if invalid else "")

    def set_metadata(self, values: Dict[str, str]) -> None:
        for key, label in self._metadata_labels.items():
            label.setText(values.get(key, "-"))
