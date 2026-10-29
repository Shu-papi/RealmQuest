"""
Checks the HUD bars show the right numbers and drain the way the game plan says.
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

from ui.hud import HUD, StatBar, HEALTH_COLOR, HEART, GHOST_DELAY

DT = 1 / 60


def make_player(hp=5, armor=5, energy=200):
    return types.SimpleNamespace(hp=hp, max_hp=5, armor=armor, max_armor=5,
                                 energy=energy, max_energy=200)


def run(bar, seconds):
    for _ in range(int(seconds / DT) + 1):
        bar.update(DT)


class TestNumbers(unittest.TestCase):
    def test_reads_all_three_values(self):
        hud = HUD()
        hud.update(DT, make_player(hp=3, armor=1, energy=150))
        self.assertEqual(hud.health.label(), "3/5")
        self.assertEqual(hud.armor.label(), "1/5")
        self.assertEqual(hud.energy.label(), "150/200")

    def test_full_bar_is_full(self):
        hud = HUD()
        hud.update(DT, make_player())
        for bar in hud.bars:
            self.assertEqual(bar.fill_fraction(), 1.0)

    def test_values_are_kept_between_0_and_max(self):
        bar = StatBar("health", HEALTH_COLOR, HEART)
        bar.set(-3, 5)
        self.assertEqual(bar.value, 0)
        bar.set(99, 5)
        self.assertEqual(bar.value, 5)

    def test_missing_player_fields_show_zero(self):
        hud = HUD()
        hud.update(DT, types.SimpleNamespace(hp=4, max_hp=6))   # no armor/energy yet
        self.assertEqual(hud.health.label(), "4/6")
        self.assertEqual(hud.armor.label(), "0/0")
        self.assertEqual(hud.energy.fill_fraction(), 0.0)       # no divide-by-zero


class TestDrain(unittest.TestCase):
    def setUp(self):
        self.bar = StatBar("health", HEALTH_COLOR, HEART)
        self.bar.set(5, 5)

    def test_no_ghost_at_start(self):
        self.assertEqual(self.bar.ghost, 5)

    def test_number_drops_at_once_and_ghost_stays_behind(self):
        self.bar.set(2, 5)
        self.assertEqual(self.bar.label(), "2/5")
        self.assertEqual(self.bar.ghost, 5)

    def test_ghost_waits_then_shrinks_to_value(self):
        self.bar.set(2, 5)
        run(self.bar, GHOST_DELAY * 0.5)
        self.assertEqual(self.bar.ghost, 5)             # still waiting
        run(self.bar, 2)
        self.assertEqual(self.bar.ghost, 2)             # fully drained

    def test_healing_hides_ghost(self):
        self.bar.set(1, 5)
        self.bar.set(5, 5)
        self.assertEqual(self.bar.ghost, 5)
        run(self.bar, 2)
        self.assertEqual(self.bar.ghost, 5)


class TestDrawing(unittest.TestCase):
    def test_draw_does_not_crash(self):
        hud = HUD()
        screen = pygame.Surface((640, 360))
        for player in (make_player(), make_player(0, 0, 0), types.SimpleNamespace()):
            hud.update(DT, player)
            hud.draw(screen)

    def test_size_fits_three_rows(self):
        width, height = HUD().size()
        self.assertGreater(width, 100)
        self.assertGreater(height, 3 * 20)


if __name__ == "__main__":
    unittest.main()
