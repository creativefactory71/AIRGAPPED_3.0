# numeric_keyboard.py
# Backward-compatible wrapper that presents a big numeric pad using the new keyboard.

from ui.on_screen_keyboard import OnScreenKeyboard

class NumericKeyboard:
    def __init__(self, screen, title="Number", default_value=""):
        self.screen = screen
        self.title = title or "Number"
        self.default = str(default_value or "")

    def run(self):
        kb = OnScreenKeyboard(
            self.screen,
            prompt_or_default=self.title,
            default_text=self.default,
            input_type="numeric",
            password=False
        )
        out = kb.run()
        return out
