# receive_flow.py
import pygame
from stores.settings import get_display_mode
from stores.network_store import list_networks
from stores.wallet_store import load_wallet
import qrcode
from PIL import Image
from qr.qr_scanner import QRScanner

WHITE=(255,255,255); BLACK=(0,0,0); OUT=(0,0,0); BG=(238,238,238)

def _qr_surface(data, size=180):
    qr=qrcode.QRCode(error_correction=qrcode.constants.ERROR_CORRECT_Q, box_size=4, border=1)
    qr.add_data(data); qr.make(fit=True)
    img=qr.make_image(fill_color="black", back_color="white").convert("RGB")
    img=img.resize((size,size), Image.NEAREST)
    mode,size,data2=img.mode,img.size,img.tobytes()
    import pygame as pg
    return pg.image.fromstring(data2, size, mode)

class ReceiveFlow:
    """
    RECEIVE:
      - Show my address QR
      - New: 'Scan Invoice' (webcam) to parse simple payment URIs (EIP-681 / BIP-21)
    """
    def __init__(self, screen, renderer, title_font, body_font):
        self.sc=screen; self.r=renderer; self.tf=title_font; self.bf=body_font
        self.sw,self.sh=screen.get_size()

    def run(self):
        nets=list_networks()
        labels=[n["name"] for n in nets]+["Back"]
        rects=self.r.draw_menu("Receive → Select Network", labels, get_display_mode(self.r.settings))
        while True:
            for ev in pygame.event.get():
                if ev.type==pygame.QUIT: return
                if ev.type==pygame.MOUSEBUTTONDOWN and ev.button==1:
                    hit=self.r.hit_test(rects, ev.pos)
                    if hit is None: break
                    if hit==len(labels)-1: return
                    self._show_for_network(nets[hit])

    def _show_for_network(self, net):
        w=load_wallet()
        acct=next((a for a in w["accounts"] if a["network_key"]==net["key"]), None)
        self.sc.fill(WHITE)
        self.sc.blit(self.tf.render(f"{net['name']} Receive", True, BLACK),(8,6))
        if not acct:
            self.sc.blit(self.bf.render("No account found. Create/Restore first.", True, BLACK),(8,28))
            pygame.display.flip(); self._wait_back(); return
        addr=acct["address"]; pub=acct["public_key"]
        # address block
        box=pygame.Rect(8, 28, self.sw-16, 46)
        pygame.draw.rect(self.sc, BG, box, border_radius=8); pygame.draw.rect(self.sc, OUT, box, 1, border_radius=8)
        self.sc.blit(self.bf.render(addr, True, BLACK), (box.x+6, box.y+14))
        qr=_qr_surface(addr, 120); rect=qr.get_rect(center=(self.sw//2, self.sh//2+4))
        self.sc.blit(qr, rect)
        # buttons
        btn_pub   = pygame.Rect(8, self.sh-26, 84, 20)
        btn_scan  = pygame.Rect(98, self.sh-26, 92, 20)
        btn_back  = pygame.Rect(self.sw-60, self.sh-26, 52, 20)
        for r,l in ((btn_pub,"PubKey QR"), (btn_scan,"Scan Invoice"), (btn_back,"Back")):
            pygame.draw.rect(self.sc, (220,220,220), r, border_radius=6); pygame.draw.rect(self.sc, OUT, r, 1, border_radius=6)
            self.sc.blit(self.bf.render(l, True, BLACK),(r.x+6, r.y+2))
        pygame.display.flip()

        # loop
        while True:
            for ev in pygame.event.get():
                if ev.type==pygame.QUIT: return
                if ev.type==pygame.MOUSEBUTTONDOWN and ev.button==1:
                    if btn_back.collidepoint(ev.pos): return
                    if btn_pub.collidepoint(ev.pos):
                        self._qr_modal(pub, "Public Key")
                    if btn_scan.collidepoint(ev.pos):
                        data = QRScanner(self.sc, self.tf, self.bf).scan()
                        if data:
                            self._show_invoice_info(net, data)

    def _show_invoice_info(self, net, raw):
        """Very small parser for ethereum:/bitcoin: URIs; shows results."""
        t = net.get("type","evm").lower()
        info = []
        if t=="evm" and raw.lower().startswith("ethereum:"):
            core = raw.split(":",1)[1]
            addr = core.split("@",1)[0].split("?",1)[0]
            info += [f"ETH URI detected", f"Address: {addr}"]
            if "?" in core:
                qs = core.split("?",1)[1]
                params = {p.split("=")[0]:p.split("=")[1] for p in qs.split("&") if "=" in p}
                if "value" in params: info.append(f"value: {params['value']}")
        elif t=="utxo" and raw.lower().startswith("bitcoin:"):
            core = raw.split(":",1)[1]
            addr = core.split("?",1)[0]
            info += [f"BTC URI detected", f"Address: {addr}"]
            if "?" in core:
                qs = core.split("?",1)[1]
                params = {p.split("=")[0]:p.split("=")[1] for p in qs.split("&") if "=" in p}
                if "amount" in params: info.append(f"amount: {params['amount']}")
        else:
            info += ["Raw scan:", raw[:120]]

        # modal
        while True:
            self.sc.fill(WHITE)
            self.sc.blit(self.tf.render("Scanned Invoice", True, BLACK),(8,6))
            y=28
            for line in info:
                self.sc.blit(self.bf.render(line, True, BLACK),(8,y)); y+=16
            btn=pygame.Rect(self.sw-60, self.sh-26, 52, 20)
            pygame.draw.rect(self.sc,(220,220,220),btn,border_radius=6); pygame.draw.rect(self.sc, OUT, btn,1,border_radius=6)
            self.sc.blit(self.bf.render("Close", True, BLACK),(btn.x+6, btn.y+2))
            pygame.display.flip()
            for ev in pygame.event.get():
                if ev.type==pygame.QUIT: return
                if ev.type==pygame.MOUSEBUTTONDOWN and ev.button==1 and btn.collidepoint(ev.pos):
                    return

    def _qr_modal(self, text, title):
        while True:
            self.sc.fill(WHITE)
            self.sc.blit(self.tf.render(title, True, BLACK),(8,6))
            qr=_qr_surface(text, 180); rect=qr.get_rect(center=(self.sw//2, self.sh//2))
            self.sc.blit(qr, rect)
            btn=pygame.Rect(self.sw-60, 6, 52, 20)
            pygame.draw.rect(self.sc, (220,220,220), btn, border_radius=6); pygame.draw.rect(self.sc, OUT, btn, 1, border_radius=6)
            self.sc.blit(self.bf.render("Close", True, BLACK),(btn.x+6, btn.y+2))
            pygame.display.flip()
            for ev in pygame.event.get():
                if ev.type==pygame.QUIT: return
                if ev.type==pygame.MOUSEBUTTONDOWN and ev.button==1 and btn.collidepoint(ev.pos): return

    def _wait_back(self):
        btn=pygame.Rect(self.sw-60, self.sh-26, 52, 20)
        pygame.draw.rect(self.sc, (220,220,220), btn, border_radius=6); pygame.draw.rect(self.sc, OUT, btn, 1, border_radius=6)
        self.sc.blit(self.bf.render("Back", True, BLACK),(btn.x+10, btn.y+2))
        pygame.display.flip()
        while True:
            for ev in pygame.event.get():
                if ev.type==pygame.QUIT: return
                if ev.type==pygame.MOUSEBUTTONDOWN and ev.button==1 and btn.collidepoint(ev.pos): return
