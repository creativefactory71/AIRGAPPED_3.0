# menu_renderer.py
import pygame
from ui.display_modes import DisplayMode

WHITE=(255,255,255)
BLACK=(0,0,0)
HILITE=(0,0,0)  # outline
BG_TILE=(238,238,238)

class MenuRenderer:
    """
    Renders selectable menus as:
      - GRID: 3 rows × 2 columns, centered
      - LIST: vertically stacked buttons
      - COMPACT: tighter list with smaller font/height
    Mouse only: returns index of clicked item or None.
    """
    def __init__(self, screen, settings):
        self.screen = screen
        self.settings = settings
        sw = settings.get("screen_width", 320)
        sh = settings.get("screen_height", 240)

        # fonts for 320x240
        self.title_font = pygame.font.SysFont("dejavusans", 16, bold=True)
        self.list_font = pygame.font.SysFont("dejavusans", 14)
        self.compact_font = pygame.font.SysFont("dejavusans", 12)

        self.sw, self.sh = sw, sh

    def draw_menu(self, title:str, items:list[str], mode:DisplayMode):
        self.screen.fill(WHITE)
        # Title
        title_surf = self.title_font.render(title, True, BLACK)
        self.screen.blit(title_surf, (8, 6))

        if mode == DisplayMode.GRID:
            rects = self._draw_grid(items)
        elif mode == DisplayMode.LIST:
            rects = self._draw_list(items, compact=False)
        else:
            rects = self._draw_list(items, compact=True)
        pygame.display.flip()
        return rects

    def _draw_grid(self, items:list[str]):
        # 3 rows × 2 columns, centered; tile sizes fit 320x240.
        rows, cols = 3, 2
        total = rows*cols
        # grid area margins
        top = 28
        bottom_margin = 8
        grid_h = self.sh - top - bottom_margin
        grid_w = self.sw

        # tile size & spacing
        # We’ll use small gaps to fit labels nicely
        gap = 6
        tile_w = (grid_w - (cols+1)*gap) // cols
        tile_h = (grid_h - (rows+1)*gap) // rows

        # center grid vertically (already using full width)
        used_h = rows*tile_h + (rows+1)*gap
        start_y = top + (grid_h - used_h)//2
        start_x = (grid_w - (cols*tile_w + (cols+1)*gap))//2

        rects=[]
        font = self.list_font
        for i, label in enumerate(items[:total]):
            r = i//cols
            c = i%cols
            x = start_x + gap + c*(tile_w + gap)
            y = start_y + gap + r*(tile_h + gap)
            rect = pygame.Rect(x, y, tile_w, tile_h)
            pygame.draw.rect(self.screen, BG_TILE, rect, border_radius=6)
            pygame.draw.rect(self.screen, HILITE, rect, width=1, border_radius=6)

            # label centered
            text_surface = font.render(label, True, BLACK)
            tx = rect.x + (rect.w - text_surface.get_width())//2
            ty = rect.y + (rect.h - text_surface.get_height())//2
            self.screen.blit(text_surface, (tx, ty))
            rects.append(rect)
        return rects

    def _draw_list(self, items:list[str], compact:bool):
        # vertical list; centered block
        gap = 6 if not compact else 4
        btn_h = 40 if not compact else 26
        left_margin = 12
        right_margin = 12
        btn_w = self.sw - left_margin - right_margin

        total_h = len(items)*btn_h + (len(items)-1)*gap
        start_y = 28 + max(0, (self.sh - 28 - total_h)//2)
        rects=[]
        font = self.list_font if not compact else self.compact_font

        for i, label in enumerate(items):
            y = start_y + i*(btn_h + gap)
            rect = pygame.Rect(left_margin, y, btn_w, btn_h)
            pygame.draw.rect(self.screen, BG_TILE, rect, border_radius=6)
            pygame.draw.rect(self.screen, HILITE, rect, width=1, border_radius=6)

            text_surface = font.render(label, True, BLACK)
            tx = rect.x + 8
            ty = rect.y + (rect.h - text_surface.get_height())//2
            self.screen.blit(text_surface, (tx, ty))
            rects.append(rect)
        return rects

    def hit_test(self, rects, mouse_pos):
        for idx, r in enumerate(rects):
            if r.collidepoint(mouse_pos):
                return idx
        return None
