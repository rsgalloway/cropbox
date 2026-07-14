import re
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
    image_sequence_padding: Optional[int]
    source_is_still_image: bool


class ExportDialog(QDialog):
    FORMAT_SUFFIXES = {
        "MP4": ".mp4",
        "MOV": ".mov",
        "GIF": ".gif",
        "PNG Sequence": ".png",
        "PNG": ".png",
    }
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
        source_is_still_image: bool,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Export")
        self.setModal(True)
        self.resize(580, 390)

        self._source_path = source_path
        self._source_size = source_size
        self._has_audio = has_audio
        self._source_is_still_image = source_is_still_image
        self._settings = QSettings()
        self._options: Optional[ExportOptions] = None

        self.path_edit = QLineEdit(self)
        browse_button = QPushButton("Browse...", self)
        browse_button.clicked.connect(self._browse)
        path_row = QHBoxLayout()
        path_row.addWidget(self.path_edit, stretch=1)
        path_row.addWidget(browse_button)

        self.format_combo = QComboBox(self)
        if self._source_is_still_image:
            self.format_combo.addItem("PNG", "PNG")
        else:
            for name in ("MP4", "MOV", "GIF", "PNG Sequence"):
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
        self.sequence_padding = QSpinBox(self)
        self.sequence_padding.setRange(1, 12)
        self.sequence_padding.setValue(8)
        self.output_dimensions_label = QLabel(self)
        self.output_dimensions_label.setWordWrap(True)

        form = QFormLayout()
        form.addRow("Destination", path_row)
        form.addRow("Format", self.format_combo)
        form.addRow("Size", self.size_combo)
        form.addRow("Custom bounds", self.custom_widget)
        form.addRow("Quality", self.quality_combo)
        form.addRow("Audio", self.audio_checkbox)
        form.addRow("Frame Padding", self.sequence_padding)
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
        self.sequence_padding.valueChanged.connect(self._sequence_padding_changed)
        self._restore_settings()
        self._format_changed()
        self._size_changed()

    def options(self) -> Optional[ExportOptions]:
        return self._options

    def _restore_settings(self) -> None:
        default_format = "PNG" if self._source_is_still_image else "MP4"
        format_name = str(self._settings.value("export/format", default_format))
        size_name = str(self._settings.value("export/size", "original"))
        quality_name = str(self._settings.value("export/quality", "balanced"))
        sequence_padding = int(self._settings.value("export/png_padding", 8))
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
        self.sequence_padding.setValue(sequence_padding)
        self.audio_checkbox.setChecked(self._has_audio)
        self.path_edit.setText(
            self._default_output_path(last_directory, str(self.format_combo.currentData()))
        )

    def _set_combo_value(self, combo: QComboBox, value: str) -> None:
        index = combo.findData(value)
        combo.setCurrentIndex(max(index, 0))

    def _format_changed(self) -> None:
        format_name = str(self.format_combo.currentData())
        if not self.path_edit.text():
            current_directory = self._source_path.parent
        else:
            current_directory = Path(self.path_edit.text()).expanduser().parent
        self.path_edit.setText(self._default_output_path(current_directory, format_name))
        audio_enabled = self._has_audio and format_name not in {"GIF", "PNG Sequence", "PNG"}
        self.audio_checkbox.setEnabled(audio_enabled)
        self.audio_checkbox.setChecked(audio_enabled)
        self.sequence_padding.setEnabled(format_name == "PNG Sequence")
        self.quality_combo.setEnabled(format_name != "PNG")
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
        format_name = str(self.format_combo.currentData())
        result_text = (
            f"{output_size[0]} x {output_size[1]} from crop "
            f"{self._source_size[0]} x {self._source_size[1]}"
        )
        if format_name == "PNG Sequence":
            result_text += f" | frame files use %0{self.sequence_padding.value()}d padding"
        self.output_dimensions_label.setText(result_text)

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
            output_path = Path(path).with_suffix(suffix)
            if format_name == "PNG Sequence":
                self.path_edit.setText(
                    self._sequence_path_for_padding(
                        output_path.parent, self.sequence_padding.value()
                    )
                )
            else:
                self.path_edit.setText(str(output_path))

    def _default_output_path(self, directory: Path, format_name: str) -> str:
        if format_name == "PNG Sequence":
            return self._sequence_path_for_padding(directory, self.sequence_padding.value())
        suffix = self.FORMAT_SUFFIXES.get(format_name, ".mp4")
        return str(directory / f"{self._source_path.stem}_export{suffix}")

    def _sequence_path_for_padding(self, directory: Path, padding: int) -> str:
        return str(directory / f"{self._source_path.stem}_export.%0{padding}d.png")

    def _sequence_padding_changed(self) -> None:
        if str(self.format_combo.currentData()) != "PNG Sequence":
            self._update_dimensions()
            return
        text = self.path_edit.text().strip()
        if text:
            updated = re.sub(r"%0\d+d", f"%0{self.sequence_padding.value()}d", text)
            if updated == text and text.endswith(".png"):
                updated = str(Path(text).with_suffix(""))
                updated += f".%0{self.sequence_padding.value()}d.png"
            self.path_edit.setText(updated)
        self._update_dimensions()

    def _accept(self) -> None:
        path_text = self.path_edit.text().strip()
        if not path_text:
            QMessageBox.warning(self, "Missing Destination", "Choose an export destination.")
            return

        format_name = str(self.format_combo.currentData())
        output_path = Path(path_text).expanduser()
        if format_name == "PNG Sequence":
            if "%" not in output_path.name:
                output_path = output_path.with_suffix("")
                output_path = output_path.parent / (
                    output_path.name + f".%0{self.sequence_padding.value()}d.png"
                )
        else:
            output_path = output_path.with_suffix(self.FORMAT_SUFFIXES[format_name])
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
            image_sequence_padding=(
                self.sequence_padding.value() if format_name == "PNG Sequence" else None
            ),
            source_is_still_image=self._source_is_still_image,
        )

        self._settings.setValue("export/format", format_name)
        self._settings.setValue("export/size", self.size_combo.currentData())
        self._settings.setValue("export/quality", quality_name)
        self._settings.setValue("export/include_audio", include_audio)
        self._settings.setValue("export/png_padding", self.sequence_padding.value())
        self._settings.setValue("export/last_directory", str(output_path.parent))
        self._settings.setValue("export/custom_width", self.custom_width.value())
        self._settings.setValue("export/custom_height", self.custom_height.value())
        self.accept()
