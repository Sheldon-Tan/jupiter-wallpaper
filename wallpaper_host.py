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
import urllib.request


ROOT = Path(__file__).resolve().parent
STATE = ROOT / ".wallpaper-state.json"
STOP = ROOT / ".stop"
LOG = ROOT / "wallpaper.log"
ROTATION_COUNT = ROOT / "rotation-count.json"
ROTATION_COUNT_TMP = ROOT / "rotation-count.json.tmp"
LEGACY_ROTATION_COUNT = ROOT / ".rotation-count.json"
LIVE_STATE = ROOT / ".live-weather.json"
# Global switch for the live atmosphere.  Ctrl+Alt+J works from any window.
HOTKEY_ID = 0xB001
WM_HOTKEY = 0x0312
MOD_ALT = 0x0001
MOD_CONTROL = 0x0002
MOD_NOREPEAT = 0x4000
VK_J = 0x4A
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
USER32.GetClientRect.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.RECT)]
USER32.GetClientRect.restype = wintypes.BOOL
USER32.ClientToScreen.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.POINT)]
USER32.ClientToScreen.restype = wintypes.BOOL
USER32.GetClassNameW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
USER32.RegisterHotKey.argtypes = [wintypes.HWND, ctypes.c_int, wintypes.UINT, wintypes.UINT]
USER32.RegisterHotKey.restype = wintypes.BOOL
USER32.UnregisterHotKey.argtypes = [wintypes.HWND, ctypes.c_int]
USER32.UnregisterHotKey.restype = wintypes.BOOL
USER32.PeekMessageW.argtypes = [ctypes.POINTER(wintypes.MSG), wintypes.HWND,
                                wintypes.UINT, wintypes.UINT, wintypes.UINT]
USER32.PeekMessageW.restype = wintypes.BOOL


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
    path = ROTATION_COUNT if ROTATION_COUNT.exists() else LEGACY_ROTATION_COUNT
    if not path.exists():
        return 0
    try:
        turns = json.loads(path.read_text(encoding="utf-8"))["completed_turns"]
        if type(turns) is int and turns >= 0:
            return turns
    except (OSError, ValueError, KeyError, TypeError):
        pass
    raise ValueError(f"计数文件无效：{path}")


def save_rotation_count(turns: int) -> None:
    ROTATION_COUNT_TMP.write_text(
        json.dumps({"completed_turns": turns}) + "\n", encoding="utf-8")
    ROTATION_COUNT_TMP.replace(ROTATION_COUNT)


def load_live(default: bool = True) -> bool:
    """Read the persisted live-weather switch; atmosphere.js holds the default."""
    try:
        value = json.loads(LIVE_STATE.read_text(encoding="utf-8"))["live"]
        if type(value) is bool:
            return value
    except (OSError, ValueError, KeyError, TypeError):
        pass
    return default


def save_live(live: bool) -> None:
    temporary = LIVE_STATE.with_suffix(".json.tmp")
    temporary.write_text(json.dumps({"live": bool(live)}) + "\n", encoding="utf-8")
    temporary.replace(LIVE_STATE)


def set_live(live: bool, persist: bool = True) -> bool:
    WallpaperFiles.live_mode = bool(live)
    if persist:
        try:
            save_live(live)
        except OSError as error:
            log(f"Live switch save failed: {error!r}")
    log(f"Live atmosphere {'on' if live else 'off'}")
    return WallpaperFiles.live_mode


class WallpaperFiles(http.server.SimpleHTTPRequestHandler):
    """Serve wallpaper assets and the local playback state."""

    ALLOWED = {"/", "/index.html", "/wallpaper.js", "/atmosphere.js",
               "/assets/jupiter_cassini_2000.png",
               "/assets/jupiter_hubble_2015.png",
               "/assets/jupiter_cassini_juno_8k.png"}
    wallpaper_hwnd = 0
    screen_width = 0
    screen_height = 0
    rotation_total = 0
    rotation_sessions: dict[str, int] = {}
    rotation_lock = threading.Lock()
    live_mode = True

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
        if path == "/live":
            self.send_json({"live": type(self).live_mode})
            return
        if path not in self.ALLOWED:
            self.send_error(404)
            return
        super().do_GET()

    def do_POST(self):
        path = urlsplit(self.path).path
        if path == "/live":
            self.handle_live()
            return
        if path != "/rotation-count":
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

    def handle_live(self):
        """Accept {"live": bool} from the page, the toggle script or a hotkey."""
        if self.headers.get("Content-Type", "").split(";", 1)[0] != "application/json":
            self.send_error(415)
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if not 0 < length <= 64:
                raise ValueError("invalid length")
            live = json.loads(self.rfile.read(length))["live"]
            if type(live) is not bool:
                raise ValueError("invalid switch")
        except (ValueError, KeyError, TypeError, UnicodeDecodeError):
            self.send_error(400)
            return
        self.send_json({"live": set_live(live)})

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
    # The browser can retain an invisible side/bottom border, so size the actual
    # client area to the screen rather than assuming the outer window is enough.
    if not USER32.SetWindowPos(hwnd, 0, 0, -31, width, height + 31,
                              SWP_FRAMECHANGED | SWP_SHOWWINDOW):
        raise OSError("无法设置壁纸窗口尺寸")
    for _ in range(2):
        window = wintypes.RECT()
        client = wintypes.RECT()
        origin = wintypes.POINT()
        if not (USER32.GetWindowRect(hwnd, ctypes.byref(window)) and
                USER32.GetClientRect(hwnd, ctypes.byref(client)) and
                USER32.ClientToScreen(hwnd, ctypes.byref(origin))):
            raise OSError("无法读取壁纸窗口尺寸")
        left_gap = origin.x
        right_gap = width - (origin.x + client.right)
        bottom_gap = height - (origin.y + client.bottom)
        if left_gap == right_gap == bottom_gap == 0:
            break
        if not USER32.SetWindowPos(hwnd, 0, window.left - left_gap, window.top,
                                  window.right - window.left + left_gap + right_gap,
                                  window.bottom - window.top + bottom_gap,
                                  SWP_FRAMECHANGED | SWP_SHOWWINDOW):
            raise OSError("无法校正壁纸窗口边界")
    log(f"Attached hwnd={hwnd} parent={target}, client="
        f"({origin.x},{origin.y})-{origin.x + client.right},{origin.y + client.bottom}")


def run(map_name: str = "cassini", live: bool | None = None) -> None:
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
    if not ROTATION_COUNT.exists():
        save_rotation_count(WallpaperFiles.rotation_total)
    WallpaperFiles.rotation_sessions = {}
    # An explicit command-line choice wins over the saved switch.
    WallpaperFiles.live_mode = load_live(True) if live is None else bool(live)
    if live is not None:
        try:
            save_live(live)
        except OSError as error:
            log(f"Live switch save failed: {error!r}")
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
        # Ctrl+Alt+J toggles the live atmosphere from any application.  A
        # message-only registration is enough: WM_HOTKEY is posted to this
        # thread's queue and drained below.
        if not USER32.RegisterHotKey(None, HOTKEY_ID,
                                     MOD_CONTROL | MOD_ALT | MOD_NOREPEAT, VK_J):
            log("Ctrl+Alt+J unavailable (already in use); use toggle_weather.cmd")
        else:
            log("Ctrl+Alt+J registered for the live atmosphere switch")
        message = wintypes.MSG()
        while not STOP.exists() and USER32.IsWindow(hwnd):
            while USER32.PeekMessageW(ctypes.byref(message), None, 0, 0, 1):
                if (message.message == WM_HOTKEY and
                        int(message.wParam) == HOTKEY_ID):
                    set_live(not WallpaperFiles.live_mode)
            time.sleep(0.25)
    finally:
        USER32.UnregisterHotKey(None, HOTKEY_ID)
        USER32.PostMessageW(hwnd, 0x0010, 0, 0) if hwnd and USER32.IsWindow(hwnd) else None
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


def main() -> None:
    args = [argument.lower() for argument in sys.argv[1:]]
    if "stop" in args:
        STOP.touch()
        for _ in range(30):
            if not STATE.exists():
                break
            time.sleep(0.2)
        print("Wallpaper stopped." if not STATE.exists() else "Stop requested; please wait.")
        return
    if "toggle" in args:
        toggle_live()
        return
    map_name = "cassini"
    live = None
    for argument in args:
        if argument in ("cassini", "hubble", "merged"):
            map_name = argument
        elif argument == "live" or argument == "on":
            live = True
        elif argument in ("static", "off"):
            live = False
        else:
            raise ValueError("用法：wallpaper_host.py [cassini|hubble|merged] "
                             "[live|static] | toggle | stop")
    try:
        run(map_name, live)
    except Exception as error:
        log(f"ERROR: {error!r}")
        raise


if __name__ == "__main__":
    main()
