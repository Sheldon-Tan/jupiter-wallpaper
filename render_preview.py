"""Render one real 4K frame with local Chrome for visual quality checks.

Usage:
    python render_preview.py [cassini|hubble|merged] [phase] [live|static] [flow]

    phase  starting longitude, 0..1
    live   live atmosphere on (default) or static rigid rotation
    flow   freeze the atmosphere at this many simulated seconds
"""

import http.server
from functools import partial
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import threading

from wallpaper_host import chrome_path


ROOT = Path(__file__).resolve().parent


def main():
    class QuietServer(http.server.SimpleHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def end_headers(self):
            # Headless Chrome must never reuse a cached shader between runs.
            self.send_header("Cache-Control", "no-store, must-revalidate")
            super().end_headers()

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
    live = sys.argv[3].lower() if len(sys.argv) > 3 else "live"
    if live not in ("live", "static"):
        raise ValueError("Use live or static")
    flow = float(sys.argv[4]) if len(sys.argv) > 4 else None
    extra = sys.argv[5] if len(sys.argv) > 5 else ""
    size = sys.argv[6].lower() if len(sys.argv) > 6 else "3840x2160"
    width, height = (int(value) for value in size.split("x"))
    suffix = (f"_phase_{phase:g}" if phase is not None else "")
    suffix += "_static" if live == "static" else ""
    suffix += f"_flow{flow:g}" if flow is not None else ""
    suffix += f"_extra{extra.replace('=', '-').replace(',', '_')}" if extra else ""
    suffix += f"_{width}x{height}" if (width, height) != (3840, 2160) else ""
    output = ROOT / f"preview_{mode}{suffix}_4k.png"
    url = (f"http://127.0.0.1:{server.server_address[1]}/?map={mode}"
           + (f"&phase={phase}" if phase is not None else "")
           + ("&live=0" if live == "static" else "")
           + (f"&flow={flow}" if flow is not None else "")
           + ("&" + extra if extra else ""))
    profile = tempfile.mkdtemp(prefix="jupiter-preview-")
    try:
        subprocess.run([
            str(chrome_path()), "--headless=new", "--enable-unsafe-swiftshader",
            "--disable-gpu-sandbox", "--hide-scrollbars",
            f"--user-data-dir={profile}",
            "--force-device-scale-factor=1", f"--window-size={width},{height}",
            f"--screenshot={output}", "--virtual-time-budget=9000", url,
        ], cwd=ROOT, timeout=120, check=True, stdout=subprocess.DEVNULL)
    finally:
        shutil.rmtree(profile, ignore_errors=True)
        server.shutdown()
    print(output)


if __name__ == "__main__":
    main()
