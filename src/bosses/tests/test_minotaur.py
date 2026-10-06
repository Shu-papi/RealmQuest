"""Minotaur-specific checks. Run from the repo root:  python -m unittest discover -s src/bosses/tests"""
import math
import os
import sys
import tempfile
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

from bosses import Minotaur, get_boss
from bosses.minotaur import art as minotaur_art
from bosses.minotaur.art import MinotaurArt, check_assets
from bosses.minotaur.boss import PHASE_STATS, STUN_DAMAGE_MULT, _distance_to_wall

DT = 1 / 60
BOUNDS = (40, 110, 920, 600)

REAL_PYGAME = hasattr(pygame, "get_sdl_version")
needs_pygame = unittest.skipUnless(REAL_PYGAME, "needs real pygame (pip install pygame-ce)")


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
    """A Minotaur that has finished its intro."""
    boss = Minotaur(seed=seed)
    advance(boss, StubPlayer(), Minotaur.INTRO_TIME + 0.1)
    return boss


def phase_two_boss():
    boss = ready_boss()
    boss.take_damage(150)
    advance(boss, StubPlayer(), boss.TRANSITION_TIME + 0.1)
    return boss


class TestMinotaurFight(unittest.TestCase):
    def test_is_registered(self):
        self.assertIsInstance(get_boss("minotaur"), Minotaur)

    def test_cannot_be_hurt_during_intro(self):
        boss = Minotaur()
        self.assertEqual(boss.take_damage(50), 0)
        self.assertEqual(boss.hp, boss.max_hp)

    def test_can_be_hurt_after_intro(self):
        boss = ready_boss()
        self.assertEqual(boss.take_damage(20), 20)
        self.assertEqual(boss.hp, boss.max_hp - 20)

    def test_phase_two_at_half_health(self):
        boss = ready_boss()
        boss.take_damage(150)
        self.assertEqual(boss.phase, 2)
        self.assertEqual(boss.state, "transition")
        self.assertEqual(boss.take_damage(50), 0)          # invulnerable during transition
        advance(boss, StubPlayer(), boss.TRANSITION_TIME + 0.1)
        self.assertEqual(boss.state, "idle")

    def test_debug_jump_to_phase_two(self):
        boss = ready_boss()
        boss.debug_set_hp_percent(0.5)
        self.assertEqual(boss.phase, 2)

    # ---------- charge ----------

    def test_charge_has_telegraph_before_moving(self):
        boss = ready_boss()
        player = StubPlayer(x=480, y=560)
        boss._start_attack("charge")
        start = (boss.x, boss.y)
        advance(boss, player, PHASE_STATS[1]["charge_windup"] - 0.1)
        self.assertEqual(boss.state, "charge_windup")
        self.assertEqual((boss.x, boss.y), start)           # stands still while warning
        self.assertEqual(player.damage_taken, 0)
        advance(boss, player, 0.2)
        self.assertEqual(boss.state, "charge")

    def test_charge_hits_player_in_the_lane_once(self):
        boss = ready_boss()
        player = StubPlayer(x=int(boss.x), y=int(boss.y) + 250)
        boss._start_attack("charge")
        advance(boss, player, 3.0)
        self.assertEqual(player.damage_taken, PHASE_STATS[1]["charge_damage"])

    def test_charge_misses_if_player_leaves_the_lane(self):
        boss = ready_boss()
        player = StubPlayer(x=int(boss.x), y=int(boss.y) + 250)
        boss._start_attack("charge")
        advance(boss, player, PHASE_STATS[1]["charge_windup"] + 0.05)   # locked on now
        player.rect.center = (850, 300)
        advance(boss, player, 3.0)
        self.assertEqual(player.damage_taken, 0)

    def test_charge_stays_inside_the_arena_and_ends_stunned(self):
        boss = ready_boss()
        player = StubPlayer(x=int(boss.x), y=int(boss.y) + 250)
        boss._start_attack("charge")
        for _ in range(int(3.0 / DT)):
            boss.update(DT, player, BOUNDS)
            self.assertGreaterEqual(boss.x, BOUNDS[0] + boss.radius - 1)
            self.assertLessEqual(boss.x, BOUNDS[2] - boss.radius + 1)
            self.assertGreaterEqual(boss.y, BOUNDS[1] + boss.radius - 1)
            self.assertLessEqual(boss.y, BOUNDS[3] - boss.radius + 1)
            if boss.state == "stunned":
                break
        self.assertEqual(boss.state, "stunned")

    def test_stunned_boss_takes_extra_damage_then_recovers(self):
        boss = ready_boss()
        boss.set_state("stunned")
        self.assertEqual(boss.take_damage(20), int(20 * STUN_DAMAGE_MULT))
        advance(boss, StubPlayer(), PHASE_STATS[1]["stun"] + 0.1)
        self.assertEqual(boss.state, "idle")

    def test_phase_two_charges_twice_before_stunning(self):
        boss = phase_two_boss()
        player = StubPlayer(x=int(boss.x), y=int(boss.y) + 250)
        boss._start_attack("charge")
        charges = 0
        seen_charge = False
        for _ in range(int(6.0 / DT)):
            boss.update(DT, player, BOUNDS)
            if boss.state == "charge" and not seen_charge:
                seen_charge = True
                charges += 1
            elif boss.state != "charge":
                seen_charge = False
            if boss.state == "stunned":
                break
        self.assertEqual(charges, 2)
        self.assertEqual(boss.state, "stunned")

    # ---------- slam ----------

    def test_slam_has_telegraph_then_hurts_player_inside_circle(self):
        boss = ready_boss()
        player = StubPlayer(x=int(boss.x), y=int(boss.y) + 40)
        boss._start_attack("slam")
        self.assertEqual(len(boss.hazards), 1)
        advance(boss, player, PHASE_STATS[1]["slam_windup"] - 0.1)
        self.assertEqual(player.damage_taken, 0)
        advance(boss, player, 0.3)
        self.assertEqual(player.damage_taken, PHASE_STATS[1]["slam_damage"])

    def test_slam_misses_if_player_leaves_the_circle(self):
        boss = ready_boss()
        player = StubPlayer(x=int(boss.x), y=int(boss.y) + 40)
        boss._start_attack("slam")
        advance(boss, player, PHASE_STATS[1]["slam_windup"] / 2)
        player.rect.center = (int(boss.x) + 400, int(boss.y) + 40)
        advance(boss, player, PHASE_STATS[1]["slam_windup"])
        self.assertEqual(player.damage_taken, 0)

    def test_phase_one_slam_throws_no_rocks_phase_two_does(self):
        boss = ready_boss()
        far = StubPlayer(x=900, y=590)
        boss._start_attack("slam")
        advance(boss, far, PHASE_STATS[1]["slam_windup"] + 0.05)
        self.assertEqual(len(boss.projectiles), 0)

        boss = phase_two_boss()
        boss._start_attack("slam")
        advance(boss, far, PHASE_STATS[2]["slam_windup"] + 0.05)
        self.assertEqual(len(boss.projectiles), PHASE_STATS[2]["rocks"])

    def test_never_uses_the_same_attack_three_times_in_a_row(self):
        boss = ready_boss(seed=7)
        history = []
        for _ in range(200):
            name = boss._pick_attack(300)
            boss._start_attack(name)
            history.append(name)
        for i in range(2, len(history)):
            self.assertFalse(history[i] == history[i - 1] == history[i - 2],
                             f"same attack 3 times in a row at {i}")

    def test_keeps_fighting_by_itself(self):
        """Left alone for 20 seconds the boss must start attacking on its own."""
        boss = ready_boss()
        player = StubPlayer()
        used = set()
        for _ in range(int(20 / DT)):
            boss.update(DT, player, BOUNDS)
            used.add(boss.state)
        self.assertTrue({"charge_windup", "slam_windup"} & used)

    def test_ray_to_wall_helper(self):
        # straight down from (480, 230): wall at 600, minus a 46 margin
        self.assertAlmostEqual(_distance_to_wall(480, 230, math.pi / 2, BOUNDS, 46), 324, places=3)
        # already against the wall: nothing left
        self.assertEqual(_distance_to_wall(480, 554, math.pi / 2, BOUNDS, 46), 0.0)

    # ---------- death ----------

    def test_death_sequence_and_loot(self):
        boss = ready_boss()
        boss.take_damage(9999)
        self.assertFalse(boss.is_alive())
        self.assertEqual(boss.state, "dying")
        self.assertFalse(boss.is_defeated())
        advance(boss, StubPlayer(), boss.DYING_TIME + 0.1)
        self.assertTrue(boss.is_defeated())
        self.assertTrue(boss.drop_loot())

    def test_death_clears_attacks(self):
        boss = ready_boss()
        boss._start_attack("slam")
        boss.take_damage(9999)
        self.assertEqual(boss.hazards, [])
        self.assertEqual(boss.projectiles, [])


class TestMinotaurArt(unittest.TestCase):
    @needs_pygame
    def test_shipped_sprites_pass_the_checker(self):
        pygame.init()
        errors, warnings = check_assets()
        self.assertEqual(errors, [], errors)
        self.assertEqual(warnings, [], warnings)

    @needs_pygame
    def test_checker_reports_a_missing_folder_and_missing_required_file(self):
        errors, _ = check_assets("/no/such/folder")
        self.assertTrue(errors)
        with tempfile.TemporaryDirectory() as empty:
            errors, _ = check_assets(empty)
            self.assertTrue(any("body_phase1_a.png" in e for e in errors))

    @needs_pygame
    def test_checker_catches_mismatched_sizes(self):
        with tempfile.TemporaryDirectory() as folder:
            for name, size in (("body_phase1_a.png", (48, 56)), ("body_phase1_b.png", (40, 56))):
                surface = pygame.Surface(size, pygame.SRCALPHA)
                pygame.image.save(surface, os.path.join(folder, name))
            errors, _ = check_assets(folder)
            self.assertTrue(any("same size" in e for e in errors), errors)

    @needs_pygame
    def test_art_draws_something_with_the_real_sprites(self):
        pygame.init()
        surface = pygame.Surface((400, 400))
        surface.fill((0, 0, 0))
        art = MinotaurArt()
        for phase in (1, 2):
            self.assertTrue(art.draw(surface, 200, 200, clock=0.0, phase=phase))
            self.assertTrue(art.draw(surface, 200, 200, clock=0.5, phase=phase, tint="flash"))
            self.assertTrue(art.draw(surface, 200, 200, phase=phase, tint="warn", lift=3, alpha=90))
        self.assertNotEqual(surface.get_at((200, 200))[:3], (0, 0, 0))

    def test_missing_sprites_fall_back_to_shapes_without_crashing(self):
        art = MinotaurArt(folder="/no/such/folder")
        surface = pygame.Surface((400, 400))
        self.assertFalse(art.draw(surface, 200, 200))        # tells the boss to draw shapes
        boss = Minotaur()
        boss.art = art
        boss.draw(surface)                                   # must not raise
        for state in ("idle", "charge_windup", "slam_windup", "stunned", "transition", "dying"):
            boss.set_state(state)
            boss.draw(surface)

    def test_boss_draws_in_every_state(self):
        surface = pygame.Surface((960, 640))
        boss = ready_boss()
        for state in ("intro", "idle", "charge_windup", "charge", "slam_windup", "recover",
                      "stunned", "transition", "dying", "dead"):
            boss.set_state(state)
            boss.draw(surface)


if __name__ == "__main__":
    unittest.main()
