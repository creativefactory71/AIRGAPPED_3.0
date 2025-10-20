# numeric_keyboard.py
# Touch-friendly numeric keypad (works on PC and Pi)
# - Optional pump_input keeps evdev touch flowing on Pi
# - Debounces queued pointer events on entry
# - Click-on-release to avoid cascading taps
from __future__ import annotations
import time
import pygame

class NumericKeyboard:
    def __init__(
        self,
        screen: pygame.Surface,
        title: str = "",
        initial: str = "",
        pump_input=None,
        allow_decimal: bool = True,
        allow_negative: bool = False,
        mask: bool = False,
    ):
        self.sc = screen
        self.w, self.h = screen.get_size()
        self.title = title or "Enter value"
        self.text = initial or ""
        self.pump_input = pump_input
        self.allow_decimal = allow_decimal
        self.allow_negative = allow_negative
        self.mask = mask

        pygame.font.init()
        try:
            self.tf = pygame.font.SysFont("Verdana", 18, bold=True)
            self.bf = pygame.font.SysFont("Verdana", 14)
        except Exception:
            self.tf = pygame.font.Font(None, 18)
            self.bf = pygame.font.Font(None, 14)

        # layout
        self.margin = 6
        self.top_h = 40
        self.keypad_h = self.h - self.top_h - 34  # leave space for action row
        self.rows, self.cols = 4, 3  # 1..9 / . 0 ←
        self.cell_w = (self.w - self.margin* (self.cols+1)) // self.cols
        self.cell_h = (self.keypad_h - self.margin*(self.rows+1)) // self.rows
        self.action_h = 28

        # action buttons
        y_act = self.h - self.action_h - self.margin
        self.btn_clear = pygame.Rect(self.margin, y_act, (self.w-4*self.margin)//3, self.action_h)
        self.btn_ok    = pygame.Rect(self.btn_clear.right + self.margin, y_act, (self.w-4*self.margin)//3, self.action_h)
        self.btn_cancel= pygame.Rect(self.btn_ok.right + self.margin, y_act, (self.w-4*self.margin)//3, self.action_h)

        # mapping for grid
        self.grid = [
            ["7","8","9"],
            ["4","5","6"],
            ["1","2","3"],
            ["." if allow_decimal else "", "0", "←"],
        ]

        self._down_idx = None
        self._ignore_until = 0.0

    # ---------- helpers ----------
    def _debounce_on_entry(self):
        cleared = pygame.event.clear([pygame.MOUSEBUTTONDOWN, pygame.MOUSEBUTTONUP, pygame.MOUSEMOTION])
        if cleared:
            # print("numeric_keyboard: debounced", len(cleared), "events")
            pass
        self._ignore_until = time.time() + 0.15

    def _draw_top(self):
        self.sc.fill((245,245,245))
        self.sc.blit(self.tf.render(self.title, True, (0,0,0)), (6, 6))
        # input box
        box = pygame.Rect(6, 22, self.w-12, 16)
        pygame.draw.rect(self.sc, (255,255,255), box, border_radius=6)
        pygame.draw.rect(self.sc, (0,0,0), box, 1, border_radius=6)
        disp = ("•"*len(self.text)) if self.mask else self.text
        self.sc.blit(self.bf.render(disp, True, (0,0,0)), (box.x+6, box.y+1))

    def _cell_rect(self, r, c):
        x = self.margin + c*(self.cell_w + self.margin)
        y = self.top_h + self.margin + r*(self.cell_h + self.margin)
        return pygame.Rect(x, y, self.cell_w, self.cell_h)

    def _draw_keypad(self):
        for r in range(self.rows):
            for c in range(self.cols):
                lab = self.grid[r][c]
                if lab == "":  # disabled (.)
                    continue
                rect = self._cell_rect(r,c)
                pygame.draw.rect(self.sc, (230,230,230), rect, border_radius=10)
                pygame.draw.rect(self.sc, (0,0,0), rect, 1, border_radius=10)
                text = self.bf.render(lab, True, (0,0,0))
                self.sc.blit(text, (rect.centerx - text.get_width()//2,
                                    rect.centery - text.get_height()//2))

    def _draw_actions(self):
        for r,lab in ((self.btn_clear,"CLR"),(self.btn_ok,"OK"),(self.btn_cancel,"CANCEL")):
            pygame.draw.rect(self.sc,(230,230,230),r,border_radius=8)
            pygame.draw.rect(self.sc,(0,0,0),r,1,border_radius=8)
            t = self.bf.render(lab, True, (0,0,0))
            self.sc.blit(t, (r.centerx - t.get_width()//2, r.centery - t.get_height()//2))

    def _press_at(self, pos):
        # action bar has priority
        if self.btn_clear.collidepoint(pos): return ("act","CLR")
        if self.btn_ok.collidepoint(pos):    return ("act","OK")
        if self.btn_cancel.collidepoint(pos):return ("act","CANCEL")
        # grid
        for r in range(self.rows):
            for c in range(self.cols):
                lab = self.grid[r][c]
                if not lab: continue
                rect = self._cell_rect(r,c)
                if rect.collidepoint(pos):
                    return ("key", lab)
        return None

    def _apply(self, kind, lab):
        if kind == "act":
            if lab == "CLR": self.text = ""
            elif lab == "OK": return "OK"
            elif lab == "CANCEL": return "CANCEL"
            return None
        # key
        if lab == "←":
            self.text = self.text[:-1] if self.text else ""
            return None
        if lab == "-" and not self.allow_negative:
            return None
        if lab == "." and not self.allow_decimal:
            return None
        # enforce one dot only
        if lab == "." and "." in self.text:
            return None
        self.text += lab
        return None

    # ---------- public ----------
    def run(self) -> str | None:
        self._debounce_on_entry()

        while True:
            if self.pump_input:
                self.pump_input()

            # draw
            self._draw_top()
            self._draw_keypad()
            self._draw_actions()
            pygame.display.update()

            # events
            for ev in pygame.event.get():
                if ev.type == pygame.QUIT:
                    return None
                if ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 1:
                    if time.time() < self._ignore_until:
                        continue
                    hit = self._press_at(ev.pos)
                    self._down_idx = hit
                if ev.type == pygame.MOUSEBUTTONUP and ev.button == 1:
                    if self._down_idx:
                        kind, lab = self._down_idx
                        up_hit = self._press_at(ev.pos)
                        if up_hit == self._down_idx:
                            res = self._apply(kind, lab)
                            if res == "OK":
                                return self.text
                            if res == "CANCEL":
                                return None
                        self._down_idx = None

            pygame.time.Clock().tick(30)
