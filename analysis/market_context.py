from dataclasses import dataclass
import numpy as np
import pandas as pd
from analysis.utils import calc_ema, linear_slope, calc_overlap_ratio, count_consecutive_same_direction
from analysis.contradiction import (
    analyze_contradiction, ContradictionResult, ContradictionType, TransformationRisk,
)

@dataclass
class AlwaysInResult:
    direction: str  # "LONG", "SHORT", "NEUTRAL"
    confidence: float
    ema_slope: float
    price_ema_score: float
    momentum_score: float

@dataclass
class MarketContextResult:
    state: str  # "STRONG_TREND", "WEAK_TREND", "CHANNEL", "TRADING_RANGE"
    always_in: AlwaysInResult
    overlap_ratio: float
    trend_bar_ratio: float
    # Contradiction-aware fields (矛盾论增强)
    contradiction: ContradictionResult | None = None
    state_transition_risk: str = ""  # "NONE" / "TREND_WEAKENING" / "BREAKOUT_IMMINENT" / "REVERSAL_LIKELY"
    transformation_conditions_met: int = 0  # 0-5, how many transformation conditions align

def analyze_context(bars: pd.DataFrame, signal_k_scores: pd.Series,
                    ema_period: int = 20, threshold: float = 0.3) -> MarketContextResult:
    close = bars['close'].values
    ema = calc_ema(close, ema_period)
    ema_valid = ema[~np.isnan(ema)]

    # 1. EMA slope
    if len(ema_valid) >= 5:
        ema_slope = linear_slope(ema_valid[-20:]) if len(ema_valid) >= 20 else linear_slope(ema_valid[-5:])
        # Normalize to roughly -1 to 1
        price = close[-1] if close[-1] > 0 else 1
        norm_slope = np.clip(ema_slope / (price * 0.0005), -1.0, 1.0)
    else:
        norm_slope = 0.0

    # 2. Price vs EMA
    ema_last = ema_valid[-1] if len(ema_valid) > 0 else close[-1]
    price_ema_diff = close[-10:] - ema[-10:]
    avg_diff = np.nanmean(price_ema_diff)
    price_ema_score = np.clip(avg_diff / (close[-1] * 0.003 + 1e-8), -1.0, 1.0)

    # 3. Bar momentum from signal K scores
    if len(signal_k_scores) >= 5:
        momentum_score = signal_k_scores.iloc[-5:].mean()
    else:
        momentum_score = signal_k_scores.mean() if len(signal_k_scores) > 0 else 0.0

    # 4. Consecutive direction
    max_bull, max_bear = count_consecutive_same_direction(bars, 20)
    if max_bull >= max_bear:
        consec_score = min(max_bull / 5, 1.0)
    else:
        consec_score = -min(max_bear / 5, 1.0)

    # Always In combined score
    combined = (norm_slope * 0.30 + price_ema_score * 0.25 +
                momentum_score * 0.25 + consec_score * 0.20)

    if combined > threshold:
        direction = "LONG"
        confidence = min(abs(combined), 1.0)
    elif combined < -threshold:
        direction = "SHORT"
        confidence = min(abs(combined), 1.0)
    else:
        direction = "NEUTRAL"
        confidence = min(abs(combined) / threshold, 1.0)

    always_in = AlwaysInResult(
        direction=direction,
        confidence=confidence,
        ema_slope=norm_slope,
        price_ema_score=price_ema_score,
        momentum_score=momentum_score
    )

    # Market state classification
    overlap_ratio = calc_overlap_ratio(bars, 10)
    # Trend bar ratio: bars with meaningful directional bias
    trend_scores = signal_k_scores.abs()
    if len(trend_scores) >= 20:
        trend_bar_ratio = (trend_scores.iloc[-20:] > 0.3).mean()
    else:
        trend_bar_ratio = (trend_scores > 0.3).mean() if len(trend_scores) > 0 else 0.0

    abs_slope = abs(norm_slope)

    if abs_slope > 0.5 and overlap_ratio < 0.3 and trend_bar_ratio > 0.55:
        state = "STRONG_TREND"
    elif abs_slope > 0.25 and overlap_ratio < 0.5:
        state = "WEAK_TREND"
    elif overlap_ratio > 0.6 and abs_slope < 0.2:
        state = "TRADING_RANGE"
    else:
        state = "CHANNEL"

    return MarketContextResult(
        state=state,
        always_in=always_in,
        overlap_ratio=overlap_ratio,
        trend_bar_ratio=trend_bar_ratio,
    )


def analyze_context_enhanced(
    bars: pd.DataFrame,
    signal_k_scores: pd.Series,
    sr_levels: list = None,
    zones: list = None,
    ema_period: int = 20,
    threshold: float = 0.3,
) -> MarketContextResult:
    """
    矛盾论增强版市场上下文分析。

    在原始 state/Always In 判断之上，叠加矛盾结构分析：
    1. 识别矛盾类型（趋势主导/震荡僵持/转化中/对抗性爆发）
    2. 评估矛盾转化风险——内因+外因双重确认
    3. 输出状态转换警告（趋势减弱/突破在即/反转可能）

    这是从"表面状态分类"到"深层矛盾诊断"的升级。
    """
    # Original analysis
    base_result = analyze_context(bars, signal_k_scores, ema_period, threshold)

    # Contradiction analysis (contradiction module)
    contradiction = analyze_contradiction(
        bars, signal_k_scores, sr_levels or [], zones or [], ema_period
    )

    # Map contradiction type to state transition risk
    trans_risk = contradiction.transformation_risk
    state_transition_risk = "NONE"

    if contradiction.type == ContradictionType.ANTAGONISTIC:
        state_transition_risk = "REVERSAL_LIKELY"
    elif contradiction.type == ContradictionType.TRANSFORMING:
        if trans_risk == TransformationRisk.HIGH:
            # Determine direction of transformation
            if base_result.state in ("STRONG_TREND", "WEAK_TREND"):
                state_transition_risk = "TREND_WEAKENING"
            elif base_result.state == "TRADING_RANGE":
                state_transition_risk = "BREAKOUT_IMMINENT"
            else:
                state_transition_risk = "REVERSAL_LIKELY"
        elif trans_risk == TransformationRisk.MODERATE:
            if base_result.state in ("STRONG_TREND", "WEAK_TREND"):
                state_transition_risk = "TREND_WEAKENING"
            else:
                state_transition_risk = "BREAKOUT_IMMINENT"
        else:
            state_transition_risk = "NONE"
    elif (contradiction.type == ContradictionType.TREND_DOMINANT and
          trans_risk in (TransformationRisk.MODERATE, TransformationRisk.HIGH)):
        state_transition_risk = "TREND_WEAKENING"

    # Count how many transformation conditions are met
    internal_conds = sum([
        contradiction.internal.bar_strength_decay > 0.6,
        contradiction.internal.pullback_deepening > 0.6,
        contradiction.internal.consecutive_opposite >= 3,
        contradiction.internal.momentum_divergence > 0.5,
    ])
    external_conds = sum([
        contradiction.external.near_major_sr,
        contradiction.external.near_ema,
        contradiction.external.near_round_number,
        contradiction.external.near_tr_boundary,
        contradiction.external.zone_confluence >= 2,
    ])
    total_conditions = internal_conds + external_conds

    return MarketContextResult(
        state=base_result.state,
        always_in=base_result.always_in,
        overlap_ratio=base_result.overlap_ratio,
        trend_bar_ratio=base_result.trend_bar_ratio,
        contradiction=contradiction,
        state_transition_risk=state_transition_risk,
        transformation_conditions_met=total_conditions,
    )
