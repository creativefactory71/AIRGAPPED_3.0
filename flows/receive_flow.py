# flows/receive_flow.py
import json, time, pygame
from pathlib import Path

from stores.wallet_store import load_active_wallet
from stores.network_store import list_networks
from debug import dbg
from qr.qr_chunker import show_paged

WHITE=(255,255,255); BLACK=(0,0,0); OUT=(0,0,0)

class ReceiveFlow:
    """
    Select Network -> Show address (and QR if available).
    Returns:
      None        -> caller just redraws Home
      "HOME"      -> caller should go Home immediately
      "SETTINGS"  -> caller should open Settings
    """
    def __init__(self, screen, renderer, title_font, body_font, pump_input=None):
        self.sc=screen; self.r=renderer
        self.tf=title_font; self.bf=body_font
        self.sw,self.sh = screen.get_size()
        self.pump_input = pump_input
        self._down = None
        self._ignore_until = 0.0

    def _pump(self):
        if self.pump_input: self.pump_input()

    def _debounce_on_entry(self):
        pygame.event.clear([pygame.MOUSEBUTTONDOWN, pygame.MOUSEBUTTONUP, pygame.MOUSEMOTION])
        self._ignore_until = time.time() + 0.15

    # ---------------- public ----------------
    def run(self):
        self._debounce_on_entry()
        nets = list_networks()
        labels = [f"{n['key']} · {n['name']} ({n['type']})" for n in nets] + ["Back"]
        rects = self.r.draw_menu("Receive → Select Network", labels, self.r.settings.get("ui_mode","grid"))
        pygame.display.update()

        while True:
            self._pump()
            for ev in pygame.event.get():
                if ev.type==pygame.QUIT: return None
                if ev.type==pygame.MOUSEBUTTONDOWN and ev.button==1:
                    if time.time() < self._ignore_until: continue
                    # bottom bar first
                    bh = self.r.bottom_hit(ev.pos)
                    if bh == "back": return None
                    if bh == "home": return "HOME"
                    if bh == "opts": return "SETTINGS"
                    self._down = self.r.hit_test(rects, ev.pos)
                if ev.type==pygame.MOUSEBUTTONUP and ev.button==1:
                    up = self.r.hit_test(rects, ev.pos)
                    if self._down is not None and up == self._down:
                        if up == len(labels)-1:  # Back
                            return None
                        net = nets[up]
                        nav = self._show_address_for_network(net)
                        if nav in ("HOME","SETTINGS"): return nav
                        # redraw selection after returning
                        self._debounce_on_entry()
                        rects = self.r.draw_menu("Receive → Select Network", labels, self.r.settings.get("ui_mode","grid"))
                        pygame.display.update()
                    self._down = None
            pygame.time.Clock().tick(30)

    # ---------------- helpers ----------------
    def _show_address_for_network(self, net):
        self._debounce_on_entry()
        w = load_active_wallet()
        if not w:
            return self._alert("No active wallet.\nGo Settings → Wallets to set one.")
        acct = next((a for a in w.get("accounts", []) if a.get("network_key")==net["key"]), None)
        if not acct:
            return self._alert("Active wallet has no account for this network.")

        addr = acct.get("address","")
        dbg(f"Receive: {net['key']} addr={addr}")

        btn_back = pygame.Rect(8, self.sh-26, 60, 20)
        btn_qrpg = pygame.Rect(self.sw-120, self.sh-26, 112, 20)

        while True:
            self._pump()
            self.sc.fill(WHITE)
            self.sc.blit(self.tf.render(f"{net['key']} Receive", True, BLACK),(8,6))

            # content
            y = 30
            self.sc.blit(self.bf.render("Address:", True, BLACK), (8,y)); y+=18
            for line in [addr[i:i+26] for i in range(0,len(addr),26)]:
                self.sc.blit(self.bf.render(line, True, BLACK), (8,y)); y+=16

            # local buttons
            for r,l in ((btn_back,"Back"),(btn_qrpg,"Show QR (paged)")):
                pygame.draw.rect(self.sc,(230,230,230),r,border_radius=6)
                pygame.draw.rect(self.sc,OUT,r,1,border_radius=6)
                self.sc.blit(self.bf.render(l, True, BLACK),(r.x+6, r.y+2))

            # bottom nav
            self.r.draw_bottom_nav()
            pygame.display.update()

            for ev in pygame.event.get():
                if ev.type==pygame.QUIT: return None
                if ev.type==pygame.MOUSEBUTTONDOWN and ev.button==1:
                    if time.time() < self._ignore_until: continue
                    # bottom nav?
                    bh = self.r.bottom_hit(ev.pos)
                    if bh == "back": return None
                    if bh == "home": return "HOME"
                    if bh == "opts": return "SETTINGS"
                    # local?
                    if btn_back.collidepoint(ev.pos):
                        return None
                    if btn_qrpg.collidepoint(ev.pos):
                        show_paged(self.sc, addr, self.tf, self.bf, chunk_size=350, pump_input=self.pump_input)
                        # after modal close, loop continues
            pygame.time.Clock().tick(30)

    def _alert(self, msg):
        self._pump()
        self.sc.fill((255,255,255))
        self.sc.blit(self.tf.render("Notice", True, (0,0,0)), (8,6))
        y=34
        for line in str(msg).split("\n"):
            self.sc.blit(self.bf.render(line, True, (0,0,0)), (8,y)); y+=16
        btn=pygame.Rect(self.sw-60, self.sh-26, 52, 20)
        pygame.draw.rect(self.sc, (220,220,220), btn, border_radius=6)
        pygame.draw.rect(self.sc, (0,0,0), btn, 1, border_radius=6)
        self.sc.blit(self.bf.render("OK", True, (0,0,0)), (btn.x+14, btn.y+2))
        self.r.draw_bottom_nav()
        pygame.display.update()
        while True:
            self._pump()
            for ev in pygame.event.get():
                if ev.type==pygame.QUIT: return None
                if ev.type==pygame.MOUSEBUTTONDOWN and ev.button==1:
                    if btn.collidepoint(ev.pos): return None
                    bh = self.r.bottom_hit(ev.pos)
                    if bh == "back": return None
                    if bh == "home": return "HOME"
                    if bh == "opts": return "SETTINGS"
            pygame.time.Clock().tick(30)
