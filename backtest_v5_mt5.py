"""
V5 回测 — MT5 实时数据 — 矛盾论·实践论·游击战
==============================================
从 MT5 拉取 XAUUSD M2 数据，用 V5 增强引擎回测：
- 矛盾分析（内因+外因双重确认）
- 游击战共振加权（集中优势兵力）
- ATR 自适应止损
"""
import sys
sys.path.insert(0, '.')
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import MetaTrader5 as mt5

# ============================================================
# 1. 连接 MT5 拉数据
# ============================================================
print("=" * 70)
print("  V5 回测 — 矛盾论·实践论·游击战")
print("  MT5 实时数据")
print("=" * 70)

if not mt5.initialize():
    print(f"MT5 初始化失败: {mt5.last_error()}")
    sys.exit(1)

account = mt5.account_info()
print(f"账户: {account.login if account else 'unknown'}")
print(f"服务器: {mt5.terminal_info().name if mt5.terminal_info() else 'unknown'}")

SYMBOL = "XAUUSDm"
TIMEFRAME = mt5.TIMEFRAME_M2

# Enable symbol
mt5.symbol_select(SYMBOL, True)

# Fetch last ~30 trading days of M2 bars (M2 = 2 minutes, ~720 bars/day → ~22000 bars)
HISTORY_BARS = 25000
print(f"拉取 {SYMBOL} M2 最近 {HISTORY_BARS} 根K线...")
rates = mt5.copy_rates_from_pos(SYMBOL, TIMEFRAME, 0, HISTORY_BARS)

if rates is None or len(rates) == 0:
    print(f"拉取失败: {mt5.last_error()}")
    mt5.shutdown()
    sys.exit(1)

mt5.shutdown()

# Build DataFrame
df = pd.DataFrame(rates)
df['time'] = pd.to_datetime(df['time'], unit='s')
df.set_index('time', inplace=True)
df.rename(columns={'tick_volume': 'volume'}, inplace=True)
df = df[['open', 'high', 'low', 'close', 'volume', 'spread']]

print(f"数据: {len(df)} 根 M2 K线")
print(f"区间: {df.index[0]} ~ {df.index[-1]}")
print(f"价格: {df['close'].min():.1f} ~ {df['close'].max():.1f}")
print(f"交易天数: {len(set(d.date() for d in df.index))} 天")

# Filter to last ~30 days
latest_date = df.index[-1].date()
cutoff = latest_date - timedelta(days=35)
df = df[df.index.date >= cutoff]
print(f"过滤后 ({cutoff} 至今): {len(df)} 根K线 | {len(set(d.date() for d in df.index))} 个交易日\n")

if len(df) < 100:
    print("数据不足，退出")
    sys.exit(1)

# ============================================================
# 2. 导入 V5 分析模块
# ============================================================
from analysis.signal_k import analyze_signal_k, BarType
from analysis.support_resistance import analyze_support_resistance
from analysis.key_zones import analyze_key_zones
from analysis.market_context import analyze_context_enhanced
from analysis.contradiction import ContradictionType, TransformationRisk
from analysis.trade_signals import compute_trade_signals, SignalStrength
from analysis.utils import calc_ema, calc_atr

# Pre-compute signal K (expensive, do once)
print("预计算信号K...")
signal_results = analyze_signal_k(df, 5)
all_scores = signal_results.apply(lambda x: x.score)
print(f"  完成: {len(signal_results)} 根K线\n")

# Pre-compute ATR
atr_series = calc_atr(df, 14)
avg_atr = float(np.nanmean(atr_series))
print(f"平均 ATR(14): {avg_atr:.2f}\n")

# ============================================================
# 3. 交易参数
# ============================================================
INITIAL_CAPITAL = 1000.0
account = INITIAL_CAPITAL
MAX_RISK_PCT = 0.03          # 单笔最大风险 3%
MAX_DAILY_LOSS_PCT = 0.10   # 单日最大亏损 10%
STOP_ATR = 3.0
TARGET_RR = 3.0
MIN_QUALITY = 0.0           # 出信号就做
MAX_TRADES_PER_DAY = 999    # 出信号就做（不限次数）

# V5: 游击战参数
RESONANCE_MIN = 0           # 出信号就做
CONTRADICTION_SKIP = False  # 不跳过

class Trade:
    def __init__(self, entry_time, direction, entry_price, stop, target,
                 size_units, risk_dollars, reason, resonance=0, tactical_layer=""):
        self.entry_time = entry_time
        self.direction = direction
        self.entry_price = entry_price
        self.stop = stop
        self.target = target
        self.size_units = size_units
        self.risk_dollars = risk_dollars
        self.reason = reason
        self.resonance = resonance
        self.tactical_layer = tactical_layer
        self.exit_time = None
        self.exit_price = None
        self.exit_reason = ''
        self.pnl = 0.0
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
daily_pnl = 0.0
current_day = None

# ============================================================
# 4. 回测主循环
# ============================================================
WINDOW = 50
position = None
bars_in_trade = 0
daily_trades = 0
current_day = None

print("回测中", end="", flush=True)

for i in range(WINDOW, len(df) - 1):
    if i % 200 == 0:
        print(".", end="", flush=True)

    window = df.iloc[:i+1]
    current_bar = df.iloc[i]
    next_bar = df.iloc[i+1]
    current_time = df.index[i]
    bar_day = current_time.date()

    if bar_day != current_day:
        current_day = bar_day
        daily_trades = 0
        daily_pnl = 0.0

    current_atr = atr_series[i]
    if np.isnan(current_atr) or current_atr < 0.5:
        current_atr = avg_atr

    if paused_until and current_time < paused_until:
        continue

    # ---- 管理持仓 ----
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
            account += position.pnl
            daily_pnl += position.pnl

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

    # ---- 入场过滤 ----
    if i < WINDOW or daily_trades >= MAX_TRADES_PER_DAY:
        continue

    # 单日亏损上限 10%
    if daily_pnl < -INITIAL_CAPITAL * MAX_DAILY_LOSS_PCT:
        continue

    # ---- V5: 运行增强分析 ----
    try:
        win_scores = all_scores.iloc[:i+1]
        sr = analyze_support_resistance(window)
        zones = analyze_key_zones(window, sr.levels)
        ctx = analyze_context_enhanced(window, win_scores, sr_levels=sr.levels, zones=zones.zones)
        sig = signal_results.iloc[i]
        signals = compute_trade_signals(window, sig, win_scores.iloc[:i+1], ctx, zones)
    except Exception:
        continue

    ai_dir = ctx.always_in.direction

    # V5: 矛盾转化高风险 → 跳过入场（保存自己）
    if CONTRADICTION_SKIP and ctx.contradiction:
        if ctx.contradiction.transformation_risk in (TransformationRisk.HIGH,):
            continue

    if ai_dir == 'NEUTRAL':
        continue

    # 取最高共振信号
    if not signals:
        continue

    best_sig = signals[0]

    # V5: 共振不足 → 不交易（集中优势兵力）
    if best_sig.resonance_count < RESONANCE_MIN:
        continue

    # 信号质量
    q = best_sig.confidence
    if q < MIN_QUALITY:
        continue

    if best_sig.direction not in ('L', 'S'):
        continue

    direction = best_sig.direction
    entry_price = next_bar['close']
    stop_price = best_sig.stop_price
    target_price = best_sig.target_price
    resonance = best_sig.resonance_count
    tac_layer = best_sig.tactical_layer
    reason = f"{best_sig.signal_type.value} | {best_sig.reason}"

    # 止损验证
    stop_dist = abs(entry_price - stop_price)
    if direction == 'L' and stop_price >= entry_price:
        continue
    if direction == 'S' and stop_price <= entry_price:
        continue
    if stop_dist < current_atr * 1.5 or stop_dist > current_atr * 6:
        continue

    # 仓位（游击战：防御时减半）
    risk_allowed = account * MAX_RISK_PCT
    if tac_layer == "战略防御":
        risk_allowed *= 0.5
    size_units = risk_allowed / stop_dist
    size_units = min(size_units, 500)

    # ATR-adaptive target
    if direction == 'L':
        target_price = entry_price + stop_dist * TARGET_RR
    else:
        target_price = entry_price - stop_dist * TARGET_RR

    position = Trade(
        entry_time=df.index[i+1],
        direction=direction,
        entry_price=entry_price,
        stop=stop_price,
        target=target_price,
        size_units=size_units,
        risk_dollars=min(risk_allowed, stop_dist * size_units),
        reason=reason,
        resonance=resonance,
        tactical_layer=tac_layer
    )
    daily_trades += 1

print(" 完成\n")

# ============================================================
# 5. 结果统计
# ============================================================
wins = [t for t in TRADES if t.result == 'WIN']
losses = [t for t in TRADES if t.result == 'LOSS']
total = len(TRADES)

if total == 0:
    print("无交易信号。可能原因：数据不足 / 共振阈值太高 / 矛盾转化风险过大")
    sys.exit()

win_count = len(wins)
loss_count = len(losses)
wr = win_count / total * 100
total_pnl = sum(t.pnl for t in TRADES)
avg_win = np.mean([t.pnl for t in wins]) if wins else 0
avg_loss = np.mean([t.pnl for t in losses]) if losses else 0
gross_profit = sum(t.pnl for t in wins) if wins else 0
gross_loss = abs(sum(t.pnl for t in losses)) if losses else 1
pf = gross_profit / max(gross_loss, 1)

peak = INITIAL_CAPITAL
running = INITIAL_CAPITAL
max_dd = 0
for t in TRADES:
    running += t.pnl
    peak = max(peak, running)
    max_dd = max(max_dd, (peak - running) / peak * 100)

print()
print("─" * 90)
print("  交易明细")
print("─" * 90)
for t in TRADES[-40:]:
    day = t.entry_time.strftime('%m/%d %H:%M')
    d = 'LONG' if t.direction == 'L' else 'SHORT'
    sd = abs(t.entry_price - t.stop)
    res = 'WIN' if t.result == 'WIN' else 'LOSS'
    res_info = f"共振{t.resonance}/5 {t.tactical_layer}" if t.resonance else ""
    print(f"  {day} {d:5s} | 入场{t.entry_price:.1f} 止损{t.stop:.1f}({sd:.1f}pt) "
          f"PnL:${t.pnl:+.1f} {res} | {res_info}")
    print(f"         {t.reason[:80]}")

print()
print("=" * 90)
print("  V5 矛盾论·实践论·游击战 — MT5 实时数据回测")
print("=" * 90)
print(f"  数据: {len(df)}根 M2 K线 | {df.index[0].date()} ~ {df.index[-1].date()}")
print(f"  价格: {df['close'].min():.1f} ~ {df['close'].max():.1f} | ATR:{avg_atr:.2f}")
print(f"  ATR止损: {STOP_ATR}x | 盈亏比: 1:{TARGET_RR} | 最低质量: {MIN_QUALITY}")
print(f"  最低共振: {RESONANCE_MIN}/5 | 矛盾转化跳过: {'是' if CONTRADICTION_SKIP else '否'}")
print(f"  ───────────────────────────────────────")
print(f"  交易: {total}笔 | 胜率: {wr:.1f}%")
if avg_loss != 0:
    print(f"  均盈: ${avg_win:+.2f} | 均亏: ${avg_loss:+.2f} | 盈亏比: {abs(avg_win/avg_loss):.2f}")
print(f"  盈利因子: {pf:.2f} | 总PnL: ${total_pnl:+.2f}")
print(f"  最终: ${account:+.2f} ({(account-INITIAL_CAPITAL)/INITIAL_CAPITAL*100:+.1f}%) | 最大回撤: {max_dd:.1f}%")

# 按日统计
print()
print("─" * 90)
print("  按日")
print("─" * 90)
for day in sorted(set(t.entry_time.date() for t in TRADES)):
    dt = [t for t in TRADES if t.entry_time.date() == day]
    dp = sum(t.pnl for t in dt)
    dw = sum(1 for t in dt if t.result == 'WIN')
    print(f"  {day}: {len(dt)}笔({dw}W/{len(dt)-dw}L) PnL:${dp:+.1f}")

# 按共振等级
print()
print("─" * 90)
print("  按共振等级（集中优势兵力验证）")
print("─" * 90)
res_stats = {}
for t in TRADES:
    r = t.resonance
    if r not in res_stats:
        res_stats[r] = {'n': 0, 'w': 0, 'p': 0.0}
    res_stats[r]['n'] += 1
    if t.result == 'WIN':
        res_stats[r]['w'] += 1
    res_stats[r]['p'] += t.pnl
for k in sorted(res_stats):
    v = res_stats[k]
    r = v['w'] / v['n'] * 100 if v['n'] else 0
    print(f"  共振{k}/5: {v['n']:3d}笔 胜率{r:.0f}% PnL:${v['p']:+.1f}")

# 按战术层级
print()
print("─" * 90)
print("  按战术层级")
print("─" * 90)
tac_stats = {}
for t in TRADES:
    tl = t.tactical_layer or "未分类"
    if tl not in tac_stats:
        tac_stats[tl] = {'n': 0, 'w': 0, 'p': 0.0}
    tac_stats[tl]['n'] += 1
    if t.result == 'WIN':
        tac_stats[tl]['w'] += 1
    tac_stats[tl]['p'] += t.pnl
for k, v in sorted(tac_stats.items(), key=lambda x: x[1]['p'], reverse=True):
    r = v['w'] / v['n'] * 100 if v['n'] else 0
    print(f"  {k}: {v['n']:3d}笔 胜率{r:.0f}% PnL:${v['p']:+.1f}")

# 按入场类型
print()
print("─" * 90)
print("  按入场类型")
print("─" * 90)
cats = {}
for t in TRADES:
    c = t.reason.split(':')[0] if ':' in t.reason else t.reason[:20]
    if c not in cats:
        cats[c] = {'n': 0, 'w': 0, 'p': 0.0}
    cats[c]['n'] += 1
    if t.result == 'WIN':
        cats[c]['w'] += 1
    cats[c]['p'] += t.pnl
for k, v in sorted(cats.items(), key=lambda x: x[1]['p'], reverse=True):
    r = v['w'] / v['n'] * 100 if v['n'] else 0
    print(f"  {k:20s}: {v['n']:3d}笔 胜率{r:.0f}% PnL:${v['p']:+.1f}")

# 实践论总结
print()
print("─" * 90)
print("  实践论·再认识")
print("─" * 90)
if wr >= 50:
    print(f"  [OK] 胜率 {wr:.1f}% — 矛盾论增强的状态判断有效")
else:
    print(f"  [!!] 胜率 {wr:.1f}% — 调高最低共振阈值或最低质量门槛")

if res_stats.get(5, {}).get('w', 0) / max(res_stats.get(5, {}).get('n', 1), 1) > \
   res_stats.get(2, {}).get('w', 0) / max(res_stats.get(2, {}).get('n', 1), 1):
    print("  [OK] 高共振胜率高于低共振 — 集中优势兵力原则有效")
else:
    print("  [!!] 共振与胜率相关性弱 — 检查共振评分维度权重")

if max_dd < 10:
    print(f"  [OK] 最大回撤 {max_dd:.1f}% — 保存自己原则到位")
else:
    print(f"  [!!] 最大回撤 {max_dd:.1f}% — 收紧止损或减少单日最大交易数")

print()
