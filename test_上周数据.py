"""
模拟上周 XAUUSD 5分钟K线，运行 Al Brooks 分析引擎。
包含: 上涨趋势、震荡区间、下跌楔形底、卖出高潮反转、熊陷阱
"""
import sys
sys.path.insert(0, '.')
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

np.random.seed(42)

def generate_session(bars_data, start_time, volatility=1.5):
    """Generate OHLC bars. bars_data = list of (open, close_offset) tuples."""
    bars = []
    t = start_time
    prev_close = None
    for i, (base_open, offset) in enumerate(bars_data):
        o = base_open
        c = o + offset
        rng = abs(o - c) + abs(np.random.randn()) * volatility * 2
        h = max(o, c) + abs(np.random.randn()) * volatility * 0.8
        l = min(o, c) - abs(np.random.randn()) * volatility * 0.8
        bars.append({
            'open': o, 'high': max(h, o, c), 'low': min(l, o, c), 'close': c
        })
        t += timedelta(minutes=5)
    return bars, t

def make_uptrend(start, n, trend_strength=2.5, mean_rev=1.0, vol=1.5):
    """HH+HL bull trend with shallow pullbacks."""
    data = []
    price = start
    leg_len = np.random.randint(5, 10)
    for i in range(n):
        if i % leg_len < max(1, leg_len - 3):
            drift = abs(np.random.randn()) * trend_strength + 0.5
        else:
            drift = -abs(np.random.randn()) * mean_rev - 0.5
        data.append((price, drift))
        price += drift
        if i % leg_len == leg_len - 1:
            leg_len = np.random.randint(5, 10)
    return data

def make_range(start, n, center=None, width=15, vol=1.5):
    """Trading range, mean-reverting."""
    data = []
    price = start
    if center is None:
        center = start
    for i in range(n):
        dist = price - center
        if dist > width * 0.7:
            drift = -abs(np.random.randn()) * 2 - 1
        elif dist < -width * 0.7:
            drift = abs(np.random.randn()) * 2 + 1
        else:
            drift = np.random.randn() * 2.5
        data.append((price, drift))
        price += drift
    return data

def make_wedge_bottom(start, n, vol=1.5):
    """Three pushes down, each weaker -> reversal up."""
    data = []
    price = start
    third = n // 3
    push_strength = [3.5, 2.5, 1.5]
    push_len = [third, third, n - 2 * third]
    for push_idx, (strength, plen) in enumerate(zip(push_strength, push_len)):
        for j in range(plen):
            if j < plen * 0.7:
                drift = -abs(np.random.randn()) * strength - 1
            else:
                drift = abs(np.random.randn()) * 2 + 0.5
            # Last push: stronger reversal at end
            if push_idx == 2 and j >= plen - 5:
                drift = abs(np.random.randn()) * 4 + 2
            data.append((price, drift))
            price += drift
    return data

def make_sell_climax(start, n, vol=1.5):
    """Strong downtrend -> big climax bars -> sharp reversal."""
    data = []
    price = start
    climax_start = n - 12
    reversal_start = n - 5
    for i in range(n):
        if i < climax_start:
            drift = -abs(np.random.randn()) * 3 - 1
        elif i < reversal_start:
            drift = -abs(np.random.randn()) * 5 - 2  # Climax bars
        else:
            drift = abs(np.random.randn()) * 5 + 2  # Strong reversal
        data.append((price, drift))
        price += drift
    return data

def make_bear_trap(start, n, vol=1.5):
    """Range -> breakdown -> sharp reversal (bear trap!)."""
    data = []
    price = start
    trap_start = n - 10
    reverse_start = n - 4
    for i in range(n):
        if i < trap_start:
            drift = np.random.randn() * 2
        elif i < reverse_start:
            drift = -abs(np.random.randn()) * 4 - 2  # Breakdown
        else:
            drift = abs(np.random.randn()) * 5 + 2  # Bear trap reversal!
        data.append((price, drift))
        price += drift
    return data

# ============ Build Week ============
start_price = 2680.0
n_bars_per_day = 78  # ~6.5 hours of 5min bars

all_bars = []
dates = []

# Monday: Uptrend
mon_data = make_uptrend(start_price, n_bars_per_day, trend_strength=2.5)
mon_bars, _ = generate_session(mon_data, datetime(2026, 5, 18, 9, 30), 1.5)
t0 = datetime(2026, 5, 18, 9, 30)
for i, b in enumerate(mon_bars):
    dates.append(t0 + timedelta(minutes=5*i))
all_bars.extend(mon_bars)

# Tuesday: Trading range
tue_price = mon_bars[-1]['close']
tue_data = make_range(tue_price, n_bars_per_day, center=tue_price, width=12)
tue_bars, _ = generate_session(tue_data, datetime(2026, 5, 19, 9, 30), 1.2)
t1 = datetime(2026, 5, 19, 9, 30)
for i, b in enumerate(tue_bars):
    dates.append(t1 + timedelta(minutes=5*i))
all_bars.extend(tue_bars)

# Wednesday: Wedge bottom
wed_price = tue_bars[-1]['close']
wed_data = make_wedge_bottom(wed_price, n_bars_per_day, 1.5)
wed_bars, _ = generate_session(wed_data, datetime(2026, 5, 20, 9, 30), 1.5)
t2 = datetime(2026, 5, 20, 9, 30)
for i, b in enumerate(wed_bars):
    dates.append(t2 + timedelta(minutes=5*i))
all_bars.extend(wed_bars)

# Thursday: Sell climax
thu_price = wed_bars[-1]['close']
thu_data = make_sell_climax(thu_price, n_bars_per_day, 1.5)
thu_bars, _ = generate_session(thu_data, datetime(2026, 5, 21, 9, 30), 1.5)
t3 = datetime(2026, 5, 21, 9, 30)
for i, b in enumerate(thu_bars):
    dates.append(t3 + timedelta(minutes=5*i))
all_bars.extend(thu_bars)

# Friday: Bear trap (half day)
fri_price = thu_bars[-1]['close']
fri_data = make_bear_trap(fri_price, n_bars_per_day // 2, 1.2)
fri_bars, _ = generate_session(fri_data, datetime(2026, 5, 22, 9, 30), 1.2)
t4 = datetime(2026, 5, 22, 9, 30)
for i, b in enumerate(fri_bars):
    dates.append(t4 + timedelta(minutes=5*i))
all_bars.extend(fri_bars)

df = pd.DataFrame(all_bars, index=pd.DatetimeIndex(dates))
df['volume'] = np.random.randint(200, 2000, len(df))
df['spread'] = np.ones(len(df)) * 2

print(f"生成: {len(df)}根K线, {df.index[0]} ~ {df.index[-1]}")
print(f"价格: {df['close'].min():.1f} ~ {df['close'].max():.1f}")
print()

# ============ Analysis Engine ============
from analysis.engine import AnalysisEngine
from analysis.signal_k import BarType
from config.settings import load_config

cfg = load_config()
engine = AnalysisEngine(cfg)

# Group by day
for day in [18, 19, 20, 21, 22]:
    day_df = df[df.index.day == day]
    if len(day_df) < 10:
        continue

    day_names = {18: '周一 5/18', 19: '周二 5/19', 20: '周三 5/20', 21: '周四 5/21', 22: '周五 5/22'}
    name = day_names[day]
    o, c = day_df['close'].iloc[0], day_df['close'].iloc[-1]
    chg = c - o

    result = engine.analyze('XAUUSD', 'M5', day_df)
    ctx = result.context
    sk = result.signal_k

    print(f"{'─'*65}")
    print(f"  {name}  |  {o:.1f} → {c:.1f}  ({chg:+.1f})  {len(day_df)}根K")
    print(f"{'─'*65}")

    # Context
    dir_map = {'LONG': '▲ 做多', 'SHORT': '▼ 做空', 'NEUTRAL': '■ 观望'}
    state_map = {'STRONG_TREND': '强趋势', 'WEAK_TREND': '弱趋势', 'CHANNEL': '通道', 'TRADING_RANGE': '震荡区间'}
    print(f"  Always In: {dir_map.get(ai_dir := ctx.always_in.direction, ai_dir)}  "
          f"置信度: {ctx.always_in.confidence:.1%}  "
          f"状态: {state_map.get(ctx.state, ctx.state)}")

    # Signal stats for the day
    sig_list = []
    for i in range(len(day_df)):
        bar = day_df.iloc[i]
        prev = day_df.iloc[i-1] if i > 0 else None
        from analysis.signal_k import analyze_single_bar
        s = analyze_single_bar(bar, prev, day_df.iloc[max(0,i-5):i])
        sig_list.append(s)

    strong = [s for s in sig_list if s.bar_type == BarType.STRONG_TREND]
    reversals = [s for s in sig_list if s.bar_type == BarType.REVERSAL]
    pins = [s for s in sig_list if s.bar_type.name in ('BULLISH_PIN', 'BEARISH_PIN')]
    outside = [s for s in sig_list if s.bar_type == BarType.OUTSIDE]
    inside = [s for s in sig_list if s.bar_type == BarType.INSIDE]
    doji = [s for s in sig_list if s.bar_type == BarType.DOJI]

    print(f"  信号统计: 强趋势={len(strong)}  反转={len(reversals)}  Pin={len(pins)}  "
          f"外包={len(outside)}  内包={len(inside)}  十字星={len(doji)}")

    # Show latest signal bars
    if strong:
        print(f"  ── 强趋势K线 ──")
        for s in strong[-3:]:
            d = '▲阳' if s.is_bullish else '▼阴'
            print(f"    {d} 评分:{s.score:+.2f} 实体:{s.body_ratio:.0%} 收盘位:{s.close_position:.0%}")

    if reversals:
        print(f"  ── 反转K线 ──")
        for s in reversals[-3:]:
            d = '转多▲' if s.is_bullish else '转空▼'
            print(f"    {d} 评分:{s.score:+.2f}")

    if pins:
        print(f"  ── Pin Bar ──")
        for s in pins[-2:]:
            t = '锤子线' if s.bar_type == BarType.BULLISH_PIN else '流星线'
            print(f"    {t} 评分:{s.score:+.2f}")

    # Key zones
    if result.zones and result.zones.zones:
        print(f"  ── 关键区域 ──")
        for z in result.zones.zones:
            if z.zone_type != 'confluence' or '共振' in z.name:
                print(f"    [{z.zone_type}] {z.name}: {z.lower:.1f}-{z.upper:.1f}")

    # Key SR levels
    if result.sr:
        strong_sr = [l for l in result.sr.levels if l.strength >= 0.5]
        if strong_sr:
            levels_str = ' | '.join(f'{l.label}={l.price:.1f}' for l in strong_sr[:8])
            print(f"  ── 关键S/R ──")
            print(f"    {levels_str}")

# ============ Weekly Summary ============
print()
print("=" * 65)
print("  全周汇总")
print("=" * 65)
full_result = engine.analyze('XAUUSD', 'M5', df)

# Gather all signal bars
all_sigs = []
for i in range(len(df)):
    bar = df.iloc[i]
    prev = df.iloc[i-1] if i > 0 else None
    from analysis.signal_k import analyze_single_bar
    all_sigs.append(analyze_single_bar(bar, prev, df.iloc[max(0,i-5):i]))

strong_all = [s for s in all_sigs if s.bar_type == BarType.STRONG_TREND]
rev_all = [s for s in all_sigs if s.bar_type == BarType.REVERSAL]
pins_all = [s for s in all_sigs if s.bar_type.name in ('BULLISH_PIN', 'BEARISH_PIN')]

print(f"  总K线: {len(df)}  周涨跌: {df['close'].iloc[-1] - df['close'].iloc[0]:+.1f}")
print(f"  信号K线: 强趋势={len(strong_all)}根  反转={len(rev_all)}根  PinBar={len(pins_all)}根")
avg_score = np.mean([abs(s.score) for s in all_sigs])
print(f"  平均K线强度: {avg_score:.2f}")
print(f"  最终状态: Always In={full_result.context.always_in.direction}  "
      f"市场={full_result.context.state}")
print()
print("  各模式出现天数:")
print(f"    ▲ 上涨趋势: 周一 (Always In LONG)")
print(f"    ■ 震荡区间: 周二 (高低点反复测试)")
print(f"    ▼ 下跌楔形底: 周三 (三推下+尾盘反转)")
print(f"    ◆ 卖出高潮反转: 周四 (连续大跌→强力反转)")
print(f"    ★ 熊陷阱: 周五 (假突破→强力拉回)")
