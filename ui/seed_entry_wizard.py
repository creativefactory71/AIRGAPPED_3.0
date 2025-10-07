# seed_entry_wizard.py
import pygame, re
from mnemonic import Mnemonic
from ui.on_screen_keyboard import OnScreenKeyboard

WHITE=(255,255,255); BLACK=(0,0,0); OUT=(0,0,0); BG=(238,238,238)

class SeedEntryWizard:
    def __init__(self, screen, renderer, title_font, body_font):
        self.sc=screen; self.r=renderer; self.tf=title_font; self.bf=body_font
        self.sw,self.sh=screen.get_size()
        self.mnemo = Mnemonic("english")

    def run(self):
        # choose 12 / 24
        from stores.settings import get_display_mode
        items = ["12 words", "24 words", "Cancel"]
        rects = self.r.draw_menu("Restore (numbered)", items, get_display_mode(self.r.settings))
        words_n = None
        while words_n is None:
            for ev in pygame.event.get():
                if ev.type==pygame.QUIT: return None
                if ev.type==pygame.MOUSEBUTTONDOWN and ev.button==1:
                    hit = self.r.hit_test(rects, ev.pos)
                    if hit is None: break
                    if items[hit]=="Cancel": return None
                    words_n = 12 if items[hit].startswith("12") else 24

        # collect words
        words = [""]*words_n
        i = 0
        while i < words_n:
            # draw numbered grid w/ progress
            self._draw_progress(words, i)
            # open keyboard for this word
            entered = OnScreenKeyboard(self.sc, f"Word {i+1}/{words_n}").run()
            if entered is None: return None
            w = re.sub(r"[^a-z]", "", entered.lower())
            if not w:
                self._toast("Empty word"); continue
            if w not in self.mnemo.wordlist:
                self._toast("Not in BIP-39 wordlist"); continue
            words[i] = w
            i += 1

        mnemonic = " ".join(words)
        # checksum validate
        if not self.mnemo.check(mnemonic):
            # show error + options
            if not self._checksum_failed_dialog():
                return None
            # if user chose "Edit last", step back a few words
            i = max(0, words_n-3)
            while i < words_n:
                self._draw_progress(words, i)
                edited = OnScreenKeyboard(self.sc, f"Edit word {i+1}").run()
                if edited is None: return None
                w = re.sub(r"[^a-z]", "", edited.lower())
                if w not in self.mnemo.wordlist:
                    self._toast("Not in BIP-39 wordlist"); continue
                words[i] = w
                i += 1
            mnemonic = " ".join(words)
            if not self.mnemo.check(mnemonic):
                self._toast("Checksum still invalid"); return None
        return mnemonic

    def _draw_progress(self, words, focus_idx):
        self.sc.fill(WHITE)
        self.sc.blit(self.tf.render("Restore (numbered)", True, BLACK),(8,6))
        y=28
        # numbered list (compact for 320x240)
        for idx,w in enumerate(words):
            prefix = f"{idx+1:02d}: "
            txt = (w or "_____")
            color = (20,20,20) if w else (120,120,120)
            if idx==focus_idx:
                # highlight row
                row = pygame.Rect(6,y-2,self.sw-12,16)
                pygame.draw.rect(self.sc, (235,245,255), row, border_radius=4)
                pygame.draw.rect(self.sc, OUT, row, 1, border_radius=4)
            self.sc.blit(self.bf.render(prefix+txt, True, color),(10,y))
            y+=14
            if y> self.sh-30: break
        # hint
        self.sc.blit(self.bf.render("Tap to type the next word", True, BLACK),(8,self.sh-18))
        pygame.display.flip()

    def _checksum_failed_dialog(self):
        # returns True to edit last words, False to cancel
        self.sc.fill(WHITE)
        self.sc.blit(self.tf.render("Checksum invalid", True, BLACK),(8,6))
        self.sc.blit(self.bf.render("Words look OK, but checksum failed.", True, BLACK),(8,28))
        self.sc.blit(self.bf.render("Edit last few words?", True, BLACK),(8,44))
        btn_yes = pygame.Rect(8, self.sh-26, 80, 20)
        btn_no  = pygame.Rect(self.sw-60, self.sh-26, 52, 20)
        for r,l in ((btn_yes,"Edit"),(btn_no,"Cancel")):
            pygame.draw.rect(self.sc,(220,220,220),r,border_radius=6); pygame.draw.rect(self.sc,OUT,r,1,border_radius=6)
            self.sc.blit(self.bf.render(l, True, BLACK),(r.x+8, r.y+2))
        pygame.display.flip()
        while True:
            for ev in pygame.event.get():
                if ev.type==pygame.QUIT: return False
                if ev.type==pygame.MOUSEBUTTONDOWN and ev.button==1:
                    if btn_yes.collidepoint(ev.pos): return True
                    if btn_no.collidepoint(ev.pos): return False

    def _toast(self, text, ms=900):
        overlay=pygame.Surface((self.sw, 22)); overlay.fill((240,240,240))
        msg=self.bf.render(text, True, BLACK)
        self.sc.blit(overlay,(0,self.sh-22)); self.sc.blit(msg,(6,self.sh-18))
        pygame.display.flip(); pygame.time.delay(ms)
