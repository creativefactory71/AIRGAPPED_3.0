# settings.py
from ui.theme_store import get_ui_mode

def get_display_mode(_settings_dict=None):
    """
    Returns 'list' | 'grid' | 'compact' from the persisted UI mode store.
    Any local renderer.settings['mode'] should mirror this.
    """
    return get_ui_mode()
