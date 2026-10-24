"""本机 HTTP 服务：页面文件、自转计数、播放状态与实时模拟开关。

页面每 250 ms 轮询 /live，每秒轮询 /playback，只在转动一圈时 POST 一次计数。
服务只监听 127.0.0.1，且只放行白名单里的文件。
"""

from __future__ import annotations

import http.server
import json
import threading
from urllib.parse import urlsplit

from host_common import log, save_live, save_rotation_count
from host_win32 import desktop_obscured


class WallpaperFiles(http.server.SimpleHTTPRequestHandler):
    """Serve the wallpaper page and the local state endpoints."""

    ALLOWED = {"/", "/index.html", "/css/wallpaper.css",
               "/js/settings.js", "/js/atmosphere.js", "/js/scene.js",
               "/js/rotation.js", "/js/live-mode.js", "/js/wallpaper.js",
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

    # ---- 工具 ----------------------------------------------------------
    def end_headers(self) -> None:
        # 页面、脚本、贴图一律不缓存。否则改了 js/ 之后，重启壁纸仍可能跑
        # Chrome 磁盘缓存里的旧着色器，看起来就像“算法自己跑坏了”。
        if not any(b"Cache-Control" in line for line in self._headers_buffer):
            self.send_header("Cache-Control", "no-store, must-revalidate")
        super().end_headers()

    def send_json(self, data: dict) -> None:
        body = json.dumps(data).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _read_json(self, limit: int) -> dict:
        if self.headers.get("Content-Type", "").split(";", 1)[0] != "application/json":
            raise ValueError("not json")
        length = int(self.headers.get("Content-Length", "0"))
        if not 0 < length <= limit:
            raise ValueError("bad length")
        return json.loads(self.rfile.read(length))

    # ---- GET -----------------------------------------------------------
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

    # ---- POST ----------------------------------------------------------
    def do_POST(self):
        path = urlsplit(self.path).path
        if path == "/live":
            self.handle_live()
            return
        if path != "/rotation-count":
            self.send_error(404)
            return
        try:
            data = self._read_json(256)
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
        """Accept {"live": bool} from the page, the toggle script or the hotkey."""
        try:
            live = self._read_json(64)["live"]
            if type(live) is not bool:
                raise ValueError("invalid switch")
        except (ValueError, KeyError, TypeError, UnicodeDecodeError):
            self.send_error(400)
            return
        self.send_json({"live": set_live(live)})

    def log_message(self, format, *args):
        pass


def set_live(live: bool, persist: bool = True) -> bool:
    """Update the in-process switch, optionally persist it, and log the change."""
    WallpaperFiles.live_mode = bool(live)
    if persist:
        try:
            save_live(live)
        except OSError as error:
            log(f"Live switch save failed: {error!r}")
    log(f"Live atmosphere {'on' if live else 'off'}")
    return WallpaperFiles.live_mode


def start_server() -> tuple[http.server.ThreadingHTTPServer, int]:
    """Bind an ephemeral localhost port and serve in a daemon thread."""
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), WallpaperFiles)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server, server.server_address[1]
