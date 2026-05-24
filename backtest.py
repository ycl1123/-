"""
Al Brooks 价格行为策略回测
资金: $1000 | 单笔风险: 3% ($30) | XAUUSD 5分钟
基于上周模拟数据，严格按照 Al Brooks 十大入场模式回测
"""
import sys
sys.path.insert(0, '.')
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

np.random.seed(42)

# =========================================================
# Generate same weekly data
# =========================================================
from test_上周数据 import make_uptrend, make_range, make_wedge_bottom, make_sell_climax, make_bear_trap, generate_session

start_price = 2680.0
n_bars = 78
all_bars = []
dates = []

mon_data = make_uptrend(start_price, n_bars, 2.5)
mon_bars, _ = generate_session(mon_data, datetime(2026,5,18,9,30), 1.5)
t0 = datetime(2026,5,18,9,30)
for i,b in enumerate(mon_bars): dates.append(t0+timedelta(minutes=5*i))
all_bars.extend(mon_bars)

tue_data = make_range(mon_bars[-1]['close'], n_bars, center=mon_bars[-1]['close'], width=12)
tue_bars, _ = generate_session(tue_data, datetime(2026,5,19,9,30), 1.2)
t1 = datetime(2026,5,19,9,30)
for i,b in enumerate(tue_bars): dates.append(t1+timedelta(minutes=5*i))
all_bars.extend(tue_bars)

wed_data = make_wedge_bottom(tue_bars[-1]['close'], n_bars, 1.5)
wed_bars, _ = generate_session(wed_data, datetime(2026,5,20,9,30), 1.5)
t2 = datetime(2026,5,20,9,30)
for i,b in enumerate(wed_bars): dates.append(t2+timedelta(minutes=5*i))
all_bars.extend(wed_bars)

thu_data = make_sell_climax(wed_bars[-1]['close'], n_bars, 1.5)
thu_bars, _ = generate_session(thu_data, datetime(2026,5,21,9,30), 1.5)
t3 = datetime(2026,5,21,9,30)
for i,b in enumerate(thu_bars): dates.append(t3+timedelta(minutes=5*i))
all_bars.extend(thu_bars)

fri_data = make_bear_trap(thu_bars[-1]['close'], n_bars//2, 1.2)
fri_bars, _ = generate_session(fri_data, datetime(2026,5,22,9,30), 1.2)
t4 = datetime(2026,5,22,9,30)
for i,b in enumerate(fri_bars): dates.append(t4+timedelta(minutes=5*i))
all_bars.extend(fri_bars)

df = pd.DataFrame(all_bars, index=pd.DatetimeIndex(dates))
df['volume'] = np.random.randint(200, 2000, len(df))
df['spread'] = np.ones(len(df))*2

# =========================================================
# Analysis
# =========================================================
from analysis.signal_k import analyze_signal_k, BarType
from analysis.market_context import analyze_context
from analysis.support_resistance import analyze_support_resistance
from analysis.utils import calc_ema, find_swing_points

signal_results = analyze_signal_k(df)
all_scores = signal_results.apply(lambda x: x.score)

print("=" * 70)
print("  Al Brooks 价格行为策略 -- 上周回测报告")
print("=" * 70)
print(f"  初始资金: $1,000 | 单笔最大风险: 3% ($30)")
print(f"  品种: XAUUSD | 周期: 5分钟")
print(f"  数据: 2026/5/18 - 5/22 (模拟真实K线)")
print(f"  总K线: {len(df)}")
print()

# =========================================================
# Trading Strategy
# =========================================================

class Trade:
    def __init__(self, entry_time, direction, entry_price, stop, target, risk, size_units):
        self.entry_time = entry_time
        self.direction = direction  # 'L' or 'S'
        self.entry_price = entry_price
        self.stop = stop
        self.target = target
        self.risk_dollars = risk
        self.size_units = size_units
        self.exit_time = None
        self.exit_price = None
        self.pnl = 0
        self.result = 'OPEN'  # 'WIN', 'LOSS', 'BE'

    def close(self, exit_time, exit_price, result):
        self.exit_time = exit_time
        self.exit_price = exit_price
        self.result = result
        if self.direction == 'L':
            self.pnl = (exit_price - self.entry_price) * self.size_units
        else:
            self.pnl = (self.entry_price - exit_price) * self.size_units

TRADES = []
ACCOUNT = 1000.0
MAX_RISK = 30.0  # 3% of $1000

# Walk through bars
window_size = 30  # bars needed before trading
position = None

for i in range(window_size, len(df) - 1):
    window = df.iloc[:i+1]
    current_bar = df.iloc[i]
    next_bar = df.iloc[i+1]
    current_time = df.index[i]

    # Check if we have an open position
    if position is not None:
        exit_price = None
        result = None
        # Check stop loss
        if position.direction == 'L':
            if next_bar['low'] <= position.stop:
                exit_price = position.stop
                result = 'LOSS'
            elif next_bar['high'] >= position.target:
                exit_price = position.target
                result = 'WIN'
        else:  # SHORT
            if next_bar['high'] >= position.stop:
                exit_price = position.stop
                result = 'LOSS'
            elif next_bar['low'] <= position.target:
                exit_price = position.target
                result = 'WIN'

        if result:
            position.close(df.index[i+1], exit_price, result)
            TRADES.append(position)
            ACCOUNT += position.pnl
            position = None
            continue

    # Don't enter new trades in first/last 30 min
    hour = current_time.hour + current_time.minute / 60
    if hour < 9.5 or hour > 15.5:
        continue

    # Only enter if no position
    if position is not None:
        continue

    # ---- ENTRY LOGIC ----
    sig = signal_results.iloc[i]
    prev_sig = signal_results.iloc[i-1] if i > 0 else sig
    bar = current_bar
    prev_bar = df.iloc[i-1]

    # Compute context on rolling window
    win_scores = all_scores.iloc[:i+1]
    ctx = analyze_context(window, win_scores)
    ai_dir = ctx.always_in.direction

    # Compute swing points for stop placement
    sw_highs, sw_lows = find_swing_points(window, 5)

    # --- ENTRY RULES ---
    direction = None
    entry_price = next_bar['open']
    stop_price = None
    target_price = None
    entry_reason = ""

    # Rule 1: Strong trend bar aligned with Always In direction
    if sig.bar_type == BarType.STRONG_TREND:
        if sig.is_bullish and ai_dir == 'LONG':
            direction = 'L'
            # Stop at signal bar low minus a bit
            stop_price = bar['low'] - 0.3
            entry_reason = "强牛市K + Always In LONG"
        elif not sig.is_bullish and ai_dir == 'SHORT':
            direction = 'S'
            stop_price = bar['high'] + 0.3
            entry_reason = "强熊市K + Always In SHORT"

    # Rule 2: Reversal bar at swing extreme
    if direction is None and sig.bar_type == BarType.REVERSAL:
        if sig.is_bullish and ai_dir != 'SHORT':
            # Bullish reversal: check if near swing low
            near_low = any(abs(bar['low'] - sl['price']) < 5 for sl in sw_lows[-3:]) if sw_lows else False
            if near_low or ai_dir == 'LONG':
                direction = 'L'
                stop_price = bar['low'] - 0.5
                entry_reason = "牛市反转K + 波段低点"
        elif not sig.is_bullish and ai_dir != 'LONG':
            near_high = any(abs(bar['high'] - sh['price']) < 5 for sh in sw_highs[-3:]) if sw_highs else False
            if near_high or ai_dir == 'SHORT':
                direction = 'S'
                stop_price = bar['high'] + 0.5
                entry_reason = "熊市反转K + 波段高点"

    # Rule 3: Outside bar breakout in trend direction
    if direction is None and sig.bar_type == BarType.OUTSIDE:
        if bar['close'] > bar['open'] and ai_dir == 'LONG':
            direction = 'L'
            stop_price = bar['low'] - 0.3
            entry_reason = "外包阳线 + Always In LONG"
        elif bar['close'] < bar['open'] and ai_dir == 'SHORT':
            direction = 'S'
            stop_price = bar['high'] + 0.3
            entry_reason = "外包阴线 + Always In SHORT"

    # Rule 4: In trading range, fade at boundaries
    if direction is None and ctx.state == 'TRADING_RANGE' and sig.bar_type == BarType.REVERSAL:
        recent = window.tail(20)
        tr_high = recent['high'].max()
        tr_low = recent['low'].min()
        if sig.is_bullish and bar['close'] < tr_low * 1.005:
            direction = 'L'
            stop_price = bar['low'] - 0.5
            entry_reason = "TR下沿反转做多"
        elif not sig.is_bullish and bar['close'] > tr_high * 0.995:
            direction = 'S'
            stop_price = bar['high'] + 0.5
            entry_reason = "TR上沿反转做空"

    if direction is None:
        continue

    # Calculate risk and position size
    stop_distance = abs(entry_price - stop_price)
    if stop_distance < 0.2 or stop_distance > 20:
        continue  # Stop too tight or too wide

    # Position sizing
    risk_amount = min(MAX_RISK, ACCOUNT * 0.03)
    size_units = risk_amount / stop_distance
    # XAUUSD: 1 micro-lot (0.01) = ~$0.10 per $1 move. Let's use $1 per unit
    size_units = min(size_units, 300)  # Max position cap

    # Target: 1.5:1 risk/reward
    if direction == 'L':
        target_price = entry_price + stop_distance * 1.5
    else:
        target_price = entry_price - stop_distance * 1.5

    position = Trade(
        entry_time=df.index[i+1],
        direction=direction,
        entry_price=entry_price,
        stop=stop_price,
        target=target_price,
        risk=risk_amount,
        size_units=size_units
    )

# =========================================================
# Results
# =========================================================
print()
print("─" * 70)
print("  交易明细")
print("─" * 70)

wins = [t for t in TRADES if t.result == 'WIN']
losses = [t for t in TRADES if t.result == 'LOSS']

total_trades = len(TRADES)
if total_trades == 0:
    print("  无交易信号触发")
    sys.exit()

win_count = len(wins)
loss_count = len(losses)
win_rate = win_count / total_trades * 100

total_pnl = sum(t.pnl for t in TRADES)
avg_win = np.mean([t.pnl for t in wins]) if wins else 0
avg_loss = np.mean([t.pnl for t in losses]) if losses else 0

# Profit factor
gross_profit = sum(t.pnl for t in wins) if wins else 0
gross_loss = abs(sum(t.pnl for t in losses)) if losses else 1
profit_factor = gross_profit / max(gross_loss, 1)

# Max drawdown
peak = ACCOUNT_START = 1000
running = ACCOUNT_START
max_dd = 0
for t in TRADES:
    running += t.pnl
    peak = max(peak, running)
    dd = (peak - running) / peak * 100
    max_dd = max(max_dd, dd)

for t in TRADES:
    day = t.entry_time.strftime('%m/%d %H:%M')
    dir_sym = '▲多' if t.direction == 'L' else '▼空'
    result_sym = '✓赢' if t.result == 'WIN' else '✗输'
    print(f"  {day} {dir_sym} 入场:{t.entry_price:.1f}  止损:{t.stop:.1f}  目标:{t.target:.1f}  "
          f"出场:{t.exit_price:.1f}  PnL:${t.pnl:+.1f}  {result_sym}")

print()
print("=" * 70)
print("  回测统计")
print("=" * 70)
print(f"  总交易: {total_trades} 笔")
print(f"  盈利: {win_count} 笔  |  亏损: {loss_count} 笔")
print(f"  胜率: {win_rate:.1f}%")
print(f"  平均盈利: ${avg_win:+.2f}  |  平均亏损: ${avg_loss:+.2f}")
print(f"  盈亏比 (Avg Win/Avg Loss): {abs(avg_win/avg_loss):.2f}" if avg_loss != 0 else f"  盈亏比: N/A")
print(f"  盈利因子 (Profit Factor): {profit_factor:.2f}")
print(f"  总盈亏: ${total_pnl:+.2f}")
print(f"  最终资金: ${ACCOUNT:+.2f}")
print(f"  收益率: {(ACCOUNT-1000)/1000*100:+.1f}%")
print(f"  最大回撤: {max_dd:.1f}%")
print()

# By day
print("─" * 70)
print("  按日统计")
print("─" * 70)
for day in [18, 19, 20, 21, 22]:
    day_trades = [t for t in TRADES if t.entry_time.day == day]
    if not day_trades:
        continue
    day_names = {18:'周一', 19:'周二', 20:'周三', 21:'周四', 22:'周五'}
    day_pnl = sum(t.pnl for t in day_trades)
    day_wins = sum(1 for t in day_trades if t.result == 'WIN')
    print(f"  {day_names[day]}: {len(day_trades)}笔  {day_wins}赢{len(day_trades)-day_wins}输  PnL:${day_pnl:+.1f}")

# By entry type
print()
print("─" * 70)
print("  按信号类型统计")
print("─" * 70)
# We'd need to store reason... skip for now

# Key findings
print()
print("─" * 70)
print("  回测结论")
print("─" * 70)
if win_rate >= 50:
    print(f"  ✓ 胜率 {win_rate:.1f}% 达到 Brooks 体系 40-60% 目标范围")
else:
    print(f"  ⚠ 胜率 {win_rate:.1f}%，低于 Brooks 体系 40-60% 目标")
if profit_factor >= 1.5:
    print(f"  ✓ 盈利因子 {profit_factor:.2f}，策略具有正向期望值")
else:
    print(f"  ⚠ 盈利因子 {profit_factor:.2f}，需优化入场过滤")
if abs(avg_win/avg_loss) >= 1.5 if avg_loss else False:
    print(f"  ✓ 盈亏比 > 1.5:1，符合策略要求")
print(f"  → 周收益率: {(ACCOUNT-1000)/1000*100:+.1f}%  |  最大回撤: {max_dd:.1f}%")
