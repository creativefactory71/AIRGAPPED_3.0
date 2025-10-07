# ui_mode_picker.py
import pygame
from ui.theme_store import get_ui_mode, set_ui_mode, theme_color

class UiModePicker:
    def __init__(self, screen, renderer, title_font, body_font):
        self.sc=screen; self.r=renderer; self.tf=title_font; self.bf=body_font
        self.sw,self.sh=screen.get_size()

    def run(self):
        from stores.settings import get_display_mode
        items = ["LIST", "GRID", "COMPACT", "Back"]
        while True:
            rects = self.r.draw_menu("UI Mode", items, get_display_mode(self.r.settings))
            for ev in pygame.event.get():
                if ev.type==pygame.QUIT: return
                if ev.type==pygame.MOUSEBUTTONDOWN and ev.button==1:
                    nav = self.r.bottom_hit(ev.pos)
                    if nav == "back": return
                    if nav == "home": return
                    hit = self.r.hit_test(rects, ev.pos)
                    if hit is None: break
                    label = items[hit]
                    if label == "Back": return
                    if label in ("LIST","GRID","COMPACT"):
                        set_ui_mode(label.lower())
                        self.r.settings["mode"] = label.lower()
                        # quick toast
                        self._toast(f"UI Mode set: {label}")
                        return
            pygame.time.Clock().tick(30)

    def _toast(self, text, ms=800):
        bar = pygame.Surface((self.sw, 20)); bar.fill(theme_color("card"))
        self.sc.blit(bar,(0,self.sh-20))
        self.sc.blit(self.bf.render(text, True, theme_color("fg")),(6,self.sh-16))
        pygame.display.flip(); pygame.time.delay(ms)
