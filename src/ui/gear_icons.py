"""
gear_icons.py - Pictures of gear items (inventory.gear.Item) for the inventory, shop and
loot on the ground.

    icon = item_icon(item, 48)      # Surface, cached; rarity-coloured frame is NOT included
    draw_item_slot(surface, rect, item, selected=False)

Weapons reuse the team's weapon art in assets/ui (weapon_iron_sword.png, ...). Helmets,
armor, boots and trinkets are drawn here with plain shapes, tinted by tier.
"""
import pygame

from . import theme
from .assets import get_image

WEAPON_ART = {"sword": "weapon_iron_sword.png", "greatsword": "weapon_greatsword.png",
              "axe": "weapon_battle_axe.png", "staff": "weapon_apprentice_staff.png",
              "wand": "weapon_fire_wand.png", "bow": "weapon_short_bow.png",
              "crossbow": "weapon_crossbow.png"}

# metal colour by tier: leather / iron / steel / gold
TIER_METAL = {1: (150, 104, 64), 2: (150, 156, 170), 3: (200, 206, 222), 4: (236, 196, 92)}

_cache = {}


def item_icon(item, size=48):
    key = (item.base, size)
    if key not in _cache:
        _cache[key] = _make(item, size)
    return _cache[key]


def _make(item, size):
    art = get_image(WEAPON_ART[item.kind]) if item.kind in WEAPON_ART else None
    if art is not None:
        k = min(size / art.get_width(), size / art.get_height())
        return pygame.transform.smoothscale(art, (max(1, int(art.get_width() * k)), max(1, int(art.get_height() * k))))
    s = pygame.Surface((32, 32), pygame.SRCALPHA)
    metal = TIER_METAL.get(item.tier, (160, 160, 170))
    dark = tuple(int(c * 0.55) for c in metal)
    light = tuple(min(255, int(c * 1.25)) for c in metal)
    o = (24, 16, 12)
    kind = item.kind
    if kind in ("helmet", "crown"):
        if kind == "crown":
            pts = [(5, 24), (5, 10), (10, 16), (16, 6), (22, 16), (27, 10), (27, 24)]
            pygame.draw.polygon(s, o, pts)
            pygame.draw.polygon(s, metal, [(x + (1 if x < 16 else -1), y + 1) for x, y in pts])
            for x in (10, 16, 22):
                pygame.draw.circle(s, (220, 60, 70), (x, 20), 2)
        else:
            pygame.draw.ellipse(s, o, (4, 5, 24, 24))
            pygame.draw.ellipse(s, metal, (6, 7, 20, 20))
            pygame.draw.rect(s, (0, 0, 0, 0), (0, 22, 32, 10))
            pygame.draw.rect(s, o, (4, 19, 24, 6))
            pygame.draw.rect(s, dark, (5, 20, 22, 4))
            pygame.draw.rect(s, (30, 24, 26), (10, 15, 12, 3))
            pygame.draw.line(s, light, (10, 10), (14, 8), 2)
    elif kind == "armor":
        pts = [(6, 6), (12, 4), (16, 7), (20, 4), (26, 6), (29, 14), (24, 15), (24, 28), (8, 28), (8, 15), (3, 14)]
        pygame.draw.polygon(s, o, pts)
        pygame.draw.polygon(s, metal, [(x * 0.92 + 1.3, y * 0.92 + 1.3) for x, y in pts])
        pygame.draw.line(s, dark, (16, 9), (16, 26), 2)
        pygame.draw.line(s, light, (10, 12), (13, 10), 2)
    elif kind == "boots":
        for bx in (4, 16):
            pygame.draw.polygon(s, o, [(bx, 6), (bx + 8, 6), (bx + 8, 22), (bx + 13, 24), (bx + 13, 28), (bx, 28)])
            pygame.draw.polygon(s, metal, [(bx + 1, 7), (bx + 7, 7), (bx + 7, 23), (bx + 12, 25), (bx + 12, 27),
                                           (bx + 1, 27)])
            pygame.draw.rect(s, dark, (bx + 1, 8, 6, 3))
    elif kind in ("ring", "amulet"):
        if kind == "amulet":
            pygame.draw.arc(s, (210, 180, 90), (6, 1, 20, 20), 3.3, 6.1, 2)
            pygame.draw.circle(s, o, (16, 21), 8)
            pygame.draw.circle(s, metal, (16, 21), 7)
            pygame.draw.circle(s, (120, 80, 230), (16, 21), 4)
        else:
            pygame.draw.circle(s, o, (16, 19), 10, 4)
            pygame.draw.circle(s, metal, (16, 19), 9, 2)
            gem = {1: (200, 120, 60), 2: (180, 220, 255), 3: (230, 50, 70)}.get(item.tier, (120, 80, 230))
            pygame.draw.circle(s, o, (16, 9), 5)
            pygame.draw.circle(s, gem, (16, 9), 4)
            pygame.draw.circle(s, (255, 255, 255), (15, 8), 1)
    else:
        pygame.draw.circle(s, metal, (16, 16), 10)
    return pygame.transform.scale(s, (size, size))


def draw_item_slot(surface, rect, item, selected=False, dim=False, empty_label=""):
    """A dark slot with a rarity-coloured frame and the item's icon (or a faint label)."""
    r = pygame.Rect(rect)
    pygame.draw.rect(surface, theme.OUTLINE, r.inflate(4, 4))
    pygame.draw.rect(surface, (34, 26, 24), r)
    if item is not None:
        col = item.color
        glow = pygame.Surface(r.size, pygame.SRCALPHA)
        glow.fill((*col, 40))
        surface.blit(glow, r)
        icon = item_icon(item, int(r.w * 0.78))
        if dim:
            icon = icon.copy()
            icon.set_alpha(110)
        surface.blit(icon, icon.get_rect(center=r.center))
        pygame.draw.rect(surface, col, r, 2)
    elif empty_label:
        from .assets import get_font
        font = get_font(theme.FONT_SMALL)
        img = font.render(empty_label, True, (90, 80, 76))
        surface.blit(img, img.get_rect(center=r.center))
    if selected:
        pygame.draw.rect(surface, theme.TITLE, r.inflate(6, 6), 3)
