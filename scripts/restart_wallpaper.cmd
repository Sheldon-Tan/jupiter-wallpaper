@echo off
cd /d "%~dp0.."
rem Stop the running wallpaper, then start it again so the browser reloads
rem the current js/ modules, css and textures.
python "python\wallpaper_host.py" stop
python "python\wallpaper_host.py" %*
