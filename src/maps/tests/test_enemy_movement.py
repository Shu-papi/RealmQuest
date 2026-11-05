"""
Monsters don't get stuck on obstacles: they slide along walls, turn past corners and, when that is
not enough, follow a path round (combat.move_enemy). Also the Goblin King's longer reach and aimed
cones, and the sword's cone (combat.sword_hits).
Run from the repo root:  python -m unittest discover -s src/maps/tests
"""
import math
import os
import sys
import types
import unittest

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
if REPO not in sys.path:
    sys.path.insert(0, REPO)

import pygame

pygame.init()
pygame.display.set_mode((1152, 648))

from src.maps import combat, dungeon_map   # noqa: E402

TILE, MAP_W, MAP_H = combat.TILE, combat.MAP_W, combat.MAP_H
DT = 1 / 60


class Room:
    """A walled room of floor tiles with solid blocks inside (uses the real Dungeon.can_stand)."""

    def __init__(self, x0=10, y0=10, x1=50, y1=34, blocks=()):
        self.tiles = bytearray(MAP_W * MAP_H)
        self.solid = bytearray(MAP_W * MAP_H)
        self.lock_rect = None
        for ty in range(y0, y1):
            for tx in range(x0, x1):
                self.tiles[ty * MAP_W + tx] = combat.FLOOR
        for tx, ty in blocks:
            self.solid[ty * MAP_W + tx] = 1

    def can_stand(self, x, y):
        return dungeon_map.Dungeon.can_stand(self, x, y)


def px(tx, ty):
    return tx * TILE + TILE / 2, ty * TILE + TILE / 2


def wall(x, y0, y1):
    return [(x, y) for y in range(y0, y1 + 1)]


class FakePC:
    dead = False

    def hurt(self, *a, **k):
        return False


def chase(e, d, hero, seconds=12.0, near=None):
    """Let the monster chase until it is next to the hero (within `near` px); returns the seconds
    it took (or None)."""
    pc = FakePC()
    near = e.radius + combat.CONTACT_REACH + 4 if near is None else near
    t = 0.0
    while t < seconds:
        e.update(DT, hero, d, pc)
        t += DT
        if math.hypot(hero.x - e.x, hero.y - e.y) <= near:
            return t
    return None


class Unstuck(unittest.TestCase):
    def setUp(self):
        self.hero = types.SimpleNamespace(x=0.0, y=0.0, face=(1.0, 0.0))

    def place_hero(self, tx, ty):
        self.hero.x, self.hero.y = px(tx, ty)

    def make(self, cls, tx, ty, *extra, **kw):
        x, y = px(tx, ty)
        e = cls(x, y, "Test", 10, 90, 1, (200, 200, 200), 14, *extra, **kw)
        return e

    def test_walks_round_a_pillar(self):
        d = Room(blocks=wall(30, 16, 26))           # a long pillar between them
        self.place_hero(36, 21)
        e = self.make(combat.Enemy, 24, 21)
        self.assertIsNotNone(chase(e, d, self.hero), "got round the pillar")

    def test_gets_out_of_a_pocket(self):
        # a U open to the left: the hero is to the right, so the straight way is a dead end
        blocks = wall(28, 16, 26) + [(x, 16) for x in range(22, 29)] + [(x, 26) for x in range(22, 29)]
        d = Room(blocks=blocks)
        self.place_hero(40, 21)
        e = self.make(combat.Enemy, 26, 21)
        self.assertIsNotNone(chase(e, d, self.hero, 20.0), "found the way out of the pocket")

    def test_slides_along_a_wall_at_an_angle(self):
        d = Room(blocks=[(x, 20) for x in range(14, 46)])      # a long low wall, hero on the other side
        self.place_hero(40, 24)
        e = self.make(combat.Enemy, 20, 17)
        self.assertIsNotNone(chase(e, d, self.hero, 20.0))

    def test_orcs_and_shamans_too(self):
        d = Room(blocks=wall(30, 16, 26))
        self.place_hero(36, 21)
        orc = self.make(combat.OrcEnemy, 24, 21)
        self.assertIsNotNone(chase(orc, d, self.hero, near=orc.radius + orc.reach + 10), "orc: in axe range")

    def test_backing_off_also_slides(self):
        d = Room(blocks=wall(20, 14, 28))
        x0, y0 = px(21, 21)
        e = types.SimpleNamespace(x=x0, y=y0, speed=90, speed_k=1.0)
        hx, hy = px(24, 20)                          # hero to the right and a bit up: it backs left into the wall
        for _ in range(60):
            combat.move_enemy(e, hx, hy, DT, d, away=True)
        self.assertGreater(abs(e.y - y0), 10, "slid along the wall instead of freezing")

    def test_the_path_field_goes_round(self):
        d = Room(blocks=wall(30, 11, 33))            # a wall right across, a gap at the very top / bottom
        d.solid[33 * MAP_W + 30] = 0
        field = combat.flow_field(d, 36, 21)
        self.assertIn(21 * MAP_W + 24, field, "the far side can be reached")
        self.assertNotIn(21 * MAP_W + 30, field, "not through the wall")


class SwordCone(unittest.TestCase):
    def test_hits_in_front_not_behind(self):
        self.assertTrue(combat.sword_hits(0, 0, 1, 0, 60, 0, 14))
        self.assertTrue(combat.sword_hits(0, 0, 1, 0, 50, 40, 14), "a little to the side")
        self.assertFalse(combat.sword_hits(0, 0, 1, 0, -60, 0, 14), "behind")
        self.assertFalse(combat.sword_hits(0, 0, 1, 0, 2, 80, 14), "straight to the side")
        self.assertTrue(combat.sword_hits(0, 0, 1, 0, -10, 4, 14), "touching the hero")
        self.assertFalse(combat.sword_hits(0, 0, 1, 0, combat.SWORD_REACH + 40, 0, 14), "out of reach")


class GoblinKingReach(unittest.TestCase):
    def test_reach_is_longer_than_before(self):
        from bosses.goblin_king import boss_config as cfg
        self.assertGreaterEqual(cfg.HEAVY["hits"][12][0], 170)
        self.assertGreaterEqual(cfg.SPECIAL["hits"][5][0], 250)
        self.assertGreaterEqual(cfg.SPECIAL["hits"][12][0], 230)

    def test_his_cone_aims_at_a_hero_above_him(self):
        from bosses.goblin_king.goblin_king import GoblinKing
        boss = GoblinKing(400, 400, {"dist_k": 0.6, "squash": 1.0})
        gx, gy = boss.ground
        hurt = []
        target = types.SimpleNamespace(x=gx, y=gy - 60, hurt=lambda dmg: hurt.append(dmg))
        boss.wake()
        boss.heavy_cooldown = 0.0
        boss.special_cooldown = 99.0
        for _ in range(int(3.0 / DT)):
            target.x, target.y = boss.ground[0], boss.ground[1] - 60      # stays right above him
            boss.update(DT, target)
        self.assertTrue(hurt, "the slam reaches a hero standing above him")


if __name__ == "__main__":
    unittest.main()
