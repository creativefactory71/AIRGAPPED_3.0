# main_wallet.py
# Unified entry for PC and Raspberry Pi (framebuffer + touch)
# - PIN gate (PBKDF2 via security/pin_store.py) on both PC & Pi
# - Multi-wallet aware flows (Send/Receive use active wallet)
# - Settings → Wallets, Networks, PIN & Security
# - Framebuffer-safe flushing (maps display.flip/update → flush() when headless)
# - Pi touch FIX: pass platform pump_input into all flows/managers/keyboards
# - NEW: consume flow return codes so Bottom Nav (Home/Opts/Back) works everywhere

import os, sys, json
import pygame
from pathlib import Path

from platforms.runtime import init_platform
from debug import dbg, set_kv, draw_overlay

# Flows
from flows.send_flow import SendFlow
from flows.receive_flow import ReceiveFlow

# Managers
from ui.wallet_manager import WalletManager
from ui.network_manager import NetworkManager
from ui.security_manager import SecurityManager  # PIN & Security

# PIN store (PBKDF2 verification compatible with your pin.json)
from security.pin_store import pin_present, verify_pin

# Optional: settings helper
try:
    from stores.settings import get_display_mode as _get_mode_from_store  # type: ignore
except Exception:
    _get_mode_from_store = None

# Keyboards
from ui.numeric_keyboard import NumericKeyboard
from ui.on_screen_keyboard import OnScreenKeyboard


# ---------------- Settings ----------------
SETTINGS_PATH = Path("settings.json")

def _load_settings() -> dict:
    d = {"ui_mode": "grid", "theme": "classic"}  # default
    if SETTINGS_PATH.exists():
        try:
            d.update(json.loads(SETTINGS_PATH.read_text() or "{}"))
        except Exception:
            pass
    return d

def _save_settings(d: dict):
    try:
        SETTINGS_PATH.write_text(json.dumps(d, indent=2))
    except Exception:
        pass

def _get_display_mode(settings_obj) -> str:
    if _get_mode_from_store:
        try:
            return _get_mode_from_store(settings_obj)
        except Exception:
            pass
    return (settings_obj or {}).get("ui_mode", "grid")


# ---------------- Colors & fonts ----------------
PALETTES = {
    "classic": {"bg": (245,245,245), "fg": (0,0,0), "accent": (0,122,204), "tile": (230,230,230)},
    "dark":    {"bg": (20,20,22),    "fg": (240,240,240), "accent": (10,132,255), "tile": (40,40,42)},
    "contrast":{"bg": (255,255,255), "fg": (0,0,0), "accent": (200,0,0), "tile": (230,230,230)},
}

def _make_fonts():
    pygame.font.init()
    try:
        title = pygame.font.SysFont("Verdana", 20, bold=True)
        body  = pygame.font.SysFont("Verdana", 14)
        small = pygame.font.SysFont("Verdana", 12)
    except Exception:
        title = pygame.font.Font(None, 20)
        body  = pygame.font.Font(None, 14)
        small = pygame.font.Font(None, 12)
    return title, body, small


# ---------------- Renderer ----------------
class Renderer:
    """Minimal renderer with bottom nav and 3 modes (grid/list/compact)."""
    def __init__(self, screen, settings: dict, palette: dict, title_font, body_font, small_font):
        self.screen = screen
        self.settings = settings
        self.palette = palette
        self.tf, self.bf, self.sf = title_font, body_font, small_font
        self.w, self.h = screen.get_size()
        self.nav_back  = pygame.Rect(4,  self.h-24, 52, 20)
        self.nav_home  = pygame.Rect((self.w//2)-26, self.h-24, 52, 20)
        self.nav_opts  = pygame.Rect(self.w-56, self.h-24, 52, 20)

    def draw_bottom_nav(self):
        fg = self.palette["fg"]; tile = self.palette["tile"]
        for rect, label in ((self.nav_back,"Back"), (self.nav_home,"Home"), (self.nav_opts,"Opts")):
            pygame.draw.rect(self.screen, tile, rect, border_radius=6)
            pygame.draw.rect(self.screen, fg, rect, 1, border_radius=6)
            self.screen.blit(self.sf.render(label, True, fg), (rect.x+8, rect.y+2))

    def bottom_hit(self, pos):
        if self.nav_back.collidepoint(pos): return "back"
        if self.nav_home.collidepoint(pos): return "home"
        if self.nav_opts.collidepoint(pos): return "opts"
        return None

    def draw_menu(self, title: str, items: list[str], mode: str):
        self.screen.fill(self.palette["bg"])
        fg = self.palette["fg"]
        # title
        self.screen.blit(self.tf.render(title, True, fg), (8, 6))
        rects = []
        if (mode or "").lower() == "grid":
            cols, rows = 2, 3
            pad_x, pad_y = 10, 8
            tile_w = (self.w - pad_x* (cols+1)) // cols
            tile_h = (self.h - 48 - pad_y* (rows+1)) // rows
            y0 = 28
            idx = 0
            for r in range(rows):
                for c in range(cols):
                    if idx >= len(items): break
                    x = pad_x + c*(tile_w + pad_x)
                    y = y0 + r*(tile_h + pad_y)
                    rect = pygame.Rect(x, y, tile_w, tile_h)
                    pygame.draw.rect(self.screen, self.palette["tile"], rect, border_radius=10)
                    pygame.draw.rect(self.screen, fg, rect, 1, border_radius=10)
                    label = self.bf.render(items[idx], True, fg)
                    self.screen.blit(label, (rect.centerx - label.get_width()//2,
                                             rect.centery - label.get_height()//2))
                    rects.append(rect); idx += 1
        elif (mode or "").lower() == "compact":
            y = 28
            for it in items:
                rect = pygame.Rect(8, y, self.w-16, 26)
                pygame.draw.rect(self.screen, self.palette["tile"], rect, border_radius=8)
                pygame.draw.rect(self.screen, fg, rect, 1, border_radius=8)
                self.screen.blit(self.bf.render(it, True, fg), (rect.x+8, rect.y+5))
                rects.append(rect)
                y += 28
        else:  # list
            y = 28
            for it in items:
                rect = pygame.Rect(8, y, self.w-16, 34)
                pygame.draw.rect(self.screen, self.palette["tile"], rect, border_radius=10)
                pygame.draw.rect(self.screen, fg, rect, 1, border_radius=10)
                self.screen.blit(self.bf.render(it, True, fg), (rect.x+8, rect.y+8))
                rects.append(rect)
                y += 38

        self.draw_bottom_nav()
        pygame.display.update()
        return rects

    @staticmethod
    def hit_test(rects, pos):
        for i, r in enumerate(rects):
            if r.collidepoint(pos): return i
        return None


# ---------------- App ----------------
class App:
    def __init__(self):
        self.screen, self.pump_input, self.flush, self.shutdown = init_platform()
        self.title_font, self.body_font, self.small_font = _make_fonts()

        self.settings = _load_settings()
        theme_key = self.settings.get("theme", "classic")
        self.palette = PALETTES.get(theme_key, PALETTES["classic"])

        self.renderer = Renderer(self.screen, self.settings, self.palette,
                                 self.title_font, self.body_font, self.small_font)

        self._patch_display_for_headless()
        self.clock = pygame.time.Clock()
        self.running = True

        dbg(f"PIN file present: {Path('pin.json').exists()}")

    def _patch_display_for_headless(self):
        """If no SDL window exists (dummy driver), route display.flip/update to self.flush()."""
        headless = (pygame.display.get_surface() is None)
        if not headless:
            return
        _flush = self.flush
        def _flip(): _flush()
        def _update(rect=None): _flush(rect)
        pygame.display.flip = _flip          # type: ignore[attr-defined]
        pygame.display.update = _update      # type: ignore[attr-defined]
        dbg("Headless mode: patched pygame.display.flip/update → flush()")

    # ----- helpers -----
    @staticmethod
    def _clear_pointer_queue():
        """Prevent phantom taps: clear mouse/touch queue when entering modal UIs (PIN/Keyboards)."""
        cleared = pygame.event.clear([pygame.MOUSEBUTTONDOWN, pygame.MOUSEBUTTONUP, pygame.MOUSEMOTION])
        if cleared:
            dbg(f"Debounced {len(cleared)} pointer events")

    def _run_numeric_keyboard(self, title: str, initial: str = "", mask: bool = False) -> str | None:
        """Run NumericKeyboard; pass pump_input if supported to enable touch on Pi."""
        self._clear_pointer_queue()
        try:
            val = NumericKeyboard(self.screen, title, initial, pump_input=self.pump_input, mask=mask).run()
        except TypeError:
            val = NumericKeyboard(self.screen, title, initial).run()
        return val

    # ----- PIN gate -----
    def _pin_gate(self) -> bool:
        must_flag = self.settings.get("pin_required", None)
        require = pin_present() if must_flag is None else bool(must_flag)
        if not require:
            return True

        tries = 3
        while tries > 0:
            pin = self._run_numeric_keyboard("Enter PIN", "", mask=True)
            if pin and verify_pin(pin):
                dbg("PIN OK"); return True
            tries -= 1
            dbg(f"PIN FAIL ({3-tries}/3)")
            self._toast(f"Wrong PIN ({3-tries}/3)")
            pygame.time.delay(400)
        return False

    # ----- Screens -----
    def _home_menu(self):
        mode = _get_display_mode(self.renderer.settings)
        items = ["Send", "Receive", "Settings", "Exit"]
        rects = self.renderer.draw_menu("Wallet", items, mode)
        dbg("STATE → HOME"); set_kv("state","HOME")
        draw_overlay(self.screen, self.clock.get_fps()); self.flush()
        return items, rects

    def _settings_menu(self):
        modes = ["LIST", "GRID", "COMPACT"]
        themes = list(PALETTES.keys())
        mode = _get_display_mode(self.renderer.settings)
        curr_theme = self.settings.get("theme", "classic")

        items = [
            f"UI Mode: {mode}",
            f"Theme: {curr_theme}",
            "Wallets",
            "Networks",
            "PIN & Security",
            "Back"
        ]
        rects = self.renderer.draw_menu("Settings", items, mode)
        dbg(f"STATE → SETTINGS (mode={mode}, theme={curr_theme})"); set_kv("state","SETTINGS")
        draw_overlay(self.screen, self.clock.get_fps()); self.flush()

        while True:
            self.pump_input()
            for ev in pygame.event.get():
                if ev.type == pygame.QUIT:
                    self.running = False; return
                if ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 1:
                    bh = self.renderer.bottom_hit(ev.pos)
                    if bh in ("back","home"): return
                    hit = self.renderer.hit_test(rects, ev.pos)
                    if hit is None: break

                    if hit == 0:  # UI Mode cycle
                        cur = _get_display_mode(self.renderer.settings).upper()
                        nxt = modes[(modes.index(cur)+1)%len(modes)] if cur in modes else "GRID"
                        self.settings["ui_mode"] = nxt.lower(); _save_settings(self.settings)
                        dbg(f"SET ui_mode → {nxt.lower()}")
                    elif hit == 1:  # Theme cycle
                        cur = self.settings.get("theme", "classic")
                        nxt = themes[(themes.index(cur)+1)%len(themes)] if cur in themes else "classic"
                        self.settings["theme"] = nxt; _save_settings(self.settings)
                        self.palette = PALETTES.get(nxt, PALETTES["classic"])
                        self.renderer.palette = self.palette
                        dbg(f"SET theme → {nxt}")
                    elif hit == 2:  # Wallets manager
                        WalletManager(self.screen, self.renderer,
                                      self.title_font, self.body_font, self.small_font,
                                      self._toast, pump_input=self.pump_input).run()
                    elif hit == 3:  # Networks manager
                        NetworkManager(self.screen, self.renderer,
                                       self.title_font, self.body_font, self.small_font,
                                       self._toast, pump_input=self.pump_input).run()
                    elif hit == 4:  # PIN & Security
                        SecurityManager(self.screen, self.renderer,
                                        self.title_font, self.body_font, self.small_font,
                                        self._toast, pump_input=self.pump_input).run()
                    elif hit == 5:  # Back
                        return

                    # redraw after change
                    mode = _get_display_mode(self.renderer.settings)
                    items = [f"UI Mode: {self.settings.get('ui_mode','grid')}",
                             f"Theme: {self.settings.get('theme','classic')}",
                             "Wallets","Networks","PIN & Security","Back"]
                    rects = self.renderer.draw_menu("Settings", items, mode)
                    draw_overlay(self.screen, self.clock.get_fps()); self.flush()

            draw_overlay(self.screen, self.clock.get_fps()); self.flush()
            self.clock.tick(30)

    def _run_send(self):
        dbg("STATE → SEND"); set_kv("state","SEND")
        nav = SendFlow(self.screen, self.renderer, None, self.title_font, self.body_font,
                       pump_input=self.pump_input).run()
        if nav == "SETTINGS":
            self._settings_menu()
        # For "HOME" or None, caller (main loop) will redraw home next iteration

    def _run_receive(self):
        dbg("STATE → RECEIVE"); set_kv("state","RECEIVE")
        nav = ReceiveFlow(self.screen, self.renderer, self.title_font, self.body_font,
                          pump_input=self.pump_input).run()
        if nav == "SETTINGS":
            self._settings_menu()
        # For "HOME" or None, caller (main loop) will redraw home next iteration

    def _toast(self, text, ms=900):
        overlay = pygame.Surface((self.screen.get_width(), 22))
        overlay.fill((240,240,240))
        self.screen.blit(overlay, (0, self.screen.get_height()-22))
        self.screen.blit(self.small_font.render(text, True, (0,0,0)),
                         (6, self.screen.get_height()-18))
        draw_overlay(self.screen, self.clock.get_fps()); self.flush()
        pygame.time.delay(ms)

    # ----- main loop -----
    def run(self):
        if not self._pin_gate():
            self.shutdown(); return

        while self.running:
            items, rects = self._home_menu()
            while self.running:
                self.pump_input()
                for ev in pygame.event.get():
                    if ev.type == pygame.QUIT:
                        self.running = False
                    elif ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 1:
                        bh = self.renderer.bottom_hit(ev.pos)
                        if bh == "back":
                            pass  # no-op on home
                        elif bh == "home":
                            pass  # already home
                        elif bh == "opts":
                            self._settings_menu()
                            items, rects = self._home_menu()
                            continue
                        hit = self.renderer.hit_test(rects, ev.pos)
                        if hit is None: continue
                        label = items[hit].lower()
                        if label == "send":
                            self._run_send(); items, rects = self._home_menu()
                        elif label == "receive":
                            self._run_receive(); items, rects = self._home_menu()
                        elif label == "settings":
                            self._settings_menu(); items, rects = self._home_menu()
                        elif label == "exit":
                            self.running = False
                draw_overlay(self.screen, self.clock.get_fps()); self.flush()
                self.clock.tick(30)
        self.shutdown()


if __name__ == "__main__":
    try:
        App().run()
    except KeyboardInterrupt:
        dbg("KeyboardInterrupt: exiting", level="WARN")
        try: pygame.event.pump()
        except Exception: pass
        sys.exit(0)
