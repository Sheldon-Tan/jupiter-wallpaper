"""Attach the local WebGL Jupiter scene behind Windows desktop icons.

Run without arguments to start; run with 'stop' to close the wallpaper.
No third-party Python package is needed.
"""

from __future__ import annotations

import ctypes
from ctypes import wintypes
import http.server
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import threading
import time
from urllib.parse import urlsplit


ROOT = Path(__file__).resolve().parent
STATE = ROOT / ".wallpaper-state.json"
STOP = ROOT / ".stop"
LOG = ROOT / "wallpaper.log"
ROTATION_COUNT = ROOT / ".rotation-count.json"
ROTATION_COUNT_TMP = ROOT / ".rotation-count.json.tmp"
USER32 = ctypes.windll.user32
USER32.FindWindowW.argtypes = [wintypes.LPCWSTR, wintypes.LPCWSTR]
USER32.FindWindowW.restype = wintypes.HWND
USER32.FindWindowExW.argtypes = [wintypes.HWND, wintypes.HWND,
                                wintypes.LPCWSTR, wintypes.LPCWSTR]
USER32.FindWindowExW.restype = wintypes.HWND
USER32.SetParent.argtypes = [wintypes.HWND, wintypes.HWND]
USER32.SetParent.restype = wintypes.HWND
USER32.SetWindowLongPtrW.argtypes = [wintypes.HWND, ctypes.c_int, ctypes.c_ssize_t]
USER32.SetWindowLongPtrW.restype = ctypes.c_ssize_t
USER32.GetWindowLongPtrW.argtypes = [wintypes.HWND, ctypes.c_int]
USER32.GetWindowLongPtrW.restype = ctypes.c_ssize_t
USER32.SetLayeredWindowAttributes.argtypes = [wintypes.HWND, wintypes.DWORD,
                                              ctypes.c_ubyte, wintypes.DWORD]
USER32.SetLayeredWindowAttributes.restype = wintypes.BOOL
USER32.SetWindowPos.argtypes = [wintypes.HWND, wintypes.HWND, ctypes.c_int,
                                ctypes.c_int, ctypes.c_int, ctypes.c_int, wintypes.UINT]
USER32.SetWindowPos.restype = wintypes.BOOL
USER32.SendMessageTimeoutW.argtypes = [wintypes.HWND, wintypes.UINT,
                                       ctypes.c_size_t, ctypes.c_ssize_t,
                                       wintypes.UINT, wintypes.UINT,
                                       ctypes.POINTER(ctypes.c_size_t)]
USER32.EnumWindows.argtypes = [ctypes.c_void_p, wintypes.LPARAM]
USER32.GetWindowTextW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
USER32.GetWindowTextLengthW.argtypes = [wintypes.HWND]
USER32.GetForegroundWindow.restype = wintypes.HWND
USER32.GetWindowRect.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.RECT)]
USER32.GetWindowRect.restype = wintypes.BOOL
USER32.GetClassNameW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]


def desktop_obscured(wallpaper_hwnd: int, width: int, height: int) -> bool:
    """Pause rendering when a foreground window covers nearly all the desktop."""
    if not wallpaper_hwnd or not width or not height:
        return False
    hwnd = USER32.GetForegroundWindow()
    if not hwnd or hwnd == wallpaper_hwnd or not USER32.IsWindowVisible(hwnd):
        return False
    class_name = ctypes.create_unicode_buffer(256)
    USER32.GetClassNameW(hwnd, class_name, len(class_name))
    if class_name.value in ("Progman", "WorkerW"):
        return False
    rect = wintypes.RECT()
    if not USER32.GetWindowRect(hwnd, ctypes.byref(rect)):
        return False
    covered_width = max(0, min(rect.right, width) - max(rect.left, 0))
    covered_height = max(0, min(rect.bottom, height) - max(rect.top, 0))
    return covered_width * covered_height >= width * height * 0.95


def log(message: str) -> None:
    with LOG.open("a", encoding="utf-8") as file:
        file.write(time.strftime("%Y-%m-%d %H:%M:%S ") + message + "\n")


def load_rotation_count() -> int:
    if not ROTATION_COUNT.exists():
        return 0
    try:
        turns = json.loads(ROTATION_COUNT.read_text(encoding="utf-8"))["completed_turns"]
        if type(turns) is int and turns >= 0:
            return turns
    except (OSError, ValueError, KeyError, TypeError):
        pass
    raise ValueError(f"计数文件无效：{ROTATION_COUNT}")


def save_rotation_count(turns: int) -> None:
    ROTATION_COUNT_TMP.write_text(
        json.dumps({"completed_turns": turns}) + "\n", encoding="utf-8")
    ROTATION_COUNT_TMP.replace(ROTATION_COUNT)


class WallpaperFiles(http.server.SimpleHTTPRequestHandler):
    """Serve wallpaper assets and the local playback state."""

    ALLOWED = {"/", "/index.html", "/wallpaper.js",
               "/assets/jupiter_cassini_2000.png",
               "/assets/jupiter_hubble_2015.png",
               "/assets/jupiter_cassini_juno_8k.png"}
    wallpaper_hwnd = 0
    screen_width = 0
    screen_height = 0
    rotation_total = 0
    rotation_sessions: dict[str, int] = {}
    rotation_lock = threading.Lock()

    def send_json(self, data: dict) -> None:
        body = json.dumps(data).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        path = urlsplit(self.path).path
        if path == "/rotation-count":
            with self.rotation_lock:
                turns = type(self).rotation_total
            self.send_json({"completed_turns": turns})
            return
        if path == "/playback":
            paused = desktop_obscured(self.wallpaper_hwnd, self.screen_width,
                                      self.screen_height)
            self.send_json({"paused": paused})
            return
        if path not in self.ALLOWED:
            self.send_error(404)
            return
        super().do_GET()

    def do_POST(self):
        if urlsplit(self.path).path != "/rotation-count":
            self.send_error(404)
            return
        if self.headers.get("Content-Type", "").split(";", 1)[0] != "application/json":
            self.send_error(415)
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if not 0 < length <= 256:
                raise ValueError("invalid length")
            data = json.loads(self.rfile.read(length))
            session = data["session"]
            completed = data["completed"]
            if (not isinstance(session, str) or not 1 <= len(session) <= 64 or
                    not all(character.isalnum() or character == "-" for character in session) or
                    type(completed) is not int or not 0 <= completed <= 10_000_000):
                raise ValueError("invalid count")
        except (ValueError, KeyError, TypeError, UnicodeDecodeError):
            self.send_error(400)
            return
        with self.rotation_lock:
            cls = type(self)
            previous = cls.rotation_sessions.get(session, 0)
            if completed > previous:
                total = cls.rotation_total + completed - previous
                try:
                    save_rotation_count(total)
                except OSError as error:
                    log(f"Rotation count save failed: {error!r}")
                    self.send_error(500)
                    return
                cls.rotation_total = total
                cls.rotation_sessions[session] = completed
            self.send_json({"completed_turns": cls.rotation_total})

    def log_message(self, format, *args):
        pass


def chrome_path() -> Path:
    candidates = [
        Path(os.environ.get("PROGRAMFILES", r"C:\Program Files")) / "Google/Chrome/Application/chrome.exe",
        Path(os.environ.get("PROGRAMFILES(X86)", r"C:\Program Files (x86)")) / "Microsoft/Edge/Application/msedge.exe",
    ]
    for path in candidates:
        if path.is_file():
            return path
    raise FileNotFoundError("未找到 Chrome 或 Edge")


def screen_size() -> tuple[int, int]:
    # Screen 0 is the desktop monitor for this single-screen setup.
    USER32.SetProcessDPIAware()
    return USER32.GetSystemMetrics(0), USER32.GetSystemMetrics(1)


def find_wallpaper_window() -> int:
    found = []
    callback_type = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)

    def callback(hwnd, unused):
        if USER32.IsWindowVisible(hwnd):
            length = USER32.GetWindowTextLengthW(hwnd)
            if length:
                title = ctypes.create_unicode_buffer(length + 1)
                USER32.GetWindowTextW(hwnd, title, length + 1)
                if title.value == "Jupiter Wallpaper":
                    found.append(hwnd)
                    return False
        return True

    USER32.EnumWindows(callback_type(callback), 0)
    return found[0] if found else 0


def desktop_layer() -> int:
    progman = USER32.FindWindowW("Progman", None)
    if not progman:
        raise RuntimeError("Windows 桌面窗口不存在")
    # Recent Windows 11 keeps a raised, layered icon view inside Progman.
    # Its child WorkerW sits directly underneath the icons.
    raised = bool(USER32.GetWindowLongPtrW(progman, -20) & 0x00200000)
    if raised:
        worker = USER32.FindWindowExW(progman, 0, "WorkerW", None)
        if worker:
            return worker
    result = ctypes.c_size_t()
    USER32.SendMessageTimeoutW(progman, 0x052C, 0xD, 0x1, 0, 1000, ctypes.byref(result))
    if raised:
        worker = USER32.FindWindowExW(progman, 0, "WorkerW", None)
        if worker:
            return worker
    layers = []
    callback_type = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)

    def callback(hwnd, unused):
        icon_layer = USER32.FindWindowExW(hwnd, 0, "SHELLDLL_DefView", None)
        if icon_layer:
            worker = USER32.FindWindowExW(0, hwnd, "WorkerW", None)
            if worker:
                layers.append(worker)
        return True

    USER32.EnumWindows(callback_type(callback), 0)
    return layers[0] if layers else progman


def attach(hwnd: int, width: int, height: int) -> None:
    target = desktop_layer()
    GWL_STYLE = -16
    WS_CHILD = 0x40000000
    WS_VISIBLE = 0x10000000
    WS_POPUP = 0x80000000
    WS_OVERLAPPEDWINDOW = 0x00CF0000
    WS_EX_LAYERED = 0x00080000
    WS_EX_TOOLWINDOW = 0x00000080
    SWP_FRAMECHANGED = 0x0020
    SWP_SHOWWINDOW = 0x0040
    # This program runs in 64-bit Python, so HWND and window styles fit in LONG_PTR.
    old = USER32.GetWindowLongPtrW(hwnd, GWL_STYLE)
    USER32.SetWindowLongPtrW(hwnd, GWL_STYLE,
                             (old | WS_CHILD | WS_VISIBLE) & ~(WS_POPUP | WS_OVERLAPPEDWINDOW))
    ex = USER32.GetWindowLongPtrW(hwnd, -20)
    USER32.SetWindowLongPtrW(hwnd, -20, ex | WS_EX_LAYERED | WS_EX_TOOLWINDOW)
    USER32.SetLayeredWindowAttributes(hwnd, 0, 255, 0x2)
    if not USER32.SetParent(hwnd, target):
        raise OSError("无法将浏览器窗口放到桌面图标后面")
    # Chromium draws its own 31 px caption even after the Win32 frame is removed.
    # Move that caption just outside the parent and preserve a full-screen client area.
    USER32.SetWindowPos(hwnd, 0, 0, -31, width, height + 31,
                         SWP_FRAMECHANGED | SWP_SHOWWINDOW)
    log(f"Attached hwnd={hwnd} parent={target}, size={width}x{height}")


def run(map_name: str = "cassini") -> None:
    if STATE.exists():
        try:
            old_hwnd = json.loads(STATE.read_text(encoding="utf-8"))["hwnd"]
        except (OSError, ValueError, KeyError):
            old_hwnd = 0
        if old_hwnd and USER32.IsWindow(old_hwnd):
            raise RuntimeError("壁纸已经运行。先执行 stop_wallpaper.cmd。")
        STATE.unlink(missing_ok=True)
    STOP.unlink(missing_ok=True)
    os.chdir(ROOT)
    WallpaperFiles.rotation_total = load_rotation_count()
    WallpaperFiles.rotation_sessions = {}
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), WallpaperFiles)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    port = server.server_address[1]
    width, height = screen_size()
    WallpaperFiles.screen_width = width
    WallpaperFiles.screen_height = height
    browser = chrome_path()
    args = [str(browser), f"--user-data-dir={ROOT / '.browser-profile'}",
            "--new-window", "--no-first-run", "--no-default-browser-check",
            "--disable-extensions", "--disable-session-crashed-bubble",
            "--disable-features=CalculateNativeWinOcclusion",
            "--disable-backgrounding-occluded-windows",
            "--disable-renderer-backgrounding", "--disable-background-timer-throttling",
            f"--app=http://127.0.0.1:{port}/?map={map_name}"]
    startup = subprocess.STARTUPINFO()
    startup.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    startup.wShowWindow = 1  # show browser even when the Python host has no window
    process = subprocess.Popen(args, cwd=ROOT, stdout=subprocess.DEVNULL,
                               stderr=subprocess.DEVNULL, startupinfo=startup)
    log(f"Launching {browser.name} pid={process.pid}, port={port}")
    hwnd = 0
    try:
        for _ in range(100):
            hwnd = find_wallpaper_window()
            if hwnd:
                break
            if _ in (10, 30, 60):
                log(f"Waiting for browser window, launcher status={process.poll()}")
            time.sleep(0.2)
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
        while not STOP.exists() and USER32.IsWindow(hwnd):
            time.sleep(0.5)
    finally:
        USER32.PostMessageW(hwnd, 0x0010, 0, 0) if hwnd and USER32.IsWindow(hwnd) else None
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.terminate()
        server.shutdown()
        STATE.unlink(missing_ok=True)
        STOP.unlink(missing_ok=True)
        log("Stopped")


def main() -> None:
    if len(sys.argv) > 1 and sys.argv[1].lower() == "stop":
        STOP.touch()
        for _ in range(30):
            if not STATE.exists():
                break
            time.sleep(0.2)
        print("Wallpaper stopped." if not STATE.exists() else "Stop requested; please wait.")
        return
    map_name = sys.argv[1].lower() if len(sys.argv) > 1 else "cassini"
    if map_name not in ("cassini", "hubble", "merged"):
        raise ValueError("Use cassini, hubble, merged, or stop")
    try:
        run(map_name)
    except Exception as error:
        log(f"ERROR: {error!r}")
        raise


if __name__ == "__main__":
    main()
