from dataclasses import dataclass, field
import pandas as pd
from pathlib import Path
from datetime import datetime
from PyQt6.QtCore import QObject, pyqtSignal

from analysis.signal_k import analyze_signal_k, SignalKResult
from analysis.support_resistance import analyze_support_resistance, SRResult
from analysis.key_zones import analyze_key_zones, KeyZonesResult
from analysis.market_context import analyze_context, MarketContextResult
from analysis.trade_signals import compute_trade_signals, TradeSignal

ANALYSIS_LOG = Path(__file__).parent.parent / "analysis_log.txt"


def _log(msg: str):
    entry = f"[{datetime.now().strftime('%H:%M:%S.%f')[:-3]}] {msg}"
    try:
        with open(ANALYSIS_LOG, "a", encoding="utf-8") as f:
            f.write(entry + "\n")
            f.flush()
    except Exception:
        pass


@dataclass
class AnalysisResult:
    symbol: str
    timeframe: str
    current_bar: pd.Series | None
    signal_k: SignalKResult | None
    sr: SRResult | None
    zones: KeyZonesResult | None
    context: MarketContextResult | None
    timestamp: pd.Timestamp | None
    trade_signals: list = field(default_factory=list)


class AnalysisEngine(QObject):
    analysis_ready = pyqtSignal(AnalysisResult)

    def __init__(self, config):
        super().__init__()
        self.cfg = config
        self._prev_results: dict[str, AnalysisResult] = {}

    def analyze(self, symbol: str, timeframe: str, bars: pd.DataFrame) -> AnalysisResult:
        """Run all 4 core analysis modules. Crash-proof logging before each step."""
        cfg_a = self.cfg.analysis
        n_bars = len(bars)
        _log(f"=== analyze START: {symbol} {timeframe} {n_bars} bars ===")

        # Step 1: Signal K
        _log("Step 1/5: signal_k...")
        signal_k_results = analyze_signal_k(bars, cfg_a.signal_k.lookback_for_avg)
        latest_signal_k = signal_k_results.iloc[-1] if len(signal_k_results) > 0 else None
        if latest_signal_k:
            _log(f"  signal_k: type={latest_signal_k.bar_type.name} score={latest_signal_k.score:.3f}")
        else:
            _log("  signal_k: None")

        # Step 2: Support/Resistance
        _log("Step 2/5: support_resistance...")
        sr_result = analyze_support_resistance(
            bars,
            ema_period=cfg_a.support_resistance.ema_period,
            swing_order=cfg_a.support_resistance.swing_order,
            round_step=cfg_a.support_resistance.round_number_step
        )
        _log(f"  sr: {len(sr_result.levels)} levels")

        # Step 3: Market Context
        _log("Step 3/5: market_context...")
        context_result = analyze_context(
            bars, signal_k_results.apply(lambda x: x.score),
            ema_period=cfg_a.support_resistance.ema_period,
            threshold=cfg_a.market_context.always_in_threshold
        )
        _log(f"  context: state={context_result.state} always_in={context_result.always_in.direction}")

        # Step 4: Key Zones
        _log("Step 4/5: key_zones...")
        zones_result = analyze_key_zones(
            bars,
            sr_result.levels,
            range_lookback=cfg_a.key_zones.range_lookback,
            range_touch_min=cfg_a.key_zones.range_touch_min,
            confluence_threshold_pct=cfg_a.key_zones.confluence_threshold_pct
        )
        _log(f"  zones: {len(zones_result.zones)} zones")

        # Step 5: Trade Signals
        _log("Step 5/5: trade_signals...")
        current_bar = bars.iloc[-1] if len(bars) > 0 else None
        trade_signals = compute_trade_signals(
            bars, latest_signal_k, signal_k_results.apply(lambda x: x.score),
            context_result, zones_result
        )
        _log(f"  signals: {len(trade_signals)} signals")

        result = AnalysisResult(
            symbol=symbol,
            timeframe=timeframe,
            current_bar=current_bar,
            signal_k=latest_signal_k,
            sr=sr_result,
            zones=zones_result,
            context=context_result,
            timestamp=bars.index[-1] if len(bars) > 0 else None,
            trade_signals=trade_signals
        )

        key = f"{symbol}_{timeframe}"
        self._prev_results[key] = result
        _log("=== analyze DONE ===\n")
        self.analysis_ready.emit(result)
        return result

    def get_previous(self, symbol: str, timeframe: str) -> AnalysisResult | None:
        return self._prev_results.get(f"{symbol}_{timeframe}")
