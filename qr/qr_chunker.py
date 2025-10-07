# qr_chunker.py
import pygame, qrcode
from PIL import Image
WHITE=(255,255,255); BLACK=(0,0,0); OUT=(0,0,0)

def _to_surface(img: Image.Image):
    mode,size,data=img.mode,img.size,img.tobytes()
    import pygame as pg
    return pg.image.fromstring(data,size,mode)

def _qr(data, size=180):
    qr=qrcode.QRCode(error_correction=qrcode.constants.ERROR_CORRECT_Q, box_size=4, border=1)
    qr.add_data(data); qr.make(fit=True)
    img=qr.make_image(fill_color="black", back_color="white").convert("RGB")
    img=img.resize((size,size), Image.NEAREST)
    return _to_surface(img)

def show_paged(screen, text:str, title_font, body_font, chunk_size=350):
    """Split long text into chunks and page with Prev/Next."""
    chunks=[text[i:i+chunk_size] for i in range(0,len(text),chunk_size)] or [text]
    i=0; clock=pygame.time.Clock()
    while True:
        screen.fill(WHITE)
        screen.blit(title_font.render("Signed Tx (QR pages)", True, BLACK),(8,6))
        screen.blit(body_font.render(f"Page {i+1}/{len(chunks)}", True, BLACK),(8,26))
        qr=_qr(chunks[i], 180); rect=qr.get_rect(center=(screen.get_width()//2, screen.get_height()//2+8))
        screen.blit(qr, rect)
        # buttons
        prev=pygame.Rect(8, screen.get_height()-26, 48, 20)
        nxt =pygame.Rect(screen.get_width()-56, screen.get_height()-26, 48, 20)
        cls =pygame.Rect(screen.get_width()-56, 6, 48, 20)
        for r,l in ((prev,"Prev"), (nxt,"Next"), (cls,"Close")):
            pygame.draw.rect(screen, (220,220,220), r, border_radius=6)
            pygame.draw.rect(screen, OUT, r, 1, border_radius=6)
            screen.blit(body_font.render(l, True, BLACK),(r.x+6, r.y+2))
        pygame.display.flip()
        for ev in pygame.event.get():
            if ev.type==pygame.QUIT: return
            if ev.type==pygame.MOUSEBUTTONDOWN and ev.button==1:
                if prev.collidepoint(ev.pos) and i>0: i-=1
                elif nxt.collidepoint(ev.pos) and i<len(chunks)-1: i+=1
                elif cls.collidepoint(ev.pos): return
        clock.tick(30)
