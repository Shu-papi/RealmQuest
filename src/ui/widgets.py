"""
widgets.py - Small drawing helpers shared by the screens (class select, inventory...).

    from ui import widgets
    widgets.dim(screen)                                   # darken what's behind
    widgets.wood_box(screen, (x, y, w, h), glowing=False) # dark wood frame with brass corners
    widgets.title_plate(screen, (480, 100), "INVENTORY")
    widgets.button(screen, (x, y, w, h), "EQUIP", selected=True)

Every helper uses the pictures in assets/ui/ when they exist and plain shapes when not.
"""
import pygame

from . import theme
from .assets import get_image, get_font, nine_slice
from .text import draw_text

_stretched = {}


def stretched(name, w, h, border):
    """A picture stretched with nine_slice, made once and remembered. None if missing."""
    key = (name, w, h, border)
    if key not in _stretched:
        image = get_image(name)
        _stretched[key] = nine_slice(image, w, h, border) if image is not None else None
    return _stretched[key]


def clear_cache():
    _stretched.clear()


def dim(surface, alpha=150):
    shade = pygame.Surface((surface.get_width(), surface.get_height()), pygame.SRCALPHA)
    shade.fill((0, 0, 0, alpha))
    surface.blit(shade, (0, 0))


def stone_panel(surface, rect):
    x, y, w, h = rect
    picture = stretched("panel.png", w, h, 28)
    if picture is not None:
        surface.blit(picture, (x, y))
    else:
        pygame.draw.rect(surface, theme.OUTLINE, (x - 3, y - 3, w + 6, h + 6))
        pygame.draw.rect(surface, theme.STONE, (x, y, w, h))
        pygame.draw.rect(surface, theme.PANEL, (x + 18, y + 18, w - 36, h - 36))


def wood_box(surface, rect, glowing=False):
    x, y, w, h = rect
    picture = stretched("slot_selected.png" if glowing else "slot.png", w, h, 14)
    if picture is not None:
        surface.blit(picture, (x, y))
    else:
        pygame.draw.rect(surface, theme.OUTLINE, (x - 2, y - 2, w + 4, h + 4))
        pygame.draw.rect(surface, theme.BRASS if glowing else theme.WOOD_DARK, (x, y, w, h))
        pygame.draw.rect(surface, theme.TORCH if glowing else theme.STONE_DARK,
                         (x + 6, y + 6, w - 12, h - 12))


def title_plate(surface, center, text):
    cx, cy = center
    plate = get_image("title_plate.png")
    if plate is not None:
        surface.blit(plate, (cx - plate.get_width() // 2, cy - plate.get_height() // 2))
    else:
        pygame.draw.rect(surface, theme.OUTLINE, (cx - 156, cy - 26, 312, 52))
        pygame.draw.rect(surface, theme.WOOD, (cx - 152, cy - 22, 304, 44))
    draw_text(surface, text, get_font(theme.FONT_BUTTON), theme.TITLE, (cx, cy),
              outline=2, outline_color=theme.TITLE_SHADOW, center=True)


def button(surface, rect, label, selected=False, enabled=True):
    x, y, w, h = rect
    picture = stretched("button_selected.png" if (selected and enabled) else "button.png", w, h, 14)
    if picture is not None:
        surface.blit(picture, (x, y))
    else:
        pygame.draw.rect(surface, theme.OUTLINE, (x - 2, y - 2, w + 4, h + 4))
        pygame.draw.rect(surface, theme.BRASS if selected else theme.WOOD, (x, y, w, h))
        pygame.draw.rect(surface, theme.TORCH if (selected and enabled) else theme.STONE,
                         (x + 5, y + 5, w - 10, h - 10))
    color = theme.TEXT if enabled else theme.TEXT_DIM
    draw_text(surface, label, get_font(theme.FONT_BUTTON), color, (x + w // 2, y + h // 2),
              outline=2, center=True)


def icon(surface, name, pos, size=None):
    """Draw assets/ui/<name> at pos (top-left), optionally scaled. Returns True if drawn."""
    picture = get_image(name)
    if picture is None:
        return False
    if size is not None and picture.get_width() != size:
        picture = pygame.transform.scale(picture, (size, size))
    surface.blit(picture, pos)
    return True


def portrait(surface, name, box):
    """Draw a character picture scaled (crisply) to fit inside box, centred at the bottom."""
    x, y, w, h = box
    picture = get_image(name)
    if picture is None:
        draw_text(surface, "?", get_font(theme.FONT_TITLE), theme.TEXT_DIM,
                  (x + w // 2, y + h // 2), outline=2, center=True)
        return
    scale = min(w / picture.get_width(), h / picture.get_height())
    size = (int(picture.get_width() * scale), int(picture.get_height() * scale))
    picture = pygame.transform.scale(picture, size)
    surface.blit(picture, (x + (w - size[0]) // 2, y + h - size[1]))


def inside(pos, rect):
    x, y, w, h = rect
    return x <= pos[0] < x + w and y <= pos[1] < y + h
