"""项目路径、日志与两份小的 JSON 状态文件。

这一层不碰 ctypes、不碰 HTTP，只负责“把东西写在哪里、怎么读回来”。
其余模块都依赖它，它不依赖其余模块。
"""

from __future__ import annotations

import json
from pathlib import Path
import time


ROOT = Path(__file__).resolve().parent.parent   # 项目根目录（python/ 的上一层）
RUNTIME = ROOT / "runtime"                      # 运行期产物统一放这里
RUNTIME.mkdir(parents=True, exist_ok=True)

STATE = RUNTIME / ".wallpaper-state.json"        # 运行时状态：pid / 端口 / 窗口句柄
STOP = RUNTIME / ".stop"                          # 停止信号文件
LOG = RUNTIME / "wallpaper.log"                   # 追加日志
ROTATION_COUNT = RUNTIME / "rotation-count.json"  # 累计自转次数
ROTATION_COUNT_TMP = RUNTIME / "rotation-count.json.tmp"
LEGACY_ROTATION_COUNT = ROOT / ".rotation-count.json"  # 旧版本的隐藏文件名
LIVE_STATE = RUNTIME / ".live-weather.json"       # 实时模拟开关
BROWSER_PROFILE = RUNTIME / "browser-profile"     # 壁纸专用 Chrome 配置目录


def log(message: str) -> None:
    """Append one timestamped line; never raise because logging failed."""
    try:
        with LOG.open("a", encoding="utf-8") as file:
            file.write(time.strftime("%Y-%m-%d %H:%M:%S ") + message + "\n")
    except OSError:
        pass


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
    """Write through a temporary file so a crash never truncates the count."""
    ROTATION_COUNT_TMP.write_text(
        json.dumps({"completed_turns": turns}) + "\n", encoding="utf-8")
    ROTATION_COUNT_TMP.replace(ROTATION_COUNT)


def load_live(default: bool = True) -> bool:
    """Read the persisted live-atmosphere switch; settings.js holds the default."""
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
