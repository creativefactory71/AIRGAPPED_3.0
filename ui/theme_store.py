# theme_store.py
from pathlib import Path
import json

SETTINGS_PATH = Path("settings.json")

# --- Built-in themes ---
THEMES = {
    "classic": {
        "name": "Classic Light",
        "colors": {
            "bg": (255, 255, 255),
            "fg": (0, 0, 0),
            "muted": (120, 120, 120),
            "card": (238, 238, 238),
            "border": (0, 0, 0),
            "accent": (28, 110, 255),
            "accent_fg": (255, 255, 255),
        },
        "radius": 8, "shadow": False, "focus_ring": True, "font_scale": 1.0,
    },
    "amoled": {
        "name": "AMOLED Dark",
        "colors": {
            "bg": (0, 0, 0),
            "fg": (240, 240, 240),
            "muted": (160, 160, 160),
            "card": (16, 16, 16),
            "border": (60, 60, 60),
            "accent": (60, 130, 255),
            "accent_fg": (0, 0, 0),
        },
        "radius": 10, "shadow": False, "focus_ring": True, "font_scale": 1.0,
    },
    "high_contrast": {
        "name": "High Contrast",
        "colors": {
            "bg": (255, 255, 255),
            "fg": (0, 0, 0),
            "muted": (0, 0, 0),
            "card": (255, 255, 0),
            "border": (0, 0, 0),
            "accent": (255, 0, 0),
            "accent_fg": (255, 255, 255),
        },
        "radius": 2, "shadow": False, "focus_ring": True, "font_scale": 1.0,
    },
    "ocean": {
        "name": "Ocean",
        "colors": {
            "bg": (232, 244, 248),
            "fg": (10, 35, 48),
            "muted": (70, 100, 120),
            "card": (214, 234, 248),
            "border": (110, 160, 190),
            "accent": (20, 110, 170),
            "accent_fg": (255, 255, 255),
        },
        "radius": 12, "shadow": False, "focus_ring": True, "font_scale": 1.0,
    },
    "retro": {
        "name": "Retro",
        "colors": {
            "bg": (250, 245, 235),
            "fg": (40, 30, 20),
            "muted": (120, 100, 80),
            "card": (240, 230, 210),
            "border": (90, 70, 50),
            "accent": (200, 120, 40),
            "accent_fg": (20, 10, 0),
        },
        "radius": 6, "shadow": False, "focus_ring": False, "font_scale": 1.0,
    },
}

DEFAULTS = {
    "theme": "classic",
    "ui_mode": "grid",   # 'list' | 'grid' | 'compact'
}

def _read_settings():
    try:
        if SETTINGS_PATH.exists():
            data = json.loads(SETTINGS_PATH.read_text() or "{}")
        else:
            data = {}
    except Exception:
        data = {}
    for k,v in DEFAULTS.items():
        data.setdefault(k, v)
    return data

def _write_settings(data):
    data = {**DEFAULTS, **(data or {})}
    SETTINGS_PATH.write_text(json.dumps(data, indent=2))

# ---- Theme API ----
def list_themes():
    return [{"key": k, "name": v["name"]} for k,v in THEMES.items()]

def get_theme_key():
    return _read_settings().get("theme", DEFAULTS["theme"])

def set_theme_key(key: str):
    if key not in THEMES:
        key = "classic"
    data = _read_settings()
    data["theme"] = key
    _write_settings(data)

def theme_color(name: str):
    key = get_theme_key()
    theme = THEMES.get(key, THEMES["classic"])
    return theme["colors"].get(name, (0,0,0))

def theme_radius():
    key = get_theme_key()
    return THEMES.get(key, THEMES["classic"]).get("radius", 8)

# ---- UI Mode API ----
def get_ui_mode() -> str:
    return _read_settings().get("ui_mode", DEFAULTS["ui_mode"])

def set_ui_mode(mode: str):
    mode = (mode or "").lower()
    if mode not in ("list", "grid", "compact"):
        mode = "grid"
    data = _read_settings()
    data["ui_mode"] = mode
    _write_settings(data)
