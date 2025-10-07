# word_check.py
import pygame
import random
import re

from ui.on_screen_keyboard import OnScreenKeyboard

WHITE=(255,255,255); BLACK=(0,0,0); OUT=(0,0,0); BG=(238,238,238)

class WordCheck:
    """
    Post-create seed confirmation:
      - Shows an instruction screen first (no keyboard yet)
      - Randomly selects 6 unique word positions from the mnemonic
      - For each, asks user to enter exactly that word via on-screen keyboard
      - Returns True if all 6 answers are correct, else False
    """
    def __init__(self, screen, title_font, body_font):
        self.sc=screen; self.tf=title_font; self.bf=body_font
        self.sw,self.sh=screen.get_size()

    def run(self, mnemonic: str) -> bool:
        words = [w.strip().lower() for w in mnemonic.split()]
        n = len(words)
        if n not in (12, 24):
            # Fallback: just pass; we don't know how many words to sample
            return True

        # 1) Instruction screen (avoid immediate keyboard popup)
        if not self._intro_screen(n):
            return False

        # 2) Pick 6 unique positions and sort for clarity
        idxs = sorted(random.sample(range(n), 6))

        # 3) Ask each required word with a clear prompt; keyboard opens only when user clicks "Enter Word"
        for i, idx in enumerate(idxs, start=1):
            ok = self._ask_word(i, 6, idx+1, words[idx])
            if not ok:
                return False

        # All passed
        self._toast("Recovery check passed")
        return True

    # ---------- UI helpers ----------
    def _intro_screen(self, n_words: int) -> bool:
        """Returns True to start test, False to cancel."""
        while True:
            self.sc.fill(WHITE)
            self.sc.blit(self.tf.render("Recovery Check", True, BLACK),(8,6))
            y=30
            lines = [
                f"You will be asked for 6 random words",
                f"from your {n_words}-word recovery phrase.",
                "Have your written backup ready.",
                "",
                "Click Start when ready."
            ]
            for ln in lines:
                self.sc.blit(self.bf.render(ln, True, BLACK),(10,y)); y+=16

            btn_start=pygame.Rect(8, self.sh-26, 70, 20)
            btn_cancel=pygame.Rect(self.sw-70, self.sh-26, 62, 20)
            for r,l in ((btn_start,"Start"), (btn_cancel,"Cancel")):
                pygame.draw.rect(self.sc,(220,220,220),r,border_radius=6)
                pygame.draw.rect(self.sc,OUT,r,1,border_radius=6)
                self.sc.blit(self.bf.render(l, True, BLACK),(r.x+10, r.y+2))
            pygame.display.flip()

            for ev in pygame.event.get():
                if ev.type==pygame.QUIT: return False
                if ev.type==pygame.MOUSEBUTTONDOWN and ev.button==1:
                    if btn_start.collidepoint(ev.pos): return True
                    if btn_cancel.collidepoint(ev.pos): return False

    def _ask_word(self, step_i: int, step_total: int, human_index: int, expected_word: str) -> bool:
        """Ask for word #human_index; returns True on correct entry, else False."""
        entered_word = None
        while True:
            self.sc.fill(WHITE)
            title = f"Test {step_i}/{step_total}"
            self.sc.blit(self.tf.render(title, True, BLACK),(8,6))
            y=30
            self.sc.blit(self.bf.render(f"Enter word #{human_index}", True, BLACK),(10,y)); y+=18

            # slot box
            slot = pygame.Rect(8, y, self.sw-16, 32)
            pygame.draw.rect(self.sc, BG, slot, border_radius=6)
            pygame.draw.rect(self.sc, OUT, slot, 1, border_radius=6)
            preview = (entered_word or "__________")
            self.sc.blit(self.bf.render(preview, True, (0,0,0)), (slot.x+8, slot.y+8))

            # buttons
            btn_enter=pygame.Rect(8, self.sh-26, 90, 20)
            btn_back =pygame.Rect(self.sw-60, self.sh-26, 52, 20)
            for r,l in ((btn_enter,"Enter Word"), (btn_back,"Cancel")):
                pygame.draw.rect(self.sc,(220,220,220),r,border_radius=6)
                pygame.draw.rect(self.sc,OUT,r,1,border_radius=6)
                self.sc.blit(self.bf.render(l, True, BLACK),(r.x+8, r.y+2))
            pygame.display.flip()

            for ev in pygame.event.get():
                if ev.type==pygame.QUIT: return False
                if ev.type==pygame.MOUSEBUTTONDOWN and ev.button==1:
                    if btn_back.collidepoint(ev.pos):
                        return False
                    if btn_enter.collidepoint(ev.pos):
                        # Open keyboard only on demand (prevents instant popup)
                        typed = OnScreenKeyboard(self.sc, f"Word #{human_index}").run()
                        if typed is None:
                            # user closed keyboard → stay on screen
                            continue
                        # normalize typed word
                        w = re.sub(r"[^a-z]", "", typed.lower())
                        entered_word = w
                        # validate
                        if w == expected_word:
                            self._toast("OK")
                            return True
                        else:
                            self._alert(f"Incorrect word for #{human_index}")
                            # let user retry; do not exit immediately

    def _alert(self, msg):
        self.sc.fill(WHITE)
        self.sc.blit(self.tf.render("Notice", True, BLACK),(8,6))
        y=34
        for ln in str(msg).split("\n"):
            self.sc.blit(self.bf.render(ln, True, BLACK),(8,y)); y+=16
        btn=pygame.Rect(self.sw-60, self.sh-26, 52, 20)
        pygame.draw.rect(self.sc,(220,220,220),btn,border_radius=6)
        pygame.draw.rect(self.sc,OUT,btn,1,border_radius=6)
        self.sc.blit(self.bf.render("OK", True, BLACK),(btn.x+14, btn.y+2))
        pygame.display.flip()
        while True:
            for ev in pygame.event.get():
                if ev.type==pygame.QUIT: return
                if ev.type==pygame.MOUSEBUTTONDOWN and ev.button==1 and btn.collidepoint(ev.pos):
                    return

    def _toast(self, text, ms=800):
        overlay=pygame.Surface((self.sw, 20)); overlay.fill((240,240,240))
        self.sc.blit(overlay,(0,self.sh-20))
        self.sc.blit(self.bf.render(text, True, BLACK),(6,self.sh-16))
        pygame.display.flip(); pygame.time.delay(ms)
