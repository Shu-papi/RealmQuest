"""Checks for the playable Minotaur arena. Run from the repo root:  python -m unittest discover -s src/bosses/tests"""
import math
import os
import sys
import unittest

SRC_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

try:
    import pygame
except ImportError:
    from pygame_stub import install
    install()
    import pygame

REAL_PYGAME = hasattr(pygame, "get_sdl_version")
needs_pygame = unittest.skipUnless(REAL_PYGAME, "needs real pygame (pip install pygame-ce)")

DT = 1 / 60


def _arena(seed=1):
    from bosses.minotaur.arena import Arena
    return Arena(seed=seed)


def _run_intro(arena):
    from bosses.minotaur.arena import Inputs
    for _ in range(int(4 / DT)):
        arena.step(DT, Inputs(aim=(arena.boss.x, arena.boss.y)))
        if arena.boss.state != "intro":
            break


@needs_pygame
class ArenaTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pygame.init()
        cls.screen = pygame.display.set_mode((960, 640))

    def test_player_cannot_leave_the_floor(self):
        from bosses.minotaur.arena import BOUNDS, Inputs
        arena = _arena()
        for direction in ((-1, 0), (1, 0), (0, -1), (0, 1)):
            for _ in range(240):
                arena.step(DT, Inputs(move=direction, aim=(480, 300)))
            left, top, right, bottom = BOUNDS
            self.assertTrue(left <= arena.player.x <= right and top <= arena.player.y <= bottom)

    def test_sword_hurts_the_boss_only_when_in_range_and_not_during_intro(self):
        from bosses.minotaur.arena import Inputs
        arena = _arena()
        arena.player.x, arena.player.y = arena.boss.x, arena.boss.y + 90
        arena.step(DT, Inputs(aim=(arena.boss.x, arena.boss.y), attack=True))
        for _ in range(20):
            arena.step(DT, Inputs(aim=(arena.boss.x, arena.boss.y)))
        self.assertEqual(arena.boss.hp, arena.boss.max_hp, "he is invulnerable while he storms in")

        _run_intro(arena)
        arena.boss.state = "idle"
        arena.player.swing_cd = 0
        arena.player.x, arena.player.y = arena.boss.x, arena.boss.y + 90
        before = arena.boss.hp
        arena.step(DT, Inputs(aim=(arena.boss.x, arena.boss.y), attack=True))
        for _ in range(20):
            arena.step(DT, Inputs(aim=(arena.boss.x, arena.boss.y)))
        self.assertLess(arena.boss.hp, before)

        arena.player.x, arena.player.y = 100, 560                       # far away, swinging at nothing
        arena.player.swing_cd = 0
        before = arena.boss.hp
        arena.step(DT, Inputs(aim=(500, 300), attack=True))
        for _ in range(20):
            arena.step(DT, Inputs(aim=(500, 300)))
        self.assertEqual(arena.boss.hp, before)

    def test_roll_gives_invulnerability_and_has_a_cooldown(self):
        from bosses.minotaur.arena import Inputs
        arena = _arena()
        arena.step(DT, Inputs(move=(1, 0), roll=True))
        self.assertTrue(arena.player.rolling)
        self.assertEqual(arena.player.take_damage(30), 0)
        self.assertEqual(arena.player.hp, 100)
        for _ in range(int(0.5 / DT)):
            arena.step(DT, Inputs())
        self.assertFalse(arena.player.rolling)
        arena.step(DT, Inputs(roll=True))
        self.assertFalse(arena.player.rolling, "roll is still on cooldown")

    def test_hit_gives_brief_invulnerability(self):
        arena = _arena()
        self.assertEqual(arena.player.take_damage(20), 20)
        self.assertEqual(arena.player.take_damage(20), 0)
        self.assertEqual(arena.player.hp, 80)

    def test_dying_ends_the_fight_and_r_restart_resets_it(self):
        from bosses.minotaur.arena import Inputs
        arena = _arena()
        _run_intro(arena)
        arena.player.take_damage(10 ** 6)
        arena.step(DT, Inputs())
        self.assertEqual(arena.state, "lost")
        arena.restart(seed=2)
        self.assertEqual(arena.state, "fight")
        self.assertEqual(arena.player.hp, arena.player.max_hp)
        self.assertEqual(arena.boss.hp, arena.boss.max_hp)

    def test_killing_the_boss_wins_and_drops_loot_once(self):
        from bosses.minotaur.arena import Inputs
        arena = _arena()
        _run_intro(arena)
        arena.boss.state = "idle"
        arena.boss.take_damage(10 ** 6)
        for _ in range(int(8 / DT)):
            arena.step(DT, Inputs())
            if arena.state == "won":
                break
        self.assertEqual(arena.state, "won")
        self.assertTrue(arena.loot)
        loot = list(arena.loot)
        for _ in range(30):
            arena.step(DT, Inputs())
        self.assertEqual(arena.loot, loot)

    def test_bot_dodges_and_wins_a_full_fight(self):
        from bosses.minotaur.arena import bot_inputs
        for seed in (1, 2, 3):
            arena = _arena(seed)
            for _ in range(int(120 / DT)):
                arena.step(DT, bot_inputs(arena))
                if arena.state != "fight":
                    break
            self.assertEqual(arena.state, "won", f"bot lost on seed {seed}")

    def test_a_player_who_stands_still_gets_hurt(self):
        """Proves the boss's charges and slams really reach the arena's player."""
        from bosses.minotaur.arena import Inputs
        arena = _arena(1)
        for _ in range(int(60 / DT)):
            arena.step(DT, Inputs(aim=(arena.boss.x, arena.boss.y)))
            if arena.state != "fight":
                break
        self.assertEqual(arena.state, "lost")

    def test_every_screen_draws(self):
        from bosses.minotaur.arena import Inputs, bot_inputs
        font, big = pygame.font.Font(None, 26), pygame.font.Font(None, 110)
        arena = _arena(1)
        for second in range(30):
            for _ in range(60):
                arena.step(DT, bot_inputs(arena))
            arena.draw(self.screen, font, big)
            if arena.state != "fight":
                break
        arena.draw(self.screen, font, big)
        arena.state = "lost"
        arena.draw(self.screen, font, big)
        self.assertNotEqual(self.screen.get_at((480, 200))[:3], (0, 0, 0))


@needs_pygame
class CalloutTests(unittest.TestCase):
    def test_two_skill_labels_at_once_do_not_overlap(self):
        pygame.init()
        arena = _arena()
        boss = arena.boss
        boss.state = "slam_windup"
        arena.step(DT, __import__("bosses.minotaur.arena", fromlist=["Inputs"]).Inputs())
        boss.state = "transition"
        arena.step(DT, __import__("bosses.minotaur.arena", fromlist=["Inputs"]).Inputs())
        labels = [f for f in arena.floaters if f[5] == 40]
        self.assertEqual(len(labels), 2)
        self.assertGreaterEqual(abs(labels[0][2] - labels[1][2]), 40)


@needs_pygame
class IsoArenaTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pygame.init()
        cls.screen = pygame.display.set_mode((960, 640))

    @staticmethod
    def _iso_arena(seed=1):
        from bosses.minotaur.arena import Arena
        from bosses.minotaur.view import IsoView
        return Arena(seed=seed, view=IsoView())

    def test_the_fight_is_identical_in_both_views(self):
        """Only the drawing changes: same seed + same inputs = same fight, move for move."""
        from bosses.minotaur.arena import Arena, bot_inputs
        from bosses.minotaur.view import IsoView
        flat, iso = Arena(seed=3), Arena(seed=3, view=IsoView())
        for _ in range(int(25 / DT)):
            flat.step(DT, bot_inputs(flat))
            iso.step(DT, bot_inputs(iso))
        self.assertEqual((flat.boss.hp, flat.player.hp, flat.state), (iso.boss.hp, iso.player.hp, iso.state))
        self.assertAlmostEqual(flat.boss.x, iso.boss.x, places=6)
        self.assertAlmostEqual(flat.boss.y, iso.boss.y, places=6)
        self.assertEqual(flat.boss.last_attack, iso.boss.last_attack)

    def test_the_bot_wins_in_isometric_too(self):
        from bosses.minotaur.arena import bot_inputs
        for seed in (1, 2):
            arena = self._iso_arena(seed)
            for _ in range(int(120 / DT)):
                arena.step(DT, bot_inputs(arena))
                if arena.state != "fight":
                    break
            self.assertEqual(arena.state, "won", f"seed {seed}")

    def test_keys_move_the_player_along_the_screen(self):
        from bosses.minotaur.arena import Inputs
        arena = self._iso_arena()
        view = arena.view
        arena.player.x, arena.player.y = 480, 355
        start = view.project(arena.player.x, arena.player.y)
        for key, axis in (((1, 0), "right"), ((0, -1), "up")):
            arena.player.x, arena.player.y = 480, 355
            for _ in range(30):
                arena.step(DT, Inputs(move=view.to_world(*key), aim=(480, 355)))
            end = view.project(arena.player.x, arena.player.y)
            if axis == "right":
                self.assertGreater(end[0] - start[0], 20)
                self.assertAlmostEqual(end[1], start[1], delta=2)
            else:
                self.assertLess(end[1] - start[1], -10)
                self.assertAlmostEqual(end[0], start[0], delta=2)

    def test_the_mouse_aims_at_the_floor_spot_under_it(self):
        from bosses.minotaur.arena import Inputs
        arena = self._iso_arena()
        view = arena.view
        arena.player.x, arena.player.y = 300, 300
        target = (600.0, 420.0)
        screen_spot = view.project(*target)
        arena.step(DT, Inputs(aim=view.unproject(*screen_spot)))
        expected = math.atan2(target[1] - 300, target[0] - 300)
        self.assertAlmostEqual(arena.player.aim_angle, expected, places=2)

    def test_the_player_looks_left_or_right_on_screen(self):
        from bosses.minotaur.arena import Inputs
        arena = self._iso_arena()
        view = arena.view
        arena.player.x, arena.player.y = 480, 355
        for screen_target, expected in (((900, 330), 1), ((60, 330), -1)):
            arena.step(DT, Inputs(aim=view.unproject(*screen_target)))
            self.assertEqual(arena.player.facing, expected)

    def test_hit_effects_appear_on_the_boss_on_screen(self):
        from bosses.minotaur.arena import Inputs
        arena = self._iso_arena()
        view = arena.view
        for _ in range(int(2.3 / DT)):
            arena.step(DT, Inputs())
        arena.boss.state = "idle"
        arena.boss.x, arena.boss.y = 480, 355
        arena.player.x, arena.player.y = 480, 440
        arena.player.swing_cd = 0
        arena.step(DT, Inputs(aim=(480, 355), attack=True))
        for _ in range(8):
            arena.step(DT, Inputs(aim=(480, 355)))
        self.assertTrue(arena.floaters)
        fx, fy = arena.floaters[0][1], arena.floaters[0][2]
        bx, by = view.project(480, 355)
        self.assertLess(math.hypot(fx - bx, fy - by), 220, "the damage number is next to him on SCREEN, not at his floor coordinates")

    def test_every_screen_draws_in_isometric(self):
        from bosses.minotaur.arena import bot_inputs
        font, big = pygame.font.Font(None, 26), pygame.font.Font(None, 110)
        arena = self._iso_arena(4)
        for second in range(26):
            for _ in range(60):
                arena.step(DT, bot_inputs(arena))
            arena.draw(self.screen, font, big)
            if arena.state != "fight":
                break
        for state in ("won", "lost"):
            arena.state = state
            arena.draw(self.screen, font, big)
        self.assertNotEqual(self.screen.get_at((480, 300))[:3], (0, 0, 0))

    def test_ground_circles_are_drawn_flat_on_the_isometric_floor(self):
        """A slam circle must show up as a 2:1 ellipse around its floor spot."""
        from bosses.minotaur.arena import Inputs
        arena = self._iso_arena(2)
        font, big = pygame.font.Font(None, 26), pygame.font.Font(None, 110)
        for _ in range(int(2.3 / DT)):
            arena.step(DT, Inputs())
        arena.boss.set_state("idle")
        arena.boss.x, arena.boss.y = 480, 300
        arena.player.x, arena.player.y = 480, 560
        arena.draw(self.screen, font, big)
        before = pygame.image.tobytes(self.screen, "RGB")
        arena.boss._start_slam()
        arena.boss.state_time = 0.5
        arena.draw(self.screen, font, big)
        after = pygame.image.tobytes(self.screen, "RGB")
        self.assertNotEqual(before, after)
        # the ring's left and right ends are about twice as far from the centre as its top and bottom
        cx, cy = arena.view.project(480, 340)
        radius = arena.boss.stats["slam_radius"]
        half_width = radius * arena.view.k * math.sqrt(2)
        orange = lambda c: c[0] > 200 and 120 < c[1] < 190 and c[2] < 140
        right_end = any(orange(self.screen.get_at((int(cx + half_width + dx), int(cy + dy)))[:3])
                        for dx in range(-6, 7) for dy in range(-6, 7))
        top_end_if_circle = any(orange(self.screen.get_at((int(cx + dx), int(cy - half_width + dy)))[:3])
                                for dx in range(-6, 7) for dy in range(-6, 7))
        self.assertTrue(right_end, "the circle reaches out sideways")
        self.assertFalse(top_end_if_circle, "...but is squashed vertically (it is not a round circle on screen)")


if __name__ == "__main__":
    unittest.main()
