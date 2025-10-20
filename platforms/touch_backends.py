# platforms/touch_backends.py
import os, glob, importlib, select, time
import pygame
from debug import dbg, set_kv

class PygameMouseInput:
    def pump(self):  # desktop mouse
        pass


def _find_touch_event_path(preferred="/dev/input/touchscreen"):
    if preferred and os.path.exists(preferred):
        return preferred
    for ev in sorted(glob.glob("/sys/class/input/event*/device/name")):
        try:
            name = open(ev, "r").read().strip().lower()
        except Exception:
            continue
        if any(k in name for k in ("ads7846", "xpt2046", "touchscreen")):
            event_dir = os.path.dirname(ev)                 # /sys/class/input/eventX/device
            eventX = os.path.basename(os.path.dirname(event_dir))  # eventX
            devnode = f"/dev/input/{eventX}"
            if os.path.exists(devnode):
                return devnode
    evs = sorted(glob.glob("/dev/input/event*"))
    return evs[0] if evs else None


class XPT2046TouchInput:
    """
    Uses your touch_xpt2046.XPT2046Touch if available.
    Else falls back to raw evdev (non-blocking, with broad compatibility).
    Posts pygame mouse events: MOVE / BUTTONDOWN / BUTTONUP.
    """
    def __init__(self, device=None, size=(240,320),
                 calib=(200,3900,200,3900), swap_xy=False, invertx=True, inverty=False, rot=0):
        self.w, self.h = size
        self.xmin, self.xmax, self.ymin, self.ymax = calib
        self.swap_xy, self.invertx, self.inverty = bool(swap_xy), bool(invertx), bool(inverty)
        self.rot = int(rot) % 360

        self.devpath = device or _find_touch_event_path()
        set_kv("touch_dev", self.devpath)
        dbg(f"Touch dev: {self.devpath} calib={calib} flags(swap_xy={self.swap_xy}, invx={self.invertx}, invy={self.inverty}, rot={self.rot})")

        self.driver = None
        self._ev = None           # evdev.InputDevice
        self._evdev_mod = None    # evdev module
        self._fd = None
        self._pressed_prev = False
        self._raw_x = None
        self._raw_y = None
        self._down = False

        # 1) Try your helper class first (if present in project)
        try:
            mod = importlib.import_module("touch_xpt2046")
            cls = getattr(mod, "XPT2046Touch", None)
            if cls:
                self.driver = cls(device=self.devpath)
                dbg("Using touch_xpt2046.XPT2046Touch")
        except Exception as e:
            dbg(f"touch_xpt2046 not usable: {e}", level="WARN")

        # 2) evdev fallback
        if self.driver is None and self.devpath:
            try:
                evdev = importlib.import_module("evdev")
                self._evdev_mod = evdev
            except ModuleNotFoundError:
                dbg("python-evdev not installed. Install with: sudo apt install python3-evdev  (or: pip3 install evdev)", level="ERROR")
                return
            except Exception as e:
                dbg(f"Cannot import evdev: {e}", level="ERROR")
                return

            try:
                self._ev = self._evdev_mod.InputDevice(self.devpath)
                self._fd = self._ev.fd
                dbg(f'Using evdev fallback on {self.devpath}: "{self._ev.name}"')

                # Try to set non-blocking in a version-compatible way
                nonblock_set = False
                for meth in ("set_nonblocking", "setblocking", "set_blocking"):
                    if hasattr(self._ev, meth):
                        try:
                            if meth == "set_nonblocking":
                                self._ev.set_nonblocking(True)              # new API
                            elif meth == "setblocking":
                                self._ev.setblocking(False)                 # stdlib-like
                            else:
                                self._ev.set_blocking(False)                 # alt spelling
                            dbg(f"evdev non-blocking via {meth}")
                            nonblock_set = True
                            break
                        except Exception as e:
                            dbg(f"{meth} failed: {e}", level="WARN")

                if not nonblock_set:
                    # Fallback: fcntl on the FD
                    try:
                        import fcntl
                        flags = fcntl.fcntl(self._fd, fcntl.F_GETFL)
                        fcntl.fcntl(self._fd, fcntl.F_SETFL, flags | os.O_NONBLOCK)
                        dbg("evdev non-blocking via fcntl")
                        nonblock_set = True
                    except Exception as e:
                        dbg(f"fcntl non-blocking failed: {e}", level="ERROR")

                # Print AbsInfo (helps calibrations)
                try:
                    X, Y = self._evdev_mod.ecodes.ABS_X, self._evdev_mod.ecodes.ABS_Y
                    ax, ay = self._ev.absinfo(X), self._ev.absinfo(Y)
                    dbg(f"Touch AbsInfo: X={ax.min}..{ax.max} Y={ay.min}..{ay.max}")
                except Exception:
                    pass

            except PermissionError as e:
                dbg(f"Permission error opening {self.devpath}: {e}. Tip: sudo usermod -aG input $USER ; then reboot.", level="ERROR")
            except Exception as e:
                dbg(f"Cannot open {self.devpath}: {e}", level="ERROR")

    # --------- math ----------
    def _normalize(self, rx, ry):
        x = (rx - self.xmin) / max(1, (self.xmax - self.xmin))
        y = (ry - self.ymin) / max(1, (self.ymax - self.ymin))
        x = min(max(x, 0.0), 1.0); y = min(max(y, 0.0), 1.0)
        sx, sy = int(x * (self.w-1)), int(y * (self.h-1))
        if self.swap_xy: sx, sy = sy, sx
        if self.invertx: sx = (self.w-1) - sx
        if self.inverty: sy = (self.h-1) - sy
        if self.rot == 90:  sx, sy = sy, (self.w-1) - sx
        if self.rot == 180: sx, sy = (self.w-1) - sx, (self.h-1) - sy
        if self.rot == 270: sx, sy = (self.h-1) - sy, sx
        return sx, sy

    def _post(self, x, y, pressed, raw=None):
        pygame.event.post(pygame.event.Event(
            pygame.MOUSEMOTION, {"pos": (x, y), "rel": (0,0), "buttons": (1,0,0) if pressed else (0,0,0)}
        ))
        if pressed and not self._pressed_prev:
            dbg(f"TOUCH PRESS raw={raw} → xy=({x},{y})")
            pygame.event.post(pygame.event.Event(pygame.MOUSEBUTTONDOWN, {"pos": (x, y), "button": 1}))
        elif not pressed and self._pressed_prev:
            dbg(f"TOUCH RELEASE raw={raw} → xy=({x},{y})")
            pygame.event.post(pygame.event.Event(pygame.MOUSEBUTTONUP, {"pos": (x, y), "button": 1}))
        else:
            dbg(f"TOUCH MOVE raw={raw} → xy=({x},{y})", tag="tmove", throttle_ms=100)
        self._pressed_prev = pressed
        set_kv("touch_raw", raw); set_kv("touch_xy", (x,y)); set_kv("touch_down", pressed)

    # --------- helper driver path ----------
    def _pump_helper(self):
        for name in ("read","read_touch","sample","get"):
            if hasattr(self.driver, name):
                try:
                    s = getattr(self.driver, name)()
                except TypeError:
                    s = getattr(self.driver, name)(0)
                if not s:
                    return
                if isinstance(s, dict):
                    rx, ry, down = s.get("x"), s.get("y"), bool(s.get("pressed", True))
                else:
                    rx, ry = s[0], s[1]
                    down = bool(s[2]) if len(s) > 2 else True
                if rx is None or ry is None:
                    return
                x, y = self._normalize(rx, ry)
                self._post(x, y, down, raw=(rx, ry))
                return

    # --------- evdev path ----------
    def _pump_evdev(self):
        if self._fd is None:
            return
        r, _, _ = select.select([self._fd], [], [], 0)
        if not r:
            return
        try:
            evdev = self._evdev_mod
            for ev in self._ev.read():
                if ev.type == evdev.ecodes.EV_ABS:
                    if ev.code == evdev.ecodes.ABS_X:
                        self._raw_x = ev.value
                    elif ev.code == evdev.ecodes.ABS_Y:
                        self._raw_y = ev.value
                elif ev.type == evdev.ecodes.EV_KEY and ev.code == evdev.ecodes.BTN_TOUCH:
                    self._down = bool(ev.value)
                elif ev.type == evdev.ecodes.EV_SYN:
                    if self._raw_x is not None and self._raw_y is not None:
                        x, y = self._normalize(self._raw_x, self._raw_y)
                        self._post(x, y, self._down, raw=(self._raw_x, self._raw_y))
        except Exception as e:
            dbg(f"evdev read error: {e}", level="ERROR")

    # --------- public ----------
    def pump(self):
        if self.driver is not None:
            self._pump_helper()
        else:
            self._pump_evdev()
