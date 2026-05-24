"""
Al Brooks 回测 — M2周期, 2026年5月(1-23日)模拟数据
=====================================================
XAUUSD May 2026 特征: 起始~2650, 先跌后反弹, 波动约300点
"""
import sys
sys.path.insert(0, '.')
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

np.random.seed(2026)

# =========================================================
# Generate realistic May 2026 XAUUSD M2 bars
# =========================================================
START_PRICE = 2650.0
N_DAYS = 17  # Trading days May 1-23 (roughly)
BARS_PER_DAY_2M = 210  # ~7h * 30 bars/h (2min)

def generate_may_data():
    """Generate realistic XAUUSD May 2026 data with trends and ranges."""
    bars = []
    price = START_PRICE

    # Week 1: May 1-2 (Thu-Fri) — Consolidation around 2650
    for _ in range(2):
        for _ in range(BARS_PER_DAY_2M):
            drift = np.random.randn() * 1.5
            o = price
            c = o + drift
            h = max(o, c) + abs(np.random.randn()) * 0.8
            l = min(o, c) - abs(np.random.randn()) * 0.8
            bars.append({'open': o, 'high': h, 'low': l, 'close': c})
            price = c

    # Week 2: May 5-9 — Downtrend to 2550
    for _ in range(5):
        for _ in range(BARS_PER_DAY_2M):
            drift = np.random.randn() * 2.2 - 0.5  # bias down
            o = price
            c = o + drift
            h = max(o, c) + abs(np.random.randn()) * 1.0
            l = min(o, c) - abs(np.random.randn()) * 1.0
            bars.append({'open': o, 'high': h, 'low': l, 'close': c})
            price = c

    # Week 3: May 12-16 — Trading range 2530-2580
    center = price
    for _ in range(5):
        for _ in range(BARS_PER_DAY_2M):
            dist = price - center
            if dist > 25:
                drift = -abs(np.random.randn()) * 2.0
            elif dist < -25:
                drift = abs(np.random.randn()) * 2.0
            else:
                drift = np.random.randn() * 2.5
            o = price
            c = o + drift
            h = max(o, c) + abs(np.random.randn()) * 0.8
            l = min(o, c) - abs(np.random.randn()) * 0.8
            bars.append({'open': o, 'high': h, 'low': l, 'close': c})
            price = c

    # Week 4: May 19-22 — Strong rally back to 2680
    for _ in range(3):
        for _ in range(BARS_PER_DAY_2M):
            drift = np.random.randn() * 2.0 + 0.6  # bias up
            o = price
            c = o + drift
            h = max(o, c) + abs(np.random.randn()) * 0.8
            l = min(o, c) - abs(np.random.randn()) * 0.8
            bars.append({'open': o, 'high': h, 'low': l, 'close': c})
            price = c

    return bars

all_bars = generate_may_data()

# Build datetime index
dates = []
t = datetime(2026, 5, 1, 9, 30)
for b in all_bars:
    dates.append(t)
    t += timedelta(minutes=2)
    hh = t.hour + t.minute / 60
    if hh >= 16.5:
        t = t.replace(hour=9, minute=30) + timedelta(days=1)
        # Skip weekends
        while t.weekday() >= 5:
            t += timedelta(days=1)

dates = dates[:len(all_bars)]
all_bars = all_bars[:len(dates)]

df = pd.DataFrame(all_bars, index=pd.DatetimeIndex(dates))
df['volume'] = np.random.randint(50, 800, len(df))
df['spread'] = np.ones(len(df)) * 2

print(f"XAUUSD M2 5月数据: {len(df)}根K线")
print(f"日期: {df.index[0]} ~ {df.index[-1]}")
print(f"价格: {df['close'].min():.1f} ~ {df['close'].max():.1f}")
print(f"起始: {START_PRICE:.1f} → 结束: {df['close'].iloc[-1]:.1f}")
print(f"交易天数: {len(set(d.date() for d in df.index))} 天")

# =========================================================
# Analysis
# =========================================================
from analysis.signal_k import analyze_signal_k, BarType
from analysis.market_context import analyze_context
from analysis.utils import calc_ema, find_swing_points

signal_results = analyze_signal_k(df)
all_scores = signal_results.apply(lambda x: x.score)

# =========================================================
# Trading Engine (from V3)
# =========================================================

INITIAL_CAPITAL = 1000.0
ACCOUNT = INITIAL_CAPITAL
MAX_TOTAL_RISK_PCT = 0.03

class Trade:
    def __init__(self, entry_time, direction, entry_price, stop, target,
                 risk_dollars, size_units, reason):
        self.entry_time = entry_time
        self.direction = direction
        self.entry_price = entry_price
        self.stop = stop
        self.target = target
        self.risk_dollars = risk_dollars
        self.size_units = size_units
        self.reason = reason
        self.is_add = False
        self.exit_time = None
        self.exit_price = None
        self.exit_reason = ''
        self.pnl = 0
        self.result = 'OPEN'

    def close(self, exit_time, exit_price, result, reason=''):
        self.exit_time = exit_time
        self.exit_price = exit_price
        self.result = result
        self.exit_reason = reason
        if self.direction == 'L':
            self.pnl = (exit_price - self.entry_price) * self.size_units
        else:
            self.pnl = (self.entry_price - exit_price) * self.size_units

TRADES = []
consecutive_losses = 0
paused_until = None

def signal_k_quality(sig, bar) -> float:
    score = 0.0
    if sig.body_ratio >= 0.70: score += 0.3
    elif sig.body_ratio >= 0.50: score += 0.15
    if sig.close_position >= 0.85 or sig.close_position <= 0.15: score += 0.25
    if max(sig.upper_wick_ratio, sig.lower_wick_ratio) < 0.2: score += 0.25
    elif max(sig.upper_wick_ratio, sig.lower_wick_ratio) < 0.35: score += 0.1
    return min(score, 1.0)

def detect_tr_with_boundaries(window):
    if len(window) < 30:
        return False, 0, 0, 0
    recent = window.tail(30)
    upper = recent['high'].max()
    lower = recent['low'].min()
    touches_upper = sum(recent['high'] >= upper * 0.998)
    touches_lower = sum(recent['low'] <= lower * 1.002)
    quality = min(touches_upper, touches_lower) / 3
    return (touches_upper >= 2 and touches_lower >= 2), upper, lower, quality

def check_add_position(position, bar, sig, bars_since_entry, prev_bar):
    if position.is_add:
        return False, None
    if bars_since_entry < 2:
        return False, None
    if signal_k_quality(sig, bar) < 0.2:
        return False, None
    if position.direction == 'L':
        if not sig.is_bullish:
            return False, None
        if bar['close'] > position.entry_price * 1.0015:
            return False, None
        stop_price = bar['low'] - 0.3
    else:
        if sig.is_bullish:
            return False, None
        if bar['close'] < position.entry_price * 0.9985:
            return False, None
        stop_price = bar['high'] + 0.3
    return True, stop_price

window_size = 40
position = None
has_added = False
premise_flip_bars = 0
bars_since_entry = 0

for i in range(window_size, len(df) - 1):
    window = df.iloc[:i+1]
    current_bar = df.iloc[i]
    next_bar = df.iloc[i+1]
    current_time = df.index[i]

    if paused_until and current_time < paused_until:
        continue

    # ---- Manage Position ----
    if position is not None:
        exit_price = None; result = None; exit_reason = ''
        bars_since_entry += 1

        if position.direction == 'L':
            if next_bar['low'] <= position.stop:
                exit_price = position.stop; result = 'LOSS'; exit_reason = '止损'
            elif next_bar['high'] >= position.target:
                exit_price = position.target; result = 'WIN'; exit_reason = '止盈'
        else:
            if next_bar['high'] >= position.stop:
                exit_price = position.stop; result = 'LOSS'; exit_reason = '止损'
            elif next_bar['low'] <= position.target:
                exit_price = position.target; result = 'WIN'; exit_reason = '止盈'

        flip_limit = 5 if ('TR' in position.reason) else 3
        if result is None and premise_flip_bars >= flip_limit:
            exit_price = next_bar['close']; result = 'LOSS'; exit_reason = '前提消失'

        if result:
            position.close(df.index[i+1], exit_price, result, exit_reason)
            TRADES.append(position)
            ACCOUNT += position.pnl

            if result == 'WIN':
                consecutive_losses = 0
            else:
                consecutive_losses += 1
                if consecutive_losses >= 3:
                    paused_until = current_time + timedelta(minutes=30)

            position = None; has_added = False
            premise_flip_bars = 0; bars_since_entry = 0
            continue

        if position.direction == 'L' and next_bar['close'] < current_bar['close']:
            premise_flip_bars += 1
        elif position.direction == 'S' and next_bar['close'] > current_bar['close']:
            premise_flip_bars += 1
        else:
            premise_flip_bars = 0

        # Add-on check
        if not has_added:
            win_scores = all_scores.iloc[:i+2]
            ctx_add = analyze_context(
                pd.concat([window, pd.DataFrame([next_bar.to_dict()])], ignore_index=True),
                win_scores)
            if ctx_add.state == 'TRADING_RANGE':
                sig_i = signal_results.iloc[i]
                can_add, add_stop = check_add_position(
                    position, next_bar, sig_i, bars_since_entry, current_bar)
                if can_add:
                    add_risk = abs(next_bar['close'] - position.stop)
                    add_units = position.size_units * 0.5
                    total_risk = position.risk_dollars + (add_risk * add_units)
                    if total_risk <= ACCOUNT * MAX_TOTAL_RISK_PCT:
                        has_added = True
                        total_units = position.size_units + add_units
                        avg_entry = (position.entry_price * position.size_units +
                                    next_bar['close'] * add_units) / total_units
                        position.entry_price = avg_entry
                        position.size_units = total_units
                        position.risk_dollars += add_risk * add_units
                        position.reason += ' + 加仓'
        continue

    # ---- Time Filter ----
    hour = current_time.hour + current_time.minute / 60
    if hour < 9.5 or hour > 15.5:
        continue
    if i < 50:
        continue

    # ---- Entry Logic ----
    win_scores = all_scores.iloc[:i+1]
    ctx = analyze_context(window, win_scores)
    ai_dir = ctx.always_in.direction
    is_tr, tr_high, tr_low, tr_quality = detect_tr_with_boundaries(window)

    if ai_dir == 'NEUTRAL' and not is_tr:
        continue

    sig = signal_results.iloc[i]
    bar = current_bar
    entry_price = next_bar['close']
    direction = None; stop_price = None; reason = ''
    is_tr_entry = False

    # Trend + Strong K
    if sig.bar_type == BarType.STRONG_TREND and signal_k_quality(sig, bar) >= 0.5:
        if sig.is_bullish and ai_dir == 'LONG':
            direction = 'L'
            stop_price = bar['low'] - 0.2
            reason = '趋势: 强牛K + Always In LONG'
        elif not sig.is_bullish and ai_dir == 'SHORT':
            direction = 'S'
            stop_price = bar['high'] + 0.2
            reason = '趋势: 强熊K + Always In SHORT'

    # EMA pullback/bounce
    if direction is None and signal_k_quality(sig, bar) >= 0.5:
        close = window['close'].values
        ema = calc_ema(close, 20)
        ema_l = ema[-1] if not np.isnan(ema[-1]) else close[-1]
        dist = abs(close[-1] - ema_l) / ema_l

        if ai_dir == 'LONG' and sig.is_bullish and dist < 0.01 and ema[-3] >= ema[-5]:
            direction = 'L'
            stop_price = bar['low'] - 1.0
            reason = 'EMA回调做多'
        elif ai_dir == 'SHORT' and not sig.is_bullish and dist < 0.01 and ema[-3] <= ema[-5]:
            direction = 'S'
            stop_price = bar['high'] + 1.0
            reason = 'EMA反弹做空'

    # TR boundary
    if direction is None and is_tr and signal_k_quality(sig, bar) >= 0.4:
        if sig.is_bullish and sig.bar_type in (BarType.STRONG_TREND, BarType.REVERSAL, BarType.BULLISH_PIN):
            if bar['close'] < tr_low * 1.004:
                direction = 'L'
                normal_dist = abs(entry_price - (bar['low'] - 0.3))
                stop_price = entry_price - normal_dist * 1.8
                is_tr_entry = True
                reason = 'TR下沿做多(宽止损)'
        elif not sig.is_bullish and sig.bar_type in (BarType.STRONG_TREND, BarType.REVERSAL, BarType.BEARISH_PIN):
            if bar['close'] > tr_high * 0.996:
                direction = 'S'
                normal_dist = abs(entry_price - (bar['high'] + 0.3))
                stop_price = entry_price + normal_dist * 1.8
                is_tr_entry = True
                reason = 'TR上沿做空(宽止损)'

    # Failed breakout
    if direction is None and is_tr:
        last_6 = window.tail(6)
        if last_6['low'].min() < tr_low * 0.999 and bar['close'] > tr_low:
            if sig.is_bullish and signal_k_quality(sig, bar) >= 0.4:
                direction = 'L'
                stop_price = bar['low'] - 0.5
                is_tr_entry = True
                reason = 'TR失败突破(牛陷阱)做多'
        if last_6['high'].max() > tr_high * 1.001 and bar['close'] < tr_high:
            if not sig.is_bullish and signal_k_quality(sig, bar) >= 0.4:
                direction = 'S'
                stop_price = bar['high'] + 0.5
                is_tr_entry = True
                reason = 'TR失败突破(熊陷阱)做空'

    if direction is None:
        continue

    # Stop validation
    if direction == 'L' and stop_price >= entry_price:
        continue
    if direction == 'S' and stop_price <= entry_price:
        continue

    stop_dist = abs(entry_price - stop_price)
    if stop_dist < 0.12 or stop_dist > 25:
        continue

    total_risk_allowed = ACCOUNT * MAX_TOTAL_RISK_PCT
    if is_tr_entry:
        risk_for_entry = total_risk_allowed * 0.6
    else:
        risk_for_entry = min(30, total_risk_allowed * 0.8)

    size_units = risk_for_entry / stop_dist
    size_units = min(size_units, 500)

    if direction == 'L':
        target_price = entry_price + stop_dist * 1.5
    else:
        target_price = entry_price - stop_dist * 1.5

    position = Trade(
        entry_time=df.index[i+1], direction=direction,
        entry_price=entry_price, stop=stop_price, target=target_price,
        risk_dollars=min(risk_for_entry, stop_dist * size_units),
        size_units=size_units, reason=reason
    )
    has_added = False; premise_flip_bars = 0; bars_since_entry = 0

# =========================================================
# Results
# =========================================================
print()
print("=" * 70)
print("  5月回测结果 — M2周期 | $1000 | 3%风险上限")
print("=" * 70)

wins = [t for t in TRADES if t.result == 'WIN']
losses = [t for t in TRADES if t.result == 'LOSS']
total_trades = len(TRADES)

if total_trades == 0:
    print("  无交易信号")
    sys.exit()

win_count = len(wins); loss_count = len(losses)
win_rate = win_count / total_trades * 100
total_pnl = sum(t.pnl for t in TRADES)
avg_win = np.mean([t.pnl for t in wins]) if wins else 0
avg_loss = np.mean([t.pnl for t in losses]) if losses else 0
gross_profit = sum(t.pnl for t in wins) if wins else 0
gross_loss = abs(sum(t.pnl for t in losses)) if losses else 1
profit_factor = gross_profit / max(gross_loss, 1)

peak = INITIAL_CAPITAL; running = INITIAL_CAPITAL; max_dd = 0
for t in TRADES:
    running += t.pnl; peak = max(peak, running)
    dd = (peak - running) / peak * 100; max_dd = max(max_dd, dd)

# Print trades
print(f"\n  数据: {len(df)}根M2 K线 ({len(set(d.date() for d in df.index))}个交易日)")
print(f"  价格: {df['close'].min():.1f} - {df['close'].max():.1f}")
print()

print("─" * 70)
print("  交易明细")
print("─" * 70)
for t in TRADES:
    day = t.entry_time.strftime('%m/%d %H:%M')
    dir_sym = '多' if t.direction == 'L' else '空'
    res = '✓' if t.result == 'WIN' else '✗'
    print(f"  {day} {dir_sym} {t.reason}")
    print(f"       入场:{t.entry_price:.1f} 止损:{t.stop:.1f} 目标:{t.target:.1f} "
          f"仓位:{t.size_units:.0f} 风险:${t.risk_dollars:.1f} "
          f"出场:{t.exit_price if t.exit_price else 0:.1f}({t.exit_reason}) "
          f"PnL:${t.pnl:+.1f} {res}")

print()
print("─" * 70)
print("  统计汇总")
print("─" * 70)
print(f"  总交易: {total_trades} 笔")
add_trades = [t for t in TRADES if t.is_add]
tr_trades = [t for t in TRADES if 'TR' in t.reason]
print(f"  加仓: {len(add_trades)} 次 | TR交易: {len(tr_trades)} 笔")
print(f"  盈利: {win_count} 笔  |  亏损: {loss_count} 笔")
print(f"  胜率: {win_rate:.1f}%")
print(f"  平均盈利: ${avg_win:+.2f}  |  平均亏损: ${avg_loss:+.2f}")
if avg_loss != 0:
    print(f"  盈亏比: {abs(avg_win/avg_loss):.2f}")
print(f"  盈利因子: {profit_factor:.2f}")
print(f"  总盈亏: ${total_pnl:+.2f}")
print(f"  最终资金: ${ACCOUNT:+.2f}  ({(ACCOUNT/INITIAL_CAPITAL-1)*100:+.1f}%)")
print(f"  最大回撤: {max_dd:.1f}%")

# By week
print()
print("─" * 70)
print("  按周统计")
print("─" * 70)
for wk_start in [1, 5, 12, 19]:
    wk_trades = [t for t in TRADES if t.entry_time.day >= wk_start and t.entry_time.day < wk_start + 5]
    if not wk_trades:
        continue
    wk_pnl = sum(t.pnl for t in wk_trades)
    wk_wins = sum(1 for t in wk_trades if t.result == 'WIN')
    print(f"  W{wk_start}: {len(wk_trades)}笔 {wk_wins}赢{len(wk_trades)-wk_wins}输 PnL:${wk_pnl:+.1f}")

# By type
print()
print("─" * 70)
print("  按入场类型")
print("─" * 70)
categories = {}
for t in TRADES:
    if t.is_add: continue
    cat = t.reason.split(':')[0] if ':' in t.reason else t.reason[:12]
    if cat not in categories:
        categories[cat] = {'trades': 0, 'wins': 0, 'pnl': 0}
    categories[cat]['trades'] += 1
    if t.result == 'WIN': categories[cat]['wins'] += 1
    categories[cat]['pnl'] += t.pnl

for k, v in sorted(categories.items(), key=lambda x: x[1]['pnl'], reverse=True):
    wr = v['wins']/v['trades']*100 if v['trades']>0 else 0
    print(f"  {k}: {v['trades']}笔 胜率{wr:.0f}% PnL:${v['pnl']:+.1f}")

# By day of week
print()
print("─" * 70)
print("  按交易日")
print("─" * 70)
day_names = {0:'周一',1:'周二',2:'周三',3:'周四',4:'周五'}
for d in sorted(set(t.entry_time.date() for t in TRADES)):
    day_t = [t for t in TRADES if t.entry_time.date() == d]
    dpnl = sum(t.pnl for t in day_t)
    dwins = sum(1 for t in day_t if t.result == 'WIN')
    dn = day_names.get(d.weekday(), '?')
    print(f"  {d} {dn}: {len(day_t)}笔 {dwins}赢 PnL:${dpnl:+.1f}")
