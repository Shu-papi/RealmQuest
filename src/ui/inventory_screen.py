"""
inventory_screen.py - The inventory window opened DURING a run (e.g. with the I key).
The game should pause while it's open.

    from ui.inventory_screen import InventoryScreen, CLOSE

    window = InventoryScreen(inventory, player)     # player: for HP / armor / energy

    # every frame, while it's open:
    for event in pygame.event.get():
        if window.handle_event(event) == CLOSE:
            close it and un-pause the game
    window.update(dt)
    ...draw the (paused) game...
    window.draw(screen)

LEFT:   the class (badge, name, picture) and HP / Armor / Energy
MIDDLE: the 3 weapon slots (the glowing one is in your hands, the arrow is what you're looking at)
RIGHT:  details of the weapon you're looking at + EQUIP button

CONTROLS
    Up / Down or 1 / 2 / 3 (or click a slot)   look at a slot
    Enter (or click EQUIP)                     put that weapon in your hands
    Esc or I                                   close
"""
import pygame

from . import theme, widgets
from .assets import get_font
from .class_info import info, portrait_file, badge_file
from .text import draw_text, text_width

CLOSE = "close"

PANEL = (70, 100, 820, 470)
LEFT_BOX = (98, 150, 254, 380)
DETAIL_BOX = (570, 150, 290, 380)
SLOT_SIZE = 96
SLOTS_X, SLOTS_TOP, SLOTS_STEP = 440, 196, 112
EQUIP_RECT = (592, 456, 246, 52)


class InventoryScreen:
    def __init__(self, inventory, player=None, toggle_key="i"):
        self.inventory = inventory
        self.player = player
        self.toggle_key = toggle_key
        self.viewing = inventory.current_index      # the slot whose details are shown
        self.time = 0.0

    # ---------- logic ----------

    @property
    def viewed_weapon(self):
        return self.inventory.slots[self.viewing]

    def equip_state(self):
        """'equip', 'equipped' (already in hand) or 'empty'."""
        if self.viewed_weapon is None:
            return "empty"
        if self.viewing == self.inventory.current_index:
            return "equipped"
        return "equip"

    def look_at(self, index):
        if 0 <= index < len(self.inventory.slots):
            self.viewing = index

    def move(self, step):
        self.viewing = (self.viewing + step) % len(self.inventory.slots)

    def equip(self):
        if self.equip_state() == "equip":
            self.inventory.select_slot(self.viewing)
            return True
        return False

    def slot_rects(self):
        return [(SLOTS_X, SLOTS_TOP + i * SLOTS_STEP, SLOT_SIZE, SLOT_SIZE)
                for i in range(len(self.inventory.slots))]

    def handle_event(self, event):
        if event.type == pygame.KEYDOWN:
            name = pygame.key.name(event.key)
            if event.key == pygame.K_ESCAPE or name == self.toggle_key:
                return CLOSE
            if event.key in (pygame.K_UP, pygame.K_w):
                self.move(-1)
            elif event.key in (pygame.K_DOWN, pygame.K_s):
                self.move(+1)
            elif name in ("1", "2", "3", "4", "5"):
                self.look_at(int(name) - 1)
            elif event.key in (pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_SPACE):
                self.equip()
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            return self.click(event.pos)
        return None

    def click(self, pos):
        for i, rect in enumerate(self.slot_rects()):
            if widgets.inside(pos, rect):
                if self.viewing == i:          # clicking the same slot again equips it
                    self.equip()
                self.look_at(i)
                return None
        if widgets.inside(pos, EQUIP_RECT):
            self.equip()
        return None

    def update(self, dt):
        self.time += dt

    # ---------- drawing ----------

    def draw(self, surface):
        widgets.dim(surface, 165)
        widgets.stone_panel(surface, PANEL)
        widgets.title_plate(surface, (PANEL[0] + PANEL[2] // 2, PANEL[1]), "INVENTORY")
        self._draw_character(surface)
        self._draw_slots(surface)
        self._draw_details(surface)
        draw_text(surface, "UP / DOWN OR 1-3: LOOK    ENTER: EQUIP    I / ESC: CLOSE",
                  get_font(theme.FONT_SMALL), theme.TEXT_DIM, (PANEL[0] + PANEL[2] // 2, 548),
                  outline=1, center=True)

    def _draw_character(self, surface):
        cls = self.inventory.character_class
        data = info(cls)
        x, y, w, h = LEFT_BOX
        widgets.wood_box(surface, LEFT_BOX)
        label = get_font(theme.FONT_LABEL)
        widgets.icon(surface, badge_file(cls), (x + 18, y + 18), size=32)
        draw_text(surface, data["name"].upper(), get_font(theme.FONT_BUTTON), theme.TEXT,
                  (x + 60, y + 34), outline=2, middle=True)

        box = (x + 20, y + 64, w - 40, 166)
        pygame.draw.rect(surface, theme.BRASS, (box[0] - 2, box[1] - 2, box[2] + 4, box[3] + 4))
        pygame.draw.rect(surface, theme.STONE_DARK, box)
        widgets.portrait(surface, portrait_file(cls), (box[0] + 10, box[1] + 8, box[2] - 20, box[3] - 14))

        stats = data["stats"]
        rows = [
            ("icon_heart.png", "HP", "hp", "max_hp", stats["hp"]),
            ("icon_shield.png", "ARMOR", "armor", "max_armor", stats["armor"]),
            ("icon_energy.png", "ENERGY", "energy", "max_energy", stats["energy"]),
        ]
        for r, (icon, name, now_attr, max_attr, default) in enumerate(rows):
            ry = y + 250 + r * 40
            now = getattr(self.player, now_attr, default)
            most = getattr(self.player, max_attr, default)
            widgets.icon(surface, icon, (x + 20, ry), size=26)
            draw_text(surface, name, label, theme.TEXT, (x + 56, ry + 13), outline=2, middle=True)
            value = f"{int(now)}/{int(most)}"
            vw = text_width(label, value)
            draw_text(surface, value, label, theme.TEXT, (x + w - 22 - vw, ry + 13), outline=2,
                      middle=True)

    def _draw_slots(self, surface):
        draw_text(surface, "WEAPONS", get_font(theme.FONT_LABEL), theme.TITLE,
                  (SLOTS_X + SLOT_SIZE // 2, 166), outline=2, center=True)
        number_font = get_font(theme.FONT_BUTTON)
        for i, rect in enumerate(self.slot_rects()):
            x, y, w, h = rect
            in_hand = i == self.inventory.current_index
            widgets.wood_box(surface, rect, glowing=in_hand)
            weapon = self.inventory.slots[i]
            if weapon is not None:
                if not widgets.icon(surface, f"weapon_{weapon.weapon_id}.png", (x + 12, y + 12), size=72):
                    draw_text(surface, weapon.name[:3].upper(), number_font, theme.TEXT,
                              (x + w // 2, y + h // 2), outline=2, center=True)
            else:
                draw_text(surface, "empty", get_font(theme.FONT_LABEL), theme.TEXT_DIM,
                          (x + w // 2, y + h // 2), outline=2, center=True)
            looking = i == self.viewing
            draw_text(surface, str(i + 1), number_font, theme.TITLE if looking else theme.TEXT_DIM,
                      (x - 26, y + h // 2), outline=2, center=True)
            if looking:                      # a gold arrow pointing at the slot you're looking at
                ax, ay = x - 52, y + h // 2
                for k, height in enumerate((14, 10, 6, 2)):
                    pygame.draw.rect(surface, theme.TITLE, (ax + k * 3, ay - height // 2, 3, height))
            if in_hand:
                draw_text(surface, "IN HAND", get_font(theme.FONT_SMALL), theme.TITLE,
                          (x + w // 2, y + h + 8), outline=1, center=True)

    def _draw_details(self, surface):
        x, y, w, h = DETAIL_BOX
        widgets.wood_box(surface, DETAIL_BOX)
        weapon = self.viewed_weapon
        label = get_font(theme.FONT_LABEL)
        if weapon is None:
            draw_text(surface, "Empty slot", get_font(theme.FONT_BUTTON), theme.TEXT_DIM,
                      (x + w // 2, y + 120), outline=2, center=True)
            draw_text(surface, "Pick up a weapon in the", label, theme.TEXT_DIM,
                      (x + w // 2, y + 170), outline=2, center=True)
            draw_text(surface, "dungeon to fill it.", label, theme.TEXT_DIM,
                      (x + w // 2, y + 196), outline=2, center=True)
        else:
            widgets.wood_box(surface, (x + 22, y + 22, 64, 64))
            widgets.icon(surface, f"weapon_{weapon.weapon_id}.png", (x + 30, y + 30), size=48)
            draw_text(surface, weapon.name, get_font(theme.FONT_BUTTON), theme.TEXT,
                      (x + 100, y + 38), outline=2, middle=True)
            class_name = info(weapon.weapon_class)["name"]
            widgets.icon(surface, badge_file(weapon.weapon_class), (x + 100, y + 60), size=22)
            draw_text(surface, class_name, label, (255, 150, 120), (x + 128, y + 71),
                      outline=2, middle=True)

            for i, line in enumerate(_wrap(weapon.description, 26)[:3]):
                draw_text(surface, line, label, (214, 204, 186), (x + 22, y + 104 + i * 24), outline=2)
            pygame.draw.rect(surface, theme.WOOD, (x + 22, y + 178, w - 44, 2))
            rows = [("Damage", str(weapon.damage)), ("Energy cost", str(weapon.energy_cost)),
                    ("Range", info(weapon.weapon_class)["range"])]
            for i, (name, value) in enumerate(rows):
                ry = y + 202 + i * 34
                draw_text(surface, name, label, theme.TEXT, (x + 22, ry), outline=2, middle=True)
                vw = text_width(label, value)
                draw_text(surface, value, label, theme.TEXT, (x + w - 26 - vw, ry), outline=2,
                          middle=True)

        state = self.equip_state()
        text = {"equip": "EQUIP", "equipped": "IN HAND", "empty": "EQUIP"}[state]
        widgets.button(surface, EQUIP_RECT, text, selected=state == "equip", enabled=state == "equip")


def _wrap(text, width):
    """Split text into lines of about 'width' characters, on spaces."""
    lines, line = [], ""
    for word in text.split():
        if line and len(line) + 1 + len(word) > width:
            lines.append(line)
            line = word
        else:
            line = f"{line} {word}".strip()
    if line:
        lines.append(line)
    return lines
