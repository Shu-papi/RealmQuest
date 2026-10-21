"""
menu_preview.py - Try the main menu and the settings screen on their own.

Run from the repo root:
    python src/ui/dev/menu_preview.py

Up/Down (or W/S, or the mouse) to choose, Enter or click to press.
"Settings" opens the settings screen (Esc or X to come back).
"New Game" just shows a message for now. "Exit" closes the window.
"""
import os
import sys

SRC_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)

import pygame

from ui import theme
from ui.assets import get_font
from ui.menu import MainMenu, NEW_GAME, SETTINGS, EXIT
from ui.settings_data import Settings
from ui.settings_screen import SettingsScreen, BACK, VIDEO_CHANGED
from ui.text import draw_text

SIZE = (theme.SCREEN_W, theme.SCREEN_H)


def main():
    pygame.init()
    settings = Settings.load()
    screen = settings.apply_display(SIZE)
    pygame.display.set_caption("RealmQuest - Main menu preview")
    clock = pygame.time.Clock()

    menu = MainMenu()
    settings_screen = None                 # not None while the settings window is open
    message, message_time = "", 0.0

    running = True
    while running:
        dt = clock.tick(60) / 1000
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                settings.save()
                running = False
                continue

            if settings_screen is not None:            # settings open: it gets the input
                result = settings_screen.handle_event(event)
                if result == BACK:
                    settings_screen = None
                elif result == VIDEO_CHANGED:
                    screen = settings.apply_display(SIZE)
                continue

            action = menu.handle_event(event)
            if action == EXIT:
                running = False
            elif action == SETTINGS:
                settings_screen = SettingsScreen(settings)
            elif action == NEW_GAME:
                message, message_time = "New Game pressed (the game isn't built yet)", 2.0

        menu.update(dt)
        menu.draw(screen)
        if settings_screen is not None:
            settings_screen.update(dt)
            settings_screen.draw(screen)
        if message_time > 0:
            message_time -= dt
            draw_text(screen, message, get_font(theme.FONT_SMALL), theme.TEXT,
                      (theme.SCREEN_W // 2, 600), outline=1, center=True)
        pygame.display.flip()

    pygame.quit()


if __name__ == "__main__":
    main()
