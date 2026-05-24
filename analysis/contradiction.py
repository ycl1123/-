"""
Contradiction Analysis Module — 矛盾分析模块
==============================================
Based on Mao's "On Contradiction" (矛盾论), this module analyzes:
1. Primary contradiction structure (trend vs range contradiction)
2. Internal factors (内因) — bar strength, pullback depth, momentum decay
3. External factors (外因) — key S/R proximity, EMA, round numbers
4. Contradiction transformation conditions (矛盾转化条件)
5. Antagonistic contradiction detection (对抗性矛盾 — climax/failed breakout)
"""
from dataclasses import dataclass, field
from enum import Enum, auto
import numpy as np
import pandas as pd

from analysis.utils import calc_ema, calc_atr, calc_overlap_ratio


class ContradictionType(Enum):
    TREND_DOMINANT = "趋势主导"        # One side dominates — primary contradiction
    RANGE_STALEMATE = "震荡僵持"       # Neither side dominates — balanced
    TRANSFORMING = "矛盾转化中"         # Contradiction is shifting
    ANTAGONISTIC = "对抗性爆发"        # Contradiction resolving explosively


class TransformationRisk(Enum):
    NONE = "无转化迹象"
    WEAK_SIGNAL = "弱转化信号"         # Internal only or external only
    MODERATE = "中等转化概率"          # Internal + external, not confirmed
    HIGH = "高转化概率"               # Internal + external aligned, waiting signal K


@dataclass
class InternalFactors:
    """内因 — 多空力量对比的内在变化"""
    bar_strength_decay: float       # 0-1, 1=K线实体在缩小（趋势减弱）
    pullback_deepening: float       # 0-1, 1=回调在加深
    consecutive_opposite: int       # 连续反向K线数量
    momentum_divergence: float      # 0-1, 1=动量明显背离
    body_shadow_ratio_change: float # 实体/影线比变化，负数=影线变长


@dataclass
class ExternalFactors:
    """外因 — 关键价位的外部条件"""
    near_major_sr: bool             # 是否接近主要支撑/阻力
    near_ema: bool                  # 是否接近20EMA
    near_round_number: bool         # 是否接近整数关口
    near_tr_boundary: bool          # 是否接近震荡区间边界
    zone_confluence: int            # 共振区域数量


@dataclass
class ContradictionResult:
    """矛盾分析结果"""
    type: ContradictionType
    transformation_risk: TransformationRisk
    internal: InternalFactors
    external: ExternalFactors
    dominant_side: str              # "BULL" / "BEAR" / "NEUTRAL"
    contradiction_intensity: float  # 0-1, overall contradiction tension
    transformation_confidence: float  # 0-1, probability of imminent shift
    summary: str


def analyze_contradiction(
    bars: pd.DataFrame,
    signal_k_scores: pd.Series,
    sr_levels: list,
    zones: list,
    ema_period: int = 20,
    lookback: int = 20,
) -> ContradictionResult:
    """
    Analyze the contradiction structure of the current market.

    Returns a ContradictionResult describing:
    - What type of contradiction is dominant
    - Whether conditions are aligning for a transformation
    - The internal and external factors at play
    """
    close = bars['close'].values
    high = bars['high'].values
    low = bars['low'].values
    n = len(bars)

    if n < lookback:
        return _empty_result()

    # === Internal Factors (内因) ===

    # 1. Bar strength decay — are trend bars getting smaller?
    recent_bodies = np.array([
        abs(close[i] - bars['open'].values[i]) / max(high[i] - low[i], 1e-8)
        for i in range(max(0, n - lookback), n)
    ])
    if len(recent_bodies) >= 10:
        first_half = np.mean(recent_bodies[:len(recent_bodies)//2])
        second_half = np.mean(recent_bodies[len(recent_bodies)//2:])
        bar_strength_decay = np.clip((first_half - second_half) / max(first_half, 0.01) + 0.5, 0, 1)
    else:
        bar_strength_decay = 0.5

    # 2. Pullback deepening — are retracements getting deeper?
    ema = calc_ema(close, ema_period)
    if not np.isnan(ema[-1]):
        recent_dists = np.abs(close[-10:] - ema[-10:]) / close[-10:]
        if len(recent_dists) >= 6:
            early = np.mean(recent_dists[:len(recent_dists)//2])
            late = np.mean(recent_dists[len(recent_dists)//2:])
            pullback_deepening = np.clip((late - early) / max(early, 0.001) + 0.5, 0, 1)
        else:
            pullback_deepening = 0.5
    else:
        pullback_deepening = 0.5

    # 3. Consecutive opposite bars
    max_bull = max_bear = 0
    curr_bull = curr_bear = 0
    for i in range(n - lookback, n):
        if bars['close'].values[i] > bars['open'].values[i]:
            curr_bull += 1; curr_bear = 0
        elif bars['close'].values[i] < bars['open'].values[i]:
            curr_bear += 1; curr_bull = 0
        max_bull = max(max_bull, curr_bull)
        max_bear = max(max_bear, curr_bear)
    consecutive_opposite = max_bear if signal_k_scores.iloc[-5:].mean() > 0 else max_bull

    # 4. Momentum divergence — price making new highs/lows but momentum weakening
    if len(signal_k_scores) >= 10 and len(close) >= 10:
        price_direction = close[-1] - close[-10]
        momentum_direction = signal_k_scores.iloc[-5:].mean() - signal_k_scores.iloc[-10:-5].mean()
        # Divergence: price going one way, momentum going the other
        momentum_divergence = np.clip(abs(price_direction / max(close[-1], 1e-8) * 100) -
                                       abs(momentum_direction) * 0.5, 0, 1)
    else:
        momentum_divergence = 0.0

    # 5. Body/shadow ratio change — are wicks getting longer relative to bodies?
    wick_ratios = []
    for i in range(max(0, n - lookback), n):
        b = bars.iloc[i]
        total_range = b['high'] - b['low']
        if total_range > 0:
            body = abs(b['close'] - b['open'])
            wick_ratios.append(1.0 - body / total_range)
    if len(wick_ratios) >= 10:
        early_wr = np.mean(wick_ratios[:len(wick_ratios)//2])
        late_wr = np.mean(wick_ratios[len(wick_ratios)//2:])
        body_shadow_ratio_change = (late_wr - early_wr)  # positive = more wicks = uncertainty
    else:
        body_shadow_ratio_change = 0.0

    internal = InternalFactors(
        bar_strength_decay=round(bar_strength_decay, 3),
        pullback_deepening=round(pullback_deepening, 3),
        consecutive_opposite=consecutive_opposite,
        momentum_divergence=round(momentum_divergence, 3),
        body_shadow_ratio_change=round(body_shadow_ratio_change, 3),
    )

    # === External Factors (外因) ===

    current_price = close[-1]

    # Proximity to S/R levels
    near_major_sr = False
    for sl in (sr_levels or []):
        if hasattr(sl, 'price'):
            dist_pct = abs(sl.price - current_price) / current_price
            if dist_pct < 0.002:  # within 0.2%
                near_major_sr = True
                break

    # Proximity to EMA
    near_ema = False
    if not np.isnan(ema[-1]):
        ema_dist = abs(current_price - ema[-1]) / current_price
        near_ema = ema_dist < 0.0015

    # Proximity to round number
    round_step = 50
    base = (current_price // round_step) * round_step
    near_round_number = abs(current_price - base) / current_price < 0.001

    # Proximity to TR boundary
    near_tr_boundary = False
    for z in (zones or []):
        if hasattr(z, 'zone_type') and z.zone_type == 'trading_range':
            if hasattr(z, 'upper') and hasattr(z, 'lower'):
                if (abs(current_price - z.upper) / current_price < 0.002 or
                    abs(current_price - z.lower) / current_price < 0.002):
                    near_tr_boundary = True
                    break

    # Zone confluence count
    zone_confluence = 0
    for z in (zones or []):
        if hasattr(z, 'upper') and hasattr(z, 'lower'):
            if z.lower <= current_price <= z.upper:
                zone_confluence += 1

    external = ExternalFactors(
        near_major_sr=near_major_sr,
        near_ema=near_ema,
        near_round_number=near_round_number,
        near_tr_boundary=near_tr_boundary,
        zone_confluence=zone_confluence,
    )

    # === Determine Contradiction Type ===

    overlap = calc_overlap_ratio(bars, 10)
    recent_scores = signal_k_scores.iloc[-lookback:]
    mean_score = recent_scores.mean() if len(recent_scores) > 0 else 0
    abs_scores = recent_scores.abs().mean()

    # Count climax bars (large range + strong score)
    atr_arr = calc_atr(bars, 14)
    current_atr = atr_arr[-1] if not np.isnan(atr_arr[-1]) else 3.0
    climax_count = 0
    for i in range(max(0, n - 10), n):
        bar_range = bars.iloc[i]['high'] - bars.iloc[i]['low']
        if bar_range > current_atr * 1.8:
            climax_count += 1

    if climax_count >= 3:
        contradiction_type = ContradictionType.ANTAGONISTIC
    elif overlap > 0.6 and abs(mean_score) < 0.25:
        contradiction_type = ContradictionType.RANGE_STALEMATE
    elif abs(mean_score) > 0.3 and overlap < 0.45:
        contradiction_type = ContradictionType.TREND_DOMINANT
    else:
        contradiction_type = ContradictionType.TRANSFORMING

    # === Dominant Side ===
    if mean_score > 0.15:
        dominant_side = "BULL"
    elif mean_score < -0.15:
        dominant_side = "BEAR"
    else:
        dominant_side = "NEUTRAL"

    # === Transformation Risk ===
    internal_signals = sum([
        internal.bar_strength_decay > 0.6,
        internal.pullback_deepening > 0.6,
        internal.consecutive_opposite >= 3,
        internal.momentum_divergence > 0.5,
        internal.body_shadow_ratio_change > 0.2,
    ])
    external_signals = sum([
        external.near_major_sr,
        external.near_ema,
        external.near_round_number,
        external.near_tr_boundary,
        external.zone_confluence >= 2,
    ])

    if internal_signals >= 3 and external_signals >= 2:
        transformation_risk = TransformationRisk.HIGH
    elif internal_signals >= 2 and external_signals >= 1:
        transformation_risk = TransformationRisk.MODERATE
    elif internal_signals >= 2 or external_signals >= 2:
        transformation_risk = TransformationRisk.WEAK_SIGNAL
    else:
        transformation_risk = TransformationRisk.NONE

    # === Intensity and Confidence ===
    intensity = (abs_scores * 0.4 + (1 - overlap) * 0.3 +
                 (climax_count / 5) * 0.3)
    intensity = np.clip(intensity, 0, 1)

    trans_conf = (internal_signals / 5 * 0.6 + external_signals / 5 * 0.4)
    if contradiction_type == ContradictionType.ANTAGONISTIC:
        trans_conf = min(trans_conf + 0.3, 1.0)

    # === Summary ===
    summaries = {
        ContradictionType.TREND_DOMINANT: f"{'多头' if dominant_side == 'BULL' else '空头'}主导趋势，"
                                          f"内因信号{internal_signals}/5 外因信号{external_signals}/5",
        ContradictionType.RANGE_STALEMATE: f"多空在区间内相持，共振区{zone_confluence}个",
        ContradictionType.TRANSFORMING: f"矛盾正在转化，转化置信度{trans_conf:.0%}，"
                                         f"内因{internal_signals}/5 外因{external_signals}/5",
        ContradictionType.ANTAGONISTIC: f"对抗性矛盾爆发（{climax_count}根高潮K线），"
                                         f"反转概率高",
    }

    return ContradictionResult(
        type=contradiction_type,
        transformation_risk=transformation_risk,
        internal=internal,
        external=external,
        dominant_side=dominant_side,
        contradiction_intensity=round(intensity, 3),
        transformation_confidence=round(trans_conf, 3),
        summary=summaries.get(contradiction_type, "未知状态"),
    )


def _empty_result() -> ContradictionResult:
    return ContradictionResult(
        type=ContradictionType.RANGE_STALEMATE,
        transformation_risk=TransformationRisk.NONE,
        internal=InternalFactors(0.5, 0.5, 0, 0.0, 0.0),
        external=ExternalFactors(False, False, False, False, 0),
        dominant_side="NEUTRAL",
        contradiction_intensity=0.0,
        transformation_confidence=0.0,
        summary="数据不足，无法分析矛盾结构",
    )
