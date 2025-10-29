# on_screen_keyboard.py
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

SAFE_BOTTOM = 24            # height reserved for Back/Home/Opts bar
SAFE_MARGIN = 6
COLS = 6                    # fewer columns -> bigger keys
PAD = 4                     # inner padding between keys
INPUT_H = 28                # input box height

class OnScreenKeyboard:
    """
    Bigger-key on-screen keyboard (ASCII labels).
    API unchanged:
        OnScreenKeyboard(screen, title, initial, pump_input=None, mask=False).run() -> str | None

    Special keys:
      - Shift: 'Aa' (toggles to 'aA' when active)
      - Symbols toggle: '123' <-> 'ABC'
      - Backspace: 'BK'
      - Space: 'Space' (spans 2 columns)
      - Clear: 'CL'
      - Cancel: '<'
      - Done: '>'
    """
    def __init__(self, screen, title: str = "", initial: str = "",
                 pump_input=None, mask: bool = False):
        self.sc = screen
        self.title = title or "Input"
        self.value = initial or ""
        self.mask = mask
        self.pump_input = pump_input

        self.w, self.h = self.sc.get_size()
        self._down = None
        self._ignore_until = 0.0
        self.shift = False
        self.symbols = False

        self.key_rects = []  # list[(rect, label, span)]

    # ---------- lifecycle helpers ----------
    def _pump(self):
        if self.pump_input:
            self.pump_input()

    def _debounce_on_entry(self):
        pygame.event.clear([pygame.MOUSEBUTTONDOWN, pygame.MOUSEBUTTONUP, pygame.MOUSEMOTION])
        self._ignore_until = time.time() + 0.15

    # ---------- layouts ----------
    def _rows_letters(self):
        # 6 columns per row; last row balances to 6 with spans
        return [
            ["q","w","e","r","t","y"],
            ["u","i","o","p","a","s"],
            ["d","f","g","h","j","k"],
            ["l","z","x","c","v","b"],
            ["n","m",".",",","Aa","BK"],            # Shift, Backspace
            ["123","Space(2)","CL","<",">"],        # 1 + 2 + 1 + 1 + 1 = 6
        ]

    def _rows_symbols(self):
        return [
            ["1","2","3","4","5","6"],
            ["7","8","9","0","-","_"],
            ["@","#","$","%","&","*"],
            [".",",","?","!","'",";"],
            ["/","(",")",":","Aa","BK"],           # keep Shift/Backspace here too
            ["ABC","Space(2)","CL","<",">"],
        ]

    def _key_rows(self):
        return self._rows_symbols() if self.symbols else self._rows_letters()

    # ---------- drawing ----------
    def _fit_label(self, base_font, text, max_w):
        """Auto-shrink label to fit if needed."""
        size = base_font.get_height()
        font = base_font
        srf = font.render(text, True, BLACK)
        while srf.get_width() > max_w and size > 10:
            size -= 1
            try: font = pygame.font.SysFont("Verdana", size)
            except Exception: font = pygame.font.Font(None, size)
            srf = font.render(text, True, BLACK)
        return srf

    def _draw(self):
        self.sc.fill(WHITE)
        fg = BLACK

        # Fonts
        try:
            tf = pygame.font.SysFont("Verdana", 18, bold=True)
            bf = pygame.font.SysFont("Verdana", 16)
            sf = pygame.font.SysFont("Verdana", 14)
        except Exception:
            tf = pygame.font.Font(None, 18)
            bf = pygame.font.Font(None, 16)
            sf = pygame.font.Font(None, 14)

        # Title
        self.sc.blit(tf.render(self.title, True, fg), (8, 6))

        # Input box
        input_rect = pygame.Rect(8, 8 + 18, self.w-16, INPUT_H)
        pygame.draw.rect(self.sc, GREY, input_rect, border_radius=8)
        pygame.draw.rect(self.sc, OUT, input_rect, 1, border_radius=8)
        disp = ("*"*len(self.value)) if self.mask else self.value
        # trim visually if too long
        trimmed = disp
        srf = bf.render(trimmed, True, fg)
        while srf.get_width() > input_rect.width-12 and len(trimmed) > 0:
            trimmed = trimmed[1:]
            srf = bf.render(trimmed, True, fg)
        self.sc.blit(srf, (input_rect.x+6, input_rect.y+(INPUT_H//2 - srf.get_height()//2)))

        # Keyboard grid area (leave safe bottom for nav bar)
        top = input_rect.bottom + SAFE_MARGIN
        bottom = self.h - SAFE_BOTTOM - SAFE_MARGIN
        kh = max(90, bottom - top)
        rows = self._key_rows()
        n_rows = len(rows)

        # metrics
        row_h = (kh - (n_rows+1)*PAD) // n_rows
        row_h = max(row_h, 22)
        col_w = (self.w - (COLS+1)*PAD) // COLS

        self.key_rects = []
        y = top + PAD
        for row in rows:
            x = PAD
            col_used = 0
            for spec in row:
                span = 1
                label = spec
                if spec.endswith("(2)"):
                    label = spec[:-3]
                    span = 2
                width = span*col_w + (span-1)*PAD
                r = pygame.Rect(x, y, width, row_h)

                # draw
                pygame.draw.rect(self.sc, GREY, r, border_radius=8)
                pygame.draw.rect(self.sc, OUT, r, 1, border_radius=8)

                # visible label (Shift shows Aa / aA)
                vis = label
                if label == "Aa":
                    vis = "aA" if self.shift else "Aa"

                srf = self._fit_label(bf, vis, max_w=r.width-8)
                self.sc.blit(srf, (r.centerx - srf.get_width()//2,
                                   r.centery - srf.get_height()//2))

                self.key_rects.append((r, label, span))
                x += width + PAD
                col_used += span

            # spacer if row shorter than COLS (should not occur with these rows)
            if col_used < COLS:
                spacer_w = (COLS-col_used)*col_w + (COLS-col_used-1)*PAD
                pygame.draw.rect(self.sc, WHITE, pygame.Rect(x, y, spacer_w, row_h))
            y += row_h + PAD

        pygame.display.update()

    # ---------- key handling ----------
    def _emit_char(self, label: str):
        # Normal characters
        if len(label) == 1 and label.isprintable() and label not in {"<", ">", }:
            ch = label.upper() if (self.shift and label.isalpha()) else (
                 label.lower() if (not self.shift and label.isalpha()) else label)
            self.value += ch
            dbg(f"[OSK] char: {ch!r} → {self.value!r}")
            return

        # Special actions
        if label == "Aa":          # Shift toggle
            self.shift = not self.shift
            dbg(f"[OSK] shift={self.shift}")
            return
        if label == "123":         # switch to symbols
            self.symbols = True
            dbg("[OSK] symbols=True")
            return
        if label == "ABC":         # back to letters
            self.symbols = False
            dbg("[OSK] symbols=False")
            return
        if label == "Space":       # space (spans 2 cols)
            self.value += " "
            dbg(f"[OSK] space → {self.value!r}")
            return
        if label == "BK":          # backspace
            self.value = self.value[:-1]
            dbg(f"[OSK] backspace → {self.value!r}")
            return
        if label == "CL":          # clear
            self.value = ""
            dbg("[OSK] cleared")
            return
        # '<' (Cancel) and '>' (Done) handled in main loop

    # ---------- main ----------
    def run(self) -> str | None:
        self._debounce_on_entry()
        dbg(f"[OSK] open: title={self.title!r} initial={self.value!r}")
        clock = pygame.time.Clock()
        down_idx = None

        while True:
            self._pump()
            self._draw()

            for ev in pygame.event.get():
                if ev.type == pygame.QUIT:
                    return None
                if ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 1:
                    if time.time() < self._ignore_until: continue
                    for i, (r, lab, span) in enumerate(self.key_rects):
                        if r.collidepoint(ev.pos):
                            down_idx = i
                            break
                if ev.type == pygame.MOUSEBUTTONUP and ev.button == 1:
                    up_idx = None
                    for i, (r, lab, span) in enumerate(self.key_rects):
                        if r.collidepoint(ev.pos):
                            up_idx = i
                            break
                    if down_idx is not None and up_idx == down_idx:
                        _, label, _ = self.key_rects[up_idx]
                        if label == "<":     # Cancel
                            dbg("[OSK] cancel")
                            return None
                        if label == ">":     # Done
                            dbg(f"[OSK] done → {self.value!r}")
                            return self.value
                        self._emit_char(label)
                        self._ignore_until = time.time() + 0.06
                    down_idx = None

            clock.tick(30)
