"""最简单的PyQt6窗口测试 - 不加载任何MT5或分析模块"""
import sys
from PyQt6.QtWidgets import QApplication, QMainWindow, QLabel, QVBoxLayout, QWidget
from PyQt6.QtCore import Qt

print("[1] PyQt6 import OK")

app = QApplication(sys.argv)
print("[2] QApplication OK")

w = QMainWindow()
w.setWindowTitle("测试窗口")
w.resize(400, 200)

c = QWidget()
l = QVBoxLayout(c)
label = QLabel("如果看到这个窗口，PyQt6工作正常\n可以关闭此窗口")
label.setAlignment(Qt.AlignmentFlag.AlignCenter)
l.addWidget(label)
w.setCentralWidget(c)

print("[3] Window created, showing...")
w.show()
print("[4] Entering event loop...")
sys.exit(app.exec())
