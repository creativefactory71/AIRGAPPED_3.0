# wallet_manager.py
import re, pygame
from stores.settings import get_display_mode
from stores.wallet_store import list_wallets, get_active_wallet_name, set_active_wallet, ensure_wallet_exists, delete_wallet, rename_wallet
from ui.on_screen_keyboard import OnScreenKeyboard
from ui.pin_screen import PinScreen
from ui.theme_store import theme_color

WHITE=theme_color("bg"); BLACK=theme_color("fg"); OUT=theme_color("border")

class WalletManagerScreen:
    def __init__(self, screen, renderer, title_font, body_font):
        self.sc=screen; self.r=renderer; selftf=title_font; selfbf=body_font
        self.tf=title_font; self.bf=body_font
        self.sw,self.sh=screen.get_size()

    def run(self):
        while True:
            names = list_wallets()
            active = get_active_wallet_name()
            labels = [f"{'* ' if n==active else '  '}{n}" for n in names] + ["+ New Wallet", "Rename Wallet", "Delete Wallet (PIN)", "Back"]
            rects = self.r.draw_menu("Wallets (Manage)", labels, get_display_mode(self.r.settings))
            for ev in pygame.event.get():
                if ev.type==pygame.QUIT: return
                if ev.type==pygame.MOUSEBUTTONDOWN and ev.button==1:
                    nav = self.r.bottom_hit(ev.pos)
                    if nav == "back": return
                    if nav == "home": return
                    hit = self.r.hit_test(rects, ev.pos)
                    if hit is None: break
                    if hit < len(names):
                        set_active_wallet(names[hit]); self._toast(f"Active: {names[hit]}"); return
                    elif hit == len(names):
                        self._new_wallet_flow()
                    elif hit == len(names)+1:
                        self._rename_wallet_flow()
                    elif hit == len(names)+2:
                        self._delete_wallet_flow()
                    else:
                        return
            pygame.time.Clock().tick(30)

    def _new_wallet_flow(self):
        kb = OnScreenKeyboard(self.sc, "Wallet name")
        name = kb.run()
        if not name: return
        safe = re.sub(r"[^A-Za-z0-9_\-]", "_", name).strip("_-")[:24] or "wallet"
        ensure_wallet_exists(safe); set_active_wallet(safe)
        self._toast(f"Created & active: {safe}")

    def _rename_wallet_flow(self):
        names = list_wallets()
        if not names: return
        rects = self.r.draw_menu("Rename which wallet?", names+["Cancel"], get_display_mode(self.r.settings))
        target=None
        while target is None:
            for ev in pygame.event.get():
                if ev.type==pygame.QUIT: return
                if ev.type==pygame.MOUSEBUTTONDOWN and ev.button==1:
                    nav = self.r.bottom_hit(ev.pos)
                    if nav: return
                    hit=self.r.hit_test(rects, ev.pos)
                    if hit is None: break
                    if hit == len(names): return
                    target = names[hit]
        new = OnScreenKeyboard(self.sc, f"New name for {target}").run()
        if not new: return
        safe = re.sub(r"[^A-Za-z0-9_\-]", "_", new).strip("_-")[:24] or target
        ok = rename_wallet(target, safe)
        self._toast("Renamed" if ok else "Rename failed")

    def _delete_wallet_flow(self):
        names = list_wallets()
        if not names: return
        rects = self.r.draw_menu("Delete which wallet?", names+["Cancel"], get_display_mode(self.r.settings))
        target=None
        while target is None:
            for ev in pygame.event.get():
                if ev.type==pygame.QUIT: return
                if ev.type==pygame.MOUSEBUTTONDOWN and ev.button==1:
                    nav = self.r.bottom_hit(ev.pos)
                    if nav: return
                    hit=self.r.hit_test(rects, ev.pos)
                    if hit is None: break
                    if hit == len(names): return
                    target = names[hit]
        if not PinScreen(self.sc, self.tf, self.bf).gate():
            self._toast("PIN failed"); return
        if not self._confirm(f"Delete '{target}'?\nThis cannot be undone."):
            return
        ok = delete_wallet(target)
        self._toast("Deleted" if ok else "Delete failed")

    def _confirm(self, text):
        self.sc.fill(WHITE)
        self.sc.blit(self.tf.render("Confirm", True, BLACK),(8,6))
        y=28
        for line in text.split("\n"):
            self.sc.blit(self.bf.render(line, True, BLACK),(8,y)); y+=16
        yes=pygame.Rect(8,self.sh-26,60,20); no=pygame.Rect(self.sw-60,self.sh-26,52,20)
        for r,l in ((yes,"Yes"),(no,"No")):
            pygame.draw.rect(self.sc,(220,220,220),r,border_radius=6); pygame.draw.rect(self.sc,OUT,r,1,border_radius=6)
            self.sc.blit(self.bf.render(l, True, BLACK),(r.x+12, r.y+2))
        pygame.display.flip()
        while True:
            for ev in pygame.event.get():
                if ev.type==pygame.QUIT: return False
                if ev.type==pygame.MOUSEBUTTONDOWN and ev.button==1:
                    if yes.collidepoint(ev.pos): return True
                    if no.collidepoint(ev.pos): return False

    def _toast(self, text, ms=900):
        bar = pygame.Surface((self.sw, 20)); bar.fill(theme_color("card"))
        self.sc.blit(bar,(0,self.sh-20)); self.sc.blit(self.bf.render(text, True, theme_color("fg")),(6,self.sh-16))
        pygame.display.flip(); pygame.time.delay(ms)
