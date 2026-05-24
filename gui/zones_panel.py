from PyQt6.QtWidgets import QGroupBox, QVBoxLayout, QTreeWidget, QTreeWidgetItem

class ZonesPanel(QGroupBox):
    def __init__(self):
        super().__init__("关键区域")
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout()

        self.tree = QTreeWidget()
        self.tree.setHeaderLabels(["区域", "范围", "强度"])
        self.tree.setColumnWidth(0, 140)
        self.tree.setColumnWidth(1, 110)
        self.tree.setColumnWidth(2, 60)
        self.tree.setRootIsDecorated(False)
        self.tree.setAlternatingRowColors(True)
        layout.addWidget(self.tree)

        self.setLayout(layout)
        self.setMinimumWidth(260)

    def update_zones(self, zones_result):
        self.tree.clear()
        for zone in zones_result.zones:
            item = QTreeWidgetItem()
            item.setText(0, zone.name)
            item.setText(1, f"{zone.lower:.2f} - {zone.upper:.2f}")
            item.setText(2, f"{zone.strength:.0%}")

            if zone.zone_type == "trading_range":
                item.setToolTip(1, zone.description)
            elif zone.zone_type in ("supply", "demand"):
                item.setToolTip(1, zone.description)

            self.tree.addTopLevelItem(item)
