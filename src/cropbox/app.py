import sys
from pathlib import Path
from typing import Optional

from PySide6.QtWidgets import QApplication

from cropbox.logging_utils import configure_logging
from cropbox.models.crop_rect import CropRect
from cropbox.models.trim_range import TrimRange
from cropbox.widgets.main_window import MainWindow


def main(
    initial_media: Optional[str] = None,
    initial_trim: Optional[TrimRange] = None,
    initial_crop: Optional[CropRect] = None,
) -> int:
    configure_logging()
    app = QApplication(sys.argv)
    app.setApplicationName("Cropbox")
    app.setOrganizationName("Cropbox")
    initial_path = Path(initial_media).expanduser().resolve() if initial_media else None
    window = MainWindow(
        initial_media_path=initial_path,
        initial_trim=initial_trim,
        initial_crop=initial_crop,
    )
    window.show()
    return app.exec()
