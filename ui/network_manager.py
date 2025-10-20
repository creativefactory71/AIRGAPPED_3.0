# ui/network_manager.py
import pygame, time
from stores.network_store import list_networks, add_or_replace_network, edit_network, delete_network

class NetworkManager:
    """Settings → Networks. Pi touch fix: pump_input per frame."""
    def __init__(self, screen, renderer, title_font, body_font, small_font, toast_cb, pump_input=None):
        self.sc=screen; self.r=renderer; self.tf=title_font; self.bf=body_font; self.sf=small_font
        self.toast = toast_cb
        self.pump_input = pump_input
        self._down = None
        self._ignore_until = 0.0

    def _pump(self):
        if self.pump_input: self.pump_input()

    def _debounce_on_entry(self):
        cleared = pygame.event.clear([pygame.MOUSEBUTTONDOWN, pygame.MOUSEBUTTONUP, pygame.MOUSEMOTION])
        if cleared: pass
        self._ignore_until = time.time() + 0.15

    def _draw(self):
        nets = list_networks()
        labels = [f"{n['key']} · {n['name']} ({n['type']})" for n in nets]
        labels += ["Add Network","Edit Network","Delete Network","Back"]
        rects = self.r.draw_menu("Networks", labels, self.r.settings.get("ui_mode","grid"))
        pygame.display.update()
        return nets, labels, rects

    def _osk(self, title, initial=""):
        try:
            from ui.on_screen_keyboard import OnScreenKeyboard
            return OnScreenKeyboard(self.sc, title, initial, pump_input=self.pump_input).run()
        except TypeError:
            from ui.on_screen_keyboard import OnScreenKeyboard
            return OnScreenKeyboard(self.sc, title, initial).run()

    def _nk(self, title, initial=""):
        try:
            from ui.numeric_keyboard import NumericKeyboard
            return NumericKeyboard(self.sc, title, initial, pump_input=self.pump_input).run()
        except TypeError:
            from ui.numeric_keyboard import NumericKeyboard
            return NumericKeyboard(self.sc, title, initial).run()

    def _pick_key(self, title):
        self._debounce_on_entry()
        nets = list_networks(); keys = [n["key"] for n in nets]
        rects = self.r.draw_menu(title, keys+["Back"], self.r.settings.get("ui_mode","grid"))
        pygame.display.update()
        down = None
        while True:
            self._pump()
            for ev in pygame.event.get():
                if ev.type==pygame.QUIT: return None
                if ev.type==pygame.MOUSEBUTTONDOWN and ev.button==1:
                    if time.time() < self._ignore_until: continue
                    down = self.r.hit_test(rects, ev.pos)
                if ev.type==pygame.MOUSEBUTTONUP and ev.button==1:
                    up = self.r.hit_test(rects, ev.pos)
                    if down is not None and up == down:
                        if up == len(keys): return None
                        return keys[up]
                    down = None
            pygame.time.Clock().tick(30)

    def run(self):
        self._debounce_on_entry()
        while True:
            self._pump()
            nets, labels, rects = self._draw()
            for ev in pygame.event.get():
                if ev.type==pygame.QUIT: return
                if ev.type==pygame.MOUSEBUTTONDOWN and ev.button==1:
                    if time.time() < self._ignore_until: continue
                    self._down = self.r.hit_test(rects, ev.pos)
                if ev.type==pygame.MOUSEBUTTONUP and ev.button==1:
                    up = self.r.hit_test(rects, ev.pos)
                    if self._down is not None and up == self._down:
                        lab = labels[up]
                        if lab.endswith("Back"): return
                        if lab == "Add Network":
                            key  = (self._osk("Key (A-Z0-9_)", "") or "").upper().strip()
                            name = (self._osk("Name", "") or "").strip()
                            typ  = (self._osk("Type (evm/utxo/xrp)", "") or "").lower().strip()
                            sym  = (self._osk("Symbol", "") or "").strip()
                            patch = {"key":key,"name":name,"type":typ,"symbol":sym}
                            if typ == "evm":
                                cid = self._nk("chain_id","1"); patch["chain_id"]=int((cid or "1"))
                            elif typ == "utxo":
                                at  = (self._osk("address_type (P2WPKH/P2PKH)","P2WPKH") or "P2WPKH").upper()
                                ct  = self._nk("coin_type","0"); patch["address_type"]=at; patch["coin_type"]=int((ct or "0"))
                            try: add_or_replace_network(patch); self.toast("Saved")
                            except Exception as e: self.toast(str(e))
                        elif lab == "Edit Network":
                            k = self._pick_key("Edit which key?")
                            if not k: break
                            typ = (self._osk("Type (evm/utxo/xrp)", "") or "").lower().strip()
                            name= (self._osk("Name", "") or "").strip()
                            sym = (self._osk("Symbol", "") or "").strip()
                            patch={"type":typ,"name":name,"symbol":sym}
                            if typ == "evm":
                                cid = self._nk("chain_id","1"); patch["chain_id"]=int((cid or "1"))
                            elif typ == "utxo":
                                at  = (self._osk("address_type (P2WPKH/P2PKH)","P2WPKH") or "P2WPKH").upper()
                                ct  = self._nk("coin_type","0"); patch["address_type"]=at; patch["coin_type"]=int((ct or "0"))
                            try: edit_network(k, patch); self.toast("Updated")
                            except Exception as e: self.toast(str(e))
                        elif lab == "Delete Network":
                            k = self._pick_key("Delete which key?")
                            if not k: break
                            try: delete_network(k); self.toast("Deleted")
                            except Exception as e: self.toast(str(e))
                    self._down = None
            pygame.time.Clock().tick(30)
