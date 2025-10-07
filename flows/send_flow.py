# send_flow.py
import json
import pygame
from pathlib import Path

from ui.on_screen_keyboard import OnScreenKeyboard
from ui.numeric_keyboard import NumericKeyboard
from stores.settings import get_display_mode
from stores.network_store import list_networks
from stores.wallet_store import load_wallet
from qr.qr_chunker import show_paged
from qr.qr_scanner import QRScanner

# Signers
from crypto.evm_signer import sign_legacy_tx            # ETH/XDC/EVM (legacy)
# from btc_signer import sign_p2wpkh_single_input  # BTC P2WPKH
from crypto.xrp_signer import sign_xrp_payment_tx       # XRP Payment

WHITE=(255,255,255); BLACK=(0,0,0); OUT=(0,0,0); BG=(238,238,238)

UNSIGNED_PATH = Path("unsigned_tx.json")
SIGNED_PATH   = Path("signed_tx.txt")

# --- Default EVM receiver so you don't need to type/scan ---
DEFAULT_EVM_RECEIVER = "0xb922645E90e9fCAea54029be2434EA10eE9Ef47e"

# Optional convenience map; falls back to network['chain_id']
CHAIN_IDS = {
    "XDC": 50,
    "ETHEREUM": 11155111,  # Sepolia
}

class SendFlow:
    """SEND aligned with your previous flow:
       - EVM: strict 0x address validation, float->wei, fixed gas=21000 & 12.5 Gwei (editable if you prefer).
       - BTC/XRP: collect fields, sign offline (btclib / xrpl-py).
       Always writes unsigned_tx.json (first) and signed_tx.txt.
       Uses DEFAULT_EVM_RECEIVER automatically.
    """
    def __init__(self, screen, renderer, engine, title_font, body_font):
        self.sc=screen; self.r=renderer; self.eng=engine
        self.tf=title_font; self.bf=body_font
        self.sw,self.sh=screen.get_size()

    def run(self):
        nets=list_networks()
        labels=[f"{n['name']} ({n['type']})" for n in nets]+["Back"]
        rects=self.r.draw_menu("Send → Select Network", labels, get_display_mode(self.r.settings))
        while True:
            for ev in pygame.event.get():
                if ev.type==pygame.QUIT: return
                if ev.type==pygame.MOUSEBUTTONDOWN and ev.button==1:
                    hit=self.r.hit_test(rects, ev.pos)
                    if hit is None: break
                    if hit==len(labels)-1: return
                    net=nets[hit]
                    t=(net.get("type") or "").lower()
                    if t=="evm": self._send_evm_legacy_like_before(net)
                    # elif t=="utxo": self._send_btc_sign(net)
                    elif t=="xrp": self._send_xrp_sign(net)
                    else: self._alert(f"Unsupported network type: {t}")
            pygame.time.Clock().tick(30)

    # ---------------- Helpers ----------------
    def _alert(self, msg):
        self.sc.fill((255,255,255))
        self.sc.blit(self.tf.render("Notice", True, (0,0,0)), (8,6))
        y=34
        for line in str(msg).split("\n"):
            self.sc.blit(self.bf.render(line, True, (0,0,0)), (8,y)); y+=16
        btn=pygame.Rect(self.sw-60, self.sh-26, 52, 20)
        pygame.draw.rect(self.sc, (220,220,220), btn, border_radius=6)
        pygame.draw.rect(self.sc, (0,0,0), btn, 1, border_radius=6)
        self.sc.blit(self.bf.render("OK", True, (0,0,0)), (btn.x+14, btn.y+2))
        pygame.display.flip()
        while True:
            for ev in pygame.event.get():
                if ev.type==pygame.QUIT: return
                if ev.type==pygame.MOUSEBUTTONDOWN and ev.button==1 and btn.collidepoint(ev.pos): return

    def _validate_evm_receiver_or_raise(self, receiver_address: str):
        if not isinstance(receiver_address, str) or not receiver_address.strip():
            raise ValueError("Receiver address is empty")
        ra = receiver_address.strip()
        if not ra.startswith("0x") or len(ra) != 42:
            raise ValueError("Receiver address format invalid")
        # ensure hex body
        int(ra[2:], 16)

    def _chain_id_for_net(self, net):
        key = (net.get("key") or "").upper()
        name = (net.get("name") or "").upper()
        if key in CHAIN_IDS: return CHAIN_IDS[key]
        if name in CHAIN_IDS: return CHAIN_IDS[name]
        return int(net.get("chain_id", 1))

    # ---------------- EVM (legacy-style, auto default receiver) ----------------
    def _send_evm_legacy_like_before(self, net):
        w=load_wallet()
        acct=next((a for a in w.get("accounts", []) if (a.get("network_key") or "").upper()==(net["key"] or "").upper()), None)
        if not acct:
            self._alert("No account for this network.\nCreate/Restore wallet first.")
            return

        # Use your default receiver automatically
        recv = DEFAULT_EVM_RECEIVER

        # Validate receiver (0x + 40 hex)
        try:
            self._validate_evm_receiver_or_raise(recv)
        except Exception as e:
            self._alert(e); return

        # Amount ETH → wei (float*1e18 like your code)
        amt_str = NumericKeyboard(self.sc, f"Amount ({net.get('symbol','')})", "").run()
        if amt_str is None: return
        try:
            value_wei = int(float(amt_str) * 1e18)
        except Exception:
            self._alert("Invalid amount"); return

        # Nonce (int)
        nonce_txt = NumericKeyboard(self.sc, "Nonce", "").run()
        if nonce_txt is None: return
        try:
            nonce = int(nonce_txt)
        except Exception:
            self._alert("Invalid nonce"); return

        # Fixed gas settings to mirror your previous script
        gas = 21000
        gas_price = 12_500_000_000  # 12.5 Gwei

        chain_id = self._chain_id_for_net(net)

        # Build unsigned tx (JSON-friendly; data MUST be "0x")
        unsigned_tx = {
            "nonce": nonce,
            "to": recv,
            "value": value_wei,
            "gas": gas,
            "gasPrice": gas_price,
            "chainId": chain_id,
            "data": "0x"
        }

        # Save unsigned BEFORE signing
        try:
            if UNSIGNED_PATH.exists(): UNSIGNED_PATH.unlink()
        except Exception:
            pass
        UNSIGNED_PATH.write_text(json.dumps(unsigned_tx, indent=2))

        # Sign (returns 0x-hex string; do NOT access .rawTransaction)
        try:
            raw_hex = sign_legacy_tx(
                acct["private_key"], recv, value_wei, nonce, gas, gas_price, chain_id
            )
        except Exception as e:
            self._alert(f"Sign error:\n{e}"); return

        if not isinstance(raw_hex, str): raw_hex = str(raw_hex)
        if not raw_hex.startswith("0x"): raw_hex = "0x"+raw_hex

        SIGNED_PATH.write_text(raw_hex + ("\n" if not raw_hex.endswith("\n") else ""))
        show_paged(self.sc, raw_hex, self.tf, self.bf, chunk_size=350)

    # ---------------- BTC (collect + sign) ----------------
    def _send_btc_sign(self, net):
        # Destination & fee
        recipient = self._ask_receiver_btc()
        if not recipient: return
        amt_btc = NumericKeyboard(self.sc, "Amount (BTC)", "").run()
        if amt_btc is None: return

        # UTXO info
        utxo_txid = OnScreenKeyboard(self.sc, "Prev TXID (hex)", input_type="hex").run()
        if not utxo_txid: return
        utxo_index = NumericKeyboard(self.sc, "Prev Vout", "0").run()
        if utxo_index is None: return
        utxo_value = NumericKeyboard(self.sc, "UTXO Value (sats)", "").run()
        if utxo_value is None: return

        # Change (default: our BTC address)
        w = load_wallet()
        acc = next((a for a in w.get("accounts", []) if (a.get("network_key") or "").upper()=="BTC"), None)
        if not acc:
            self._alert("No BTC account; create/restore wallet first."); return
        change_address = OnScreenKeyboard(self.sc, "Change address", default_text=acc["address"]).run()
        if not change_address: return
        fee_sats = NumericKeyboard(self.sc, "Fee (sats)", "").run()
        if fee_sats is None: return

        try:
            value = int(float(amt_btc) * 1e8)
            utxo_index = int(utxo_index)
            utxo_value = int(utxo_value)
            fee = int(fee_sats)
        except Exception:
            self._alert("Invalid numeric BTC inputs"); return

        if value + fee > utxo_value:
            self._alert("Value + Fee exceeds available UTXO"); return

        unsigned = {
            "network": "BTC",
            "utxo": {"txid": utxo_txid, "vout": utxo_index, "amount_sats": utxo_value, "address": acc["address"]},
            "to": recipient,
            "send_amount_sats": value,
            "fee_sats": fee,
            "change_address": change_address
        }

        try:
            if UNSIGNED_PATH.exists(): UNSIGNED_PATH.unlink()
        except Exception:
            pass
        UNSIGNED_PATH.write_text(json.dumps(unsigned, indent=2))

        # # Sign (single-input P2WPKH)
        # try:
        #     raw_hex = sign_p2wpkh_single_input(
        #         privkey_hex=acc["private_key"],
        #         utxo_txid_be_hex=utxo_txid,
        #         utxo_vout=utxo_index,
        #         utxo_amount_sats=utxo_value,
        #         utxo_address=acc["address"],  # input owner script
        #         recipient_address=recipient,
        #         send_amount_sats=value,
        #         fee_sats=fee,
        #         change_address=change_address,
        #         network="mainnet"
        #     )
        # except Exception as e:
        #     self._alert(f"BTC sign error:\n{e}"); return

        # SIGNED_PATH.write_text(raw_hex + ("\n" if not raw_hex.endswith("\n") else ""))
        # show_paged(self.sc, raw_hex, self.tf, self.bf, chunk_size=350)

    def _ask_receiver_btc(self):
        # enter/scan BTC address
        btn_scan=pygame.Rect(16, self.sh-30, 120, 22)
        btn_manual=pygame.Rect(self.sw-140, self.sh-30, 120, 22)
        while True:
            self.sc.fill(WHITE)
            self.sc.blit(self.tf.render("BTC receiver", True, BLACK),(8,6))
            self.sc.blit(self.bf.render("Choose input method", True, BLACK),(8,28))
            for r,l in ((btn_scan,"Scan QR (webcam)"), (btn_manual,"Manual Input")):
                pygame.draw.rect(self.sc,(220,220,220),r,border_radius=6)
                pygame.draw.rect(self.sc,OUT,r,1,border_radius=6)
                self.sc.blit(self.bf.render(l, True, BLACK),(r.x+6, r.y+2))
            pygame.display.flip()
            for ev in pygame.event.get():
                if ev.type==pygame.QUIT: return None
                if ev.type==pygame.MOUSEBUTTONDOWN and ev.button==1:
                    if btn_scan.collidepoint(ev.pos):
                        try:
                            data = QRScanner(self.sc, self.tf, self.bf).scan()
                        except TypeError:
                            data = QRScanner(self.sc).scan()
                        return data.strip() if data else None
                    if btn_manual.collidepoint(ev.pos):
                        addr = OnScreenKeyboard(self.sc, "").run()
                        return addr.strip() if addr else None

    # ---------------- XRP (collect + sign) ----------------
    def _send_xrp_sign(self, net):
        # Active XRP account
        w = load_wallet()
        acc = next((a for a in w.get("accounts", []) if (a.get("network_key") or "").upper()=="XRP"), None)
        if not acc:
            self._alert("No XRP account; create/restore wallet first."); return
        account_addr = acc["address"]

        destination = self._ask_receiver_xrp()
        if not destination: return
        amount_xrp = NumericKeyboard(self.sc, "Amount (XRP)", "").run()
        if amount_xrp is None: return
        sequence = NumericKeyboard(self.sc, "Sequence", "").run()
        if sequence is None: return
        fee_drops = NumericKeyboard(self.sc, "Fee (drops)", "").run()
        if fee_drops is None: return

        try:
            amount_drops = int(float(amount_xrp) * 1_000_000)  # 1 XRP = 1e6 drops
            sequence_i = int(sequence)
            fee_i = int(fee_drops)
        except Exception:
            self._alert("Invalid XRP number"); return

        unsigned = {
            "network": "XRP",
            "TransactionType": "Payment",
            "Account": account_addr,
            "Destination": destination,
            "Amount": amount_drops,
            "Sequence": sequence_i,
            "Fee": fee_i,
            "Flags": 2147483648
        }

        try:
            if UNSIGNED_PATH.exists(): UNSIGNED_PATH.unlink()
        except Exception:
            pass
        UNSIGNED_PATH.write_text(json.dumps(unsigned, indent=2))

        # Sign (returns hex blob without 0x)
        try:
            blob_hex = sign_xrp_payment_tx(
                privkey_hex=acc["private_key"],
                account_address=account_addr,
                destination=destination,
                amount_drops=amount_drops,
                sequence=sequence_i,
                fee_drops=fee_i
            )
        except Exception as e:
            self._alert(f"XRP sign error:\n{e}"); return

        SIGNED_PATH.write_text(blob_hex + ("\n" if not blob_hex.endswith("\n") else ""))
        show_paged(self.sc, blob_hex, self.tf, self.bf, chunk_size=350)

    def _ask_receiver_xrp(self):
        btn_scan=pygame.Rect(16, self.sh-30, 120, 22)
        btn_manual=pygame.Rect(self.sw-140, self.sh-30, 120, 22)
        while True:
            self.sc.fill(WHITE)
            self.sc.blit(self.tf.render("XRP destination", True, BLACK),(8,6))
            self.sc.blit(self.bf.render("Choose input method", True, BLACK),(8,28))
            for r,l in ((btn_scan,"Scan QR (webcam)"), (btn_manual,"Manual Input")):
                pygame.draw.rect(self.sc,(220,220,220),r,border_radius=6)
                pygame.draw.rect(self.sc,OUT,r,1,border_radius=6)
                self.sc.blit(self.bf.render(l, True, BLACK),(r.x+6, r.y+2))
            pygame.display.flip()
            for ev in pygame.event.get():
                if ev.type==pygame.QUIT: return None
                if ev.type==pygame.MOUSEBUTTONDOWN and ev.button==1:
                    if btn_scan.collidepoint(ev.pos):
                        try:
                            data = QRScanner(self.sc, self.tf, self.bf).scan()
                        except TypeError:
                            data = QRScanner(self.sc).scan()
                        return data.strip() if data else None
                    if btn_manual.collidepoint(ev.pos):
                        addr = OnScreenKeyboard(self.sc, "").run()
                        return addr.strip() if addr else None
