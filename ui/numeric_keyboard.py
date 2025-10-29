# numeric_keyboard.py
from __future__ import annotations
import time
import pygame

# Optional debug
try:
    from debug import dbg
except Exception:
    def dbg(*a, **k): pass

WHITE=(255,255,255); BLACK=(0,0,0); GREY=(230,230,230)
OUT=(0,0,0)

SAFE_BOTTOM = 24            # reserve space for Back/Home/Opts bar
SAFE_MARGIN = 6
PAD = 6                     # inner padding (smaller keys + more spacing)
INPUT_H = 28                # input box height
TITLE_H = 20
PIN_SPACER = 14             # gap between input and keypad
GRID_COLS = 3
GRID_ROWS = 4               # 1–9, CL/0/BK
MAX_KEY_H = 36              # cap key height so they don't feel gigantic

class NumericKeyboard:
    """
    Numeric keypad with smaller keys, breathing space, and top 'X' (Cancel) + 'OK' controls.

    API:
      NumericKeyboard(screen, title, initial="",
                      pump_input=None, allow_decimal=True, mask=False).run() -> str|None

    Grid:
      1 2 3
      4 5 6
      7 8 9
      CL 0 BK

    Top controls (small buttons above keypad, right side):
      X  (Cancel)
      OK (Done)

    Notes:
      - BK deletes one character (backspace)
      - CL clears the whole input
      - If allow_decimal=True, '.' replaces 'CL' (for amounts)
      - For PIN screens, pass mask=True and usually allow_decimal=False
    """
    def __init__(self, screen, title: str, initial: str = "",
                 pump_input=None, allow_decimal: bool = True, mask: bool = False):
        self.sc = screen
        self.title = title or "Enter value"
        self.value = initial or ""
        self.pump_input = pump_input
        self.allow_decimal = allow_decimal
        self.mask = mask

        self.w, self.h = self.sc.get_size()
        self._ignore_until = 0.0
        self.key_rects: list[tuple[pygame.Rect, str]] = []
        self.btn_cancel = None
        self.btn_ok = None

    # --- helpers ---
    def _pump(self):
        if self.pump_input: self.pump_input()

    def _debounce_on_entry(self):
        pygame.event.clear([pygame.MOUSEBUTTONDOWN, pygame.MOUSEBUTTONUP, pygame.MOUSEMOTION])
        self._ignore_until = time.time() + 0.15

    def _fonts(self):
        try:
            tf = pygame.font.SysFont("Verdana", 18, bold=True)
            bf = pygame.font.SysFont("Verdana", 18)    # key labels
            sf = pygame.font.SysFont("Verdana", 14)    # small (X/OK)
        except Exception:
            tf = pygame.font.Font(None, 18)
            bf = pygame.font.Font(None, 18)
            sf = pygame.font.Font(None, 14)
        return tf, bf, sf

    # --- layout ---
    def _compute_layout(self):
        """Compute rects for input, keypad, and small Cancel/OK buttons."""
        tf, bf, sf = self._fonts()
        top = 6

        title_rect = pygame.Rect(8, top, self.w-16, TITLE_H)
        input_rect = pygame.Rect(8, title_rect.bottom + 4, self.w-16, INPUT_H)

        # keypad area: from after input+spacer down to above bottom safe zone
        k_top = input_rect.bottom + PIN_SPACER
        k_bottom = self.h - SAFE_BOTTOM - SAFE_MARGIN
        avail_h = max(80, k_bottom - k_top)

        # row/col sizes (smaller keys: increase padding and cap height)
        key_h = min(MAX_KEY_H, (avail_h - (GRID_ROWS+1)*PAD) // GRID_ROWS)
        key_w = (self.w - (GRID_COLS+1)*PAD) // GRID_COLS

        # center the keypad block vertically within available space
        used_h = GRID_ROWS*key_h + (GRID_ROWS+1)*PAD
        y = k_top + max(0, (avail_h - used_h)//2)

        # small control buttons (X/OK) above keypad, right side
        btn_h = 20
        btn_w = 46
        btn_gap = 6
        btn_ok = pygame.Rect(self.w - SAFE_MARGIN - btn_w, input_rect.bottom + 4, btn_w, btn_h)
        btn_cancel = pygame.Rect(btn_ok.x - btn_w - btn_gap, input_rect.bottom + 4, btn_w, btn_h)

        return title_rect, input_rect, (key_w, key_h, y), btn_cancel, btn_ok

    # --- drawing ---
    def _draw(self):
        self.sc.fill(WHITE)
        tf, bf, sf = self._fonts()

        # layout
        title_rect, input_rect, (key_w, key_h, y0), btn_cancel, btn_ok = self._compute_layout()
        self.btn_cancel, self.btn_ok = btn_cancel, btn_ok

        # title
        self.sc.blit(tf.render(self.title, True, BLACK), (8, title_rect.y))

        # input box
        pygame.draw.rect(self.sc, GREY, input_rect, border_radius=8)
        pygame.draw.rect(self.sc, OUT, input_rect, 1, border_radius=8)
        disp = ("*"*len(self.value)) if self.mask else self.value
        srf = bf.render(disp, True, BLACK)
        # trim left if too long
        trimmed = disp
        while srf.get_width() > input_rect.width - 12 and trimmed:
            trimmed = trimmed[1:]
            srf = bf.render(trimmed, True, BLACK)
        self.sc.blit(srf, (input_rect.x+6, input_rect.y + (input_rect.height - srf.get_height())//2))

        # small buttons: X (Cancel) and OK (Done)
        for r, lab in ((btn_cancel, "X"), (btn_ok, "OK")):
            pygame.draw.rect(self.sc, GREY, r, border_radius=6)
            pygame.draw.rect(self.sc, OUT, r, 1, border_radius=6)
            ts = sf.render(lab, True, BLACK)
            self.sc.blit(ts, (r.centerx - ts.get_width()//2, r.centery - ts.get_height()//2))

        # keypad keys (3x4)
        self.key_rects.clear()
        labels_rows = [
            ["1","2","3"],
            ["4","5","6"],
            ["7","8","9"],
            ["CL","0","BK"],
        ]
        # optional decimal: replace 'CL' with '.'
        if self.allow_decimal:
            labels_rows[-1][0] = "."

        y = y0 + PAD
        for r in range(GRID_ROWS):
            x = PAD
            for c in range(GRID_COLS):
                rect = pygame.Rect(x, y, key_w, key_h)
                lab = labels_rows[r][c]
                pygame.draw.rect(self.sc, GREY, rect, border_radius=8)
                pygame.draw.rect(self.sc, OUT, rect, 1, border_radius=8)
                s = bf.render(lab, True, BLACK)
                self.sc.blit(s, (rect.centerx - s.get_width()//2, rect.centery - s.get_height()//2))
                self.key_rects.append((rect, lab))
                x += key_w + PAD
            y += key_h + PAD

        pygame.display.update()

    # --- main ---
    def run(self) -> str | None:
        self._debounce_on_entry()
        dbg(f"[NK] open: title={self.title!r} initial={self.value!r} mask={self.mask} dec={self.allow_decimal}")
        clock = pygame.time.Clock()
        down_key = None

        while True:
            self._pump()
            self._draw()

            for ev in pygame.event.get():
                if ev.type == pygame.QUIT:
                    return None

                if ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 1:
                    if time.time() < self._ignore_until: continue

                    # keypad keys
                    for i,(r,lab) in enumerate(self.key_rects):
                        if r.collidepoint(ev.pos):
                            down_key = i
                            break

                    # top buttons
                    if self.btn_cancel and self.btn_cancel.collidepoint(ev.pos):
                        dbg("[NK] CANCEL pressed")
                        return None
                    if self.btn_ok and self.btn_ok.collidepoint(ev.pos):
                        dbg(f"[NK] OK → {self.value!r}")
                        return self.value

                if ev.type == pygame.MOUSEBUTTONUP and ev.button == 1:
                    if down_key is not None:
                        r, lab = self.key_rects[down_key]
                        if r.collidepoint(ev.pos):
                            if lab.isdigit():
                                self.value += lab
                                dbg(f"[NK] +{lab} -> {self.value!r}")
                            elif lab == "." and self.allow_decimal and "." not in self.value:
                                self.value = self.value + ("" if self.value else "0") + "."
                                dbg(f"[NK] +. -> {self.value!r}")
                            elif lab == "BK":
                                self.value = self.value[:-1]
                                dbg(f"[NK] BACKSPACE -> {self.value!r}")
                            elif lab == "CL":
                                self.value = ""
                                dbg("[NK] CLEAR")
                            self._ignore_until = time.time() + 0.06
                        down_key = None

            clock.tick(30)
