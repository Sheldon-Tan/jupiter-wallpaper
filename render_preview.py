"""Render one real 4K frame with local Chrome for visual quality checks."""

import http.server
from functools import partial
from pathlib import Path
import subprocess
import sys
import threading

from wallpaper_host import chrome_path


ROOT = Path(__file__).resolve().parent


def main():
    class QuietServer(http.server.SimpleHTTPRequestHandler):
        def log_message(self, *args):
            pass

    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0),
                                              partial(QuietServer, directory=str(ROOT)))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    mode = sys.argv[1] if len(sys.argv) > 1 else "hubble"
    if mode not in ("hubble", "cassini", "merged"):
        raise ValueError("Use hubble, cassini, or merged")
    phase = float(sys.argv[2]) if len(sys.argv) > 2 else None
    if phase is not None and not 0 <= phase < 1:
        raise ValueError("Phase must be between 0 and 1")
    output = ROOT / (f"preview_{mode}_phase_{phase:g}_4k.png" if phase is not None
                     else f"preview_{mode}_4k.png")
    try:
        subprocess.run([
            str(chrome_path()), "--headless=new", "--enable-unsafe-swiftshader",
            "--disable-gpu-sandbox", "--hide-scrollbars",
            "--force-device-scale-factor=1", "--window-size=3840,2160",
            f"--screenshot={output}", "--virtual-time-budget=9000",
            f"http://127.0.0.1:{server.server_address[1]}/?map={mode}"
            + (f"&phase={phase}" if phase is not None else ""),
        ], cwd=ROOT, timeout=60, check=True, stdout=subprocess.DEVNULL)
    finally:
        server.shutdown()
    print(output)


if __name__ == "__main__":
    main()
