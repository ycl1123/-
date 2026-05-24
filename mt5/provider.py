import pandas as pd
from datetime import datetime, timedelta
from PyQt6.QtCore import QObject, QTimer, pyqtSignal

# Lazy import — MetaTrader5 may not be installed or may crash at C level
_mt5 = None
TIMEFRAME_MAP = {}

def _get_mt5():
    """Lazy-load MetaTrader5. Returns None if not available."""
    global _mt5, TIMEFRAME_MAP
    if _mt5 is not None:
        return _mt5
    try:
        import MetaTrader5 as mt5
        _mt5 = mt5
        TIMEFRAME_MAP = {
            "M1": mt5.TIMEFRAME_M1, "M2": mt5.TIMEFRAME_M2,
            "M3": mt5.TIMEFRAME_M3, "M4": mt5.TIMEFRAME_M4,
            "M5": mt5.TIMEFRAME_M5, "M6": mt5.TIMEFRAME_M6,
            "M10": mt5.TIMEFRAME_M10, "M12": mt5.TIMEFRAME_M12,
            "M15": mt5.TIMEFRAME_M15, "M20": mt5.TIMEFRAME_M20,
            "M30": mt5.TIMEFRAME_M30, "H1": mt5.TIMEFRAME_H1,
            "H4": mt5.TIMEFRAME_H4, "D1": mt5.TIMEFRAME_D1,
        }
        return _mt5
    except Exception as e:
        print(f"[MT5] MetaTrader5 导入失败: {e}")
        return None


class MT5Provider(QObject):
    new_bar = pyqtSignal(str, pd.DataFrame)
    connection_status = pyqtSignal(bool, str)

    def __init__(self, symbol: str, timeframes: list[str], history_bars: int = 500):
        super().__init__()
        self.symbol = symbol
        self.timeframes = timeframes
        self.history_bars = history_bars
        self._connected = False
        self._last_bar_times: dict[str, datetime] = {}
        self._bars_cache: dict[str, pd.DataFrame] = {}

    def connect(self) -> bool:
        try:
            mt5 = _get_mt5()
            if mt5 is None:
                self.connection_status.emit(False, "MetaTrader5 模块不可用")
                return False

            if not mt5.initialize():
                error = mt5.last_error()
                self.connection_status.emit(False, f"MT5 初始化失败: {error}")
                return False

            self._connected = True
            account = mt5.account_info()
            name = account.login if account else "未知"
            self.connection_status.emit(True, f"已连接 (账户: {name})")

            for tf in self.timeframes:
                try:
                    self._load_history(tf)
                except Exception as e:
                    print(f"[MT5] 加载 {tf} 失败: {e}")

            return True
        except Exception as e:
            self.connection_status.emit(False, f"MT5 连接异常: {e}")
            return False

    def disconnect(self):
        self._connected = False
        try:
            mt5 = _get_mt5()
            if mt5:
                mt5.shutdown()
        except:
            pass
        self.connection_status.emit(False, "已断开")

    def _load_history(self, timeframe: str):
        try:
            mt5 = _get_mt5()
            if mt5 is None:
                return
            tf = TIMEFRAME_MAP.get(timeframe)
            if tf is None:
                return

            rates = mt5.copy_rates_from_pos(self.symbol, tf, 0, self.history_bars)
            if rates is None or len(rates) == 0:
                return

            df = pd.DataFrame(rates)
            df['time'] = pd.to_datetime(df['time'], unit='s')
            df.set_index('time', inplace=True)
            df.rename(columns={'open': 'open', 'high': 'high', 'low': 'low',
                              'close': 'close', 'tick_volume': 'volume'}, inplace=True)
            df = df[['open', 'high', 'low', 'close', 'volume', 'spread']]

            self._bars_cache[timeframe] = df
            if len(df) > 0:
                self._last_bar_times[timeframe] = df.index[-1]
        except Exception as e:
            print(f"[MT5] _load_history({timeframe}) 异常: {e}")

    def get_bars(self, timeframe: str) -> pd.DataFrame | None:
        return self._bars_cache.get(timeframe)

    def poll(self):
        if not self._connected:
            return

        try:
            mt5 = _get_mt5()
            if mt5 is None:
                return
            for tf in self.timeframes:
                mt5_tf = TIMEFRAME_MAP.get(tf)
                if mt5_tf is None:
                    continue

                rates = mt5.copy_rates_from_pos(self.symbol, mt5_tf, 0, 1)
                if rates is None or len(rates) == 0:
                    continue

                bar_time = pd.to_datetime(rates[0]['time'], unit='s')
                last_time = self._last_bar_times.get(tf)

                if last_time is None or bar_time > last_time:
                    self._load_history(tf)
                    df = self._bars_cache.get(tf)
                    if df is not None and len(df) > 0:
                        self.new_bar.emit(tf, df)
        except Exception as e:
            print(f"[MT5] poll 异常: {e}")

    @property
    def is_connected(self) -> bool:
        return self._connected
