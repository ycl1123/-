from dataclasses import dataclass, field
import math
import pandas as pd
import numpy as np
from analysis.utils import calc_ema, find_swing_points

@dataclass
class SRLevel:
    price: float
    label: str
    level_type: str  # "resistance", "support", "ema", "pivot", "round"
    strength: float  # 0.0 - 1.0

@dataclass
class SRResult:
    levels: list[SRLevel]

def analyze_support_resistance(bars: pd.DataFrame, ema_period: int = 20,
                               swing_order: int = 5, round_step: float = 50) -> SRResult:
    levels = []
    close = bars['close'].values
    current = close[-1]

    # 1. Swing highs/lows
    swing_highs, swing_lows = find_swing_points(bars, swing_order)
    # Recent swing points (last 10)
    for sh in swing_highs[-5:]:
        if sh['price'] > current:
            levels.append(SRLevel(sh['price'], f"波段高点", "resistance", 0.6))
        else:
            levels.append(SRLevel(sh['price'], f"波段高点(已破)", "support", 0.4))
    for sl in swing_lows[-5:]:
        if sl['price'] < current:
            levels.append(SRLevel(sl['price'], f"波段低点", "support", 0.6))
        else:
            levels.append(SRLevel(sl['price'], f"波段低点(已破)", "resistance", 0.4))

    # 2. 20 EMA
    ema = calc_ema(close, ema_period)
    ema_last = ema[-1] if not np.isnan(ema[-1]) else None
    if ema_last is not None:
        ema_type = "support" if ema_last < current else "resistance"
        levels.append(SRLevel(ema_last, f"{ema_period}EMA", ema_type, 0.7))

    # 3. Previous day high/low/close (from daily bars if available, or estimate)
    prev_day_high = bars.iloc[-2]['high'] if len(bars) >= 2 else None
    prev_day_low = bars.iloc[-2]['low'] if len(bars) >= 2 else None
    prev_day_close = bars.iloc[-2]['close'] if len(bars) >= 2 else None

    if prev_day_high and prev_day_low and prev_day_close:
        # Pivot points
        pp = (prev_day_high + prev_day_low + prev_day_close) / 3
        r1 = 2 * pp - prev_day_low
        r2 = pp + (prev_day_high - prev_day_low)
        r3 = r2 + (prev_day_high - prev_day_low)
        s1 = 2 * pp - prev_day_high
        s2 = pp - (prev_day_high - prev_day_low)
        s3 = s2 - (prev_day_high - prev_day_low)

        for name, price in [("PP", pp), ("R1", r1), ("R2", r2), ("R3", r3),
                             ("S1", s1), ("S2", s2), ("S3", s3)]:
            lt = "resistance" if price > current else "support"
            levels.append(SRLevel(price, name, lt, 0.5))

    # 4. Previous bar's high/low
    if len(bars) >= 2:
        prev_high = bars.iloc[-2]['high']
        prev_low = bars.iloc[-2]['low']
        levels.append(SRLevel(prev_high, "前K高点", "resistance", 0.3))
        levels.append(SRLevel(prev_low, "前K低点", "support", 0.3))

    # 5. Round numbers
    base = (current // round_step) * round_step
    for i in range(-3, 4):
        rn = base + i * round_step
        if rn != current:
            lt = "resistance" if rn > current else "support"
            levels.append(SRLevel(rn, f"整数关口 {rn:.0f}", lt, 0.35))

    # 6. Today's open
    if len(bars) >= 1:
        today_open = bars.iloc[-1]['open']
        lt = "support" if today_open < current else "resistance"
        levels.append(SRLevel(today_open, "今开", lt, 0.4))

    # Sort by price descending
    levels.sort(key=lambda x: x.price, reverse=True)
    return SRResult(levels=levels)
