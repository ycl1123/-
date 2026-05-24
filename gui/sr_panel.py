from PyQt6.QtWidgets import QGroupBox, QVBoxLayout, QTreeWidget, QTreeWidgetItem
from PyQt6.QtCore import Qt
from gui.app import BULL_COLOR, BEAR_COLOR, NEUTRAL_COLOR

class SRPanel(QGroupBox):
    def __init__(self):
        super().__init__("支撑压力")
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout()

        self.tree = QTreeWidget()
        self.tree.setHeaderLabels(["级别", "价格", "强度"])
        self.tree.setColumnWidth(0, 120)
        self.tree.setColumnWidth(1, 80)
        self.tree.setColumnWidth(2, 50)
        self.tree.setRootIsDecorated(False)
        self.tree.setAlternatingRowColors(True)
        layout.addWidget(self.tree)

        self.setLayout(layout)
        self.setMinimumWidth(220)

    def update_sr(self, sr_result, current_price: float):
        self.tree.clear()
        items = []
        for level in sr_result.levels:
            item = QTreeWidgetItem()
            item.setText(0, level.label)
            item.setText(1, f"{level.price:.2f}")
            item.setText(2, f"{level.strength:.0%}")

            # Color based on type and position
            if level.level_type == "resistance":
                item.setForeground(1, Qt.GlobalColor(Qt.GlobalColor(0xEF5350)))  # red
            elif level.level_type == "support":
                item.setForeground(1, Qt.GlobalColor(Qt.GlobalColor(0x26A69A)))  # green
            else:
                item.setForeground(1, Qt.GlobalColor(Qt.GlobalColor(0x90A4AE)))

            # Bold for strong levels
            if level.strength >= 0.6:
                font = item.font(0)
                font.setBold(True)
                item.setFont(0, font)

            # Calculate distance from current price
            dist_pct = (level.price - current_price) / current_price * 100
            dist_text = f"{dist_pct:+.2f}%"
            item.setText(2, dist_text)

            items.append(item)

        self.tree.addTopLevelItems(items)
