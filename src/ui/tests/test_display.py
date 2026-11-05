"""
Checks ui.display.Display: the game's canvas fills any window (keeping its shape) and mouse
positions are turned back into canvas positions.
Run from the repo root:  python -m unittest discover -s src/ui/tests
"""
import os
import sys
import unittest

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
SRC_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)

import pygame

if not hasattr(pygame, "Rect") or getattr(pygame, "IS_STUB", False):
    raise unittest.SkipTest("needs real pygame")

from ui.display import Display          # noqa: E402
from ui.settings_data import Settings    # noqa: E402


class FakeSettings(Settings):
    def __init__(self, size):
        super().__init__()
        self.size = size

    def open_window(self, size=None):
        return pygame.display.set_mode(self.size)


class Fill(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pygame.init()

    def open(self, size):
        d = Display((1152, 648))
        d.open(FakeSettings(size))
        return d

    def test_16_by_9_fills_the_whole_screen(self):
        for size in ((1920, 1080), (1280, 720), (2560, 1440), (1152, 648)):
            d = self.open(size)
            self.assertEqual(d.view, pygame.Rect(0, 0, *size), size)

    def test_other_shapes_get_bars_but_keep_the_shape(self):
        d = self.open((1024, 768))
        self.assertEqual(d.view.w, 1024)
        self.assertAlmostEqual(d.view.w / d.view.h, 1152 / 648, places=2)
        self.assertGreater(d.view.y, 0)

    def test_mouse_lands_on_the_same_spot_of_the_game(self):
        d = self.open((1920, 1080))
        self.assertEqual(d.to_canvas((960, 540)), (576, 324))
        self.assertEqual(d.to_canvas((1919, 1079)), (1151, 647))
        ev = d.map_event(pygame.event.Event(pygame.MOUSEBUTTONDOWN, pos=(1920 // 4, 1080 // 4), button=1))
        self.assertEqual(ev.pos, (288, 162))
        self.assertEqual(ev.button, 1)

    def test_present_scales_the_canvas_up(self):
        d = self.open((1920, 1080))
        d.canvas.fill((255, 0, 0))
        d.present()
        win = pygame.display.get_surface()
        for p in ((5, 5), (1914, 1074), (960, 540)):
            self.assertEqual(win.get_at(p)[:3], (255, 0, 0), p)


if __name__ == "__main__":
    unittest.main()
