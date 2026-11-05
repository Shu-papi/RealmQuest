"""
Checks the name screen, the CONTINUE button and the Home -> Name -> Class flow.
Run from the repo root:  python -m unittest discover -s src/ui/tests
"""
import json
import os
import sys
import tempfile
import unittest

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
SRC_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)

import pygame

from ui.app_screens import FrontEnd
from ui.menu import MainMenu, CONTINUE, NEW_GAME
from ui.name_entry import NameEntry, NEXT, BACK, MAX_LEN, clean
from ui.settings_data import Settings


def key(k):
    return pygame.event.Event(pygame.KEYDOWN, key=k, mod=0, unicode="")


def text(s):
    return pygame.event.Event(pygame.TEXTINPUT, text=s)


class NameScreen(unittest.TestCase):
    def test_typing_and_limits(self):
        n = NameEntry()
        n.handle_event(text("Sir <Bob>!"))
        self.assertEqual(n.name, "Sir Bob")
        n.handle_event(text("x" * 40))
        self.assertEqual(len(n.text), MAX_LEN)
        n.handle_event(key(pygame.K_BACKSPACE))
        self.assertEqual(len(n.text), MAX_LEN - 1)

    def test_needs_a_letter(self):
        n = NameEntry()
        self.assertIsNone(n.handle_event(key(pygame.K_RETURN)))
        n.handle_event(text("   "))
        self.assertIsNone(n.handle_event(key(pygame.K_RETURN)))
        n.handle_event(text("Ash"))
        self.assertEqual(n.handle_event(key(pygame.K_RETURN)), NEXT)

    def test_random_and_back(self):
        n = NameEntry()
        n.handle_event(key(pygame.K_TAB))
        self.assertTrue(n.ready)
        self.assertEqual(n.handle_event(key(pygame.K_ESCAPE)), BACK)

    def test_clean(self):
        self.assertEqual(clean("  a   b  "), "a b")

    def test_draws(self):
        pygame.init()
        NameEntry("Aria").draw(pygame.Surface((960, 640)))


class MenuWithContinue(unittest.TestCase):
    def test_continue_comes_first_when_there_is_a_save(self):
        front = FrontEnd(Settings(), save_info="Aria - Mage - Lv 3")
        self.assertEqual([b[1] for b in front.menu.buttons][:2], [CONTINUE, NEW_GAME])
        self.assertEqual(front.handle_event(key(pygame.K_RETURN)), ("continue",))

    def test_no_continue_without_a_save(self):
        front = FrontEnd(Settings())
        self.assertNotIn(CONTINUE, [b[1] for b in front.menu.buttons])

    def test_four_buttons_fit_in_the_frame(self):
        menu = MainMenu(buttons=FrontEnd(Settings(), save_info="x").menu.buttons)
        x, y, w, h = menu.button_rects()[-1]
        self.assertLessEqual(y + h, 547)          # the inside of screen_frame.png ends at y 547


class Flow(unittest.TestCase):
    def test_home_name_class_start(self):
        front = FrontEnd(Settings())
        front.handle_event(key(pygame.K_RETURN))               # NEW GAME
        self.assertEqual(front.screen, "name")
        front.handle_event(text("Aria"))
        front.handle_event(key(pygame.K_RETURN))
        self.assertEqual(front.screen, "class")
        self.assertEqual(front.class_screen.hero_name, "Aria")
        front.handle_event(key(pygame.K_RIGHT))
        self.assertEqual(front.handle_event(key(pygame.K_RETURN)), ("new", "Aria", "mage"))

    def test_back_steps(self):
        front = FrontEnd(Settings())
        front.handle_event(key(pygame.K_RETURN))
        front.handle_event(key(pygame.K_ESCAPE))
        self.assertEqual(front.screen, "menu")

    def test_mouse_is_mapped_into_the_centred_screen(self):
        pygame.init()
        window = pygame.Surface((1152, 648))
        front = FrontEnd(Settings())
        front.draw(window)
        self.assertEqual(front.offset, (96, 4))
        x, y, w, h = front.menu.button_rects()[1]               # SETTINGS
        front.handle_event(pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=1,
                                              pos=(x + 10 + 96, y + 10 + 4)))
        self.assertEqual(front.screen, "settings")
        front.draw(window)


class OldSettingsFiles(unittest.TestCase):
    def test_old_space_dash_moves_to_shift_and_new_keys_appear(self):
        path = os.path.join(tempfile.mkdtemp(), "settings.json")
        old = {"key_bindings": {"move_up": "w", "attack": "j", "skill": "k", "dash": "space",
                                "switch_weapon": "q", "interact": "e"}}
        with open(path, "w") as f:
            json.dump(old, f)
        s = Settings.load(path)
        self.assertEqual(s.key_for("dash"), "left shift")
        self.assertEqual((s.key_for("skill_2"), s.key_for("special")), ("u", "f"))
        self.assertEqual(len(set(s.key_bindings.values())), len(s.key_bindings))

    def test_new_files_keep_the_players_choice(self):
        path = os.path.join(tempfile.mkdtemp(), "settings.json")
        s = Settings()
        s.rebind("dash", "space")
        s.save(path)
        self.assertEqual(Settings.load(path).key_for("dash"), "space")


if __name__ == "__main__":
    unittest.main()
