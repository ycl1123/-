"""Application factory with modern dark theme."""
from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import QPalette, QColor
from PyQt6.QtCore import Qt
from gui.styles import GLOBAL_STYLESHEET


def create_app() -> QApplication:
    app = QApplication([])
    app.setStyle("Fusion")

    p = QPalette()
    p.setColor(QPalette.ColorRole.Window, QColor(13, 17, 23))
    p.setColor(QPalette.ColorRole.WindowText, QColor(230, 237, 243))
    p.setColor(QPalette.ColorRole.Base, QColor(22, 27, 34))
    p.setColor(QPalette.ColorRole.AlternateBase, QColor(28, 35, 51))
    p.setColor(QPalette.ColorRole.Text, QColor(230, 237, 243))
    p.setColor(QPalette.ColorRole.Button, QColor(22, 27, 34))
    p.setColor(QPalette.ColorRole.ButtonText, QColor(230, 237, 243))
    p.setColor(QPalette.ColorRole.Highlight, QColor(31, 111, 235))
    p.setColor(QPalette.ColorRole.HighlightedText, QColor(255, 255, 255))
    p.setColor(QPalette.ColorRole.BrightText, QColor(248, 81, 73))
    app.setPalette(p)

    app.setStyleSheet(GLOBAL_STYLESHEET)
    return app


# Legacy color constants
BULL_COLOR = "#26A69A"
BEAR_COLOR = "#EF5350"
NEUTRAL_COLOR = "#90A4AE"
