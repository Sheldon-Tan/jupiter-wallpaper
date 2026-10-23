@echo off
cd /d "%~dp0"
rem Stop the running wallpaper, then start it again so the browser reloads
rem the current wallpaper.js / atmosphere.js / textures.
python "%~dp0wallpaper_host.py" stop
python "%~dp0wallpaper_host.py" %*
