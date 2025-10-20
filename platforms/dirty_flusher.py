# core/dirty_flusher.py
import threading, time
from collections import deque
import pygame

class DirtyFlusher:
    """
    Background flusher that:
      • coalesces dirty rects
      • flushes at most target_hz times per second
      • uses fb.write_rect(...) if available, else single fb.write(...)
    """
    def __init__(self, fb, canvas: pygame.Surface, canvas_lock: threading.Lock,
                 swap_bytes=False, target_hz=30, max_rects_per_flush=8, union_margin=2):
        self.fb = fb
        self.canvas = canvas
        self.lock = canvas_lock
        self.swap_bytes = swap_bytes
        self.period = 1.0 / float(target_hz)
        self.max_rects = max_rects_per_flush
        self.union_margin = union_margin

        self.screen_rect = pygame.Rect(0, 0, canvas.get_width(), canvas.get_height())
        self.have_write_rect = hasattr(fb, "write_rect")
        self._rect_q = deque()
        self._evt = threading.Event()
        self._stop = False
        self._t = threading.Thread(target=self._run, name="DirtyFlusher", daemon=True)
        self._t.start()

    def stop(self):
        self._stop = True
        self._evt.set()
        self._t.join(timeout=1.0)

    def mark(self, rect: pygame.Rect):
        r = rect.clip(self.screen_rect)
        if r.width <= 0 or r.height <= 0:
            return
        self._rect_q.append(r)
        self._evt.set()

    def mark_full(self):
        self._rect_q.append(self.screen_rect.copy())
        self._evt.set()

    # ---- internals ----

    def _merge_rects(self, rects):
        if not rects:
            return []
        # expand slightly so near-adjacent rects get merged
        grown = [pygame.Rect(r.x - self.union_margin, r.y - self.union_margin,
                             r.w + 2*self.union_margin, r.h + 2*self.union_margin)
                 for r in rects]
        merged = []
        while grown:
            a = grown.pop()
            changed = True
            while changed:
                changed = False
                keep = []
                for b in grown:
                    if a.colliderect(b):
                        a.union_ip(b)
                        changed = True
                    else:
                        keep.append(b)
                grown = keep
            a = a.clip(self.screen_rect)
            if a.w > 0 and a.h > 0:
                merged.append(a)
            if len(merged) >= self.max_rects:
                return [self.screen_rect.copy()]
        return merged

    def _coalesce_pending(self):
        if not self._rect_q:
            return []
        items = list(self._rect_q)
        self._rect_q.clear()
        for r in items:
            if r.size == self.screen_rect.size and r.topleft == self.screen_rect.topleft:
                return [self.screen_rect.copy()]
        uniq, seen = [], set()
        for r in items:
            key = (r.x, r.y, r.w, r.h)
            if key not in seen:
                seen.add(key)
                uniq.append(r)
        return self._merge_rects(uniq)

    def _run(self):
        next_time = time.perf_counter()
        while not self._stop:
            timeout = max(0.0, next_time - time.perf_counter())
            self._evt.wait(timeout)
            self._evt.clear()

            rects = self._coalesce_pending()
            if rects:
                # if a lot changed, just do a full flush
                area_sum = sum(r.w * r.h for r in rects)
                if area_sum > (self.screen_rect.w * self.screen_rect.h) // 3:
                    rects = [self.screen_rect.copy()]

                if self.have_write_rect and rects != [self.screen_rect]:
                    with self.lock:
                        for r in rects:
                            sub = self.canvas.subsurface(r).copy()
                            self.fb.write_rect(sub, r, rotate=0, swap_bytes=self.swap_bytes)
                else:
                    with self.lock:
                        self.fb.write(self.canvas, rotate=0, swap_bytes=self.swap_bytes)

            now = time.perf_counter()
            next_time = max(now, next_time + self.period)
