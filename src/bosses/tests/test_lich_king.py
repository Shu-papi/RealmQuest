"""Run from the repo root:  python -m unittest discover -s src/bosses/tests"""
import unittest

import math
import os
import sys

SRC_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)

try:
    import pygame
except ImportError:
    from pygame_stub import install
    install()
    import pygame

from bosses import LichKing
from bosses.lich_king.boss import PHASE_STATS
from bosses.lich_king.minions import Skeleton
from bosses.dev.arena import Game, empty_input, BOUNDS

DT = 1 / 60


class StubPlayer:
    def __init__(self, x=480, y=500):
        self.rect = pygame.Rect(0, 0, 28, 28)
        self.rect.center = (x, y)
        self.damage_taken = 0

    def take_damage(self, amount):
        self.damage_taken += amount
        return amount


def advance(boss, player, seconds):
    for _ in range(int(seconds / DT)):
        boss.update(DT, player, BOUNDS)


def ready_boss(seed=1):
    """A boss that has finished its intro and is ready to fight."""
    boss = LichKing(seed=seed)
    advance(boss, StubPlayer(), LichKing.INTRO_TIME + 0.1)
    return boss


class TestLichKing(unittest.TestCase):
    def test_cannot_be_hurt_during_intro(self):
        boss = LichKing()
        self.assertEqual(boss.take_damage(50), 0)
        self.assertEqual(boss.hp, boss.max_hp)

    def test_can_be_hurt_after_intro(self):
        boss = ready_boss()
        self.assertEqual(boss.take_damage(20), 20)
        self.assertEqual(boss.hp, boss.max_hp - 20)

    def test_phase_two_at_half_health(self):
        boss = ready_boss()
        boss.take_damage(boss.max_hp // 2)
        self.assertEqual(boss.phase, 2)
        self.assertEqual(boss.state, "transition")
        self.assertEqual(boss.take_damage(50), 0)      # invulnerable during transition

    def test_volley_has_telegraph_before_bolts(self):
        boss = ready_boss()
        player = StubPlayer()
        boss._begin_attack("volley", player, BOUNDS)
        advance(boss, player, boss.windup_time - 0.1)
        self.assertEqual(len(boss.projectiles), 0)
        advance(boss, player, 0.2)
        self.assertEqual(len(boss.projectiles), PHASE_STATS[1]["bolts"])

    def test_phase_two_volley_fires_its_bolts(self):
        boss = ready_boss()
        boss.take_damage(boss.max_hp // 2)
        advance(boss, StubPlayer(), boss.TRANSITION_TIME + 0.1)
        player = StubPlayer(x=480, y=590)
        boss._begin_attack("volley", player, BOUNDS)
        advance(boss, player, boss.windup_time + 0.02)
        self.assertEqual(len(boss.projectiles), PHASE_STATS[2]["bolts"])

    def test_bolt_hits_player(self):
        boss = ready_boss()
        player = StubPlayer(x=int(boss.x), y=int(boss.y) + 200)
        boss._begin_attack("volley", player, BOUNDS)
        advance(boss, player, 2.0)
        self.assertGreaterEqual(player.damage_taken, 12)

    def test_drain_circle_hurts_and_heals(self):
        boss = ready_boss()
        boss.take_damage(100)
        hp_before = boss.hp
        player = StubPlayer(x=300, y=450)
        boss._begin_attack("drain", player, BOUNDS)
        advance(boss, player, boss.windup_time + 0.1)
        self.assertEqual(player.damage_taken, 18)
        self.assertEqual(boss.hp, hp_before + PHASE_STATS[1]["drain_heal"])

    def test_drain_circle_misses_if_player_moves(self):
        boss = ready_boss()
        boss.take_damage(100)
        hp_before = boss.hp
        player = StubPlayer(x=300, y=450)
        boss._begin_attack("drain", player, BOUNDS)
        advance(boss, player, boss.windup_time / 2)
        player.rect.center = (700, 300)
        advance(boss, player, boss.windup_time)
        self.assertEqual(player.damage_taken, 0)
        self.assertEqual(boss.hp, hp_before)

    def test_summon_never_used_in_phase_one(self):
        boss = ready_boss()
        for _ in range(200):
            self.assertNotEqual(boss._choose_attack(), "summon")

    def test_summon_creates_skeletons_in_phase_two(self):
        boss = ready_boss()
        boss.take_damage(boss.max_hp // 2)
        advance(boss, StubPlayer(), boss.TRANSITION_TIME + 0.1)
        player = StubPlayer()
        boss._begin_attack("summon", player, BOUNDS)
        advance(boss, player, boss.windup_time + 0.05)
        self.assertEqual(len(boss.minions), PHASE_STATS[2]["summon_picks"])

    def test_skeleton_dies_in_one_hit_after_spawning(self):
        skeleton = Skeleton(400, 400)
        self.assertEqual(skeleton.take_damage(20), 0)   # still rising from the ground
        skeleton.update(1.0, StubPlayer(900, 100), BOUNDS)
        self.assertEqual(skeleton.take_damage(20), 20)
        self.assertFalse(skeleton.is_alive())

    def test_skeleton_warns_then_lunges_for_one_hit_per_attack(self):
        # (skeletons used to hurt on touch; now they wind up first, so you can dodge)
        player = StubPlayer(400, 400)
        skeleton = Skeleton(400, 400)
        skeleton.slash_cd = 999                 # (the quick basic slash has its own tests in src/monsters)
        for _ in range(int(0.9 / DT)):          # rising from the ground, then winding up
            skeleton.update(DT, player, BOUNDS)
        self.assertEqual(player.damage_taken, 0)        # it warns before it hits
        for _ in range(int(1.2 / DT)):                  # the lunge lands
            skeleton.update(DT, player, BOUNDS)
        self.assertEqual(player.damage_taken, 8)
        for _ in range(int(0.5 / DT)):
            skeleton.update(DT, player, BOUNDS)
        self.assertEqual(player.damage_taken, 8)        # recovering: no second hit yet

    def test_death_sequence_and_loot(self):
        boss = ready_boss()
        boss.take_damage(9999)
        self.assertFalse(boss.is_alive())
        self.assertEqual(boss.state, "dying")
        self.assertFalse(boss.is_defeated())
        advance(boss, StubPlayer(), boss.DYING_TIME + 0.1)
        self.assertTrue(boss.is_defeated())
        self.assertTrue(len(boss.drop_loot()) > 0)

    def test_hittables_includes_minions(self):
        boss = ready_boss()
        boss.minions.append(Skeleton(100, 100))
        self.assertEqual(len(boss.hittables()), 2)


class TestFullFights(unittest.TestCase):
    def setUp(self):
        pygame.font.init()

    def test_bot_can_beat_boss(self):
        game = Game()
        game.player.god = True
        for frame in range(60 * 150):
            boss = game.boss
            target = boss
            if boss.shielded:                           # phase 3: the Soul Ward means the army must die first
                army = [m for m in boss.minions if m.is_alive()]
                target = min(army, key=lambda m: math.hypot(m.x - game.player.x, m.y - game.player.y))
            inp = empty_input()
            inp["move"] = (target.x - game.player.x, target.y - game.player.y)
            inp["aim"] = (target.x, target.y)
            inp["attack"] = True
            game.update(DT, inp)
            if frame % 7 == 0:
                game.draw(pygame.Surface((960, 640)))
            if game.result:
                break
        self.assertEqual(game.result, "victory")
        self.assertEqual(game.boss.phase, 3)              # he is beaten in his enraged Last Stand

    def test_later_phases_use_every_attack_type(self):
        for phase, hp, expected in (
                (2, 0.5, {"volley", "drain", "rain", "summon", "nova", "grasp", "barrage"}),
                (3, 0.2, {"volley", "drain", "rain", "nova", "grasp", "barrage"})):
            with self.subTest(phase=phase):
                game = Game()
                game.player.god = True
                game.boss = LichKing(seed=3)
                seen, teleported = set(), False
                for frame in range(60 * 4):
                    game.update(DT, empty_input())
                game.boss.debug_set_hp_percent(hp)
                for frame in range(60 * 120):
                    game.update(DT, empty_input())
                    boss = game.boss
                    if boss.state == "windup":
                        seen.add(boss.attack_name)
                    if boss.state == "teleport_out":
                        teleported = True
                    if frame % 5 == 0:
                        game.draw(pygame.Surface((960, 640)))
                self.assertTrue(expected <= seen, f"phase {phase} only used {seen}")
                self.assertTrue(teleported)

    def test_phase_one_only_uses_volley_drain_and_rain(self):
        game = Game()
        game.player.god = True
        game.boss = LichKing(seed=4)
        seen = set()
        for frame in range(60 * 60):
            game.update(DT, empty_input())
            if game.boss.state == "windup":
                seen.add(game.boss.attack_name)
        self.assertEqual(seen, {"volley", "drain", "rain"})

    def test_player_can_lose(self):
        game = Game()
        game.player.hp = 5
        for _ in range(60 * 40):
            game.update(DT, empty_input())
            if game.result:
                break
        self.assertEqual(game.result, "defeat")


if __name__ == "__main__":
    unittest.main()
