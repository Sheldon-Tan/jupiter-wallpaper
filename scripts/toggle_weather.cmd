@echo off
cd /d "%~dp0.."
python "python\wallpaper_host.py" toggle
rem Keep the window up briefly so the result can be read.
ping -n 3 127.0.0.1 >nul
