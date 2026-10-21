"""
text.py - Draw text with a dark outline, so it's readable on any background.

    from ui.text import draw_text
    from ui.assets import get_font
    from ui import theme

    draw_text(screen, "SETTINGS", get_font(theme.FONT_BUTTON), theme.TEXT, (100, 50))

Pixel fonts look crisp only WITHOUT smoothing, so antialias is off.
"""
from . import theme


def text_width(font, text):
    """How many pixels wide 'text' is in this font (handy for right-aligning numbers)."""
    return font.render(text, False, (0, 0, 0)).get_width()


def render_text(text, font, color, outline=2, outline_color=theme.OUTLINE, shadow=True):
    """Make a picture of the text (with outline). Returns a Surface you can blit."""
    import pygame

    main = font.render(text, False, color)
    if outline <= 0:
        return main
    edge = font.render(text, False, outline_color)
    extra = outline * 2 + (outline if shadow else 0)
    result = pygame.Surface((main.get_width() + extra, main.get_height() + extra), pygame.SRCALPHA)
    offsets = [(dx, dy) for dx in (-outline, 0, outline) for dy in (-outline, 0, outline)
               if (dx, dy) != (0, 0)]
    if shadow:
        offsets.append((outline * 2, outline * 2))          # a drop shadow down-right
    for dx, dy in offsets:
        result.blit(edge, (outline + dx, outline + dy))
    result.blit(main, (outline, outline))
    return result


def draw_text(surface, text, font, color, pos, outline=2, outline_color=theme.OUTLINE,
              shadow=True, center=False, middle=False):
    """
    Draw outlined text. Returns its (width, height).
      pos is the top-left corner, unless:
      center=True  -> pos is the exact middle of the text
      middle=True  -> pos is the left edge, halfway down (handy inside buttons)
    """
    image = render_text(text, font, color, outline, outline_color, shadow)
    x, y = pos
    if center:
        x -= image.get_width() // 2
    if center or middle:
        y -= image.get_height() // 2
    surface.blit(image, (x, y))
    return image.get_width(), image.get_height()
