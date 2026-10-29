"""
weapon_preview.py - Try the weapon slots (with the HUD) on their own.

Run from the repo root:
    python src/ui/dev/weapon_preview.py

KEYS
    F1 / F2 / F3   play as Warrior / Mage / Archer (starts a fresh inventory)
    N              walk up to the next weapon on the "floor" (shows the pick-up prompt)
    E              pick it up (uses your Interact key from Settings)
    Q              switch weapon (uses your Switch Weapon key from Settings)
    1 / 2 / 3      jump to a slot
    X              drop the weapon in your hands
    ESC            quit

Try picking up a bow as the Warrior: you'll get "Archers only!".
"""
import os
import sys

SRC_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)

import pygame

from inventory import Inventory, make_weapon, list_weapons
from ui import theme
from ui.assets import get_font
from ui.hud import HUD
from ui.settings_data import Settings
from ui.text import draw_text
from ui.weapon_bar import WeaponBar

FLOOR_ORDER = ["battle_axe", "fire_wand", "short_bow", "greatsword", "crossbow",
               "apprentice_staff", "iron_sword"]


class PreviewPlayer:
    hp, max_hp, armor, max_armor, energy, max_energy = 5, 5, 5, 5, 200, 200


def main():
    pygame.init()
    screen = pygame.display.set_mode((theme.SCREEN_W, theme.SCREEN_H))
    pygame.display.set_caption("RealmQuest - Weapon slots preview")
    clock = pygame.time.Clock()
    settings = Settings.load()

    def new_run(character_class):
        inventory = Inventory(character_class)
        return character_class, WeaponBar(inventory, settings)

    character_class, bar = new_run("warrior")
    hud = HUD(x=12, y=12)
    player = PreviewPlayer()
    floor_index = -1

    running = True
    while running:
        dt = clock.tick(60) / 1000
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN:
                name = pygame.key.name(event.key)
                if event.key == pygame.K_ESCAPE:
                    running = False
                elif event.key in (pygame.K_F1, pygame.K_F2, pygame.K_F3):
                    cls = {pygame.K_F1: "warrior", pygame.K_F2: "mage", pygame.K_F3: "archer"}[event.key]
                    character_class, bar = new_run(cls)
                    bar.show(f"Playing as {cls.title()}")
                elif name == "n":
                    floor_index = (floor_index + 1) % len(FLOOR_ORDER)
                    bar.set_nearby(make_weapon(FLOOR_ORDER[floor_index]))
                elif name == settings.key_for("interact") and bar.nearby is not None:
                    bar.pick_up(bar.nearby)
                elif name == "x":
                    dropped = bar.inventory.drop_current()
                    if dropped:
                        bar.show(f"Dropped {dropped.name}")
                else:
                    bar.handle_event(event)

        hud.update(dt, player)
        bar.update(dt)

        screen.fill(theme.STONE_DARK)
        for gx in range(0, theme.SCREEN_W, 64):          # simple dungeon floor tiles
            for gy in range(0, theme.SCREEN_H, 64):
                pygame.draw.rect(screen, theme.STONE, (gx + 2, gy + 2, 60, 60))
        hud.draw(screen)
        bar.draw(screen)
        small = get_font(theme.FONT_SMALL)
        for i, line in enumerate([f"CLASS: {character_class.upper()}   (F1 / F2 / F3 to change)",
                                  "N: walk to next floor weapon    E: pick up",
                                  "Q or 1-3: switch weapon    X: drop"]):
            draw_text(screen, line, small, theme.TEXT, (16, 130 + i * 24), outline=1)
        pygame.display.flip()

    pygame.quit()


if __name__ == "__main__":
    main()
