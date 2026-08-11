@echo off
rem ============================================================
rem  MyBotPy - install dependencies. Run this ONCE after
rem  installing Python 3.13. Installs packages into the same
rem  Python 3.13 that the bot (run.bat) uses.
rem ============================================================
title MyBotPy setup

py -3.13 --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python 3.13 not found.
    echo Install it from https://www.python.org/downloads/release/python-3132/
    echo During install tick "Add python.exe to PATH".
    echo.
    pause
    exit /b 1
)

echo Installing MyBotPy dependencies into Python 3.13...
echo.
py -3.13 -m pip install --upgrade pip
py -3.13 -m pip install -r "%~dp0requirements.txt"
if errorlevel 1 (
    echo.
    echo [ERROR] Install failed. Check your internet connection and try again.
    pause
    exit /b 1
)

echo.
echo ============================================================
echo  Done. Now start the bot with run.bat
echo ============================================================
pause
