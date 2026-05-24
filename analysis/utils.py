import numpy as np
import pandas as pd

def calc_ema(series: np.ndarray | pd.Series, period: int) -> np.ndarray:
    """Exponential Moving Average."""
    if isinstance(series, pd.Series):
        series = series.values
    result = np.empty_like(series)
    result[:] = np.nan
    if len(series) < period:
        return result
    alpha = 2 / (period + 1)
    # Seed with SMA
    result[period - 1] = np.mean(series[:period])
    for i in range(period, len(series)):
        result[i] = alpha * series[i] + (1 - alpha) * result[i - 1]
    return result

def calc_atr(df: pd.DataFrame, period: int = 14) -> np.ndarray:
    """Average True Range."""
    high, low, close = df['high'].values, df['low'].values, df['close'].values
    result = np.empty_like(high)
    result[:] = np.nan
    if len(df) < 2:
        return result
    tr = np.maximum(
        high[1:] - low[1:],
        np.maximum(
            np.abs(high[1:] - close[:-1]),
            np.abs(low[1:] - close[:-1])
        )
    )
    result[1] = tr[0]
    alpha = 2 / (period + 1)
    for i in range(2, len(high)):
        result[i] = alpha * tr[i - 1] + (1 - alpha) * result[i - 1]
    return result

def linear_slope(series: np.ndarray) -> float:
    """Linear regression slope of last N values."""
    x = np.arange(len(series))
    return np.polyfit(x, series, 1)[0]

def calc_overlap_ratio(df: pd.DataFrame, lookback: int = 10) -> float:
    """Average overlap ratio between consecutive bars."""
    if len(df) < 2:
        return 0.5
    ratios = []
    n = min(lookback, len(df) - 1)
    for i in range(1, n + 1):
        prev = df.iloc[-i - 1]
        curr = df.iloc[-i]
        overlap = min(prev['high'], curr['high']) - max(prev['low'], curr['low'])
        avg_range = ((prev['high'] - prev['low']) + (curr['high'] - curr['low'])) / 2
        if avg_range > 0:
            ratios.append(max(0, overlap / avg_range))
    return float(np.mean(ratios)) if ratios else 0.5

def find_swing_points(df: pd.DataFrame, order: int = 5) -> tuple[list, list]:
    """Find local swing highs and lows."""
    highs = df['high'].values
    lows = df['low'].values
    n = len(highs)

    if n < 2 * order + 1:
        return [], []

    swing_highs = []
    for i in range(order, n - order):
        if highs[i] == max(highs[i - order:i + order + 1]):
            swing_highs.append({
                'index': i,
                'price': highs[i],
                'time': df.index[i]
            })

    swing_lows = []
    for i in range(order, n - order):
        if lows[i] == min(lows[i - order:i + order + 1]):
            swing_lows.append({
                'index': i,
                'price': lows[i],
                'time': df.index[i]
            })

    return swing_highs, swing_lows

def count_consecutive_same_direction(df: pd.DataFrame, lookback: int = 10) -> tuple[int, int]:
    """Count max consecutive bullish/bearish bars in recent lookback."""
    recent = df.tail(lookback)
    if len(recent) == 0:
        return 0, 0

    max_bull = max_bear = 0
    curr_bull = curr_bear = 0
    for _, bar in recent.iterrows():
        if bar['close'] > bar['open']:
            curr_bull += 1
            curr_bear = 0
        elif bar['close'] < bar['open']:
            curr_bear += 1
            curr_bull = 0
        max_bull = max(max_bull, curr_bull)
        max_bear = max(max_bear, curr_bear)
    return max_bull, max_bear
