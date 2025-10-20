# ui/security_manager.py
from __future__ import annotations
import time, random, pygame

from security.pin_store import pin_present, verify_pin, set_pin, change_pin, clear_pin
from stores.wallet_store import load_active_wallet
from ui.on_screen_keyboard import OnScreenKeyboard
from ui.numeric_keyboard import NumericKeyboard

WHITE=(255,255,255); BLACK=(0,0,0); OUT=(0,0,0)

class SecurityManager:
    """Settings → PIN & Security (PC + Pi with touch pump)."""
    def __init__(self, screen, renderer, title_font, body_font, small_font, toast_cb, pump_input=None):
        self.sc=screen; self.r=renderer; self.tf=title_font; self.bf=body_font; self.sf=small_font
        self.w,self.h = screen.get_size()
        self.toast = toast_cb
        self.pump_input = pump_input
        self._down=None; self._ignore_until=0.0

    # ---- helpers ----
    def _pump(self):
        if self.pump_input: self.pump_input()

    def _debounce(self):
        pygame.event.clear([pygame.MOUSEBUTTONDOWN, pygame.MOUSEBUTTONUP, pygame.MOUSEMOTION])
        self._ignore_until = time.time() + 0.15

    def _nk(self, title, initial="", mask=False):
        try:
            return NumericKeyboard(self.sc, title, initial, pump_input=self.pump_input,
                                   allow_decimal=False, mask=mask).run()
        except TypeError:
            # older class signature
            return NumericKeyboard(self.sc, title, initial).run()

    def _osk(self, title, initial=""):
        try:
            return OnScreenKeyboard(self.sc, title, initial, pump_input=self.pump_input).run()
        except TypeError:
            return OnScreenKeyboard(self.sc, title, initial).run()

    def _draw_menu(self):
        items = []
        if pin_present():
            items = ["Change PIN", "Reset PIN (seed auth)", "Disable PIN", "Back"]
        else:
            items = ["Set PIN", "Back"]
        rects = self.r.draw_menu("PIN & Security", items, self.r.settings.get("ui_mode","grid"))
        pygame.display.update()
        return items, rects

    def run(self):
        self._debounce()
        while True:
            self._pump()
            items, rects = self._draw_menu()
            for ev in pygame.event.get():
                if ev.type==pygame.QUIT: return
                if ev.type==pygame.MOUSEBUTTONDOWN and ev.button==1:
                    if time.time() < self._ignore_until: continue
                    self._down = self.r.hit_test(rects, ev.pos)
                if ev.type==pygame.MOUSEBUTTONUP and ev.button==1:
                    up = self.r.hit_test(rects, ev.pos)
                    if self._down is not None and up == self._down:
                        lab = items[up].lower()
                        if lab.endswith("back"): return
                        if lab == "set pin":
                            self._set_pin_flow()
                        elif lab == "change pin":
                            self._change_pin_flow()
                        elif lab.startswith("reset pin"):
                            self._reset_pin_seed_flow()
                        elif lab == "disable pin":
                            self._disable_pin_flow()
                    self._down=None
            pygame.time.Clock().tick(30)

    # ---- flows ----
    def _set_pin_flow(self):
        p1 = self._nk("New PIN (4-10 digits)", "", mask=True)
        if not p1 or not (4 <= len(p1) <= 10) or not p1.isdigit():
            self.toast("Invalid PIN"); return
        p2 = self._nk("Confirm PIN", "", mask=True)
        if p1 != p2:
            self.toast("PIN mismatch"); return
        set_pin(p1); self.toast("PIN set")

    def _change_pin_flow(self):
        cur = self._nk("Current PIN", "", mask=True)
        if not cur or not verify_pin(cur):
            self.toast("Wrong PIN"); return
        self._set_pin_flow()

    def _reset_pin_seed_flow(self):
        # Try 3-word quiz from active wallet seed
        w = load_active_wallet()
        words = []
        if w and w.get("seed_phrase"):
            words = [x.strip().lower() for x in w["seed_phrase"].split() if x.strip()]
        if words and len(words) in (12,24):
            idxs = sorted(random.sample(range(len(words)), k=3))
            for i in idxs:
                ans = (self._osk(f"Seed word #{i+1}", "") or "").strip().lower()
                if ans != words[i]:
                    self.toast("Seed check failed"); return
        else:
            # Fallback: ask full seed
            phrase = (self._osk("Enter full seed (12/24 words)", "") or "").strip().lower()
            entered = [x for x in phrase.split() if x]
            if len(entered) not in (12,24):
                self.toast("Need 12 or 24 words"); return
            if words and entered != words:
                self.toast("Seed does not match active wallet"); return
            # if no wallet seed was stored, we just accept a 12/24 entry

        # Set new PIN
        self._set_pin_flow()

    def _disable_pin_flow(self):
        # Require proof: either current PIN or seed auth
        if pin_present():
            cur = self._nk("Current PIN", "", mask=True)
            if cur and verify_pin(cur):
                clear_pin(); self.toast("PIN disabled"); return
        # fallback to seed check
        self._reset_pin_seed_flow()
        # if _reset_pin_seed_flow returns without setting, it failed;
        # but if it succeeded, a new PIN is set; user can disable again with current PIN

