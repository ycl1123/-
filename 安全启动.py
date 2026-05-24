"""最小化安全启动 — 逐步加载，每一步都有日志"""
import sys
import traceback
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent))

LOG_FILE = Path(__file__).parent / "安全启动日志.txt"

def log(msg: str):
    entry = f"[{datetime.now().strftime('%H:%M:%S')}] {msg}"
    print(entry)
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(entry + "\n")
    except:
        pass

log("=== 安全启动开始 ===")

# Step 1: Only PyQt6 — no project imports
try:
    log("Step1: 导入 PyQt6...")
    from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout,
                                  QHBoxLayout, QPushButton, QLabel, QTextEdit, QStatusBar)
    from PyQt6.QtCore import QTimer, Qt
    from PyQt6.QtGui import QFont
    log("Step1: PyQt6 OK")
except Exception as e:
    log(f"Step1 FAIL: {e}")
    input("按回车退出...")
    sys.exit(1)

# Step 2: Create QApplication
try:
    log("Step2: 创建 QApplication...")
    app = QApplication(sys.argv)
    app.setStyle('Fusion')
    log("Step2: QApplication OK")
except Exception as e:
    log(f"Step2 FAIL: {e}")
    input("按回车退出...")
    sys.exit(1)

# Step 3: Create minimal window BEFORE any project import
log("Step3: 创建窗口...")
window = QMainWindow()
window.setWindowTitle("Brooks Signals - 安全模式")
window.resize(600, 500)

central = QWidget()
window.setCentralWidget(central)
layout = QVBoxLayout(central)
layout.setContentsMargins(12, 12, 12, 12)

title = QLabel("XAUUSD 信号面板 (安全启动模式)")
title.setFont(QFont("", 14, QFont.Weight.Bold))
layout.addWidget(title)

status_label = QLabel("状态: 等待操作...")
status_label.setStyleSheet("color: #FFC107; font-size: 12px;")
layout.addWidget(status_label)

log_output = QTextEdit()
log_output.setReadOnly(True)
log_output.setStyleSheet("background: #1a1a2e; color: #ccc; font-family: Consolas; font-size: 11px;")
layout.addWidget(log_output, 1)

btn_layout = QHBoxLayout()

def safe_log(msg: str):
    log(msg)
    log_output.append(msg)

connect_btn = QPushButton("1. 测试连接 MT5 (子进程)")
connect_btn.setStyleSheet(
    "QPushButton { background: #26A69A; color: #fff; padding: 8px 16px; border-radius: 4px; font-weight: bold; }"
    "QPushButton:hover { background: #2EE6D0; }"
    "QPushButton:disabled { background: #555; color: #999; }"
)
btn_layout.addWidget(connect_btn)

full_btn = QPushButton("2. 启动完整程序")
full_btn.setStyleSheet(
    "QPushButton { background: #42A5F5; color: #fff; padding: 8px 16px; border-radius: 4px; font-weight: bold; }"
    "QPushButton:hover { background: #64B5F6; }"
    "QPushButton:disabled { background: #555; color: #999; }"
)
btn_layout.addWidget(full_btn)

layout.addLayout(btn_layout)

window.status_bar = QStatusBar()
window.setStatusBar(window.status_bar)
window.status_bar.showMessage("安全模式 — 模块按需加载")

# Step 4: Wire up the test button
def on_test_connect():
    connect_btn.setEnabled(False)
    status_label.setText("状态: 正在通过子进程连接 MT5...")
    status_label.setStyleSheet("color: #FFC107; font-size: 12px;")
    safe_log("--- 开始子进程MT5连接测试 ---")

    try:
        safe_log("导入 mt5.bridge...")
        from mt5.bridge import MT5Bridge
        safe_log("bridge 导入成功")

        safe_log("导入 config...")
        from config.settings import load_config
        cfg = load_config()
        safe_log(f"配置加载: {cfg.symbol} / {cfg.timeframes}")

        tf_list = [cfg.timeframes["primary"]] + cfg.timeframes.get("secondary", [])
        safe_log(f"时间周期: {tf_list}")

        bridge = MT5Bridge(cfg.symbol, tf_list, cfg.mt5.history_bars)

        def on_result(success, msg, bars):
            if success:
                bar_info = ", ".join(f"{t}={len(d)}根" for t, d in bars.items())
                status_label.setText(f"MT5: {msg}")
                status_label.setStyleSheet("color: #4CAF50; font-size: 12px;")
                safe_log(f"连接成功! {msg}")
                safe_log(f"K线数据: {bar_info}")
                window.status_bar.showMessage(f"连接成功 — {bar_info}")
            else:
                status_label.setText(f"MT5: 失败")
                status_label.setStyleSheet("color: #EF5350; font-size: 12px;")
                safe_log(f"连接失败: {msg}")
                window.status_bar.showMessage(f"连接失败: {msg[:100]}")
            connect_btn.setEnabled(True)

        bridge.result_ready.connect(on_result)
        bridge.start()
        safe_log("子进程已启动，等待结果...")

    except Exception as e:
        safe_log(f"异常: {e}\n{traceback.format_exc()}")
        status_label.setText(f"状态: 错误 - {e}")
        status_label.setStyleSheet("color: #EF5350; font-size: 12px;")
        connect_btn.setEnabled(True)

connect_btn.clicked.connect(on_test_connect)

# Step 5: Wire up the full program button
def on_launch_full():
    full_btn.setEnabled(False)
    safe_log("--- 导入完整程序模块 ---")
    try:
        safe_log("导入 config...")
        from config.settings import load_config
        safe_log("导入 gui.app...")
        from gui.app import create_app
        safe_log("导入 gui.main_window (使用子进程桥接)...")
        from gui.main_window import MainWindow
        safe_log("所有模块导入成功!")
        safe_log("启动主窗口...")

        config = load_config()
        # Use a new app or reuse? We'll close this window and open the real one
        window.hide()
        main_win = MainWindow(config)
        main_win.show()

        # Close this launcher when main window closes
        window.main_win = main_win

    except Exception as e:
        safe_log(f"启动失败: {e}\n{traceback.format_exc()}")
        full_btn.setEnabled(True)

full_btn.clicked.connect(on_launch_full)

log("Step5: 窗口配置完成，显示窗口")
window.show()

safe_log("安全启动模式就绪 — 请点击按钮测试")
safe_log("如果窗口能显示到这里，说明 PyQt6 和基本环境正常")
safe_log(f"Python: {sys.version}")
safe_log(f"路径: {sys.path[:3]}")

sys.exit(app.exec())
