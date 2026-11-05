"""
Tests for the Lich King's pixel-art spell effects (lich_king/effects.py and the hazards / projectiles built on it).

Run from the repo root:  python -m unittest discover -s src/bosses/tests
"""
import math
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

from bosses import LichKing
from bosses.dev.arena import BOUNDS
from bosses.lich_king import effects as fxm
from bosses.lich_king.boss import PHASE_STATS
from bosses.lich_king.bone_shard import BoneShard
from bosses.lich_king.drain_circle import DrainCircle
from bosses.lich_king.effects import (FxLayer, GroundCracks, PIXEL, ShockBurst, clip_to, crack_points, draw_polyline,
                                      hexagram, jagged_points, lerp_color, rune_ring, soul_ribbon, theme, with_alpha)
from bosses.lich_king.grasping_hand import GraspingHand
from bosses.lich_king.soul_bolt import SoulBolt

DT = 1 / 60
REAL_PYGAME = hasattr(pygame, "mask")
needs_pygame = unittest.skipUnless(REAL_PYGAME, "needs real pygame to look at the pixels")
BLACK = (0, 0, 0)


class StubPlayer:
    def __init__(self, x=480, y=500):
        self.rect = pygame.Rect(0, 0, 28, 28)
        self.rect.center = (x, y)
        self.damage_taken = 0

    def take_damage(self, amount):
        self.damage_taken += amount
        return amount


def black_surface(size=(960, 640)):
    surface = pygame.Surface(size)
    surface.fill(BLACK)
    return surface


def lit(surface, step=2):
    w, h = surface.get_size()
    return sum(1 for x in range(0, w, step) for y in range(0, h, step) if surface.get_at((x, y))[:3] != BLACK)


def brightness(surface, step=2):
    w, h = surface.get_size()
    return sum(sum(surface.get_at((x, y))[:3]) for x in range(0, w, step) for y in range(0, h, step))


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


class TestThemes(unittest.TestCase):
    def test_each_phase_has_its_own_spell_colours(self):
        mains = {theme(p)["main"] for p in (1, 2, 3)}
        self.assertEqual(len(mains), 3)

    def test_out_of_range_phases_are_clamped(self):
        self.assertEqual(theme(0), theme(1))
        self.assertEqual(theme(9), theme(3))

    def test_colour_helpers_clamp(self):
        self.assertEqual(with_alpha((10, 20, 30), 999), (10, 20, 30, 255))
        self.assertEqual(with_alpha((10, 20, 30), -5), (10, 20, 30, 0))
        self.assertEqual(lerp_color((0, 0, 0), (200, 100, 50), 2.0), (200, 100, 50))
        self.assertEqual(lerp_color((0, 0, 0), (200, 100, 50), -1.0), (0, 0, 0))


class TestFxLayer(unittest.TestCase):
    def test_the_layer_snaps_to_the_shared_pixel_grid(self):
        fx = FxLayer(10, 11, 100, 100)
        self.assertEqual(fx.left % PIXEL, 0)
        self.assertEqual(fx.top % PIXEL, 0)

    @needs_pygame
    def test_pixels_are_chunky_blocks_on_the_grid(self):
        surface = black_surface((60, 60))
        fx = FxLayer(0, 0, 60, 60)
        fx.dot(10, 10, (255, 0, 0, 255))                       # low-res cell (3, 3) = screen 9..11
        fx.draw(surface)
        self.assertEqual(surface.get_at((9, 9))[:3], (255, 0, 0))
        self.assertEqual(surface.get_at((11, 11))[:3], (255, 0, 0))
        self.assertEqual(surface.get_at((12, 12))[:3], BLACK)
        self.assertEqual(surface.get_at((8, 8))[:3], BLACK)

    @needs_pygame
    def test_soft_shapes_are_dithered_into_a_checkerboard(self):
        surface = black_surface((90, 90))
        fx = FxLayer(0, 0, 90, 90)
        fx.rect(0, 0, 89, 89, (255, 255, 255, 255), soft=True)
        fx.draw(surface)
        cells = [(x, y) for x in range(0, 90, PIXEL) for y in range(0, 90, PIXEL)]
        on = sum(1 for x, y in cells if surface.get_at((x + 1, y + 1))[:3] != BLACK)
        self.assertTrue(0.4 < on / float(len(cells)) < 0.6, on / float(len(cells)))
        neighbours = [surface.get_at((1, 1))[:3], surface.get_at((1 + PIXEL, 1))[:3]]
        self.assertNotEqual(neighbours[0], neighbours[1])        # neighbouring pixels alternate

    @needs_pygame
    def test_solid_pixels_draw_over_soft_ones(self):
        surface = black_surface((60, 60))
        fx = FxLayer(0, 0, 60, 60)
        fx.rect(0, 0, 59, 59, (0, 0, 255, 255), soft=True)
        fx.rect(0, 0, 29, 29, (255, 0, 0, 255))
        fx.draw(surface)
        self.assertEqual(surface.get_at((13, 13))[:3], (255, 0, 0))
        self.assertEqual(surface.get_at((14, 14))[:3], (255, 0, 0))

    @needs_pygame
    def test_clip_to_keeps_effects_inside_the_arena_and_restores_the_clip(self):
        surface = black_surface((200, 200))
        before = surface.get_clip()
        with clip_to(surface, (60, 60, 140, 140)):
            fx = FxLayer(0, 0, 200, 200)
            fx.rect(0, 0, 199, 199, (255, 255, 255, 255))
            fx.draw(surface)
        self.assertEqual(surface.get_at((20, 20))[:3], BLACK)
        self.assertEqual(surface.get_at((100, 100))[:3], (255, 255, 255))
        self.assertEqual(surface.get_clip(), before)

    def test_clip_to_does_nothing_on_a_surface_that_cannot_clip(self):
        with clip_to(object(), (0, 0, 10, 10)):
            pass


class TestBuildingBlocks(unittest.TestCase):
    def test_broken_ground_is_never_a_clean_circle(self):
        pts = jagged_points(100, 100, 40, seed=3)
        radii = [math.hypot(x - 100, y - 100) for x, y in pts]
        self.assertGreater(max(radii) / min(radii), 1.25)
        self.assertEqual(pts, jagged_points(100, 100, 40, seed=3))          # but it is repeatable
        self.assertNotEqual(pts, jagged_points(100, 100, 40, seed=4))

    def test_cracks_wander_from_their_start_and_are_repeatable(self):
        pts = crack_points(50, 60, 0.5, 100, seed=7)
        self.assertEqual(pts[0], (50, 60))
        self.assertEqual(len(pts), 7)
        self.assertEqual(pts, crack_points(50, 60, 0.5, 100, seed=7))
        straight_end = (50 + math.cos(0.5) * 100, 60 + math.sin(0.5) * 100)
        self.assertGreater(math.hypot(pts[-1][0] - straight_end[0], pts[-1][1] - straight_end[1]), 1.0)

    @needs_pygame
    def test_a_crack_can_grow(self):
        pts = crack_points(100, 100, 0.0, 120, seed=1)
        counts = []
        for fraction in (0.0, 0.3, 1.0):
            surface = black_surface((300, 300))
            fx = FxLayer(0, 0, 300, 300)
            draw_polyline(fx, pts, (255, 255, 255, 255), width=1, upto=fraction)
            fx.draw(surface)
            counts.append(lit(surface, 1))
        self.assertEqual(counts[0], 0)
        self.assertLess(counts[1], counts[2])
        self.assertGreater(counts[1], 0)

    @needs_pygame
    def test_a_rune_ring_turns(self):
        pictures = []
        for clock in (0.0, 1.0):
            surface = black_surface((300, 300))
            fx = FxLayer(0, 0, 300, 300)
            rune_ring(fx, 150, 150, 100, (255, 255, 255, 255), clock)
            fx.draw(surface)
            pictures.append(pygame.image.tostring(surface, "RGB"))
            self.assertGreater(lit(surface, 1), 150)
        self.assertNotEqual(pictures[0], pictures[1])

    @needs_pygame
    def test_sigils_and_streams_draw(self):
        surface = black_surface((300, 300))
        fx = FxLayer(0, 0, 300, 300)
        hexagram(fx, 150, 150, 80, (255, 255, 255, 255), 0.3)
        soul_ribbon(fx, (20, 20), (280, 280), 0.4, (151, 196, 89))
        fx.draw(surface)
        self.assertGreater(lit(surface, 1), 100)

    @needs_pygame
    def test_a_soul_ribbon_flows(self):
        pictures = []
        for clock in (0.0, 0.3):
            surface = black_surface((300, 300))
            fx = FxLayer(0, 0, 300, 300)
            soul_ribbon(fx, (20, 20), (280, 280), clock, (151, 196, 89))
            fx.draw(surface)
            pictures.append(pygame.image.tostring(surface, "RGB"))
        self.assertNotEqual(pictures[0], pictures[1])


class TestBursts(unittest.TestCase):
    def test_a_shock_burst_plays_and_ends(self):
        burst = ShockBurst(400, 300, 2, life=0.5)
        self.assertTrue(burst.alive)
        for _ in range(int(0.6 / DT)):
            burst.update(DT)
        self.assertFalse(burst.alive)

    @needs_pygame
    def test_a_shock_burst_grows_outwards(self):
        def extent(age):
            surface = black_surface()
            burst = ShockBurst(480, 320, 2, life=0.5, max_radius=280)
            burst.age = age
            burst.draw(surface)
            xs = [x for x in range(0, 960, 3) for y in (320,) if surface.get_at((x, y))[:3] != BLACK]
            return max(abs(x - 480) for x in xs) if xs else 0
        self.assertLess(extent(0.1), extent(0.3))

    @needs_pygame
    def test_ground_cracks_race_out_then_fade(self):
        counts, glow = [], []
        for age in (0.05, 0.3, 0.95):
            surface = black_surface()
            cracks = GroundCracks(480, 320, 2, life=1.0, seed=2)
            cracks.age = age
            cracks.draw(surface)
            counts.append(lit(surface, 1))
            glow.append(brightness(surface, 1))
        self.assertLess(counts[0], counts[1])                  # growing
        self.assertLess(glow[2], glow[1] * 0.5)                # then fading away (dimmer, not just smaller)

    def test_cracks_expire(self):
        cracks = GroundCracks(0, 0, 2, life=0.5)
        for _ in range(int(0.6 / DT)):
            cracks.update(DT)
        self.assertFalse(cracks.alive)


@needs_pygame
class TestHazardVisuals(unittest.TestCase):
    def _drain(self, timer, phase=1):
        circle = DrainCircle(480, 320, 85, 1.0, 18, phase=phase)
        player = StubPlayer(10, 10)
        while circle.timer + 1e-9 < timer and circle.state == "warning":
            circle.update(DT, player)
        surface = black_surface()
        circle.draw(surface)
        return surface

    def test_the_drain_circle_draws_in_every_state(self):
        for t in (0.0, 0.5, 0.95, 1.1, 1.25):
            circle = DrainCircle(480, 320, 85, 1.0, 18)
            for _ in range(int(t / DT)):
                circle.update(DT, StubPlayer(10, 10))
            surface = black_surface()
            circle.draw(surface)
            self.assertGreater(lit(surface, 1), 80, t)

    def test_the_runes_turn(self):
        a = pygame.image.tostring(self._drain(0.3), "RGB")
        b = pygame.image.tostring(self._drain(0.6), "RGB")
        self.assertNotEqual(a, b)

    def test_it_flashes_just_before_it_bursts(self):
        self.assertGreater(brightness(self._drain(0.97)), brightness(self._drain(0.4)))

    def test_each_phase_has_its_own_colours(self):
        self.assertNotEqual(pygame.image.tostring(self._drain(0.5, 1), "RGB"),
                            pygame.image.tostring(self._drain(0.5, 3), "RGB"))

    def test_the_hand_warning_is_a_broken_patch_that_changes_over_time(self):
        pictures = []
        for t in (0.2, 0.6, 0.9):
            hand = GraspingHand(480, 320, 42, 1.0, 12, 1.0, seed=1.3)
            for _ in range(int(t / DT)):
                hand.update(DT, StubPlayer(10, 10))
            surface = black_surface()
            hand.draw(surface)
            self.assertGreater(lit(surface, 1), 60, t)
            pictures.append(pygame.image.tostring(surface, "RGB"))
        self.assertEqual(len(set(pictures)), 3)

    def test_the_hand_warning_is_not_a_perfect_disc(self):
        """A clean circle is symmetrical; broken ground is not."""
        hand = GraspingHand(480, 320, 42, 1.0, 12, 1.0, seed=2.1)
        for _ in range(int(0.5 / DT)):
            hand.update(DT, StubPlayer(10, 10))
        surface = black_surface()
        hand.draw(surface)
        extents = []
        for deg in range(0, 360, 30):
            a = math.radians(deg)
            reach = 0
            for r in range(5, 70):
                px, py = int(480 + math.cos(a) * r), int(320 + math.sin(a) * r)
                if surface.get_at((px, py))[:3] != BLACK:
                    reach = r
            extents.append(reach)
        self.assertGreater(max(extents) - min(extents), 6)


class TestProjectileVisuals(unittest.TestCase):
    def test_bone_shards_leave_a_trail_of_dust(self):
        shard = BoneShard(300, 300, 0.0, 300, 10)
        for _ in range(12):
            shard.update(DT, StubPlayer(10, 10), BOUNDS)
        self.assertGreaterEqual(len(shard.trail), 5)
        self.assertLessEqual(len(shard.trail), 7)

    @needs_pygame
    def test_shards_and_bolts_draw(self):
        for projectile in (BoneShard(300, 300, 0.7, 300, 10), SoulBolt(300, 300, 0.7, 300, 12, phase=2)):
            surface = black_surface((600, 600))
            projectile.draw(surface)
            self.assertGreater(lit(surface, 1), 40, type(projectile).__name__)

    @needs_pygame
    def test_bolts_change_colour_with_the_phase(self):
        pictures = []
        for phase in (1, 2, 3):
            surface = black_surface((600, 600))
            SoulBolt(300, 300, 0.0, 300, 12, phase=phase).draw(surface)
            pictures.append(pygame.image.tostring(surface, "RGB"))
        self.assertEqual(len(set(pictures)), 3)

    def test_a_soul_bolt_still_behaves_like_a_projectile(self):
        bolt = SoulBolt(400, 300, 0.0, 300, 12, phase=1)
        player = StubPlayer(430, 300)
        for _ in range(30):
            bolt.update(DT, player, BOUNDS)
        self.assertEqual(player.damage_taken, 12)
        self.assertFalse(bolt.alive)


class TestBossEffects(unittest.TestCase):
    def test_the_boss_remembers_the_arena_for_clipping(self):
        boss = LichKing(seed=1)
        boss.update(DT, StubPlayer(), (50, 120, 900, 580))
        self.assertEqual(boss.bounds, (50, 120, 900, 580))

    def test_the_volley_fires_exactly_along_the_telegraphed_lanes(self):
        for phase in (1, 2, 3):
            player = StubPlayer(300, 540)
            boss = boss_in_phase(phase, player=player)
            boss._begin_attack("volley", player, BOUNDS)
            advance(boss, player, boss.windup_time - 0.05)
            expected = boss._volley_angles((player.rect.centerx, player.rect.centery))
            self.assertEqual(len(expected), PHASE_BOLTS[phase])
            advance(boss, player, 0.1)
            fired = sorted(p.angle for p in boss.projectiles if isinstance(p, SoulBolt))
            self.assertEqual(len(fired), len(expected))
            for a, b in zip(fired, sorted(expected)):
                self.assertAlmostEqual(a, b, places=6)

    @needs_pygame
    def test_the_volley_telegraph_shows_more_lanes_in_later_phases(self):
        counts = {}
        for phase in (1, 3):
            player = StubPlayer(480, 560)
            boss = boss_in_phase(phase, player=player)
            boss._begin_attack("volley", player, BOUNDS)
            advance(boss, player, 0.3)
            surface = black_surface()
            boss._draw_volley_telegraph(surface)
            counts[phase] = lit(surface, 2)
            self.assertGreater(counts[phase], 150)
        self.assertGreater(counts[3], counts[1])

    def test_summoning_shows_what_and_where_before_it_happens(self):
        player = StubPlayer(480, 560)
        boss = boss_in_phase(2, player=player)
        boss._begin_attack("summon", player, BOUNDS)
        plan = list(boss.summon_plan)
        self.assertGreaterEqual(len(plan), 1)
        for name, x, y in plan:
            self.assertIn(name, ("skeleton_warrior", "skeleton_archer", "skeleton_acolyte", "skeleton_brute"))
            self.assertTrue(BOUNDS[0] < x < BOUNDS[2] and BOUNDS[1] < y < BOUNDS[3])
            self.assertGreater(math.hypot(x - 480, y - 560), 100)
        advance(boss, player, boss.windup_time + 0.05)
        self.assertEqual([(m.NAME, m.x, m.y) for m in boss.minions][:len(plan)], [(n, x, y) for n, x, y in plan])
        self.assertEqual(boss.summon_plan, [])

    def test_summoning_still_works_without_a_plan(self):
        player = StubPlayer(480, 560)
        boss = boss_in_phase(2, player=player)
        boss.summon_plan = []
        boss._summon(player, BOUNDS)
        self.assertGreaterEqual(len(boss.minions), 1)

    def test_changing_phase_cancels_the_summoning_sigils(self):
        player = StubPlayer(480, 560)
        boss = boss_in_phase(2, player=player)
        boss._begin_attack("summon", player, BOUNDS)
        boss.debug_set_hp_percent(0.2)
        self.assertEqual(boss.summon_plan, [])

    @needs_pygame
    def test_summoning_sigils_draw(self):
        player = StubPlayer(480, 560)
        boss = boss_in_phase(2, player=player)
        boss._begin_attack("summon", player, BOUNDS)
        advance(boss, player, 0.5)
        surface = black_surface()
        boss._draw_summon_sigils(surface)
        self.assertGreater(lit(surface, 2), 100)

    def test_the_nova_leaves_a_shockwave_and_cracks_that_then_expire(self):
        player = StubPlayer(480, 560)
        boss = boss_in_phase(2, player=player)
        boss._begin_attack("nova", player, BOUNDS)
        advance(boss, player, boss.windup_time + 0.05)
        kinds = {type(b) for b in boss.bursts}
        self.assertEqual(kinds, {ShockBurst, GroundCracks})
        boss.state, boss.cooldown = "idle", 99
        advance(boss, player, 1.3)
        self.assertEqual(boss.bursts, [])

    def test_phase_three_makes_a_burst_for_each_ring(self):
        player = StubPlayer(480, 560)
        boss = boss_in_phase(3, player=player)
        boss._begin_attack("nova", player, BOUNDS)
        advance(boss, player, boss.windup_time + 0.05)
        first = len(boss.bursts)
        advance(boss, player, 0.7)
        self.assertGreater(len(boss.bursts), first - 1)
        self.assertTrue(any(isinstance(b, ShockBurst) and b.max_radius > 300 for b in boss.bursts))

    @needs_pygame
    def test_the_nova_floor_effect_stays_inside_the_arena(self):
        player = StubPlayer(480, 560)
        boss = boss_in_phase(2, player=player)
        boss._begin_attack("nova", player, BOUNDS)
        advance(boss, player, 0.6)
        surface = black_surface()
        boss._draw_ground_effects(surface)
        left, top, right, bottom = BOUNDS
        # (a stride of 5 avoids lining up with the checkerboard dither, which would show all or nothing)
        inside = sum(1 for x in range(left, right, 5) for y in range(top, bottom, 5) if surface.get_at((x, y))[:3] != BLACK)
        outside = sum(1 for x in range(0, left - 3, 5) for y in range(0, 640, 5) if surface.get_at((x, y))[:3] != BLACK)
        self.assertGreater(inside, 500)
        self.assertEqual(outside, 0)

    @needs_pygame
    def test_the_nova_is_drawn_in_two_layers_floor_and_overlay(self):
        player = StubPlayer(480, 560)
        boss = boss_in_phase(2, player=player)
        boss._begin_attack("nova", player, BOUNDS)
        advance(boss, player, 0.6)
        ground, overlay = black_surface(), black_surface()
        boss._draw_nova_ground(ground)
        boss._draw_nova_overlay(overlay)
        self.assertGreater(lit(ground, 3), 500)
        self.assertGreater(lit(overlay, 2), 80)
        both = black_surface()
        boss._draw_nova_telegraph(both)
        self.assertGreaterEqual(lit(both, 3), lit(ground, 3))

    @needs_pygame
    def test_the_second_ring_of_phase_three_is_also_shown(self):
        pictures = {}
        for phase in (2, 3):
            player = StubPlayer(480, 560)
            boss = boss_in_phase(phase, player=player)
            boss.nova_gap = 1.0
            boss._begin_attack("nova", player, BOUNDS)
            boss.nova_gap = 1.0
            advance(boss, player, 0.6)
            surface = black_surface()
            boss._draw_nova_overlay(surface)
            pictures[phase] = lit(surface, 2)
        self.assertGreater(pictures[3], pictures[2])

    @needs_pygame
    def test_stolen_life_flows_back_as_a_soul_stream(self):
        boss = boss_in_phase(2)
        surface = black_surface()
        boss.draw_effects(surface)
        self.assertEqual(lit(surface, 1), 0)
        boss.on_hazard_hit(DrainCircle(200, 500, 85, 1.0, 18))
        boss.draw_effects(surface)
        self.assertGreater(lit(surface, 1), 20)

    @needs_pygame
    def test_the_enrage_shockwave_uses_the_hot_colours(self):
        pictures = []
        for phase in (2, 3):
            boss = boss_in_phase(phase)
            boss.state, boss.state_time = "transition", 0.5
            surface = black_surface()
            boss._draw_transformation_rings(surface, int(boss.x), int(boss.y))
            pictures.append(pygame.image.tostring(surface, "RGB"))
        self.assertNotEqual(pictures[0], pictures[1])


PHASE_BOLTS = {phase: stats["bolts"] for phase, stats in PHASE_STATS.items()}


if __name__ == "__main__":
    unittest.main()
