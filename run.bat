@echo off
rem MyBotPy - start the bot (GUI window only, no console).
rem Run setup.bat once first. If MEmu auto-setup fails,
rem right-click this file -> "Run as administrator".
cd /d "%~dp0"
start "" "%LOCALAPPDATA%\Programs\Python\Python313\pythonw.exe" "%~dp0run_from_source.py" %*
