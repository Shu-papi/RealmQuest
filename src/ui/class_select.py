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
from .class_info import CLASS_ORDER, info, portrait_file, badge_file, starting_weapon
from .text import draw_text

START = "start"
BACK = "back"

CARD_W, CARD_H, CARD_GAP = 250, 400, 24
CARDS_TOP = 110
LIFT = 8                         # the chosen card sits a little higher
START_RECT = (310, 530, 340, 56)
BACK_RECT = (96, 536, 150, 44)


class ClassSelect:
    def __init__(self, width=theme.SCREEN_W, height=theme.SCREEN_H):
        self.width = width
        self.height = height
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
        widgets.title_plate(surface, (self.width // 2, 64), "CHOOSE YOUR HERO")
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
        widgets.portrait(surface, portrait_file(cls), (box[0] + 8, box[1] + 6, box[2] - 16, box[3] - 10))

        # stats
        stats = data["stats"]
        rows = [("icon_heart.png", "HP", stats["hp"]), ("icon_shield.png", "ARMOR", stats["armor"]),
                ("icon_energy.png", "ENERGY", stats["energy"])]
        for r, (icon, name, value) in enumerate(rows):
            ry = y + 238 + r * 30
            widgets.icon(surface, icon, (x + 24, ry), size=24)
            draw_text(surface, name, label, theme.TEXT, (x + 56, ry + 12), outline=2, middle=True)
            draw_text(surface, str(value), label, theme.TEXT, (x + w - 60, ry + 12), outline=2,
                      middle=True)

        # starting weapon
        weapon = starting_weapon(cls)
        pygame.draw.rect(surface, theme.WOOD, (x + 22, y + 330, w - 44, 2))       # divider line
        draw_text(surface, "STARTS WITH", get_font(theme.FONT_SMALL), theme.TEXT_DIM,
                  (x + 24, y + 340), outline=1, shadow=False)
        widgets.icon(surface, f"weapon_{weapon.weapon_id}.png", (x + 22, y + 352), size=32)
        draw_text(surface, weapon.name, label, theme.TEXT, (x + 62, y + 368), outline=2, middle=True)
