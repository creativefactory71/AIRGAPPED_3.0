# qr_chunker.py
from __future__ import annotations
import time, pygame

try:
    import qrcode, numpy as _np
    _HAS_QR = True
except Exception:
    _HAS_QR = False

# Optional debug
try:
    from debug import dbg
except Exception:
    def dbg(*a, **k): pass

WHITE=(255,255,255); BLACK=(0,0,0); OUT=(0,0,0)

def _make_qr_surface(data: str, max_side: int = 180) -> pygame.Surface | None:
    if not _HAS_QR:
        return None
    try:
        qr = qrcode.QRCode(error_correction=qrcode.constants.ERROR_CORRECT_Q)
        qr.add_data(data); qr.make(fit=True)
        img = qr.make_image(fill_color="black", back_color="white")
        arr = _np.array(img.convert("RGB"))
        surf = pygame.surfarray.make_surface(arr.swapaxes(0,1))
        # scale proportionally to max_side
        w,h = surf.get_size()
        scale = min(max_side/float(w), max_side/float(h))
        if scale <= 0: scale = 1.0
        new_size = (max(1,int(w*scale)), max(1,int(h*scale)))
        surf = pygame.transform.smoothscale(surf, new_size)
        return surf
    except Exception as e:
        dbg(f"QR render error: {e}")
        return None

def _chunk(s: str, n: int) -> list[str]:
    return [s[i:i+n] for i in range(0, len(s), n)] if s else [""]

def show_paged(
    screen: pygame.Surface,
    data: str,
    title_font: pygame.font.Font,
    body_font: pygame.font.Font,
    chunk_size: int = 350,
    pump_input=None,
) -> None:
    """
    Modal QR/text pager with Prev / Next / Close.
    - Always pumps touch via pump_input() if provided (Pi fix).
    - Debounces stale taps on entry.
    - Click-on-release semantics to avoid accidental multiple taps.
    """
    dbg("qr_chunker.show_paged open")
    w,h = screen.get_size()
    pages = _chunk(data, max(1, chunk_size))
    idx = 0
    down_btn = None
    ignore_until = 0.0

    # Debounce on entry; clear old pointer events
    cleared = pygame.event.clear([pygame.MOUSEBUTTONDOWN, pygame.MOUSEBUTTONUP, pygame.MOUSEMOTION])
    if cleared: dbg(f"QR pager: debounced {len(cleared)} events")
    ignore_until = time.time() + 0.15

    # Pre-create button rects (stay away from any bottom-nav area, use our own bar)
    btn_h = 22
    bar_y = h - btn_h - 6
    btn_prev = pygame.Rect(6,  bar_y, 60, btn_h)
    btn_next = pygame.Rect(72, bar_y, 60, btn_h)
    btn_close= pygame.Rect(w-66, bar_y, 60, btn_h)

    clock = pygame.time.Clock()

    def _draw():
        screen.fill(WHITE)
        # Title
        screen.blit(title_font.render("Signed TX (QR)", True, BLACK), (8,6))
        # Page label
        lab = f"Page {idx+1}/{len(pages)}"
        screen.blit(body_font.render(lab, True, BLACK), (8, 26))

        # QR if available, else text
        qr = _make_qr_surface(pages[idx], max_side=min(w-16, h-70))
        if qr:
            # center
            screen.blit(qr, (w//2 - qr.get_width()//2, 40))
        else:
            # fallback: render text chunks lines
            y = 42
            s = pages[idx]
            for i in range(0, len(s), 32):
                line = s[i:i+32]
                screen.blit(body_font.render(line, True, BLACK), (8, y)); y += 16

        # Buttons
        for r,lab in ((btn_prev,"Prev"),(btn_next,"Next"),(btn_close,"Close")):
            pygame.draw.rect(screen,(230,230,230), r, border_radius=6)
            pygame.draw.rect(screen, OUT, r, 1, border_radius=6)
            t = body_font.render(lab, True, BLACK)
            screen.blit(t, (r.centerx - t.get_width()//2, r.centery - t.get_height()//2))

        pygame.display.update()

    while True:
        if pump_input:
            pump_input()

        _draw()

        for ev in pygame.event.get():
            if ev.type == pygame.QUIT:
                return
            if ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 1:
                if time.time() < ignore_until:
                    continue
                if btn_prev.collidepoint(ev.pos):  down_btn = "prev"
                elif btn_next.collidepoint(ev.pos):down_btn = "next"
                elif btn_close.collidepoint(ev.pos):down_btn = "close"
                else: down_btn = None
            if ev.type == pygame.MOUSEBUTTONUP and ev.button == 1:
                up = ("prev" if btn_prev.collidepoint(ev.pos)
                      else "next" if btn_next.collidepoint(ev.pos)
                      else "close" if btn_close.collidepoint(ev.pos) else None)
                if down_btn and up == down_btn:
                    dbg(f"QR pager click: {up}")
                    if up == "prev":
                        idx = (idx - 1) % len(pages)
                        ignore_until = time.time() + 0.08
                    elif up == "next":
                        idx = (idx + 1) % len(pages)
                        ignore_until = time.time() + 0.08
                    elif up == "close":
                        dbg("QR pager close")
                        return
                down_btn = None

        clock.tick(30)
