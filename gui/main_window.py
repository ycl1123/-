"""Main window — modern card-based layout for Brooks Signals."""
from PyQt6.QtWidgets import (QMainWindow, QWidget, QHBoxLayout, QVBoxLayout,
                             QGridLayout, QLabel, QStatusBar, QFrame,
                             QPushButton, QSplitter, QScrollArea)
from PyQt6.QtCore import QTimer, Qt
from PyQt6.QtGui import QFont
import pandas as pd
from datetime import datetime

from gui.styles import (GLOBAL_STYLESHEET, BG_DARK, BG_CARD, BORDER,
                         TEXT_PRIMARY, TEXT_SECONDARY, TEXT_MUTED,
                         ACCENT_GREEN, ACCENT_RED, ACCENT_BLUE, BULL, BEAR)
from gui.panels import ContextPanel, SignalKPanel, SRPanel, ZonesPanel, SignalsPanel
from gui.alert_log import AlertLogWidget
from gui.account_panel import AccountPanel
from mt5.bridge import MT5Bridge
from analysis.engine import AnalysisEngine, AnalysisResult
from analysis.trade_signals import SignalStrength
from analysis.utils import calc_atr
from analysis.journal import TradeJournal
from alerts.manager import AlertManager, AlertSeverity
import numpy as np

DIR_MAP = {'L': '多头', 'S': '空头'}


class MainWindow(QMainWindow):
    def __init__(self, config):
        super().__init__()
        self.cfg = config
        self._bridge = None
        self._poll_bridge = None
        self._trade_bridge = None
        self._sl_tp_bridge = None
        self._pre_close_bridge = None
        self._protected_tickets: set = set()
        self._sl_tp_queue: list = []
        self._heads_up_sent: set = set()
        self._bars_cache: dict[str, pd.DataFrame] = {}
        self._last_bar_times: dict[str, datetime] = {}
        self._polling = False
        self._current_signals: list = []
        self._last_account_info: dict = {}
        self._last_balance: float = 0.0
        self._setup_ui()
        self._setup_components()
        self._connect_signals()

    # ═══════════════════════════════════════════
    # UI Setup
    # ═══════════════════════════════════════════

    def _setup_ui(self):
        self.setWindowTitle(self.cfg.gui.window_title)
        self.resize(self.cfg.gui.window_width, self.cfg.gui.window_height)
        self.setStyleSheet(GLOBAL_STYLESHEET)

        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(12, 10, 12, 10)
        root.setSpacing(10)

        # ── Header bar ──
        root.addLayout(self._build_header())

        # ── Main content: 2×2 card grid + right signals ──
        body = QHBoxLayout()
        body.setSpacing(10)

        # Left: 2×2 analysis cards
        left_cards = QGridLayout()
        left_cards.setSpacing(10)

        self.context_panel = ContextPanel()
        self.signal_k_panel = SignalKPanel()
        self.sr_panel = SRPanel()
        self.zones_panel = ZonesPanel()

        left_cards.addWidget(self.context_panel, 0, 0)
        left_cards.addWidget(self.signal_k_panel, 0, 1)
        left_cards.addWidget(self.sr_panel, 1, 0)
        left_cards.addWidget(self.zones_panel, 1, 1)

        left_wrapper = QWidget()
        left_wrapper.setLayout(left_cards)
        body.addWidget(left_wrapper, 3)

        # Right: Account + Trade signals + Alert log
        right_split = QSplitter(Qt.Orientation.Vertical)
        right_split.setStyleSheet(f"QSplitter::handle {{ background: {BORDER}; height: 2px; }}")

        self.account_panel = AccountPanel()
        self.account_panel.set_targets(self.cfg.mt5.daily_profit_target_pct)
        right_split.addWidget(self.account_panel)

        self.signals_panel = SignalsPanel()
        right_split.addWidget(self.signals_panel)

        self.alert_log = AlertLogWidget(max_rows=self.cfg.gui.alert_max_rows)
        right_split.addWidget(self.alert_log)
        right_split.setSizes([280, 300, 220])

        body.addWidget(right_split, 2)
        root.addLayout(body, 1)

        # ── Status bar ──
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("就绪 — 点击「连接 MT5」开始")

    def _build_header(self) -> QHBoxLayout:
        h = QHBoxLayout()
        h.setSpacing(12)

        # Logo / Title
        title = QLabel(f"◆ {self.cfg.symbol}")
        title.setFont(QFont("Segoe UI", 16, QFont.Weight.Bold))
        title.setStyleSheet(f"color: {TEXT_PRIMARY}; background: transparent;")
        h.addWidget(title)

        # Timeframe pills
        primary = self.cfg.timeframes["primary"]
        secondary = ", ".join(self.cfg.timeframes.get("secondary", []))
        tf_info = QLabel(f"{primary} 主周期 · {secondary} 辅助")
        tf_info.setStyleSheet(f"color: {TEXT_MUTED}; font-size: 12px; background: transparent;")
        h.addWidget(tf_info)

        h.addStretch()

        # Connection status indicator
        self._conn_dot = QLabel("●")
        self._conn_dot.setStyleSheet(f"color: {TEXT_MUTED}; font-size: 14px; background: transparent;")
        h.addWidget(self._conn_dot)

        self.status_label = QLabel("未连接")
        self.status_label.setStyleSheet(f"color: {TEXT_MUTED}; font-size: 13px; background: transparent;")
        h.addWidget(self.status_label)

        # Connect button
        self.connect_btn = QPushButton("连接 MT5")
        self.connect_btn.setObjectName("primary")
        self.connect_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.connect_btn.clicked.connect(self._manual_connect)
        h.addWidget(self.connect_btn)

        return h

    # ═══════════════════════════════════════════
    # Engine & Timer
    # ═══════════════════════════════════════════

    def _setup_components(self):
        self.engine = AnalysisEngine(self.cfg)
        self.alerts = AlertManager()
        self.journal = TradeJournal()
        self.poll_timer = QTimer()
        self.poll_timer.setInterval(self.cfg.mt5.polling_interval_ms)
        self.poll_timer.timeout.connect(self._poll)

        self.pre_close_timer = QTimer()
        self.pre_close_timer.setInterval(1000)  # every 1 second
        self.pre_close_timer.timeout.connect(self._check_pre_close)

        # TF → seconds map for pre-close alignment
        self._tf_seconds = {
            "M1": 60, "M2": 120, "M3": 180, "M4": 240,
            "M5": 300, "M6": 360, "M10": 600, "M12": 720,
            "M15": 900, "M20": 1200, "M30": 1800, "H1": 3600,
        }

    def _connect_signals(self):
        self.engine.analysis_ready.connect(self._on_analysis)
        self.alerts.new_alert.connect(self.alert_log.add_alert)
        self.signals_panel.signal_execute.connect(self._on_execute_signal)

    # ═══════════════════════════════════════════
    # MT5 Connection (QProcess bridge)
    # ═══════════════════════════════════════════

    def _manual_connect(self):
        self.connect_btn.setEnabled(False)
        self.connect_btn.setText("连接中...")
        self._set_connection_status("connecting")
        self.status_bar.showMessage("正在通过子进程连接 MT5（隔离C层崩溃）...")

        tf_list = [self.cfg.timeframes["primary"]] + self.cfg.timeframes.get("secondary", [])
        self._bridge = MT5Bridge(self.cfg.symbol, tf_list, self.cfg.mt5.history_bars)
        self._bridge.result_ready.connect(self._on_bridge_result)
        self._bridge.start()

    def _set_connection_status(self, status: str):
        colors = {
            "connected": (ACCENT_GREEN, ACCENT_GREEN),
            "connecting": (ACCENT_RED, ACCENT_RED),
            "disconnected": (TEXT_MUTED, TEXT_MUTED),
        }
        dot_color, text_color = colors.get(status, (TEXT_MUTED, TEXT_MUTED))
        self._conn_dot.setStyleSheet(f"color: {dot_color}; font-size: 14px; background: transparent;")

    def _on_bridge_result(self, success: bool, message: str, bars_cache: dict, account_info: dict):
        if success:
            self._bars_cache = bars_cache
            for tf, df in bars_cache.items():
                if len(df) > 0:
                    self._last_bar_times[tf] = df.index[-1]

            self._set_connection_status("connected")
            self.status_label.setText(f"已连接")
            self.status_label.setStyleSheet(f"color: {ACCENT_GREEN}; font-size: 13px; background: transparent;")
            self.connect_btn.setVisible(False)

            if account_info:
                self.account_panel.update_account(account_info)
                self._last_account_info = account_info
                self._last_balance = account_info.get('balance', 0)

            bar_info = ", ".join(f"{t}={len(d)}根" for t, d in bars_cache.items())
            self.status_bar.showMessage(f"已连接 - {message} | {bar_info}")
            QTimer.singleShot(200, self._on_bridge_connected)
        else:
            self._set_connection_status("disconnected")
            self.status_label.setText("连接失败")
            self.status_label.setStyleSheet(f"color: {ACCENT_RED}; font-size: 13px; background: transparent;")
            self.status_bar.showMessage(f"连接失败: {message[:150]}")
            self.connect_btn.setEnabled(True)
            self.connect_btn.setText("重试连接")

    def _on_bridge_connected(self):
        result = None
        try:
            primary_tf = self.cfg.timeframes["primary"]
            bars = self._bars_cache.get(primary_tf)
            if bars is not None and len(bars) > 10:
                self.status_bar.showMessage("分析中...")
                result = self.engine.analyze(self.cfg.symbol, primary_tf, bars)
                self._update_all_panels(result)
                self._generate_alerts(result)
                self._refresh_performance()
                self._auto_protect_positions(self._last_account_info)
                self.alerts.add(self.cfg.symbol, primary_tf,
                               f"初始化完成，加载 {len(bars)} 根K线",
                               AlertSeverity.INFO)
            self._polling = True
            self.poll_timer.start()
            self.pre_close_timer.start()
            ctx_dir = result.context.always_in.direction if result and result.context else '--'
            self.status_bar.showMessage(f"就绪 | Always In: {ctx_dir}")
        except Exception as e:
            self.status_bar.showMessage(f"初始化分析失败: {e}")

    # ═══════════════════════════════════════════
    # Polling
    # ═══════════════════════════════════════════

    def _poll(self):
        if not self._polling or not self._bars_cache or self._poll_bridge is not None:
            return
        tf_list = [self.cfg.timeframes["primary"]] + self.cfg.timeframes.get("secondary", [])
        self._poll_bridge = MT5Bridge(self.cfg.symbol, tf_list, self.cfg.mt5.history_bars)
        self._poll_bridge.result_ready.connect(self._on_poll_result)
        self._poll_bridge.start()

    def _on_poll_result(self, success: bool, message: str, bars_cache: dict, account_info: dict):
        self._poll_bridge = None
        if not success or not bars_cache:
            return
        primary_tf = self.cfg.timeframes["primary"]
        new_bars = bars_cache.get(primary_tf)
        if new_bars is None or len(new_bars) == 0:
            return
        last_time = self._last_bar_times.get(primary_tf)
        if last_time is not None and new_bars.index[-1] <= last_time:
            return
        self._bars_cache = bars_cache
        for tf, df in bars_cache.items():
            if len(df) > 0:
                self._last_bar_times[tf] = df.index[-1]
        if account_info:
            self.account_panel.update_account(account_info)
            self._last_account_info = account_info
            self._last_balance = account_info.get('balance', 0)
        try:
            result = self.engine.analyze(self.cfg.symbol, primary_tf, new_bars)
            self._update_all_panels(result)
            self._generate_alerts(result)
            self._refresh_performance()
            self._auto_protect_positions(self._last_account_info)
        except Exception as e:
            self.status_bar.showMessage(f"轮询分析异常: {e}")

    # ═══════════════════════════════════════════
    # Panel Updates
    # ═══════════════════════════════════════════

    def _on_analysis(self, result: AnalysisResult):
        try:
            self._update_all_panels(result)
            self._generate_alerts(result)
            self._refresh_performance()
        except Exception as e:
            self.status_bar.showMessage(f"更新面板异常: {e}")

    def _update_all_panels(self, result: AnalysisResult):
        if result.context:
            self.context_panel.update_context(result.context)
        if result.signal_k:
            self.signal_k_panel.update_signal_k(
                result.signal_k,
                bar_time=result.timestamp.strftime("%H:%M") if result.timestamp else None
            )
        if result.sr:
            current = result.current_bar['close'] if result.current_bar is not None else 0
            self.sr_panel.update_sr(result.sr, current)
        if result.zones:
            self.zones_panel.update_zones(result.zones)
        if result.trade_signals is not None:
            self._current_signals = result.trade_signals
            # Annotate each signal with recommended lot size
            balance = self._last_balance
            for ts in self._current_signals:
                ts.recommended_lot = self._calc_recommended_lot(
                    balance, abs(ts.entry_price - ts.stop_price))
            self.signals_panel.update_signals(self._current_signals)

    def _generate_alerts(self, result: AnalysisResult):
        sym, tf = result.symbol, result.timeframe
        sk = result.signal_k
        if sk is not None:
            type_name = sk.bar_type.name
            if type_name in ("STRONG_TREND", "REVERSAL"):
                direction = "多头" if sk.is_bullish else "空头"
                self.alerts.add_signal_k(sym, tf,
                    f"{direction}信号K线: {sk.bar_type.name} (评分: {sk.score:+.2f})")

        ctx = result.context
        if ctx is not None:
            self.alerts.add_context_change(sym, tf, ctx.always_in.direction)

        if result.zones and result.current_bar is not None:
            close = result.current_bar['close']
            for zone in result.zones.zones:
                if zone.lower <= close <= zone.upper:
                    self.alerts.add_zone_touch(sym, tf, zone.name, close)

        for ts in result.trade_signals:
            if ts.strength.value <= SignalStrength.STRONG.value:
                dir_cn = DIR_MAP.get(ts.direction, ts.direction)
                self.alerts.add(sym, tf,
                    f"交易信号 [{ts.signal_type.value}] {dir_cn} | "
                    f"入场{ts.entry_price:.1f} 止损{ts.stop_price:.1f} 目标{ts.target_price:.1f} | "
                    f"置信度{ts.confidence:.0%}",
                    AlertSeverity.SIGNAL if ts.strength == SignalStrength.STRONG else AlertSeverity.INFO)

        if sk and ctx:
            self.status_bar.showMessage(
                f"最后更新: {result.timestamp} | "
                f"Always In: {ctx.always_in.direction} | "
                f"K线评分: {sk.score:+.2f}"
            )

    def _refresh_performance(self):
        """Read journal stats and push to account panel."""
        try:
            wr = self.journal.win_rate()
            pf = self.journal.profit_factor()
            total = self.journal.total_trades()
            daily = self.journal.daily_pnl()
            self.account_panel.update_performance(wr, pf, total, daily)
        except Exception:
            pass

    # ═══════════════════════════════════════════
    # Pre-Close Heads-Up (signal alert in last 5s of bar)
    # ═══════════════════════════════════════════

    def _check_pre_close(self):
        """Check if we're in the last 5 seconds of the current primary TF bar."""
        if not self._polling or self._pre_close_bridge is not None or self._poll_bridge is not None:
            return

        primary_tf = self.cfg.timeframes["primary"]
        tf_sec = self._tf_seconds.get(primary_tf, 120)

        now = datetime.now()
        seconds_from_hour = now.minute * 60 + now.second + now.microsecond / 1e6
        bar_start = int(seconds_from_hour // tf_sec) * tf_sec
        bar_end = bar_start + tf_sec
        seconds_left = bar_end - seconds_from_hour

        if seconds_left > 5 or seconds_left <= 0:
            return

        # Dedup: only one heads-up per bar
        bar_key = f"{now:%H:%M}:{int(bar_end) % 60:02d}"
        if bar_key in self._heads_up_sent:
            return
        self._heads_up_sent.add(bar_key)
        # Clean old entries (keep last 10)
        if len(self._heads_up_sent) > 50:
            self._heads_up_sent = set(list(self._heads_up_sent)[-10:])

        tf_list = [primary_tf] + self.cfg.timeframes.get("secondary", [])
        self._pre_close_bridge = MT5Bridge(self.cfg.symbol, tf_list, self.cfg.mt5.history_bars)
        self._pre_close_bridge.result_ready.connect(self._on_pre_close_result)
        self._pre_close_bridge.start()
        self.status_bar.showMessage(
            f"⏰ {primary_tf} 即将收盘 ({seconds_left:.0f}秒) — 正在分析预警..."
        )

    def _on_pre_close_result(self, success: bool, message: str, bars_cache: dict, account_info: dict):
        self._pre_close_bridge = None
        if not success or not bars_cache:
            return

        primary_tf = self.cfg.timeframes["primary"]
        bars = bars_cache.get(primary_tf)
        if bars is None or len(bars) < 10:
            return

        try:
            result = self.engine.analyze(self.cfg.symbol, primary_tf, bars)
            self._update_all_panels(result)
            self._generate_pre_close_alerts(result)
            if account_info:
                self._last_account_info = account_info
                self._last_balance = account_info.get('balance', 0)
        except Exception:
            pass

    def _generate_pre_close_alerts(self, result: AnalysisResult):
        """Heads-up alerts with ⏰ prefix — signal preview before bar closes."""
        sym, tf = result.symbol, result.timeframe
        sk = result.signal_k
        ctx = result.context

        if sk is not None:
            type_name = sk.bar_type.name
            if type_name in ("STRONG_TREND", "REVERSAL"):
                direction = "多头" if sk.is_bullish else "空头"
                self.alerts.add(sym, tf,
                    f"⏰ 收盘预警 [{type_name}] {direction} (评分{sk.score:+.2f}) | 准备入场",
                    AlertSeverity.SIGNAL)

        for ts in result.trade_signals:
            if ts.strength.value <= SignalStrength.MEDIUM.value:
                dir_cn = DIR_MAP.get(ts.direction, ts.direction)
                self.alerts.add(sym, tf,
                    f"⏰ 收盘预警 [{ts.signal_type.value}] {dir_cn} | "
                    f"入场{ts.entry_price:.1f} 止损{ts.stop_price:.1f} 目标{ts.target_price:.1f} | "
                    f"置信度{ts.confidence:.0%} | 推荐{getattr(ts, 'recommended_lot', 0.01):.2f}手",
                    AlertSeverity.SIGNAL)

        if sk and ctx:
            self.status_bar.showMessage(
                f"⏰ {tf}收盘预警 | Always In: {ctx.always_in.direction} | "
                f"K线: {sk.bar_type.name}({sk.score:+.2f}) | "
                f"信号数: {len(result.trade_signals)}"
            )

    # ═══════════════════════════════════════════
    # Auto SL/TP Protection (detect naked positions, auto-set SL/TP)
    # ═══════════════════════════════════════════

    def _auto_protect_positions(self, account_info: dict):
        """Check open positions and queue unprotected ones for SL/TP setting."""
        if account_info is None:
            return
        positions = account_info.get('positions', [])
        if not positions:
            return

        bars = self._bars_cache.get(self.cfg.timeframes["primary"])
        if bars is None or len(bars) < 14:
            return

        for pos in positions:
            ticket = pos['ticket']
            # Already has both SL and TP → skip
            if pos['sl'] > 0 and pos['tp'] > 0:
                self._protected_tickets.add(ticket)
                continue
            # Already queued or being processed
            if ticket in self._protected_tickets:
                continue
            if any(q['ticket'] == ticket for q in self._sl_tp_queue):
                continue

            sl, tp, source = self._calc_sl_tp_for_position(pos, bars)
            self._sl_tp_queue.append({
                'ticket': ticket, 'sl': sl, 'tp': tp, 'source': source,
                'pos_type': pos['type'], 'entry': pos['price_open']
            })
            self._protected_tickets.add(ticket)

        self._process_sl_tp_queue()

    def _find_matching_signal(self, pos_type: str):
        """Find a current trade signal matching the position direction."""
        pos_is_long = pos_type == 'BUY'
        for sig in self._current_signals:
            sig_is_long = sig.direction == 'L'
            if pos_is_long == sig_is_long:
                return sig
        return None

    def _calc_sl_tp_for_position(self, pos: dict, bars) -> tuple:
        """Compute SL/TP. Signal SL/TP if same direction, otherwise ATR-based.
        Returns (sl, tp, source_str)."""
        entry = pos['price_open']
        pos_type = pos['type']

        # Try to match a current signal in the same direction
        sig = self._find_matching_signal(pos_type)
        if sig is not None:
            # Validate: SL must be on the correct side of entry
            if pos_type == 'BUY' and sig.stop_price < entry and sig.target_price > entry:
                return sig.stop_price, sig.target_price, f"信号: {sig.signal_type.value}"
            elif pos_type == 'SELL' and sig.stop_price > entry and sig.target_price < entry:
                return sig.stop_price, sig.target_price, f"信号: {sig.signal_type.value}"

        # Fallback: ATR-based stops
        atr_arr = calc_atr(bars, 14)
        current_atr = atr_arr[-1] if not np.isnan(atr_arr[-1]) else 3.0
        if current_atr < 1.0:
            current_atr = 3.0

        is_long = pos_type == 'BUY'
        stop_dist = current_atr * 1.5
        stop_dist = max(stop_dist, current_atr * 0.3)
        stop_dist = min(stop_dist, current_atr * 3.0)

        if is_long:
            sl = round(entry - stop_dist, 1)
            tp = round(entry + stop_dist * 1.5, 1)
        else:
            sl = round(entry + stop_dist, 1)
            tp = round(entry - stop_dist * 1.5, 1)

        return sl, tp, "ATR通用"

    def _calc_recommended_lot(self, balance: float, stop_distance: float) -> float:
        """Calculate recommended lot size based on risk_pct rule."""
        if balance <= 0 or stop_distance <= 0:
            return self.cfg.mt5.lot_size
        risk_amount = balance * self.cfg.mt5.risk_pct
        contract_size = self.cfg.mt5.contract_size
        raw_lot = risk_amount / (stop_distance * contract_size)
        # Round down to nearest 0.01
        lot = max(int(raw_lot * 100) / 100, 0.01)
        return lot

    def _process_sl_tp_queue(self):
        """Process SL/TP queue one position at a time."""
        if self._sl_tp_bridge is not None:
            return  # already processing
        if not self._sl_tp_queue:
            return

        item = self._sl_tp_queue.pop(0)
        ticket = item['ticket']
        sl = item['sl']
        tp = item['tp']
        source = item.get('source', '')
        entry = item.get('entry', 0)
        stop_dist = abs(entry - sl)
        rec_lot = self._calc_recommended_lot(self._last_balance, stop_dist)
        item['rec_lot'] = rec_lot

        self.status_bar.showMessage(
            f"自动挂SL/TP: 单号#{ticket} SL={sl:.1f} TP={tp:.1f} | {source} | 推荐{rec_lot:.2f}手"
        )

        self._sl_tp_bridge = MT5Bridge(self.cfg.symbol, [], 0)
        self._sl_tp_bridge.sl_tp_result.connect(self._on_sl_tp_result)
        self._sl_tp_bridge.set_sl_tp(ticket, sl, tp, self.cfg.symbol)

    def _on_sl_tp_result(self, success: bool, message: str, data: dict):
        if success:
            ticket = data.get('ticket', '?')
            # Find the original queue item for context
            self.status_bar.showMessage(f"SL/TP已挂上: 单号#{ticket}")
            self.alerts.add(
                self.cfg.symbol, self.cfg.timeframes["primary"],
                f"自动挂SL/TP #{ticket}: {message}",
                AlertSeverity.INFO
            )
        else:
            self.status_bar.showMessage(f"SL/TP挂单失败: {message}")
            self.alerts.add(
                self.cfg.symbol, self.cfg.timeframes["primary"],
                f"自动挂SL/TP失败: {message}",
                AlertSeverity.WARNING
            )

        self._sl_tp_bridge = None
        self._process_sl_tp_queue()

    # ═══════════════════════════════════════════
    # Manual Trade Execution (from signal card button)
    # ═══════════════════════════════════════════

    def _on_execute_signal(self, ts):
        """User clicked Execute on a trade signal card."""
        lot_size = getattr(ts, 'recommended_lot', self.cfg.mt5.lot_size)
        symbol = self.cfg.symbol
        direction = ts.direction
        entry = ts.entry_price
        sl = ts.stop_price
        tp = ts.target_price
        signal_name = ts.signal_type.value
        comment = f"Brooks_{signal_name}"

        self.status_bar.showMessage(
            f"正在执行: {signal_name} {DIR_MAP.get(direction, direction)} "
            f"入场{entry:.1f} 止损{sl:.1f} 止盈{tp:.1f} 手数{lot_size}..."
        )

        self._trade_bridge = MT5Bridge(symbol, [], 0)
        self._trade_bridge.trade_result.connect(self._on_trade_result)
        self._trade_bridge.execute_trade(symbol, direction, lot_size, entry, sl, tp, comment)

    def _on_trade_result(self, success: bool, message: str, order_info: dict):
        if success:
            order_id = order_info.get('order_id', '?')
            fill_price = order_info.get('entry_price', 0)
            self.status_bar.showMessage(
                f"交易成功 #{order_id} | {message} | 成交价 {fill_price:.1f}"
            )
            self.alerts.add(
                self.cfg.symbol, self.cfg.timeframes["primary"],
                f"交易已执行 #{order_id}: {message}",
                AlertSeverity.SIGNAL
            )
        else:
            self.status_bar.showMessage(f"交易失败: {message}")
            self.alerts.add(
                self.cfg.symbol, self.cfg.timeframes["primary"],
                f"交易执行失败: {message}",
                AlertSeverity.WARNING
            )

        self._trade_bridge = None

    def closeEvent(self, event):
        self._polling = False
        self.poll_timer.stop()
        self.pre_close_timer.stop()
        if self._bridge:
            self._bridge.stop()
        if self._poll_bridge:
            self._poll_bridge.stop()
        if self._pre_close_bridge:
            self._pre_close_bridge.stop()
        if self._trade_bridge:
            self._trade_bridge.stop()
        if self._sl_tp_bridge:
            self._sl_tp_bridge.stop()
        event.accept()
