import sys
import traceback
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent))

LOG_FILE = Path(__file__).parent / "error.log"

def log_error(msg: str):
    entry = f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {msg}"
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(entry + "\n")
    except:
        pass
    print(entry)

def global_exception_hook(exc_type, exc_value, exc_tb):
    tb_str = "".join(traceback.format_exception(exc_type, exc_value, exc_tb))
    log_error(f"未捕获异常:\n{tb_str}")
    try:
        from PyQt6.QtWidgets import QMessageBox
        QMessageBox.critical(None, "运行错误", f"{exc_value}\n\n详情见 error.log")
    except:
        pass
    sys.__excepthook__(exc_type, exc_value, exc_tb)

sys.excepthook = global_exception_hook

def main():
    log_error("程序启动")

    try:
        from config.settings import load_config
        config = load_config()
        log_error(f"配置: {config.symbol} {config.timeframes['primary']}")

        from gui.app import create_app
        app = create_app()
        log_error("QApplication OK")

        from gui.main_window import MainWindow
        window = MainWindow(config)
        log_error("MainWindow OK — 等待用户点击「连接 MT5」")

        window.show()
        sys.exit(app.exec())

    except Exception as e:
        log_error(f"启动失败: {e}\n{traceback.format_exc()}")
        traceback.print_exc()
        try:
            from PyQt6.QtWidgets import QMessageBox
            QMessageBox.critical(None, "启动失败",
                f"{e}\n\n请查看 error.log 了解详情")
        except:
            pass
        input("\n按回车退出...")

if __name__ == "__main__":
    main()
