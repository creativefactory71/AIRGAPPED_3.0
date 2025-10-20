# on_screen_keyboard.py
# Touch-friendly QWERTY keyboard (PC + Pi)
# - Optional pump_input keeps evdev touch flowing on Pi
# - Shift toggle for upper/lower
# - Debounce on entry, click-on-release
from __future__ import annotations
import time
import pygame

class OnScreenKeyboard:
    def __init__(
        self,
        screen: pygame.Surface,
        title: str = "",
        initial: str = "",
        pump_input=None,
        allow_space: bool = True,
        max_len: int = 256,
    ):
        self.sc = screen
        self.w, self.h = screen.get_size()
        self.title = title or "Enter text"
        self.text = initial or ""
        self.pump_input = pump_input
        self.allow_space = allow_space
        self.max_len = max_len

        pygame.font.init()
        try:
            self.tf = pygame.font.SysFont("Verdana", 18, bold=True)
            self.bf = pygame.font.SysFont("Verdana", 14)
        except Exception:
            self.tf = pygame.font.Font(None, 18)
            self.bf = pygame.font.Font(None, 14)

        # keyboard layout (rows)
        self.row1 = list("qwertyuiop")
        self.row2 = list("asdfghjkl")
        self.row3 = list("zxcvbnm")
        self.digits = list("1234567890")
        self.shift = False

        self.margin = 6
        self.top_h = 44
        self.line_h = 28
        self.key_h  = 28
        self.row_gap = 4

        # build rects later
        self.rects = {}
        self._down_key = None
        self._ignore_until = 0.0

        # action bar
        y = self.h - 30
        third = (self.w - 4*self.margin)//3
        self.btn_ok     = pygame.Rect(self.margin, y, third, 24)
        self.btn_cancel = pygame.Rect(self.btn_ok.right + self.margin, y, third, 24)
        self.btn_bksp   = pygame.Rect(self.btn_cancel.right + self.margin, y, third, 24)

    # ---------- helpers ----------
    def _debounce_on_entry(self):
        cleared = pygame.event.clear([pygame.MOUSEBUTTONDOWN, pygame.MOUSEBUTTONUP, pygame.MOUSEMOTION])
        if cleared:
            # print("osk: debounced", len(cleared), "events")
            pass
        self._ignore_until = time.time() + 0.15

    def _draw_top(self):
        self.sc.fill((245,245,245))
        self.sc.blit(self.tf.render(self.title, True, (0,0,0)), (6, 6))
        box = pygame.Rect(6, 22, self.w-12, 18)
        pygame.draw.rect(self.sc, (255,255,255), box, border_radius=6)
        pygame.draw.rect(self.sc, (0,0,0), box, 1, border_radius=6)
        t = self.bf.render(self.text, True, (0,0,0))
        self.sc.blit(t, (box.x+6, box.y+1))

    def _row_rects(self):
        # compute and cache key rects each frame (handles resize)
        self.rects = {}
        y = self.top_h + 2
        # digits row
        cols = len(self.digits)
        cell_w = (self.w - self.margin*(cols+1)) // cols
        for i, ch in enumerate(self.digits):
            x = self.margin + i*(cell_w + self.margin)
            r = pygame.Rect(x, y, cell_w, self.key_h)
            self.rects[ch] = r
        y += self.key_h + self.row_gap

        # row1
        cols = len(self.row1)
        cell_w = (self.w - self.margin*(cols+1)) // cols
        for i, ch in enumerate(self.row1):
            x = self.margin + i*(cell_w + self.margin)
            r = pygame.Rect(x, y, cell_w, self.key_h)
            self.rects[ch] = r
        y += self.key_h + self.row_gap

        # row2
        cols = len(self.row2)
        cell_w = (self.w - self.margin*(cols+1)) // cols
        for i, ch in enumerate(self.row2):
            x = self.margin + i*(cell_w + self.margin)
            r = pygame.Rect(x, y, cell_w, self.key_h)
            self.rects[ch] = r
        y += self.key_h + self.row_gap

        # row3 + shift + space
        cols = len(self.row3) + 2  # shift on left/right visually
        cell_w = (self.w - self.margin*(cols+1)) // cols
        x = self.margin
        self.btn_shift = pygame.Rect(x, y, cell_w, self.key_h); x += cell_w + self.margin
        for ch in self.row3:
            r = pygame.Rect(x, y, cell_w, self.key_h)
            self.rects[ch] = r
            x += cell_w + self.margin
        self.btn_space = pygame.Rect(x, y, cell_w, self.key_h)

    def _draw_keys(self):
        # draw all letter/digit keys
        for ch, r in self.rects.items():
            pygame.draw.rect(self.sc, (230,230,230), r, border_radius=6)
            pygame.draw.rect(self.sc, (0,0,0), r, 1, border_radius=6)
            lab = ch.upper() if self.shift and ch.isalpha() else ch
            t = self.bf.render(lab, True, (0,0,0))
            self.sc.blit(t, (r.centerx - t.get_width()//2, r.centery - t.get_height()//2))

        # shift
        for r,lab in ((self.btn_shift, "⇧"), (self.btn_space, "Space")):
            pygame.draw.rect(self.sc, (230,230,230), r, border_radius=6)
            pygame.draw.rect(self.sc, (0,0,0), r, 1, border_radius=6)
            t = self.bf.render(lab, True, (0,0,0))
            self.sc.blit(t, (r.centerx - t.get_width()//2, r.centery - t.get_height()//2))

        # action bar
        for r,lab in ((self.btn_ok,"OK"),(self.btn_cancel,"CANCEL"),(self.btn_bksp,"←")):
            pygame.draw.rect(self.sc, (230,230,230), r, border_radius=8)
            pygame.draw.rect(self.sc, (0,0,0), r, 1, border_radius=8)
            t = self.bf.render(lab, True, (0,0,0))
            self.sc.blit(t, (r.centerx - t.get_width()//2, r.centery - t.get_height()//2))

    def _hit(self, pos):
        # action buttons
        if self.btn_ok.collidepoint(pos): return ("act","OK")
        if self.btn_cancel.collidepoint(pos): return ("act","CANCEL")
        if self.btn_bksp.collidepoint(pos): return ("act","BKSP")
        # special row
        if self.btn_shift.collidepoint(pos): return ("sp","SHIFT")
        if self.btn_space.collidepoint(pos): return ("sp","SPACE")
        # keys
        for ch, r in self.rects.items():
            if r.collidepoint(pos):
                return ("key", ch)
        return None

    def _apply(self, kind, lab):
        if kind == "act":
            if lab == "OK": return "OK"
            if lab == "CANCEL": return "CANCEL"
            if lab == "BKSP":
                self.text = self.text[:-1] if self.text else ""
                return None
        if kind == "sp":
            if lab == "SHIFT":
                self.shift = not self.shift
            elif lab == "SPACE" and self.allow_space:
                if len(self.text) < self.max_len:
                    self.text += " "
            return None
        if kind == "key":
            ch = lab.upper() if (self.shift and lab.isalpha()) else lab
            if len(self.text) < self.max_len:
                self.text += ch
            return None

    # ---------- public ----------
    def run(self) -> str | None:
        self._debounce_on_entry()

        while True:
            if self.pump_input:
                self.pump_input()

            # layout & draw
            self._draw_top()
            self._row_rects()
            self._draw_keys()
            pygame.display.update()

            for ev in pygame.event.get():
                if ev.type == pygame.QUIT:
                    return None
                if ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 1:
                    if time.time() < self._ignore_until:
                        continue
                    self._down_key = self._hit(ev.pos)
                if ev.type == pygame.MOUSEBUTTONUP and ev.button == 1:
                    if self._down_key:
                        up = self._hit(ev.pos)
                        if up == self._down_key:
                            kind, lab = self._down_key
                            res = self._apply(kind, lab)
                            if res == "OK": return self.text
                            if res == "CANCEL": return None
                        self._down_key = None

            pygame.time.Clock().tick(30)
