"""诊断启动脚本 — 逐步检查并记录到文件（使用子进程桥接，隔离C层崩溃）"""
import sys
import traceback
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent))

LOG_FILE = Path(__file__).parent / "启动日志.txt"

def log(msg: str):
    entry = f"[{datetime.now().strftime('%H:%M:%S')}] {msg}"
    print(entry)
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(entry + "\n")

log("=" * 50)
log("诊断启动开始（子进程桥接模式）")

# Step 1: Config
try:
    from config.settings import load_config
    config = load_config()
    log(f"Step1 配置: OK - {config.symbol} / {config.timeframes}")
except Exception as e:
    log(f"Step1 配置: FAIL - {e}")
    traceback.print_exc()
    input("按回车退出...")
    sys.exit(1)

# Step 2: PyQt6
try:
    from PyQt6.QtWidgets import QApplication, QMessageBox
    from PyQt6.QtCore import QTimer
    log("Step2 PyQt6: OK")
except Exception as e:
    log(f"Step2 PyQt6: FAIL - {e}")
    traceback.print_exc()
    input("按回车退出...")
    sys.exit(1)

# Step 3: GUI modules
try:
    from gui.app import create_app
    from gui.main_window import MainWindow
    from gui.context_panel import MarketContextPanel
    from gui.signal_k_panel import SignalKPanel
    from gui.sr_panel import SRPanel
    from gui.zones_panel import ZonesPanel
    from gui.signals_panel import TradingSignalsPanel
    from gui.alert_log import AlertLogWidget
    log("Step3 GUI模块: OK")
except Exception as e:
    log(f"Step3 GUI模块: FAIL - {e}")
    traceback.print_exc()
    input("按回车退出...")
    sys.exit(1)

# Step 4: Bridge module (subprocess-based, won't trigger MT5 C-crash)
try:
    from mt5.bridge import MT5Bridge
    log("Step4 MT5桥接模块: import OK（子进程隔离模式）")
except Exception as e:
    log(f"Step4 MT5桥接模块: FAIL - {e}")
    traceback.print_exc()
    input("按回车退出...")
    sys.exit(1)

# Step 5: Create QApplication
try:
    app = create_app()
    log("Step5 QApplication: OK")
except Exception as e:
    log(f"Step5 QApplication: FAIL - {e}")
    traceback.print_exc()
    input("按回车退出...")
    sys.exit(1)

# Step 6: Create MainWindow
try:
    log("Step6 创建主窗口...")
    window = MainWindow(config)
    log("Step6 MainWindow: OK")
except Exception as e:
    log(f"Step6 MainWindow: FAIL - {e}")
    traceback.print_exc()
    try:
        QMessageBox.critical(None, "启动失败", str(e))
    except:
        pass
    input("按回车退出...")
    sys.exit(1)

# Step 7: Test subprocess bridge (quick MT5 data fetch)
try:
    log("Step7 测试子进程桥接(获取MT5数据)...")
    bridge = MT5Bridge(config.symbol,
                       [config.timeframes["primary"]] + config.timeframes.get("secondary", []),
                       config.mt5.history_bars)

    result_holder = []
    def on_result(success, msg, bars):
        result_holder.append((success, msg, bars))

    bridge.result_ready.connect(on_result)
    bridge.start()
    bridge.wait(15000)  # Wait up to 15s for subprocess

    if result_holder:
        success, msg, bars = result_holder[0]
        if success:
            bar_counts = {tf: len(df) for tf, df in bars.items()}
            log(f"Step7 桥接测试: OK - {msg} | K线: {bar_counts}")
        else:
            log(f"Step7 桥接测试: 子进程返回失败 - {msg[:120]}")
    else:
        log("Step7 桥接测试: 超时(15秒) - 子进程未响应")
except Exception as e:
    log(f"Step7 桥接测试: FAIL - {e}")
    traceback.print_exc()

# Step 8: Launch window
log("Step8 显示窗口，进入事件循环...")
window.show()
log("所有诊断步骤完成，程序已启动")
sys.exit(app.exec())
