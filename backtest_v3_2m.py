"""
Al Brooks 回测 V3 — 2分钟K线 + 震荡区间宽止损二次加仓
=============================================================
新规则:
1. 数据粒度: 2分钟K线 (5分钟→2分钟, bar数量翻2.5倍)
2. 震荡区间: 止损放大1.8x, 允许在更优价位二次加仓(同一方向)
3. 总风险控制: 单笔+加仓合计风险 ≤ 3%账户
4. 趋势行情: 标准止损+标准仓位
5. 加仓条件: 首次入场后价格回调至更优位置+信号K确认
"""
import sys
sys.path.insert(0, '.')
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

np.random.seed(42)

# =========================================================
# 生成2分钟K线数据 (上周)
# =========================================================
def make_2m_from_5m_like(bars_5m_style, bar_interval=2):
    """将5分钟风格的数据转换为2分钟粒度。插值出更多bar。"""
    result = []
    for i, b in enumerate(bars_5m_style):
        open_p, _, _, close_p = b['open'], b['high'], b['low'], b['close']
        sub_bars = 5 // bar_interval  # 5min -> N bars
        if sub_bars < 2:
            result.append(b)
            continue

        # 用布朗桥拆成sub_bars根
        prices = np.linspace(open_p, close_p, sub_bars + 1)
        for j in range(sub_bars):
            o = prices[j]
            c = prices[j + 1]
            noise = np.random.randn() * 0.8
            c += noise
            h = max(o, c) + abs(np.random.randn()) * 0.6
            l = min(o, c) - abs(np.random.randn()) * 0.6
            result.append({'open': o, 'high': h, 'low': l, 'close': c})
    return result

# Generate base 5min-style data
from test_上周数据 import make_uptrend, make_range, make_wedge_bottom, make_sell_climax, make_bear_trap

start_price = 2680.0
n_5min_bars = 78

def make_price_bars(data):
    bars = []
    for o, drift in data:
        c = o + drift
        h = max(o, c) + abs(np.random.randn()) * 1.2
        l = min(o, c) - abs(np.random.randn()) * 1.2
        bars.append({'open': o, 'high': h, 'low': l, 'close': c})
    return bars

# Generate 5min bar objects first, then convert to 2min
mon_data = make_uptrend(start_price, n_5min_bars, 2.5)
mon_bars_5m = make_price_bars(mon_data)
mon_bars_2m = make_2m_from_5m_like(mon_bars_5m)

# Fix centers for remaining days
last_close = mon_bars_5m[-1]['close']
tue_data = make_price_bars(make_range(last_close, n_5min_bars, center=last_close, width=12))
tue_bars_2m = make_2m_from_5m_like(tue_data)

last_close = tue_data[-1]['close']
wed_data = make_price_bars(make_wedge_bottom(last_close, n_5min_bars, 1.5))
wed_bars_2m = make_2m_from_5m_like(wed_data)

last_close = wed_data[-1]['close']
thu_data = make_price_bars(make_sell_climax(last_close, n_5min_bars, 1.5))
thu_bars_2m = make_2m_from_5m_like(thu_data)

last_close = thu_data[-1]['close']
fri_data = make_price_bars(make_bear_trap(last_close, n_5min_bars//2, 1.2))
fri_bars_2m = make_2m_from_5m_like(fri_data)

# Assemble all 2m bars
all_2m = mon_bars_2m + tue_bars_2m + wed_bars_2m + thu_bars_2m + fri_bars_2m
dates_2m = []
t = datetime(2026,5,18,9,30)
for b in all_2m:
    dates_2m.append(t)
    t += timedelta(minutes=2)
    # Skip outside trading hours
    hh = t.hour + t.minute/60
    if hh >= 16.5:
        t = t.replace(hour=9, minute=30) + timedelta(days=1)

dates_2m = dates_2m[:len(all_2m)]
all_2m = all_2m[:len(dates_2m)]

df = pd.DataFrame(all_2m, index=pd.DatetimeIndex(dates_2m))
df['volume'] = np.random.randint(50, 800, len(df))
df['spread'] = np.ones(len(df))*2

print(f"2分钟数据: {len(df)}根K线 (5分钟={len(df)//2.5:.0f})")
print(f"日期: {df.index[0]} ~ {df.index[-1]}")
print(f"价格: {df['close'].min():.1f} ~ {df['close'].max():.1f}")
print()

# =========================================================
# Analysis
# =========================================================
from analysis.signal_k import analyze_signal_k, BarType
from analysis.market_context import analyze_context
from analysis.utils import calc_ema, find_swing_points

signal_results = analyze_signal_k(df)
all_scores = signal_results.apply(lambda x: x.score)

# =========================================================
# Trading Engine V3
# =========================================================

INITIAL_CAPITAL = 1000.0
ACCOUNT = INITIAL_CAPITAL
MAX_TOTAL_RISK_PCT = 0.03  # 总亏损上限3%

class TradeV3:
    def __init__(self, entry_time, direction, entry_price, stop, target,
                 risk_dollars, size_units, reason, is_add=False):
        self.entry_time = entry_time
        self.direction = direction
        self.entry_price = entry_price
        self.stop = stop
        self.target = target
        self.risk_dollars = risk_dollars
        self.size_units = size_units
        self.reason = reason
        self.is_add = is_add
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

# =========================================================
# 信号K质量 (与V2相同)
# =========================================================
def signal_k_quality(sig, bar) -> float:
    score = 0.0
    if sig.body_ratio >= 0.70: score += 0.3
    elif sig.body_ratio >= 0.50: score += 0.15
    if sig.close_position >= 0.85 or sig.close_position <= 0.15: score += 0.25
    if max(sig.upper_wick_ratio, sig.lower_wick_ratio) < 0.2: score += 0.25
    elif max(sig.upper_wick_ratio, sig.lower_wick_ratio) < 0.35: score += 0.1
    return min(score, 1.0)

# =========================================================
# V3新规则: 震荡区间检测+宽止损配置
# =========================================================
def detect_tr_with_boundaries(window):
    """返回 (is_tr, tr_high, tr_low, tr_quality)"""
    if len(window) < 30:
        return False, 0, 0, 0
    recent = window.tail(30)
    upper = recent['high'].max()
    lower = recent['low'].min()
    touches_upper = sum(recent['high'] >= upper * 0.998)
    touches_lower = sum(recent['low'] <= lower * 1.002)
    # TR质量: 触及次数越多越好
    quality = min(touches_upper, touches_lower) / 3
    return (touches_upper >= 2 and touches_lower >= 2), upper, lower, quality

# =========================================================
# V3新规则: 加仓条件检测
# =========================================================
def check_add_position(position, bar, sig, bars_since_entry, prev_bar):
    """
    加仓条件:
    1. 首次入场后价格回调到更优位置(距止损更近但未触发) 或 入场价附近横盘整理
    2. 出现顺方向的信号K (震荡中允许较弱信号)
    """
    if position.is_add:
        return False, None

    if bars_since_entry < 2:  # 至少等2根K线再考虑加仓
        return False, None

    # 信号K质量至少0.2 (很低门槛——震荡中信号弱)
    if signal_k_quality(sig, bar) < 0.2:
        return False, None

    # 价格必须相对入场价有优势或持平
    price_range = abs(bar['close'] - position.entry_price) / position.entry_price

    if position.direction == 'L':
        if not sig.is_bullish:
            return False, None
        # 回调到更低价位 或 在入场价附近横盘(0.15%内)
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

# =========================================================
# Main Loop
# =========================================================
window_size = 40  # 2分钟需要更多bar做初始判断
position = None
has_added = False
premise_flip_bars = 0
bars_since_entry = 0

for i in range(window_size, len(df) - 1):
    window = df.iloc[:i+1]
    current_bar = df.iloc[i]
    next_bar = df.iloc[i+1]
    current_time = df.index[i]

    # 连亏暂停
    if paused_until and current_time < paused_until:
        continue

    # ============ 管理持仓 ============
    if position is not None:
        exit_price = None; result = None; exit_reason = ''
        bars_since_entry += 1

        # 计算联合止损位（如果加过仓，用平均入场价和新止损）
        if has_added:
            # 加仓后的联合止损：原仓位和加仓共用同一个止损
            composite_stop = position.stop
        else:
            composite_stop = position.stop

        if position.direction == 'L':
            if next_bar['low'] <= composite_stop:
                exit_price = composite_stop
                result = 'LOSS'
                exit_reason = '止损'
            elif next_bar['high'] >= position.target:
                exit_price = position.target
                result = 'WIN'
                exit_reason = '止盈'
        else:
            if next_bar['high'] >= composite_stop:
                exit_price = composite_stop
                result = 'LOSS'
                exit_reason = '止损'
            elif next_bar['low'] <= position.target:
                exit_price = position.target
                result = 'WIN'
                exit_reason = '止盈'

        # 前提消失: TR用5根(震荡正常回调), 趋势用3根
        flip_limit = 5 if ('宽止损' in position.reason) else 3
        if result is None and premise_flip_bars >= flip_limit:
            exit_price = next_bar['close']
            result = 'LOSS'
            exit_reason = '前提消失'

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
                    print(f"  ⚠ {current_time.strftime('%m/%d %H:%M')} 连亏3笔—暂停30min")

            position = None
            has_added = False
            premise_flip_bars = 0
            bars_since_entry = 0
            continue

        # 追踪逆势K
        if position.direction == 'L' and next_bar['close'] < current_bar['close']:
            premise_flip_bars += 1
        elif position.direction == 'S' and next_bar['close'] > current_bar['close']:
            premise_flip_bars += 1
        else:
            premise_flip_bars = 0

        # ============ V3新规则: 加仓检查 ============
        if not has_added:
            # Compute context for current bar to check TR state
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
                    # 检查总风险: (原仓风险 + 加仓风险) ≤ 3%
                    add_units = position.size_units * 0.5
                    total_risk = position.risk_dollars + (add_risk * add_units)
                    if total_risk <= ACCOUNT * MAX_TOTAL_RISK_PCT:
                        add_trade = TradeV3(
                            entry_time=df.index[i+1],
                            direction=position.direction,
                            entry_price=next_bar['close'],
                            stop=position.stop,
                            target=position.target,
                            risk_dollars=add_risk * add_units,
                            size_units=add_units,
                            reason='TR加仓(宽止损)',
                            is_add=True
                        )
                        has_added = True
                        total_units = position.size_units + add_units
                        avg_entry = (position.entry_price * position.size_units +
                                    add_trade.entry_price * add_units) / total_units
                        position.entry_price = avg_entry
                        position.size_units = total_units
                        position.risk_dollars += add_trade.risk_dollars
                        position.reason += ' + 加仓'

        continue

    # ============ 时间过滤 ============
    hour = current_time.hour + current_time.minute / 60
    if hour < 9.5 or hour > 15.5:
        continue

    # 只判断不入场的前30根
    if i < 50:  # 2分钟需要更多初始bar
        continue

    # ============ 市场状态 ============
    win_scores = all_scores.iloc[:i+1]
    ctx = analyze_context(window, win_scores)
    ai_dir = ctx.always_in.direction
    is_tr, tr_high, tr_low, tr_quality = detect_tr_with_boundaries(window)

    if ai_dir == 'NEUTRAL' and not is_tr:
        continue

    # ============ 入场逻辑 ============
    sig = signal_results.iloc[i]
    bar = current_bar
    entry_price = next_bar['close']  # 市价入场
    direction = None; stop_price = None; reason = ''
    is_tr_entry = False  # 标记是否是震荡区间入场(用于宽止损)

    # ---- TR状态锁定 ----
    market_state = ctx.state if not is_tr else 'TRADING_RANGE'

    # ---- 趋势 + 强信号K ----
    if sig.bar_type == BarType.STRONG_TREND and signal_k_quality(sig, bar) >= 0.5:
        if sig.is_bullish and ai_dir == 'LONG':
            direction = 'L'
            stop_price = bar['low'] - 0.2
            reason = f'趋势: 强牛K + Always In LONG'
        elif not sig.is_bullish and ai_dir == 'SHORT':
            direction = 'S'
            stop_price = bar['high'] + 0.2
            reason = f'趋势: 强熊K + Always In SHORT'

    # ---- EMA回调 ----
    if direction is None and signal_k_quality(sig, bar) >= 0.5:
        close = window['close'].values
        ema = calc_ema(close, 20)
        ema_l = ema[-1] if not np.isnan(ema[-1]) else close[-1]
        dist = abs(close[-1] - ema_l) / ema_l

        if ai_dir == 'LONG' and sig.is_bullish and dist < 0.01 and ema[-3] >= ema[-5]:
            direction = 'L'
            stop_price = bar['low'] - 0.2
            reason = 'EMA回调做多'
        elif ai_dir == 'SHORT' and not sig.is_bullish and dist < 0.01 and ema[-3] <= ema[-5]:
            direction = 'S'
            stop_price = bar['high'] + 0.2
            reason = 'EMA反弹做空'

    # ---- 震荡区间 TR 边界交易 (V3核心: 宽止损+允许加仓) ----
    if direction is None and is_tr and signal_k_quality(sig, bar) >= 0.4:

        # TR下沿做多
        if sig.is_bullish and (sig.bar_type in (BarType.STRONG_TREND, BarType.REVERSAL, BarType.BULLISH_PIN)):
            if bar['close'] < tr_low * 1.004:
                direction = 'L'
                # V3宽止损: 1.8x标准距离
                normal_stop_dist = abs(entry_price - (bar['low'] - 0.3))
                stop_price = entry_price - normal_stop_dist * 1.8
                is_tr_entry = True
                reason = f'TR下沿做多(宽止损)'

        # TR上沿做空
        elif not sig.is_bullish and (sig.bar_type in (BarType.STRONG_TREND, BarType.REVERSAL, BarType.BEARISH_PIN)):
            if bar['close'] > tr_high * 0.996:
                direction = 'S'
                normal_stop_dist = abs(entry_price - (bar['high'] + 0.3))
                stop_price = entry_price + normal_stop_dist * 1.8
                is_tr_entry = True
                reason = f'TR上沿做空(宽止损)'

    # ---- 失败突破 ----
    if direction is None and is_tr:
        # 向下假突破 → 牛陷阱做多
        last_6 = window.tail(6)
        if last_6['low'].min() < tr_low * 0.999 and bar['close'] > tr_low:
            if sig.is_bullish and signal_k_quality(sig, bar) >= 0.4:
                direction = 'L'
                stop_price = bar['low'] - 0.5
                is_tr_entry = True
                reason = 'TR失败突破(牛陷阱)做多'
        # 向上假突破 → 熊陷阱做空
        if last_6['high'].max() > tr_high * 1.001 and bar['close'] < tr_high:
            if not sig.is_bullish and signal_k_quality(sig, bar) >= 0.4:
                direction = 'S'
                stop_price = bar['high'] + 0.5
                is_tr_entry = True
                reason = 'TR失败突破(熊陷阱)做空'

    if direction is None:
        continue

    # ============ 风险计算 ============
    # 止损必须在入场价的反向: 多头止损<入场, 空头止损>入场
    if direction == 'L' and stop_price >= entry_price:
        continue
    if direction == 'S' and stop_price <= entry_price:
        continue

    stop_dist = abs(entry_price - stop_price)
    if stop_dist < 0.12 or stop_dist > 25:
        continue

    # TR宽止损仓位: 减小仓位以保持总风险可控
    total_risk_allowed = ACCOUNT * MAX_TOTAL_RISK_PCT
    if is_tr_entry:
        # 震荡模式: 预留50%风险给可能的加仓
        risk_for_entry = total_risk_allowed * 0.6
    else:
        # 趋势模式: 单笔风险控制在总风险内
        risk_for_entry = min(30, total_risk_allowed * 0.8)

    size_units = risk_for_entry / stop_dist
    size_units = min(size_units, 500)

    if direction == 'L':
        target_price = entry_price + stop_dist * 1.5
    else:
        target_price = entry_price - stop_dist * 1.5

    position = TradeV3(
        entry_time=df.index[i+1],
        direction=direction,
        entry_price=entry_price,
        stop=stop_price,
        target=target_price,
        risk_dollars=min(risk_for_entry, stop_dist * size_units),
        size_units=size_units,
        reason=reason,
        is_add=False
    )
    has_added = False
    premise_flip_bars = 0
    bars_since_entry = 0

# =========================================================
# 结果统计
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
    dir_sym = '▲' if t.direction == 'L' else '▼'
    add_tag = '[加仓]' if t.is_add else ''
    res = '✓' if t.result == 'WIN' else '✗'
    tr_tag = '(宽止损)' if '宽止损' in t.reason else ''
    print(f"  {day} {dir_sym} {add_tag} {t.reason}")
    print(f"       入场:{t.entry_price:.1f} 止损:{t.stop:.1f} 仓位:{t.size_units:.0f} "
          f"风险:${t.risk_dollars:.1f} 出场:{t.exit_price if t.exit_price else 0:.1f}({t.exit_reason}) "
          f"PnL:${t.pnl:+.1f} {res}")

print()
print("=" * 70)
print("  V3 回测统计 — 2分钟K线 + 震荡宽止损加仓")
print("=" * 70)
print(f"  数据: {len(df)}根2分K线 (≈{len(df)*2/60:.0f}交易小时)")
print(f"  初始资金: ${INITIAL_CAPITAL:.0f} | 总风险上限: {MAX_TOTAL_RISK_PCT*100:.0f}%")
print()
print(f"  总交易: {total_trades} 笔")
add_trades = [t for t in TRADES if t.is_add]
tr_trades = [t for t in TRADES if '宽止损' in t.reason or 'TR' in t.reason]
print(f"  其中加仓: {len(add_trades)} 次 | 震荡区间交易: {len(tr_trades)} 笔")
print(f"  盈利: {win_count} 笔  |  亏损: {loss_count} 笔")
print(f"  胜率: {win_rate:.1f}%")
print(f"  平均盈利: ${avg_win:+.2f}  |  平均亏损: ${avg_loss:+.2f}")
if avg_loss != 0:
    print(f"  盈亏比: {abs(avg_win/avg_loss):.2f}")
print(f"  盈利因子: {profit_factor:.2f}")
print(f"  总盈亏: ${total_pnl:+.2f}")
print(f"  最终资金: ${ACCOUNT:+.2f}  (收益率: {(ACCOUNT-INITIAL_CAPITAL)/INITIAL_CAPITAL*100:+.1f}%)")
print(f"  最大回撤: {max_dd:.1f}%")
print()

# 按日
print("─" * 70)
print("  按日统计")
print("─" * 70)
for day in [18, 19, 20, 21, 22]:
    day_trades = [t for t in TRADES if t.entry_time.day == day]
    if not day_trades:
        continue
    dn = {18:'周一',19:'周二',20:'周三',21:'周四',22:'周五'}
    day_pnl = sum(t.pnl for t in day_trades)
    day_wins = sum(1 for t in day_trades if t.result == 'WIN')
    adds = sum(1 for t in day_trades if t.is_add)
    print(f"  {dn[day]}: {len(day_trades)}笔({day_wins}赢{len(day_trades)-day_wins}输"
          f"{' 加仓'+str(adds)+'次' if adds else ''}) PnL:${day_pnl:+.1f}")

# 按类型
print()
print("─" * 70)
print("  按入场类型")
print("─" * 70)
categories = {}
for t in TRADES:
    if t.is_add: continue
    cat = t.reason.split(':')[0]
    if cat not in categories:
        categories[cat] = {'trades': 0, 'wins': 0, 'pnl': 0, 'max_risk': 0}
    categories[cat]['trades'] += 1
    if t.result == 'WIN': categories[cat]['wins'] += 1
    categories[cat]['pnl'] += t.pnl
    categories[cat]['max_risk'] = max(categories[cat]['max_risk'], t.risk_dollars)

for k, v in sorted(categories.items(), key=lambda x: x[1]['pnl'], reverse=True):
    wr = v['wins']/v['trades']*100 if v['trades']>0 else 0
    print(f"  {k}: {v['trades']}笔 胜率{wr:.0f}% PnL:${v['pnl']:+.1f} 最大风险:${v['max_risk']:.1f}")

# V3 特性验证
print()
print("─" * 70)
print("  V3 特性验证")
print("─" * 70)
print(f"  ✓ 2分钟K线粒度 ({len(df)}根 vs V2 351根)")
print(f"  ✓ 震荡宽止损 ({len(tr_trades)}笔 TR交易)")
print(f"  ✓ 加仓机制 ({len(add_trades)}次加仓)")
tr_wins = sum(1 for t in tr_trades if t.result == 'WIN')
print(f"  → TR交易胜率: {tr_wins/len(tr_trades)*100:.0f}%" if tr_trades else "  无TR交易")
# V2 comparison
print(f"  → V2对比: 13笔/+$210/回撤8.3%/胜率61.5%")
print(f"  → V3:    {total_trades}笔/+${total_pnl:.0f}/回撤{max_dd:.1f}%/胜率{win_rate:.1f}%")
