"""
hud.py - The top-left box with the player's Health, Armor and Energy (like Soul Knight).

    from ui.hud import HUD

    hud = HUD()

    # every frame:
    hud.update(dt, player)
    hud.draw(screen)

WHAT THE HUD NEEDS FROM THE PLAYER (missing ones just show 0/0)
    player.hp,     player.max_hp        red bar
    player.armor,  player.max_armor     gray bar
    player.energy, player.max_energy    blue bar

The HUD only SHOWS these numbers. It never changes them. Damage, armor
regen and energy costs belong to the Characters & Skills team.

THE DRAIN EFFECT (from the game plan: "the color of the bar will drain")
    When a value goes down, the bright bar and the number drop right away,
    and a pale "ghost" piece is left behind that then shrinks away.
    That way the player can SEE how much they just lost.
"""
import pygame

from . import theme
from .assets import get_font, get_image, nine_slice

# ---------- colours ----------
FRAME_OUTER = (20, 10, 6)           # dark outline
FRAME = (74, 36, 18)                # dark walnut wood (fallback when slot.png is missing)
BAR_BACK = (32, 26, 22)             # empty part of a bar
TEXT = (255, 255, 255)
TEXT_SHADOW = (20, 20, 20)

HEALTH_COLOR = (214, 52, 52)
ARMOR_COLOR = (150, 150, 150)
ENERGY_COLOR = (46, 112, 214)
GHOST_COLOR = (240, 225, 200)       # the pale "just lost" piece

# ---------- sizes (pixels) ----------
ICON_SCALE = 3                      # fallback icons: each pixel becomes a 3x3 block
BAR_W = 150
BAR_H = 22
ROW_GAP = 6
PADDING = 16                        # room for the wooden frame around the bars
ICON_GAP = 6

# ---------- drain timing ----------
GHOST_DELAY = 0.35                  # seconds the ghost waits before shrinking
GHOST_SPEED = 2.5                   # how many FULL bars per second it shrinks

# ---------- 8x8 pixel icons ('.' = transparent, X = main colour, o = outline) ----------
HEART = [
    ".oo..oo.",
    "oXXooXXo",
    "oXXXXXXo",
    "oXXXXXXo",
    ".oXXXXo.",
    "..oXXo..",
    "...oo...",
    "........",
]
SHIELD = [
    "oooooooo",
    "oXXXXXXo",
    "oXXXXXXo",
    "oXXXXXXo",
    ".oXXXXo.",
    ".oXXXXo.",
    "..oXXo..",
    "...oo...",
]
DIAMOND = [
    "...oo...",
    "..oXXo..",
    ".oXXXXo.",
    "oXXXXXXo",
    "oXXXXXXo",
    ".oXXXXo.",
    "..oXXo..",
    "...oo...",
]
ICON_SIZE = len(HEART[0]) * ICON_SCALE
FRAME_BORDER = 14                   # frame thickness inside slot.png (for nine_slice)
ICON_FILES = {"health": "icon_heart.png", "armor": "icon_shield.png", "energy": "icon_energy.png"}


class StatBar:
    """One bar: knows its numbers and handles the drain effect. No drawing logic here."""

    def __init__(self, name, color, icon):
        self.name = name
        self.color = color
        self.icon = icon
        self.value = 0
        self.max_value = 0
        self.ghost = 0.0            # where the pale piece ends (>= value while draining)
        self.ghost_timer = 0.0
        self._started = False

    def set(self, value, max_value):
        max_value = max(0, max_value)
        value = max(0, min(value, max_value))       # keep it between 0 and max

        if not self._started:                       # first frame: no ghost
            self.ghost = value
            self._started = True
        elif value < self.value:                    # lost some: start the ghost timer
            self.ghost = max(self.ghost, self.value)
            self.ghost_timer = GHOST_DELAY
        elif value > self.ghost:                    # healed past the ghost: hide it
            self.ghost = value

        self.value = value
        self.max_value = max_value

    def update(self, dt):
        if self.ghost <= self.value:
            self.ghost = self.value
            return
        if self.ghost_timer > 0:
            self.ghost_timer -= dt
            return
        self.ghost -= GHOST_SPEED * self.max_value * dt
        if self.ghost < self.value:
            self.ghost = self.value

    def fill_fraction(self):
        return self.value / self.max_value if self.max_value else 0.0

    def ghost_fraction(self):
        return self.ghost / self.max_value if self.max_value else 0.0

    def label(self):
        return f"{int(self.value)}/{int(self.max_value)}"


class HUD:
    def __init__(self, x=10, y=10, font=None):
        self.x = x
        self.y = y
        self.font = font            # made on first draw if not given
        self._frame = None          # the stretched wooden frame, made once
        self.bars = [
            StatBar("health", HEALTH_COLOR, HEART),
            StatBar("armor", ARMOR_COLOR, SHIELD),
            StatBar("energy", ENERGY_COLOR, DIAMOND),
        ]

    @property
    def health(self):
        return self.bars[0]

    @property
    def armor(self):
        return self.bars[1]

    @property
    def energy(self):
        return self.bars[2]

    def size(self):
        """(width, height) of the whole box, handy for placing other UI next to it."""
        width = PADDING * 2 + ICON_SIZE + ICON_GAP + BAR_W
        height = PADDING * 2 + len(self.bars) * BAR_H + (len(self.bars) - 1) * ROW_GAP
        return width, height

    def update(self, dt, player):
        self.health.set(getattr(player, "hp", 0), getattr(player, "max_hp", 0))
        self.armor.set(getattr(player, "armor", 0), getattr(player, "max_armor", 0))
        self.energy.set(getattr(player, "energy", 0), getattr(player, "max_energy", 0))
        for bar in self.bars:
            bar.update(dt)

    # ---------- drawing ----------

    def draw(self, surface):
        if self.font is None:
            self.font = get_font(theme.FONT_HUD)

        width, height = self.size()
        x, y = self.x, self.y

        # dark wooden frame with brass corners (same picture as the weapon slots)
        if self._frame is None:
            slot = get_image("slot.png")
            self._frame = nine_slice(slot, width, height, FRAME_BORDER) if slot is not None else False
        if self._frame:
            surface.blit(self._frame, (x, y))
        else:
            pygame.draw.rect(surface, FRAME_OUTER, (x - 2, y - 2, width + 4, height + 4))
            pygame.draw.rect(surface, FRAME, (x, y, width, height))

        row_y = y + PADDING
        for bar in self.bars:
            self._draw_icon(surface, bar, x + PADDING, row_y + (BAR_H - ICON_SIZE) // 2)
            self._draw_bar(surface, bar, x + PADDING + ICON_SIZE + ICON_GAP, row_y)
            row_y += BAR_H + ROW_GAP

    def _draw_icon(self, surface, bar, left, top):
        picture = get_image(ICON_FILES.get(bar.name, ""))
        if picture is not None:
            if picture.get_width() != ICON_SIZE:
                picture = pygame.transform.scale(picture, (ICON_SIZE, ICON_SIZE))
            surface.blit(picture, (left, top))
            return
        colors = {"X": bar.color, "o": FRAME_OUTER}
        for row_index, row in enumerate(bar.icon):
            for col_index, ch in enumerate(row):
                if ch in colors:
                    pygame.draw.rect(
                        surface, colors[ch],
                        (left + col_index * ICON_SCALE, top + row_index * ICON_SCALE,
                         ICON_SCALE, ICON_SCALE),
                    )

    def _draw_bar(self, surface, bar, left, top):
        pygame.draw.rect(surface, FRAME_OUTER, (left - 2, top - 2, BAR_W + 4, BAR_H + 4))
        pygame.draw.rect(surface, BAR_BACK, (left, top, BAR_W, BAR_H))

        ghost_w = int(BAR_W * bar.ghost_fraction())
        fill_w = int(BAR_W * bar.fill_fraction())
        if ghost_w > fill_w:
            pygame.draw.rect(surface, GHOST_COLOR, (left, top, ghost_w, BAR_H))
        if fill_w > 0:
            pygame.draw.rect(surface, bar.color, (left, top, fill_w, BAR_H))
            # a lighter stripe on top gives the bar a bit of pixel-art shine
            pygame.draw.rect(surface, _lighter(bar.color), (left, top, fill_w, 3))

        text = bar.label()
        shadow = self.font.render(text, False, TEXT_SHADOW)     # False = crisp pixel font
        image = self.font.render(text, False, TEXT)
        tx = left + (BAR_W - image.get_width()) // 2
        ty = top + (BAR_H - image.get_height()) // 2 + 1
        surface.blit(shadow, (tx + 2, ty + 2))
        surface.blit(image, (tx, ty))


def _lighter(color, amount=50):
    return tuple(min(255, c + amount) for c in color)
