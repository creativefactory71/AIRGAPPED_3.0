# add_wallet_screen.py
import re, pygame
from stores.wallet_store import ensure_wallet_exists, set_active_wallet
from ui.on_screen_keyboard import OnScreenKeyboard
from ui.wallet_screens import WalletScreens
from stores.settings import get_display_mode

class AddWalletScreen:
    def __init__(self, screen, renderer, engine, title_font, body_font):
        self.sc=screen; self.r=renderer; self.engine=engine
        self.tf=title_font; self.bf=body_font
        self.sw,self.sh=screen.get_size()

    def run(self):
        # ask name
        name = OnScreenKeyboard(self.sc, "Wallet name").run()
        if not name: return
        safe = re.sub(r"[^A-Za-z0-9_\-]", "_", name).strip("_-")[:24] or "wallet"
        ensure_wallet_exists(safe); set_active_wallet(safe)

        items = ["Create Wallet", "Restore Wallet", "Back"]
        rects = self.r.draw_menu(f"Add Wallet: {safe}", items, get_display_mode(self.r.settings))
        while True:
            for ev in pygame.event.get():
                if ev.type==pygame.QUIT: return
                if ev.type==pygame.MOUSEBUTTONDOWN and ev.button==1:
                    nav = self.r.bottom_hit(ev.pos)
                    if nav == "back": return
                    if nav == "home": return
                    hit = self.r.hit_test(rects, ev.pos)
                    if hit is None: break
                    choice = items[hit]
                    if choice == "Back": return
                    ws = WalletScreens(self.sc, self.r, self.engine)
                    if choice == "Create Wallet":
                        ws.create_wallet_flow()
                    elif choice == "Restore Wallet":
                        ws.restore_wallet_flow()
                    return
            pygame.time.Clock().tick(30)
