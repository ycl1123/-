"""
MT5 subprocess bridge using QProcess (Qt-native).
Avoids QThread + subprocess.run pipe issues on Windows.
The MT5 connection runs in a child process. If it crashes, the parent survives.
"""
import json
import sys
import tempfile
import os
from pathlib import Path
from PyQt6.QtCore import QProcess, pyqtSignal, QObject


WORKER_SCRIPT = Path(__file__).parent / "_mt5_worker.py"


class MT5Bridge(QObject):
    """Runs MT5 in a QProcess subprocess. C-level crashes won't kill the GUI."""
    result_ready = pyqtSignal(bool, str, dict, dict)  # success, message, {tf: DataFrame}, account_info
    trade_result = pyqtSignal(bool, str, dict)         # success, message, order_info
    sl_tp_result = pyqtSignal(bool, str, dict)         # success, message, {ticket, sl, tp}
    error_occurred = pyqtSignal(str)

    def __init__(self, symbol: str, timeframes: list, history_bars: int = 500):
        super().__init__()
        self.symbol = symbol
        self.timeframes = timeframes
        self.history_bars = history_bars
        self._proc = None
        self._stdout_file = None
        self._stderr_file = None

    def start(self):
        """Launch the MT5 worker subprocess."""
        config = {
            'symbol': self.symbol,
            'timeframes': self.timeframes,
            'history_bars': self.history_bars,
        }

        # Use temp files for stdout/stderr (NOT pipes — avoids Windows pipe hang on child crash)
        self._stdout_file = tempfile.NamedTemporaryFile(
            mode='w', suffix='.json', delete=False, encoding='utf-8')
        self._stderr_file = tempfile.NamedTemporaryFile(
            mode='w', suffix='.log', delete=False, encoding='utf-8')
        stdout_path = self._stdout_file.name
        stderr_path = self._stderr_file.name
        self._stdout_file.close()
        self._stderr_file.close()

        self._proc = QProcess(self)
        self._proc.setProgram(sys.executable)
        self._proc.setArguments([str(WORKER_SCRIPT)])
        self._proc.setStandardOutputFile(stdout_path)
        self._proc.setStandardErrorFile(stderr_path)
        self._proc.setProcessChannelMode(QProcess.ProcessChannelMode.SeparateChannels)

        # Write config to stdin via a temp file
        config_file = tempfile.NamedTemporaryFile(
            mode='w', suffix='.json', delete=False, encoding='utf-8')
        json.dump(config, config_file)
        config_file.close()
        config_path = config_file.name

        self._proc.setProperty('config_file', config_path)
        self._proc.setProperty('stdout_file', stdout_path)
        self._proc.setProperty('stderr_file', stderr_path)

        self._proc.finished.connect(self._on_finished)
        self._proc.errorOccurred.connect(self._on_error)

        # Start with config file path as argument
        self._proc.setArguments([str(WORKER_SCRIPT), config_path])
        self._proc.start()

    def _on_error(self, error):
        if error == QProcess.ProcessError.FailedToStart:
            self.result_ready.emit(False, "MT5子进程无法启动 (Python路径或脚本不存在)", {}, {})
            self._cleanup()
        elif error == QProcess.ProcessError.TimedOut:
            self.result_ready.emit(False, "MT5子进程超时", {}, {})
            self._cleanup()

    def _on_finished(self, exit_code, exit_status):
        proc = self.sender()
        stdout_path = proc.property('stdout_file')
        stderr_path = proc.property('stderr_file')
        config_path = proc.property('config_file')

        try:
            # Read stdout
            output = ''
            if stdout_path and os.path.exists(stdout_path):
                with open(stdout_path, 'r', encoding='utf-8') as f:
                    output = f.read().strip()

            # Read stderr for diagnostics
            stderr_output = ''
            if stderr_path and os.path.exists(stderr_path):
                with open(stderr_path, 'r', encoding='utf-8') as f:
                    stderr_output = f.read()[:500]

            if exit_status != QProcess.ExitStatus.NormalExit or exit_code != 0:
                self.result_ready.emit(
                    False,
                    f"MT5子进程异常退出(code={exit_code})\n{stderr_output}",
                    {}, {}
                )
                return

            if not output:
                self.result_ready.emit(False, "MT5子进程无输出", {}, {})
                return

            data = json.loads(output)
            if data.get('ok'):
                import pandas as pd
                bars_cache = {}
                for tf_str, bar_list in data.get('bars', {}).items():
                    df = pd.DataFrame(bar_list)
                    df['time'] = pd.to_datetime(df['time'], unit='s')
                    df.set_index('time', inplace=True)
                    df = df[['open', 'high', 'low', 'close', 'tick_volume', 'spread']]
                    df.rename(columns={'tick_volume': 'volume'}, inplace=True)
                    bars_cache[tf_str] = df

                account_info = data.get('account') or {}
                positions = data.get('positions', [])
                account_info['positions'] = positions
                login = account_info.get('login', 'unknown')
                self.result_ready.emit(True, f"已连接 (账户: {login})", bars_cache, account_info)
            else:
                self.result_ready.emit(False, data.get('error', 'Unknown error'), {}, {})

        except json.JSONDecodeError as e:
            self.result_ready.emit(
                False,
                f"MT5子进程返回了无效JSON\nstdout({len(output)}字): {output[:200]}\nstderr: {stderr_output[:200]}",
                {}, {}
            )
        except Exception as e:
            self.result_ready.emit(False, f"MT5桥接数据处理异常: {e}", {}, {})

        finally:
            self._cleanup()

    def _cleanup(self):
        proc = self.sender() or self._proc
        if proc is None:
            return
        for prop in ('stdout_file', 'stderr_file', 'config_file'):
            path = proc.property(prop)
            if path:
                try:
                    os.unlink(path)
                except OSError:
                    pass

    def execute_trade(self, symbol: str, direction: str, volume: float,
                       entry_price: float, sl_price: float, tp_price: float,
                       comment: str = "Brooks Signal"):
        """Place a market order with SL/TP via a one-shot subprocess."""
        config = {
            'action': 'execute_trade',
            'symbol': symbol,
            'direction': direction,
            'volume': volume,
            'sl_price': sl_price,
            'tp_price': tp_price,
            'comment': comment,
        }

        self._stdout_file = tempfile.NamedTemporaryFile(
            mode='w', suffix='.json', delete=False, encoding='utf-8')
        self._stderr_file = tempfile.NamedTemporaryFile(
            mode='w', suffix='.log', delete=False, encoding='utf-8')
        stdout_path = self._stdout_file.name
        stderr_path = self._stderr_file.name
        self._stdout_file.close()
        self._stderr_file.close()

        config_file = tempfile.NamedTemporaryFile(
            mode='w', suffix='.json', delete=False, encoding='utf-8')
        json.dump(config, config_file)
        config_file.close()
        config_path = config_file.name

        self._proc = QProcess(self)
        self._proc.setProgram(sys.executable)
        self._proc.setStandardOutputFile(stdout_path)
        self._proc.setStandardErrorFile(stderr_path)
        self._proc.setProcessChannelMode(QProcess.ProcessChannelMode.SeparateChannels)

        self._proc.setProperty('config_file', config_path)
        self._proc.setProperty('stdout_file', stdout_path)
        self._proc.setProperty('stderr_file', stderr_path)
        self._proc.setProperty('mode', 'trade')

        self._proc.finished.connect(self._on_trade_finished)
        self._proc.errorOccurred.connect(self._on_trade_error)
        self._proc.setArguments([str(WORKER_SCRIPT), config_path])
        self._proc.start()

    def _on_trade_error(self, error):
        if error == QProcess.ProcessError.FailedToStart:
            self.trade_result.emit(False, "MT5交易子进程无法启动", {})
            self._cleanup()
        elif error == QProcess.ProcessError.TimedOut:
            self.trade_result.emit(False, "MT5交易子进程超时", {})
            self._cleanup()

    def _on_trade_finished(self, exit_code, exit_status):
        proc = self.sender()
        stdout_path = proc.property('stdout_file')
        stderr_path = proc.property('stderr_file')
        config_path = proc.property('config_file')

        try:
            output = ''
            if stdout_path and os.path.exists(stdout_path):
                with open(stdout_path, 'r', encoding='utf-8') as f:
                    output = f.read().strip()

            if exit_status != QProcess.ExitStatus.NormalExit or exit_code != 0:
                stderr_output = ''
                if stderr_path and os.path.exists(stderr_path):
                    with open(stderr_path, 'r', encoding='utf-8') as f:
                        stderr_output = f.read()[:500]
                self.trade_result.emit(False, f"交易子进程异常退出(code={exit_code})\n{stderr_output}", {})
                return

            if not output:
                self.trade_result.emit(False, "交易子进程无输出", {})
                return

            data = json.loads(output)
            if data.get('ok'):
                self.trade_result.emit(True, f"订单 #{data.get('order_id')} 已成交", data)
            else:
                self.trade_result.emit(False, data.get('error', 'Unknown error'), data)

        except json.JSONDecodeError as e:
            self.trade_result.emit(False, f"交易返回无效JSON: {output[:200]}", {})
        except Exception as e:
            self.trade_result.emit(False, f"交易结果处理异常: {e}", {})

        finally:
            self._cleanup()

    def set_sl_tp(self, ticket: int, sl_price: float, tp_price: float, symbol: str = ""):
        """Modify an existing position's SL/TP via a one-shot subprocess."""
        config = {
            'action': 'set_sl_tp',
            'ticket': ticket,
            'sl_price': sl_price,
            'tp_price': tp_price,
            'symbol': symbol,
        }

        self._stdout_file = tempfile.NamedTemporaryFile(
            mode='w', suffix='.json', delete=False, encoding='utf-8')
        self._stderr_file = tempfile.NamedTemporaryFile(
            mode='w', suffix='.log', delete=False, encoding='utf-8')
        stdout_path = self._stdout_file.name
        stderr_path = self._stderr_file.name
        self._stdout_file.close()
        self._stderr_file.close()

        config_file = tempfile.NamedTemporaryFile(
            mode='w', suffix='.json', delete=False, encoding='utf-8')
        json.dump(config, config_file)
        config_file.close()
        config_path = config_file.name

        self._proc = QProcess(self)
        self._proc.setProgram(sys.executable)
        self._proc.setStandardOutputFile(stdout_path)
        self._proc.setStandardErrorFile(stderr_path)
        self._proc.setProcessChannelMode(QProcess.ProcessChannelMode.SeparateChannels)

        self._proc.setProperty('config_file', config_path)
        self._proc.setProperty('stdout_file', stdout_path)
        self._proc.setProperty('stderr_file', stderr_path)
        self._proc.setProperty('mode', 'sl_tp')

        self._proc.finished.connect(self._on_sl_tp_finished)
        self._proc.errorOccurred.connect(self._on_sl_tp_error)
        self._proc.setArguments([str(WORKER_SCRIPT), config_path])
        self._proc.start()

    def _on_sl_tp_error(self, error):
        if error == QProcess.ProcessError.FailedToStart:
            self.sl_tp_result.emit(False, "SL/TP子进程无法启动", {})
            self._cleanup()
        elif error == QProcess.ProcessError.TimedOut:
            self.sl_tp_result.emit(False, "SL/TP子进程超时", {})
            self._cleanup()

    def _on_sl_tp_finished(self, exit_code, exit_status):
        proc = self.sender()
        stdout_path = proc.property('stdout_file')
        stderr_path = proc.property('stderr_file')

        try:
            output = ''
            if stdout_path and os.path.exists(stdout_path):
                with open(stdout_path, 'r', encoding='utf-8') as f:
                    output = f.read().strip()

            if exit_status != QProcess.ExitStatus.NormalExit or exit_code != 0:
                stderr_output = ''
                if stderr_path and os.path.exists(stderr_path):
                    with open(stderr_path, 'r', encoding='utf-8') as f:
                        stderr_output = f.read()[:500]
                self.sl_tp_result.emit(False, f"SL/TP子进程异常退出(code={exit_code})\n{stderr_output}", {})
                return

            if not output:
                self.sl_tp_result.emit(False, "SL/TP子进程无输出", {})
                return

            data = json.loads(output)
            if data.get('ok'):
                self.sl_tp_result.emit(
                    True,
                    f"止损止盈已挂上 (单号#{data.get('ticket')})",
                    data
                )
            else:
                self.sl_tp_result.emit(False, data.get('error', 'Unknown error'), data)

        except json.JSONDecodeError:
            self.sl_tp_result.emit(False, f"SL/TP返回无效JSON: {output[:200]}", {})
        except Exception as e:
            self.sl_tp_result.emit(False, f"SL/TP结果处理异常: {e}", {})

        finally:
            self._cleanup()

    def stop(self):
        if self._proc and self._proc.state() != QProcess.ProcessState.NotRunning:
            self._proc.kill()
            self._proc.waitForFinished(3000)
