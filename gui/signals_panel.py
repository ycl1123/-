from PyQt6.QtWidgets import (QGroupBox, QVBoxLayout, QScrollArea, QWidget,
                             QLabel, QFrame, QSizePolicy)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont

from analysis.trade_signals import TradeSignal, SignalStrength, STRENGTH_COLORS
from gui.app import BULL_COLOR, BEAR_COLOR, TEXT_SECONDARY

DIR_MAP = {'L': '多', 'S': '空'}
DIR_COLOR = {'L': BULL_COLOR, 'S': BEAR_COLOR}


class SignalCard(QFrame):
    """Single trade signal card."""
    def __init__(self):
        super().__init__()
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setStyleSheet("SignalCard { background: #1E1E2E; border: 1px solid #333; "
                           "border-radius: 4px; padding: 4px; margin: 2px 0; }")
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout()
        layout.setContentsMargins(6, 4, 6, 4)
        layout.setSpacing(2)

        # Row 0: type + strength badge
        row0 = QVBoxLayout()  # placeholder, will be filled dynamically
        self.header_label = QLabel()
        self.header_label.setFont(QFont("", 10, QFont.Weight.Bold))
        row0.addWidget(self.header_label)

        # Row 1: entry / stop / target
        self.price_label = QLabel()
        self.price_label.setStyleSheet(f"color: {TEXT_SECONDARY}; font-size: 11px;")
        row0.addWidget(self.price_label)

        # Row 2: stop distance + confidence + reason
        self.info_label = QLabel()
        self.info_label.setStyleSheet(f"color: {TEXT_SECONDARY}; font-size: 10px;")
        self.info_label.setWordWrap(True)
        row0.addWidget(self.info_label)

        layout.addLayout(row0)
        self.setLayout(layout)

    def set_signal(self, sig: TradeSignal):
        strength_name = {SignalStrength.STRONG: "强信号", SignalStrength.MEDIUM: "中级",
                         SignalStrength.WEAK: "弱信号"}
        color = STRENGTH_COLORS[sig.strength]
        d_color = DIR_COLOR[sig.direction]
        d_cn = DIR_MAP[sig.direction]

        # Tactical layer badge
        tac_badge = ""
        if sig.tactical_layer:
            tac_colors = {"战略进攻": "#00E676", "战略防御": "#FFC107", "战略转移": "#EF5350"}
            tc = tac_colors.get(sig.tactical_layer, "#888")
            tac_badge = f" <span style='color:{tc}; font-size:9px;'>[{sig.tactical_layer}]</span>"

        # Resonance indicator
        res_str = ""
        if sig.resonance_count >= 4:
            res_str = f" <span style='color:#00E676; font-size:10px;'>★共振{sig.resonance_count}/5</span>"
        elif sig.resonance_count >= 3:
            res_str = f" <span style='color:#B2FF59; font-size:10px;'>共振{sig.resonance_count}/5</span>"
        elif sig.resonance_count >= 1:
            res_str = f" <span style='color:#FFC107; font-size:9px;'>共振{sig.resonance_count}/5</span>"

        self.header_label.setText(
            f"<span style='color:{d_color};'>{d_cn}</span> "
            f"{sig.signal_type.value} "
            f"<span style='color:{color}; font-size:9px;'>[{strength_name[sig.strength]}]</span>"
            f"{tac_badge}{res_str}"
        )

        self.price_label.setText(
            f"入场 <span style='color:{d_color};'>{sig.entry_price:.1f}</span>  |  "
            f"止损 <span style='color:#EF5350;'>{sig.stop_price:.1f}</span>  |  "
            f"止盈 <span style='color:{BULL_COLOR};'>{sig.target_price:.1f}</span>"
        )

        self.info_label.setText(
            f"止损距离: {sig.stop_distance:.1f}点 | "
            f"盈亏比: 1:{sig.risk_reward_ratio:.1f} | "
            f"置信度: {sig.confidence:.0%} | {sig.reason}"
        )


class TradingSignalsPanel(QGroupBox):
    """Panel showing active trading signals."""
    def __init__(self):
        super().__init__("交易信号")
        self._setup_ui()
        self._cards = []

    def _setup_ui(self):
        layout = QVBoxLayout()
        layout.setContentsMargins(2, 4, 2, 2)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        container = QWidget()
        self.card_layout = QVBoxLayout(container)
        self.card_layout.setContentsMargins(0, 0, 0, 0)
        self.card_layout.setSpacing(2)
        self.card_layout.addStretch()

        self.scroll.setWidget(container)
        layout.addWidget(self.scroll)

        self.no_signal_label = QLabel("暂无交易信号")
        self.no_signal_label.setStyleSheet(f"color: {TEXT_SECONDARY}; font-size: 10px;")
        self.no_signal_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.no_signal_label)

        self.setLayout(layout)
        self.setMinimumWidth(300)
        self.setMaximumHeight(350)

    def update_signals(self, signals: list[TradeSignal]):
        # Clear old cards
        for card in self._cards:
            self.card_layout.removeWidget(card)
            card.deleteLater()
        self._cards.clear()

        if not signals:
            self.no_signal_label.setVisible(True)
            return

        self.no_signal_label.setVisible(False)

        for sig in signals:
            card = SignalCard()
            card.set_signal(sig)
            self._cards.append(card)
            # Insert before stretch
            self.card_layout.insertWidget(self.card_layout.count() - 1, card)
