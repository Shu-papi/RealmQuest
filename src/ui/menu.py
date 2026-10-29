"""
menu.py - The main menu: the dungeon-gate picture, the title, and three buttons
(New Game, Settings, Exit), as the game plan asks.

    from ui.menu import MainMenu

    menu = MainMenu()

    # every frame:
    for event in pygame.event.get():
        action = menu.handle_event(event)
        if action == "new_game": ...start the game...
        if action == "settings": ...open the settings screen...
        if action == "exit":     ...quit...
    menu.update(dt)
    menu.draw(screen)

CONTROLS
    Up / Down or W / S   move between buttons
    Enter or Space       press the selected button
    Mouse                hover to select, click to press

The menu never starts the game or quits by itself. It only RETURNS an
action word, and whoever owns the game loop decides what to do with it.

PICTURES (assets/ui/): menu_bg.png, screen_frame.png, title_sign.png, hero.png,
                      button.png, button_selected.png, icon_*.png
FONTS (assets/ui/fonts/): chosen in theme.py (FONT_TITLE, FONT_BUTTON, FONT_SMALL)
If any are missing, simple shapes and the built-in font are used instead.
"""
import math

import pygame

from . import theme
from .assets import get_image, get_font, nine_slice
from .text import draw_text

NEW_GAME = "new_game"
SETTINGS = "settings"
EXIT = "exit"

#                 label        action     icon picture
DEFAULT_BUTTONS = [
    ("NEW GAME", NEW_GAME, "icon_play.png"),
    ("SETTINGS", SETTINGS, "icon_gear.png"),
    ("EXIT",     EXIT,     "icon_exit.png"),
]

TITLE = "REALMQUEST"
SIGN_POS = (84, 58)                # top-left of title_sign.png (the sword pokes over the frame)
SIGN_TEXT_CENTER = (190, 137)      # middle of the wooden board, inside title_sign.png

# the inside of screen_frame.png is roughly x 82-885, y 80-547; everything fits in there
BUTTONS_LEFT = 100
BUTTONS_TOP = 304
BUTTON_W, BUTTON_H = 300, 56
BUTTON_GAP = 12
HINT_POS = (100, 512)
HERO_FEET = (700, 532)             # where the hero stands (bottom-middle of hero.png)
BUTTON_BORDER = 14                 # frame thickness inside button.png (for nine_slice)
ICON_SIZE = 32


class MainMenu:
    def __init__(self, width=theme.SCREEN_W, height=theme.SCREEN_H, buttons=None):
        self.width = width
        self.height = height
        self.buttons = list(buttons or DEFAULT_BUTTONS)     # [(label, action, icon), ...]
        self.selected = 0
        self.time = 0.0
        self._button_images = None                          # made once, on first draw
        self.stars = [((i * 157) % width, (i * 89) % (height // 2), i * 0.7) for i in range(60)]

    # ---------- logic (no drawing, easy to test) ----------

    def move(self, step):
        """Move the highlight up (-1) or down (+1). Wraps around."""
        self.selected = (self.selected + step) % len(self.buttons)

    def activate(self):
        """Press the highlighted button. Returns its action word."""
        return self.buttons[self.selected][1]

    def button_rects(self):
        """Where each button is on screen, as (x, y, w, h)."""
        return [(BUTTONS_LEFT, BUTTONS_TOP + i * (BUTTON_H + BUTTON_GAP), BUTTON_W, BUTTON_H)
                for i in range(len(self.buttons))]

    def button_at(self, pos):
        """Index of the button under the mouse, or None."""
        px, py = pos
        for index, (x, y, w, h) in enumerate(self.button_rects()):
            if x <= px < x + w and y <= py < y + h:
                return index
        return None

    def handle_event(self, event):
        """Give it every pygame event. Returns an action word, or None."""
        if event.type == pygame.KEYDOWN:
            if event.key in (pygame.K_UP, pygame.K_w):
                self.move(-1)
            elif event.key in (pygame.K_DOWN, pygame.K_s):
                self.move(+1)
            elif event.key in (pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_SPACE):
                return self.activate()
        elif event.type == pygame.MOUSEMOTION:
            index = self.button_at(event.pos)
            if index is not None:
                self.selected = index
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            index = self.button_at(event.pos)
            if index is not None:
                self.selected = index
                return self.activate()
        return None

    def update(self, dt):
        self.time += dt

    # ---------- drawing ----------

    def draw(self, surface):
        # back to front: scene, hero, wooden frame, title sign, buttons
        self._draw_background(surface)
        self._draw_hero(surface)
        self._draw_frame(surface)
        self._draw_title(surface)
        for index, rect in enumerate(self.button_rects()):
            label, _, icon = self.buttons[index]
            self._draw_button(surface, rect, label, icon, index == self.selected)
        draw_text(surface, "Enter to select",
                  get_font(theme.FONT_SMALL), theme.TEXT, HINT_POS, outline=1)

    def _draw_background(self, surface):
        picture = get_image("menu_bg.png")
        if picture is not None:
            if picture.get_width() != self.width or picture.get_height() != self.height:
                picture = pygame.transform.scale(picture, (self.width, self.height))
            surface.blit(picture, (0, 0))
        else:
            self._draw_fallback_scene(surface)

    def _draw_hero(self, surface):
        hero = get_image("hero.png")
        if hero is None:
            return
        bob = 1 if math.sin(self.time * 2.5) > 0 else 0          # gentle breathing
        fx, fy = HERO_FEET
        surface.blit(hero, (fx - hero.get_width() // 2, fy - hero.get_height() - bob))

    def _draw_frame(self, surface):
        frame = get_image("screen_frame.png")
        if frame is None:   # fallback: a plain wooden border
            for i, color in enumerate((theme.OUTLINE, theme.WOOD_DARK, theme.WOOD, theme.WOOD)):
                pygame.draw.rect(surface, color, (i * 6, i * 6, self.width - i * 12, 6))
                pygame.draw.rect(surface, color, (i * 6, self.height - (i + 1) * 6, self.width - i * 12, 6))
                pygame.draw.rect(surface, color, (i * 6, i * 6, 6, self.height - i * 12))
                pygame.draw.rect(surface, color, (self.width - (i + 1) * 6, i * 6, 6, self.height - i * 12))
            return
        if frame.get_width() != self.width or frame.get_height() != self.height:
            frame = pygame.transform.scale(frame, (self.width, self.height))
        surface.blit(frame, (0, 0))

    def _draw_fallback_scene(self, surface):
        w, h = self.width, self.height
        band = int(h * 0.7) // len(theme.SKY) + 1
        for i, color in enumerate(theme.SKY):
            pygame.draw.rect(surface, color, (0, i * band, w, band))
        for x, y, phase in self.stars:
            if math.sin(self.time * 2 + phase) > -0.3:
                pygame.draw.rect(surface, theme.STAR, (x, y, 2, 2))
        pygame.draw.circle(surface, theme.MOON, (int(w * 0.16), int(h * 0.14)), 30)
        ground = int(h * 0.7)
        for i in range(0, w, 48):                                    # pine tree line
            top = ground - 90 - (i * 37) % 70
            pygame.draw.polygon(surface, theme.FOREST, [(i - 30, ground), (i + 18, top), (i + 66, ground)])
        pygame.draw.rect(surface, theme.GRASS, (0, ground, w, h - ground))
        gx, gw = int(w * 0.66), 220                                  # dungeon gate
        pygame.draw.rect(surface, theme.STONE, (gx, ground - 230, gw, 230))
        pygame.draw.rect(surface, theme.OUTLINE, (gx + 60, ground - 150, 100, 150))
        for tx in (gx + 30, gx + gw - 46):                           # two torches
            pygame.draw.rect(surface, theme.WOOD, (tx + 4, ground - 120, 8, 24))
            pygame.draw.rect(surface, theme.TORCH, (tx, ground - 140, 16, 20))
            pygame.draw.rect(surface, theme.TORCH_LIGHT, (tx + 4, ground - 134, 8, 10))

    def _draw_title(self, surface):
        sx, sy = SIGN_POS
        sign = get_image("title_sign.png")
        if sign is not None:
            surface.blit(sign, (sx, sy))
        cx, cy = SIGN_TEXT_CENTER
        draw_text(surface, TITLE, get_font(theme.FONT_TITLE), theme.TITLE, (sx + cx, sy + cy),
                  outline=3, outline_color=theme.TITLE_SHADOW, center=True)

    def _get_button_images(self):
        """Stretch button.png / button_selected.png to the button size once, then reuse."""
        if self._button_images is None:
            normal, selected = get_image("button.png"), get_image("button_selected.png")
            if normal is not None and selected is not None:
                self._button_images = (
                    nine_slice(normal, BUTTON_W, BUTTON_H, BUTTON_BORDER),
                    nine_slice(selected, BUTTON_W, BUTTON_H, BUTTON_BORDER),
                )
            else:
                self._button_images = False                    # remember: no pictures
        return self._button_images or None

    def _draw_button(self, surface, rect, label, icon, selected):
        x, y, w, h = rect
        images = self._get_button_images()
        if images is not None:
            surface.blit(images[1] if selected else images[0], (x, y))
        else:   # fallback: stone face, wood frame, torch-orange when selected
            pygame.draw.rect(surface, theme.OUTLINE, (x - 2, y - 2, w + 4, h + 4))
            pygame.draw.rect(surface, theme.BRASS if selected else theme.WOOD, (x, y, w, h))
            pygame.draw.rect(surface, theme.TORCH if selected else theme.STONE,
                             (x + 5, y + 5, w - 10, h - 10))

        icon_image = get_image(icon)
        if icon_image is not None:
            surface.blit(icon_image, (x + 24, y + (h - ICON_SIZE) // 2))

        color = theme.TEXT if selected else theme.TEXT_DIM
        draw_text(surface, label, get_font(theme.FONT_BUTTON), color,
                  (x + 72, y + h // 2), outline=2, center=False, middle=True)


