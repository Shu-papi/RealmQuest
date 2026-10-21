"""
weapon_bar.py - Shows the player's weapon slots in the bottom-right corner (like Soul Knight),
plus "Press E to pick up" prompts and short messages like "Archers only!".

    from inventory import Inventory, make_weapon
    from ui.weapon_bar import WeaponBar

    inventory = Inventory("warrior")
    bar = WeaponBar(inventory, settings)        # settings: for the player's chosen keys

    # every frame:
    for event in pygame.event.get():
        bar.handle_event(event)                 # switch weapon key, or 1 / 2 / 3
    bar.set_nearby(weapon_on_floor_or_None)     # shows the pick-up prompt
    bar.update(dt)
    bar.draw(screen)

    # when the player presses the interact key next to a weapon:
    picked_up, dropped = bar.pick_up(weapon)    # also shows the right message
    if dropped: ...put 'dropped' on the floor...

The bar only SHOWS the inventory and passes key presses to it. Picking up and
switching rules live in src/inventory/inventory.py.

PICTURES: slot.png, slot_selected.png, weapon_<id>.png, badge_<class>.png,
          icon_energy.png  (all optional)
"""
import pygame

from . import theme
from .assets import get_image, get_font, nine_slice
from .text import draw_text

SLOT = 64
SLOT_GAP = 10
MARGIN = 16
INFO_H = 44
INFO_W = 290
POP_TIME = 0.15                 # the selected slot "pops" bigger for a moment after switching
MESSAGE_TIME = 1.8

CLASS_NAMES = {"warrior": "Warriors", "mage": "Mages", "archer": "Archers"}
GOOD = (150, 230, 120)          # message colours
BAD = (255, 110, 90)


class WeaponBar:
    def __init__(self, inventory, settings=None, screen_size=(theme.SCREEN_W, theme.SCREEN_H)):
        self.inventory = inventory
        self.settings = settings
        self.screen_w, self.screen_h = screen_size
        self.nearby = None                  # weapon on the floor next to the player
        self.message = ""
        self.message_color = theme.TEXT
        self.message_time = 0.0
        self.pop = 0.0
        self._info_box = None

    # ---------- logic (no drawing, easy to test) ----------

    def key_name(self, action, default):
        return self.settings.key_for(action) if self.settings else default

    def switch_next(self):
        before = self.inventory.current_index
        self.inventory.switch_next()
        if self.inventory.current_index != before:
            self.pop = POP_TIME

    def select_slot(self, index):
        before = self.inventory.current_index
        self.inventory.select_slot(index)
        if self.inventory.current_index != before:
            self.pop = POP_TIME

    def pick_up(self, weapon):
        """Try to pick up 'weapon'. Shows a message. Returns (picked_up, dropped)."""
        picked_up, dropped = self.inventory.pick_up(weapon)
        if not picked_up:
            self.show(f"{CLASS_NAMES.get(weapon.weapon_class, weapon.weapon_class)} only!", BAD)
        elif dropped is not None:
            self.show(f"Swapped {dropped.name} for {weapon.name}", GOOD)
            self.pop = POP_TIME
        else:
            self.show(f"Picked up {weapon.name}", GOOD)
            self.pop = POP_TIME
        if picked_up and self.nearby is weapon:
            self.nearby = None
        return picked_up, dropped

    def set_nearby(self, weapon):
        self.nearby = weapon

    def prompt(self):
        """The text shown when standing next to a weapon (or '' if none)."""
        if self.nearby is None:
            return ""
        if not self.inventory.can_use(self.nearby):
            cls = CLASS_NAMES.get(self.nearby.weapon_class, self.nearby.weapon_class)
            return f"{self.nearby.name}  ({cls} only)"
        key = self.key_name("interact", "e").upper()
        return f"Press {key} to pick up {self.nearby.name}"

    def show(self, text, color=theme.TEXT):
        self.message, self.message_color, self.message_time = text, color, MESSAGE_TIME

    def handle_event(self, event):
        """Switch weapons with the player's key, or 1 / 2 / 3. Returns True if it used the key."""
        if event.type != pygame.KEYDOWN:
            return False
        name = pygame.key.name(event.key)
        if name == self.key_name("switch_weapon", "q"):
            self.switch_next()
            return True
        if name in ("1", "2", "3", "4", "5")[: len(self.inventory.slots)]:
            self.select_slot(int(name) - 1)
            return True
        return False

    def update(self, dt):
        self.pop = max(0.0, self.pop - dt)
        self.message_time = max(0.0, self.message_time - dt)

    # ---------- where things are ----------

    def slot_rects(self):
        count = len(self.inventory.slots)
        total = count * SLOT + (count - 1) * SLOT_GAP
        left = self.screen_w - MARGIN - total
        top = self.screen_h - MARGIN - SLOT
        return [(left + i * (SLOT + SLOT_GAP), top, SLOT, SLOT) for i in range(count)]

    def info_rect(self):
        """The name box sits above the slots, lined up with their right edge."""
        _, y, _, _ = self.slot_rects()[0]
        right = self.slot_rects()[-1][0] + SLOT
        return (right - INFO_W, y - INFO_H - 8, INFO_W, INFO_H)

    # ---------- drawing ----------

    def draw(self, surface):
        self._draw_info(surface)
        for i, rect in enumerate(self.slot_rects()):
            self._draw_slot(surface, i, rect)
        small = get_font(theme.FONT_SMALL)
        text = self.prompt()
        if text:
            color = BAD if not self.inventory.can_use(self.nearby) else theme.TEXT
            draw_text(surface, text, small, color, (self.screen_w // 2, self.screen_h - 90),
                      outline=2, center=True)
        if self.message_time > 0:
            draw_text(surface, self.message, get_font(theme.FONT_LABEL), self.message_color,
                      (self.screen_w // 2, self.screen_h - 130), outline=2, center=True)

    def _draw_slot(self, surface, index, rect):
        x, y, w, h = rect
        selected = index == self.inventory.current_index
        grow = 4 if (selected and self.pop > 0) else 0
        picture = get_image("slot_selected.png" if selected else "slot.png")
        if picture is not None:
            if grow:
                picture = pygame.transform.scale(picture, (w + grow * 2, h + grow * 2))
            surface.blit(picture, (x - grow, y - grow))
        else:
            pygame.draw.rect(surface, theme.OUTLINE, (x - 2 - grow, y - 2 - grow, w + 4 + grow * 2, h + 4 + grow * 2))
            pygame.draw.rect(surface, theme.BRASS if selected else theme.WOOD_DARK,
                             (x - grow, y - grow, w + grow * 2, h + grow * 2))
            pygame.draw.rect(surface, theme.TORCH if selected else theme.STONE_DARK,
                             (x + 6, y + 6, w - 12, h - 12))

        weapon = self.inventory.slots[index]
        if weapon is not None:
            icon = get_image(f"weapon_{weapon.weapon_id}.png") if weapon.weapon_id else None
            if icon is not None:
                surface.blit(icon, (x + (w - icon.get_width()) // 2, y + (h - icon.get_height()) // 2))
            else:   # no picture: show the first letters of the name
                draw_text(surface, weapon.name[:3].upper(), get_font(theme.FONT_LABEL), theme.TEXT,
                          (x + w // 2, y + h // 2), outline=2, center=True)
        draw_text(surface, str(index + 1), get_font(theme.FONT_SMALL), theme.TEXT_DIM,
                  (x + 6, y + 2), outline=1, shadow=False)

    def _draw_info(self, surface):
        """The box above the slots: badge + weapon name + energy cost."""
        weapon = self.inventory.current
        x, y, w, h = self.info_rect()
        if self._info_box is None:
            slot = get_image("slot.png")
            self._info_box = nine_slice(slot, w, h, 14) if slot is not None else False
        if self._info_box:
            surface.blit(self._info_box, (x, y))
        else:
            pygame.draw.rect(surface, theme.OUTLINE, (x - 2, y - 2, w + 4, h + 4))
            pygame.draw.rect(surface, theme.WOOD_DARK, (x, y, w, h))
            pygame.draw.rect(surface, theme.STONE_DARK, (x + 5, y + 5, w - 10, h - 10))
        if weapon is None:
            draw_text(surface, "Empty hands", get_font(theme.FONT_LABEL), theme.TEXT_DIM,
                      (x + 14, y + h // 2), outline=2, middle=True)
            return

        left = x + 12
        badge = get_image(f"badge_{weapon.weapon_class}.png")
        if badge is not None:
            surface.blit(badge, (left, y + (h - badge.get_height()) // 2))
            left += badge.get_width() + 8
        draw_text(surface, weapon.name, get_font(theme.FONT_LABEL), theme.TEXT,
                  (left, y + h // 2), outline=2, middle=True)

        # energy cost on the right, e.g. [diamond] 2
        cost_w, _ = draw_text(surface, str(weapon.energy_cost), get_font(theme.FONT_LABEL),
                              (140, 190, 255), (x + w - 34, y + h // 2), outline=2, middle=True)
        energy = get_image("icon_energy.png")
        if energy is not None:
            small = pygame.transform.scale(energy, (20, 20))
            surface.blit(small, (x + w - 58, y + (h - 20) // 2))
