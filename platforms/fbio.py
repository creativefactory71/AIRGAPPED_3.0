# fbio.py — framebuffer detection + fast frame/rect writer
import os, mmap, pygame
from typing import Tuple

def fb_info(fbdev: str) -> Tuple[int,int,int,int]:
    base = f"/sys/class/graphics/{os.path.basename(fbdev)}"
    def rtxt(p):
        try:
            with open(p) as f: return f.read().strip()
        except: return None
    def rint(p, d=None):
        s = rtxt(p)
        try: return int(s) if s is not None else d
        except: return d

    vs = rtxt(f"{base}/virtual_size")
    if vs and "," in vs:
        w, h = vs.split(",", 1); W, H = int(w), int(h)
    else:
        W = rint(f"{base}/xres", 240); H = rint(f"{base}/yres", 320)
    bpp    = rint(f"{base}/bits_per_pixel", 16)
    stride = rint(f"{base}/stride", None) or (W * bpp) // 8
    return W, H, bpp, stride


class FramebufferWriter:
    """Minimal writer for /dev/fbX. Call write(surface, rotate=0/90/180/270) or write_rect(...)."""
    def __init__(self, fbdev="/dev/fb0"):
        self.fbdev = fbdev
        self.W, self.H, self.bpp, self.stride = fb_info(fbdev)
        # O_SYNC is unnecessary for mmap and can slow syscalls; drop it.
        self.fd = os.open(self.fbdev, os.O_RDWR)
        # Map whole buffer once; use slicing for per-row copies.
        self.mm = mmap.mmap(self.fd, self.stride * self.H, mmap.MAP_SHARED,
                            mmap.PROT_WRITE | mmap.PROT_READ, 0)

    def close(self):
        try:
            self.mm.close()
        finally:
            try: os.close(self.fd)
            except: pass

    # --- pixel packers (hot path) ---
    def _rgb888_to_rgb565(self, rgb: bytes, swap: bool) -> Tuple[bytes, int]:
        n = len(rgb) // 3
        out = bytearray(n * 2)
        mv_in  = memoryview(rgb)
        mv_out = memoryview(out)
        j = 0
        # Local var binding for speed
        _and = int.__and__
        for i in range(0, n * 3, 3):
            r = mv_in[i]
            g = mv_in[i + 1]
            b = mv_in[i + 2]
            v = ((_and(r, 0xF8) << 8) | (_and(g, 0xFC) << 3) | (b >> 3))
            if swap:
                mv_out[j]     = (v >> 8) & 0xFF
                mv_out[j + 1] =  v       & 0xFF
            else:
                mv_out[j]     =  v       & 0xFF
                mv_out[j + 1] = (v >> 8) & 0xFF
            j += 2
        return out, 2  # return bytearray (writable) + bytes/pixel

    def _rgb888_to_xrgb8888(self, rgb: bytes) -> Tuple[bytes, int]:
        n = len(rgb) // 3
        out = bytearray(n * 4)
        mv_in  = memoryview(rgb)
        mv_out = memoryview(out)
        j = 0
        for i in range(0, n * 3, 3):
            r = mv_in[i]
            g = mv_in[i + 1]
            b = mv_in[i + 2]
            mv_out[j + 0] = b
            mv_out[j + 1] = g
            mv_out[j + 2] = r
            mv_out[j + 3] = 0
            j += 4
        return out, 4

    # --- full-frame write ---
    def write(self, surf: pygame.Surface, rotate: int = 0, swap_bytes: bool = False):
        frame = surf
        print("Entered Write func")
        if rotate in (90, 180, 270):
            angle = -rotate if rotate in (90, 270) else 180
            frame = pygame.transform.rotate(surf, angle)

        rgb = pygame.image.tostring(frame, "RGB")
        if self.bpp == 16:
            data, px = self._rgb888_to_rgb565(rgb, swap=swap_bytes)
        elif self.bpp == 32:
            data, px = self._rgb888_to_xrgb8888(rgb)
        else:
            raise SystemExit(f"Unsupported bpp: {self.bpp}")

        row_in = frame.get_width() * px
        H = frame.get_height()

        mmv = memoryview(self.mm)
        datav = memoryview(data)

        if self.stride == row_in:
            # Contiguous; one big copy
            mmv[0:len(datav)] = datav
            return

        # Strided; copy rows via slices (faster than mm.seek per row)
        for row in range(H):
            off_fb = row * self.stride
            off_in = row * row_in
            mmv[off_fb: off_fb + row_in] = datav[off_in: off_in + row_in]

    # --- partial-rect write (preferred by DirtyFlusher) ---
    def write_rect(self, surf: pygame.Surface, dst_rect: pygame.Rect,
                   rotate: int = 0, swap_bytes: bool = False):
        frame = surf
        if rotate in (90, 180, 270):
            angle = -rotate if rotate in (90, 270) else 180
            frame = pygame.transform.rotate(surf, angle)

        rgb = pygame.image.tostring(frame, "RGB")
        if self.bpp == 16:
            data, px = self._rgb888_to_rgb565(rgb, swap=swap_bytes)
        elif self.bpp == 32:
            data, px = self._rgb888_to_xrgb8888(rgb)
        else:
            raise SystemExit(f"Unsupported bpp: {self.bpp}")

        W = frame.get_width()
        H = frame.get_height()
        row_in = W * px

        dst_x, dst_y = int(dst_rect.x), int(dst_rect.y)
        base = dst_y * self.stride + dst_x * (self.bpp // 8)

        mmv   = memoryview(self.mm)
        datav = memoryview(data)

        # Fast path: rect spans full width and is stride-aligned at x=0
        if dst_x == 0 and row_in == self.stride and W == self.W:
            mmv[base: base + len(datav)] = datav
            return

        # Otherwise, copy row-by-row with slices (no mm.seek)
        for row in range(H):
            off_fb = base + row * self.stride
            off_in = row * row_in
            mmv[off_fb: off_fb + row_in] = datav[off_in: off_in + row_in]
