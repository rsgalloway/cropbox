from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Optional, Tuple

from PySide6.QtCore import QSettings
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)


@dataclass(frozen=True)
class ExportOptions:
    output_path: Path
    output_size: Optional[Tuple[int, int]]
    crf: int
    gif_colors: int
    include_audio: bool


class ExportDialog(QDialog):
    FORMAT_SUFFIXES = {"MP4": ".mp4", "MOV": ".mov", "GIF": ".gif"}
    SIZE_PRESETS: Dict[str, Optional[Tuple[int, int]]] = {
        "original": None,
        "2160p": (3840, 2160),
        "1080p": (1920, 1080),
        "720p": (1280, 720),
        "480p": (854, 480),
        "custom": None,
    }
    QUALITY_PRESETS = {
        "high": (18, 256),
        "balanced": (23, 128),
        "small": (28, 64),
    }

    def __init__(
        self,
        source_path: Path,
        source_size: Tuple[int, int],
        has_audio: bool,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Export")
        self.setModal(True)
        self.resize(580, 390)

        self._source_path = source_path
        self._source_size = source_size
        self._has_audio = has_audio
        self._settings = QSettings()
        self._options: Optional[ExportOptions] = None

        self.path_edit = QLineEdit(self)
        browse_button = QPushButton("Browse...", self)
        browse_button.clicked.connect(self._browse)
        path_row = QHBoxLayout()
        path_row.addWidget(self.path_edit, stretch=1)
        path_row.addWidget(browse_button)

        self.format_combo = QComboBox(self)
        for name in self.FORMAT_SUFFIXES:
            self.format_combo.addItem(name, name)

        self.size_combo = QComboBox(self)
        self.size_combo.addItem("Original", "original")
        self.size_combo.addItem("Fit within 3840 x 2160 (2160p)", "2160p")
        self.size_combo.addItem("Fit within 1920 x 1080 (1080p)", "1080p")
        self.size_combo.addItem("Fit within 1280 x 720 (720p)", "720p")
        self.size_combo.addItem("Fit within 854 x 480 (480p)", "480p")
        self.size_combo.addItem("Custom bounds", "custom")

        self.custom_width = QSpinBox(self)
        self.custom_width.setRange(2, 16384)
        self.custom_height = QSpinBox(self)
        self.custom_height.setRange(2, 16384)
        custom_row = QHBoxLayout()
        custom_row.setContentsMargins(0, 0, 0, 0)
        custom_row.addWidget(self.custom_width)
        custom_row.addWidget(QLabel("x", self))
        custom_row.addWidget(self.custom_height)
        custom_widget = QWidget(self)
        custom_widget.setLayout(custom_row)
        self.custom_widget = custom_widget

        self.quality_combo = QComboBox(self)
        self.quality_combo.addItem("High", "high")
        self.quality_combo.addItem("Balanced", "balanced")
        self.quality_combo.addItem("Smaller file", "small")

        self.audio_checkbox = QCheckBox("Include source audio", self)
        self.output_dimensions_label = QLabel(self)
        self.output_dimensions_label.setWordWrap(True)

        form = QFormLayout()
        form.addRow("Destination", path_row)
        form.addRow("Format", self.format_combo)
        form.addRow("Size", self.size_combo)
        form.addRow("Custom bounds", self.custom_widget)
        form.addRow("Quality", self.quality_combo)
        form.addRow("Audio", self.audio_checkbox)
        form.addRow("Result", self.output_dimensions_label)

        hint = QLabel(
            "Size presets fit within the selected bounds and preserve the cropped aspect ratio.",
            self,
        )
        hint.setWordWrap(True)

        buttons = QDialogButtonBox(
            QDialogButtonBox.Save | QDialogButtonBox.Cancel,
            parent=self,
        )
        buttons.accepted.connect(self._accept)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(hint)
        layout.addStretch(1)
        layout.addWidget(buttons)

        self.format_combo.currentIndexChanged.connect(self._format_changed)
        self.size_combo.currentIndexChanged.connect(self._size_changed)
        self.custom_width.valueChanged.connect(self._update_dimensions)
        self.custom_height.valueChanged.connect(self._update_dimensions)
        self._restore_settings()
        self._format_changed()
        self._size_changed()

    def options(self) -> Optional[ExportOptions]:
        return self._options

    def _restore_settings(self) -> None:
        format_name = str(self._settings.value("export/format", "MP4"))
        size_name = str(self._settings.value("export/size", "original"))
        quality_name = str(self._settings.value("export/quality", "balanced"))
        include_audio = self._settings.value("export/include_audio", True, type=bool)
        last_directory = Path(
            str(self._settings.value("export/last_directory", str(self._source_path.parent)))
        )

        self._set_combo_value(self.format_combo, format_name)
        self._set_combo_value(self.size_combo, size_name)
        self._set_combo_value(self.quality_combo, quality_name)
        self.custom_width.setValue(
            int(self._settings.value("export/custom_width", self._source_size[0]))
        )
        self.custom_height.setValue(
            int(self._settings.value("export/custom_height", self._source_size[1]))
        )
        self.audio_checkbox.setChecked(bool(include_audio) and self._has_audio)
        suffix = self.FORMAT_SUFFIXES.get(format_name, ".mp4")
        self.path_edit.setText(str(last_directory / f"{self._source_path.stem}_export{suffix}"))

    def _set_combo_value(self, combo: QComboBox, value: str) -> None:
        index = combo.findData(value)
        combo.setCurrentIndex(max(index, 0))

    def _format_changed(self) -> None:
        format_name = str(self.format_combo.currentData())
        suffix = self.FORMAT_SUFFIXES[format_name]
        current_path = Path(self.path_edit.text()) if self.path_edit.text() else self._source_path
        self.path_edit.setText(str(current_path.with_suffix(suffix)))
        audio_enabled = self._has_audio and format_name != "GIF"
        self.audio_checkbox.setEnabled(audio_enabled)
        if not audio_enabled:
            self.audio_checkbox.setChecked(False)
        self._update_dimensions()

    def _size_changed(self) -> None:
        is_custom = self.size_combo.currentData() == "custom"
        self.custom_widget.setEnabled(is_custom)
        self._update_dimensions()

    def _selected_output_size(self) -> Optional[Tuple[int, int]]:
        preset_name = str(self.size_combo.currentData())
        if preset_name == "original":
            return None
        bounds = (
            (self.custom_width.value(), self.custom_height.value())
            if preset_name == "custom"
            else self.SIZE_PRESETS[preset_name]
        )
        if bounds is None:
            return None
        return self._fit_size(self._source_size, bounds)

    @staticmethod
    def _fit_size(source: Tuple[int, int], bounds: Tuple[int, int]) -> Tuple[int, int]:
        scale = min(bounds[0] / float(source[0]), bounds[1] / float(source[1]))
        width = max(2, int(round(source[0] * scale)))
        height = max(2, int(round(source[1] * scale)))
        width -= width % 2
        height -= height % 2
        return max(2, width), max(2, height)

    def _update_dimensions(self) -> None:
        output_size = self._selected_output_size() or self._source_size
        self.output_dimensions_label.setText(
            f"{output_size[0]} x {output_size[1]} from crop "
            f"{self._source_size[0]} x {self._source_size[1]}"
        )

    def _browse(self) -> None:
        format_name = str(self.format_combo.currentData())
        suffix = self.FORMAT_SUFFIXES[format_name]
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Export Media",
            self.path_edit.text(),
            f"{format_name} Files (*{suffix})",
        )
        if path:
            self.path_edit.setText(str(Path(path).with_suffix(suffix)))

    def _accept(self) -> None:
        path_text = self.path_edit.text().strip()
        if not path_text:
            QMessageBox.warning(self, "Missing Destination", "Choose an export destination.")
            return

        format_name = str(self.format_combo.currentData())
        output_path = Path(path_text).expanduser().with_suffix(self.FORMAT_SUFFIXES[format_name])
        if not output_path.parent.exists():
            QMessageBox.warning(
                self,
                "Invalid Destination",
                f"The output directory does not exist:\n{output_path.parent}",
            )
            return
        if output_path.exists():
            answer = QMessageBox.question(
                self,
                "Replace Existing File?",
                f"Replace the existing file?\n{output_path}",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No,
            )
            if answer != QMessageBox.Yes:
                return

        quality_name = str(self.quality_combo.currentData())
        crf, gif_colors = self.QUALITY_PRESETS[quality_name]
        include_audio = self.audio_checkbox.isEnabled() and self.audio_checkbox.isChecked()
        self._options = ExportOptions(
            output_path=output_path,
            output_size=self._selected_output_size(),
            crf=crf,
            gif_colors=gif_colors,
            include_audio=include_audio,
        )

        self._settings.setValue("export/format", format_name)
        self._settings.setValue("export/size", self.size_combo.currentData())
        self._settings.setValue("export/quality", quality_name)
        self._settings.setValue("export/include_audio", include_audio)
        self._settings.setValue("export/last_directory", str(output_path.parent))
        self._settings.setValue("export/custom_width", self.custom_width.value())
        self._settings.setValue("export/custom_height", self.custom_height.value())
        self.accept()
