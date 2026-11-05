"""
class_select.py - "Choose your hero": the screen after New Game where the player picks
Warrior, Mage or Archer.

    from ui.class_select import ClassSelect, START, BACK

    picker = ClassSelect()

    # every frame:
    for event in pygame.event.get():
        result = picker.handle_event(event)
        if result == START:  start a run with picker.chosen   ("warrior" / "mage" / "archer")
        if result == BACK:   go back to the main menu
    picker.update(dt)
    picker.draw(screen)

CONTROLS
    Left / Right (or A / D, or the mouse)   choose a class
    Enter (or click START)                 start
    Esc (or click BACK)                    back to the main menu

The cards read their text and numbers from class_info.py (placeholders for now).
"""
import pygame

from . import theme, widgets
from .assets import get_image, get_font
from .class_info import CLASS_ORDER, info, portrait_file, badge_file
from .text import draw_text

START = "start"
BACK = "back"

CARD_W, CARD_H, CARD_GAP = 250, 400, 24
CARDS_TOP = 110
LIFT = 8                         # the chosen card sits a little higher
START_RECT = (310, 530, 340, 56)
BACK_RECT = (96, 536, 150, 44)


SKILL_KEYS = {"skill": "K", "skill_2": "U", "special": "F"}


class ClassSelect:
    def __init__(self, width=theme.SCREEN_W, height=theme.SCREEN_H, hero_name="", portraits=None,
                 skill_keys=None):
        self.width = width
        self.height = height
        self.hero_name = hero_name               # shown above the cards ("Aria, choose your path")
        self.portraits = portraits or {}         # {class: Surface} - the game's own hero art
        self.skill_keys = dict(SKILL_KEYS, **(skill_keys or {}))
        self.selected = 0
        self.time = 0.0
        self.focus_start = False     # True when the START button is highlighted (mouse)

    @property
    def chosen(self):
        return CLASS_ORDER[self.selected]

    # ---------- logic ----------

    def move(self, step):
        self.selected = (self.selected + step) % len(CLASS_ORDER)

    def card_rects(self):
        total = len(CLASS_ORDER) * CARD_W + (len(CLASS_ORDER) - 1) * CARD_GAP
        left = (self.width - total) // 2
        return [(left + i * (CARD_W + CARD_GAP), CARDS_TOP, CARD_W, CARD_H)
                for i in range(len(CLASS_ORDER))]

    def handle_event(self, event):
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                return BACK
            if event.key in (pygame.K_LEFT, pygame.K_a):
                self.move(-1)
            elif event.key in (pygame.K_RIGHT, pygame.K_d):
                self.move(+1)
            elif event.key in (pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_SPACE):
                return START
        elif event.type == pygame.MOUSEMOTION:
            self.focus_start = widgets.inside(event.pos, START_RECT)
            for i, rect in enumerate(self.card_rects()):
                if widgets.inside(event.pos, rect):
                    self.selected = i
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            return self.click(event.pos)
        return None

    def click(self, pos):
        if widgets.inside(pos, START_RECT):
            return START
        if widgets.inside(pos, BACK_RECT):
            return BACK
        for i, rect in enumerate(self.card_rects()):
            if widgets.inside(pos, rect):
                self.selected = i
        return None

    def update(self, dt):
        self.time += dt

    # ---------- drawing ----------

    def draw(self, surface):
        background = get_image("menu_bg.png")
        if background is not None:
            surface.blit(pygame.transform.scale(background, (self.width, self.height)), (0, 0))
        else:
            surface.fill(theme.SKY[0])
        widgets.dim(surface, 170)
        widgets.title_plate(surface, (self.width // 2, 52), "CHOOSE YOUR HERO")
        if self.hero_name:
            draw_text(surface, f"{self.hero_name.upper()}, CHOOSE YOUR PATH", get_font(theme.FONT_SMALL),
                      theme.TORCH_LIGHT, (self.width // 2, 88), outline=1, center=True)
        for i, rect in enumerate(self.card_rects()):
            self._draw_card(surface, i, rect)
        widgets.button(surface, START_RECT, f"START AS {info(self.chosen)['name'].upper()}",
                       selected=True)
        widgets.button(surface, BACK_RECT, "BACK")
        draw_text(surface, "LEFT / RIGHT: CHOOSE    ENTER: START    ESC: BACK",
                  get_font(theme.FONT_SMALL), theme.TEXT_DIM, (self.width // 2, self.height - 22),
                  outline=1, center=True)

    def _draw_card(self, surface, index, rect):
        cls = CLASS_ORDER[index]
        data = info(cls)
        chosen = index == self.selected
        x, y, w, h = rect
        if chosen:
            y -= LIFT
        if chosen:   # a glowing gold edge around the chosen card
            pygame.draw.rect(surface, theme.TORCH_LIGHT, (x - 5, y - 5, w + 10, h + 10))
            pygame.draw.rect(surface, theme.TORCH, (x - 3, y - 3, w + 6, h + 6))
        widgets.wood_box(surface, (x, y, w, h))
        label = get_font(theme.FONT_LABEL)

        # name + badge
        widgets.icon(surface, badge_file(cls), (x + 22, y + 22), size=28)
        draw_text(surface, data["name"].upper(), get_font(theme.FONT_BUTTON), theme.TEXT,
                  (x + 58, y + 36), outline=2, middle=True)
        draw_text(surface, data["role"].upper(), get_font(theme.FONT_SMALL), theme.TITLE,
                  (x + 24, y + 62), outline=1, shadow=False)

        # picture
        box = (x + 22, y + 84, w - 44, 142)
        pygame.draw.rect(surface, theme.OUTLINE, (box[0] - 2, box[1] - 2, box[2] + 4, box[3] + 4))
        pygame.draw.rect(surface, theme.STONE_DARK, box)
        art = self.portraits.get(cls)
        inner = (box[0] + 8, box[1] + 6, box[2] - 16, box[3] - 10)
        if art is not None:              # the hero exactly as they look in the world
            k = min(inner[2] / art.get_width(), inner[3] / art.get_height())
            if k >= 1:
                k = int(k)
            img = pygame.transform.scale(art, (int(art.get_width() * k), int(art.get_height() * k)))
            surface.blit(img, (inner[0] + (inner[2] - img.get_width()) // 2, inner[1] + inner[3] - img.get_height()))
        else:
            widgets.portrait(surface, portrait_file(cls), inner)

        # stats: HP, then the two resource bars of this class
        stats = data["stats"]
        rows = [("icon_heart.png", "HP", stats["hp"])]
        for bar in data["bars"]:
            rows.append(("icon_energy.png", bar.upper(), stats[bar]))
        for r, (icon, name, value) in enumerate(rows):
            ry = y + 230 + r * 27
            widgets.icon(surface, icon, (x + 24, ry), size=22)
            draw_text(surface, name, label, theme.TEXT, (x + 54, ry + 11), outline=2, middle=True)
            draw_text(surface, str(value), label, theme.TEXT, (x + w - 60, ry + 11), outline=2,
                      middle=True)

        # skills
        small = get_font(theme.FONT_SMALL)
        pygame.draw.rect(surface, theme.WOOD, (x + 22, y + 314, w - 44, 2))       # divider line
        for i, (slot, name, _desc) in enumerate(data["skills"]):
            sy = y + 322 + i * 21
            key = self.skill_keys.get(slot, "?")
            pygame.draw.rect(surface, theme.OUTLINE, (x + 22, sy, 22, 17))
            pygame.draw.rect(surface, theme.BRASS, (x + 22, sy, 22, 17), 1)
            draw_text(surface, key, small, theme.TITLE, (x + 33, sy + 9), outline=1, shadow=False, center=True)
            color = theme.TORCH_LIGHT if slot == "special" else theme.TEXT
            draw_text(surface, name.upper(), small, color, (x + 52, sy + 1), outline=1, shadow=False)
