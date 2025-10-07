# info_screen.py
import pygame, json
from stores.wallet_store import load_wallet, get_active_wallet_name   # <-- changed
from stores.network_store import load_networks
WHITE=(255,255,255); BLACK=(0,0,0); OUT=(0,0,0); BG=(238,238,238)

class InfoScreen:
    def __init__(self, screen, title_font, body_font):
        self.sc=screen; self.tf=title_font; self.bf=body_font
        self.sw,self.sh=screen.get_size()

    def run(self):
        active = get_active_wallet_name()                      # <-- show active
        w=load_wallet(); n=load_networks()
        self.sc.fill(WHITE)
        self.sc.blit(self.tf.render(f"Info — active: {active}", True, BLACK),(8,6))
        y=28
        self.sc.blit(self.bf.render(f"Accounts: {len(w.get('accounts',[]))}", True, BLACK),(8,y)); y+=16
        self.sc.blit(self.bf.render("Files:", True, BLACK),(8,y)); y+=16
        for p in ("wallets/*.json (per wallet)", "wallet_meta.json", "networks.json", "pin.json"):
            self.sc.blit(self.bf.render(f"- {p}", True, BLACK),(16,y)); y+=16
        if w.get("accounts"):
            a=w["accounts"][0]
            y+=6; self.sc.blit(self.bf.render("Preview (first acct):", True, BLACK),(8,y)); y+=16
            for line in [f"{a['network_key']} {a['network_type']}", f"Addr: {a['address']}", f"Path: {a['derivation_path']}"]:
                self.sc.blit(self.bf.render(line[:44], True, BLACK),(8,y)); y+=16

        btn=pygame.Rect(self.sw-60, self.sh-26, 52, 20)
        pygame.draw.rect(self.sc, (220,220,220), btn, border_radius=6); pygame.draw.rect(self.sc, OUT, btn, 1, border_radius=6)
        self.sc.blit(self.bf.render("Back", True, BLACK),(btn.x+10, btn.y+2))
        pygame.display.flip()
        while True:
            for ev in pygame.event.get():
                if ev.type==pygame.QUIT: return
                if ev.type==pygame.MOUSEBUTTONDOWN and ev.button==1 and btn.collidepoint(ev.pos): return
