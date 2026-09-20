"""
Checks that EVERY boss follows the rules the game relies on.

Every boss in bosses.BOSSES is tested automatically. The _template boss is
tested too, so you know your starting point works.
Run from the repo root:  python -m unittest discover -s src/bosses/tests
"""
import os
import sys
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

from bosses import BOSSES, get_boss, list_bosses
from bosses._template import TemplateBoss
from bosses.paths import BOSSES_DIR

BOUNDS = (40, 110, 920, 600)
DT = 1 / 60


class StubPlayer:
    def __init__(self, x=480, y=500):
        self.rect = pygame.Rect(0, 0, 28, 28)
        self.rect.center = (x, y)

    def take_damage(self, amount):
        return amount


def every_boss():
    bosses = dict(BOSSES)
    bosses["_template"] = TemplateBoss
    return bosses


class TestBossContract(unittest.TestCase):
    def setUp(self):
        pygame.font.init()

    def test_registry_names_match_folder_names(self):
        for name in BOSSES:
            with self.subTest(boss=name):
                self.assertTrue(os.path.isdir(os.path.join(BOSSES_DIR, name)),
                                f"'{name}' is in BOSSES but src/bosses/{name}/ does not exist")

    def test_get_boss_builds_each_boss(self):
        for name in list_bosses():
            with self.subTest(boss=name):
                self.assertIsInstance(get_boss(name), BOSSES[name])

    def test_unknown_boss_raises_a_clear_error(self):
        with self.assertRaises(ValueError):
            get_boss("not_a_boss")

    def test_each_boss_has_what_the_game_needs(self):
        for name, cls in every_boss().items():
            with self.subTest(boss=name):
                boss = cls()
                for attr in ("name", "max_hp", "hp", "x", "y", "radius", "phase",
                             "state", "clock", "shake", "death_line"):
                    self.assertTrue(hasattr(boss, attr), f"{name} is missing '{attr}'")
                for method in ("update", "draw", "draw_health_bar", "hittables",
                               "take_damage", "is_alive", "is_defeated", "drop_loot",
                               "get_intro"):
                    self.assertTrue(callable(getattr(boss, method, None)),
                                    f"{name} is missing {method}()")

    def test_each_boss_fights_draws_and_can_be_defeated(self):
        surface = pygame.Surface((960, 640))
        font = pygame.font.Font(None, 20)
        for name, cls in every_boss().items():
            with self.subTest(boss=name):
                boss = cls()
                player = StubPlayer()

                # 20 seconds of fight: it attacks, takes some hits, and is drawn
                for frame in range(60 * 20):
                    boss.update(DT, player, BOUNDS)
                    if frame % 6 == 0:
                        boss.draw(surface)
                        boss.draw_health_bar(surface, font)
                    if frame % 30 == 0:
                        for target in boss.hittables():
                            target.take_damage(5)

                # then finish him off
                for frame in range(60 * 20):
                    for target in boss.hittables():
                        target.take_damage(10000)
                    boss.update(DT, player, BOUNDS)
                    if frame % 6 == 0:
                        boss.draw(surface)
                    if boss.is_defeated():
                        break

                self.assertFalse(boss.is_alive(), f"{name} is still alive")
                self.assertTrue(boss.is_defeated(),
                                f"{name} never reached the 'dead' state (is_defeated)")
                self.assertTrue(len(boss.drop_loot()) > 0, f"{name} drops no loot")
                self.assertTrue(boss.death_line, f"{name} has no death_line")


if __name__ == "__main__":
    unittest.main()
