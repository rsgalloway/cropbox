import sys
from pathlib import Path
from typing import Optional

from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QApplication

from cropbox import __version__
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
    app.setApplicationVersion(__version__)
    app.setOrganizationName("Cropbox")
    app.setStyle("Fusion")
    _apply_dark_theme(app)
    initial_path = Path(initial_media).expanduser().resolve() if initial_media else None
    window = MainWindow(
        initial_media_path=initial_path,
        initial_trim=initial_trim,
        initial_crop=initial_crop,
    )
    window.show()
    return app.exec()


def _apply_dark_theme(app: QApplication) -> None:
    palette = QPalette()
    palette.setColor(QPalette.ColorRole.Window, QColor("#101519"))
    palette.setColor(QPalette.ColorRole.WindowText, QColor("#dbe2e8"))
    palette.setColor(QPalette.ColorRole.Base, QColor("#0d1216"))
    palette.setColor(QPalette.ColorRole.AlternateBase, QColor("#141b20"))
    palette.setColor(QPalette.ColorRole.ToolTipBase, QColor("#11161b"))
    palette.setColor(QPalette.ColorRole.ToolTipText, QColor("#f2f5f8"))
    palette.setColor(QPalette.ColorRole.Text, QColor("#dbe2e8"))
    palette.setColor(QPalette.ColorRole.Button, QColor("#161d23"))
    palette.setColor(QPalette.ColorRole.ButtonText, QColor("#edf2f7"))
    palette.setColor(QPalette.ColorRole.Highlight, QColor("#2a333b"))
    palette.setColor(QPalette.ColorRole.HighlightedText, QColor("#ffffff"))
    palette.setColor(QPalette.ColorRole.PlaceholderText, QColor("#75818d"))
    app.setPalette(palette)
    app.setStyleSheet(
        """
        QWidget {
            font-size: 12px;
        }
        QTreeView, QTableWidget, QLineEdit, QPushButton, QLabel, QListWidget {
            background-color: #1b232a;
            color: #dbe2e8;
        }
        QMenuBar {
            background-color: #0f1519;
            color: #d5dde4;
            padding: 1px 4px;
        }
        QMenuBar::item {
            background: transparent;
            padding: 4px 8px;
        }
        QMenuBar::item:selected {
            background-color: #1e272f;
        }
        QMenu {
            background-color: #151c22;
            color: #dbe2e8;
            border: 1px solid #26303a;
        }
        QMenu::item {
            padding: 6px 18px;
        }
        QMenu::item:selected {
            background-color: #27313a;
        }
        QMainWindow, QWidget#mainContent {
            background-color: #0f1418;
            color: #dbe2e8;
        }
        QLineEdit {
            background-color: #141b20;
            border: 1px solid #1f2830;
            border-radius: 3px;
            color: #dbe2e8;
        }
        QPushButton {
            background-color: #1a2127;
            border: 1px solid #25303a;
            border-radius: 3px;
            padding: 4px 9px;
            min-height: 24px;
        }
        QPushButton:disabled {
            color: #697581;
            background-color: #151b20;
        }
        QToolButton {
            background: transparent;
            border: 0;
            color: #83919e;
        }
        QToolButton:hover {
            color: #d6dde4;
            background-color: #1e262d;
        }
        QToolButton:checked {
            background-color: #263039;
            border-color: #34414d;
        }
        """
    )
