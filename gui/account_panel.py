"""Account info panel with balance, equity, win rate, and daily risk monitor."""
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel,
                             QFrame, QProgressBar)
from PyQt6.QtCore import Qt

from gui.styles import (BG_CARD, BORDER, TEXT_PRIMARY, TEXT_SECONDARY,
                         TEXT_MUTED, ACCENT_GREEN, ACCENT_RED, ACCENT_BLUE,
                         ACCENT_YELLOW, ACCENT_ORANGE)


def _kv_row(label: str, value: str, v_color: str = TEXT_PRIMARY) -> QWidget:
    row = QWidget()
    row.setStyleSheet("background: transparent;")
    h = QHBoxLayout(row)
    h.setContentsMargins(0, 1, 0, 1)
    h.setSpacing(6)
    lbl = QLabel(label)
    lbl.setStyleSheet(f"font-size: 12px; color: {TEXT_SECONDARY}; background: transparent;")
    h.addWidget(lbl)
    h.addStretch()
    val = QLabel(value)
    val.setStyleSheet(f"font-size: 12px; color: {v_color}; font-weight: 600; background: transparent;")
    h.addWidget(val)
    return row


class AccountPanel(QWidget):
    def __init__(self):
        super().__init__()
        self._account = {}
        self._win_rate = 0.0
        self._profit_factor = 0.0
        self._total_trades = 0
        self._daily_pnl = 0.0
        self._daily_loss_pct = 0.0
        self._daily_profit_pct = 0.0
        self._profit_target_pct = 15.0  # default, override via set_targets
        self._balance = 0.0
        self._setup()

    def _setup(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        frame = QFrame()
        frame.setObjectName("card")
        frame.setStyleSheet(f"""
            QFrame#card {{
                background-color: {BG_CARD};
                border: 1px solid {BORDER};
                border-radius: 10px;
            }}
        """)
        inner = QVBoxLayout(frame)
        inner.setContentsMargins(14, 10, 14, 10)
        inner.setSpacing(6)

        # Title
        title = QLabel("账户状态")
        title.setStyleSheet(f"font-size: 13px; font-weight: 700; color: {ACCENT_BLUE}; padding-bottom: 6px; "
                           f"border-bottom: 1px solid {BORDER}; background: transparent;")
        inner.addWidget(title)

        # Account info
        self._login_lbl = _kv_row("账户", "--")
        self._balance_lbl = _kv_row("余额", "--", ACCENT_GREEN)
        self._equity_lbl = _kv_row("净值", "--", ACCENT_GREEN)
        self._margin_lbl = _kv_row("保证金", "--")
        self._free_margin_lbl = _kv_row("可用保证金", "--")
        self._leverage_lbl = _kv_row("杠杆", "--")

        inner.addWidget(self._login_lbl)
        inner.addWidget(self._balance_lbl)
        inner.addWidget(self._equity_lbl)
        inner.addWidget(self._margin_lbl)
        inner.addWidget(self._free_margin_lbl)
        inner.addWidget(self._leverage_lbl)

        # Separator
        sep = QFrame()
        sep.setObjectName("separator")
        sep.setStyleSheet(f"background-color: {BORDER}; max-height: 1px;")
        sep.setFixedHeight(1)
        inner.addWidget(sep)

        # Performance stats
        perf_title = QLabel("交易绩效")
        perf_title.setStyleSheet(f"font-size: 11px; font-weight: 700; color: {TEXT_MUTED}; "
                                 f"padding: 4px 0 2px 0; background: transparent;")
        inner.addWidget(perf_title)

        self._win_rate_lbl = _kv_row("胜率", "--", ACCENT_BLUE)
        self._profit_factor_lbl = _kv_row("盈亏比", "--", ACCENT_BLUE)
        self._total_trades_lbl = _kv_row("总交易", "--")
        self._daily_pnl_lbl = _kv_row("今日盈亏", "--")

        inner.addWidget(self._win_rate_lbl)
        inner.addWidget(self._profit_factor_lbl)
        inner.addWidget(self._total_trades_lbl)
        inner.addWidget(self._daily_pnl_lbl)

        # Daily loss limit bar
        risk_title = QLabel("日亏损监控 (上限 15%)")
        risk_title.setStyleSheet(f"font-size: 11px; font-weight: 700; color: {TEXT_MUTED}; "
                                 f"padding: 6px 0 2px 0; background: transparent;")
        inner.addWidget(risk_title)

        self._risk_bar = QProgressBar()
        self._risk_bar.setFixedHeight(12)
        self._risk_bar.setRange(0, 100)
        self._risk_bar.setValue(0)
        self._risk_bar.setTextVisible(True)
        self._risk_bar.setFormat("0%")
        self._risk_bar.setStyleSheet(f"""
            QProgressBar {{
                background-color: {TEXT_MUTED}22;
                border: 1px solid {BORDER};
                border-radius: 6px;
                text-align: center;
                color: {TEXT_PRIMARY};
                font-size: 10px;
                font-weight: 600;
            }}
            QProgressBar::chunk {{
                background-color: {ACCENT_GREEN};
                border-radius: 5px;
            }}
        """)
        self._risk_pct_lbl = QLabel("0.00%")
        self._risk_pct_lbl.setStyleSheet(f"font-size: 11px; color: {TEXT_MUTED}; background: transparent;")

        risk_row = QHBoxLayout()
        risk_row.addWidget(self._risk_bar, 1)
        risk_row.addWidget(self._risk_pct_lbl)
        inner.addLayout(risk_row)

        # Daily profit target bar
        profit_title = QLabel("日盈利目标 (15%)")
        profit_title.setStyleSheet(f"font-size: 11px; font-weight: 700; color: {TEXT_MUTED}; "
                                   f"padding: 6px 0 2px 0; background: transparent;")
        inner.addWidget(profit_title)

        self._profit_bar = QProgressBar()
        self._profit_bar.setFixedHeight(12)
        self._profit_bar.setRange(0, 100)
        self._profit_bar.setValue(0)
        self._profit_bar.setTextVisible(True)
        self._profit_bar.setFormat("0%")
        self._profit_bar.setStyleSheet(f"""
            QProgressBar {{
                background-color: {TEXT_MUTED}22;
                border: 1px solid {BORDER};
                border-radius: 6px;
                text-align: center;
                color: {TEXT_PRIMARY};
                font-size: 10px;
                font-weight: 600;
            }}
            QProgressBar::chunk {{
                background-color: {ACCENT_GREEN};
                border-radius: 5px;
            }}
        """)
        self._profit_pct_lbl = QLabel("0.00%")
        self._profit_pct_lbl.setStyleSheet(f"font-size: 11px; color: {TEXT_MUTED}; background: transparent;")

        profit_row = QHBoxLayout()
        profit_row.addWidget(self._profit_bar, 1)
        profit_row.addWidget(self._profit_pct_lbl)
        inner.addLayout(profit_row)

        inner.addStretch()
        layout.addWidget(frame)

    def update_account(self, account_info: dict):
        self._account = account_info
        self._balance = float(account_info.get('balance', 0))
        equity = float(account_info.get('equity', 0))
        margin = float(account_info.get('margin', 0))
        margin_free = float(account_info.get('margin_free', 0))
        login = account_info.get('login', '--')
        leverage = account_info.get('leverage', '--')
        name = account_info.get('name', '')
        server = account_info.get('server', '')

        self._update_kv(self._login_lbl, "账户", f"{login} ({name})" if name else str(login))
        self._update_kv(self._balance_lbl, "余额", f"${self._balance:,.2f}", ACCENT_GREEN)
        self._update_kv(self._equity_lbl, "净值", f"${equity:,.2f}",
                       ACCENT_GREEN if equity >= self._balance else ACCENT_RED)
        self._update_kv(self._margin_lbl, "保证金", f"${margin:,.2f}")
        self._update_kv(self._free_margin_lbl, "可用保证金", f"${margin_free:,.2f}",
                       ACCENT_GREEN if margin_free > 0 else ACCENT_RED)
        self._update_kv(self._leverage_lbl, "杠杆", f"1:{leverage}")

        self._refresh_risk()

    def update_performance(self, win_rate: float, profit_factor: float,
                           total_trades: int, daily_pnl: float):
        self._win_rate = win_rate
        self._profit_factor = profit_factor
        self._total_trades = total_trades
        self._daily_pnl = daily_pnl

        self._update_kv(self._win_rate_lbl, "胜率", f"{win_rate:.1%}",
                       ACCENT_GREEN if win_rate >= 0.5 else ACCENT_YELLOW)
        self._update_kv(self._profit_factor_lbl, "盈亏比", f"{profit_factor:.2f}",
                       ACCENT_GREEN if profit_factor >= 1.5 else ACCENT_YELLOW)
        self._update_kv(self._total_trades_lbl, "总交易", str(total_trades))

        pnl_color = ACCENT_GREEN if daily_pnl >= 0 else ACCENT_RED
        self._update_kv(self._daily_pnl_lbl, "今日盈亏", f"${daily_pnl:+,.2f}", pnl_color)

        self._refresh_risk()

    def set_targets(self, daily_profit_target_pct: float):
        """Set risk/profit target percentages from config."""
        self._profit_target_pct = daily_profit_target_pct * 100  # convert to %
        profit_title = self.layout().itemAt(0).widget().findChildren(QLabel)
        for lbl in profit_title:
            if "日盈利目标" in lbl.text():
                lbl.setText(f"日盈利目标 ({self._profit_target_pct:.0f}%)")
                break

    def _refresh_risk(self):
        balance = self._balance
        if balance <= 0:
            self._daily_loss_pct = 0.0
            self._daily_profit_pct = 0.0
        else:
            pnl = self._daily_pnl
            loss = abs(min(pnl, 0))
            profit = max(pnl, 0)
            self._daily_loss_pct = (loss / balance) * 100
            self._daily_profit_pct = (profit / balance) * 100

        # Loss risk bar
        loss_pct = self._daily_loss_pct
        self._risk_bar.setValue(int(min(loss_pct, 100)))
        self._risk_pct_lbl.setText(f"{loss_pct:.2f}%")

        if loss_pct < 5:
            risk_color = ACCENT_GREEN
        elif loss_pct < 10:
            risk_color = ACCENT_YELLOW
        elif loss_pct < 15:
            risk_color = ACCENT_ORANGE
        else:
            risk_color = ACCENT_RED

        self._risk_bar.setStyleSheet(f"""
            QProgressBar {{
                background-color: {TEXT_MUTED}22;
                border: 1px solid {BORDER};
                border-radius: 6px;
                text-align: center;
                color: {TEXT_PRIMARY};
                font-size: 10px;
                font-weight: 600;
            }}
            QProgressBar::chunk {{
                background-color: {risk_color};
                border-radius: 5px;
            }}
        """)
        self._risk_bar.setFormat(f"{int(loss_pct)}%")

        # Profit target bar
        target = self._profit_target_pct
        profit_pct = min(self._daily_profit_pct, target * 1.2)  # cap at 120% of target
        bar_value = int((profit_pct / target) * 100) if target > 0 else 0
        bar_value = min(bar_value, 100)
        self._profit_bar.setValue(bar_value)
        self._profit_pct_lbl.setText(f"{profit_pct:.2f}%")

        if profit_pct >= target:
            profit_color = ACCENT_GREEN  # hit target!
        elif profit_pct >= target * 0.5:
            profit_color = ACCENT_BLUE
        else:
            profit_color = ACCENT_GREEN

        self._profit_bar.setStyleSheet(f"""
            QProgressBar {{
                background-color: {TEXT_MUTED}22;
                border: 1px solid {BORDER};
                border-radius: 6px;
                text-align: center;
                color: {TEXT_PRIMARY};
                font-size: 10px;
                font-weight: 600;
            }}
            QProgressBar::chunk {{
                background-color: {profit_color};
                border-radius: 5px;
            }}
        """)
        self._profit_bar.setFormat(f"{int(profit_pct / target * 100) if target > 0 else 0}%")

    @staticmethod
    def _update_kv(widget, label, value, color=TEXT_PRIMARY):
        children = widget.findChildren(QLabel)
        if len(children) >= 2:
            children[1].setText(str(value))
            children[1].setStyleSheet(
                f"font-size: 12px; color: {color}; font-weight: 600; background: transparent;")
