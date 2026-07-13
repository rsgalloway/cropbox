import sys
from pathlib import Path
from typing import Optional

from PySide6.QtWidgets import QApplication

from cropbox.logging_utils import configure_logging
from cropbox.widgets.main_window import MainWindow


def main(initial_media: Optional[str] = None) -> int:
    configure_logging()
    app = QApplication(sys.argv)
    app.setApplicationName("Cropbox")
    app.setOrganizationName("Cropbox")
    initial_path = Path(initial_media).expanduser().resolve() if initial_media else None
    window = MainWindow(initial_media_path=initial_path)
    window.show()
    return app.exec()
