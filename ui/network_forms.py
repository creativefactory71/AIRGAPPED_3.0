# network_forms.py
import pygame
from ui.on_screen_keyboard import OnScreenKeyboard
from stores.network_store import add_network
WHITE=(255,255,255); BLACK=(0,0,0); OUT=(0,0,0); BG=(238,238,238)

class AddNetworkForm:
    """
    Small 320x240 mouse-only form:
      - Name
      - Key (ID)
      - Symbol
      - Type: EVM / UTXO (toggle)
      - EVM: Chain ID, Derivation Path
      - UTXO: Address Type (cycle P2WPKH/P2SH-P2WPKH/P2PKH), Coin Type, Derivation Path
    """
    def __init__(self, screen, title_font, body_font):
        self.screen = screen
        self.title_font = title_font
        self.body_font = body_font
        self.sw, self.sh = screen.get_size()
        self.fields = {
            "name": "",
            "key": "",
            "symbol": "",
            "type": "evm",  # evm | utxo
            "chain_id": "1",
            "addr_type": "P2WPKH",
            "coin_type": "0",
            "derivation_path": "m/44'/60'/0'/0/{index}",  # default for evm
        }

    def _row(self, y, label, value=None, wide=False):
        lab = self.body_font.render(label, True, BLACK)
        self.screen.blit(lab, (8, y))
        w = self.sw - 16 if wide else (self.sw - 90)
        rect = pygame.Rect(8 if wide else 86, y-2, w, 20)
        pygame.draw.rect(self.screen, BG, rect, border_radius=6)
        pygame.draw.rect(self.screen, OUT, rect, 1, border_radius=6)
        if value is not None:
            txt = self.body_font.render(value, True, BLACK)
            self.screen.blit(txt, (rect.x+6, rect.y+3))
        return rect

    def run(self):
        clock = pygame.time.Clock()
        def draw():
            self.screen.fill(WHITE)
            self.screen.blit(self.title_font.render("Add Custom Network", True, BLACK),(8,6))
            r_name = self._row(28, "Name", self.fields["name"])
            r_key  = self._row(50, "Key", self.fields["key"])
            r_sym  = self._row(72, "Symbol", self.fields["symbol"])
            # type toggle
            type_rect = pygame.Rect(self.sw-110, 72, 100, 20)
            pygame.draw.rect(self.screen, BG, type_rect, border_radius=6)
            pygame.draw.rect(self.screen, OUT, type_rect, 1, border_radius=6)
            tval = f"Type: {self.fields['type'].upper()}"
            self.screen.blit(self.body_font.render(tval, True, BLACK),(type_rect.x+6,type_rect.y+3))

            if self.fields["type"] == "evm":
                r_cid = self._row(98, "Chain ID", self.fields["chain_id"])
                r_path = self._row(120, "Deriv Path", self.fields["derivation_path"], wide=True)
                evm_rects = ("chain_id", r_cid), ("derivation_path", r_path)
                utxo_rects = ()
            else:
                # utxo block
                # address type cycle
                addr_rect = pygame.Rect(8, 98, 132, 20)
                pygame.draw.rect(self.screen, BG, addr_rect, border_radius=6)
                pygame.draw.rect(self.screen, OUT, addr_rect, 1, border_radius=6)
                self.screen.blit(self.body_font.render(f"Addr: {self.fields['addr_type']}", True, BLACK),(addr_rect.x+6, addr_rect.y+3))

                r_coin = self._row(120, "Coin Type", self.fields["coin_type"])
                # default path for utxo
                if self.fields["addr_type"] == "P2WPKH":
                    default_path = "m/84'/0'/0'/0/{index}"
                elif self.fields["addr_type"] == "P2SH-P2WPKH":
                    default_path = "m/49'/0'/0'/0/{index}"
                else:
                    default_path = "m/44'/0'/0'/0/{index}"
                if self.fields["derivation_path"].startswith("m/44'"):
                    # if previously evm default, switch to utxo default
                    self.fields["derivation_path"] = default_path
                r_path = self._row(142, "Deriv Path", self.fields["derivation_path"], wide=True)
                utxo_rects = (("addr_type", addr_rect), ("coin_type", r_coin), ("derivation_path", r_path))
                evm_rects = ()

            # buttons
            btn_save = pygame.Rect(self.sw-120, self.sh-28, 50, 20)
            btn_back = pygame.Rect(self.sw-60, self.sh-28, 50, 20)
            for r,lab in ((btn_save, "Save"), (btn_back, "Back")):
                pygame.draw.rect(self.screen, (220,220,220), r, border_radius=6)
                pygame.draw.rect(self.screen, OUT, r, 1, border_radius=6)
                self.screen.blit(self.body_font.render(lab, True, BLACK),
                                 (r.x + (r.w- self.body_font.size(lab)[0])//2, r.y+2))
            pygame.display.flip()
            return {
                "name": r_name, "key": r_key, "symbol": r_sym, "type": type_rect,
                "evm": dict(evm_rects) if evm_rects else {},
                "utxo": dict(utxo_rects) if utxo_rects else {},
                "save": btn_save, "back": btn_back
            }

        while True:
            rects = draw()
            for ev in pygame.event.get():
                if ev.type == pygame.QUIT: return
                if ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 1:
                    p = ev.pos
                    if rects["back"].collidepoint(p): return
                    if rects["save"].collidepoint(p):
                        net = self._to_network()
                        add_network(net)
                        return
                    if rects["type"].collidepoint(p):
                        self.fields["type"] = "utxo" if self.fields["type"]=="evm" else "evm"
                    # text fields via OSK
                    for k in ("name","key","symbol"):
                        if rects[k].collidepoint(p):
                            t = OnScreenKeyboard(self.screen, self.fields[k]).run()
                            if t is not None: self.fields[k]=t
                    if self.fields["type"]=="evm":
                        if rects["evm"].get("chain_id") and rects["evm"]["chain_id"].collidepoint(p):
                            t = OnScreenKeyboard(self.screen, self.fields["chain_id"]).run()
                            if t is not None: self.fields["chain_id"]=t
                        if rects["evm"].get("derivation_path") and rects["evm"]["derivation_path"].collidepoint(p):
                            t = OnScreenKeyboard(self.screen, self.fields["derivation_path"]).run()
                            if t is not None: self.fields["derivation_path"]=t
                    else:
                        if rects["utxo"].get("coin_type") and rects["utxo"]["coin_type"].collidepoint(p):
                            t = OnScreenKeyboard(self.screen, self.fields["coin_type"]).run()
                            if t is not None: self.fields["coin_type"]=t
                        if rects["utxo"].get("derivation_path") and rects["utxo"]["derivation_path"].collidepoint(p):
                            t = OnScreenKeyboard(self.screen, self.fields["derivation_path"]).run()
                            if t is not None: self.fields["derivation_path"]=t
                        if rects["utxo"].get("addr_type") and rects["utxo"]["addr_type"].collidepoint(p):
                            order = ["P2WPKH","P2SH-P2WPKH","P2PKH"]
                            cur = order.index(self.fields["addr_type"])
                            self.fields["addr_type"] = order[(cur+1)%len(order)]
            clock.tick(30)

    def _to_network(self):
        if self.fields["type"]=="evm":
            return {
                "key": self.fields["key"].upper(),
                "name": self.fields["name"],
                "type": "evm",
                "symbol": self.fields["symbol"].upper(),
                "chain_id": int(self.fields["chain_id"] or "1"),
                "derivation_path": self.fields["derivation_path"] or "m/44'/60'/0'/0/{index}"
            }
        else:
            return {
                "key": self.fields["key"].upper(),
                "name": self.fields["name"],
                "type": "utxo",
                "symbol": self.fields["symbol"].upper(),
                "address_type": self.fields["addr_type"],
                "coin_type": int(self.fields["coin_type"] or "0"),
                "derivation_path": self.fields["derivation_path"] or "m/84'/0'/0'/0/{index}"
            }
