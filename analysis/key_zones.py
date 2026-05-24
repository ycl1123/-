from dataclasses import dataclass
import pandas as pd
import numpy as np

@dataclass
class KeyZone:
    name: str
    zone_type: str  # "trading_range", "supply", "demand", "confluence", "gap"
    upper: float
    lower: float
    strength: float
    description: str = ""

@dataclass
class KeyZonesResult:
    zones: list[KeyZone]

def analyze_key_zones(bars: pd.DataFrame, sr_levels: list,
                      range_lookback: int = 20,
                      range_touch_min: int = 2,
                      confluence_threshold_pct: float = 0.05) -> KeyZonesResult:
    zones = []

    # 1. Trading range boundaries
    if len(bars) >= range_lookback:
        recent = bars.tail(range_lookback)
        upper = recent['high'].max()
        lower = recent['low'].min()
        touches_upper = sum(recent['high'] >= upper * 0.998)
        touches_lower = sum(recent['low'] <= lower * 1.002)
        if touches_upper >= range_touch_min and touches_lower >= range_touch_min:
            zones.append(KeyZone(
                name="震荡区间",
                zone_type="trading_range",
                upper=upper,
                lower=lower,
                strength=min(touches_upper, touches_lower) / range_touch_min,
                description=f"上沿触及{touches_upper}次 下沿触及{touches_lower}次"
            ))

    # 2. Supply/Demand zones (3+ bar reversals)
    if len(bars) >= 5:
        for i in range(3, len(bars) - 2):
            seg_a = bars.iloc[i - 3:i]
            seg_b = bars.iloc[i:i + 2]
            # Supply: 3 bullish then 2 bearish
            if (all(b.close > b.open for b in seg_a.itertuples()) and
                all(b.close < b.open for b in seg_b.itertuples())):
                zones.append(KeyZone(
                    name="供应区",
                    zone_type="supply",
                    upper=seg_a['high'].max(),
                    lower=seg_b['low'].min(),
                    strength=0.5,
                    description="3阳转2阴 卖压区"
                ))
                break  # Only take the most recent
            # Demand: 3 bearish then 2 bullish
            if (all(b.close < b.open for b in seg_a.itertuples()) and
                all(b.close > b.open for b in seg_b.itertuples())):
                zones.append(KeyZone(
                    name="需求区",
                    zone_type="demand",
                    upper=seg_b['high'].max(),
                    lower=seg_a['low'].min(),
                    strength=0.5,
                    description="3阴转2阳 买盘区"
                ))
                break

    # 3. Confluence zones (cluster SR levels)
    sr_objects = [sl for sl in sr_levels]
    sr_objects.sort(key=lambda x: x.price)
    if len(sr_objects) >= 2:
        cluster = [sr_objects[0]]
        for s in sr_objects[1:]:
            if abs(s.price - cluster[-1].price) / max(cluster[-1].price, 0.001) <= confluence_threshold_pct:
                cluster.append(s)
            else:
                if len(cluster) >= 2:
                    names = "/".join(c.label for c in cluster)
                    zones.append(KeyZone(
                        name=f"共振区: {names}",
                        zone_type="confluence",
                        upper=max(c.price for c in cluster),
                        lower=min(c.price for c in cluster),
                        strength=len(cluster) / 5,
                        description=f"{len(cluster)}个级别共振"
                    ))
                cluster = [s]
        # Last cluster
        if len(cluster) >= 2:
            names = "/".join(c.label for c in cluster)
            zones.append(KeyZone(
                name=f"共振区: {names}",
                zone_type="confluence",
                upper=max(c.price for c in cluster),
                lower=min(c.price for c in cluster),
                strength=len(cluster) / 5,
                description=f"{len(cluster)}个级别共振"
            ))

    return KeyZonesResult(zones=zones)
