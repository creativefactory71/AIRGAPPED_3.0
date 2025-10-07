# ui_modes_demo.py
import pygame
from ui.theme_store import get_ui_mode, theme_color, theme_radius

NAV_H = 22   # bottom navigation bar height
TITLE_H = 22 # title bar height

class AppRenderer:
    def __init__(self, screen):
        self.screen = screen
        self.settings = {"mode": get_ui_mode()}  # 'list' | 'grid' | 'compact'
        self._last_item_rects = []
        self._nav_rects = {}
        self._title_rect = None

    # ---------- public ----------
    def draw_menu(self, title, items, mode_from_settings: str):
        # honor mode coming from settings store
        self.settings["mode"] = (mode_from_settings or self.settings["mode"]).lower()
        sw, sh = self.screen.get_size()
        bg, fg, card, border = theme_color("bg"), theme_color("fg"), theme_color("card"), theme_color("border")
        radius = theme_radius()

        # clear
        self.screen.fill(bg)

        # title
        font = pygame.font.SysFont("dejavusans", 16, bold=True)
        title_surf = font.render(title, True, fg)
        self._title_rect = pygame.Rect(0, 0, sw, TITLE_H)
        self.screen.blit(title_surf, (8, 4))

        # content bounds (reserve bottom nav)
        content = pygame.Rect(0, TITLE_H, sw, sh - TITLE_H - NAV_H)

        # layout
        if self.settings["mode"] == "list":
            rects = self._layout_list(items, content, radius, card, border, fg)
        elif self.settings["mode"] == "compact":
            rects = self._layout_list(items, content, radius, card, border, fg, compact=True)
        else:
            rects = self._layout_grid(items, content, radius, card, border, fg)  # default grid

        self._last_item_rects = rects
        # bottom bar
        self.draw_bottom_bar()
        pygame.display.flip()
        return rects

    def hit_test(self, rects, pos):
        if not rects: return None
        for i, r in enumerate(rects):
            if r.collidepoint(pos): return i
        return None

    # bottom bar utilities
    def draw_bottom_bar(self):
        sw, sh = self.screen.get_size()
        card, border, fg, acc, acc_fg = theme_color("card"), theme_color("border"), theme_color("fg"), theme_color("accent"), theme_color("accent_fg")
        bar = pygame.Rect(0, sh - NAV_H, sw, NAV_H)
        pygame.draw.rect(self.screen, card, bar)
        pygame.draw.line(self.screen, border, (0, sh - NAV_H - 1), (sw, sh - NAV_H - 1))

        w = sw // 3
        r_back = pygame.Rect(0, sh - NAV_H, w, NAV_H)
        r_home = pygame.Rect(w, sh - NAV_H, w, NAV_H)
        r_opt  = pygame.Rect(2*w, sh - NAV_H, w, NAV_H)

        self._nav_rects = {"back": r_back, "home": r_home, "options": r_opt}

        def draw_btn(rect, label):
            pygame.draw.rect(self.screen, acc, rect, border_radius=theme_radius())
            txt = pygame.font.SysFont("dejavusans", 12).render(label, True, acc_fg)
            self.screen.blit(txt, (rect.x + (rect.w - txt.get_width())//2, rect.y + 3))

        draw_btn(r_back, "Back")
        draw_btn(r_home, "Home")
        draw_btn(r_opt,  "Options")

    def bottom_hit(self, pos):
        for k, r in self._nav_rects.items():
            if r.collidepoint(pos): return k
        return None

    # ---------- private layouts ----------
    def _layout_list(self, items, content, radius, card, border, fg, compact=False):
        # line height
        lh = 28 if not compact else 22
        gap = 6 if not compact else 4
        y = content.y + 4
        font = pygame.font.SysFont("dejavusans", 12)
        rects = []
        for it in items:
            r = pygame.Rect(content.x + 8, y, content.w - 16, lh)
            pygame.draw.rect(self.screen, card, r, border_radius=radius)
            pygame.draw.rect(self.screen, border, r, 1, border_radius=radius)
            self.screen.blit(font.render(str(it), True, fg), (r.x + 8, r.y + (lh-16)//2))
            rects.append(r)
            y += lh + gap
        return rects

    def _layout_grid(self, items, content, radius, card, border, fg):
        # fixed 3 rows x 2 cols, centered vertically
        rows, cols = 3, 2
        pad = 8
        # compute tile size
        tile_w = (content.w - pad*(cols+1)) // cols
        tile_h = (content.h - pad*(rows+1)) // rows
        # center grid vertically
        used_h = rows*tile_h + pad*(rows+1)
        y0 = content.y + (content.h - used_h)//2
        font = pygame.font.SysFont("dejavusans", 12)
        rects = []
        i = 0
        for r in range(rows):
            for c in range(cols):
                if i >= len(items): break
                x = content.x + pad + c*(tile_w + pad)
                y = y0 + pad + r*(tile_h + pad)
                R = pygame.Rect(x, y, tile_w, tile_h)
                pygame.draw.rect(self.screen, card, R, border_radius=radius)
                pygame.draw.rect(self.screen, border, R, 1, border_radius=radius)
                label = str(items[i])
                txt = font.render(label, True, fg)
                self.screen.blit(txt, (R.x + (R.w - txt.get_width())//2, R.y + (R.h - txt.get_height())//2))
                rects.append(R)
                i += 1
        return rects


class SimpleApp:
    def __init__(self):
        pygame.init()
        # exact 320x240, no scaling
        self.screen = pygame.display.set_mode((320, 240))
        pygame.display.set_caption("Air-gapped Wallet")
        self.renderer = AppRenderer(self.screen)

    # kept for backward-compat if you call it
    def _loop_settings(self):
        # simple inline UI Mode quick toggle (LIST, GRID, COMPACT)
        from ui.theme_store import get_ui_mode, set_ui_mode
        running = True
        items = ["LIST", "GRID", "COMPACT", "Back"]
        while running:
            rects = self.renderer.draw_menu("UI Mode", items, get_ui_mode())
            for ev in pygame.event.get():
                if ev.type == pygame.QUIT: return
                if ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 1:
                    # bottom bar first
                    nav = self.renderer.bottom_hit(ev.pos)
                    if nav == "back": return
                    if nav == "home": return
                    # items
                    hit = self.renderer.hit_test(rects, ev.pos)
                    if hit is None: continue
                    lab = items[hit]
                    if lab == "Back": return
                    if lab in ("LIST","GRID","COMPACT"):
                        set_ui_mode(lab.lower())
                        self.renderer.settings["mode"] = lab.lower()
                        # re-render once and exit
                        self.renderer.draw_menu("UI Mode", items, lab.lower())
                        pygame.time.delay(300)
                        return
