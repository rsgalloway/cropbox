# SPDX-License-Identifier: BSD-3-Clause

from typing import Optional, Tuple

from PySide6.QtCore import QSignalBlocker
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)


class ResizeDialog(QDialog):
    PRESETS = (
        ("Original size", "original"),
        ("50%", "percent:50"),
        ("75%", "percent:75"),
        ("100%", "percent:100"),
        ("150%", "percent:150"),
        ("200%", "percent:200"),
        ("Fit within 854 x 480 (480p)", "fit:854:480"),
        ("Fit within 1280 x 720 (720p)", "fit:1280:720"),
        ("Fit within 1920 x 1080 (1080p)", "fit:1920:1080"),
        ("Custom", "custom"),
    )

    def __init__(
        self,
        source_size: Tuple[int, int],
        current_size: Optional[Tuple[int, int]],
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Resize")
        self.setModal(True)
        self.resize(500, 260)

        self._source_size = source_size
        self._result: Optional[Tuple[int, int]] = None
        self._updating = False

        self.preset_combo = QComboBox(self)
        for label, value in self.PRESETS:
            self.preset_combo.addItem(label, value)

        self.width_spin = QSpinBox(self)
        self.width_spin.setRange(2, 16384)
        self.width_spin.setSingleStep(2)
        self.height_spin = QSpinBox(self)
        self.height_spin.setRange(2, 16384)
        self.height_spin.setSingleStep(2)
        dimensions = QHBoxLayout()
        dimensions.setContentsMargins(0, 0, 0, 0)
        dimensions.addWidget(self.width_spin)
        dimensions.addWidget(QLabel("x", self))
        dimensions.addWidget(self.height_spin)
        dimensions_widget = QWidget(self)
        dimensions_widget.setLayout(dimensions)

        self.preserve_checkbox = QCheckBox("Preserve source aspect ratio", self)
        self.preserve_checkbox.setChecked(True)
        self.summary_label = QLabel(self)

        form = QFormLayout()
        form.addRow("Preset", self.preset_combo)
        form.addRow("Dimensions", dimensions_widget)
        form.addRow("", self.preserve_checkbox)
        form.addRow("Result", self.summary_label)

        hint = QLabel(
            "Resize is applied after crop and before rotation. Original size disables "
            "the edit-stage resize.",
            self,
        )
        hint.setWordWrap(True)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel, self)
        buttons.accepted.connect(self._accept)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(hint)
        layout.addStretch(1)
        layout.addWidget(buttons)

        self.preset_combo.currentIndexChanged.connect(self._preset_changed)
        self.width_spin.valueChanged.connect(self._width_changed)
        self.height_spin.valueChanged.connect(self._height_changed)
        self.preserve_checkbox.toggled.connect(self._preserve_changed)

        if current_size is None:
            self.preset_combo.setCurrentIndex(0)
            self._set_dimensions(*source_size)
        else:
            self.preset_combo.setCurrentIndex(self.preset_combo.findData("custom"))
            self._set_dimensions(*current_size)
        self._preset_changed()

    def result_size(self) -> Optional[Tuple[int, int]]:
        return self._result

    @staticmethod
    def _fit_size(source: Tuple[int, int], bounds: Tuple[int, int]) -> Tuple[int, int]:
        scale = min(bounds[0] / float(source[0]), bounds[1] / float(source[1]))
        width = max(2, int(round(source[0] * scale)))
        height = max(2, int(round(source[1] * scale)))
        return width - (width % 2), height - (height % 2)

    def _set_dimensions(self, width: int, height: int) -> None:
        self._updating = True
        self.width_spin.setValue(max(2, width))
        self.height_spin.setValue(max(2, height))
        self._updating = False
        self._update_summary()

    def _preset_changed(self) -> None:
        preset = str(self.preset_combo.currentData())
        is_custom = preset == "custom"
        self.width_spin.setEnabled(is_custom)
        self.height_spin.setEnabled(is_custom)
        self.preserve_checkbox.setEnabled(is_custom)

        if preset == "original":
            self._set_dimensions(*self._source_size)
        elif preset.startswith("percent:"):
            percent = float(preset.split(":", 1)[1]) / 100.0
            self._set_dimensions(
                int(round(self._source_size[0] * percent)),
                int(round(self._source_size[1] * percent)),
            )
        elif preset.startswith("fit:"):
            _, width, height = preset.split(":")
            self._set_dimensions(*self._fit_size(self._source_size, (int(width), int(height))))
        else:
            self._update_summary()

    def _set_custom_preset(self) -> None:
        custom_index = self.preset_combo.findData("custom")
        if self.preset_combo.currentIndex() != custom_index:
            with QSignalBlocker(self.preset_combo):
                self.preset_combo.setCurrentIndex(custom_index)
            self.width_spin.setEnabled(True)
            self.height_spin.setEnabled(True)
            self.preserve_checkbox.setEnabled(True)

    def _width_changed(self, width: int) -> None:
        if self._updating:
            return
        self._set_custom_preset()
        if self.preserve_checkbox.isChecked():
            height = int(round(width * self._source_size[1] / self._source_size[0]))
            with QSignalBlocker(self.height_spin):
                self.height_spin.setValue(max(2, height))
        self._update_summary()

    def _height_changed(self, height: int) -> None:
        if self._updating:
            return
        self._set_custom_preset()
        if self.preserve_checkbox.isChecked():
            width = int(round(height * self._source_size[0] / self._source_size[1]))
            with QSignalBlocker(self.width_spin):
                self.width_spin.setValue(max(2, width))
        self._update_summary()

    def _preserve_changed(self, preserve: bool) -> None:
        if preserve:
            self._width_changed(self.width_spin.value())
        self._update_summary()

    def _update_summary(self) -> None:
        self.summary_label.setText(f"{self.width_spin.value()} x {self.height_spin.value()} pixels")

    def _accept(self) -> None:
        if self.preset_combo.currentData() == "original":
            self._result = None
        else:
            width = self.width_spin.value()
            height = self.height_spin.value()
            self._result = (width - (width % 2), height - (height % 2))
        self.accept()
