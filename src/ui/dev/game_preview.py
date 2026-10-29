"""
game_preview.py - Click through ALL the UI screens in order, like the real game will:

    Main menu  ->  New Game  ->  Choose your hero  ->  (in a run)  ->  I = Inventory

Run from the repo root:
    python src/ui/dev/game_preview.py

IN THE RUN (there's no real gameplay yet, this only shows the UI)
    N              walk up to the next weapon on the "floor"
    E              pick it up              (your Interact key from Settings)
    Q / 1-3        switch weapon           (your Switch Weapon key from Settings)
    H              take 1 damage           (to see the HUD drain)
    I              open / close the inventory (the run is PAUSED while it's open)
    ESC            back to the main menu

This file is only a preview. The real game loop belongs to whoever builds the
main game; it can copy how the screens are switched here.
"""
import os
import sys
import types

SRC_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)

import pygame

from inventory import Inventory, make_weapon
from ui import theme
from ui.assets import get_font
from ui.class_info import info
from ui.class_select import ClassSelect, START, BACK as CLASS_BACK
from ui.hud import HUD
from ui.inventory_screen import InventoryScreen, CLOSE
from ui.menu import MainMenu, NEW_GAME, SETTINGS, EXIT
from ui.settings_data import Settings
from ui.settings_screen import SettingsScreen, BACK, VIDEO_CHANGED
from ui.text import draw_text
from ui.weapon_bar import WeaponBar

SIZE = (theme.SCREEN_W, theme.SCREEN_H)
FLOOR_WEAPONS = ["battle_axe", "fire_wand", "short_bow", "greatsword", "crossbow",
                 "apprentice_staff", "iron_sword"]


def new_player(character_class):
    stats = info(character_class)["stats"]          # placeholder numbers from class_info.py
    return types.SimpleNamespace(hp=stats["hp"], max_hp=stats["hp"],
                                 armor=stats["armor"], max_armor=stats["armor"],
                                 energy=stats["energy"], max_energy=stats["energy"])


def draw_floor(screen):
    screen.fill(theme.STONE_DARK)
    for gx in range(0, theme.SCREEN_W, 64):
        for gy in range(0, theme.SCREEN_H, 64):
            pygame.draw.rect(screen, theme.STONE, (gx + 2, gy + 2, 60, 60))


def main():
    pygame.init()
    settings = Settings.load()
    screen = settings.apply_display(SIZE)
    pygame.display.set_caption("RealmQuest - UI flow preview")
    clock = pygame.time.Clock()

    state = "menu"                   # "menu" -> "class_select" -> "run"
    menu, picker = MainMenu(), None
    overlay = None                   # a window on top: SettingsScreen or InventoryScreen
    run = None                       # everything about the current run
    floor_index = -1

    running = True
    while running:
        dt = clock.tick(60) / 1000
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
                continue

            if overlay is not None:                         # a window is open: it gets the keys
                result = overlay.handle_event(event)
                if result in (BACK, CLOSE):
                    overlay = None
                elif result == VIDEO_CHANGED:
                    screen = settings.apply_display(SIZE)
                continue

            if state == "menu":
                action = menu.handle_event(event)
                if action == NEW_GAME:
                    state, picker = "class_select", ClassSelect()
                elif action == SETTINGS:
                    overlay = SettingsScreen(settings)
                elif action == EXIT:
                    running = False

            elif state == "class_select":
                result = picker.handle_event(event)
                if result == CLASS_BACK:
                    state = "menu"
                elif result == START:
                    inventory = Inventory(picker.chosen)
                    run = types.SimpleNamespace(
                        inventory=inventory, player=new_player(picker.chosen), hud=HUD(),
                        bar=WeaponBar(inventory, settings))
                    run.bar.show(f"You are a {info(picker.chosen)['name']}. Good luck!")
                    state = "run"

            elif state == "run" and event.type == pygame.KEYDOWN:
                name = pygame.key.name(event.key)
                if event.key == pygame.K_ESCAPE:
                    state = "menu"
                elif name == "i":
                    overlay = InventoryScreen(run.inventory, run.player)
                elif name == "n":
                    floor_index = (floor_index + 1) % len(FLOOR_WEAPONS)
                    run.bar.set_nearby(make_weapon(FLOOR_WEAPONS[floor_index]))
                elif name == settings.key_for("interact") and run.bar.nearby is not None:
                    run.bar.pick_up(run.bar.nearby)
                elif name == "h":
                    if run.player.armor > 0:
                        run.player.armor -= 1
                    else:
                        run.player.hp = max(0, run.player.hp - 1)
                else:
                    run.bar.handle_event(event)

        # ----- update (the run is PAUSED while a window is open) -----
        if overlay is not None:
            overlay.update(dt)
        elif state == "menu":
            menu.update(dt)
        elif state == "class_select":
            picker.update(dt)
        elif state == "run":
            run.hud.update(dt, run.player)
            run.bar.update(dt)

        # ----- draw -----
        if state == "menu":
            menu.draw(screen)
        elif state == "class_select":
            picker.draw(screen)
        elif state == "run":
            draw_floor(screen)
            run.hud.draw(screen)
            run.bar.draw(screen)
            if overlay is None:
                small = get_font(theme.FONT_SMALL)
                for i, line in enumerate(["N: NEXT FLOOR WEAPON   E: PICK UP   Q / 1-3: SWITCH",
                                          "H: TAKE DAMAGE   I: INVENTORY   ESC: MAIN MENU"]):
                    draw_text(screen, line, small, theme.TEXT, (16, 140 + i * 24), outline=1)
        if overlay is not None:
            overlay.draw(screen)
            if state == "run":
                draw_text(screen, "PAUSED", get_font(theme.FONT_BUTTON), theme.TITLE,
                          (theme.SCREEN_W // 2, 30), outline=2, center=True)
        pygame.display.flip()

    settings.save()
    pygame.quit()


if __name__ == "__main__":
    main()
