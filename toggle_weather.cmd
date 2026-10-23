@echo off
cd /d "%~dp0"
python "%~dp0wallpaper_host.py" toggle
timeout /t 2 >nul
