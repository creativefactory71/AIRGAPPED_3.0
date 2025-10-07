# qr_scanner.py
import pygame
import cv2
import numpy as np

WHITE=(255,255,255); BLACK=(0,0,0); OUT=(0,0,0)

class QRScanner:
    """
    Webcam QR scanner embedded in the 320x240 pygame UI.
    - Mouse-only: 'Cancel' button to exit
    - Returns the decoded string, or None if cancelled
    """
    def __init__(self, screen, title_font, body_font, camera_index=0):
        self.sc = screen
        self.tf = title_font
        self.bf = body_font
        self.sw, self.sh = screen.get_size()
        self.cam_index = camera_index
        self.detector = cv2.QRCodeDetector()

    def scan(self, timeout_ms=0):
        cap = cv2.VideoCapture(self.cam_index, cv2.CAP_DSHOW)  # CAP_DSHOW helps on Windows
        if not cap.isOpened():
            self._alert("Camera not available.\nTry a different index (0 or 1).")
            return None
        # try to reduce load
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)

        clock = pygame.time.Clock()
        start_ticks = pygame.time.get_ticks()

        decoded = None
        while True:
            ok, frame = cap.read()
            if not ok:
                decoded = None
                break

            # Detect + decode
            try:
                # Prefer detectAndDecodeMulti if available, else fallback
                if hasattr(self.detector, "detectAndDecodeMulti"):
                    data_list, pts, _ = self.detector.detectAndDecodeMulti(frame)
                    decoded = next((d for d in data_list if d), None)
                else:
                    decoded, pts, _ = self.detector.detectAndDecode(frame)
            except Exception:
                decoded = None
                pts = None

            # draw to pygame
            frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            surf = pygame.image.frombuffer(frame_rgb.tobytes(), frame_rgb.shape[1::-1], "RGB")
            # scale to fit 320x200 area
            target_h = self.sh - 40
            scale = min(self.sw / surf.get_width(), target_h / surf.get_height())
            disp_w = int(surf.get_width()*scale)
            disp_h = int(surf.get_height()*scale)
            surf = pygame.transform.smoothscale(surf, (disp_w, disp_h))

            self.sc.fill(WHITE)
            self.sc.blit(self.tf.render("QR Scanner", True, BLACK), (8, 6))
            x = (self.sw - disp_w)//2
            y = 28 + (target_h - disp_h)//2
            self.sc.blit(surf, (x, y))

            # cancel button
            btn = pygame.Rect(self.sw-68, 6, 60, 20)
            pygame.draw.rect(self.sc, (220,220,220), btn, border_radius=6)
            pygame.draw.rect(self.sc, OUT, btn, 1, border_radius=6)
            self.sc.blit(self.bf.render("Cancel", True, BLACK), (btn.x+6, btn.y+2))

            # helper hint
            self.sc.blit(self.bf.render("Hold QR code in front of camera", True, BLACK), (8, self.sh-18))

            pygame.display.flip()

            # finish if decoded
            if decoded:
                break

            # cancel / timeout
            for ev in pygame.event.get():
                if ev.type == pygame.QUIT:
                    decoded = None
                    break
                if ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 1:
                    if btn.collidepoint(ev.pos):
                        decoded = None
                        break

            if decoded is None and timeout_ms and (pygame.time.get_ticks() - start_ticks > timeout_ms):
                break

            clock.tick(30)

        cap.release()
        cv2.destroyAllWindows()
        return decoded

    def _alert(self, msg):
        self.sc.fill(WHITE)
        self.sc.blit(self.tf.render("QR Scanner", True, BLACK), (8, 6))
        y=34
        for line in msg.split("\n"):
            self.sc.blit(self.bf.render(line, True, BLACK), (8, y)); y+=16
        btn=pygame.Rect(self.sw-60, self.sh-26, 52, 20)
        pygame.draw.rect(self.sc, (220,220,220), btn, border_radius=6)
        pygame.draw.rect(self.sc, OUT, btn, 1, border_radius=6)
        self.sc.blit(self.bf.render("OK", True, BLACK), (btn.x+14, btn.y+2))
        pygame.display.flip()
        while True:
            for ev in pygame.event.get():
                if ev.type == pygame.QUIT: return
                if ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 1 and btn.collidepoint(ev.pos):
                    return
