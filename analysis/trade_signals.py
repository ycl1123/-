"""Trade signal generation — Al Brooks 4-signal strategy (backtest-proven 44%+ WR on MT5).

Four core signals:
  1. TR boundary fade — TRADING_RANGE only, reversal bars at boundaries
  2. EMA pullback — trend only, strong trend K at EMA in trend direction
  3. Strong trend K continuation — trend only, strong K in Always In direction
  4. TR boundary with strong K — backup for TR mode (strong K at boundaries)
"""
from dataclasses import dataclass
from enum import Enum
import numpy as np
import pandas as pd

from analysis.signal_k import SignalKResult, BarType
from analysis.market_context import MarketContextResult
from analysis.key_zones import KeyZonesResult
from analysis.utils import calc_ema, calc_atr


class SignalStrength(Enum):
    STRONG = 1
    MEDIUM = 2
    WEAK = 3


class SignalType(Enum):
    TREND_STRONG_LONG = "趋势跟踪多"
    TREND_STRONG_SHORT = "趋势跟踪空"
    EMA_PULLBACK_LONG = "EMA回调做多"
    EMA_BOUNCE_SHORT = "EMA反弹做空"
    TR_LOWER_LONG = "TR下沿做多"
    TR_UPPER_SHORT = "TR上沿做空"


DIR_MAP = {'L': '多头', 'S': '空头'}

# ── Strategy parameters (backtest-verified) ──
TARGET_RR = 1.5          # 1.5:1 risk/reward
STOP_BUFFER = 0.3        # ATR multiplier for stop buffer beyond signal bar
MAX_STOP_ATR = 3.0       # max stop distance in ATR
MIN_STOP_ATR = 0.2       # min stop distance in ATR
TR_BOUNDARY_PCT = 0.003  # 0.3% = near boundary
EMA_NEAR_PCT = 0.01      # 1% = near EMA


@dataclass
class TradeSignal:
    signal_type: SignalType
    direction: str          # 'L' or 'S'
    strength: SignalStrength
    entry_price: float
    stop_price: float
    target_price: float
    stop_distance: float
    risk_reward_ratio: float
    confidence: float
    reason: str
    bar_time: str = ""
    resonance_count: int = 0
    tactical_layer: str = ""


# ── Helpers ──

def _bar_quality(sk: SignalKResult) -> float:
    """Score signal K bar quality 0-1."""
    score = 0.0
    if sk.body_ratio >= 0.70: score += 0.3
    elif sk.body_ratio >= 0.50: score += 0.15
    if sk.close_position >= 0.85 or sk.close_position <= 0.15: score += 0.25
    if max(sk.upper_wick_ratio, sk.lower_wick_ratio) < 0.2: score += 0.25
    elif max(sk.upper_wick_ratio, sk.lower_wick_ratio) < 0.35: score += 0.1
    return min(score, 1.0)


def _tr_boundaries(bars: pd.DataFrame, lookback: int = 20) -> tuple:
    """Trading range: (is_tr, upper, lower)."""
    recent = bars.tail(lookback)
    upper = recent['high'].max()
    lower = recent['low'].min()
    touches_upper = int(sum(recent['high'] >= upper * 0.998))
    touches_lower = int(sum(recent['low'] <= lower * 1.002))
    is_tr = touches_upper >= 2 and touches_lower >= 2
    return is_tr, upper, lower


def _near_boundary(price: float, boundary: float) -> bool:
    return abs(price - boundary) / boundary < TR_BOUNDARY_PCT


def _near_ema(price: float, ema_val: float) -> bool:
    if ema_val <= 0:
        return False
    return abs(price - ema_val) / ema_val < EMA_NEAR_PCT


def _ema_slope_ok(bars: pd.DataFrame, direction: str) -> bool:
    """Check if 20EMA slope aligns with direction."""
    close = bars['close'].values
    ema = calc_ema(close, 20)
    if len(ema) < 6:
        return False
    return ema[-1] > ema[-5] if direction == 'LONG' else ema[-1] < ema[-5]


def _make_signal(stype, direction, entry, stop, target, conf, reason, strength) -> TradeSignal:
    stop_dist = abs(entry - stop)
    rr = abs(target - entry) / max(stop_dist, 0.001)
    return TradeSignal(
        signal_type=stype, direction=direction, strength=strength,
        entry_price=round(entry, 1), stop_price=round(stop, 1),
        target_price=round(target, 1), stop_distance=round(stop_dist, 1),
        risk_reward_ratio=round(rr, 1), confidence=round(min(conf, 1.0), 2),
        reason=reason
    )


# ═════════════════════════════════════════════════════════════
#  Main signal generation
# ═════════════════════════════════════════════════════════════

def compute_trade_signals(
    bars: pd.DataFrame,
    signal_k: SignalKResult | None,
    all_scores: pd.Series,
    context: MarketContextResult | None,
    zones: KeyZonesResult | None,
) -> list[TradeSignal]:
    """
    Al Brooks 4-signal strategy (backtest-verified on XAUUSD M2).

    Signal 1 — TR boundary fade: TRADING_RANGE + reversal at boundary
    Signal 2 — EMA pullback: trend + strong K at EMA + EMA slope aligned
    Signal 3 — Strong trend K: trend + strong K in Always In direction
    Signal 4 — TR boundary with strong K: backup TR signal (strong K at boundary)
    """
    if signal_k is None or context is None or len(bars) < 50:
        return []

    signals = []
    close = bars['close'].values
    entry = close[-1]
    bar = bars.iloc[-1]
    sig = signal_k

    # ── Pre-compute ──
    atr_arr = calc_atr(bars, 14)
    current_atr = atr_arr[-1] if not np.isnan(atr_arr[-1]) else 3.0
    if current_atr < 1.0:
        current_atr = 3.0

    ema_arr = calc_ema(close, 20)
    ema_now = ema_arr[-1] if not np.isnan(ema_arr[-1]) else close[-1]

    q = _bar_quality(sig)
    is_tr, tr_high, tr_low = _tr_boundaries(bars)

    state = context.state
    ai_dir = context.always_in.direction
    is_trend = state in ("STRONG_TREND", "WEAK_TREND")
    is_range = state == "TRADING_RANGE"

    # ═══════════════════════════════════════════════════════
    # Signal 1: TR boundary fade (TRADING_RANGE only)
    #   Short at upper boundary + bearish reversal bar
    #   Long at lower boundary + bullish reversal bar
    # ═══════════════════════════════════════════════════════
    if is_range and is_tr:
        # Short at TR upper
        if (_near_boundary(entry, tr_high) and
            sig.bar_type == BarType.REVERSAL and not sig.is_bullish):
            stop = bar['high'] + current_atr * STOP_BUFFER
            target = entry - abs(entry - stop) * TARGET_RR
            signals.append(_make_signal(
                SignalType.TR_UPPER_SHORT, 'S', entry, stop, target, q,
                f"TR上沿做空 | 区间:{tr_low:.0f}-{tr_high:.0f} | 质量:{q:.0%}",
                SignalStrength.STRONG if q >= 0.6 else SignalStrength.MEDIUM
            ))

        # Long at TR lower
        if (_near_boundary(entry, tr_low) and
            sig.bar_type == BarType.REVERSAL and sig.is_bullish):
            stop = bar['low'] - current_atr * STOP_BUFFER
            target = entry + abs(entry - stop) * TARGET_RR
            signals.append(_make_signal(
                SignalType.TR_LOWER_LONG, 'L', entry, stop, target, q,
                f"TR下沿做多 | 区间:{tr_low:.0f}-{tr_high:.0f} | 质量:{q:.0%}",
                SignalStrength.STRONG if q >= 0.6 else SignalStrength.MEDIUM
            ))

    # ═══════════════════════════════════════════════════════
    # Signal 2: EMA pullback (trend only)
    #   Price near 20EMA + EMA slope in trend direction
    #   + strong trend K bar aligned
    # ═══════════════════════════════════════════════════════
    if is_trend and ai_dir in ('LONG', 'SHORT'):
        near_ema = _near_ema(entry, ema_now)
        ema_ok = _ema_slope_ok(bars, ai_dir)
        is_strong_k = sig.bar_type == BarType.STRONG_TREND

        if near_ema and ema_ok and is_strong_k:
            if ai_dir == 'LONG' and sig.is_bullish:
                stop = bar['low'] - current_atr * STOP_BUFFER
                target = entry + abs(entry - stop) * TARGET_RR
                ema_dist = abs(entry - ema_now) / ema_now
                signals.append(_make_signal(
                    SignalType.EMA_PULLBACK_LONG, 'L', entry, stop, target, q + 0.05,
                    f"EMA回调做多 | 距EMA:{ema_dist:.2%} | 质量:{q:.0%}",
                    SignalStrength.STRONG if q >= 0.6 else SignalStrength.MEDIUM
                ))

            elif ai_dir == 'SHORT' and not sig.is_bullish:
                stop = bar['high'] + current_atr * STOP_BUFFER
                target = entry - abs(entry - stop) * TARGET_RR
                ema_dist = abs(entry - ema_now) / ema_now
                signals.append(_make_signal(
                    SignalType.EMA_BOUNCE_SHORT, 'S', entry, stop, target, q + 0.05,
                    f"EMA反弹做空 | 距EMA:{ema_dist:.2%} | 质量:{q:.0%}",
                    SignalStrength.STRONG if q >= 0.6 else SignalStrength.MEDIUM
                ))

    # ═══════════════════════════════════════════════════════
    # Signal 3: Strong trend K continuation (trend only)
    #   Strong trend K in Always In direction = continuation
    # ═══════════════════════════════════════════════════════
    if is_trend and ai_dir in ('LONG', 'SHORT'):
        if sig.bar_type == BarType.STRONG_TREND:
            if ai_dir == 'LONG' and sig.is_bullish:
                stop = bar['low'] - current_atr * STOP_BUFFER
                target = entry + abs(entry - stop) * TARGET_RR
                signals.append(_make_signal(
                    SignalType.TREND_STRONG_LONG, 'L', entry, stop, target, q + 0.1,
                    f"趋势跟踪多 | Always In=LONG | 实体:{sig.body_ratio:.0%} | 质量:{q:.0%}",
                    SignalStrength.STRONG
                ))

            elif ai_dir == 'SHORT' and not sig.is_bullish:
                stop = bar['high'] + current_atr * STOP_BUFFER
                target = entry - abs(entry - stop) * TARGET_RR
                signals.append(_make_signal(
                    SignalType.TREND_STRONG_SHORT, 'S', entry, stop, target, q + 0.1,
                    f"趋势跟踪空 | Always In=SHORT | 实体:{sig.body_ratio:.0%} | 质量:{q:.0%}",
                    SignalStrength.STRONG
                ))

    # ═══════════════════════════════════════════════════════
    # Signal 4: TR boundary with strong K (TR backup)
    #   Strong trend K at TR boundary = confirm fade
    # ═══════════════════════════════════════════════════════
    if is_range and is_tr:
        if sig.bar_type == BarType.STRONG_TREND:
            if _near_boundary(entry, tr_low) and sig.is_bullish:
                stop = bar['low'] - current_atr * STOP_BUFFER
                target = entry + abs(entry - stop) * TARGET_RR
                signals.append(_make_signal(
                    SignalType.TR_LOWER_LONG, 'L', entry, stop, target, q + 0.05,
                    f"TR下沿做多 | 区间:{tr_low:.0f}-{tr_high:.0f} | 质量:{q:.0%}",
                    SignalStrength.STRONG if q >= 0.6 else SignalStrength.MEDIUM
                ))

            elif _near_boundary(entry, tr_high) and not sig.is_bullish:
                stop = bar['high'] + current_atr * STOP_BUFFER
                target = entry - abs(entry - stop) * TARGET_RR
                signals.append(_make_signal(
                    SignalType.TR_UPPER_SHORT, 'S', entry, stop, target, q + 0.05,
                    f"TR上沿做空 | 区间:{tr_low:.0f}-{tr_high:.0f} | 质量:{q:.0%}",
                    SignalStrength.STRONG if q >= 0.6 else SignalStrength.MEDIUM
                ))

    # ── Validate ──
    valid = []
    for s in signals:
        stop_dist = s.stop_distance
        if stop_dist < current_atr * MIN_STOP_ATR:
            continue
        if stop_dist > current_atr * MAX_STOP_ATR:
            continue
        if s.direction == 'L':
            if s.stop_price < s.entry_price < s.target_price:
                valid.append(s)
        elif s.direction == 'S':
            if s.stop_price > s.entry_price > s.target_price:
                valid.append(s)

    strength_order = {SignalStrength.STRONG: 0, SignalStrength.MEDIUM: 1, SignalStrength.WEAK: 2}
    valid.sort(key=lambda s: (strength_order[s.strength], -s.confidence))
    return valid
