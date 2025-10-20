# flows/send_flow.py
import json, time, pygame
from pathlib import Path

from stores.network_store import list_networks
from stores.wallet_store import load_active_wallet
from debug import dbg
from ui.numeric_keyboard import NumericKeyboard
from ui.on_screen_keyboard import OnScreenKeyboard
from qr.qr_chunker import show_paged
#from qr_scanner import QRScanner
from crypto.evm_signer import sign_legacy_tx  # must return 0x-hex

WHITE=(255,255,255); BLACK=(0,0,0); OUT=(0,0,0)

UNSIGNED_PATH = Path("unsigned_tx.json")
SIGNED_PATH   = Path("signed_tx.txt")

DEFAULT_EVM_RECEIVER = "0xb922645E90e9fCAea54029be2434EA10eE9Ef47e"
CHAIN_IDS = {"XDC": 50, "ETHEREUM": 11155111}  # fallback to net["chain_id"]

class SendFlow:
    """
    Returns:
      None        -> caller just redraws Home
      "HOME"      -> caller should go Home immediately
      "SETTINGS"  -> caller should open Settings
    """
    def __init__(self, screen, renderer, engine, title_font, body_font, pump_input=None):
        self.sc=screen; self.r=renderer; self.eng=engine
        self.tf=title_font; self.bf=body_font
        self.sw,self.sh=screen.get_size()
        self.pump_input = pump_input
        self._down = None
        self._ignore_until = 0.0

    # -------- utilities --------
    def _pump(self):
        if self.pump_input: self.pump_input()

    def _debounce_on_entry(self):
        pygame.event.clear([pygame.MOUSEBUTTONDOWN, pygame.MOUSEBUTTONUP, pygame.MOUSEMOTION])
        self._ignore_until = time.time() + 0.15

    def _nk(self, title, initial=""):
        try:
            return NumericKeyboard(self.sc, title, initial, pump_input=self.pump_input).run()
        except TypeError:
            return NumericKeyboard(self.sc, title, initial).run()

    def _osk(self, title, initial=""):
        try:
            return OnScreenKeyboard(self.sc, title, initial, pump_input=self.pump_input).run()
        except TypeError:
            return OnScreenKeyboard(self.sc, title, initial).run()

    # -------- public --------
    def run(self):
        self._debounce_on_entry()
        nets=list_networks()
        labels=[f"{n['key']} · {n['name']} ({n['type']})" for n in nets]+["Back"]
        rects=self.r.draw_menu("Send → Select Network", labels, self.r.settings.get("ui_mode","grid"))
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
                        if up==len(labels)-1: return None
                        net=nets[up]
                        t=(net.get("type") or "").lower()
                        if t=="evm":  nav = self._send_evm(net)
                        elif t=="utxo": nav = self._send_btc_unsigned(net)
                        elif t=="xrp":  nav = self._send_xrp_unsigned(net)
                        else:
                            nav = self._alert(f"Unsupported network type: {t}")
                        if nav in ("HOME","SETTINGS"): return nav
                        # redraw picker after returning
                        self._debounce_on_entry()
                        rects=self.r.draw_menu("Send → Select Network", labels, self.r.settings.get("ui_mode","grid"))
                        pygame.display.update()
                    self._down = None
            pygame.time.Clock().tick(30)

    # -------- EVM --------
    def _validate_evm_receiver_or_raise(self, receiver_address: str):
        if not isinstance(receiver_address, str) or not receiver_address.strip():
            raise ValueError("Receiver address is empty")
        ra = receiver_address.strip()
        if not ra.startswith("0x") or len(ra) != 42:
            raise ValueError("Receiver address format invalid")
        try:
            int(ra[2:], 16)
        except ValueError:
            raise ValueError("Receiver address must be hex")

    def _chain_id_for_net(self, net):
        key = (net.get("key") or "").upper()
        name = (net.get("name") or "").upper()
        if key in CHAIN_IDS: return CHAIN_IDS[key]
        if name in CHAIN_IDS: return CHAIN_IDS[name]
        if "chain_id" in net: return int(net["chain_id"])
        return 1

    def _send_evm(self, net):
        self._debounce_on_entry()
        w = load_active_wallet()
        if not w:
            return self._alert("No active wallet.\nGo Settings → Wallets to set one.")
        acct = next((a for a in w.get("accounts",[]) if a.get("network_key")==net["key"]), None)
        if not acct:
            return self._alert("Active wallet has no account for this network.")

        recv = DEFAULT_EVM_RECEIVER
        try: self._validate_evm_receiver_or_raise(recv)
        except ValueError as e: return self._alert(str(e))

        amt_str = self._nk(f"Amount ({net.get('symbol','')})", "")
        if amt_str is None: return None
        try: value_wei = int(float(amt_str) * 1e18)
        except Exception: return self._alert("Invalid amount")

        nonce_txt = self._nk("Nonce", "")
        if nonce_txt is None: return None
        try: nonce = int(nonce_txt)
        except Exception: return self._alert("Invalid nonce")

        gas = 21000
        gas_price = 12_500_000_000  # 12.5 gwei
        chain_id = self._chain_id_for_net(net)

        unsigned_tx = {
            "nonce": nonce, "to": recv, "value": value_wei,
            "gas": gas, "gasPrice": gas_price, "chainId": chain_id, "data": "0x"
        }

        if UNSIGNED_PATH.exists():
            try: UNSIGNED_PATH.unlink()
            except Exception: pass
        UNSIGNED_PATH.write_text(json.dumps(unsigned_tx))

        try:
            raw_hex = sign_legacy_tx(
                acct["private_key"], recv, value_wei, nonce, gas, gas_price, chain_id
            )
        except Exception as e:
            return self._alert(f"Sign error:\n{e}")

        SIGNED_PATH.write_text(raw_hex)
        # Use paged QR viewer (has its own buttons)
        show_paged(self.sc, raw_hex, self.tf, self.bf, chunk_size=350, pump_input=self.pump_input)
        return None

    # -------- BTC (unsigned JSON) --------
    def _send_btc_unsigned(self, net):
        self._debounce_on_entry()
        recv = self._ask_receiver_btc()
        if recv in ("HOME","SETTINGS"): return recv
        if not recv: return None
        amt_btc = self._nk("Amount (BTC)", "")
        if amt_btc is None: return None

        utxo_txid = self._osk("Prev TXID", "")
        if not utxo_txid: return None
        utxo_index = self._nk("Prev Vout", "0")
        if utxo_index is None: return None
        utxo_value = self._nk("UTXO Value (sats)", "")
        if utxo_value is None: return None
        change_address = self._osk("Change address", "")
        if not change_address: return None
        fee_sats = self._nk("Fee (sats)", "")
        if fee_sats is None: return None

        try:
            value = int(float(amt_btc) * 1e8)
            utxo_index = int(utxo_index)
            utxo_value = int(utxo_value)
            fee = int(fee_sats)
        except Exception:
            return self._alert("Invalid numeric BTC inputs")

        if value + fee > utxo_value:
            return self._alert("Value + Fee exceeds available UTXO")

        change = utxo_value - value - fee

        tx = {
            "version": 1,
            "vin": [{
                "txid": utxo_txid,
                "vout": utxo_index,
                "scriptSig": "",
                "sequence": 0xFFFFFFFF
            }],
            "vout": [
                {"address": recv, "value": value},
                {"address": change_address, "value": change}
            ],
            "locktime": 0
        }

        if UNSIGNED_PATH.exists():
            try: UNSIGNED_PATH.unlink()
            except Exception: pass
        UNSIGNED_PATH.write_text(json.dumps(tx))
        SIGNED_PATH.write_text(json.dumps(tx))  # placeholder (air-gapped)
        show_paged(self.sc, json.dumps(tx), self.tf, self.bf, chunk_size=350, pump_input=self.pump_input)
        return None

    def _ask_receiver_btc(self):
        btn_scan=pygame.Rect(16, self.sh-30, 120, 22)
        btn_manual=pygame.Rect(self.sw-140, self.sh-30, 120, 22)
        self._debounce_on_entry()
        while True:
            self._pump()
            self.sc.fill(WHITE)
            self.sc.blit(self.tf.render("BTC receiver", True, BLACK),(8,6))
            self.sc.blit(self.bf.render("Choose input method", True, BLACK),(8,28))
            for r,l in ((btn_scan,"Scan QR (webcam)"), (btn_manual,"Manual Input")):
                pygame.draw.rect(self.sc,(220,220,220),r,border_radius=6)
                pygame.draw.rect(self.sc,OUT,r,1,border_radius=6)
                self.sc.blit(self.bf.render(l, True, BLACK),(r.x+6, r.y+2))

            self.r.draw_bottom_nav()
            pygame.display.update()

            for ev in pygame.event.get():
                if ev.type==pygame.QUIT: return None
                if ev.type==pygame.MOUSEBUTTONDOWN and ev.button==1:
                    if time.time() < self._ignore_until: continue
                    bh = self.r.bottom_hit(ev.pos)
                    if bh == "back": return None
                    if bh == "home": return "HOME"
                    if bh == "opts": return "SETTINGS"
                    if btn_scan.collidepoint(ev.pos):
                        data = QRScanner(self.sc, self.tf, self.bf).scan()
                        return data.strip() if data else None
                    if btn_manual.collidepoint(ev.pos):
                        addr = self._osk("", "")
                        return addr.strip() if addr else None
            pygame.time.Clock().tick(30)

    # -------- XRP (unsigned JSON) --------
    def _send_xrp_unsigned(self, net):
        self._debounce_on_entry()
        w = load_active_wallet()
        if not w:
            return self._alert("No active wallet.\nGo Settings → Wallets to set one.")
        acct = next((a for a in w.get("accounts",[]) if a.get("network_key")==net["key"]), None)
        if not acct:
            return self._alert("Active wallet has no account for this network.")

        recv = self._ask_receiver_xrp()
        if recv in ("HOME","SETTINGS"): return recv
        if not recv: return None
        amount_xrp = self._nk("Amount (XRP)", "")
        if amount_xrp is None: return None
        sequence = self._nk("Sequence", "")
        if sequence is None: return None
        fee_drops = self._nk("Fee (drops)", "")
        if fee_drops is None: return None

        try:
            amount_drops = int(float(amount_xrp) * 1_000_000)
            sequence_i = int(sequence)
            fee_i = int(fee_drops)
        except Exception:
            return self._alert("Invalid XRP number")

        sender = acct.get("address","")
        tx = {
            "TransactionType": "Payment",
            "Account": sender,
            "Destination": recv,
            "Amount": str(amount_drops),
            "Sequence": sequence_i,
            "Fee": str(fee_i),
            "Flags": 2147483648,
            "SigningPubKey": "",
            "TxnSignature": ""
        }

        if UNSIGNED_PATH.exists():
            try: UNSIGNED_PATH.unlink()
            except Exception: pass
        UNSIGNED_PATH.write_text(json.dumps(tx))
        SIGNED_PATH.write_text(json.dumps(tx))  # placeholder (air-gapped)
        show_paged(self.sc, json.dumps(tx), self.tf, self.bf, chunk_size=350, pump_input=self.pump_input)
        return None

    def _ask_receiver_xrp(self):
        btn_scan=pygame.Rect(16, self.sh-30, 120, 22)
        btn_manual=pygame.Rect(self.sw-140, self.sh-30, 120, 22)
        self._debounce_on_entry()
        while True:
            self._pump()
            self.sc.fill(WHITE)
            self.sc.blit(self.tf.render("XRP destination", True, BLACK),(8,6))
            self.sc.blit(self.bf.render("Choose input method", True, BLACK),(8,28))
            for r,l in ((btn_scan,"Scan QR (webcam)"), (btn_manual,"Manual Input")):
                pygame.draw.rect(self.sc,(220,220,220),r,border_radius=6)
                pygame.draw.rect(self.sc,OUT,r,1,border_radius=6)
                self.sc.blit(self.bf.render(l, True, BLACK),(r.x+6, r.y+2))

            self.r.draw_bottom_nav()
            pygame.display.update()

            for ev in pygame.event.get():
                if ev.type==pygame.QUIT: return None
                if ev.type==pygame.MOUSEBUTTONDOWN and ev.button==1:
                    if time.time() < self._ignore_until: continue
                    bh = self.r.bottom_hit(ev.pos)
                    if bh == "back": return None
                    if bh == "home": return "HOME"
                    if bh == "opts": return "SETTINGS"
                    if btn_scan.collidepoint(ev.pos):
                        data = QRScanner(self.sc, self.tf, self.bf).scan()
                        return data.strip() if data else None
                    if btn_manual.collidepoint(ev.pos):
                        addr = self._osk("", "")
                        return addr.strip() if addr else None
            pygame.time.Clock().tick(30)

    # -------- misc --------
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
