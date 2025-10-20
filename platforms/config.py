# platform/config.py
import json, os
from pathlib import Path

DEFAULT = {
    "profile": "auto",            # auto | pc | pi
    "screen": {"width": 320, "height": 240, "rotation": 0},
    "backend": "auto",            # auto | sdl | fbwriter
    "fb": {"device": "/dev/fb0", "swap_bytes": True, "target_hz": 30},
    "touch": {
        "device": "/dev/input/touchscreen",  # or null to disable
        "calib": [200, 3900, 200, 3900],     # xmin,xmax,ymin,ymax raw ADC
        "swap_xy": True, "invertx": True, "inverty": False, "rot": 0
    },
    "qr_scanner": {"backend_pc": "opencv", "backend_pi": "zbarcam"}
}

CFG_PATH = Path("platform.json")

def load_platform_config() -> dict:
    data = {}
    if CFG_PATH.exists():
        try: data = json.loads(CFG_PATH.read_text() or "{}")
        except Exception: data = {}
    # merge defaults (shallow)
    merged = DEFAULT | data
    merged["screen"] = DEFAULT["screen"] | merged.get("screen", {})
    merged["fb"]     = DEFAULT["fb"]     | merged.get("fb", {})
    merged["touch"]  = DEFAULT["touch"]  | merged.get("touch", {})
    return merged
