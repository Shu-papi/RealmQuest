"""
assets.py - Loads the UI pictures from assets/ui/ (backgrounds, buttons, panels, icons).

    from ui.assets import get_image, nine_slice

    bg = get_image("menu_bg.png")          # a pygame Surface, or None if the file is missing
    box = nine_slice(get_image("panel.png"), 400, 300, border=28)

IF A PICTURE IS MISSING, get_image() returns None and every screen falls back to
drawing simple shapes, so the game never crashes because of art.

To make new pictures from generated art, see src/ui/dev/prepare_assets.py.
"""
import os

import pygame

SRC_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REPO_ROOT = os.path.dirname(SRC_DIR)
UI_ASSETS_DIR = os.path.join(REPO_ROOT, "assets", "ui")

ENABLED = True                  # tests can switch this off to check the fallback drawing
_cache = {}


def get_image(name):
    """Load assets/ui/<name> once and remember it. Returns None if it can't be loaded."""
    if not ENABLED or not hasattr(pygame, "get_init"):   # off, or the test stub (no real pygame)
        return None
    if name in _cache:
        return _cache[name]
    path = os.path.join(UI_ASSETS_DIR, name)
    image = None
    if os.path.exists(path):
        try:
            image = pygame.image.load(path)
            try:
                image = image.convert_alpha()     # faster drawing (needs the window to exist)
            except pygame.error:
                pass
        except (pygame.error, FileNotFoundError):
            image = None
    _cache[name] = image
    return image


def get_font(spec):
    """
    Load a font from assets/ui/fonts/. 'spec' is (file name, size), e.g. theme.FONT_BUTTON.
    Falls back to pygame's built-in font if the file is missing.
    """
    filename, size = spec
    if hasattr(pygame.font, "get_init") and not pygame.font.get_init():
        pygame.font.init()           # fonts must be switched on before use (safe to call again)
    key = ("font", filename, size)
    if key in _cache:
        return _cache[key]
    path = os.path.join(UI_ASSETS_DIR, "fonts", filename)
    font = None
    if ENABLED and os.path.exists(path):
        try:
            font = pygame.font.Font(path, size)
        except (pygame.error, OSError):
            font = None
    if font is None:
        font = pygame.font.Font(None, int(size * 1.2))    # built-in font is a bit smaller
    _cache[key] = font
    return font


def clear_cache():
    _cache.clear()


def nine_slice(image, width, height, border):
    """
    Stretch a framed picture to any size WITHOUT stretching its corners.

    The picture is cut into 9 pieces like a tic-tac-toe board:
      corners stay the same, edges stretch in one direction, the middle stretches both ways.
    'border' is how thick the frame is (in pixels) in the original picture.
    """
    src_w, src_h = image.get_width(), image.get_height()
    b = min(border, src_w // 2, src_h // 2, width // 2, height // 2)
    result = pygame.Surface((width, height), pygame.SRCALPHA)

    src_x = [0, b, src_w - b, src_w]       # where the cuts are in the original
    src_y = [0, b, src_h - b, src_h]
    dst_x = [0, b, width - b, width]       # where they go in the result
    dst_y = [0, b, height - b, height]

    for row in range(3):
        for col in range(3):
            sw, sh = src_x[col + 1] - src_x[col], src_y[row + 1] - src_y[row]
            dw, dh = dst_x[col + 1] - dst_x[col], dst_y[row + 1] - dst_y[row]
            if sw <= 0 or sh <= 0 or dw <= 0 or dh <= 0:
                continue
            piece = image.subsurface((src_x[col], src_y[row], sw, sh))
            if (sw, sh) != (dw, dh):
                piece = pygame.transform.scale(piece, (dw, dh))
            result.blit(piece, (dst_x[col], dst_y[row]))
    return result
