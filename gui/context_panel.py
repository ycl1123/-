from PyQt6.QtWidgets import QGroupBox, QVBoxLayout, QLabel, QFrame
from PyQt6.QtCore import Qt
from gui.app import BULL_COLOR, BEAR_COLOR, NEUTRAL_COLOR, TEXT_SECONDARY

class MarketContextPanel(QGroupBox):
    def __init__(self):
        super().__init__("行情背景")
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout()

        self.always_in_label = QLabel("Always In: --")
        self.always_in_label.setStyleSheet(f"font-size: 16px; font-weight: bold;")
        layout.addWidget(self.always_in_label)

        self.confidence_label = QLabel("置信度: --")
        layout.addWidget(self.confidence_label)

        self.state_label = QLabel("市场状态: --")
        layout.addWidget(self.state_label)

        self.ema_label = QLabel("EMA斜率: --")
        layout.addWidget(self.ema_label)

        self.overlap_label = QLabel("K线重叠率: --")
        layout.addWidget(self.overlap_label)

        self.trend_bar_label = QLabel("顺势K占比: --")
        layout.addWidget(self.trend_bar_label)

        # Separator
        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setStyleSheet("color: #555;")
        layout.addWidget(line)

        self.tip_label = QLabel("")
        self.tip_label.setWordWrap(True)
        self.tip_label.setStyleSheet(f"color: {TEXT_SECONDARY}; font-size: 11px;")
        layout.addWidget(self.tip_label)

        layout.addStretch()
        self.setLayout(layout)
        self.setMinimumWidth(180)

    def update_context(self, context_result):
        ai = context_result.always_in
        direction = ai.direction

        if direction == "LONG":
            color = BULL_COLOR
            arrow = "▲ LONG"
            tip = "顺势做多 | 关注回调买入"
        elif direction == "SHORT":
            color = BEAR_COLOR
            arrow = "▼ SHORT"
            tip = "顺势做空 | 关注反弹卖出"
        else:
            color = NEUTRAL_COLOR
            arrow = "■ NEUTRAL"
            tip = "方向不明 | 高抛低吸或观望"

        self.always_in_label.setText(f"Always In: {arrow}")
        self.always_in_label.setStyleSheet(f"font-size: 16px; font-weight: bold; color: {color};")
        self.confidence_label.setText(f"置信度: {ai.confidence:.2f}")
        self.state_label.setText(f"市场状态: {_state_cn(context_result.state)}")
        self.ema_label.setText(f"EMA斜率: {ai.ema_slope:+.3f}")
        self.overlap_label.setText(f"K线重叠率: {context_result.overlap_ratio:.1%}")
        self.trend_bar_label.setText(f"顺势K占比: {context_result.trend_bar_ratio:.1%}")

        # V5: Contradiction info
        if context_result.contradiction:
            ct = context_result.contradiction
            self.tip_label.setText(
                f"{tip}\n"
                f"[矛盾] {ct.type.value} | 主导:{ct.dominant_side} | "
                f"转化风险:{ct.transformation_risk.value}\n"
                f"[内因] K体衰减:{ct.internal.bar_strength_decay:.0%} "
                f"回调深:{ct.internal.pullback_deepening:.0%} "
                f"连反:{ct.internal.consecutive_opposite}根\n"
                f"[外因] S/R:{'是' if ct.external.near_major_sr else '否'} "
                f"EMA:{'是' if ct.external.near_ema else '否'} "
                f"共振区:{ct.external.zone_confluence}个\n"
                f"[状态转换] {context_result.state_transition_risk} "
                f"({context_result.transformation_conditions_met}/8)"
            )
        else:
            self.tip_label.setText(tip)

def _state_cn(state: str) -> str:
    return {
        "STRONG_TREND": "强趋势",
        "WEAK_TREND": "弱趋势",
        "CHANNEL": "通道",
        "TRADING_RANGE": "震荡区间",
    }.get(state, state)
