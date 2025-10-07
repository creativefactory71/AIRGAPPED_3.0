# pin_screen.py
import pygame
from ui.numeric_keyboard import NumericKeyboard
from stores.pin_store import has_pin, set_pin, verify_pin, reset_pin
WHITE=(255,255,255); BLACK=(0,0,0); OUT=(0,0,0); BG=(238,238,238)

class PinScreen:
    """Boot PIN gate. If no PIN, asks to set one (twice)."""
    def __init__(self, screen, title_font, body_font):
        self.sc=screen; self.tf=title_font; self.bf=body_font
        self.sw,self.sh=screen.get_size()

    def gate(self) -> bool:
        if not has_pin():
            # set pin
            p1=NumericKeyboard(self.sc, "Set PIN", "").run()
            if not p1: return False
            p2=NumericKeyboard(self.sc, "Confirm PIN", "").run()
            if not p2 or p1!=p2:
                self._toast("PIN mismatch"); return False
            set_pin(p1); self._toast("PIN saved")
        # verify
        for _ in range(3):
            p=NumericKeyboard(self.sc, "Enter PIN", "").run()
            if p is None: return False
            if verify_pin(p): return True
            self._toast("Wrong PIN")
        return False

    def reset_pin_flow(self):
        # ask current, then new twice
        cur=NumericKeyboard(self.sc, "Current PIN", "").run()
        if cur is None: return
        if not verify_pin(cur):
            self._toast("Wrong PIN"); return
        p1=NumericKeyboard(self.sc, "New PIN", "").run()
        if p1 is None: return
        p2=NumericKeyboard(self.sc, "Confirm PIN", "").run()
        if p2 is None or p1!=p2:
            self._toast("PIN mismatch"); return
        reset_pin(); set_pin(p1); self._toast("PIN updated")

    def _toast(self, text, ms=900):
        overlay = pygame.Surface((self.sw, 22))
        overlay.fill((240,240,240))
        msg = self.bf.render(text, True, BLACK)
        self.sc.blit(overlay, (0, self.sh-22))
        self.sc.blit(msg, (6, self.sh-18))
        pygame.display.flip(); pygame.time.delay(ms)
