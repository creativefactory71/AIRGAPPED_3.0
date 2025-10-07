# main_wallet.py
import sys, pygame
from ui.ui_modes_demo import SimpleApp
from crypto.wallet_engine import WalletEngine
from ui.wallet_screens import WalletScreens
from ui.on_screen_keyboard import OnScreenKeyboard
from ui.network_forms import AddNetworkForm
from ui.networks_screen import NetworksScreen
from ui.pin_screen import PinScreen
from flows.send_flow import SendFlow
from flows.receive_flow import ReceiveFlow
from ui.info_screen import InfoScreen
from stores.file_ops import wipe_files
from stores.wallet_store import load_wallet
from ui.wallet_manager import WalletManagerScreen
from ui.add_wallet_screen import AddWalletScreen
from ui.ui_mode_picker import UiModePicker
from ui.theme_picker import ThemePicker
from ui.theme_store import theme_color

class WalletApp(SimpleApp):
    def __init__(self):
        super().__init__()
        self.engine = WalletEngine()
        self.wscreens = WalletScreens(self.screen, self.renderer, self.engine)
        self.title_font = pygame.font.SysFont("dejavusans", 16, bold=True)
        self.body_font  = pygame.font.SysFont("dejavusans", 12)

        self.state = "PIN"

        self.first_run_items = ["Create Wallet", "Restore Wallet", "Settings", "Exit"]
        self.menu_items = ["Send", "Receive", "Add Custom Network", "Settings", "Info", "Delete"]

    def run(self):
        while True:
            if self.state == "PIN":
                if not PinScreen(self.screen, self.title_font, self.body_font).gate():
                    pygame.quit(); sys.exit()
                w=load_wallet(); self.state = "MENU" if w.get("seed_phrase") else "FIRST_RUN"

            elif self.state == "FIRST_RUN":
                self._loop_first_run()

            elif self.state == "MENU":
                self._loop_menu()

            elif self.state == "SETTINGS":
                self._loop_settings_menu()

            elif self.state == "CREATE":
                self.wscreens.create_wallet_flow(); self.state="MENU"

            elif self.state == "RESTORE":
                self.wscreens.restore_wallet_flow(OnScreenKeyboard); self.state="MENU"

            elif self.state == "NETWORKS":
                ns = NetworksScreen(self.screen, self.renderer, self.engine,
                                    self.title_font, self.body_font,
                                    last_seed_getter=lambda: self.wscreens.last_seed)
                ns.run(); self.state="MENU"

            elif self.state == "ADD_NET":
                AddNetworkForm(self.screen, self.title_font, self.body_font).run(); self.state="MENU"

            elif self.state == "SEND":
                SendFlow(self.screen, self.renderer, self.engine, self.title_font, self.body_font).run(); self.state="MENU"

            elif self.state == "RECEIVE":
                ReceiveFlow(self.screen, self.renderer, self.title_font, self.body_font).run(); self.state="MENU"

            elif self.state == "INFO":
                InfoScreen(self.screen, self.title_font, self.body_font).run(); self.state="MENU"

            elif self.state == "WALLET_MGR":
                WalletManagerScreen(self.screen, self.renderer, self.title_font, self.body_font).run(); self.state="MENU"

            elif self.state == "ADD_WALLET":
                AddWalletScreen(self.screen, self.renderer, self.engine, self.title_font, self.body_font).run(); self.state="MENU"

            elif self.state == "UI_MODE":
                UiModePicker(self.screen, self.renderer, self.title_font, self.body_font).run(); self.state="MENU"

            elif self.state == "THEME":
                ThemePicker(self.screen, self.renderer, self.title_font, self.body_font).run(); self.state="MENU"

            elif self.state == "DELETE":
                self._confirm_delete(); self.state="PIN"

            else:
                pygame.quit(); sys.exit()

    def _loop_first_run(self):
        from stores.settings import get_display_mode
        rects = self.renderer.draw_menu("Wallet: Create / Restore", self.first_run_items, get_display_mode(self.renderer.settings))
        for event in pygame.event.get():
            if event.type == pygame.QUIT: pygame.quit(); sys.exit()
            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                hit = self.renderer.hit_test(rects, event.pos)
                if hit is None: return
                label = self.first_run_items[hit]
                if label == "Create Wallet": self.state="CREATE"
                elif label == "Restore Wallet": self.state="RESTORE"
                elif label == "Settings": self.state="SETTINGS"
                elif label == "Exit": pygame.quit(); sys.exit()

    def _loop_menu(self):
        from stores.settings import get_display_mode
        rects = self.renderer.draw_menu("Menu", self.menu_items, get_display_mode(self.renderer.settings))
        for event in pygame.event.get():
            if event.type == pygame.QUIT: pygame.quit(); sys.exit()
            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                hit = self.renderer.hit_test(rects, event.pos)
                if hit is None: return
                label = self.menu_items[hit]
                self.state = {
                    "Send": "SEND", "Receive": "RECEIVE", "Add Custom Network": "ADD_NET",
                    "Settings": "SETTINGS", "Info": "INFO", "Delete": "DELETE"
                }[label]

    def _loop_settings_menu(self):
        from stores.settings import get_display_mode
        items = ["Add Wallet", "Wallets (Manage)", "UI Mode", "Theme", "Back"]
        rects = self.renderer.draw_menu("Settings", items, get_display_mode(self.renderer.settings))
        while True:
            for event in pygame.event.get():
                if event.type == pygame.QUIT: pygame.quit(); sys.exit()
                elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                    hit = self.renderer.hit_test(rects, event.pos)
                    if hit is None: return
                    label = items[hit]
                    if label == "Add Wallet": self.state = "ADD_WALLET"; return
                    elif label == "Wallets (Manage)": self.state = "WALLET_MGR"; return
                    elif label == "UI Mode": self.state = "UI_MODE"; return
                    elif label == "Theme": self.state = "THEME"; return
                    elif label == "Back":
                        self.state = "MENU"; return

    def _confirm_delete(self):
        sw,sh=self.screen.get_size()
        self.screen.fill(theme_color("bg"))
        self.screen.blit(self.title_font.render("Reset Device", True, theme_color("fg")), (8,6))
        y=34
        for ln in ["This will delete wallet.json and pin.json.", "Are you sure?"]:
            self.screen.blit(self.body_font.render(ln, True, theme_color("fg")),(8,y)); y+=16
        yes=pygame.Rect(8, sh-26, 52, 20); no=pygame.Rect(sw-60, sh-26, 52, 20)
        for r,l in ((yes,"Yes"),(no,"No")):
            pygame.draw.rect(self.screen,(220,220,220),r,border_radius=6); pygame.draw.rect(self.screen,theme_color("border"),r,1,border_radius=6)
            self.screen.blit(self.body_font.render(l, True, theme_color("fg")),(r.x+12, r.y+2))
        pygame.display.flip()
        while True:
            for ev in pygame.event.get():
                if ev.type==pygame.QUIT: return
                if ev.type==pygame.MOUSEBUTTONDOWN and ev.button==1:
                    if yes.collidepoint(ev.pos):
                        wipe_files()
                        return
                    if no.collidepoint(ev.pos):
                        return

if __name__ == "__main__":
    WalletApp().run()
