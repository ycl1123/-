"""Modern alert log widget with color-coded severity rows."""
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel,
                             QScrollArea, QFrame)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont

from gui.styles import (BG_CARD, BG_DARK, BORDER, TEXT_PRIMARY, TEXT_SECONDARY,
                         TEXT_MUTED, ACCENT_BLUE, ACCENT_GREEN, ACCENT_ORANGE, ACCENT_RED)

SEVERITY_COLORS = {
    "info": ACCENT_BLUE,
    "signal": ACCENT_GREEN,
    "warning": ACCENT_ORANGE,
    "danger": ACCENT_RED,
}

SEVERITY_LABELS = {
    "info": "信息",
    "signal": "★ 信号",
    "warning": "▲ 提醒",
    "danger": "● 严重",
}


class AlertLogWidget(QWidget):
    def __init__(self, max_rows: int = 500):
        super().__init__()
        self.max_rows = max_rows
        self._rows = []
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Title
        title = QLabel("告警日志")
        title.setFont(QFont("Segoe UI", 13, QFont.Weight.Bold))
        title.setStyleSheet(f"color: {TEXT_PRIMARY}; padding: 0 0 8px 0; background: transparent;")
        layout.addWidget(title)

        # Scroll area
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet(f"""
            QScrollArea {{
                background-color: {BG_DARK};
                border: 1px solid {BORDER};
                border-radius: 10px;
            }}
        """)

        self._container = QWidget()
        self._container.setStyleSheet(f"background-color: {BG_DARK};")
        self._list_layout = QVBoxLayout(self._container)
        self._list_layout.setContentsMargins(6, 4, 6, 4)
        self._list_layout.setSpacing(2)
        self._list_layout.addStretch()

        scroll.setWidget(self._container)
        layout.addWidget(scroll)

    def add_alert(self, alert):
        color = SEVERITY_COLORS.get(alert.severity.value, ACCENT_BLUE)
        label_text = SEVERITY_LABELS.get(alert.severity.value, alert.severity.value)

        row = QFrame()
        row.setStyleSheet(f"""
            QFrame {{
                background-color: {BG_CARD};
                border-left: 3px solid {color};
                border-radius: 4px;
                padding: 2px 0;
            }}
        """)

        h = QHBoxLayout(row)
        h.setContentsMargins(10, 4, 10, 4)
        h.setSpacing(8)

        # Time
        time_lbl = QLabel(alert.time.strftime("%H:%M:%S"))
        time_lbl.setStyleSheet(f"color: {TEXT_MUTED}; font-size: 11px; font-family: Consolas; background: transparent;")
        time_lbl.setFixedWidth(65)
        h.addWidget(time_lbl)

        # Timeframe
        tf_lbl = QLabel(alert.timeframe)
        tf_lbl.setStyleSheet(f"color: {color}; font-size: 11px; font-weight: 600; background: transparent;")
        tf_lbl.setFixedWidth(30)
        tf_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        h.addWidget(tf_lbl)

        # Severity badge
        sev_lbl = QLabel(label_text)
        sev_lbl.setStyleSheet(f"""
            color: {color}; font-size: 11px; font-weight: 600;
            background: transparent;
        """)
        sev_lbl.setFixedWidth(55)
        h.addWidget(sev_lbl)

        # Content
        content_lbl = QLabel(alert.message)
        content_lbl.setStyleSheet(f"color: {TEXT_PRIMARY}; font-size: 12px; background: transparent;")
        content_lbl.setWordWrap(True)
        h.addWidget(content_lbl, 1)

        # Insert at top
        self._list_layout.insertWidget(self._list_layout.count() - 1, row)
        self._rows.append(row)

        # Trim old rows
        while len(self._rows) > self.max_rows:
            old = self._rows.pop(0)
            self._list_layout.removeWidget(old)
            old.deleteLater()
