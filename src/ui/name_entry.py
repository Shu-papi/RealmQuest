"""
name_entry.py - "Name your hero": the screen after New Game, before choosing a class.

    from ui.name_entry import NameEntry, NEXT, BACK

    screen = NameEntry()
    result = screen.handle_event(event)     # NEXT (screen.name is ready) / BACK / None
    screen.update(dt)
    screen.draw(surface)

CONTROLS
    type                letters, digits, spaces, ' and -  (up to MAX_LEN)
    Backspace           delete
    Tab / the dice      a random fantasy name
    Enter / NEXT        continue (needs at least one letter)
    Esc / BACK          back to the main menu
"""
import random

import pygame

from . import theme, widgets
from .assets import get_font, get_image
from .text import draw_text

NEXT = "next"
BACK = "back"
MAX_LEN = 14

NAMES = ["Aldric", "Brienne", "Cael", "Darian", "Elowen", "Fenwick", "Gwyn", "Halvar", "Isolde",
         "Joren", "Kaela", "Lucan", "Maeve", "Nyra", "Orrin", "Perrin", "Quinn", "Rowan", "Seren",
         "Talia", "Ulric", "Vesper", "Wynn", "Yara", "Zephyr", "Ashe", "Bram", "Corin", "Lyra", "Theron"]

PANEL = (200, 150, 560, 330)
BOX = (260, 268, 440, 64)
DICE = (712, 272, 56, 56)
BACK_RECT = (260, 392, 180, 56)
NEXT_RECT = (520, 392, 180, 56)


def valid_char(ch):
    return len(ch) == 1 and (ch.isalnum() or ch in " '-")


def clean(name):
    """What would be saved: allowed characters only, single spaces, trimmed, at most MAX_LEN."""
    keep = "".join(ch for ch in name if valid_char(ch))
    return " ".join(keep.split())[:MAX_LEN].strip()


class NameEntry:
    def __init__(self, name="", width=theme.SCREEN_W, height=theme.SCREEN_H, rng=None):
        self.width, self.height = width, height
        self.text = clean(name)
        self.time = 0.0
        self.focus = None            # "back" / "next" / "dice" under the mouse
        self.rng = rng or random.Random()
        self.shake = 0.0             # the box shakes when NEXT is pressed with no name

    @property
    def name(self):
        return clean(self.text)

    @property
    def ready(self):
        return any(ch.isalpha() for ch in self.name)

    # ---------- logic ----------
    def type(self, chars):
        for ch in chars:
            if valid_char(ch) and len(self.text) < MAX_LEN and not (ch == " " and (not self.text or
                                                                                   self.text.endswith(" "))):
                self.text += ch

    def backspace(self):
        self.text = self.text[:-1]

    def randomize(self):
        choices = [n for n in NAMES if n != self.text] or NAMES
        self.text = self.rng.choice(choices)

    def confirm(self):
        if self.ready:
            self.text = self.name
            return NEXT
        self.shake = 0.35
        return None

    def handle_event(self, event):
        if event.type == pygame.TEXTINPUT:
            self.type(event.text)
        elif event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                return BACK
            if event.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                return self.confirm()
            if event.key == pygame.K_BACKSPACE:
                self.backspace()
            elif event.key == pygame.K_TAB:
                self.randomize()
        elif event.type == pygame.MOUSEMOTION:
            self.focus = self._button_at(event.pos)
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            hit = self._button_at(event.pos)
            if hit == "back":
                return BACK
            if hit == "next":
                return self.confirm()
            if hit == "dice":
                self.randomize()
        return None

    def _button_at(self, pos):
        for name, rect in (("back", BACK_RECT), ("next", NEXT_RECT), ("dice", DICE)):
            if widgets.inside(pos, rect):
                return name
        return None

    def update(self, dt):
        self.time += dt
        self.shake = max(0.0, self.shake - dt)

    # ---------- drawing ----------
    def draw(self, surface):
        bg = get_image("menu_bg.png")
        if bg is not None:
            surface.blit(pygame.transform.scale(bg, (self.width, self.height)), (0, 0))
        else:
            surface.fill(theme.SKY[0])
        widgets.dim(surface, 160)
        widgets.title_plate(surface, (self.width // 2, 92), "NAME YOUR HERO")
        widgets.stone_panel(surface, PANEL)
        small = get_font(theme.FONT_SMALL)
        draw_text(surface, "MERLIN'S SUMMONING CIRCLE CALLS A HERO...", small, theme.TEXT_DIM,
                  (self.width // 2, 200), outline=1, center=True)
        draw_text(surface, "WHAT SHALL OAKWOOD CALL YOU?", small, theme.TITLE,
                  (self.width // 2, 230), outline=1, center=True)

        x, y, w, h = BOX
        if self.shake:
            x += 6 if int(self.time * 40) % 2 else -6
        widgets.wood_box(surface, (x, y, w, h), glowing=True)
        font = get_font(theme.FONT_BUTTON)
        shown = self.text if self.text else ""
        color = theme.TEXT if shown else theme.TEXT_DIM
        draw_text(surface, shown or "Type a name", font, color, (x + 22, y + h // 2), outline=2, middle=True)
        if int(self.time * 2) % 2 == 0 and len(self.text) < MAX_LEN:
            cx = x + 24 + (font.size(shown)[0] if shown else 0)
            pygame.draw.rect(surface, theme.TORCH_LIGHT, (cx, y + 16, 4, h - 32))
        draw_text(surface, f"{len(self.text)}/{MAX_LEN}", small, theme.TEXT_DIM, (x + w - 12, y + h + 14),
                  outline=1, center=True)

        widgets.wood_box(surface, DICE, glowing=self.focus == "dice")
        self._draw_die(surface, DICE)

        widgets.button(surface, BACK_RECT, "BACK", selected=self.focus == "back")
        widgets.button(surface, NEXT_RECT, "NEXT", selected=self.focus == "next" or self.ready,
                       enabled=self.ready)
        draw_text(surface, "TYPE A NAME    TAB: RANDOM    ENTER: NEXT    ESC: BACK", small, theme.TEXT_DIM,
                  (self.width // 2, self.height - 22), outline=1, center=True)

    @staticmethod
    def _draw_die(surface, rect):
        x, y, w, h = rect
        face = pygame.Rect(x + 12, y + 12, w - 24, h - 24)
        pygame.draw.rect(surface, theme.OUTLINE, face.inflate(4, 4), border_radius=6)
        pygame.draw.rect(surface, theme.TEXT, face, border_radius=5)
        for dx, dy in ((0.25, 0.25), (0.75, 0.25), (0.5, 0.5), (0.25, 0.75), (0.75, 0.75)):
            pygame.draw.circle(surface, theme.OUTLINE, (face.x + int(face.w * dx), face.y + int(face.h * dy)), 3)
