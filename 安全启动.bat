@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo ========================================
echo Brooks Signals - 安全启动模式
echo ========================================
echo.
echo 清除缓存...
for /d /r . %%d in (__pycache__) do @if exist "%%d" rd /s /q "%%d" 2>nul
echo.
python 安全启动.py
pause
