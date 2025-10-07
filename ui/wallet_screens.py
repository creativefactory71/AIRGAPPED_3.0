# wallet_screens.py
import pygame, qrcode
from PIL import Image
from stores.settings import get_display_mode
from stores.network_store import list_networks
from stores.wallet_store import upsert_wallet
from ui.word_check import WordCheck
from ui.seed_entry_wizard import SeedEntryWizard

WHITE=(255,255,255); BLACK=(0,0,0); OUT=(0,0,0); BG=(238,238,238)

def pil_to_surface(img: Image.Image):
    mode, size, data = img.mode, img.size, img.tobytes()
    return pygame.image.fromstring(data, size, mode)

def make_qr_surface(s, px=180):
    import qrcode
    qr = qrcode.QRCode(error_correction=qrcode.constants.ERROR_CORRECT_Q, box_size=4, border=1)
    qr.add_data(s); qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white").convert("RGB")
    img = img.resize((px, px), Image.NEAREST)
    return pil_to_surface(img)

class WalletScreens:
    def __init__(self, screen, renderer, engine):
        self.screen = screen; self.renderer = renderer; self.engine = engine
        self.sw, self.sh = screen.get_size()
        self.title_font = pygame.font.SysFont("dejavusans", 16, bold=True)
        self.body_font  = pygame.font.SysFont("dejavusans", 12)
        self.last_mnemonic = None; self.last_seed = None

    # ---------------- Create ----------------
    def create_wallet_flow(self):
        items = ["12-word Seed", "24-word Seed", "Back"]
        rects = self.renderer.draw_menu("Create Wallet", items, get_display_mode(self.renderer.settings))
        choice = self._wait_click(rects, items)
        if choice in (None, "Back"): return
        words = 12 if "12" in choice else 24
        try:
            mnemonic = self.engine.generate_mnemonic(words)
        except Exception as e:
            self._alert(f"Generate failed:\n{e}"); return
        # Show numbered seed first
        if not self._show_seed_numbered(mnemonic):
            return
        # Security word check BEFORE saving
        try:
            if not WordCheck(self.screen, self.title_font, self.body_font).run(mnemonic):
                self._toast("Word check failed"); return
            seed = self.engine.mnemonic_to_seed(mnemonic)
            self.last_mnemonic, self.last_seed = mnemonic, seed
            accounts = self._derive_all_known(seed)
            upsert_wallet(mnemonic, accounts)
            self._toast("Wallet saved")
            # Quick address preview
            acc = next((a for a in accounts if a["network_key"]=="ETH"), accounts[0] if accounts else None)
            if acc: self._show_address_screen(acc["address"])
        except Exception as e:
            self._alert(f"Save/derive failed:\n{e}")

    def _show_seed_numbered(self, mnemonic: str) -> bool:
        # returns True to continue, False to cancel
        words = mnemonic.split()
        scroll=0
        while True:
            self.screen.fill(WHITE)
            self.screen.blit(self.title_font.render("Seed (write down)", True, BLACK),(8,6))
            # list (numbered)
            y=28 - scroll
            for i,w in enumerate(words, start=1):
                self.screen.blit(self.body_font.render(f"{i:02d}. {w}", True, BLACK),(10,y))
                y+=14
            # QR + buttons
            qr=make_qr_surface(mnemonic, px=120); rect=qr.get_rect(center=(self.sw//2, self.sh//2+6))
            self.screen.blit(qr, rect)
            btn_qr = pygame.Rect(8, self.sh-26, 60, 20)
            btn_next=pygame.Rect(self.sw-68, self.sh-26, 60, 20)
            for r,l in ((btn_qr,"QR"), (btn_next,"Next")):
                pygame.draw.rect(self.screen,(220,220,220),r,border_radius=6); pygame.draw.rect(self.screen,OUT,r,1,border_radius=6)
                self.screen.blit(self.body_font.render(l, True, BLACK),(r.x+10, r.y+2))
            pygame.display.flip()
            for ev in pygame.event.get():
                if ev.type==pygame.QUIT: return False
                if ev.type==pygame.MOUSEBUTTONDOWN and ev.button==1:
                    if btn_qr.collidepoint(ev.pos): self._show_qr_modal(mnemonic)
                    if btn_next.collidepoint(ev.pos): return True

    # ---------------- Restore ----------------
    def restore_wallet_flow(self, keyboard_cls=None):
        # Numbered wizard by default
        wizard = SeedEntryWizard(self.screen, self.renderer, self.title_font, self.body_font)
        mnemonic = wizard.run()
        if not mnemonic: return
        # Optionally show summary (numbered) then proceed
        self._show_seed_numbered(mnemonic)
        # Derive & save
        try:
            seed = self.engine.mnemonic_to_seed(mnemonic)
            self.last_mnemonic, self.last_seed = mnemonic, seed
            accounts = self._derive_all_known(seed)
            upsert_wallet(mnemonic, accounts)
            self._toast("Wallet saved")
            acc = next((a for a in accounts if a["network_key"]=="ETH"), accounts[0] if accounts else None)
            if acc: self._show_address_screen(acc["address"])
        except Exception as e:
            self._alert(f"Save/derive failed:\n{e}")

    # ----- helpers (unchanged derive, alert, toast, address/qr) -----
    def _derive_all_known(self, seed):
        nets = list_networks(); out=[]
        for n in nets:
            t = n.get("type","evm").lower(); key = n.get("key","").upper()
            if t == "evm":
                path = (n.get("derivation_path") or "m/44'/60'/0'/0/{index}").replace("{index}","0")
                acc = self.engine.derive_evm_account(seed, path)
                out.append({"network_key": key,"network_type":"evm",
                            "derivation_path": acc["derivation_path"],"index": acc["index"],
                            "address": acc["address"],"public_key": acc["public_key"],"private_key": acc["private_key"]})
            else:
                path = (n.get("derivation_path") or "m/84'/0'/0'/0/{index}").replace("{index}","0")
                addr_type = n.get("address_type","P2WPKH"); coin_type = n.get("coin_type",0)
                acc = self.engine.derive_utxo_account(seed, addr_type, coin_type, path)
                out.append({"network_key": key,"network_type":"utxo","address_type": addr_type,
                            "derivation_path": acc["derivation_path"],"index": acc["index"],
                            "address": acc["address"],"public_key": acc["public_key"],"private_key": acc["private_key"]})
        return out

    def _alert(self, msg):
        self.screen.fill(WHITE); self.screen.blit(self.title_font.render("Notice", True, BLACK),(8,6))
        y=34
        for ln in str(msg).split("\n"):
            self.screen.blit(self.body_font.render(ln, True, BLACK),(8,y)); y+=16
        btn=pygame.Rect(self.sw-60, self.sh-26, 52, 20)
        pygame.draw.rect(self.screen,(220,220,220),btn,border_radius=6); pygame.draw.rect(self.screen,OUT,btn,1,border_radius=6)
        self.screen.blit(self.body_font.render("OK", True, BLACK),(btn.x+14, btn.y+2))
        pygame.display.flip()
        while True:
            for ev in pygame.event.get():
                if ev.type==pygame.QUIT: return
                if ev.type==pygame.MOUSEBUTTONDOWN and ev.button==1 and btn.collidepoint(ev.pos): return

    def _toast(self, text, ms=900):
        overlay = pygame.Surface((self.sw, 22)); overlay.fill((240,240,240))
        self.screen.blit(overlay,(0,self.sh-22))
        self.screen.blit(self.body_font.render(text, True, BLACK),(6,self.sh-18))
        pygame.display.flip(); pygame.time.delay(ms)

    def _show_address_screen(self, address: str):
        while True:
            self.screen.fill(WHITE); self.screen.blit(self.title_font.render("Address", True, BLACK),(8,6))
            box=pygame.Rect(8,28,self.sw-16,48); pygame.draw.rect(self.screen,BG,box,border_radius=8); pygame.draw.rect(self.screen,OUT,box,1,border_radius=8)
            y=box.y+8
            self.screen.blit(self.body_font.render(address, True, BLACK),(box.x+6,y))
            qr = make_qr_surface(address, px=100); rect=qr.get_rect(); rect.centerx=self.sw//2; rect.y=box.bottom+6; self.screen.blit(qr, rect)
            btn_back=pygame.Rect(16, self.sh-30, 60, 22); btn_qr=pygame.Rect(self.sw-80, self.sh-30, 60, 22)
            for r,lab in ((btn_back,"Back"), (btn_qr,"Full QR")):
                pygame.draw.rect(self.screen,(220,220,220),r,border_radius=6); pygame.draw.rect(self.screen,OUT,r,1,border_radius=6)
                self.screen.blit(self.body_font.render(lab, True, BLACK),(r.x+(r.w-self.body_font.size(lab)[0])//2, r.y+2))
            pygame.display.flip()
            for ev in pygame.event.get():
                if ev.type==pygame.QUIT: return
                if ev.type==pygame.MOUSEBUTTONDOWN and ev.button==1:
                    if btn_back.collidepoint(ev.pos): return
                    if btn_qr.collidepoint(ev.pos): self._show_qr_modal(address)

    def _show_qr_modal(self, data: str):
        while True:
            self.screen.fill(WHITE); qr=make_qr_surface(data, px=180); rect=qr.get_rect(center=(self.sw//2, self.sh//2)); self.screen.blit(qr, rect)
            close=pygame.Rect(self.sw-54, 6, 48, 22); pygame.draw.rect(self.screen,(220,220,220),close,border_radius=6); pygame.draw.rect(self.screen,OUT,close,1,border_radius=6)
            self.screen.blit(self.body_font.render("Close", True, BLACK),(close.x+6, close.y+2)); pygame.display.flip()
            for ev in pygame.event.get():
                if ev.type==pygame.QUIT: return
                if ev.type==pygame.MOUSEBUTTONDOWN and ev.button==1 and close.collidepoint(ev.pos): return

    def _wait_click(self, rects, labels):
        while True:
            for ev in pygame.event.get():
                if ev.type==pygame.QUIT: return None
                if ev.type==pygame.MOUSEBUTTONDOWN and ev.button==1:
                    for i,r in enumerate(rects):
                        if r.collidepoint(ev.pos): return labels[i]
