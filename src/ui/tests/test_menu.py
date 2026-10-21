"""
Checks the main menu has the buttons from the game plan and responds to keys/mouse.
Run from the repo root:  python -m unittest discover -s src/ui/tests
"""
import os
import sys
import types
import unittest

SRC_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)

try:
    import pygame
except ImportError:
    from pygame_stub import install
    install()
    import pygame

REAL_PYGAME = hasattr(pygame, "get_init")       # the test stub doesn't have this

import ui.assets as assets
from ui.menu import MainMenu, NEW_GAME, SETTINGS, EXIT


class TestButtons(unittest.TestCase):
    def setUp(self):
        self.menu = MainMenu()

    def test_has_new_game_settings_exit_in_order(self):
        actions = [action for _, action, _ in self.menu.buttons]
        self.assertEqual(actions, [NEW_GAME, SETTINGS, EXIT])

    def test_starts_on_new_game(self):
        self.assertEqual(self.menu.activate(), NEW_GAME)

    def test_move_down_and_wrap(self):
        self.menu.move(+1)
        self.assertEqual(self.menu.activate(), SETTINGS)
        self.menu.move(+1)
        self.menu.move(+1)
        self.assertEqual(self.menu.activate(), NEW_GAME)

    def test_move_up_wraps_to_exit(self):
        self.menu.move(-1)
        self.assertEqual(self.menu.activate(), EXIT)


class TestMouse(unittest.TestCase):
    def setUp(self):
        self.menu = MainMenu()

    def test_point_inside_each_button(self):
        for index, (x, y, w, h) in enumerate(self.menu.button_rects()):
            self.assertEqual(self.menu.button_at((x + w // 2, y + h // 2)), index)

    def test_point_outside_buttons(self):
        self.assertIsNone(self.menu.button_at((5, 5)))

    def test_buttons_fit_on_screen(self):
        for x, y, w, h in self.menu.button_rects():
            self.assertGreaterEqual(x, 0)
            self.assertLessEqual(x + w, self.menu.width)
            self.assertLessEqual(y + h, self.menu.height)


class TestEvents(unittest.TestCase):
    """Only runs with real pygame installed (the test stub has no key codes)."""

    def setUp(self):
        if not hasattr(pygame, "KEYDOWN"):
            self.skipTest("real pygame not installed")
        self.menu = MainMenu()

    def key(self, key):
        return self.menu.handle_event(types.SimpleNamespace(type=pygame.KEYDOWN, key=key))

    def test_keys(self):
        self.assertIsNone(self.key(pygame.K_DOWN))
        self.assertEqual(self.key(pygame.K_RETURN), SETTINGS)

    def test_click(self):
        x, y, w, h = self.menu.button_rects()[2]
        event = types.SimpleNamespace(type=pygame.MOUSEBUTTONDOWN, button=1, pos=(x + 5, y + 5))
        self.assertEqual(self.menu.handle_event(event), EXIT)


class TestDrawing(unittest.TestCase):
    def tearDown(self):
        assets.ENABLED = True
        assets.clear_cache()

    def test_draw_without_pictures_uses_fallback(self):
        assets.ENABLED = False
        menu = MainMenu()
        menu.update(0.5)
        menu.draw(pygame.Surface((menu.width, menu.height)))

    def test_draw_with_pictures(self):
        if not REAL_PYGAME:
            self.skipTest("real pygame needed to load pictures")
        menu = MainMenu()
        menu.draw(pygame.Surface((menu.width, menu.height)))
        self.assertIsNotNone(menu._get_button_images())

    def test_title_fits_on_the_sign(self):
        if not REAL_PYGAME:
            self.skipTest("real pygame needed to measure fonts")
        from ui.menu import TITLE
        from ui import theme
        w, _ = assets.get_font(theme.FONT_TITLE).size(TITLE)
        self.assertLessEqual(w, 330)          # the wooden board on title_sign.png is ~330 px wide


class TestPictures(unittest.TestCase):
    NEEDED = ["menu_bg.png", "screen_frame.png", "title_sign.png", "hero.png", "button.png",
              "button_selected.png", "panel.png", "title_plate.png"] + \
        [f"icon_{n}.png" for n in ("play", "gear", "sound", "video", "controls", "exit",
                                   "heart", "shield", "energy")]

    def test_all_pictures_are_in_assets_ui(self):
        for name in self.NEEDED:
            self.assertTrue(os.path.exists(os.path.join(assets.UI_ASSETS_DIR, name)), name)

    def test_all_fonts_are_in_assets_ui_fonts(self):
        from ui import theme
        for spec in (theme.FONT_TITLE, theme.FONT_BUTTON, theme.FONT_SMALL, theme.FONT_HUD):
            self.assertTrue(os.path.exists(os.path.join(assets.UI_ASSETS_DIR, "fonts", spec[0])),
                            spec[0])

    def test_buttons_use_existing_icons(self):
        for _, _, icon in MainMenu().buttons:
            self.assertIn(icon, self.NEEDED)


if __name__ == "__main__":
    unittest.main()
