"""Demo launcher — feeds synthetic data to the GUI without MT5."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from PyQt6.QtCore import QTimer, Qt

from gui.app import create_app
from gui.main_window import MainWindow
from config.settings import load_config
from mt5.provider import MT5Provider
from analysis.engine import AnalysisEngine, AnalysisResult


def make_price_bars(data):
    bars = []
    for o, drift in data:
        c = o + drift
        h = max(o, c) + abs(np.random.randn()) * 1.5
        l = min(o, c) - abs(np.random.randn()) * 1.5
        bars.append({'open': o, 'high': h, 'low': l, 'close': c})
    return bars


def main():
    np.random.seed(2025)

    # Generate a full week of synthetic data
    from test_上周数据 import (make_uptrend, make_range, make_wedge_bottom,
                               make_sell_climax, make_bear_trap)

    start_price = 2680.0
    n_bars = 78

    mon_data = make_uptrend(start_price, n_bars, 2.5)
    mon_bars = make_price_bars(mon_data)

    last_close = mon_bars[-1]['close']
    tue_data = make_range(last_close, n_bars, center=last_close, width=12)
    tue_bars = make_price_bars(tue_data)

    last_close = tue_bars[-1]['close']
    wed_data = make_wedge_bottom(last_close, n_bars, 1.5)
    wed_bars = make_price_bars(wed_data)

    last_close = wed_bars[-1]['close']
    thu_data = make_sell_climax(last_close, n_bars, 1.5)
    thu_bars = make_price_bars(thu_data)

    last_close = thu_bars[-1]['close']
    fri_data = make_bear_trap(last_close, n_bars // 2, 1.2)
    fri_bars = make_price_bars(fri_data)

    all_bars = mon_bars + tue_bars + wed_bars + thu_bars + fri_bars

    t = datetime(2026, 5, 18, 9, 30)
    dates = []
    for i in range(len(all_bars)):
        dates.append(t)
        t += timedelta(minutes=5)
        if t.hour >= 16:
            t = t.replace(hour=9, minute=30) + timedelta(days=1)

    dates = dates[:len(all_bars)]
    df = pd.DataFrame(all_bars, index=pd.DatetimeIndex(dates))
    df['volume'] = np.random.randint(200, 2000, len(df))
    df['spread'] = np.ones(len(df)) * 2

    print(f"Demo模式: {len(df)}根K线 ({dates[0]} ~ {dates[-1]})")
    print(f"价格范围: {df['close'].min():.1f} ~ {df['close'].max():.1f}")

    config = load_config()
    app = create_app()
    window = MainWindow(config)

    # Override MT5 connection: simulate connected with demo data
    window.status_label.setText("MT5: 模拟账户 (Demo)")
    window.status_label.setStyleSheet("color: #00E676;")
    window.status_bar.showMessage("Demo模式 — 合成数据回放")

    # Feed bars sequentially into the engine
    all_dates = df.index.tolist()
    bar_idx = [50]  # start with enough bars for analysis

    def feed_next_bar():
        idx = bar_idx[0]
        if idx >= len(df):
            # Loop back to simulate ongoing trading
            bar_idx[0] = len(df) - 20
            return

        window_data = df.iloc[:idx + 1]
        result = window.engine.analyze(config.symbol, config.timeframes["primary"], window_data)
        window._update_all_panels(result)
        window._generate_alerts(result)

        bar_time = all_dates[idx]
        window.status_bar.showMessage(
            f"Demo回放: {bar_time.strftime('%m/%d %H:%M')} | "
            f"Always In: {result.context.always_in.direction if result.context else '--'} | "
            f"信号: {len(result.trade_signals)}个 | "
            f"第{idx+1}/{len(df)}根K线"
        )

        bar_idx[0] += 1

    # Timer: advance 1 bar every 300ms
    timer = QTimer()
    timer.timeout.connect(feed_next_bar)
    timer.start(300)

    # Start with initial feed
    feed_next_bar()

    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
