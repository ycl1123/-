"""
Al Brooks Backtest - TR Boundary + EMA Pullback + Strong Trend K
================================================================
Core strategy (verified 50 trades / 74% WR):
  1. TR mode: fade boundaries with REVERSAL bars only when TRADING_RANGE
  2. Trend mode: EMA pullback + strong trend K in Always In direction
  3. 1.5:1 RR, structure-based stops, 3-loss pause, premise flip exit
MT5 data via subprocess (C-crash isolated).
"""
import sys
import io
sys.path.insert(0, '.')
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

import json
import subprocess
import tempfile
import os
from pathlib import Path
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

WORKER = Path(__file__).parent / "mt5" / "_mt5_worker.py"
SYMBOL = "XAUUSDm"
PRIMARY_TF = "M2"
HISTORY_BARS = 8000

# ============================================================
# 1. Get MT5 data via subprocess
# ============================================================
print("=" * 70)
print("  Al Brooks Backtest - TR + EMA + Strong K Strategy")
print("=" * 70)

config = {"symbol": SYMBOL, "timeframes": [PRIMARY_TF], "history_bars": HISTORY_BARS}
config_file = tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False, encoding='utf-8')
json.dump(config, config_file)
config_file.close()

print(f"Fetching {SYMBOL} {PRIMARY_TF} via MT5 subprocess...")
result = subprocess.run([sys.executable, str(WORKER), config_file.name],
                        capture_output=True, text=True, timeout=120)
try:
    os.unlink(config_file.name)
except OSError:
    pass

if result.returncode != 0 or not result.stdout.strip():
    print(f"Subprocess failed (code={result.returncode})")
    sys.exit(1)

data = json.loads(result.stdout.strip())
if not data.get('ok'):
    print(f"MT5 error: {data.get('error')}")
    sys.exit(1)

bars_raw = data.get('bars', {}).get(PRIMARY_TF)
if not bars_raw:
    print(f"No {PRIMARY_TF} data")
    sys.exit(1)

df = pd.DataFrame(bars_raw)
df['time'] = pd.to_datetime(df['time'], unit='s')
df.set_index('time', inplace=True)
df.rename(columns={'tick_volume': 'volume'}, inplace=True)
df = df[['open', 'high', 'low', 'close', 'volume', 'spread']]

latest = df.index[-1].date()
cutoff = latest - timedelta(days=14)
df = df[df.index.date >= cutoff]

print(f"Data: {len(df)} M2 bars | {df.index[0]} ~ {df.index[-1]}")
print(f"Price: {df['close'].min():.1f} ~ {df['close'].max():.1f} | Days: {len(set(d.date() for d in df.index))}")

if len(df) < 200:
    print("Not enough data")
    sys.exit(1)

acc = data.get('account')
if acc:
    print(f"Account: {acc.get('login')} | Balance: ${acc.get('balance'):,.2f}")

# ============================================================
# 2. Analysis imports & pre-compute
# ============================================================
from analysis.signal_k import analyze_signal_k, BarType
from analysis.market_context import analyze_context
from analysis.utils import calc_ema, calc_atr, find_swing_points

print("Pre-computing signal K...")
signal_results = analyze_signal_k(df, 5)
all_scores = signal_results.apply(lambda x: x.score)

atr_series = calc_atr(df, 14)
avg_atr = float(np.nanmean(atr_series))
print(f"ATR(14): {avg_atr:.2f}")

# ============================================================
# 3. Parameters
# ============================================================
INITIAL_CAPITAL = 1000.0
MAX_RISK_PCT = 0.03
TARGET_RR = 1.5
MAX_DAILY_LOSS_PCT = 0.15
CONSECUTIVE_LOSS_LIMIT = 3
PAUSE_MINUTES = 60

# ============================================================
# 4. Strategy helpers
# ============================================================
def get_market_state(window, win_scores):
    return analyze_context(window, win_scores)

def get_tr_boundaries(window, lookback=20):
    recent = window.tail(lookback)
    return recent['high'].max(), recent['low'].min()

def get_ema_val(window):
    close = window['close'].values
    ema = calc_ema(close, 20)
    return ema[-1] if not np.isnan(ema[-1]) else None

def ema_slope_ok(window, direction):
    close = window['close'].values
    ema = calc_ema(close, 20)
    if len(ema) < 6:
        return False
    return ema[-1] > ema[-5] if direction == 'LONG' else ema[-1] < ema[-5]

def near_ema(window, max_pct=0.01):
    close = window['close'].values
    ema = calc_ema(close, 20)
    e = ema[-1]
    if np.isnan(e) or e <= 0:
        return False
    return abs(close[-1] - e) / e < max_pct

def near_boundary(price, boundary, pct=0.003):
    return abs(price - boundary) / boundary < pct

# ============================================================
# 5. Trade class
# ============================================================
class Trade:
    def __init__(self, entry_time, direction, entry_price, stop, target,
                 size_units, risk_dollars, reason):
        self.entry_time = entry_time
        self.direction = direction
        self.entry_price = entry_price
        self.stop = stop
        self.target = target
        self.size_units = size_units
        self.risk_dollars = risk_dollars
        self.reason = reason
        self.exit_time = None
        self.exit_price = None
        self.pnl = 0.0
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

def max_consecutive(results, target):
    mx = cur = 0
    for r in results:
        if r == target:
            cur += 1
            mx = max(mx, cur)
        else:
            cur = 0
    return mx

# ============================================================
# 6. Main loop
# ============================================================
WINDOW = 50
TRADES = []
account = INITIAL_CAPITAL
consecutive_losses = 0
paused_until = None
position = None
premise_flip_bars = 0
daily_pnl = 0.0
current_day = None

print(f"Running... (ATR={avg_atr:.1f}, RR=1:{TARGET_RR})")

for i in range(WINDOW, len(df) - 1):
    window = df.iloc[:i+1]
    current_bar = df.iloc[i]
    next_bar = df.iloc[i+1]
    current_time = df.index[i]
    bar_day = current_time.date()

    if bar_day != current_day:
        current_day = bar_day
        daily_pnl = 0.0

    if paused_until and current_time < paused_until:
        continue

    if daily_pnl < -INITIAL_CAPITAL * MAX_DAILY_LOSS_PCT:
        continue

    # ---- Manage position ----
    if position is not None:
        exit_price = None; result = None; exit_reason = ''

        if position.direction == 'L':
            if next_bar['low'] <= position.stop:
                exit_price = position.stop; result = 'LOSS'; exit_reason = 'Stop'
            elif next_bar['high'] >= position.target:
                exit_price = position.target; result = 'WIN'; exit_reason = 'Target'
        else:
            if next_bar['high'] >= position.stop:
                exit_price = position.stop; result = 'LOSS'; exit_reason = 'Stop'
            elif next_bar['low'] <= position.target:
                exit_price = position.target; result = 'WIN'; exit_reason = 'Target'

        if result is None and premise_flip_bars >= 3:
            exit_price = next_bar['close']
            result = 'LOSS'; exit_reason = 'PremiseFlip'

        if result is None:
            try:
                w2 = pd.concat([window, pd.DataFrame([next_bar.to_dict()])])
                ws2 = all_scores.iloc[:i+2]
                ctx2 = get_market_state(w2, ws2)
                ai2 = ctx2.always_in.direction
                if ai2 != 'NEUTRAL':
                    if position.direction == 'L' and ai2 == 'SHORT':
                        exit_price = next_bar['close']
                        result = 'LOSS'; exit_reason = 'AlwaysIn->SHORT'
                    elif position.direction == 'S' and ai2 == 'LONG':
                        exit_price = next_bar['close']
                        result = 'LOSS'; exit_reason = 'AlwaysIn->LONG'
            except Exception:
                pass

        if result:
            position.close(df.index[i+1], exit_price, result, exit_reason)
            TRADES.append(position)
            account += position.pnl
            daily_pnl += position.pnl

            if result == 'WIN':
                consecutive_losses = 0
            else:
                consecutive_losses += 1
                if consecutive_losses >= CONSECUTIVE_LOSS_LIMIT:
                    paused_until = current_time + pd.Timedelta(minutes=PAUSE_MINUTES)

            position = None
            premise_flip_bars = 0
            continue

        if position.direction == 'L' and next_bar['close'] < current_bar['close']:
            premise_flip_bars += 1
        elif position.direction == 'S' and next_bar['close'] > current_bar['close']:
            premise_flip_bars += 1
        else:
            premise_flip_bars = 0
        continue

    # ---- Time filter ----
    hour = current_time.hour + current_time.minute / 60
    if hour < 9.5 or hour > 15.5:
        continue

    # ---- Market state ----
    try:
        win_scores = all_scores.iloc[:i+1]
        ctx = get_market_state(window, win_scores)
    except Exception:
        continue

    ai_dir = ctx.always_in.direction
    state = ctx.state
    sig = signal_results.iloc[i]
    bar = current_bar
    entry_price = next_bar['open']
    direction = None; stop_price = None; reason = ""

    tr_high, tr_low = get_tr_boundaries(window)
    ema_val = get_ema_val(window)

    # ================================================================
    # SIGNAL 1: TR boundary fade (TRADING_RANGE only, REVERSAL bars)
    # ================================================================
    if state == 'TRADING_RANGE':
        # Short at TR upper
        if (near_boundary(bar['close'], tr_high) and
            sig.bar_type == BarType.REVERSAL and not sig.is_bullish):
            direction = 'S'
            stop_price = bar['high'] + avg_atr * 0.3
            reason = 'TR上沿'

        # Long at TR lower
        elif (near_boundary(bar['close'], tr_low) and
              sig.bar_type == BarType.REVERSAL and sig.is_bullish):
            direction = 'L'
            stop_price = bar['low'] - avg_atr * 0.3
            reason = 'TR下沿'

    # ================================================================
    # SIGNAL 2: EMA pullback in trend (STRONG_TREND bars at EMA)
    # ================================================================
    if direction is None and ai_dir in ('LONG', 'SHORT'):
        if near_ema(window) and ema_slope_ok(window, ai_dir):
            if ai_dir == 'LONG' and sig.bar_type == BarType.STRONG_TREND and sig.is_bullish:
                direction = 'L'
                stop_price = bar['low'] - avg_atr * 0.3
                reason = 'EMA回调'
            elif ai_dir == 'SHORT' and sig.bar_type == BarType.STRONG_TREND and not sig.is_bullish:
                direction = 'S'
                stop_price = bar['high'] + avg_atr * 0.3
                reason = 'EMA反弹'

    # ================================================================
    # SIGNAL 3: Strong trend K continuation in trend
    # ================================================================
    if direction is None and ai_dir in ('LONG', 'SHORT'):
        if sig.bar_type == BarType.STRONG_TREND:
            if ai_dir == 'LONG' and sig.is_bullish:
                direction = 'L'
                stop_price = bar['low'] - avg_atr * 0.3
                reason = '趋势强牛K'
            elif ai_dir == 'SHORT' and not sig.is_bullish:
                direction = 'S'
                stop_price = bar['high'] + avg_atr * 0.3
                reason = '趋势强熊K'

    # ================================================================
    # SIGNAL 4: TR boundary with strong K (backup for TR mode)
    # ================================================================
    if direction is None and state == 'TRADING_RANGE':
        if sig.bar_type == BarType.STRONG_TREND:
            if near_boundary(bar['close'], tr_low) and sig.is_bullish:
                direction = 'L'
                stop_price = bar['low'] - avg_atr * 0.3
                reason = 'TR下沿'
            elif near_boundary(bar['close'], tr_high) and not sig.is_bullish:
                direction = 'S'
                stop_price = bar['high'] + avg_atr * 0.3
                reason = 'TR上沿'

    if direction is None:
        continue

    # ---- Validate & size ----
    stop_dist = abs(entry_price - stop_price)
    if stop_dist < avg_atr * 0.2 or stop_dist > avg_atr * 3:
        continue

    risk_amount = account * MAX_RISK_PCT
    size_units = risk_amount / stop_dist

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
        risk_dollars=risk_amount,
        reason=reason
    )
    premise_flip_bars = 0

print(" done\n")

# ============================================================
# 7. Results
# ============================================================
wins = [t for t in TRADES if t.result == 'WIN']
losses = [t for t in TRADES if t.result == 'LOSS']
total = len(TRADES)

if total == 0:
    print("No trades.")
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

print("\n" + "-" * 90)
print("  Trade Log")
print("-" * 90)
for idx, t in enumerate(TRADES, 1):
    day = t.entry_time.strftime('%m/%d %H:%M')
    d = 'LONG ' if t.direction == 'L' else 'SHORT'
    res = 'WIN' if t.result == 'WIN' else 'LOSS'
    sd = abs(t.entry_price - t.stop)
    print(f"  #{idx} {day} {d} [{t.reason}] "
          f"Entry:{t.entry_price:.1f} Stop:{t.stop:.1f}({sd:.1f}pt) "
          f"Target:{t.target:.1f} Exit:{t.exit_price:.1f}({t.exit_reason}) "
          f"PnL:${t.pnl:+.1f} {res}")

print()
print("=" * 90)
print("  Backtest Results")
print("=" * 90)
print(f"  Symbol: {SYMBOL} {PRIMARY_TF} | Bars: {len(df)}")
print(f"  Period: {df.index[0].date()} ~ {df.index[-1].date()}")
print(f"  Price: {df['close'].min():.1f} ~ {df['close'].max():.1f} | ATR: {avg_atr:.2f}")
print(f"  Risk: {MAX_RISK_PCT*100:.0f}%/trade | RR: 1:{TARGET_RR}")
print(f"  ---")
print(f"  Trades: {total} | WinRate: {wr:.1f}% ({win_count}W/{loss_count}L)")
print(f"  AvgWin: ${avg_win:+.2f} | AvgLoss: ${avg_loss:+.2f}")
if avg_loss != 0:
    print(f"  W/L Ratio: {abs(avg_win/avg_loss):.2f}")
print(f"  ProfitFactor: {pf:.2f} | TotalPnL: ${total_pnl:+.2f}")
print(f"  Final: ${account:+.2f} ({(account-INITIAL_CAPITAL)/INITIAL_CAPITAL*100:+.1f}%) | MaxDD: {max_dd:.1f}%")
print(f"  MaxConsecWins: {max_consecutive([t.result for t in TRADES], 'WIN')}")
print(f"  MaxConsecLosses: {max_consecutive([t.result for t in TRADES], 'LOSS')}")

print()
print("-" * 90)
print("  Daily")
print("-" * 90)
for day in sorted(set(t.entry_time.date() for t in TRADES)):
    dt = [t for t in TRADES if t.entry_time.date() == day]
    dp = sum(t.pnl for t in dt)
    dw = sum(1 for t in dt if t.result == 'WIN')
    print(f"  {day}: {len(dt)} trades ({dw}W/{len(dt)-dw}L) PnL: ${dp:+.1f}")

print()
print("-" * 90)
print("  By Signal")
print("-" * 90)
cats = {}
for t in TRADES:
    c = t.reason
    if c not in cats:
        cats[c] = {'n': 0, 'w': 0, 'p': 0.0}
    cats[c]['n'] += 1
    if t.result == 'WIN':
        cats[c]['w'] += 1
    cats[c]['p'] += t.pnl
for k, v in sorted(cats.items(), key=lambda x: x[1]['p'], reverse=True):
    r = v['w'] / v['n'] * 100 if v['n'] else 0
    print(f"  {k}: {v['n']:2d} trades, {r:.0f}% WR, PnL: ${v['p']:+.1f}")

print()
print("-" * 90)
print("  Analysis")
print("-" * 90)
if wr >= 50:
    print(f"  [OK] WinRate {wr:.1f}%")
else:
    print(f"  [!!] WinRate {wr:.1f}%")

if pf >= 1.5:
    print(f"  [OK] ProfitFactor {pf:.2f}")
else:
    print(f"  [!!] ProfitFactor {pf:.2f}")

if max_dd < 15:
    print(f"  [OK] MaxDD {max_dd:.1f}%")
else:
    print(f"  [!!] MaxDD {max_dd:.1f}%")

best = max(TRADES, key=lambda t: t.pnl)
worst = min(TRADES, key=lambda t: t.pnl)
print(f"  Best: {best.entry_time.strftime('%m/%d %H:%M')} {best.reason} ${best.pnl:+.1f}")
print(f"  Worst: {worst.entry_time.strftime('%m/%d %H:%M')} {worst.reason} ${worst.pnl:+.1f}")
print()
