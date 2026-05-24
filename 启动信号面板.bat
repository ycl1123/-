@echo off
chcp 65001 > nul
cd /d "%~dp0"
title XAUUSD Brooks 信号面板

echo ================================
echo   XAUUSD Al Brooks 信号面板
echo   正在连接 MT5...
echo ================================

python main.py

pause
