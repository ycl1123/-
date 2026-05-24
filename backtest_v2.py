"""
Al Brooks 回测 V2 — 整合 SKILL.md 全部 8 条决策启发式
=================================================================
启发式1: 先判状态，再定方向
启发式2: 趋势只顺势，震荡高抛低吸
启发式3: 回调至EMA+信号K=最优入场
启发式4: 三推楔形是反转之王
启发式5: 高潮后不追，等反转确认
启发式6: 失败突破=反向交易机会
启发式7: 前提消失，立刻出场
启发式8: 连亏3笔，停下来
=================================================================
"""
import sys
sys.path.insert(0, '.')
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

np.random.seed(42)

# =========================================================
# Data Generation (same as before)
# =========================================================
from test_上周数据 import make_uptrend, make_range, make_wedge_bottom, make_sell_climax, make_bear_trap, generate_session

start_price = 2680.0
n_bars = 78
all_bars, dates = [], []

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
# Analysis imports
# =========================================================
from analysis.signal_k import analyze_signal_k, BarType
from analysis.market_context import analyze_context
from analysis.utils import calc_ema, find_swing_points

signal_results = analyze_signal_k(df)
all_scores = signal_results.apply(lambda x: x.score)

# =========================================================
# SKILL.md Enhanced Trading Engine
# =========================================================

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
        self.exit_time = None
        self.exit_price = None
        self.pnl = 0
        self.result = 'OPEN'
        self.exit_reason = ''

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
ACCOUNT = 1000.0
MAX_RISK_PCT = 0.03
INITIAL_CAPITAL = 1000.0

# 启发式8: 连亏计数器
consecutive_losses = 0
paused_until = None  # datetime when pause ends

# =========================================================
# 启发式1: 先判状态，再定方向
# =========================================================
def heuristic_1_full_market_check(window, win_scores):
    """
    Brooks SKILL Step 2 — 全面市场状态检查
    ① 20 EMA 斜率 + 价格关系
    ② HH/HL vs LL/LH 结构
    ③ K线重叠度
    ④ 上市状态判定
    """
    ctx = analyze_context(window, win_scores)
    ai = ctx.always_in

    # 补充结构化判断
    status = {
        'always_in': ai.direction,
        'confidence': ai.confidence,
        'state': ctx.state,
        'overlap': ctx.overlap_ratio,
    }
    return ctx, status

# =========================================================
# 启发式3: 回调至EMA检测
# =========================================================
def heuristic_3_ema_pullback(window, current_idx, ai_dir):
    """检测是否出现1-3根浅回调至20EMA + 信号K"""
    if len(window) < 25:
        return False, None, None
    close = window['close'].values
    ema = calc_ema(close, 20)

    # 价格在EMA之上(多头)或之下(空头)
    ema_last = ema[-1] if not np.isnan(ema[-1]) else 0
    close_last = close[-1]

    if ai_dir == 'LONG':
        # 回调至EMA附近(1%以内)
        dist_pct = abs(close_last - ema_last) / ema_last
        if dist_pct > 0.008:
            return False, None, None
        # 确认之前是上升趋势
        if ema[-3] >= ema[-5]:
            return True, 'EMA回调做多', ema_last
    elif ai_dir == 'SHORT':
        dist_pct = abs(close_last - ema_last) / ema_last
        if dist_pct > 0.008:
            return False, None, None
        if ema[-3] <= ema[-5]:
            return True, 'EMA反弹做空', ema_last

    return False, None, None

# =========================================================
# 启发式4: 三推楔形检测
# =========================================================
def heuristic_4_wedge_detection(window):
    """检测三推楔形反转"""
    if len(window) < 30:
        return False, None, None

    sw_highs, sw_lows = find_swing_points(window, 5)

    # 楔形顶: 3个更高的波段高点，动量递减
    if len(sw_highs) >= 3:
        h1, h2, h3 = sw_highs[-3], sw_highs[-2], sw_highs[-1]
        if h1['price'] < h2['price'] < h3['price']:
            # Check momentum decay
            bar = window.iloc[h3['index']]
            sig = signal_results.iloc[window.index.get_loc(bar.name)]
            if sig.bar_type == BarType.REVERSAL and not sig.is_bullish:
                return True, f'楔形顶部反转 @ {h3["price"]:.1f}', h3['price']

    # 楔形底: 3个更低的波段低点，动量递减
    if len(sw_lows) >= 3:
        l1, l2, l3 = sw_lows[-3], sw_lows[-2], sw_lows[-1]
        if l1['price'] > l2['price'] > l3['price']:
            bar = window.iloc[l3['index']]
            sig = signal_results.iloc[window.index.get_loc(bar.name)]
            if sig.bar_type == BarType.REVERSAL and sig.is_bullish:
                return True, f'楔形底部反转 @ {l3["price"]:.1f}', l3['price']

    return False, None, None

# =========================================================
# 启发式5: 高潮检测（高潮后不追）
# =========================================================
def heuristic_5_climax_check(window):
    """检测是否有买入/卖出高潮。高潮后不追。"""
    if len(window) < 10:
        return False, ''

    recent_sigs = signal_results.iloc[-10:].apply(lambda x: x.bar_type)
    strong_count = sum(1 for s in recent_sigs if s == BarType.STRONG_TREND)

    # 4+ 强趋势K在最近6根 = 高潮
    recent_6 = list(signal_results.iloc[-6:].apply(lambda x: x.bar_type))
    strong_6 = sum(1 for s in recent_6 if s == BarType.STRONG_TREND)

    if strong_6 >= 3:
        # 检查方向
        scores_6 = [s.score for s in signal_results.iloc[-6:]]
        if all(s > 0.3 for s in scores_6):
            return True, '买入高潮 — 禁止追多'
        if all(s < -0.3 for s in scores_6):
            return True, '卖出高潮 — 禁止追空'

    return False, ''

# =========================================================
# 启发式6: 失败突破检测
# =========================================================
def heuristic_6_failed_breakout(window):
    """检测失败突破（震荡区间假突破后快速返回）"""
    if len(window) < 15:
        return False, None, None

    recent = window.tail(20)
    if len(recent) < 20:
        return False, None, None

    tr_high = recent['high'].max()
    tr_low = recent['low'].min()

    # 突破必须是在区间内已确认
    touches_upper = sum(recent['high'] >= tr_high * 0.998)
    touches_lower = sum(recent['low'] <= tr_low * 1.002)
    if touches_upper < 2 or touches_lower < 2:
        return False, None, None

    # 检查最近几根是否有假突破
    last_6 = window.tail(6)
    # 向上假突破
    if last_6['high'].max() > tr_high * 1.001:
        # 被打回来
        if last_6['close'].iloc[-1] < tr_high:
            return True, 'TR上沿失败突破(熊陷阱)做空', tr_high
    # 向下假突破
    if last_6['low'].min() < tr_low * 0.999:
        if last_6['close'].iloc[-1] > tr_low:
            return True, 'TR下沿失败突破(牛陷阱)做多', tr_low

    return False, None, None

# =========================================================
# 信号K质量评分 (SKILL Step 2 信号K验证维度)
# =========================================================
def signal_k_quality(sig, bar) -> float:
    """返回0-1的质量评分"""
    score = 0.0
    # 实体饱满 ≥70%
    if sig.body_ratio >= 0.70:
        score += 0.3
    elif sig.body_ratio >= 0.50:
        score += 0.15

    # 收盘在极值区域
    if sig.close_position >= 0.85 or sig.close_position <= 0.15:
        score += 0.25

    # 影线短
    if max(sig.upper_wick_ratio, sig.lower_wick_ratio) < 0.2:
        score += 0.25
    elif max(sig.upper_wick_ratio, sig.lower_wick_ratio) < 0.35:
        score += 0.1

    # 实体 > 前5根平均
    if getattr(sig, 'size_vs_avg', 1.0) >= 1.3:
        score += 0.2

    return min(score, 1.0)

# =========================================================
# Main Backtest Loop
# =========================================================
window_size = 30
position = None
premise_flip_bars = 0  # 启发式7: 追踪前提消失

print("=" * 70)
print("  Al Brooks 策略回测 V2 - 整合 SKILL.md 完整规则")
print("=" * 70)
print(f"  初始资金: ${INITIAL_CAPITAL} | 单笔风险: {MAX_RISK_PCT*100:.0f}% (${INITIAL_CAPITAL*MAX_RISK_PCT:.0f})")
print(f"  启发式规则: 全部 8 条已激活")
print()

for i in range(window_size, len(df) - 1):
    window = df.iloc[:i+1]
    current_bar = df.iloc[i]
    next_bar = df.iloc[i+1]
    current_time = df.index[i]

    # ============ 启发式8: 连亏暂停检查 ============
    if paused_until and current_time < paused_until:
        continue

    # ============ 管理持仓 ============
    if position is not None:
        exit_price = None
        result = None
        exit_reason = ''

        # 标准止损/止盈检查
        if position.direction == 'L':
            if next_bar['low'] <= position.stop:
                exit_price = position.stop
                result = 'LOSS'
                exit_reason = '止损'
            elif next_bar['high'] >= position.target:
                exit_price = position.target
                result = 'WIN'
                exit_reason = '止盈'
        else:
            if next_bar['high'] >= position.stop:
                exit_price = position.stop
                result = 'LOSS'
                exit_reason = '止损'
            elif next_bar['low'] <= position.target:
                exit_price = position.target
                result = 'WIN'
                exit_reason = '止盈'

        # ============ 启发式7: 前提消失，立刻出场 ============
        if result is None and premise_flip_bars >= 3:
            # 连续3根K线与持仓方向相反 → 前提消失
            exit_price = next_bar['close']
            result = 'LOSS'
            exit_reason = '前提消失'
            premise_flip_bars = 0

        # 检查 Always In 是否翻转
        win_scores = all_scores.iloc[:i+2]
        ctx, _ = heuristic_1_full_market_check(pd.concat([window, pd.DataFrame([next_bar.to_dict()])], ignore_index=True), win_scores)
        if ctx.always_in.direction != 'NEUTRAL':
            if position.direction == 'L' and ctx.always_in.direction == 'SHORT':
                if result is None:
                    exit_price = next_bar['close']
                    result = 'LOSS'
                    exit_reason = f'Always In翻转→SHORT'

        if result:
            position.close(df.index[i+1], exit_price, result, exit_reason)
            TRADES.append(position)
            ACCOUNT += position.pnl

            # 启发式8: 更新连亏计数
            if result == 'WIN':
                consecutive_losses = 0
            else:
                consecutive_losses += 1
                if consecutive_losses >= 3:
                    paused_until = current_time + timedelta(minutes=30)
                    print(f"  ⚠ {current_time.strftime('%m/%d %H:%M')} 连亏3笔 — 暂停30分钟 (启发式8)")

            position = None
            premise_flip_bars = 0
            continue

        # 追踪信号K是否被吃掉（启发式7辅助）
        if position.direction == 'L' and next_bar['close'] < current_bar['close']:
            premise_flip_bars += 1
        elif position.direction == 'S' and next_bar['close'] > current_bar['close']:
            premise_flip_bars += 1
        else:
            premise_flip_bars = 0

        continue

    # ============ 时间过滤 ============
    hour = current_time.hour + current_time.minute / 60
    if hour < 9.5 or hour > 15.5:
        continue

    # ============ 启发式1: 先判状态 ============
    if i < 30:
        continue  # 前30根K线只观察不交易 (Brooks: "开盘前30分钟不交易")

    win_scores = all_scores.iloc[:i+1]
    ctx, market_status = heuristic_1_full_market_check(window, win_scores)
    ai_dir = ctx.always_in.direction

    # 状态不确定 → 不交易 (启发式1)
    if ai_dir == 'NEUTRAL' and ctx.state != 'TRADING_RANGE':
        continue

    # ============ 启发式5: 高潮检查 ============
    in_climax, climax_msg = heuristic_5_climax_check(window)
    if in_climax:
        continue  # 高潮后不追

    # ============ 入场决策 (按优先级) ============
    sig = signal_results.iloc[i]
    bar = current_bar
    entry_price = next_bar['open']
    direction = None
    stop_price = None
    reason = ""

    # ---- 优先级1: 启发式4 楔形反转 ----
    is_wedge, wedge_msg, wedge_price = heuristic_4_wedge_detection(window)
    if is_wedge and signal_k_quality(sig, bar) >= 0.5:
        if '顶部' in wedge_msg and ai_dir != 'LONG':
            direction = 'S'
            stop_price = bar['high'] + 0.5
            reason = f'[启发式4] {wedge_msg}'
        elif '底部' in wedge_msg and ai_dir != 'SHORT':
            direction = 'L'
            stop_price = bar['low'] - 0.5
            reason = f'[启发式4] {wedge_msg}'

    # ---- 优先级2: 启发式3 EMA回调 ----
    if direction is None and signal_k_quality(sig, bar) >= 0.5:
        is_ema, ema_reason, ema_price = heuristic_3_ema_pullback(window, i, ai_dir)
        if is_ema and sig.bar_type == BarType.STRONG_TREND:
            if ai_dir == 'LONG' and sig.is_bullish:
                direction = 'L'
                stop_price = bar['low'] - 0.3
                reason = f'[启发式3] {ema_reason}'
            elif ai_dir == 'SHORT' and not sig.is_bullish:
                direction = 'S'
                stop_price = bar['high'] + 0.3
                reason = f'[启发式3] {ema_reason}'

    # ---- 优先级3: 强趋势K + Always In (启发式2) ----
    if direction is None and sig.bar_type == BarType.STRONG_TREND and signal_k_quality(sig, bar) >= 0.5:
        if sig.is_bullish and ai_dir == 'LONG':
            direction = 'L'
            stop_price = bar['low'] - 0.3
            reason = '[启发式2] 强牛市K + AlwaysIn LONG'
        elif not sig.is_bullish and ai_dir == 'SHORT':
            direction = 'S'
            stop_price = bar['high'] + 0.3
            reason = '[启发式2] 强熊市K + AlwaysIn SHORT'

    # ---- 优先级4: 启发式6 失败突破 ----
    if direction is None and ctx.state == 'TRADING_RANGE':
        is_bo, bo_reason, bo_price = heuristic_6_failed_breakout(window)
        if is_bo and signal_k_quality(sig, bar) >= 0.4:
            if '做多' in bo_reason:
                direction = 'L'
                stop_price = bar['low'] - 0.5
            else:
                direction = 'S'
                stop_price = bar['high'] + 0.5
            reason = f'[启发式6] {bo_reason}'

    # ---- 优先级5: 反转K + 波段极值 (启发式6辅助) ----
    if direction is None and sig.bar_type == BarType.REVERSAL:
        sw_highs, sw_lows = find_swing_points(window, 5)
        if sig.is_bullish and sw_lows:
            near_low = any(abs(bar['low'] - sl['price']) < 3 for sl in sw_lows[-3:])
            if near_low:
                direction = 'L'
                stop_price = bar['low'] - 0.5
                reason = f'[启发式6] 牛市反转K + 波段低点'
        elif not sig.is_bullish and sw_highs:
            near_high = any(abs(bar['high'] - sh['price']) < 3 for sh in sw_highs[-3:])
            if near_high:
                direction = 'S'
                stop_price = bar['high'] + 0.5
                reason = f'[启发式6] 熊市反转K + 波段高点'

    # ---- 启发式2: 震荡区间 TR 边界 ----
    if direction is None and ctx.state == 'TRADING_RANGE' and signal_k_quality(sig, bar) >= 0.5:
        recent = window.tail(20)
        tr_high = recent['high'].max()
        tr_low = recent['low'].min()
        if sig.is_bullish and bar['close'] < tr_low * 1.003:
            direction = 'L'
            stop_price = bar['low'] - 0.5
            reason = '[启发式2] TR下沿做多'
        elif not sig.is_bullish and bar['close'] > tr_high * 0.997:
            direction = 'S'
            stop_price = bar['high'] + 0.5
            reason = '[启发式2] TR上沿做空'

    if direction is None:
        continue

    # ============ 风险回报计算与验证 ============
    stop_distance = abs(entry_price - stop_price)
    if stop_distance < 0.15 or stop_distance > 15:
        continue

    # 计算仓位 (基于3%风险)
    risk_amount = min(ACCOUNT * MAX_RISK_PCT, 30)
    size_units = risk_amount / stop_distance
    size_units = min(size_units, 400)

    if direction == 'L':
        target_price = entry_price + stop_distance * 1.5
    else:
        target_price = entry_price - stop_distance * 1.5

    # 验证盈亏比 ≥ 1.5:1 (SKILL Step 2 风险回报维度)
    rr = 1.5
    if rr < 1.5:
        continue

    # ============ 开仓 ============
    position = Trade(
        entry_time=df.index[i+1],
        direction=direction,
        entry_price=entry_price,
        stop=stop_price,
        target=target_price,
        risk_dollars=risk_amount,
        size_units=size_units,
        reason=reason
    )
    premise_flip_bars = 0

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

gross_profit = sum(t.pnl for t in wins) if wins else 0
gross_loss = abs(sum(t.pnl for t in losses)) if losses else 1
profit_factor = gross_profit / max(gross_loss, 1)

peak = INITIAL_CAPITAL
running = INITIAL_CAPITAL
max_dd = 0
for t in TRADES:
    running += t.pnl
    peak = max(peak, running)
    dd = (peak - running) / peak * 100
    max_dd = max(max_dd, dd)

for t in TRADES:
    day = t.entry_time.strftime('%m/%d %H:%M')
    dir_sym = '▲多' if t.direction == 'L' else '▼空'
    res = '✓' if t.result == 'WIN' else '✗'
    print(f"  {day} {dir_sym} {t.reason}")
    print(f"       入场:{t.entry_price:.1f} 止损:{t.stop:.1f} 目标:{t.target:.1f} "
          f"出场:{t.exit_price:.1f}({t.exit_reason}) PnL:${t.pnl:+.1f} {res}")

print()
print("=" * 70)
print("  回测统计")
print("=" * 70)
print(f"  总交易: {total_trades} 笔")
print(f"  盈利: {win_count} 笔  |  亏损: {loss_count} 笔")
print(f"  胜率: {win_rate:.1f}%")
print(f"  平均盈利: ${avg_win:+.2f}  |  平均亏损: ${avg_loss:+.2f}")
if avg_loss != 0:
    print(f"  盈亏比 (Avg W/Avg L): {abs(avg_win/avg_loss):.2f}")
print(f"  盈利因子: {profit_factor:.2f}")
print(f"  总盈亏: ${total_pnl:+.2f}")
print(f"  最终资金: ${ACCOUNT:+.2f}  (收益率: {(ACCOUNT-INITIAL_CAPITAL)/INITIAL_CAPITAL*100:+.1f}%)")
print(f"  最大回撤: {max_dd:.1f}%")
print()

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
    print(f"  {day_names[day]}: {len(day_trades)}笔 {day_wins}赢{len(day_trades)-day_wins}输 PnL:${day_pnl:+.1f}")

print()
print("─" * 70)
print("  按启发式/入场原因统计")
print("─" * 70)
reasons = {}
for t in TRADES:
    key = t.reason.split(']')[0] + ']' if ']' in t.reason else t.reason[:20]
    if key not in reasons:
        reasons[key] = {'trades': 0, 'wins': 0, 'pnl': 0}
    reasons[key]['trades'] += 1
    if t.result == 'WIN':
        reasons[key]['wins'] += 1
    reasons[key]['pnl'] += t.pnl

for k, v in sorted(reasons.items(), key=lambda x: x[1]['pnl'], reverse=True):
    wr = v['wins']/v['trades']*100 if v['trades'] > 0 else 0
    print(f"  {k}: {v['trades']}笔 胜率{wr:.0f}% PnL:${v['pnl']:+.1f}")

print()
print("─" * 70)
print("  V2改进点验证")
print("─" * 70)

# Check if Tuesday was improved
tue_trades_v1 = 6  # from V1
tue_losses_v1 = 5
tue_trades = [t for t in TRADES if t.entry_time.day == 19]
tue_losses_v2 = sum(1 for t in tue_trades if t.result == 'LOSS')
tue_trades_v2 = len(tue_trades)
print(f"  周二(震荡日)对比: V1={tue_trades_v1}笔/{tue_losses_v1}输 → V2={tue_trades_v2}笔/{tue_losses_v2}输")
print(f"  全周对比: V1=22笔/+$390/胜率63.6%/回撤10.6%")
print(f"           V2={total_trades}笔/+${total_pnl:.0f}/胜率{win_rate:.1f}%/回撤{max_dd:.1f}%")
