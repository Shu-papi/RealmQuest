"""
Checks the Goblin King boss: sprites load from assets/bosses/goblin_king/, the AI wakes up,
chases, attacks, deals damage on hit frames, and dies.
Run from the repo root:  python -m unittest discover -s src/bosses/goblin_king/tests
"""
import os
import sys
import unittest

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

SRC_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)

import pygame

from bosses.goblin_king import GoblinKing
from bosses.goblin_king import boss_config as cfg
from bosses.goblin_king.goblin_king import ASSET_DIR, BIG_ATTACKS

DT = 1 / 60


class Target:
    """Stand-in player: a point on the floor with HP."""

    def __init__(self, x, y, hp=100000):
        self.x, self.y, self.hp = x, y, hp


def run(boss, target, seconds):
    for _ in range(int(seconds / DT)):
        boss.update(DT, target)


class GoblinKingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pygame.init()
        cls.screen = pygame.display.set_mode((800, 500))

    @classmethod
    def tearDownClass(cls):
        pygame.quit()

    def make(self, x=400, y=200):
        return GoblinKing(x, y)

    # ---------- assets ----------
    def test_sprite_files_exist(self):
        for name in (cfg.SHEET, cfg.HEAVY_SHEET, cfg.SPECIAL_SHEET):
            self.assertTrue((ASSET_DIR / name).is_file(), name)

    def test_frames_load_and_are_not_empty(self):
        boss = self.make()
        rows = len(boss.base)
        cols = len(boss.base[0])
        for anim in cfg.ANIMS.values():
            for col in anim["frames"]:
                self.assertLess(col, cols)
        for row in cfg.DIRECTION_ROWS.values():
            self.assertLess(row, rows)
            for anim in cfg.ANIMS.values():
                for col in anim["frames"]:
                    self.assertGreater(pygame.mask.from_surface(boss.base[row][col]).count(), 0)
        for name, anim in BIG_ATTACKS.items():
            cells = len(boss.big[name]["right"])
            self.assertEqual(cells, cfg.BIG_GRID * cfg.BIG_GRID)
            for col in anim["frames"]:
                self.assertLess(col, cells, f"{name} frame {col}")
                self.assertGreater(pygame.mask.from_surface(boss.big[name]["right"][col]).count(), 0)
            for hit in anim["hits"]:
                self.assertLess(hit, len(anim["frames"]), f"{name} hit frame {hit}")

    # ---------- AI ----------
    def test_stays_idle_until_player_is_close(self):
        boss = self.make()
        far = Target(boss.x + cfg.AGGRO_RANGE * 3, boss.ground[1])
        run(boss, far, 1.0)
        self.assertFalse(boss.aggro)
        self.assertEqual(boss.state, "idle")
        self.assertEqual((boss.x, boss.y), (400, 200))

    def test_wakes_and_walks_toward_player(self):
        boss = self.make()
        tx = boss.x + cfg.AGGRO_RANGE - 20
        target = Target(tx, boss.ground[1])
        start = abs(tx - boss.x)
        run(boss, target, 0.5)
        self.assertTrue(boss.aggro)
        self.assertLess(abs(tx - boss.x), start)

    def test_being_hit_wakes_him(self):
        boss = self.make()
        boss.take_damage(10)
        self.assertTrue(boss.aggro)
        self.assertEqual(boss.hp, cfg.MAX_HP - 10)

    def test_heavy_and_special_hit_a_player_in_range(self):
        for name, anim in BIG_ATTACKS.items():
            with self.subTest(attack=name):
                boss = self.make()
                gx, gy = boss.ground
                target = Target(gx + 30, gy)            # right in front of him
                boss.facing_left = False
                boss.start_attack(name)
                self.assertTrue(boss.busy)
                before = target.hp
                frames = len(anim["frames"])
                run(boss, target, frames / anim["fps"] + 0.5)
                expected = sum(dmg for reach, dmg, arc in anim["hits"].values())
                self.assertEqual(before - target.hp, expected)
                self.assertFalse(boss.busy, "returns from the attack")

    def test_attack_misses_behind_him(self):
        boss = self.make()
        gx, gy = boss.ground
        target = Target(gx - 60, gy)                   # behind: heavy is a 120-degree cone
        boss.facing_left = False
        boss.start_attack("heavy")
        boss.attack_angle = 0.0
        hp = target.hp
        anim = cfg.HEAVY
        for _ in range(int((len(anim["frames"]) / anim["fps"] + 0.5) / DT)):
            target.x, target.y = boss.ground[0] - 60, boss.ground[1]   # stay behind during the dash
            boss.update(DT, target)
        self.assertEqual(target.hp, hp)

    def test_attacks_on_their_own_in_a_fight(self):
        boss = self.make()
        target = Target(boss.x + 100, boss.ground[1])
        seen = set()
        for _ in range(int(30 / DT)):
            boss.update(DT, target)
            seen.add(boss.state)
        self.assertIn("heavy", seen)
        self.assertIn("special", seen)
        self.assertLess(target.hp, 100000)

    def test_dies_and_stops_acting(self):
        boss = self.make()
        boss.take_damage(cfg.MAX_HP + 50)
        self.assertTrue(boss.dead)
        self.assertEqual(boss.hp, 0)
        target = Target(boss.ground[0] + 20, boss.ground[1])
        hp = target.hp
        run(boss, target, 3.0)
        self.assertEqual(target.hp, hp)
        self.assertEqual((boss.x, boss.y), (400, 200))

    def test_draws_every_state_without_errors(self):
        boss = self.make()
        target = Target(boss.ground[0] + 30, boss.ground[1])
        for name in ("idle", "walk", "heavy", "special"):
            for left in (False, True):
                boss.set_state(name)
                boss.facing_left = left
                boss.hurt_timer = 0.1
                self.screen.fill((0, 0, 0))
                boss.draw(self.screen)
                boss.update(DT, target)
        boss.take_damage(cfg.MAX_HP)
        boss.draw(self.screen)


if __name__ == "__main__":
    unittest.main()
