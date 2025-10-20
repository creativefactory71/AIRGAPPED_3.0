# debug.py
import os, time, json
from pathlib import Path

# ----- config detect -----
_CFG = None
def _load_cfg():
    global _CFG
    if _CFG is not None: return _CFG
    cfg = {}
    for p in ("platform.json", "settings.json"):
        pp = Path(p)
        if pp.exists():
            try: cfg |= json.loads(pp.read_text() or "{}")
            except Exception: pass
    _CFG = cfg
    return cfg

def enabled() -> bool:
    e = os.environ.get("DEBUG", "").strip().lower()
    if e in ("1","true","yes","on"): return True
    return bool(_load_cfg().get("debug", False))

def overlay_enabled() -> bool:
    e = os.environ.get("DEBUG_OVERLAY", "").strip().lower()
    if e in ("1","true","yes","on"): return True
    return bool(_load_cfg().get("debug_overlay", False))

# ----- logger with throttle -----
_LAST = {}
def dbg(msg: str, level: str="INFO", tag: str|None=None, throttle_ms: int|None=None):
    if not enabled(): return
    now = time.time()
    if tag and throttle_ms:
        if now - _LAST.get(tag, 0.0) < throttle_ms/1000.0: return
        _LAST[tag] = now
    ts = time.strftime("%H:%M:%S")
    print(f"[{ts}] [{level}] {msg}", flush=True)

# ----- shared debug state for HUD -----
STATE = {
    "fb": None, "fb_name": None, "size": None, "swap": None, "rot": None,
    "touch_dev": None, "state": None,
    "touch_raw": None, "touch_xy": None, "touch_down": False,
    "flush_ms": None, "fps": None,
}
def set_kv(k, v): STATE[k] = v

def draw_overlay(surface, fps: float|None=None):
    if not overlay_enabled(): return
    import pygame
    w,h = surface.get_size()
    # compose one line of status
    st = STATE
    bits = []
    if st["state"]: bits.append(f"STATE:{st['state']}")
    if fps is not None: bits.append(f"FPS:{fps:.0f}")
    if st["flush_ms"] is not None: bits.append(f"FL:{st['flush_ms']:.1f}ms")
    if st["touch_xy"] is not None:
        bits.append(f"T:{st['touch_xy']}{'✱' if st['touch_down'] else ''}")
    line = "  ".join(bits) if bits else "DEBUG"

    bar = pygame.Surface((w, 14))
    bar.set_alpha(180); bar.fill((0,0,0))
    surface.blit(bar, (0, h-14))
    font = pygame.font.Font(None, 12)
    surface.blit(font.render(line, True, (255,255,255)), (4, h-12))
