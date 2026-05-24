from dataclasses import dataclass
from enum import Enum, auto
import pandas as pd
import numpy as np

class BarType(Enum):
    STRONG_TREND = auto()
    REVERSAL = auto()
    OUTSIDE = auto()
    INSIDE = auto()
    BULLISH_PIN = auto()
    BEARISH_PIN = auto()
    DOJI = auto()
    NORMAL = auto()

@dataclass
class SignalKResult:
    bar_type: BarType
    is_bullish: bool
    score: float
    body_ratio: float
    close_position: float
    upper_wick_ratio: float
    lower_wick_ratio: float

def analyze_single_bar(bar: pd.Series, prev_bar: pd.Series | None,
                       recent_bars: pd.DataFrame) -> SignalKResult:
    open_, high, low, close = bar['open'], bar['high'], bar['low'], bar['close']
    body = abs(close - open_)
    total_range = high - low

    if total_range <= 0:
        return SignalKResult(BarType.DOJI, close >= open_, 0.0, 0.0, 0.5, 0.0, 0.0)

    is_bullish = close > open_

    body_ratio = body / total_range
    close_position = (close - low) / total_range
    upper_wick = high - max(open_, close)
    lower_wick = min(open_, close) - low
    upper_wick_ratio = upper_wick / total_range
    lower_wick_ratio = lower_wick / total_range

    # Average body of last 5 bars
    if len(recent_bars) >= 5:
        avg_body = np.mean([
            abs(b.close - b.open) / max(b.high - b.low, 1e-8)
            for b in recent_bars.tail(5).itertuples()
        ])
    else:
        avg_body = 0.3
    body_size_ratio = body_ratio / max(avg_body, 0.001)

    # Bar type classification (priority order)
    bar_type = BarType.NORMAL

    # Doji
    if body_ratio < 0.10:
        bar_type = BarType.DOJI
    # Pin bars
    elif is_bullish and lower_wick >= 3 * body and upper_wick < body * 0.3:
        bar_type = BarType.BULLISH_PIN
    elif not is_bullish and upper_wick >= 3 * body and lower_wick < body * 0.3:
        bar_type = BarType.BEARISH_PIN
    # Outside bar
    elif prev_bar is not None and high > prev_bar['high'] and low < prev_bar['low']:
        bar_type = BarType.OUTSIDE
    # Inside bar
    elif prev_bar is not None and high < prev_bar['high'] and low > prev_bar['low']:
        bar_type = BarType.INSIDE
    # Strong trend bar
    elif body_ratio >= 0.70 and body_size_ratio >= 1.5:
        bar_type = BarType.STRONG_TREND
    # Reversal bar
    elif prev_bar is not None:
        prev_bull = prev_bar['close'] > prev_bar['open']
        if is_bullish != prev_bull and close_position > 0.5:
            bar_type = BarType.REVERSAL

    # Strength score: positive=bullish, negative=bearish
    direction = 1 if is_bullish else -1
    components = {
        "body": direction * (body_ratio - 0.5) * 2,
        "close": (close_position - 0.5) * 2,
        "size": direction * np.clip(body_size_ratio - 1.0, -1.0, 1.0),
        "wick": (lower_wick_ratio - upper_wick_ratio)
    }
    weights = {"body": 0.30, "close": 0.25, "size": 0.25, "wick": 0.20}
    score = sum(components[k] * weights[k] for k in weights)
    score = np.clip(score, -1.0, 1.0)

    return SignalKResult(
        bar_type=bar_type,
        is_bullish=is_bullish,
        score=score,
        body_ratio=body_ratio,
        close_position=close_position,
        upper_wick_ratio=upper_wick_ratio,
        lower_wick_ratio=lower_wick_ratio
    )

def analyze_signal_k(bars: pd.DataFrame, lookback: int = 5) -> pd.Series:
    """Analyze all bars and return a Series of SignalKResult + scores."""
    results = []
    for i in range(len(bars)):
        bar = bars.iloc[i]
        prev = bars.iloc[i - 1] if i > 0 else None
        recent = bars.iloc[max(0, i - lookback):i]
        result = analyze_single_bar(bar, prev, recent)
        results.append(result)
    return pd.Series(results, index=bars.index)
