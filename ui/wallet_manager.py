# ui/wallet_manager.py
from __future__ import annotations
import time, json, random, hashlib
import pygame

from stores.wallet_store import (
    list_wallet_names, active_name, set_active,
    rename_wallet, delete_wallet, create_wallet_file
)
from stores.network_store import list_networks
from security.pin_store import verify_pin

# Optional engine for derivations (preferred if available)
try:
    from wallet_engine import WalletEngine  # your engine
except Exception:
    WalletEngine = None

# Keyboards
from ui.on_screen_keyboard import OnScreenKeyboard
from ui.numeric_keyboard import NumericKeyboard

# BIP helpers
try:
    from bip_utils import (
        Bip39MnemonicGenerator, Bip39WordsNum, Bip39MnemonicValidator, Bip39SeedGenerator,
        Bip44, Bip44Coins, Bip44Changes,
        Bip84, Bip84Coins,
    )
    _HAS_BIP = True
except Exception:
    _HAS_BIP = False

# minimal base58 for WIF (avoid extra deps)
_B58_ALPH = b"123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"
def _b58encode(b: bytes) -> str:
    n = int.from_bytes(b, "big")
    res = bytearray()
    while n > 0:
        n, r = divmod(n, 58)
        res.append(_B58_ALPH[r])
    # leading zero bytes
    pad = 0
    for c in b:
        if c == 0: pad += 1
        else: break
    return (b"1" * pad + res[::-1]).decode()

def _to_wif(priv32: bytes, compressed=True, mainnet=True) -> str:
    prefix = b"\x80" if mainnet else b"\xef"
    payload = prefix + priv32 + (b"\x01" if compressed else b"")
    chk = hashlib.sha256(hashlib.sha256(payload).digest()).digest()[:4]
    return _b58encode(payload + chk)


class WalletManager:
    """Settings → Wallets manager with full Add Wallet wizard (Create / Restore).
       Pi touch friendly: accepts pump_input and calls it every frame."""
    def __init__(self, screen, renderer, title_font, body_font, small_font, toast_cb, pump_input=None):
        self.sc=screen; self.r=renderer; self.tf=title_font; self.bf=body_font; self.sf=small_font
        self.toast = toast_cb
        self.w, self.h = screen.get_size()
        self.pump_input = pump_input
        self._down = None
        self._ignore_until = 0.0
        self._engine = WalletEngine() if WalletEngine else None

    # ---------- small utils ----------
    def _pump(self):
        if self.pump_input: self.pump_input()

    def _debounce_on_entry(self):
        cleared = pygame.event.clear([pygame.MOUSEBUTTONDOWN, pygame.MOUSEBUTTONUP, pygame.MOUSEMOTION])
        if cleared: pass
        self._ignore_until = time.time() + 0.15

    def _osk(self, title, initial=""):
        try:
            return OnScreenKeyboard(self.sc, title, initial, pump_input=self.pump_input).run()
        except TypeError:
            return OnScreenKeyboard(self.sc, title, initial).run()

    def _nk(self, title, initial=""):
        try:
            return NumericKeyboard(self.sc, title, initial, pump_input=self.pump_input).run()
        except TypeError:
            return NumericKeyboard(self.sc, title, initial).run()

    def _alert(self, msg: str):
        self._pump()
        self.sc.fill((255,255,255))
        self.sc.blit(self.tf.render("Notice", True, (0,0,0)), (8,6))
        y=34
        for line in str(msg).split("\n"):
            self.sc.blit(self.bf.render(line, True, (0,0,0)), (8,y)); y+=16
        btn=pygame.Rect(self.w-60, self.h-26, 52, 20)
        pygame.draw.rect(self.sc, (220,220,220), btn, border_radius=6)
        pygame.draw.rect(self.sc, (0,0,0), btn, 1, border_radius=6)
        self.sc.blit(self.bf.render("OK", True, (0,0,0)), (btn.x+14, btn.y+2))
        pygame.display.update()
        while True:
            self._pump()
            for ev in pygame.event.get():
                if ev.type==pygame.QUIT: return
                if ev.type==pygame.MOUSEBUTTONDOWN and ev.button==1 and btn.collidepoint(ev.pos): return
            pygame.time.Clock().tick(30)

    # ---------- main list ----------
    def _draw(self):
        items = [f"[Active] {n}" if n==active_name() else n for n in list_wallet_names()]
        items += ["Add Wallet", "Rename Wallet", "Delete Wallet", "Back"]
        rects = self.r.draw_menu("Wallets", items, self.r.settings.get("ui_mode","grid"))
        pygame.display.update()
        return items, rects

    def run(self):
        self._debounce_on_entry()
        while True:
            self._pump()
            items, rects = self._draw()
            for ev in pygame.event.get():
                if ev.type==pygame.QUIT: return
                if ev.type==pygame.MOUSEBUTTONDOWN and ev.button==1:
                    if time.time() < self._ignore_until: continue
                    self._down = self.r.hit_test(rects, ev.pos)
                if ev.type==pygame.MOUSEBUTTONUP and ev.button==1:
                    up = self.r.hit_test(rects, ev.pos)
                    if self._down is not None and up == self._down:
                        label = items[up]
                        if label.endswith("Back"): return
                        if label.startswith("[Active]"):
                            pass
                        elif label == "Add Wallet":
                            self._add_wallet_wizard()
                        elif label == "Rename Wallet":
                            name = self._pick_wallet("Rename which?")
                            if not name: break
                            new = self._osk(f"New name for {name}", "")
                            if not new: break
                            try: rename_wallet(name, new); self.toast("Renamed")
                            except Exception as e: self.toast(str(e))
                        elif label == "Delete Wallet":
                            name = self._pick_wallet("Delete which?")
                            if not name: break
                            if name == active_name():
                                self.toast("Cannot delete active wallet"); break
                            pin = self._nk("Enter PIN to delete", "")
                            if not pin or not verify_pin(pin):
                                self.toast("PIN wrong"); break
                            try: delete_wallet(name); self.toast("Deleted")
                            except Exception as e: self.toast(str(e))
                        else:
                            # set active
                            n = label.replace("[Active] ","")
                            try: set_active(n); self.toast(f"Active → {n}")
                            except Exception as e: self.toast(str(e))
                    self._down = None
            pygame.time.Clock().tick(30)

    def _pick_wallet(self, title="Select Wallet"):
        self._debounce_on_entry()
        names = list_wallet_names()
        rects = self.r.draw_menu(title, names+["Back"], self.r.settings.get("ui_mode","grid"))
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
                        if up == len(names): return None
                        return names[up]
                    down = None
            pygame.time.Clock().tick(30)

    # ---------- Add Wallet Wizard ----------
    def _add_wallet_wizard(self):
        self._debounce_on_entry()
        items = ["Create", "Restore", "Back"]
        rects = self.r.draw_menu("Add Wallet", items, self.r.settings.get("ui_mode","grid"))
        pygame.display.update()

        down=None
        while True:
            self._pump()
            for ev in pygame.event.get():
                if ev.type==pygame.QUIT: return
                if ev.type==pygame.MOUSEBUTTONDOWN and ev.button==1:
                    if time.time() < self._ignore_until: continue
                    down = self.r.hit_test(rects, ev.pos)
                if ev.type==pygame.MOUSEBUTTONUP and ev.button==1:
                    up = self.r.hit_test(rects, ev.pos)
                    if down is not None and up == down:
                        if up == 0: self._create_flow(); return
                        if up == 1: self._restore_flow(); return
                        return
                    down=None
            pygame.time.Clock().tick(30)

    # ---- Create (with 12/24 selection) ----
    def _create_flow(self):
        # 1) Ask wallet name
        name = (self._osk("Wallet name", "") or "").strip()
        if not name: return

        # 2) Choose words: 12 or 24 (no default)
        count = self._choose_words_num()
        if count not in (12, 24): return

        # 3) Generate mnemonic with chosen length
        if not _HAS_BIP:
            self._alert("bip_utils not installed; cannot generate BIP39 seed.")
            return
        words_num = Bip39WordsNum.WORDS_NUM_12 if count == 12 else Bip39WordsNum.WORDS_NUM_24
        mnemonic = str(Bip39MnemonicGenerator().FromWordsNumber(words_num))
        words = mnemonic.split()

        # 4) Show seed with numbering (6/pg) & confirm
        if not self._show_seed_words_and_confirm(words):
            return

        # 5) Quiz 6 random positions
        if not self._quiz_seed(words, count=6):
            self._alert("Seed quiz failed. Aborting create."); return

        # 6) Derive accounts
        accounts = self._derive_accounts(mnemonic)

        # 7) Save wallet
        wallet_obj = {
            "name": name,
            "seed_phrase": mnemonic,
            "accounts": accounts,
            "created_at": int(time.time())
        }
        try:
            create_wallet_file(name, wallet_obj)
            set_active(name)
            self.toast(f"Created & Active → {name}")
        except Exception as e:
            self._alert(f"Save error:\n{e}")

    def _choose_words_num(self) -> int | None:
        self._debounce_on_entry()
        labels = ["12 words", "24 words", "Back"]
        rects = self.r.draw_menu("Words count", labels, self.r.settings.get("ui_mode","grid"))
        pygame.display.update()
        down=None
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
                        if up == 0: return 12
                        if up == 1: return 24
                        return None
                    down=None
            pygame.time.Clock().tick(30)

    # ---- Restore ----
    def _restore_flow(self):
        # 1) Ask wallet name
        name = (self._osk("Wallet name", "") or "").strip()
        if not name: return

        # 2) Seed entry (space-separated), accept 12 or 24
        phrase = (self._osk("Enter seed (12/24 words)", "") or "").strip().lower()
        words = [w for w in phrase.split() if w]
        if len(words) not in (12, 24):
            self._alert("Expected 12 or 24 words."); return
        if _HAS_BIP:
            try:
                Bip39MnemonicValidator(words).Validate()
            except Exception as e:
                self._alert(f"Mnemonic invalid:\n{e}"); return
        mnemonic = " ".join(words)

        # 3) Confirm
        if not self._confirm_dialog("Use this seed?", mnemonic):
            return

        # 4) Derive accounts
        accounts = self._derive_accounts(mnemonic)

        # 5) Save
        wallet_obj = {
            "name": name,
            "seed_phrase": mnemonic,
            "accounts": accounts,
            "created_at": int(time.time())
        }
        try:
            create_wallet_file(name, wallet_obj)
            set_active(name)
            self.toast(f"Restored & Active → {name}")
        except Exception as e:
            self._alert(f"Save error:\n{e}")

    # ---------- Seed display & quiz ----------
    def _show_seed_words_and_confirm(self, words: list[str]) -> bool:
        """Show words with numbering, 6 per page, with Next/Prev/Confirm."""
        self._debounce_on_entry()
        idx = 0
        pages = [words[i:i+6] for i in range(0,len(words),6)]
        btn_prev = pygame.Rect(6, self.h-26, 52, 20)
        btn_next = pygame.Rect(62, self.h-26, 52, 20)
        btn_ok   = pygame.Rect(self.w-60, self.h-26, 52, 20)
        down = None

        while True:
            self._pump()
            self.sc.fill((255,255,255))
            self.sc.blit(self.tf.render("Write down your seed", True, (0,0,0)), (8,6))
            self.sc.blit(self.bf.render(f"Page {idx+1}/{len(pages)}", True, (0,0,0)), (8, 26))

            y = 46
            for i, w in enumerate(pages[idx], start=idx*6+1):
                self.sc.blit(self.bf.render(f"{i:2d}. {w}", True, (0,0,0)), (16, y))
                y += 18

            for r,l in ((btn_prev,"Prev"),(btn_next,"Next"),(btn_ok,"Confirm")):
                pygame.draw.rect(self.sc,(230,230,230),r,border_radius=6)
                pygame.draw.rect(self.sc,(0,0,0),r,1,border_radius=6)
                t=self.bf.render(l, True, (0,0,0))
                self.sc.blit(t,(r.centerx-t.get_width()//2,r.centery-t.get_height()//2))

            pygame.display.update()

            for ev in pygame.event.get():
                if ev.type==pygame.QUIT: return False
                if ev.type==pygame.MOUSEBUTTONDOWN and ev.button==1:
                    if time.time() < self._ignore_until: continue
                    if btn_prev.collidepoint(ev.pos): down="prev"
                    elif btn_next.collidepoint(ev.pos): down="next"
                    elif btn_ok.collidepoint(ev.pos):   down="ok"
                    else: down=None
                if ev.type==pygame.MOUSEBUTTONUP and ev.button==1:
                    up=("prev" if btn_prev.collidepoint(ev.pos)
                        else "next" if btn_next.collidepoint(ev.pos)
                        else "ok" if btn_ok.collidepoint(ev.pos) else None)
                    if down and up==down:
                        if up=="prev": idx=(idx-1)%len(pages)
                        elif up=="next": idx=(idx+1)%len(pages)
                        elif up=="ok":   return True
                    down=None
            pygame.time.Clock().tick(30)

    def _quiz_seed(self, words: list[str], count=6) -> bool:
        n = len(words)
        picks = sorted(random.sample(range(n), k=min(count,n)))
        for i in picks:
            ans = (self._osk(f"Enter word #{i+1}", "") or "").strip().lower()
            if ans != words[i].lower():
                return False
        return True

    def _confirm_dialog(self, title: str, body: str) -> bool:
        self._debounce_on_entry()
        btn_yes = pygame.Rect(self.w-120, self.h-26, 52, 20)
        btn_no  = pygame.Rect(self.w-60,  self.h-26, 52, 20)
        down=None
        while True:
            self._pump()
            self.sc.fill((255,255,255))
            self.sc.blit(self.tf.render(title, True, (0,0,0)), (8,6))
            y=28
            text = body.strip().split()
            line=""
            for w in text:
                if len(line)+1+len(w) > 28:
                    self.sc.blit(self.bf.render(line, True, (0,0,0)), (8,y)); y+=16; line=w
                else:
                    line = w if not line else f"{line} {w}"
            if line: self.sc.blit(self.bf.render(line, True, (0,0,0)), (8,y)); y+=16

            for r,l in ((btn_yes,"Yes"),(btn_no,"No")):
                pygame.draw.rect(self.sc,(230,230,230),r,border_radius=6)
                pygame.draw.rect(self.sc,(0,0,0),r,1,border_radius=6)
                t=self.bf.render(l, True, (0,0,0))
                self.sc.blit(t,(r.centerx-t.get_width()//2,r.centery-t.get_height()//2))
            pygame.display.update()

            for ev in pygame.event.get():
                if ev.type==pygame.QUIT: return False
                if ev.type==pygame.MOUSEBUTTONDOWN and ev.button==1:
                    if time.time() < self._ignore_until: continue
                    if btn_yes.collidepoint(ev.pos): down="yes"
                    elif btn_no.collidepoint(ev.pos): down="no"
                    else: down=None
                if ev.type==pygame.MOUSEBUTTONUP and ev.button==1:
                    up=("yes" if btn_yes.collidepoint(ev.pos) else
                        "no"  if btn_no.collidepoint(ev.pos)  else None)
                    if down and up==down:
                        return (up=="yes")
                    down=None
            pygame.time.Clock().tick(30)

    # ---------- Derivations ----------
    def _derive_accounts(self, mnemonic: str) -> list[dict]:
        """
        Try engine first; else derive using bip_utils per network type:
          - EVM  : m/44'/60'/0'/0/0 (address = EIP-55)
          - UTXO : P2WPKH -> BIP84 (m/84'/0'/0'/0/0),
                   P2PKH  -> BIP44 (m/44'/0'/0'/0/0)
          - XRP  : m/44'/144'/0'/0/0 (classic r-addr)
        Store: address, public_key (hex uncompressed where relevant), private_key (hex, no 0x)
               For BTC also store private_key_wif (compressed).
        """
        nets = list_networks()
        out = []

        # Preferred: your engine does it
        if self._engine and hasattr(self._engine, "derive_account"):
            for n in nets:
                try:
                    a = self._engine.derive_account(network=n, index=0, mnemonic=mnemonic)
                    out.append({
                        "network_key": n["key"],
                        "address": a.get("address",""),
                        "public_key": a.get("public_key",""),
                        "private_key": a.get("private_key",""),
                        **({"private_key_wif": a.get("private_key_wif","")} if "private_key_wif" in a else {})
                    }); continue
                except Exception:
                    pass  # fall through to bip_utils
        # Engine type-specific methods?
        elif self._engine:
            for n in nets:
                t = (n.get("type") or "").lower()
                try:
                    if t == "evm" and hasattr(self._engine,"derive_evm"):
                        a = self._engine.derive_evm(mnemonic, n, index=0)
                    elif t == "utxo" and hasattr(self._engine,"derive_utxo"):
                        a = self._engine.derive_utxo(mnemonic, n, index=0)
                    elif t == "xrp" and hasattr(self._engine,"derive_xrp"):
                        a = self._engine.derive_xrp(mnemonic, n, index=0)
                    else:
                        raise RuntimeError("engine missing method")
                    out.append({
                        "network_key": n["key"],
                        "address": a.get("address",""),
                        "public_key": a.get("public_key",""),
                        "private_key": a.get("private_key",""),
                        **({"private_key_wif": a.get("private_key_wif","")} if "private_key_wif" in a else {})
                    }); continue
                except Exception:
                    pass  # fallback to bip_utils

        # Fallback: bip_utils (must be installed)
        if _HAS_BIP:
            seed = Bip39SeedGenerator(mnemonic).Generate()
            for n in nets:
                typ = (n.get("type") or "").lower()
                if typ == "evm":
                    try:
                        ctx = Bip44.FromSeed(seed, Bip44Coins.ETHEREUM)
                        acc = ctx.Purpose().Coin().Account(0).Change(Bip44Changes.CHAIN_EXT).AddressIndex(0)
                        priv_hex = acc.PrivateKey().Raw().ToHex()
                        pub_hex  = acc.PublicKey().RawUncompressed().ToHex()[2:]  # drop 0x04
                        addr     = acc.PublicKey().ToAddress()
                        out.append({
                            "network_key": n["key"],
                            "address": addr,
                            "public_key": pub_hex,
                            "private_key": priv_hex
                        }); continue
                    except Exception:
                        pass
                elif typ == "utxo":
                    at = (n.get("address_type") or "P2WPKH").upper()
                    try:
                        if at == "P2PKH":
                            b = Bip44.FromSeed(seed, Bip44Coins.BITCOIN)
                            acc = b.Purpose().Coin().Account(0).Change(Bip44Changes.CHAIN_EXT).AddressIndex(0)
                        else:  # P2WPKH default
                            b = Bip84.FromSeed(seed, Bip84Coins.BITCOIN)
                            acc = b.Purpose().Coin().Account(0).Change(Bip44Changes.CHAIN_EXT).AddressIndex(0)
                        priv_bytes = bytes.fromhex(acc.PrivateKey().Raw().ToHex())
                        wif = _to_wif(priv_bytes, compressed=True, mainnet=True)
                        pub_hex = acc.PublicKey().RawCompressed().ToHex()
                        addr = acc.PublicKey().ToAddress()
                        out.append({
                            "network_key": n["key"],
                            "address": addr,
                            "public_key": pub_hex,
                            "private_key": priv_bytes.hex(),
                            "private_key_wif": wif
                        }); continue
                    except Exception:
                        pass
                elif typ == "xrp":
                    try:
                        b = Bip44.FromSeed(seed, Bip44Coins.RIPPLE)
                        acc = b.Purpose().Coin().Account(0).Change(Bip44Changes.CHAIN_EXT).AddressIndex(0)
                        priv_hex = acc.PrivateKey().Raw().ToHex()
                        pub_hex  = acc.PublicKey().RawCompressed().ToHex()
                        addr     = acc.PublicKey().ToAddress()
                        out.append({
                            "network_key": n["key"],
                            "address": addr,
                            "public_key": pub_hex,
                            "private_key": priv_hex
                        }); continue
                    except Exception:
                        pass

        # If any network failed all routes, still include placeholder to keep schema consistent
        keys_in_out = {a["network_key"] for a in out}
        for n in nets:
            if n["key"] not in keys_in_out:
                out.append({
                    "network_key": n["key"],
                    "address": "",
                    "public_key": "",
                    "private_key": ""
                })
        return out
