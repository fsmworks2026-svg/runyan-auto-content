@echo off
chcp 65001 >nul 2>&1
cd /d "%~dp0"

python --version >nul 2>&1
if errorlevel 1 (
    echo.
    echo [ERROR] Python not found.
    echo         Install from https://www.python.org
    echo.
    pause
    exit /b 1
)

python setup_bot.py
pause
