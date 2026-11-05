"""
Tests for the Lich King's later skills: Bone Nova, Grasping Hands, the phase 3 "Last Stand",
attack pairs (combos) and the enraged look.

Run from the repo root:  python -m unittest discover -s src/bosses/tests
"""
import math
import os
import sys
import unittest
from unittest import mock

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
from bosses.attacks import apply_status
from bosses.dev.arena import BOUNDS, Game, empty_input
from bosses.lich_king import boss as boss_module
from bosses.lich_king.bone_shard import BoneShard
from bosses.lich_king.boss import (REARM_AFTER, SHIELD_BREAK_WINDOW, WAVE_RAISE_BUDGET, BARRAGE_DAMAGE, BOSS_MAX_HP, COMBO_PAUSE, EXHAUST_BONUS, PHASE_3_AT,
                                   RAIN_DAMAGE, GRASP_DAMAGE, GRASP_RADIUS, GRASP_STAGGER, NOVA_DAMAGE,
                                   NOVA_GAP_SHARDS, NOVA_SECOND_RING, PHASE_STATS)
from bosses.lich_king.drain_circle import DrainCircle, SoulRain
from bosses.lich_king.grasping_hand import GraspingHand

DT = 1 / 60
REAL_PYGAME = hasattr(pygame, "mask")                    # the fake pygame cannot read pixels back
needs_pygame = unittest.skipUnless(REAL_PYGAME, "needs real pygame to look at the pixels")


class StubPlayer:
    """The minimum a boss needs: a rect and take_damage."""

    def __init__(self, x=480, y=500):
        self.rect = pygame.Rect(0, 0, 28, 28)
        self.rect.center = (x, y)
        self.damage_taken = 0

    def take_damage(self, amount):
        self.damage_taken += amount
        return amount


class StatusPlayer(StubPlayer):
    """A player that also supports status effects (like the real one should)."""

    def __init__(self, x=480, y=500):
        super().__init__(x, y)
        self.statuses = []

    def apply_status(self, name, seconds):
        self.statuses.append((name, seconds))
        return True


class GodPlayer(StatusPlayer):
    """Invulnerable: damage does nothing, statuses are refused."""

    def take_damage(self, amount):
        return 0

    def apply_status(self, name, seconds):
        return False


def advance(boss, player, seconds):
    for _ in range(int(seconds / DT)):
        boss.update(DT, player, BOUNDS)


def boss_in_phase(phase, seed=1, player=None):
    boss = LichKing(seed=seed)
    player = player or StubPlayer()
    advance(boss, player, LichKing.INTRO_TIME + 0.1)
    if phase >= 2:
        boss.debug_set_hp_percent(0.5)
        advance(boss, player, boss.TRANSITION_TIME + 0.1)
    if phase >= 3:
        boss.debug_set_hp_percent(0.2)
        advance(boss, player, boss.TRANSITION_TIME + 0.1)
    boss.state = "idle"
    boss.cooldown = 99
    return boss


def lit_pixels(surface, step=3):
    w, h = surface.get_size()
    return sum(1 for x in range(0, w, step) for y in range(0, h, step) if surface.get_at((x, y))[:3] != (0, 0, 0))


class TestApplyStatus(unittest.TestCase):
    def test_ignored_when_the_player_has_no_statuses(self):
        self.assertFalse(apply_status(StubPlayer(), "root", 1.0))

    def test_passed_on_when_the_player_supports_it(self):
        player = StatusPlayer()
        self.assertTrue(apply_status(player, "root", 1.5))
        self.assertEqual(player.statuses, [("root", 1.5)])

    def test_an_immune_player_refuses_it(self):
        self.assertFalse(apply_status(GodPlayer(), "root", 1.0))


class TestBoneShard(unittest.TestCase):
    def test_starts_slowly_then_speeds_up(self):
        shard = BoneShard(100, 300, 0.0, 300, 10)
        player = StubPlayer(900, 580)
        positions = [shard.x]
        for _ in range(40):
            shard.update(DT, player, BOUNDS)
            positions.append(shard.x)
        early = positions[6] - positions[0]
        late = positions[40] - positions[34]
        self.assertGreater(late, early * 1.5)

    def test_hits_the_player_once_and_disappears(self):
        shard = BoneShard(400, 300, 0.0, 300, 10)
        player = StubPlayer(430, 300)
        for _ in range(30):
            shard.update(DT, player, BOUNDS)
        self.assertEqual(player.damage_taken, 10)
        self.assertFalse(shard.alive)

    def test_leaves_the_arena(self):
        shard = BoneShard(900, 300, 0.0, 400, 10)
        for _ in range(60):
            shard.update(DT, StubPlayer(100, 580), BOUNDS)
        self.assertFalse(shard.alive)

    @needs_pygame
    def test_draws(self):
        surface = pygame.Surface((300, 300))
        surface.fill((0, 0, 0))
        BoneShard(150, 150, 0.7, 300, 10).draw(surface)
        self.assertGreater(lit_pixels(surface, 1), 30)


class TestGraspingHand(unittest.TestCase):
    def test_warns_first_then_hurts_and_roots(self):
        hand = GraspingHand(400, 300, 42, 1.0, 12, 1.2)
        player = StatusPlayer(400, 300)
        for _ in range(int(0.9 / DT)):
            hand.update(DT, player)
        self.assertEqual(player.damage_taken, 0)
        self.assertEqual(player.statuses, [])
        hits = [hand.update(DT, player) for _ in range(int(0.3 / DT))]
        self.assertEqual(hits.count(True), 1)                      # exactly one hit
        self.assertEqual(player.damage_taken, 12)
        self.assertEqual(player.statuses, [("root", 1.2)])

    def test_misses_a_player_who_moved_away(self):
        hand = GraspingHand(400, 300, 42, 0.5, 12, 1.2)
        player = StatusPlayer(600, 300)
        for _ in range(int(2.0 / DT)):
            hand.update(DT, player)
        self.assertEqual(player.damage_taken, 0)
        self.assertEqual(player.statuses, [])
        self.assertFalse(hand.alive)

    def test_an_invulnerable_player_is_not_rooted(self):
        hand = GraspingHand(400, 300, 42, 0.2, 12, 1.2)
        player = GodPlayer(400, 300)
        hits = [hand.update(DT, player) for _ in range(60)]
        self.assertFalse(any(hits))
        self.assertEqual(player.statuses, [])

    def test_works_with_a_player_that_has_no_statuses(self):
        hand = GraspingHand(400, 300, 42, 0.2, 12, 1.2)
        player = StubPlayer(400, 300)
        for _ in range(120):
            hand.update(DT, player)
        self.assertEqual(player.damage_taken, 12)

    @needs_pygame
    def test_draws_in_every_state(self):
        surface = pygame.Surface((300, 300))
        for duration_step in (0.0, 0.5, 0.95, 1.05, 1.2, 1.6, 1.8):
            hand = GraspingHand(150, 200, 42, 1.0, 12, 1.0)
            surface.fill((0, 0, 0))
            for _ in range(int(duration_step / DT)):
                hand.update(DT, StubPlayer(10, 10))
            hand.draw(surface)
            self.assertGreater(lit_pixels(surface, 1), 20, duration_step)


class TestAttackChoice(unittest.TestCase):
    def test_phase_one_never_uses_the_new_skills(self):
        boss = boss_in_phase(1)
        picked = {boss._choose_attack() for _ in range(300)}
        self.assertEqual(picked, {"volley", "drain", "rain"})

    def test_phase_two_uses_everything(self):
        boss = boss_in_phase(2)
        self.assertEqual({boss._choose_attack() for _ in range(500)},
                         {"volley", "drain", "rain", "nova", "grasp", "barrage", "summon"})

    def test_he_stops_summoning_once_his_army_is_full(self):
        for phase in (2, 3):
            boss = boss_in_phase(phase)
            cap = PHASE_STATS[phase]["minion_cap"]
            boss.minions = [boss_module.spawn_monster("skeleton_warrior", 100, 200, spawn=False) for _ in range(cap)]
            self.assertNotIn("summon", {boss._choose_attack() for _ in range(300)}, phase)

    def test_phase_three_army_is_smaller_than_phase_two(self):
        self.assertLess(PHASE_STATS[3]["minion_cap"], PHASE_STATS[2]["minion_cap"])


class TestBoneNova(unittest.TestCase):
    def _start(self, phase, player=None, seed=1):
        player = player or StubPlayer(480, 560)
        boss = boss_in_phase(phase, seed, player)
        boss._begin_attack("nova", player, BOUNDS)
        return boss, player

    def test_has_a_wind_up_before_any_shard(self):
        boss, player = self._start(2)
        advance(boss, player, boss.windup_time - 0.15)
        self.assertEqual(len(boss.projectiles), 0)
        advance(boss, player, 0.25)
        self.assertGreater(len(boss.projectiles), 10)

    def test_the_ring_has_a_safe_gap(self):
        boss, player = self._start(2)
        advance(boss, player, boss.windup_time + 0.05)
        shards = [p for p in boss.projectiles if isinstance(p, BoneShard)]
        count = boss.stats["nova_shards"]
        self.assertIn(len(shards), {count - NOVA_GAP_SHARDS, count - NOVA_GAP_SHARDS + 1})
        gap_half = math.tau / count * NOVA_GAP_SHARDS / 2
        for shard in shards:                                       # no shard flies into the marked gap
            diff = abs((shard.angle - boss.nova_gap + math.pi) % math.tau - math.pi)
            self.assertGreaterEqual(diff, gap_half - 1e-6)

    def test_standing_in_the_gap_is_safe_and_standing_elsewhere_is_not(self):
        for in_gap in (True, False):
            probe = LichKing(seed=1)
            player = StubPlayer(480, 560)
            advance(probe, player, LichKing.INTRO_TIME + 0.1)
            probe._begin_attack("nova", player, BOUNDS)
            angle = probe.nova_gap + (0 if in_gap else math.pi)
            player.rect.center = (probe.x + math.cos(angle) * 140, probe.y + math.sin(angle) * 140)
            probe.state_time = probe.windup_time - 0.001
            advance(probe, player, 1.2)
            if in_gap:
                self.assertEqual(player.damage_taken, 0)
            else:
                self.assertGreaterEqual(player.damage_taken, NOVA_DAMAGE)

    def test_phase_three_fires_a_second_ring_with_the_gap_on_the_opposite_side(self):
        boss, player = self._start(3)
        advance(boss, player, boss.windup_time + 0.05)
        first = len(boss.projectiles)
        self.assertTrue(boss.scheduled)
        self.assertAlmostEqual(abs(boss._nova_gap_centre(1) - boss._nova_gap_centre(0)), math.pi)
        advance(boss, player, NOVA_SECOND_RING + 0.1)
        self.assertFalse(boss.scheduled)
        self.assertGreater(len(boss.projectiles), first + 10)

    def test_phase_two_fires_only_one_ring(self):
        boss, player = self._start(2)
        advance(boss, player, boss.windup_time + 0.05)
        self.assertFalse(boss.scheduled)

    def test_boss_stands_still_while_the_second_ring_is_coming(self):
        boss, player = self._start(3, StubPlayer(100, 560))
        advance(boss, player, boss.windup_time + 0.05)
        boss.state = "idle"
        boss.cooldown = 99
        x = boss.x
        advance(boss, player, 0.3)
        self.assertEqual(boss.x, x)
        advance(boss, player, 1.0)                                  # ring is done: he moves again
        self.assertNotEqual(boss.x, x)

    @needs_pygame
    def test_the_telegraph_marks_the_gap(self):
        boss, player = self._start(3)
        advance(boss, player, 0.5)
        surface = pygame.Surface((960, 640))
        surface.fill((0, 0, 0))
        boss._draw_nova_telegraph(surface)
        self.assertGreater(lit_pixels(surface), 50)
        green = sum(1 for x in range(0, 960, 2) for y in range(0, 640, 2)
                    if surface.get_at((x, y))[:3] in ((151, 196, 89), (96, 130, 62)))
        self.assertGreater(green, 20)

    @needs_pygame
    def test_the_nova_marker_is_drawn_during_the_wind_up_only(self):
        boss, player = self._start(2)
        advance(boss, player, 0.4)
        during = pygame.Surface((960, 640))
        during.fill((0, 0, 0))
        boss.draw_effects(during)
        self.assertGreater(lit_pixels(during), 20)
        boss.state = "idle"
        boss.heal_flash, boss.drain_lines = 0.0, []
        after = pygame.Surface((960, 640))
        after.fill((0, 0, 0))
        boss.draw_effects(after)
        self.assertEqual(lit_pixels(after), 0)


class TestGraspingHandsAttack(unittest.TestCase):
    def _start(self, phase, player=None, seed=1):
        player = player or StatusPlayer(480, 520)
        boss = boss_in_phase(phase, seed, player)
        boss._begin_attack("grasp", player, BOUNDS)
        return boss, player

    def test_number_of_hands_grows_each_phase(self):
        counts = {}
        for phase in (2, 3):
            boss, _ = self._start(phase)
            counts[phase] = len([h for h in boss.hazards if isinstance(h, GraspingHand)])
            self.assertEqual(counts[phase], PHASE_STATS[phase]["grasp_hands"])
        self.assertGreater(counts[3], counts[2])

    def test_one_crack_is_under_the_player_and_the_rest_are_spread_out(self):
        boss, player = self._start(2)
        hands = [h for h in boss.hazards if isinstance(h, GraspingHand)]
        self.assertEqual((hands[0].x, hands[0].y), (480, 520))
        for i, a in enumerate(hands):
            self.assertTrue(BOUNDS[0] < a.x < BOUNDS[2] and BOUNDS[1] < a.y < BOUNDS[3])
            for b in hands[i + 1:]:
                self.assertGreater(math.hypot(a.x - b.x, a.y - b.y), GRASP_RADIUS)

    def test_hands_burst_one_after_another(self):
        boss, _ = self._start(2)
        durations = [h.duration for h in boss.hazards if isinstance(h, GraspingHand)]
        gaps = [round(b - a, 3) for a, b in zip(durations, durations[1:])]
        self.assertEqual(gaps, [GRASP_STAGGER] * len(gaps))
        self.assertAlmostEqual(durations[0], boss.windup_time)

    def test_standing_still_gets_you_hurt_and_rooted_but_not_before_the_warning_ends(self):
        boss, player = self._start(2)
        advance(boss, player, boss.windup_time - 0.1)
        self.assertEqual(player.damage_taken, 0)
        advance(boss, player, 0.3)
        self.assertEqual(player.damage_taken, GRASP_DAMAGE)
        self.assertEqual(player.statuses, [("root", PHASE_STATS[2]["grasp_root"])])

    def test_phase_three_roots_for_longer(self):
        self.assertGreater(PHASE_STATS[3]["grasp_root"], PHASE_STATS[2]["grasp_root"])

    def test_a_hand_does_not_heal_the_boss_but_a_drain_circle_does(self):
        boss, player = self._start(2)
        boss.hp = 100
        advance(boss, player, boss.windup_time + 0.3)
        self.assertEqual(boss.hp, 100)
        boss.hazards = []
        boss.on_hazard_hit(DrainCircle(0, 0, 85, 1.0, 18))
        self.assertEqual(boss.hp, 100 + PHASE_STATS[2]["drain_heal"])

    def test_the_hands_are_cleared_when_he_changes_phase(self):
        boss, player = self._start(2)
        boss.debug_set_hp_percent(0.2)
        self.assertEqual(boss.state, "transition")
        self.assertEqual(boss.hazards, [])


class TestPhaseThree(unittest.TestCase):
    def test_begins_at_the_phase_three_threshold(self):
        boss = boss_in_phase(2)
        boss.hp = int(boss.max_hp * PHASE_3_AT) + 2
        boss.take_damage(1)
        self.assertEqual(boss.phase, 2)
        boss.state = "idle"
        boss.hp = int(boss.max_hp * PHASE_3_AT) + 1
        boss.take_damage(1)
        self.assertEqual(boss.phase, 3)
        self.assertEqual(boss.state, "transition")

    def test_a_huge_hit_skips_straight_to_phase_three(self):
        boss = boss_in_phase(1)
        boss.take_damage(boss.max_hp * 0.85)
        self.assertEqual(boss.phase, 3)

    def test_cannot_be_hurt_during_the_enrage_transition(self):
        boss = boss_in_phase(2)
        boss.debug_set_hp_percent(0.2)
        self.assertEqual(boss.take_damage(10), 0)

    def test_rage_builds_during_the_transition_and_stays(self):
        boss = boss_in_phase(2)
        self.assertEqual(boss.rage, 0.0)
        boss.debug_set_hp_percent(0.2)
        player = StubPlayer()
        advance(boss, player, boss.TRANSITION_TIME * 0.5)
        self.assertTrue(0.3 < boss.rage < 0.7)
        advance(boss, player, boss.TRANSITION_TIME)
        self.assertEqual(boss.rage, 1.0)

    def test_phase_three_is_faster_than_phase_two(self):
        s2, s3 = PHASE_STATS[2], PHASE_STATS[3]
        self.assertGreater(s3["speed"], s2["speed"])
        self.assertLess(s3["recover"], s2["recover"])
        self.assertLess(s3["volley_windup"], s2["volley_windup"])
        self.assertGreater(s3["bolts"], s2["bolts"])
        self.assertGreater(s3["drain_circles"], s2["drain_circles"])
        self.assertGreater(s3["nova_rings"], s2["nova_rings"])

    def test_the_wind_ups_stay_long_enough_to_react_to(self):
        for phase in (1, 2, 3):
            for key in ("volley_windup", "drain_windup", "nova_windup", "grasp_windup", "summon_windup",
                        "rain_windup", "barrage_windup"):
                self.assertGreaterEqual(PHASE_STATS[phase][key], 0.45, (phase, key))

    def test_drain_heals_him_less_in_phase_three(self):
        results = {}
        for phase in (2, 3):
            boss = boss_in_phase(phase)
            boss.hp = 40 if phase == 3 else 100
            before = boss.hp
            boss.on_hazard_hit(DrainCircle(0, 0, 85, 1.0, 18))
            results[phase] = boss.hp - before
        self.assertEqual(results[2], PHASE_STATS[2]["drain_heal"])
        self.assertEqual(results[3], PHASE_STATS[3]["drain_heal"])
        self.assertLess(results[3], results[2])

    def _run_chain(self, phase, seed=1):
        """Start a fresh attack chain and play it until he is exhausted. Returns the attacks used, in order."""
        player = StubPlayer(480, 560)
        boss = boss_in_phase(phase, seed=seed, player=player)
        boss.force_next, boss.minions = None, []                 # (phase 3: a living army would put the Soul Ward up)
        with mock.patch.dict(PHASE_STATS[phase], {"teleport": 0.0}), \
                mock.patch.object(boss, "_can_summon", return_value=False):
            boss.cooldown = 0.0
            boss.state = "idle"
            attacks, previous = [], None
            for _ in range(60 * 60):
                boss.update(DT, player, BOUNDS)
                if boss.state == "windup" and previous != "windup":
                    attacks.append(boss.attack_name)
                previous = boss.state
                if boss.state == "exhausted":
                    break
        return boss, player, attacks

    def test_attacks_come_in_chains_that_grow_each_phase(self):
        for phase in (1, 2, 3):
            with self.subTest(phase=phase):
                boss, player, attacks = self._run_chain(phase)
                self.assertEqual(boss.state, "exhausted")
                self.assertEqual(len(attacks), PHASE_STATS[phase]["combo"] + 1, attacks)
                for first, second in zip(attacks, attacks[1:]):
                    self.assertNotEqual(first, second)              # never the same attack twice in a row
        self.assertEqual([PHASE_STATS[p]["combo"] + 1 for p in (1, 2, 3)], [2, 3, 4])

    def test_chains_have_almost_no_pause_between_attacks(self):
        player = StubPlayer(480, 560)
        boss = boss_in_phase(3, player=player)
        with mock.patch.dict(PHASE_STATS[3], {"teleport": 0.0}):
            boss.cooldown = 0.0
            boss.state = "idle"
            advance(boss, player, 0.05)
            while boss.state != "idle":
                boss.update(DT, player, BOUNDS)
            self.assertTrue(boss.combo_pending)                       # the next attack is already coming
            self.assertAlmostEqual(boss.cooldown, COMBO_PAUSE, places=1)

    def test_he_is_exhausted_after_a_chain_and_takes_bonus_damage(self):
        for phase in (1, 2, 3):
            with self.subTest(phase=phase):
                boss, player, _ = self._run_chain(phase)
                self.assertFalse(boss.invulnerable)
                before = boss.hp
                self.assertEqual(boss.take_damage(20), int(round(20 * EXHAUST_BONUS)))
                self.assertEqual(boss.hp, before - int(round(20 * EXHAUST_BONUS)))

    def test_no_bonus_damage_outside_the_window(self):
        boss = boss_in_phase(2)
        self.assertEqual(boss.state, "idle")
        self.assertEqual(boss.take_damage(20), 20)

    def test_the_window_lasts_as_long_as_promised_then_he_goes_back_to_work(self):
        for phase in (1, 2, 3):
            with self.subTest(phase=phase):
                boss, player, _ = self._run_chain(phase)
                with mock.patch.dict(PHASE_STATS[phase], {"teleport": 0.0}):
                    advance(boss, player, PHASE_STATS[phase]["exhaust"] - 0.15)
                    self.assertEqual(boss.state, "exhausted")
                    advance(boss, player, 0.3)
                    self.assertEqual(boss.state, "idle")

    def test_every_window_is_long_enough_to_walk_up_and_land_hits(self):
        """~0.8 s to reach him + at least three 0.4 s sword swings."""
        for phase in (1, 2, 3):
            self.assertGreaterEqual(PHASE_STATS[phase]["exhaust"], 2.0, phase)

    def test_the_health_pool_is_huge(self):
        self.assertGreaterEqual(BOSS_MAX_HP, 2000)
        self.assertEqual(LichKing(seed=1).max_hp, BOSS_MAX_HP)


class TestSoulBarrage(unittest.TestCase):
    def _fire(self, phase, player=None):
        player = player or StubPlayer(480, 560)
        boss = boss_in_phase(phase, player=player)
        boss._begin_attack("barrage", player, BOUNDS)
        advance(boss, player, boss.windup_time + 0.02)
        return boss, player

    def test_it_has_a_wind_up_before_the_first_bolt(self):
        player = StubPlayer(480, 560)
        boss = boss_in_phase(2, player=player)
        boss._begin_attack("barrage", player, BOUNDS)
        advance(boss, player, boss.windup_time - 0.1)
        self.assertEqual(boss.projectiles, [])
        self.assertIsNone(boss.barrage)

    def test_it_fires_the_promised_number_of_bolts_across_a_wedge(self):
        for phase in (1, 2, 3):
            with self.subTest(phase=phase):
                boss, player = self._fire(phase)
                total = PHASE_STATS[phase]["barrage_bolts"]
                advance(boss, player, total * PHASE_STATS[phase]["barrage_interval"] + 0.1)
                self.assertEqual(boss.scheduled, [])
                angles = [boss._barrage_angle(i) for i in range(total)]
                spread = abs(angles[-1] - angles[0])
                self.assertAlmostEqual(spread, math.radians(PHASE_STATS[phase]["barrage_sweep"]), places=4)

    def test_the_bolts_are_sweeping_not_a_wall(self):
        boss, player = self._fire(3)
        angles = [boss._barrage_angle(i) for i in range(PHASE_STATS[3]["barrage_bolts"])]
        self.assertEqual(angles, sorted(angles) if boss.barrage["dir"] == 1 else sorted(angles, reverse=True))

    def test_standing_outside_the_wedge_is_completely_safe(self):
        player = StubPlayer(480, 560)
        boss = boss_in_phase(3, player=player)
        boss.x, boss.y = 480.0, 268.0
        boss._begin_attack("barrage", player, BOUNDS)
        advance(boss, player, boss.windup_time + 0.02)
        centre, half = boss.barrage["centre"], boss.barrage["half"]
        safe_angle = centre + half + math.radians(25)
        player.rect.center = (round(boss.x + math.cos(safe_angle) * 300), round(boss.y + math.sin(safe_angle) * 300))
        for _ in range(60 * 3):
            boss.update(DT, player, BOUNDS)
            if boss.state == "exhausted":                    # the barrage is over; the next chain hasn't begun
                break
        advance(boss, player, 1.0)                           # let the last bolts fly past
        self.assertEqual(player.damage_taken, 0)

    def test_a_player_in_the_wedge_gets_hit(self):
        player = StubPlayer(480, 560)
        boss = boss_in_phase(2, player=player)
        boss.x, boss.y = 480.0, 268.0
        boss._begin_attack("barrage", player, BOUNDS)
        advance(boss, player, boss.windup_time + 3.0)
        self.assertGreaterEqual(player.damage_taken, BARRAGE_DAMAGE)

    def test_it_is_cancelled_when_he_changes_phase(self):
        boss, player = self._fire(2)
        boss.debug_set_hp_percent(0.2)
        self.assertIsNone(boss.barrage)
        self.assertEqual(boss.scheduled, [])

    def test_the_telegraph_draws(self):
        boss, player = self._fire(2)
        boss._draw_barrage_telegraph(pygame.Surface((960, 640)))
        boss2 = boss_in_phase(2)
        boss2._begin_attack("barrage", StubPlayer(), BOUNDS)
        boss2._draw_barrage_telegraph(pygame.Surface((960, 640)))


class TestAimLock(unittest.TestCase):
    """Volley and barrage stop tracking the player at the end of the wind-up: moving then actually works."""

    def _locked_angles(self, attack):
        player = StubPlayer(300, 560)
        boss = boss_in_phase(2, player=player)
        boss.x, boss.y = 480.0, 268.0
        boss._begin_attack(attack, player, BOUNDS)
        advance(boss, player, boss.windup_time - boss_module.AIM_LOCK - 0.05)
        before = boss.aim
        advance(boss, player, boss.windup_time - boss.state_time - 0.12)       # inside the lock
        player.rect.center = (700, 560)                                         # the player sidesteps
        advance(boss, player, 0.05)
        return boss, before, player

    def test_the_aim_freezes_during_the_last_moments(self):
        for attack in ("volley", "barrage"):
            with self.subTest(attack=attack):
                boss, before, player = self._locked_angles(attack)
                self.assertEqual(boss.state, "windup")
                self.assertNotEqual(boss.aim, (player.rect.centerx, player.rect.centery))

    def test_before_the_lock_he_still_tracks_you(self):
        player = StubPlayer(300, 560)
        boss = boss_in_phase(2, player=player)
        boss._begin_attack("volley", player, BOUNDS)
        advance(boss, player, 0.1)
        player.rect.center = (700, 560)
        advance(boss, player, 0.05)
        self.assertEqual(boss.aim, (700, 560))

    def test_a_sidestep_after_the_lock_dodges_the_whole_volley(self):
        player = StubPlayer(300, 560)
        boss = boss_in_phase(2, player=player)
        boss.x, boss.y = 480.0, 268.0
        boss._begin_attack("volley", player, BOUNDS)
        advance(boss, player, boss.windup_time - 0.15)                          # lock is on
        player.rect.center = (860, 560)                                         # far out of every lane
        advance(boss, player, 3.0)
        self.assertEqual(player.damage_taken, 0)

    def test_other_attacks_are_unaffected(self):
        player = StubPlayer(300, 560)
        boss = boss_in_phase(2, player=player)
        boss._begin_attack("nova", player, BOUNDS)
        advance(boss, player, boss.windup_time - 0.1)
        player.rect.center = (700, 560)
        advance(boss, player, 0.05)
        self.assertEqual(boss.aim, (700, 560))


class TestExhaustedLook(unittest.TestCase):
    def test_the_window_is_drawn_and_labelled(self):
        player = StubPlayer()
        boss = boss_in_phase(2, player=player)
        boss.state, boss.state_time = "exhausted", 0.5
        surface = pygame.Surface((960, 640))
        boss.draw(surface)
        boss.draw_health_bar(surface, pygame.font.Font(None, 26))

    def test_he_looks_slumped(self):
        boss = boss_in_phase(2)
        boss.state = "exhausted"
        look = boss._look()
        self.assertEqual(look["pose"], "recover")

    def test_every_phase_draws_every_state_without_errors(self):
        surface = pygame.Surface((960, 640))
        font = pygame.font.Font(None, 26)
        for phase in (1, 2, 3):
            boss = boss_in_phase(phase)
            for attack in ("volley", "drain", "rain", "barrage", "nova", "grasp", "summon"):
                boss.state, boss.cooldown = "idle", 99
                boss._begin_attack(attack, StubPlayer(), BOUNDS)
                for _ in range(int(boss.windup_time / DT) + 20):
                    boss.update(DT, StubPlayer(), BOUNDS)
                    boss.draw(surface)
                    boss.draw_health_bar(surface, font)


class TestSoulRain(unittest.TestCase):
    def _rain(self, phase, px=480, py=450):
        player = StubPlayer(px, py)
        boss = boss_in_phase(phase, player=player)
        boss._begin_attack("rain", player, BOUNDS)
        return boss, player

    def test_it_makes_the_promised_number_of_circles_one_under_the_player(self):
        for phase in (1, 2, 3):
            with self.subTest(phase=phase):
                boss, player = self._rain(phase)
                rain = [h for h in boss.hazards if isinstance(h, SoulRain)]
                self.assertEqual(len(rain), PHASE_STATS[phase]["rain_circles"])
                self.assertTrue(any(math.hypot(h.x - player.rect.centerx, h.y - player.rect.centery) < 1
                                    for h in rain))

    def test_the_circles_burst_one_after_another_never_all_at_once(self):
        boss, player = self._rain(3)
        durations = sorted(h.duration for h in boss.hazards)
        self.assertEqual(len(set(durations)), len(durations))
        self.assertGreaterEqual(durations[0], boss.windup_time - 1e-6)

    def test_there_are_always_gaps_to_stand_in(self):
        """Circles are kept apart, so a player moving to a gap is never forced into one."""
        for seed in range(15):
            player = StubPlayer(480, 450)
            boss = boss_in_phase(3, seed=seed, player=player)
            boss._begin_attack("rain", player, BOUNDS)
            r = PHASE_STATS[3]["rain_radius"]
            spots = [(h.x, h.y) for h in boss.hazards]
            hit = 0
            for gx in range(BOUNDS[0] + 20, BOUNDS[2] - 20, 15):
                for gy in range(BOUNDS[1] + 20, BOUNDS[3] - 20, 15):
                    if not any(math.hypot(gx - x, gy - y) <= r + 14 for x, y in spots):
                        hit += 1
            self.assertGreater(hit, 200, f"seed {seed}: almost nowhere safe")

    def test_standing_still_gets_you_hit_and_it_does_not_heal_him(self):
        boss, player = self._rain(2)
        boss.take_damage(500)
        boss.state = "idle"
        hp = boss.hp
        advance(boss, player, boss.windup_time + 2.0)
        self.assertGreaterEqual(player.damage_taken, RAIN_DAMAGE)
        self.assertLessEqual(boss.hp, hp)                       # soul rain never heals

    def test_a_plain_drain_circle_still_heals(self):
        boss = boss_in_phase(2)
        boss.hp -= 500
        hp = boss.hp
        boss.on_hazard_hit(DrainCircle(0, 0, 85, 1.0, 18))
        self.assertGreater(boss.hp, hp)


class TestArmyOfTheDead(unittest.TestCase):
    def test_minions_are_undying_tier(self):
        boss = boss_in_phase(2)
        player = StubPlayer()
        boss._begin_attack("summon", player, BOUNDS)
        advance(boss, player, boss.windup_time + 0.05)
        self.assertTrue(boss.minions)
        for m in boss.minions:
            base = boss_module.spawn_monster(m.NAME, 0, 0, spawn=False)
            self.assertGreaterEqual(m.max_hp, base.max_hp * 2.9, m.NAME)
            self.assertGreater(m.damage, base.damage, m.NAME)
            self.assertGreater(m.speed, base.speed, m.NAME)

    def test_he_calls_his_army_right_after_each_phase_change(self):
        for phase_hp, phase in ((0.5, 2), (0.2, 3)):
            with self.subTest(phase=phase):
                player = StubPlayer()
                boss = boss_in_phase(phase - 1, player=player)
                boss.state = "idle"
                boss.debug_set_hp_percent(phase_hp)
                self.assertEqual(boss.phase, phase)
                advance(boss, player, boss.TRANSITION_TIME + 0.05)
                boss.cooldown = 0.0
                advance(boss, player, 0.05)
                self.assertEqual(boss.state, "windup")
                self.assertEqual(boss.attack_name, "summon")

    def test_phase_two_army_is_big(self):
        player = StubPlayer()
        boss = boss_in_phase(2, player=player)
        for _ in range(4):
            boss._begin_attack("summon", player, BOUNDS)
            advance(boss, player, boss.windup_time + 0.05)
        from bosses.lich_king.minions import minion_load
        self.assertGreaterEqual(minion_load(boss.minions), 6)
        self.assertLessEqual(minion_load(boss.minions), PHASE_STATS[2]["minion_cap"] + 3)


    def test_clear_attacks_cancels_pairs_and_pending_rings(self):
        boss = boss_in_phase(3)
        boss.scheduled.append([0.3, "nova_ring", 1, (480, 268)])
        boss.combo_left, boss.combo_pending = 1, True
        boss.clear_attacks()
        self.assertEqual((boss.scheduled, boss.combo_left, boss.combo_pending), ([], 0, False))

    def test_a_whole_enraged_fight_can_be_played_and_drawn(self):
        game = Game()
        game.player.god = True
        game.boss = LichKing(seed=7)
        surface = pygame.Surface((960, 640))
        for frame in range(60 * 3):
            game.update(DT, empty_input())
        game.boss.debug_set_hp_percent(0.2)
        phases = set()
        for frame in range(60 * 40):
            inp = empty_input()
            inp["move"] = (math.sin(frame / 25.0), math.cos(frame / 40.0))
            game.update(DT, inp)
            phases.add(game.boss.phase)
            if frame % 3 == 0:
                game.draw(surface)
        self.assertEqual(phases, {3})


class TestEnragedLook(unittest.TestCase):
    def test_look_asks_for_the_right_poses_and_rage(self):
        boss = boss_in_phase(3)
        for attack in ("nova", "grasp"):
            boss.state, boss.attack_name, boss.windup_time, boss.state_time = "windup", attack, 1.0, 0.5
            look = boss._look()
            self.assertEqual(look["pose"], attack)
            self.assertEqual(look["phase"], 2)                        # phase 3 reuses the phase 2 art...
            self.assertEqual(look["rage"], 1.0)                       # ...enraged
        self.assertEqual(boss_in_phase(2)._look()["rage"], 0.0)

    def test_afterimages_follow_a_moving_boss(self):
        boss = boss_in_phase(3)
        boss.state = "idle"
        surface = pygame.Surface((960, 640))
        for step in range(40):
            boss.x = 200 + step * 10                                 # sweeping across the arena
            boss.clock += DT
            boss.trail.append((boss.clock, boss.x, boss.y))
            boss.trail = [t for t in boss.trail if boss.clock - t[0] < 0.5]
        drawn = []
        original = boss.art.draw

        def spy(*args, **kwargs):
            drawn.append(kwargs.get("ghost", False))
            return original(*args, **kwargs)
        boss.art.draw = spy
        boss.draw_boss(surface)
        self.assertEqual(drawn.count(True), 2)                        # two ghosts...
        self.assertEqual(drawn.count(False), 1)                       # ...and the real thing

    def test_no_afterimages_when_not_enraged_or_standing_still(self):
        for phase, move in ((2, True), (3, False)):
            boss = boss_in_phase(phase)
            boss.state = "idle"
            for step in range(40):
                boss.clock += DT
                boss.x = 200 + (step * 10 if move else 0)
                boss.trail.append((boss.clock, boss.x, boss.y))
            drawn = []
            original = boss.art.draw
            boss.art.draw = lambda *a, _o=original, **k: (drawn.append(k.get("ghost", False)), _o(*a, **k))[1]
            boss.draw_boss(pygame.Surface((960, 640)))
            self.assertEqual(drawn.count(True), 0, (phase, move))

    @needs_pygame
    def test_health_bar_shows_the_phase_three_tick_and_turns_hot(self):
        pygame.font.init()
        font = pygame.font.Font(None, 24)
        surface = pygame.Surface((960, 640))
        boss = boss_in_phase(3)
        boss.draw_health_bar(surface, font)
        tick_x = (960 - 520) // 2 + int(520 * 0.2)
        self.assertEqual(surface.get_at((tick_x, 45))[:3], (255, 190, 120))      # the 20% tick
        self.assertEqual(surface.get_at((230, 45))[:3], (255, 150, 60))           # a hot orange bar
        boss2 = boss_in_phase(1)
        surface2 = pygame.Surface((960, 640))
        boss2.draw_health_bar(surface2, font)
        self.assertEqual(surface2.get_at((tick_x, 45))[:3], (255, 190, 120))     # the tick shows from the start
        self.assertNotEqual(surface2.get_at((230, 45))[:3], (255, 150, 60))


if __name__ == "__main__":
    unittest.main()


class TestSoulWard(unittest.TestCase):
    """Phase 3: he is invulnerable while ANY summon lives; killing the whole wave opens him up."""

    def _warded(self, seed=1):
        player = StubPlayer(480, 560)
        boss = boss_in_phase(3, seed, player)
        boss.force_next = None
        boss.state, boss.cooldown = "idle", 5.0
        boss.minions = [boss_module.spawn_monster("skeleton_warrior", 200 + 60 * i, 300, spawn=False) for i in range(3)]
        return boss, player

    def test_a_living_summon_makes_him_invulnerable(self):
        boss, player = self._warded()
        self.assertTrue(boss.shielded and boss.invulnerable)
        before = boss.hp
        self.assertEqual(boss.take_damage(50), 0)
        self.assertEqual(boss.hp, before)
        self.assertGreater(boss.ward_flash, 0)

    def test_it_applies_in_phase_three_only(self):
        boss = boss_in_phase(2)
        boss.minions = [boss_module.spawn_monster("skeleton_warrior", 200, 300, spawn=False)]
        self.assertFalse(boss.shielded)
        self.assertEqual(boss.take_damage(20), 20)

    def test_the_minions_can_still_be_hurt_while_he_is_warded(self):
        boss, _ = self._warded()
        self.assertIn(boss.minions[0], boss.hittables())
        self.assertGreater(boss.minions[0].take_damage(10), 0)

    def test_killing_the_whole_wave_breaks_the_ward_and_opens_a_bonus_window(self):
        boss, player = self._warded()
        for m in boss.minions[:-1]:
            m.kill()
        advance(boss, player, 0.1)
        self.assertTrue(boss.shielded)                           # one is still standing
        boss.minions[-1].kill() if boss.minions else None
        for m in boss.minions:
            m.kill()
        advance(boss, player, 0.1)
        self.assertFalse(boss.shielded)
        self.assertGreater(boss.break_time, 0)
        before = boss.hp
        self.assertEqual(boss.take_damage(20), int(round(20 * EXHAUST_BONUS)))
        self.assertEqual(boss.hp, before - int(round(20 * EXHAUST_BONUS)))

    def test_breaking_the_ward_stuns_him_and_cancels_his_attack(self):
        boss, player = self._warded()
        boss._begin_attack("rain", player, BOUNDS)
        self.assertTrue(boss.hazards)
        advance(boss, player, 0.05)                              # the ward is up
        for m in boss.minions:
            m.kill()
        advance(boss, player, 0.05)
        self.assertEqual(boss.state, "stunned")
        self.assertEqual((boss.hazards, boss.scheduled, boss.combo_left), ([], [], 0))
        projectiles = len(boss.projectiles)
        advance(boss, player, SHIELD_BREAK_WINDOW - 0.3)
        self.assertEqual(boss.state, "stunned")                  # he cannot act while stunned
        self.assertLessEqual(len(boss.projectiles), projectiles)
        self.assertEqual(boss.take_damage(20), int(round(20 * EXHAUST_BONUS)))
        advance(boss, player, 0.5)
        self.assertEqual(boss.state, "idle")                     # then he goes back to work

    def test_the_stun_can_be_drawn(self):
        pygame.font.init()
        boss, player = self._warded()
        for m in boss.minions:
            m.kill()
        advance(boss, player, 0.1)
        surface = pygame.Surface((960, 640))
        boss.draw(surface)
        boss.draw_health_bar(surface, pygame.font.Font(None, 22))

    def test_the_bonus_window_ends(self):
        boss, player = self._warded()
        for m in boss.minions:
            m.kill()
        advance(boss, player, 0.1)
        advance(boss, player, SHIELD_BREAK_WINDOW + 0.2)
        self.assertEqual(boss.break_time, 0)
        self.assertEqual(boss.take_damage(20), 20)

    def test_he_does_not_get_an_exhaust_window_while_warded(self):
        boss, player = self._warded()
        boss.set_state("recover")
        boss.combo_left = 0
        advance(boss, player, PHASE_STATS[3]["recover"] + 0.1)
        self.assertNotEqual(boss.state, "exhausted")

    def test_he_calls_one_wave_at_a_time(self):
        boss, _ = self._warded()
        self.assertNotIn("summon", {boss._choose_attack() for _ in range(200)})
        boss.minions = []
        self.assertTrue(boss._can_summon())

    def test_leaving_him_alone_brings_the_ward_back(self):
        boss, player = self._warded()
        boss.minions = []
        boss.free_time = REARM_AFTER
        self.assertEqual(boss._choose_attack(), "summon")

    def test_acolytes_can_only_raise_a_few_dead_per_wave(self):
        boss, player = self._warded()
        boss.wave_raises = 0
        for _ in range(8):
            acolyte = boss_module.spawn_monster("skeleton_acolyte", 300, 300, spawn=False)
            acolyte.spawn_requests = [boss_module.spawn_monster("skeleton_warrior", 310, 310, spawn=False)]
            boss.minions.append(acolyte)
        boss.minions = boss.minions[:0] + [m for m in boss.minions if m.NAME == "skeleton_acolyte"][:3]
        before = len(boss.minions)
        boss._update_attacks(DT, player, BOUNDS)
        self.assertLessEqual(len(boss.minions) - before, WAVE_RAISE_BUDGET)
        self.assertLessEqual(boss.wave_raises, WAVE_RAISE_BUDGET)

    def test_a_new_wave_appears_in_phase_three_and_raises_the_ward(self):
        boss, player = boss_in_phase(3), StubPlayer(480, 560)
        boss.minions = []
        boss._begin_attack("summon", player, BOUNDS)
        advance(boss, player, boss.windup_time + 0.1)
        self.assertEqual(len(boss.minions), PHASE_STATS[3]["summon_picks"])
        self.assertTrue(boss.shielded)

    def test_the_ward_and_its_labels_can_be_drawn(self):
        pygame.font.init()
        boss, player = self._warded()
        surface, font = pygame.Surface((960, 640)), pygame.font.Font(None, 22)
        boss.draw(surface)
        boss.draw_health_bar(surface, font)
        for m in boss.minions:
            m.kill()
        advance(boss, player, 0.1)
        boss.draw(surface)
        boss.draw_health_bar(surface, font)

    def test_the_ward_never_blocks_the_killing_blow_or_the_death(self):
        boss, player = self._warded()
        for m in boss.minions:
            m.kill()
        advance(boss, player, 0.1)
        boss.take_damage(99999)
        self.assertFalse(boss.is_alive())
        self.assertFalse(boss.shielded)
