"""Modern signal display panels for Brooks Signals."""
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel,
                             QFrame, QScrollArea, QSizePolicy, QPushButton)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont

from gui.styles import (BG_CARD, BORDER, TEXT_PRIMARY, TEXT_SECONDARY,
                         TEXT_MUTED, ACCENT_GREEN, ACCENT_RED, ACCENT_BLUE,
                         ACCENT_YELLOW, ACCENT_TEAL, BULL, BEAR)

# ─────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────

def _card(title: str, accent: str = ACCENT_BLUE) -> tuple[QFrame, QVBoxLayout]:
    """Create a card-style frame with titled header."""
    frame = QFrame()
    frame.setObjectName("card")
    frame.setStyleSheet(f"""
        QFrame#card {{
            background-color: {BG_CARD};
            border: 1px solid {BORDER};
            border-radius: 10px;
        }}
    """)
    layout = QVBoxLayout(frame)
    layout.setContentsMargins(14, 12, 14, 12)
    layout.setSpacing(8)

    title_lbl = QLabel(title)
    title_lbl.setStyleSheet(f"""
        font-size: 13px; font-weight: 700; color: {accent};
        padding-bottom: 8px; border-bottom: 1px solid {BORDER};
    """)
    layout.addWidget(title_lbl)
    return frame, layout


def _metric_row(label: str, value: str, value_color: str = TEXT_PRIMARY) -> QWidget:
    """A single metric row: label on left, value on right."""
    row = QWidget()
    row.setStyleSheet("background: transparent;")
    h = QHBoxLayout(row)
    h.setContentsMargins(0, 2, 0, 2)
    h.setSpacing(8)

    lbl = QLabel(label)
    lbl.setStyleSheet(f"font-size: 12px; color: {TEXT_SECONDARY}; background: transparent;")
    h.addWidget(lbl)
    h.addStretch()

    val = QLabel(str(value))
    val.setStyleSheet(f"font-size: 12px; color: {value_color}; font-weight: 600; background: transparent;")
    h.addWidget(val)
    return row


def _pill(text: str, color: str, bg_alpha: str = "1a") -> QLabel:
    """A small colored pill/badge."""
    pill = QLabel(text)
    pill.setStyleSheet(f"""
        background-color: {color}22;
        color: {color};
        border: 1px solid {color}44;
        border-radius: 10px;
        padding: 3px 10px;
        font-size: 11px;
        font-weight: 600;
    """)
    return pill


# ─────────────────────────────────────────────
# Market Context Panel
# ─────────────────────────────────────────────

class ContextPanel(QWidget):
    def __init__(self):
        super().__init__()
        self._setup()

    def _setup(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self._frame, inner = _card("行情背景", ACCENT_TEAL)

        # Always In row
        ai_row = QWidget()
        ai_row.setStyleSheet("background: transparent;")
        ai_h = QHBoxLayout(ai_row)
        ai_h.setContentsMargins(0, 4, 0, 4)

        self._ai_label = QLabel("--")
        self._ai_label.setStyleSheet(f"font-size: 22px; font-weight: 800; background: transparent;")
        ai_h.addWidget(self._ai_label)
        ai_h.addStretch()

        self._state_pill = _pill("--", ACCENT_BLUE)
        ai_h.addWidget(self._state_pill)
        inner.addWidget(ai_row)

        # Metrics
        self._confidence = _metric_row("置信度", "--")
        self._ema_slope = _metric_row("EMA斜率", "--")
        self._overlap = _metric_row("重叠率", "--")
        self._trend_ratio = _metric_row("趋势K线比", "--")

        inner.addWidget(self._confidence)
        inner.addWidget(self._ema_slope)
        inner.addWidget(self._overlap)
        inner.addWidget(self._trend_ratio)

        inner.addStretch()
        layout.addWidget(self._frame)

    def update_context(self, ctx):
        direction = ctx.always_in.direction
        if direction == "LONG":
            self._ai_label.setText("LONG ▲")
            self._ai_label.setStyleSheet(f"font-size: 22px; font-weight: 800; color: {BULL}; background: transparent;")
        elif direction == "SHORT":
            self._ai_label.setText("SHORT ▼")
            self._ai_label.setStyleSheet(f"font-size: 22px; font-weight: 800; color: {BEAR}; background: transparent;")
        else:
            self._ai_label.setText("NEUTRAL")
            self._ai_label.setStyleSheet(f"font-size: 22px; font-weight: 800; color: {TEXT_MUTED}; background: transparent;")

        state_color = { "STRONG_TREND": ACCENT_GREEN, "WEAK_TREND": ACCENT_YELLOW,
                       "CHANNEL": ACCENT_BLUE, "TRADING_RANGE": ACCENT_BLUE }
        self._state_pill.setText(ctx.state)
        self._state_pill.setStyleSheet(f"""
            background-color: {state_color.get(ctx.state, ACCENT_BLUE)}22;
            color: {state_color.get(ctx.state, ACCENT_BLUE)};
            border: 1px solid {state_color.get(ctx.state, ACCENT_BLUE)}44;
            border-radius: 10px; padding: 3px 10px;
            font-size: 11px; font-weight: 600;
        """)

        self._update_metric(self._confidence, "置信度", f"{ctx.always_in.confidence:.0%}")
        self._update_metric(self._ema_slope, "EMA斜率", f"{ctx.always_in.ema_slope:+.3f}")
        self._update_metric(self._overlap, "重叠率", f"{ctx.overlap_ratio:.3f}")
        self._update_metric(self._trend_ratio, "趋势K线比", f"{ctx.trend_bar_ratio:.0%}")

    def _update_metric(self, widget, label, value):
        lbl = widget.findChildren(QLabel)[0] if widget.findChildren(QLabel) else None
        val = widget.findChildren(QLabel)[1] if widget.findChildren(QLabel) and len(widget.findChildren(QLabel)) > 1 else None
        if val:
            val.setText(str(value))


# ─────────────────────────────────────────────
# Signal K Panel
# ─────────────────────────────────────────────

class SignalKPanel(QWidget):
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self._frame, inner = _card("信号K线", ACCENT_YELLOW)

        self._type_label = QLabel("--")
        self._type_label.setStyleSheet(f"font-size: 18px; font-weight: 700; background: transparent;")
        inner.addWidget(self._type_label)

        self._score_label = QLabel("--")
        self._score_label.setStyleSheet(f"font-size: 26px; font-weight: 800; background: transparent;")
        inner.addWidget(self._score_label)

        inner.addSpacing(4)

        self._body_ratio = _metric_row("实体比", "--")
        self._close_pos = _metric_row("收盘位置", "--")
        self._upper_wick = _metric_row("上影线", "--")
        self._lower_wick = _metric_row("下影线", "--")
        self._time_label = _metric_row("时间", "--")

        inner.addWidget(self._body_ratio)
        inner.addWidget(self._close_pos)
        inner.addWidget(self._upper_wick)
        inner.addWidget(self._lower_wick)
        inner.addWidget(self._time_label)
        inner.addStretch()

        layout.addWidget(self._frame)

    def update_signal_k(self, sk, bar_time=None):
        bar_type = sk.bar_type.name
        score = sk.score

        type_names = {
            "STRONG_TREND": "强趋势K线", "REVERSAL": "反转K线",
            "DOJI": "十字星", "BULLISH_PIN": "多头Pin Bar",
            "BEARISH_PIN": "空头Pin Bar", "INSIDE_BAR": "内包K线",
            "OUTSIDE_BAR": "外包K线", "NEUTRAL": "中性K线",
        }
        self._type_label.setText(type_names.get(bar_type, bar_type))

        if bar_type in ("STRONG_TREND", "BULLISH_PIN") and sk.is_bullish:
            self._type_label.setStyleSheet(f"font-size: 18px; font-weight: 700; color: {BULL}; background: transparent;")
        elif bar_type in ("STRONG_TREND", "BEARISH_PIN") and not sk.is_bullish:
            self._type_label.setStyleSheet(f"font-size: 18px; font-weight: 700; color: {BEAR}; background: transparent;")
        else:
            self._type_label.setStyleSheet(f"font-size: 18px; font-weight: 700; color: {TEXT_PRIMARY}; background: transparent;")

        if score > 0.3:
            sc = BULL
        elif score < -0.3:
            sc = BEAR
        else:
            sc = TEXT_MUTED
        self._score_label.setText(f"{score:+.2f}")
        self._score_label.setStyleSheet(f"font-size: 26px; font-weight: 800; color: {sc}; background: transparent;")

        body = getattr(sk, 'body_ratio', 0)
        close_pos = getattr(sk, 'close_position', 0.5)
        upper = getattr(sk, 'upper_wick', 0)
        lower = getattr(sk, 'lower_wick', 0)

        self._update_metric_v(self._body_ratio, "实体比", f"{body:.0%}")
        self._update_metric_v(self._close_pos, "收盘位置", f"{close_pos:.0%}")
        self._update_metric_v(self._upper_wick, "上影线", _wick_desc(upper))
        self._update_metric_v(self._lower_wick, "下影线", _wick_desc(lower))
        if bar_time:
            self._update_metric_v(self._time_label, "时间", bar_time)

    def _update_metric_v(self, widget, label, value):
        children = widget.findChildren(QLabel)
        if len(children) >= 2:
            children[1].setText(str(value))


def _wick_desc(ratio: float) -> str:
    if ratio < 0.15:
        return "短"
    elif ratio < 0.35:
        return "中"
    else:
        return "长"


# ─────────────────────────────────────────────
# Support/Resistance Panel
# ─────────────────────────────────────────────

class SRPanel(QWidget):
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self._frame, inner = _card("支撑压力", ACCENT_GREEN)

        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setStyleSheet("QScrollArea { background: transparent; border: none; }")
        self._scroll_widget = QWidget()
        self._scroll_widget.setStyleSheet("background: transparent;")
        self._scroll_layout = QVBoxLayout(self._scroll_widget)
        self._scroll_layout.setContentsMargins(0, 0, 0, 0)
        self._scroll_layout.setSpacing(3)
        self._scroll_layout.addStretch()
        self._scroll.setWidget(self._scroll_widget)
        inner.addWidget(self._scroll)
        layout.addWidget(self._frame)

    def update_sr(self, sr_result, current_price: float):
        # Clear previous
        while self._scroll_layout.count() > 1:
            item = self._scroll_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        levels = sorted(sr_result.levels, key=lambda x: x.price, reverse=True)
        for lvl in levels:
            row = QWidget()
            row.setStyleSheet("background: transparent;")
            h = QHBoxLayout(row)
            h.setContentsMargins(0, 2, 0, 2)
            h.setSpacing(6)

            is_resistance = lvl.price > current_price
            color = ACCENT_RED if is_resistance else ACCENT_GREEN
            icon = "─" if is_resistance else "─"

            price_lbl = QLabel(f"{lvl.price:.1f}")
            price_lbl.setStyleSheet(f"font-size: 12px; color: {color}; font-weight: 700; background: transparent;")
            price_lbl.setFixedWidth(70)
            h.addWidget(price_lbl)

            name_lbl = QLabel(lvl.label)
            name_lbl.setStyleSheet(f"font-size: 11px; color: {TEXT_SECONDARY}; background: transparent;")
            h.addWidget(name_lbl)
            h.addStretch()

            strength = getattr(lvl, 'strength', 0.5)
            bar_w = int(strength * 40)
            bar = QLabel()
            bar.setFixedSize(bar_w, 4)
            bar.setStyleSheet(f"background-color: {color}66; border-radius: 2px;")
            h.addWidget(bar)

            self._scroll_layout.insertWidget(self._scroll_layout.count() - 1, row)

        # Current price marker
        marker = QWidget()
        marker.setStyleSheet("background: transparent;")
        mh = QHBoxLayout(marker)
        mh.setContentsMargins(0, 4, 0, 4)
        mh.setSpacing(6)
        cp = QLabel(f"● {current_price:.1f}")
        cp.setStyleSheet(f"font-size: 13px; color: {ACCENT_BLUE}; font-weight: 700; background: transparent;")
        mh.addWidget(cp)
        mh.addWidget(QLabel("当前价格"))
        mh.findChildren(QLabel)[-1].setStyleSheet(f"font-size: 11px; color: {TEXT_MUTED}; background: transparent;")
        mh.addStretch()
        self._scroll_layout.insertWidget(self._scroll_layout.count() - 1, marker)


# ─────────────────────────────────────────────
# Key Zones Panel
# ─────────────────────────────────────────────

class ZonesPanel(QWidget):
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self._frame, inner = _card("关键区域", ACCENT_YELLOW)

        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setStyleSheet("QScrollArea { background: transparent; border: none; }")
        self._scroll_widget = QWidget()
        self._scroll_widget.setStyleSheet("background: transparent;")
        self._scroll_layout = QVBoxLayout(self._scroll_widget)
        self._scroll_layout.setContentsMargins(0, 0, 0, 0)
        self._scroll_layout.setSpacing(4)
        self._scroll_layout.addStretch()
        self._scroll.setWidget(self._scroll_widget)
        inner.addWidget(self._scroll)
        layout.addWidget(self._frame)

    def update_zones(self, zones_result):
        while self._scroll_layout.count() > 1:
            item = self._scroll_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        for zone in zones_result.zones:
            card = QFrame()
            card.setObjectName("signalRow")
            card.setStyleSheet(f"""
                QFrame#signalRow {{
                    background-color: {BG_CARD}; border: 1px solid {BORDER};
                    border-radius: 8px; padding: 8px 12px;
                }}
            """)
            cl = QVBoxLayout(card)
            cl.setContentsMargins(10, 8, 10, 8)
            cl.setSpacing(4)

            name = QLabel(getattr(zone, 'name', '区域'))
            name.setStyleSheet(f"font-size: 13px; font-weight: 700; color: {TEXT_PRIMARY}; background: transparent;")
            cl.addWidget(name)

            lower = getattr(zone, 'lower', 0)
            upper = getattr(zone, 'upper', 0)
            range_lbl = QLabel(f"{lower:.1f} — {upper:.1f}")
            range_lbl.setStyleSheet(f"font-size: 12px; color: {ACCENT_BLUE}; font-weight: 600; background: transparent;")
            cl.addWidget(range_lbl)

            touches = getattr(zone, 'touches', 0)
            strength = getattr(zone, 'strength', 0.5)
            info = QLabel(f"触及 {touches} 次 · 强度 {strength:.0%}")
            info.setStyleSheet(f"font-size: 11px; color: {TEXT_MUTED}; background: transparent;")
            cl.addWidget(info)

            self._scroll_layout.insertWidget(self._scroll_layout.count() - 1, card)


# ─────────────────────────────────────────────
# Trade Signals Panel
# ─────────────────────────────────────────────

class SignalsPanel(QWidget):
    signal_execute = pyqtSignal(object)  # emits the TradeSignal object

    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self._frame, inner = _card("交易信号", ACCENT_GREEN)

        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setStyleSheet("QScrollArea { background: transparent; border: none; }")
        self._scroll_widget = QWidget()
        self._scroll_widget.setStyleSheet("background: transparent;")
        self._scroll_layout = QVBoxLayout(self._scroll_widget)
        self._scroll_layout.setContentsMargins(0, 0, 0, 0)
        self._scroll_layout.setSpacing(4)
        self._scroll_layout.addStretch()
        self._scroll.setWidget(self._scroll_widget)

        self._empty_label = QLabel("等待信号...")
        self._empty_label.setStyleSheet(f"font-size: 13px; color: {TEXT_MUTED}; padding: 20px;")
        self._empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._scroll_layout.insertWidget(0, self._empty_label)

        inner.addWidget(self._scroll)
        layout.addWidget(self._frame)

    def update_signals(self, signals):
        while self._scroll_layout.count() > 1:
            item = self._scroll_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        if not signals:
            self._empty_label = QLabel("等待信号...")
            self._empty_label.setStyleSheet(f"font-size: 13px; color: {TEXT_MUTED}; padding: 20px;")
            self._empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self._scroll_layout.insertWidget(0, self._empty_label)
            return

        for ts in signals:
            card = QFrame()
            card.setObjectName("signalRow")
            is_long = ts.direction == 'L'
            accent = BULL if is_long else BEAR

            card.setStyleSheet(f"""
                QFrame#signalRow {{
                    background-color: {BG_CARD};
                    border: 1px solid {BORDER};
                    border-left: 3px solid {accent};
                    border-radius: 6px;
                    padding: 8px 12px;
                }}
            """)
            cl = QVBoxLayout(card)
            cl.setContentsMargins(10, 6, 10, 6)
            cl.setSpacing(3)

            # Header row
            hr = QHBoxLayout()
            dir_label = QLabel("▲ 多头" if is_long else "▼ 空头")
            dir_label.setStyleSheet(f"font-size: 14px; font-weight: 700; color: {accent}; background: transparent;")
            hr.addWidget(dir_label)
            hr.addStretch()

            type_pill = _pill(ts.signal_type.value, accent)
            hr.addWidget(type_pill)
            cl.addLayout(hr)

            # Prices row
            prices = QLabel(f"入场 {ts.entry_price:.1f}  |  止损 {ts.stop_price:.1f}  |  目标 {ts.target_price:.1f}")
            prices.setStyleSheet(f"font-size: 12px; color: {TEXT_SECONDARY}; background: transparent;")
            cl.addWidget(prices)

            # Info row
            rec_lot = getattr(ts, 'recommended_lot', 0.01)
            info = QLabel(f"置信度 {ts.confidence:.0%}  ·  RR {ts.risk_reward_ratio:.1f}:1  ·  推荐 {rec_lot:.2f}手")
            info.setStyleSheet(f"font-size: 11px; color: {TEXT_MUTED}; background: transparent;")
            cl.addWidget(info)

            # Execute button row
            btn_row = QHBoxLayout()
            btn_row.addStretch()

            strength_label = QLabel("强力" if ts.strength.value == 1 else ("中等" if ts.strength.value == 2 else "弱"))
            strength_label.setStyleSheet(f"font-size: 11px; color: {accent}; background: transparent; font-weight: 600;")
            btn_row.addWidget(strength_label)

            exec_btn = QPushButton("执行交易 ▸")
            exec_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            exec_btn.setStyleSheet(f"""
                QPushButton {{
                    background-color: {accent};
                    color: #000000;
                    border: none;
                    border-radius: 12px;
                    padding: 5px 14px;
                    font-size: 11px;
                    font-weight: 700;
                }}
                QPushButton:hover {{
                    background-color: {accent}cc;
                }}
                QPushButton:pressed {{
                    background-color: {accent}88;
                }}
            """)
            exec_btn.clicked.connect(lambda checked, ts=ts: self.signal_execute.emit(ts))
            btn_row.addWidget(exec_btn)
            cl.addLayout(btn_row)

            self._scroll_layout.insertWidget(self._scroll_layout.count() - 1, card)
