# platforms/runtime.py
import os, pygame
from pathlib import Path
from .config import load_platform_config
from .display_backends import PCWindowBackend, PiFBCompatBackend
from .touch_backends import PygameMouseInput, XPT2046TouchInput
from debug import dbg, set_kv

_SYS_GFX = Path("/sys/class/graphics")

def _is_pi() -> bool:
    if os.environ.get("PROFILE","").lower() == "pi": return True
    if os.environ.get("PROFILE","").lower() == "pc": return False
    try:
        with open("/proc/device-tree/model","r") as f: return "Raspberry Pi" in f.read()
    except Exception: return False

def _env_force_x11_if_wayland():
    if os.environ.get("PROFILE","").lower() == "pc":
        if os.environ.get("XDG_SESSION_TYPE","").lower() == "wayland":
            os.environ.setdefault("SDL_VIDEODRIVER", "x11")
            dbg("Forcing SDL_VIDEODRIVER=x11 on Wayland desktop")

def _fb_name(fbN: str) -> str|None:
    p = _SYS_GFX / fbN / "name"
    try: return p.read_text().strip()
    except Exception: return None

def _fb_virtual_size(fbN: str) -> tuple[int,int]|None:
    p = _SYS_GFX / fbN / "virtual_size"
    try:
        text = p.read_text().strip()
        if "," in text:
            w,h = text.split(",",1); return int(w), int(h)
    except Exception: pass
    return None

def _detect_fb_device() -> tuple[str|None, dict]:
    for fbN in ("fb0","fb1"):
        if (_SYS_GFX / fbN).exists():
            nm = (_fb_name(fbN) or "").lower()
            if "ili9341" in nm or "fb_ili9341" in nm:
                geom = _fb_virtual_size(fbN) or (240,320)
                return f"/dev/{fbN}", {"name": nm, "w": geom[0], "h": geom[1]}
    if (_SYS_GFX / "fb0").exists():
        nm = _fb_name("fb0") or "unknown"
        geom = _fb_virtual_size("fb0") or (320,240)
        return "/dev/fb0", {"name": nm, "w": geom[0], "h": geom[1]}
    return None, {}

def init_platform():
    cfg = load_platform_config()
    is_pi = _is_pi() if cfg.get("profile","auto").lower()=="auto" else (cfg.get("profile","").lower()=="pi")
    dbg(f"Platform path: {'PI' if is_pi else 'PC'}")

    if not is_pi:
        _env_force_x11_if_wayland()
        pygame.init()
        W = int(cfg["screen"].get("width", 320)); H = int(cfg["screen"].get("height", 240))
        disp = PCWindowBackend(W,H,title="Airgapped Wallet")
        touch = PygameMouseInput()
        screen = disp.surface()
        set_kv("fb","SDL"); set_kv("fb_name","window")
    else:
        fbdev_cfg = str(cfg.get("fb",{}).get("device","") or "")
        fbdev = fbdev_cfg if fbdev_cfg and Path(fbdev_cfg).exists() else None
        info = {}
        if fbdev is None:
            fbdev, info = _detect_fb_device()
        else:
            fbN = Path(fbdev).name
            info = {"name": _fb_name(fbN) or "unknown"}
            geom = _fb_virtual_size(fbN); 
            if geom: info["w"], info["h"] = geom
        if fbdev is None:
            fbdev = "/dev/fb0"; info = {"name":"unknown","w":240,"h":320}

        W = int(cfg["screen"].get("width", 0) or info.get("w",240))
        H = int(cfg["screen"].get("height",0) or info.get("h",320))
        rot_cfg = cfg["screen"].get("rotation","auto")
        rotation = 0 if str(rot_cfg).lower()=="auto" else (int(rot_cfg)%360)
        swap_cfg = cfg.get("fb",{}).get("swap_bytes", None)
        swap_bytes = (("ili9341" in (info.get("name",""))) if swap_cfg is None else bool(swap_cfg))

        pygame.init()
        disp = PiFBCompatBackend(W,H, fbdev=fbdev, swap_bytes=swap_bytes, rotation=rotation)
        screen = disp.surface()
        touch = XPT2046TouchInput(
            device = cfg.get("touch",{}).get("device") or None,
            size   = (W,H),
            calib  = tuple(cfg.get("touch",{}).get("calib",[200,3900,200,3900])),
            swap_xy= bool(cfg.get("touch",{}).get("swap_xy", False)),
            invertx= bool(cfg.get("touch",{}).get("invertx", True)),
            inverty= bool(cfg.get("touch",{}).get("inverty", False)),
            rot    = int(cfg.get("touch",{}).get("rot", 0))
        )
        set_kv("fb", fbdev); set_kv("fb_name", info.get("name"))

        dbg(f"FB dev: {fbdev} name={info.get('name')} geom={info.get('w')}x{info.get('h')} swap={swap_bytes} rot={rotation}")

    def pump_input():
        touch.pump(); disp.pump_input()

    def flush(dirty=None):
        disp.flush(dirty)

    def shutdown():
        dbg("Shutdown begin")
        try:
            flush(None)
            for _ in range(2):
                pygame.event.pump(); pygame.time.delay(16)
        except Exception: pass
        try: disp.shutdown()
        except Exception: pass
        pygame.quit()
        dbg("Shutdown done")

    return screen, pump_input, flush, shutdown

