from PyQt6.QtWidgets import QGroupBox, QVBoxLayout, QLabel, QFrame
from gui.app import BULL_COLOR, BEAR_COLOR, NEUTRAL_COLOR, TEXT_SECONDARY

BAR_TYPE_CN = {
    "STRONG_TREND": "强趋势K线",
    "REVERSAL": "反转K线",
    "OUTSIDE": "外包K线 (Outside Bar)",
    "INSIDE": "内包K线 (Inside Bar)",
    "BULLISH_PIN": "锤子线 (Bullish Pin)",
    "BEARISH_PIN": "流星线 (Bearish Pin)",
    "DOJI": "十字星 (Doji)",
    "NORMAL": "普通K线",
}

class SignalKPanel(QGroupBox):
    def __init__(self):
        super().__init__("当前K线信号")
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout()

        self.bar_time_label = QLabel("时间: --")
        layout.addWidget(self.bar_time_label)

        self.bar_type_label = QLabel("类型: --")
        self.bar_type_label.setStyleSheet("font-size: 14px; font-weight: bold;")
        layout.addWidget(self.bar_type_label)

        self.score_label = QLabel("评分: --")
        layout.addWidget(self.score_label)

        self.body_label = QLabel("实体比: --")
        layout.addWidget(self.body_label)

        self.close_pos_label = QLabel("收盘位: --")
        layout.addWidget(self.close_pos_label)

        self.wick_label = QLabel("影线: --")
        layout.addWidget(self.wick_label)

        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setStyleSheet("color: #555;")
        layout.addWidget(line)

        self.suggestion_label = QLabel("")
        self.suggestion_label.setWordWrap(True)
        self.suggestion_label.setStyleSheet(f"color: {TEXT_SECONDARY}; font-size: 11px;")
        layout.addWidget(self.suggestion_label)

        layout.addStretch()
        self.setLayout(layout)
        self.setMinimumWidth(180)

    def update_signal_k(self, signal_k_result, bar_time=None):
        if signal_k_result is None:
            return

        if bar_time:
            self.bar_time_label.setText(f"时间: {bar_time}")

        type_name = BAR_TYPE_CN.get(signal_k_result.bar_type.name, "未知")
        self.bar_type_label.setText(f"类型: {type_name}")

        score = signal_k_result.score
        if score > 0.3:
            color = BULL_COLOR
        elif score < -0.3:
            color = BEAR_COLOR
        else:
            color = NEUTRAL_COLOR
        self.score_label.setText(f"评分: {score:+.2f}")
        self.score_label.setStyleSheet(f"font-size: 14px; color: {color};")

        self.body_label.setText(f"实体比: {signal_k_result.body_ratio:.0%}")
        self.close_pos_label.setText(f"收盘位: {signal_k_result.close_position:.0%}")
        self.wick_label.setText(
            f"影线: 上{signal_k_result.upper_wick_ratio:.0%} / 下{signal_k_result.lower_wick_ratio:.0%}"
        )

        # Trading suggestion based on bar type and score
        bt = signal_k_result.bar_type
        if bt.name == "STRONG_TREND":
            direction = "做多" if signal_k_result.is_bullish else "做空"
            self.suggestion_label.setText(f"← 强力顺势K线，关注{ direction }机会")
        elif bt.name == "REVERSAL":
            direction = "做多" if signal_k_result.is_bullish else "做空"
            self.suggestion_label.setText(f"← 反转信号，等待下一根确认后{ direction }")
        elif bt.name in ("BULLISH_PIN", "BEARISH_PIN"):
            direction = "做多" if signal_k_result.is_bullish else "做空"
            self.suggestion_label.setText(f"← Pin Bar反转信号，关注{ direction }")
        elif bt.name == "DOJI":
            self.suggestion_label.setText("← 十字星，市场犹豫，等待方向选择")
        elif bt.name == "OUTSIDE":
            self.suggestion_label.setText("← 外包K线，多空分歧加大，等待确认")
        elif bt.name == "INSIDE":
            self.suggestion_label.setText("← 内包K线，市场蓄力，等待突破方向")
        else:
            self.suggestion_label.setText("")
