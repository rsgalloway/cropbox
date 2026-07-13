from typing import Dict, Optional

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QDockWidget,
    QFormLayout,
    QGroupBox,
    QLabel,
    QLineEdit,
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
                "Crop",
                (
                    ("X", "crop_x"),
                    ("Y", "crop_y"),
                    ("Width", "crop_width"),
                    ("Height", "crop_height"),
                ),
            )
        )

        self.source_size_label = QLabel("Source: -", content)
        layout.addWidget(self.source_size_label)
        layout.addStretch(1)
        self.setWidget(content)
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

    def set_fields_enabled(self, enabled: bool) -> None:
        for field in self._fields.values():
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
