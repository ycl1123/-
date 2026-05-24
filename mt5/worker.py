"""MT5 worker thread — isolates MT5 C-level crashes from GUI."""
from PyQt6.QtCore import QThread, pyqtSignal
import pandas as pd
from datetime import datetime

# Lazy MT5 import
_mt5 = None
_TIMEFRAME_MAP = {}

def _init_mt5():
    global _mt5, _TIMEFRAME_MAP
    if _mt5 is not None:
        return _mt5
    import MetaTrader5 as mt5
    _mt5 = mt5
    _TIMEFRAME_MAP = {
        "M1": mt5.TIMEFRAME_M1, "M2": mt5.TIMEFRAME_M2,
        "M3": mt5.TIMEFRAME_M3, "M4": mt5.TIMEFRAME_M4,
        "M5": mt5.TIMEFRAME_M5, "M6": mt5.TIMEFRAME_M6,
        "M10": mt5.TIMEFRAME_M10, "M12": mt5.TIMEFRAME_M12,
        "M15": mt5.TIMEFRAME_M15, "M20": mt5.TIMEFRAME_M20,
        "M30": mt5.TIMEFRAME_M30, "H1": mt5.TIMEFRAME_H1,
        "H4": mt5.TIMEFRAME_H4, "D1": mt5.TIMEFRAME_D1,
    }
    return _mt5


class MT5ConnectWorker(QThread):
    """Thread that initializes MT5 and loads initial history."""
    finished = pyqtSignal(bool, str, dict)  # success, message, {tf: DataFrame}

    def __init__(self, symbol: str, timeframes: list, history_bars: int = 500):
        super().__init__()
        self.symbol = symbol
        self.timeframes = timeframes
        self.history_bars = history_bars

    def run(self):
        try:
            mt5 = _init_mt5()
            if mt5 is None:
                self.finished.emit(False, "MetaTrader5 模块不可用", {})
                return

            if not mt5.initialize():
                error = mt5.last_error()
                self.finished.emit(False, f"MT5 初始化失败: {error}", {})
                return

            account = mt5.account_info()
            name = account.login if account else "未知"

            bars_cache = {}
            for tf_str in self.timeframes:
                try:
                    mt5_tf = _TIMEFRAME_MAP.get(tf_str)
                    if mt5_tf is None:
                        continue
                    rates = mt5.copy_rates_from_pos(self.symbol, mt5_tf, 0, self.history_bars)
                    if rates is None or len(rates) == 0:
                        continue
                    df = pd.DataFrame(rates)
                    df['time'] = pd.to_datetime(df['time'], unit='s')
                    df.set_index('time', inplace=True)
                    df.rename(columns={'open': 'open', 'high': 'high', 'low': 'low',
                                      'close': 'close', 'tick_volume': 'volume'}, inplace=True)
                    df = df[['open', 'high', 'low', 'close', 'volume', 'spread']]
                    bars_cache[tf_str] = df
                except Exception as e:
                    print(f"[MT5 Worker] 加载 {tf_str} 失败: {e}")

            self.finished.emit(True, f"已连接 (账户: {name})", bars_cache)

        except Exception as e:
            self.finished.emit(False, f"MT5 线程异常: {e}", {})


class MT5PollWorker(QThread):
    """Thread for polling new bars."""
    new_bar = pyqtSignal(str, pd.DataFrame)

    def __init__(self, symbol: str, timeframe: str, last_bar_time, history_bars: int = 500):
        super().__init__()
        self.symbol = symbol
        self.timeframe = timeframe
        self.last_bar_time = last_bar_time
        self.history_bars = history_bars

    def run(self):
        try:
            mt5 = _init_mt5()
            if mt5 is None:
                return

            mt5_tf = _TIMEFRAME_MAP.get(self.timeframe)
            if mt5_tf is None:
                return

            rates = mt5.copy_rates_from_pos(self.symbol, mt5_tf, 0, 1)
            if rates is None or len(rates) == 0:
                return

            bar_time = pd.to_datetime(rates[0]['time'], unit='s')
            if self.last_bar_time is None or bar_time > self.last_bar_time:
                # Load full history
                rates_full = mt5.copy_rates_from_pos(self.symbol, mt5_tf, 0, self.history_bars)
                if rates_full is not None and len(rates_full) > 0:
                    df = pd.DataFrame(rates_full)
                    df['time'] = pd.to_datetime(df['time'], unit='s')
                    df.set_index('time', inplace=True)
                    df.rename(columns={'open': 'open', 'high': 'high', 'low': 'low',
                                      'close': 'close', 'tick_volume': 'volume'}, inplace=True)
                    df = df[['open', 'high', 'low', 'close', 'volume', 'spread']]
                    self.new_bar.emit(self.timeframe, df)
        except Exception as e:
            print(f"[MT5 Worker] poll 异常: {e}")
