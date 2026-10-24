"""启动/停止木星壁纸宿主，并处理命令行。

命令行用法：
    python wallpaper_host.py [cassini|hubble|merged] [live|static]   启动
    python wallpaper_host.py toggle                                  切换实时模拟
    python wallpaper_host.py stop                                    停止

这一层只做编排：窗口与进程交给 host_win32.py，HTTP 与状态文件交给
host_server.py / host_common.py。没有第三方依赖。
"""

from __future__ import annotations

import ctypes
import json
import os
import subprocess
import sys
import time
import urllib.request

from host_common import (BROWSER_PROFILE, ROOT, ROTATION_COUNT, STATE, STOP, log,
                         load_live, load_rotation_count, save_live,
                         save_rotation_count)
from host_server import WallpaperFiles, set_live, start_server
from host_win32 import (USER32, attach, chrome_path, find_wallpaper_window,
                        poll_hotkey, register_hotkey, screen_size,
                        unregister_hotkey)


def launch_browser(port: int, map_name: str) -> subprocess.Popen:
    """Start the app-mode browser window that will become the wallpaper."""
    browser = chrome_path()
    args = [str(browser), f"--user-data-dir={BROWSER_PROFILE}",
            "--new-window", "--no-first-run", "--no-default-browser-check",
            "--disable-extensions", "--disable-session-crashed-bubble",
            "--disable-features=CalculateNativeWinOcclusion",
            "--disable-backgrounding-occluded-windows",
            "--disable-renderer-backgrounding", "--disable-background-timer-throttling",
            f"--app=http://127.0.0.1:{port}/?map={map_name}"]
    startup = subprocess.STARTUPINFO()
    startup.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    startup.wShowWindow = 1  # 即使宿主没有窗口也把浏览器显示出来
    process = subprocess.Popen(args, cwd=ROOT, stdout=subprocess.DEVNULL,
                               stderr=subprocess.DEVNULL, startupinfo=startup)
    log(f"Launching {browser.name} pid={process.pid}, port={port}")
    return process


def wait_for_window(process: subprocess.Popen, attempts: int = 150) -> int:
    hwnd = 0
    for attempt in range(attempts):
        hwnd = find_wallpaper_window()
        if hwnd:
            return hwnd
        if attempt in (10, 30, 60):
            log(f"Waiting for browser window, launcher status={process.poll()}")
        time.sleep(0.2)
    return 0


class AlreadyRunning(RuntimeError):
    """The wallpaper is already attached to the desktop; nothing to do."""


def run(map_name: str = "cassini", live: bool | None = None) -> None:
    if STATE.exists():
        try:
            old_hwnd = json.loads(STATE.read_text(encoding="utf-8"))["hwnd"]
        except (OSError, ValueError, KeyError):
            old_hwnd = 0
        if old_hwnd and USER32.IsWindow(old_hwnd):
            raise AlreadyRunning("壁纸已经运行。先执行 stop_wallpaper.cmd。")
        STATE.unlink(missing_ok=True)
    STOP.unlink(missing_ok=True)
    os.chdir(ROOT)

    # 计数与实时开关：先把磁盘上的值装进 HTTP 服务，再启动页面。
    WallpaperFiles.rotation_total = load_rotation_count()
    if not ROTATION_COUNT.exists():
        save_rotation_count(WallpaperFiles.rotation_total)
    WallpaperFiles.rotation_sessions = {}
    WallpaperFiles.live_mode = load_live(True) if live is None else bool(live)
    if live is not None:
        try:
            save_live(live)
        except OSError as error:
            log(f"Live switch save failed: {error!r}")

    server, port = start_server()
    width, height = screen_size()
    WallpaperFiles.screen_width = width
    WallpaperFiles.screen_height = height
    process = launch_browser(port, map_name)

    hwnd = 0
    try:
        hwnd = wait_for_window(process)
        if not hwnd:
            raise RuntimeError("浏览器壁纸窗口未启动")
        attach(hwnd, width, height)
        WallpaperFiles.wallpaper_hwnd = hwnd
        STATE.write_text(json.dumps({"pid": os.getpid(), "browser_pid": process.pid,
                                     "hwnd": hwnd, "port": port,
                                     "screen": [width, height], "map": map_name}, indent=2),
                         encoding="utf-8")

        console = ctypes.windll.kernel32.GetConsoleWindow()
        if console:
            USER32.ShowWindow(console, 0)

        # WM_HOTKEY 投递到注册它的线程队列，下面这个循环负责清队列。
        if register_hotkey():
            log("Ctrl+Alt+J registered for the live atmosphere switch")
        else:
            log("Ctrl+Alt+J unavailable (already in use); use toggle_weather.cmd")

        while not STOP.exists() and USER32.IsWindow(hwnd):
            if poll_hotkey():
                set_live(not WallpaperFiles.live_mode)
            time.sleep(0.25)
    finally:
        unregister_hotkey()
        if hwnd and USER32.IsWindow(hwnd):
            USER32.PostMessageW(hwnd, 0x0010, 0, 0)  # WM_CLOSE
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.terminate()
        server.shutdown()
        STATE.unlink(missing_ok=True)
        STOP.unlink(missing_ok=True)
        log("Stopped")


def request_live(port: int, live: bool) -> bool:
    data = json.dumps({"live": live}).encode("utf-8")
    request = urllib.request.Request(
        f"http://127.0.0.1:{port}/live", data=data,
        headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(request, timeout=3) as response:
        return bool(json.loads(response.read())["live"])


def toggle_live() -> None:
    """Flip the live-atmosphere switch while the wallpaper keeps running."""
    port = 0
    if STATE.exists():
        try:
            port = int(json.loads(STATE.read_text(encoding="utf-8"))["port"])
        except (OSError, ValueError, KeyError, TypeError):
            port = 0
    if port:
        try:
            with urllib.request.urlopen(f"http://127.0.0.1:{port}/live",
                                        timeout=3) as response:
                current = bool(json.loads(response.read())["live"])
            live = request_live(port, not current)
            print(f"Live atmosphere {'on' if live else 'off'}.")
            return
        except (OSError, ValueError, KeyError, TypeError) as error:
            log(f"Toggle via running wallpaper failed: {error!r}")
    live = not load_live(True)
    save_live(live)
    print(f"Live atmosphere {'on' if live else 'off'} "
          "(wallpaper not running; setting saved).")


def stop_wallpaper() -> None:
    STOP.touch()
    for _ in range(30):
        if not STATE.exists():
            break
        time.sleep(0.2)
    print("Wallpaper stopped." if not STATE.exists() else "Stop requested; please wait.")


def parse_arguments(arguments: list[str]) -> tuple[str, bool | None]:
    map_name = "cassini"
    live: bool | None = None
    for argument in arguments:
        if argument in ("cassini", "hubble", "merged"):
            map_name = argument
        elif argument in ("live", "on"):
            live = True
        elif argument in ("static", "off"):
            live = False
        else:
            raise ValueError("用法：wallpaper_host.py [cassini|hubble|merged] "
                             "[live|static] | toggle | stop")
    return map_name, live


def main() -> None:
    arguments = [argument.lower() for argument in sys.argv[1:]]
    if "stop" in arguments:
        stop_wallpaper()
        return
    if "toggle" in arguments:
        toggle_live()
        return
    map_name, live = parse_arguments(arguments)
    try:
        run(map_name, live)
    except AlreadyRunning:
        # 开机自启与手动启动撞车时静默退出，不要弹出一屏 traceback。
        log("Already running; autostart did nothing")
    except Exception as error:
        log(f"ERROR: {error!r}")
        raise


if __name__ == "__main__":
    main()
