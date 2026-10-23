"""Open a fast rotation preview in the normal browser while wallpaper is running."""

import json
from pathlib import Path
import webbrowser


state_file = Path(__file__).resolve().parent / ".wallpaper-state.json"
if not state_file.exists():
    raise SystemExit("Start the wallpaper first.")
state = json.loads(state_file.read_text(encoding="utf-8"))
webbrowser.open(f"http://127.0.0.1:{state['port']}/?demo=1&map={state['map']}")
