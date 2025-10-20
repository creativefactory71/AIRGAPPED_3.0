# touch_xpt2046.py — modular XPT2046/ADS7846 touch via evdev
from typing import Optional, Tuple
import os, select
from evdev import InputDevice, ecodes

class XPT2046Touch:
    """
    width/height: UI canvas size (post-draw orientation)
    calib: (xmin,xmax,ymin,ymax)
    swap_xy: True for common wiring
    rot: 0/90/180/270 — rotate output coords
    """
    def __init__(
        self,
        width:int, height:int,
        dev_path: Optional[str] = None,
        calib: Tuple[int,int,int,int] = (200,3900,200,3900),
        swap_xy: bool = False,
        invertx: bool = True,
        inverty: bool = False,
        rot: int = 180
    ):
        self.W, self.H = width, height
        self.xmin, self.xmax, self.ymin, self.ymax = calib
        self.swap_xy, self.invertx, self.inverty = swap_xy, invertx, inverty
        self.rot = rot % 360
        self.dev = self._open(dev_path)
        self._down=False; self._xr=None; self._yr=None

    def _open(self, path: Optional[str]) -> InputDevice:
        if path and os.path.exists(path):
            return InputDevice(path)
        for n in sorted(os.listdir("/dev/input")):
            if not n.startswith("event"): continue
            p=f"/dev/input/{n}"
            try:
                d=InputDevice(p); nm=(d.name or "").lower()
                if "xpt2046" in nm or "ads7846" in nm or "touch" in nm:
                    return d
            except: pass
        raise RuntimeError("XPT2046/ADS7846 touch not found.")

    @staticmethod
    def _map(v:int, vmin:int, vmax:int, size:int, inv:bool) -> int:
        v = max(vmin, min(v, vmax))
        r = (v - vmin) / float(max(1, (vmax - vmin)))
        if inv: r = 1.0 - r
        return int(round(r * (size - 1)))

    def _apply_rot(self, x:int, y:int):
        if self.rot == 0:   return x, y
        if self.rot == 90:  return (self.H-1 - y, x)
        if self.rot == 180: return (self.W-1 - x, self.H-1 - y)
        if self.rot == 270: return (y, self.W-1 - x)
        return x, y

    def read(self, timeout: float = 0.0):
        r,_,_ = select.select([self.dev.fd],[],[],timeout)
        changed=False
        if r:
            for ev in self.dev.read():
                if ev.type==ecodes.EV_KEY and ev.code==ecodes.BTN_TOUCH:
                    self._down=(ev.value==1); changed=True
                elif ev.type==ecodes.EV_ABS:
                    if ev.code==ecodes.ABS_X: self._xr=ev.value; changed=True
                    if ev.code==ecodes.ABS_Y: self._yr=ev.value; changed=True

        if not changed:
            return (None, None, self._down)
        if self._xr is None or self._yr is None:
            return (None, None, self._down)

        xr, yr = self._xr, self._yr
        if self.swap_xy:
            xr, yr = yr, xr

        x = self._map(xr, self.xmin, self.xmax, self.W, self.invertx)
        y = self._map(yr, self.ymin, self.ymax, self.H, self.inverty)
        return (*self._apply_rot(x,y), self._down)
