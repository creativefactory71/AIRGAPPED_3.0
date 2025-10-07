# on_screen_keyboard.py
# Android-style on-screen keyboard for 320x240, mouse-only.
# Backwards compatible with your existing calls:
#   OnScreenKeyboard(screen, "Prompt").run()
#   OnScreenKeyboard(screen, "").run()
# Extra (optional) params:
#   input_type: "text" (default) | "numeric" | "hex" | "bip39" | "password"
#   default_text: prefill the input
#
# Shift (one-shot) + Caps-lock (double-tap Shift), ABC/123 toggle, HEX layout,
# Backspace repeat (hold), key pop-up bubble, theme-aware.

import pygame, time, re
from ui.theme_store import theme_color, theme_radius

try:
    from mnemonic import Mnemonic
except Exception:
    Mnemonic = None

class OnScreenKeyboard:
    def __init__(self, screen, prompt_or_default="", default_text=None,
                 input_type="text", password=False, max_len=None):
        """
        screen: pygame Surface
        prompt_or_default: str (used as prompt/label)
        default_text: if None, defaults to ""; otherwise prefilled text
        input_type: "text" | "numeric" | "hex" | "bip39" | "password"
        password: if True, masks characters (overrides input_type display only)
        max_len: optional max characters
        """
        self.sc = screen
        self.sw, self.sh = screen.get_size()
        self.prompt = prompt_or_default or ""
        # allow old usage OnScreenKeyboard(screen, default_str) by interpreting long tokens as prompt;
        # we'll simply keep prompt as given and keep default empty unless explicitly passed
        self.text = ("" if default_text is None else str(default_text))
        self.input_type = input_type.lower() if input_type else "text"
        # if caller set input_type="password", respect; else explicit password flag
        self.is_password = (self.input_type == "password") or bool(password)
        self.max_len = max_len

        # theme
        self.bg = theme_color("bg")
        self.fg = theme_color("fg")
        self.card = theme_color("card")
        self.border = theme_color("border")
        self.accent = theme_color("accent")
        self.accent_fg = theme_color("accent_fg")
        self.radius = theme_radius()

        # fonts
        self.title_font = pygame.font.SysFont("dejavusans", 16, bold=True)
        self.body_font  = pygame.font.SysFont("dejavusans", 12)
        self.key_font   = pygame.font.SysFont("dejavusans", 14)

        # geometry
        self.top_h = 28            # prompt + input field area
        self.nav_h = 22            # reserved for global bottom bar in your app
        self.kb_h  = 148           # keyboard height
        self.area  = pygame.Rect(0, self.top_h, self.sw, self.sh - self.top_h - self.nav_h)

        # state
        self.mode = self._default_mode_for_type()   # 'abc' | 'sym' | 'hex' | 'num'
        self.shift_once = False
        self.caps_lock = False
        self.last_shift_t = 0.0
        self.cursor = len(self.text)
        self.keys = []   # list of dict: {"rect":..., "label":..., "type": "char"/"func", "value":...}
        self.pressed_key = None
        self.pressed_time = 0.0
        self.repeat_started = False

        # bip39 hints
        self.mnemo = Mnemonic("english") if (self.input_type=="bip39" and Mnemonic is not None) else None
        self.hints = []  # [(word, rect), ...]

    # ------------- public -------------
    def run(self):
        clock = pygame.time.Clock()
        while True:
            self._layout()
            self._render()
            for ev in pygame.event.get():
                if ev.type == pygame.QUIT:
                    return None
                if ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 1:
                    self._on_mouse_down(ev.pos)
                if ev.type == pygame.MOUSEBUTTONUP and ev.button == 1:
                    self._on_mouse_up(ev.pos)

            # handle backspace hold-repeat
            self._handle_repeat()
            clock.tick(60)

    # ------------- layout -------------
    def _default_mode_for_type(self):
        if self.input_type == "numeric":
            return "num"
        if self.input_type == "hex":
            return "hex"
        return "abc"

    def _layout(self):
        # Build key layout to fit 320x(240 - top - nav)
        kb = pygame.Rect(0, self.sh - self.kb_h - self.nav_h, self.sw, self.kb_h)
        self.kb_rect = kb
        self.keys = []

        if self.mode == "num":
            self._layout_numeric(kb)
            return
        if self.mode == "hex":
            self._layout_hex(kb)
            return
        if self.mode == "sym":
            self._layout_symbols(kb)
            return
        # default ABC
        self._layout_abc(kb)

    def _row(self, kb, y, labels, left_pad=6, gap=4):
        # evenly space based on number of labels
        cols = len(labels)
        total_gap = gap * (cols - 1)
        w = (kb.w - left_pad*2 - total_gap)
        key_w = max(20, int(w // cols))
        key_h = 26
        rects = []
        x = kb.x + left_pad
        for lab in labels:
            r = pygame.Rect(x, kb.y + y, key_w, key_h)
            rects.append((lab, r))
            x += key_w + gap
        return rects

    def _add_keys(self, row_rects):
        for lab, r in row_rects:
            if lab in ("Shift", "Caps", "Back", "Space", "ABC", "123", "OK", "Cancel", "0x", "HEX", "abc"):
                self.keys.append({"rect": r, "label": lab, "type": "func", "value": lab})
            else:
                self.keys.append({"rect": r, "label": lab, "type": "char", "value": lab})

    def _layout_abc(self, kb):
        # QWERTY rows
        r1 = self._row(kb, 4,  list("qwertyuiop"))
        r2 = self._row(kb, 34, list("asdfghjkl"))
        # third row includes shift + letters + backspace
        row3 = []
        # Shift wider
        s_rect = pygame.Rect(kb.x + 6, kb.y + 64, 38, 26)
        row3.append(("Shift", s_rect))
        # letters z..m
        mid_rects = self._row(kb, 64, list("zxcvbnm"), left_pad=50)
        row3 += mid_rects
        # backspace wide
        back_rect = pygame.Rect(kb.right - 6 - 38, kb.y + 64, 38, 26)
        row3.append(("Back", back_rect))
        # space row: ABC/123, space, ".", "@", OK
        left = pygame.Rect(kb.x + 6, kb.y + 94, 40, 26)
        space = pygame.Rect(kb.x + 50, kb.y + 94, kb.w - 50 - 6 - 88, 26)
        dot   = pygame.Rect(space.right + 4, kb.y + 94, 20, 26)
        atkey = pygame.Rect(dot.right + 4, kb.y + 94, 20, 26)
        ok    = pygame.Rect(kb.right - 6 - 40, kb.y + 94, 40, 26)
        self.keys += [{"rect": left, "label": "123", "type":"func","value":"123"}]
        self.keys += [{"rect": space, "label": "Space", "type":"func","value":"Space"}]
        self.keys += [{"rect": dot,   "label": ".", "type":"char","value":"."}]
        self.keys += [{"rect": atkey, "label": "@", "type":"char","value":"@"}]
        self.keys += [{"rect": ok,    "label": "OK", "type":"func","value":"OK"}]
        # add rows 1..3
        self._add_keys(r1); self._add_keys(r2)
        self._add_keys(row3)
        # Cancel button (top-left small)
        cancel = pygame.Rect(6, self.top_h-22, 56, 18)
        self.cancel_rect = cancel

    def _layout_symbols(self, kb):
        r1 = self._row(kb, 4,  list("1234567890"))
        r2 = self._row(kb, 34, list("@#$&*()'\"/"))
        r3 = self._row(kb, 64, list("!?-_+:;,."))
        # replace weird newline introduced by string literal
        lab_r3 = []
        for lab, r in r3:
            if lab == "\n": continue
            lab_r3.append((lab, r))
        self._add_keys(r1); self._add_keys(r2); self._add_keys(lab_r3)

        left = pygame.Rect(kb.x + 6, kb.y + 94, 40, 26)
        space = pygame.Rect(kb.x + 50, kb.y + 94, kb.w - 50 - 6 - 88, 26)
        slash = pygame.Rect(space.right + 4, kb.y + 94, 20, 26)
        dot   = pygame.Rect(slash.right + 4, kb.y + 94, 20, 26)
        ok    = pygame.Rect(kb.right - 6 - 40, kb.y + 94, 40, 26)
        self.keys += [{"rect": left, "label": "ABC", "type":"func","value":"ABC"}]
        self.keys += [{"rect": space, "label": "Space", "type":"func","value":"Space"}]
        self.keys += [{"rect": slash, "label": "/", "type":"char","value":"/"}]
        self.keys += [{"rect": dot,   "label": ".", "type":"char","value":"."}]
        self.keys += [{"rect": ok,    "label": "OK", "type":"func","value":"OK"}]
        cancel = pygame.Rect(6, self.top_h-22, 56, 18)
        self.cancel_rect = cancel

    def _layout_hex(self, kb):
        r1 = self._row(kb, 4, list("1234567890"))
        # a..f in center
        a2f = ["a","b","c","d","e","f"]
        r2 = self._row(kb, 34, a2f + [])
        self._add_keys(r1); self._add_keys(r2)
        # row3: 0x, case, back
        k0x = pygame.Rect(kb.x+6, kb.y+64, 36, 26)
        kcase = pygame.Rect(k0x.right+4, kb.y+64, 60, 26)
        kback = pygame.Rect(kb.right-6-60, kb.y+64, 60, 26)
        self.keys += [{"rect": k0x, "label":"0x", "type":"func","value":"0x"}]
        self.keys += [{"rect": kcase, "label":"A⇄a", "type":"func","value":"case"}]
        self.keys += [{"rect": kback, "label":"Back", "type":"func","value":"Back"}]
        # row4: ABC, space, OK
        left = pygame.Rect(kb.x+6, kb.y+94, 40, 26)
        space= pygame.Rect(kb.x+50, kb.y+94, kb.w - 50 - 6 - 84, 26)
        ok   = pygame.Rect(kb.right-6-40, kb.y+94, 40, 26)
        self.keys += [{"rect": left, "label":"ABC", "type":"func","value":"ABC"}]
        self.keys += [{"rect": space,"label":"Space","type":"func","value":"Space"}]
        self.keys += [{"rect": ok,   "label":"OK",   "type":"func","value":"OK"}]
        cancel = pygame.Rect(6, self.top_h-22, 56, 18)
        self.cancel_rect = cancel

    def _layout_numeric(self, kb):
        # phone-style numpad 3x4 + dot
        key_w = (kb.w - 6*2 - 4*2) // 3
        key_h = 28
        xs = [kb.x + 6 + c*(key_w + 4) for c in range(3)]
        ys = [kb.y + 4 + r*(key_h + 6) for r in range(4)]
        labels = [
            ("1", xs[0], ys[0]), ("2", xs[1], ys[0]), ("3", xs[2], ys[0]),
            ("4", xs[0], ys[1]), ("5", xs[1], ys[1]), ("6", xs[2], ys[1]),
            ("7", xs[0], ys[2]), ("8", xs[1], ys[2]), ("9", xs[2], ys[2]),
            (".", xs[0], ys[3]), ("0", xs[1], ys[3]), ("Back", xs[2], ys[3]),
        ]
        for lab, x, y in labels:
            r = pygame.Rect(x, y, key_w, key_h)
            t = "func" if lab=="Back" else "char"
            self.keys.append({"rect": r, "label": lab, "type": t, "value": lab})
        # bottom row: Cancel / OK
        ok = pygame.Rect(kb.right - 6 - 56, kb.bottom - 4 - 24, 56, 22)
        cancel = pygame.Rect(kb.x + 6, kb.bottom - 4 - 22, 56, 22)
        self.keys.append({"rect": ok, "label": "OK", "type":"func", "value":"OK"})
        self.cancel_rect = cancel

    # ------------- rendering -------------
    def _render(self):
        # background
        self.sc.fill(self.bg)

        # prompt + input box
        self.sc.blit(self.title_font.render(self.prompt or "Input", True, self.fg),(8, 6))
        in_rect = pygame.Rect(6, self.top_h-2, self.sw-12, 22)
        pygame.draw.rect(self.sc, self.card, in_rect, border_radius=self.radius)
        pygame.draw.rect(self.sc, self.border, in_rect, 1, border_radius=self.radius)

        # text display (masked if password)
        disp = self._masked(self.text) if self.is_password else self.text
        txt_surf = self.body_font.render(disp, True, self.fg)
        self.sc.blit(txt_surf, (in_rect.x+8, in_rect.y+3))

        # bip39 suggestion row
        if self.mnemo is not None:
            self._render_bip39_hints(in_rect)

        # keyboard keys
        for k in self.keys:
            self._draw_key(k)

        # cancel button
        if hasattr(self, "cancel_rect") and self.cancel_rect:
            pygame.draw.rect(self.sc, self.card, self.cancel_rect, border_radius=self.radius)
            pygame.draw.rect(self.sc, self.border, self.cancel_rect, 1, border_radius=self.radius)
            self.sc.blit(self.body_font.render("Cancel", True, self.fg),(self.cancel_rect.x+6, self.cancel_rect.y+1))

        # pressed popup
        if self.pressed_key:
            self._draw_popup(self.pressed_key)

        pygame.display.flip()

    def _draw_key(self, k):
        r = k["rect"]; lab = k["label"]
        base = self.card; br = self.border
        if self.pressed_key is k:
            base = self.accent
        pygame.draw.rect(self.sc, base, r, border_radius=self.radius)
        pygame.draw.rect(self.sc, br,   r, 1, border_radius=self.radius)
        # label (respect Shift/Caps for letters)
        show = lab
        if k["type"]=="char" and len(lab)==1 and lab.isalpha():
            show = self._apply_case(lab)
        if lab=="Shift" and (self.shift_once or self.caps_lock):
            # show highlighted shift
            pygame.draw.rect(self.sc, self.accent, r, 2, border_radius=self.radius)
        text = self.key_font.render(show, True, self.fg if base==self.card else self.accent_fg)
        self.sc.blit(text, (r.x + (r.w - text.get_width())//2, r.y + (r.h - text.get_height())//2))

    def _draw_popup(self, k):
        # small bubble above pressed key
        r = k["rect"]; lab = k["label"]
        pop = pygame.Rect(r.x, r.y - 20, r.w, 18)
        pygame.draw.rect(self.sc, self.card, pop, border_radius=self.radius)
        pygame.draw.rect(self.sc, self.border, pop, 1, border_radius=self.radius)
        show = lab
        if k["type"]=="char" and len(lab)==1 and lab.isalpha():
            show = self._apply_case(lab)
        text = self.body_font.render(show, True, self.fg)
        self.sc.blit(text, (pop.x + (pop.w - text.get_width())//2, pop.y + 1))

    def _render_bip39_hints(self, in_rect):
        # Show up to 4 completions for the current word prefix
        self.hints = []
        prefix = self._current_word_prefix()
        if not prefix:
            return
        words = [w for w in self.mnemo.wordlist if w.startswith(prefix)]
        words = words[:4]
        if not words:
            return
        # hint bar just below input box
        y = in_rect.bottom + 2
        x = 6
        for w in words:
            surf = self.body_font.render(w, True, self.fg)
            r = pygame.Rect(x, y, surf.get_width()+10, 16)
            pygame.draw.rect(self.sc, self.card, r, border_radius=self.radius)
            pygame.draw.rect(self.sc, self.border, r, 1, border_radius=self.radius)
            self.sc.blit(surf, (r.x+5, r.y+1))
            self.hints.append((w, r))
            x = r.right + 6

    # ------------- events -------------
    def _on_mouse_down(self, pos):
        # hints first
        for w, r in self.hints:
            if r.collidepoint(pos):
                self._accept_hint(w)
                return
        # keys
        for k in self.keys:
            if k["rect"].collidepoint(pos):
                self.pressed_key = k
                self.pressed_time = time.time()
                self.repeat_started = False
                self._activate(k, pressed=True)
                return
        # cancel
        if hasattr(self, "cancel_rect") and self.cancel_rect and self.cancel_rect.collidepoint(pos):
            self._finish(cancel=True)

    def _on_mouse_up(self, pos):
        self.pressed_key = None
        self.repeat_started = False

    def _handle_repeat(self):
        # backspace hold-repeat
        if not self.pressed_key: return
        k = self.pressed_key
        if k["type"]=="func" and k["value"]=="Back":
            now = time.time()
            if not self.repeat_started and now - self.pressed_time > 0.4:
                self.repeat_started = True
                self.pressed_time = now
            if self.repeat_started and now - self.pressed_time > 0.06:
                self.pressed_time = now
                self._backspace()

    def _activate(self, k, pressed=False):
        if k["type"]=="char":
            ch = k["value"]
            if len(ch)==1 and ch.isalpha():
                ch = self._apply_case(ch)
            # guard allowed characters based on input_type
            if self.input_type=="numeric" and ch not in "0123456789.":
                return
            if self.input_type=="hex" and ch.lower() not in list("0123456789abcdef"):
                return
            self._insert(ch)
            if self.shift_once and not self.caps_lock:
                self.shift_once = False
            return

        # func keys
        val = k["value"]
        if val == "OK":
            self._finish(cancel=False); return
        if val == "Cancel":
            self._finish(cancel=True); return
        if val == "Back":
            self._backspace(); return
        if val == "Space":
            # for hex/numeric, allow space? we'll allow for convenience except numeric
            if self.input_type != "numeric":
                self._insert(" ")
            return
        if val == "Shift":
            t = time.time()
            if t - self.last_shift_t < 0.4:
                # double-tap = caps lock toggle
                self.caps_lock = not self.caps_lock
                self.shift_once = False
            else:
                self.shift_once = not self.shift_once
            self.last_shift_t = t
            return
        if val == "ABC":
            self.mode = "abc"; return
        if val == "123":
            self.mode = "sym"; return
        if val == "case":  # hex case toggle
            self.caps_lock = not self.caps_lock
            return
        if val == "0x":
            # insert "0x" at cursor (avoid duplicate '0x0x')
            if self.text[self.cursor-2:self.cursor].lower() != "0x":
                self._insert("0x")
            return

    # ------------- editing helpers -------------
    def _insert(self, s):
        if self.max_len is not None and len(self.text) + len(s) > self.max_len:
            return
        self.text = self.text[:self.cursor] + s + self.text[self.cursor:]
        self.cursor += len(s)

    def _backspace(self):
        if self.cursor <= 0: return
        # delete last char (handles '0x' as two)
        if self.text[self.cursor-2:self.cursor].lower()=="0x":
            self.text = self.text[:self.cursor-2] + self.text[self.cursor:]
            self.cursor -= 2
            return
        self.text = self.text[:self.cursor-1] + self.text[self.cursor:]
        self.cursor -= 1

    def _finish(self, cancel=False):
        pygame.event.clear()
        if cancel:
            raise SystemExitReturn(None)
        else:
            raise SystemExitReturn(self.text)

    def _apply_case(self, ch):
        if self.caps_lock or self.shift_once:
            return ch.upper()
        return ch.lower()

    def _masked(self, s):
        return "•"*len(s)

    def _current_word_prefix(self):
        if not self.text: return ""
        # last token by whitespace
        toks = re.split(r"\s+", self.text)
        return toks[-1].lower()

    def _accept_hint(self, word):
        # replace current prefix with full word + space
        i = self.text.rfind(" ")
        if i < 0:
            self.text = word + " "
            self.cursor = len(self.text)
            return
        self.text = self.text[:i+1] + word + " "
        self.cursor = len(self.text)


class SystemExitReturn(Exception):
    """Internal control flow to leave run() with a value."""
    def __init__(self, value):
        super().__init__("return")
        self.value = value

# expose a helper wrapper so callers can do: OnScreenKeyboard(...).run()
def run_keyboard(kb: OnScreenKeyboard):
    try:
        kb.run()
    except SystemExitReturn as e:
        return e.value
    return None

# Monkey patch run() to unwrap SystemExitReturn neatly (for backward-compat)
_orig_run = OnScreenKeyboard.run
def _patched_run(self):
    try:
        return _orig_run(self)
    except SystemExitReturn as e:
        return e.value
OnScreenKeyboard.run = _patched_run
