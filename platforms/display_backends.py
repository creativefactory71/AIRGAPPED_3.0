# platforms/display_backends.py
import os
import importlib
import pygame


import os, time, importlib
import pygame
from debug import dbg, set_kv


def _rgb_to_rgb565_bytes(surf: pygame.Surface, swap_bytes: bool) -> bytes:
    """Convert a Pygame RGB surface to RGB565 byte stream."""
    rgb = pygame.image.tostring(surf, "RGB")
    out = bytearray(len(rgb) // 3 * 2)
    j = 0
    for i in range(0, len(rgb), 3):
        r, g, b = rgb[i], rgb[i + 1], rgb[i + 2]
        v = ((r & 0xF8) << 8) | ((g & 0xFC) << 3) | (b >> 3)
        if swap_bytes:
            out[j] = v & 0xFF
            out[j + 1] = (v >> 8) & 0xFF
        else:
            out[j] = (v >> 8) & 0xFF
            out[j + 1] = v & 0xFF
        j += 2
    return bytes(out)


class PCWindowBackend:
    """Standard SDL window for desktop."""
    def __init__(self, w: int, h: int, title: str = "Airgapped Wallet"):
        pygame.display.init()
        self.screen = pygame.display.set_mode((w, h))
        pygame.display.set_caption(title)

    def surface(self) -> pygame.Surface: return self.screen
    def pump_input(self): pygame.event.pump()
    def flush(self, dirty=None): pygame.display.update(dirty if dirty else None)
    def shutdown(self): pygame.display.quit()


class PiFBCompatBackend:
    """
    Headless off-screen Surface + write to Linux framebuffer as RGB565.
    - Tries to use your old fb writer if available (fbio.FramebufferWriter & DirtyFlusher).
    - Otherwise falls back to a direct write() using os.open('/dev/fbX').
    - No pygame.display.set_mode is created (SDL dummy video driver).
    """
    def __init__(
        self,
        w: int,
        h: int,
        fbdev: str = "/dev/fb0",
        swap_bytes: bool = True,
        rotation: int = 0,
    ):
        # Headless SDL
        os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
        pygame.display.init()

        # IMPORTANT: no .convert() when no display mode is set
        self.canvas = pygame.Surface((w, h))
        self.w, self.h = w, h
        self.swap = bool(swap_bytes)
        self.rot = int(rotation) % 360
        self.fbdev = fbdev

        # Try to use your previous project's fb writer stack
        self._writer = None
        self._flusher = None
        try:
            fbio = importlib.import_module("fbio")
            DirtyFlusher = importlib.import_module("dirty_flusher").DirtyFlusher
            # discover a plausible writer class
            for name in ("FramebufferWriter", "FBWriter", "Writer"):
                if hasattr(fbio, name):
                    cls = getattr(fbio, name)
                    try:
                        # try the rich signature first
                        self._writer = cls(device=fbdev, width=w, height=h, fmt="RGB565", swap_bytes=self.swap)
                    except Exception:
                        try:
                            self._writer = cls(fbdev, w, h)  # minimal signature
                        except Exception:
                            pass
                    break
            if self._writer:
                # Flusher will call our _flush_full when frame is dirty
                self._flusher = DirtyFlusher(self._flush_full)
        except Exception:
            # Fallback to raw file writes
            self._writer = None
            self._flusher = None
            self._fb_file = open(fbdev, "wb", buffering=0)

    def surface(self) -> pygame.Surface:
        return self.canvas

    def pump_input(self):
        pygame.event.pump()

    # --- internal flushers -------------------------------------------------
    def _frame_to_bytes(self) -> bytes:
        frame = self.canvas
        if self.rot:
            if self.rot == 90:   frame = pygame.transform.rotate(frame, -90)
            elif self.rot == 180: frame = pygame.transform.rotate(frame, 180)
            elif self.rot == 270: frame = pygame.transform.rotate(frame, 90)
        return _rgb_to_rgb565_bytes(frame, self.swap)

    def _flush_full(self, *_args, **_kwargs):
        """Called by DirtyFlusher when the frame is marked dirty."""
        buf = self._frame_to_bytes()
        try:
            if self._writer and hasattr(self._writer, "write"):
                # your writer likely knows how to blit raw bytes or surfaces
                try:
                    self._writer.write(buf)  # prefer raw fast path
                except Exception:
                    # try surface path if available
                    if hasattr(self._writer, "blit_surface"):
                        self._writer.blit_surface(self.canvas)
                    else:
                        # fallback to direct device file if writer lacks a method
                        f = getattr(self, "_fb_file", None)
                        if f is None:
                            self._fb_file = open(self.fbdev, "wb", buffering=0)
                            f = self._fb_file
                        f.seek(0)
                        f.write(buf)
            else:
                # direct device write
                f = getattr(self, "_fb_file", None)
                if f is None:
                    self._fb_file = open(self.fbdev, "wb", buffering=0)
                    f = self._fb_file
                f.seek(0)
                f.write(buf)
        except Exception:
            pass  # do not crash the render loop on IO hiccups

    # --- public API expected by runtime -----------------------------------
    def flush(self, dirty=None):
        # We always push full frame; 'dirty' is optional
        if self._flusher:
            # mark dirty so the flusher batches writes
            try:
                self._flusher.mark_full()
                return
            except Exception:
                # fallback to immediate
                self._flush_full()
        else:
            self._flush_full()

    def shutdown(self):
        try:
            if self._flusher and hasattr(self._flusher, "stop"):
                self._flusher.stop()
        except Exception:
            pass
        try:
            if self._writer and hasattr(self._writer, "close"):
                self._writer.close()
        except Exception:
            pass
        try:
            if hasattr(self, "_fb_file"):
                self._fb_file.close()
        except Exception:
            pass
        pygame.display.quit()

class PCWindowBackend:
    """Standard SDL window for desktop."""
    def __init__(self, w: int, h: int, title: str = "Airgapped Wallet"):
        pygame.display.init()
        # Optional: ensure we’re not accidentally using the dummy driver
        if os.environ.get("SDL_VIDEODRIVER", "").lower() == "dummy":
            dbg("SDL_VIDEODRIVER=dummy on PC; clearing for real window", level="WARN")
            os.environ.pop("SDL_VIDEODRIVER", None)
            pygame.display.quit()
            pygame.display.init()

        # Create the window
        flags = 0  # you may add pygame.DOUBLEBUF if you like; flip() works either way
        self.screen = pygame.display.set_mode((w, h), flags)
        pygame.display.set_caption(title)

        # Prime: draw once and flip so first frame is visible on all drivers
        self.screen.fill((0, 0, 0))
        pygame.display.flip()

        dbg(f"PCWindowBackend init {w}x{h} SDL_VIDEODRIVER={os.environ.get('SDL_VIDEODRIVER')}")
        set_kv("size", (w, h))

    def surface(self) -> pygame.Surface: 
        return self.screen

    def pump_input(self):
        pygame.event.pump()

    def flush(self, dirty=None):
        # Use full flip for maximum compatibility across PC drivers
        pygame.display.flip()

    def shutdown(self):
        pygame.display.quit()
