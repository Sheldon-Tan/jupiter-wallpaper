"""Win32 封装：找桌面层、把浏览器窗口塞到图标后面、全局热键、找 Chrome。

这一层只跟窗口和进程打交道，不关心 HTTP、计数或命令行参数。
所有 ctypes 原型集中在这里声明一次，避免每个调用点各写一遍 argtypes。
"""

from __future__ import annotations

import ctypes
from ctypes import wintypes
import os
from pathlib import Path

from host_common import log


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

# Ctrl+Alt+J：任何前台程序获得焦点时都能触发。
HOTKEY_ID = 0xB001
WM_HOTKEY = 0x0312
MOD_ALT = 0x0001
MOD_CONTROL = 0x0002
MOD_NOREPEAT = 0x4000
VK_J = 0x4A


def desktop_obscured(wallpaper_hwnd: int, width: int, height: int) -> bool:
    """前台窗口遮住至少 95% 桌面时返回 True（此时暂停绘制省电）。"""
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


def screen_size() -> tuple[int, int]:
    """主屏像素尺寸；先声明 DPI 感知，避免缩放后取到逻辑分辨率。"""
    USER32.SetProcessDPIAware()
    return USER32.GetSystemMetrics(0), USER32.GetSystemMetrics(1)


def find_wallpaper_window() -> int:
    """按窗口标题找浏览器应用窗口，找不到返回 0。"""
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
    """返回桌面图标所在层：优先 Progman 下新式的 WorkerW，其次旧式枚举。"""
    progman = USER32.FindWindowW("Progman", None)
    if not progman:
        raise RuntimeError("Windows 桌面窗口不存在")
    # 新版 Windows 11 在 Progman 里保留了一个置顶的图标视图，其子 WorkerW 就在图标下方。
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
    """把浏览器窗口变成桌面层的子窗口，并校正到刚好铺满屏幕。"""
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
    # 这是 64 位 Python，HWND 与窗口样式都放得进 LONG_PTR。
    old = USER32.GetWindowLongPtrW(hwnd, GWL_STYLE)
    USER32.SetWindowLongPtrW(hwnd, GWL_STYLE,
                             (old | WS_CHILD | WS_VISIBLE) & ~(WS_POPUP | WS_OVERLAPPEDWINDOW))
    ex = USER32.GetWindowLongPtrW(hwnd, -20)
    USER32.SetWindowLongPtrW(hwnd, -20, ex | WS_EX_LAYERED | WS_EX_TOOLWINDOW)
    USER32.SetLayeredWindowAttributes(hwnd, 0, 255, 0x2)
    if not USER32.SetParent(hwnd, target):
        raise OSError("无法将浏览器窗口放到桌面图标后面")
    # Chromium 即使去掉 Win32 边框也会自绘 31 px 标题栏；同时窗口可能带有不可见
    # 的侧边/底边，所以按“实际客户区”而不是外框尺寸来校正，才能铺满整个屏幕。
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


def chrome_path() -> Path:
    """优先 Chrome，其次 Edge；两者都没有时报错。"""
    candidates = [
        Path(os.environ.get("PROGRAMFILES", r"C:\Program Files")) / "Google/Chrome/Application/chrome.exe",
        Path(os.environ.get("PROGRAMFILES(X86)", r"C:\Program Files (x86)")) / "Microsoft/Edge/Application/msedge.exe",
    ]
    for path in candidates:
        if path.is_file():
            return path
    raise FileNotFoundError("未找到 Chrome 或 Edge")


def register_hotkey() -> bool:
    """注册 Ctrl+Alt+J（线程级）。成功返回 True，被占用时返回 False。"""
    return bool(USER32.RegisterHotKey(None, HOTKEY_ID,
                                      MOD_CONTROL | MOD_ALT | MOD_NOREPEAT, VK_J))


def unregister_hotkey() -> None:
    USER32.UnregisterHotKey(None, HOTKEY_ID)


def poll_hotkey() -> bool:
    """清空本线程消息队列；遇到 WM_HOTKEY 返回 True。"""
    message = wintypes.MSG()
    pressed = False
    while USER32.PeekMessageW(ctypes.byref(message), None, 0, 0, 1):
        if message.message == WM_HOTKEY and int(message.wParam) == HOTKEY_ID:
            pressed = True
    return pressed
