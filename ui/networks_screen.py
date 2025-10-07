# networks_screen.py
import pygame
from stores.settings import get_display_mode
from ui.display_modes import DisplayMode
from stores.network_store import list_networks
WHITE=(255,255,255); BLACK=(0,0,0); OUT=(0,0,0); BG=(238,238,238)

class NetworksScreen:
    def __init__(self, screen, renderer, engine, title_font, body_font, last_seed_getter):
        self.screen = screen
        self.renderer = renderer
        self.engine = engine
        self.title_font = title_font
        self.body_font = body_font
        self.get_seed = last_seed_getter

    def run(self):
        nets = list_networks()
        labels = [f"{n['name']} ({n['key']})" for n in nets] + ["Back"]
        rects = self.renderer.draw_menu("Networks", labels, get_display_mode(self.renderer.settings))

        while True:
            for ev in pygame.event.get():
                if ev.type == pygame.QUIT: return
                if ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 1:
                    idx = self.renderer.hit_test(rects, ev.pos)
                    if idx is None: break
                    if idx == len(labels)-1:  # Back
                        return
                    self._preview_network(nets[idx])

    def _preview_network(self, net):
        seed = self.get_seed()
        self.screen.fill(WHITE)
        self.screen.blit(self.title_font.render(net["name"], True, BLACK), (8,6))

        info = []
        if not seed:
            info.append("No seed loaded. Create/Restore first.")
        else:
            # derive index 0 address only (preview)
            if net["type"] == "evm":
                acc = self.engine.derive_evm_account(seed, net.get("derivation_path","m/44'/60'/0'/0/0").replace("{index}","0"))
                info += [f"Type: EVM", f"Address: {acc['address']}"]
            else:
                acc = self.engine.derive_utxo_account(seed,
                                                      address_type=net.get("address_type","P2WPKH"),
                                                      coin_type=net.get("coin_type",0),
                                                      derivation_path=net.get("derivation_path","m/84'/0'/0'/0/0").replace("{index}","0"))
                info += [f"Type: UTXO", f"Address: {acc['address']}"]

        y=28
        for line in info:
            self.screen.blit(self.body_font.render(line, True, BLACK), (8,y))
            y+=16

        btn_back = pygame.Rect(self.screen.get_width()-60, self.screen.get_height()-26, 52, 20)
        pygame.draw.rect(self.screen, (220,220,220), btn_back, border_radius=6)
        pygame.draw.rect(self.screen, OUT, btn_back, 1, border_radius=6)
        self.screen.blit(self.body_font.render("Back", True, BLACK), (btn_back.x+10, btn_back.y+2))
        pygame.display.flip()

        while True:
            for ev in pygame.event.get():
                if ev.type == pygame.QUIT: return
                if ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 1:
                    if btn_back.collidepoint(ev.pos): return
