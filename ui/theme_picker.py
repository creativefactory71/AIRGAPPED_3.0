# theme_picker.py
import pygame
from ui.theme_store import list_themes, set_theme_key, get_theme_key, theme_color, theme_radius

TILE_W, TILE_H = 134, 46
PAD = 10

class ThemePicker:
    def __init__(self, screen, renderer, title_font, body_font):
        self.sc=screen; self.r=renderer; self.tf=title_font; self.bf=body_font
        self.sw,self.sh=screen.get_size()
        self._tiles = []  # [(rect, key, name)]

    def run(self):
        # draw grid of theme tiles (2 columns)
        self._draw()
        while True:
            for ev in pygame.event.get():
                if ev.type==pygame.QUIT: return
                if ev.type==pygame.MOUSEBUTTONDOWN and ev.button==1:
                    nav = self.r.bottom_hit(ev.pos)
                    if nav == "back": return
                    if nav == "home": return
                    for rect,key,_ in self._tiles:
                        if rect.collidepoint(ev.pos):
                            set_theme_key(key)
                            self._draw()  # re-render immediately with new theme
                            self._toast("Theme applied")
                            return
            pygame.time.Clock().tick(30)

    def _draw(self):
        # paint background + title via renderer
        from stores.settings import get_display_mode
        self.r.draw_menu("Theme", [], get_display_mode(self.r.settings))  # draws title + bottom bar
        # now draw tiles into content area
        bg, fg, card, border, acc, acc_fg = theme_color("bg"), theme_color("fg"), theme_color("card"), theme_color("border"), theme_color("accent"), theme_color("accent_fg")
        radius = theme_radius()
        themes = list_themes()
        active = get_theme_key()

        cols = 2
        x0, y0 = PAD, 26
        y = y0
        self._tiles.clear()
        for i, t in enumerate(themes):
            col = i % cols
            row = i // cols
            x = PAD + col*(TILE_W + PAD)
            y = y0 + row*(TILE_H + PAD)
            r = pygame.Rect(x, y, TILE_W, TILE_H)
            pygame.draw.rect(self.sc, card, r, border_radius=radius)
            pygame.draw.rect(self.sc, border, r, 1, border_radius=radius)
            name = t["name"]
            self.sc.blit(self.bf.render(name, True, fg), (r.x+8, r.y+6))
            # indicator
            if t["key"] == active:
                tick = self.bf.render("✓", True, acc)
                self.sc.blit(tick, (r.right-16, r.y+6))
            self._tiles.append((r, t["key"], name))
        pygame.display.flip()

    def _toast(self, text, ms=800):
        bar = pygame.Surface((self.sw, 20)); bar.fill(theme_color("card"))
        self.sc.blit(bar,(0,self.sh-20))
        self.sc.blit(self.bf.render(text, True, theme_color("fg")),(6,self.sh-16))
        pygame.display.flip(); pygame.time.delay(ms)
