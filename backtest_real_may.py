"""
Al Brooks V4 回测 — 真实 MT5 M2 数据 (精简趋势版)
====================================================
聚焦高胜率趋势跟踪，去掉TR震荡交易噪音
- 仅交易趋势+EMA回调
- 信号质量 >= 0.7
- 止损 3x ATR
- 每日最多3笔
"""
import sys
sys.path.insert(0, '.')
import pandas as pd
import numpy as np

df = pd.read_pickle('data/may2026_m2.pkl')
df = df[(df.index >= '2026-05-01') & (df.index < '2026-05-24')]

from analysis.signal_k import analyze_signal_k, BarType
from analysis.market_context import analyze_context
from analysis.utils import calc_ema, calc_atr

print(f"真实M2: {len(df)}根 | {df.index[0].date()} ~ {df.index[-1].date()}")
print(f"价格: {df['close'].min():.1f} ~ {df['close'].max():.1f}")

signal_results = analyze_signal_k(df)
all_scores = signal_results.apply(lambda x: x.score)
atr_series = calc_atr(df, 14)
avg_atr = np.nanmean(atr_series)
print(f"平均 ATR(14): {avg_atr:.2f}")

INITIAL_CAPITAL = 1000.0
ACCOUNT = INITIAL_CAPITAL
MAX_RISK_PCT = 0.03
STOP_ATR = 3.0        # 3x ATR 止损
TARGET_RR = 3.0       # 盈亏比 1:3
MIN_QUALITY = 0.7      # 高信号质量
MAX_TRADES_PER_DAY = 3

class Trade:
    def __init__(self, entry_time, direction, entry_price, stop, target, size_units, risk_dollars, reason):
        self.entry_time = entry_time; self.direction = direction
        self.entry_price = entry_price; self.stop = stop; self.target = target
        self.size_units = size_units; self.risk_dollars = risk_dollars; self.reason = reason
        self.exit_time = None; self.exit_price = None; self.exit_reason = ''; self.pnl = 0; self.result = 'OPEN'

    def close(self, exit_time, exit_price, result, reason=''):
        self.exit_time = exit_time; self.exit_price = exit_price; self.result = result; self.exit_reason = reason
        if self.direction == 'L':
            self.pnl = (exit_price - self.entry_price) * self.size_units
        else:
            self.pnl = (self.entry_price - exit_price) * self.size_units

TRADES = []
consecutive_losses = 0
paused_until = None

def quality(sig, bar) -> float:
    q = 0.0
    if sig.body_ratio >= 0.70: q += 0.3
    elif sig.body_ratio >= 0.50: q += 0.15
    if sig.close_position >= 0.85 or sig.close_position <= 0.15: q += 0.25
    if max(sig.upper_wick_ratio, sig.lower_wick_ratio) < 0.2: q += 0.25
    elif max(sig.upper_wick_ratio, sig.lower_wick_ratio) < 0.35: q += 0.1
    return min(q, 1.0)

window_size = 40
position = None
bars_in_trade = 0
daily_trades = 0
current_day = None

for i in range(window_size, len(df) - 1):
    window = df.iloc[:i+1]
    current_bar = df.iloc[i]
    next_bar = df.iloc[i+1]
    current_time = df.index[i]
    bar_day = current_time.date()

    # Reset daily counter
    if bar_day != current_day:
        current_day = bar_day
        daily_trades = 0

    current_atr = atr_series[i]
    if np.isnan(current_atr) or current_atr < 0.5:
        current_atr = avg_atr

    if paused_until and current_time < paused_until:
        continue

    # ============ 管理持仓 ============
    if position is not None:
        bars_in_trade += 1
        exit_price = None; result = None; exit_reason = ''

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

        # 持仓时间限制: 60根M2 = 2小时
        if result is None and bars_in_trade > 60:
            exit_price = next_bar['close']
            if position.direction == 'L':
                result = 'WIN' if exit_price > position.entry_price else 'LOSS'
            else:
                result = 'WIN' if exit_price < position.entry_price else 'LOSS'
            exit_reason = '超时'

        if result:
            position.close(df.index[i+1], exit_price, result, exit_reason)
            TRADES.append(position)
            ACCOUNT += position.pnl

            if result == 'WIN':
                consecutive_losses = 0
            else:
                consecutive_losses += 1
                if consecutive_losses >= 3:
                    paused_until = current_time + pd.Timedelta(minutes=60)

            position = None
            bars_in_trade = 0
            continue
        continue

    # ============ 入场过滤 ============
    if i < 50 or daily_trades >= MAX_TRADES_PER_DAY:
        continue

    win_scores = all_scores.iloc[:i+1]
    ctx = analyze_context(window, win_scores)
    ai_dir = ctx.always_in.direction

    # 只在有方向时交易
    if ai_dir == 'NEUTRAL':
        continue

    sig = signal_results.iloc[i]
    bar = current_bar
    q = quality(sig, bar)

    if q < MIN_QUALITY:
        continue

    # 必须是大实体K线
    if sig.bar_type not in (BarType.STRONG_TREND, BarType.REVERSAL):
        continue

    entry_price = next_bar['close']
    direction = None; stop_price = None; reason = ''

    # ---- 趋势: 强信号K + Always In同向 ----
    if sig.bar_type == BarType.STRONG_TREND:
        if sig.is_bullish and ai_dir == 'LONG':
            direction = 'L'
            stop_price = entry_price - current_atr * STOP_ATR
            reason = '趋势跟踪多'
        elif not sig.is_bullish and ai_dir == 'SHORT':
            direction = 'S'
            stop_price = entry_price + current_atr * STOP_ATR
            reason = '趋势跟踪空'

    # ---- EMA回调: 信号K + 接近EMA + Always In同向 ----
    if direction is None and ai_dir in ('LONG', 'SHORT'):
        close_vals = window['close'].values
        ema20 = calc_ema(close_vals, 20)
        ema_val = ema20[-1] if not np.isnan(ema20[-1]) else close_vals[-1]
        dist_pct = abs(close_vals[-1] - ema_val) / ema_val

        # Must be very close to EMA (<0.15%)
        if dist_pct < 0.0015:
            if ai_dir == 'LONG' and sig.is_bullish:
                direction = 'L'
                stop_price = entry_price - current_atr * STOP_ATR
                reason = 'EMA回调做多'
            elif ai_dir == 'SHORT' and not sig.is_bullish:
                direction = 'S'
                stop_price = entry_price + current_atr * STOP_ATR
                reason = 'EMA反弹做空'

    if direction is None:
        continue

    # 验证止损方向
    stop_dist = abs(entry_price - stop_price)
    if direction == 'L' and stop_price >= entry_price:
        continue
    if direction == 'S' and stop_price <= entry_price:
        continue
    if stop_dist < current_atr * 2.0 or stop_dist > current_atr * 5:
        continue

    # 仓位
    risk_allowed = ACCOUNT * MAX_RISK_PCT
    size_units = risk_allowed / stop_dist
    size_units = min(size_units, 500)

    if direction == 'L':
        target_price = entry_price + stop_dist * TARGET_RR
    else:
        target_price = entry_price - stop_dist * TARGET_RR

    position = Trade(df.index[i+1], direction, entry_price, stop_price, target_price,
                     size_units, min(risk_allowed, stop_dist * size_units), reason)
    daily_trades += 1

# =========================================================
# 统计
# =========================================================
wins = [t for t in TRADES if t.result == 'WIN']
losses = [t for t in TRADES if t.result == 'LOSS']
total = len(TRADES)

if total == 0:
    print("无交易")
    sys.exit()

win_count = len(wins); loss_count = len(losses)
wr = win_count / total * 100
total_pnl = sum(t.pnl for t in TRADES)
avg_win = np.mean([t.pnl for t in wins]) if wins else 0
avg_loss = np.mean([t.pnl for t in losses]) if losses else 0
gross_profit = sum(t.pnl for t in wins) if wins else 0
gross_loss = abs(sum(t.pnl for t in losses)) if losses else 1
pf = gross_profit / max(gross_loss, 1)

peak = INITIAL_CAPITAL; running = INITIAL_CAPITAL; max_dd = 0
for t in TRADES:
    running += t.pnl
    peak = max(peak, running)
    max_dd = max(max_dd, (peak - running) / peak * 100)

print()
print("─" * 90)
print("  交易明细 (最近40笔)")
print("─" * 90)
for t in TRADES[-40:]:
    day = t.entry_time.strftime('%m/%d %H:%M')
    d = 'LONG' if t.direction == 'L' else 'SHORT'
    sd = abs(t.entry_price - t.stop)
    res = 'WIN' if t.result == 'WIN' else 'LOSS'
    print(f"  {day} {d:5s} {t.reason:12s} | 入场{t.entry_price:.1f} 止损{t.stop:.1f} "
          f"({sd:.1f}pt) 仓位{t.size_units:.0f} PnL:${t.pnl:+.1f} {res}")

print()
print("=" * 90)
print("  V4 精简趋势版 — 真实M2数据回测")
print("=" * 90)
print(f"  ATR止损: {STOP_ATR}x | 盈亏比: 1:{TARGET_RR} | 最低质量: {MIN_QUALITY}")
print(f"  交易: {total}笔 | 胜率: {wr:.1f}%")
print(f"  均盈: ${avg_win:+.2f} | 均亏: ${avg_loss:+.2f} | 盈亏比: {abs(avg_win/avg_loss):.2f}" if avg_loss else "")
print(f"  盈利因子: {pf:.2f} | 总PnL: ${total_pnl:+.2f}")
print(f"  最终: ${ACCOUNT:+.2f} ({(ACCOUNT-INITIAL_CAPITAL)/INITIAL_CAPITAL*100:+.1f}%) | 回撤: {max_dd:.1f}%")

print()
print("─" * 90)
print("  按日")
print("─" * 90)
for day in sorted(set(t.entry_time.date() for t in TRADES)):
    dt = [t for t in TRADES if t.entry_time.date() == day]
    dp = sum(t.pnl for t in dt); dw = sum(1 for t in dt if t.result == 'WIN')
    print(f"  {day}: {len(dt)}笔({dw}W/{len(dt)-dw}L) PnL:${dp:+.1f}")

print()
print("─" * 90)
print("  按类型")
print("─" * 90)
cats = {}
for t in TRADES:
    c = t.reason
    if c not in cats: cats[c] = {'n':0, 'w':0, 'p':0, 's':0}
    cats[c]['n'] += 1
    if t.result == 'WIN': cats[c]['w'] += 1
    cats[c]['p'] += t.pnl
    cats[c]['s'] += abs(t.entry_price - t.stop)
for k, v in sorted(cats.items(), key=lambda x: x[1]['p'], reverse=True):
    r = v['w']/v['n']*100 if v['n'] else 0; a = v['s']/v['n'] if v['n'] else 0
    print(f"  {k:12s}: {v['n']:3d}笔 胜率{r:.0f}% 均止损{a:.1f}pt PnL:${v['p']:+.1f}")
