@echo off
rem MyBotPy - DEBUG launcher: keeps the console open and shows errors.
rem Double-click this to see what goes wrong, then send the text.
cd /d "%~dp0"
echo === Python check ===
py -3.13 --version
echo.
echo === Starting bot (close its window to return here) ===
py -3.13 run_from_source.py
echo.
echo === EXIT CODE: %errorlevel% ===
pause
