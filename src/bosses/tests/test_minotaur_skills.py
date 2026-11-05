"""Checks for the Minotaur's roar / rocks / leap skills, his moods and his animation."""
import os as _os; _os.environ["REALMQUEST_BALANCE"] = "none"      # these tests pin the code's DEFAULT numbers, not your config/ tuning
import math
import os
import shutil
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

from bosses import Minotaur
from bosses.minotaur.art import ASSET_DIR, MinotaurArt, POSE_FILES, check_assets
from bosses.minotaur.boss import PHASE_STATS, SKILLS
from bosses.minotaur.shockwave import RockFall

DT = 1 / 60
BOUNDS = (40, 110, 920, 600)
REAL_PYGAME = hasattr(pygame, "get_sdl_version")
needs_pygame = unittest.skipUnless(REAL_PYGAME, "needs real pygame (pip install pygame-ce)")

ALL_STATES = ("intro", "idle", "charge_windup", "charge", "stunned", "slam_windup", "recover",
              "cast_windup", "rain_windup", "leap_windup", "leap", "transition", "dying", "dead")


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


def ready_boss(seed=1, phase=1):
    boss = Minotaur(seed=seed)
    advance(boss, StubPlayer(), Minotaur.INTRO_TIME + 0.1)
    if phase == 2:
        boss.take_damage(150)
        advance(boss, StubPlayer(), boss.TRANSITION_TIME + 0.1)
    return boss


class TestNewSkills(unittest.TestCase):
    # ---------- roar: ring of fireballs ----------

    def test_roar_has_a_warning_then_fires_an_even_ring(self):
        for phase in (1, 2):
            boss = ready_boss(phase=phase)
            far = StubPlayer(x=900, y=590)
            boss._start_attack("cast")
            self.assertEqual(boss.state, "cast_windup")
            advance(boss, far, PHASE_STATS[phase]["cast_windup"] * 0.8)
            self.assertEqual(boss.projectiles, [], "no fireballs during the warning")
            advance(boss, far, PHASE_STATS[phase]["cast_windup"] * 0.5)
            rings = 1 if phase == 1 else 2
            self.assertEqual(len(boss.projectiles), PHASE_STATS[phase]["volley"] * rings)
            angles = sorted(round(shot.angle % math.tau, 3) for shot in boss.projectiles[:PHASE_STATS[phase]["volley"]])
            gaps = {round(b - a, 2) for a, b in zip(angles, angles[1:])}
            self.assertEqual(len(gaps), 1, "the ring is evenly spaced, so the gaps are fair")

    # ---------- rocks ----------

    def test_rocks_always_target_the_player_and_telegraph_first(self):
        boss = ready_boss()
        player = StubPlayer(x=480, y=500)
        boss.update(DT, player, BOUNDS)                       # he notes where the player stands
        boss._start_attack("rain")
        rocks = [h for h in boss.hazards if isinstance(h, RockFall)]
        self.assertEqual(len(rocks), PHASE_STATS[1]["rain_count"])
        self.assertEqual((rocks[0].x, rocks[0].y), (480, 500), "the first boulder lands on the player")
        advance(boss, player, PHASE_STATS[1]["rain_windup"] * 0.8)
        self.assertEqual(player.damage_taken, 0, "nothing lands during the warning")
        advance(boss, player, 2.0)
        self.assertGreaterEqual(player.damage_taken, PHASE_STATS[1]["rain_damage"])

    def test_rocks_miss_a_player_who_keeps_moving(self):
        boss = ready_boss()
        player = StubPlayer(x=480, y=500)
        boss.update(DT, player, BOUNDS)
        boss._start_attack("rain")
        safe = None
        for x in range(60, 900, 20):
            for y in range(130, 590, 20):
                if all(math.hypot(x - h.x, y - h.y) > h.radius + 20 for h in boss.hazards):
                    safe = (x, y)
        self.assertIsNotNone(safe, "there is always somewhere safe to stand")
        player.rect.center = safe
        advance(boss, player, 3.0)
        self.assertEqual(player.damage_taken, 0)

    def test_rocks_stay_inside_the_arena(self):
        for seed in range(10):
            boss = ready_boss(seed=seed, phase=2)
            boss._start_attack("rain")
            for rock in boss.hazards:
                self.assertTrue(BOUNDS[0] <= rock.x <= BOUNDS[2] and BOUNDS[1] <= rock.y <= BOUNDS[3])

    # ---------- leap ----------

    def test_leap_is_untouchable_in_the_air_and_lands_on_the_player(self):
        boss = ready_boss()
        player = StubPlayer(x=700, y=480)
        boss.update(DT, player, BOUNDS)
        boss._start_attack("leap")
        self.assertEqual(boss.state, "leap_windup")
        start = (boss.x, boss.y)
        advance(boss, player, PHASE_STATS[1]["leap_windup"] * 1.12 + 0.05)
        self.assertEqual(boss.state, "leap")
        self.assertEqual(boss.take_damage(50), 0, "can't be hurt while airborne")
        self.assertEqual(len(boss.hazards), 1, "the landing circle is shown during the jump")
        advance(boss, player, PHASE_STATS[1]["leap_time"] + 0.05)
        self.assertNotEqual((round(boss.x), round(boss.y)), (round(start[0]), round(start[1])))
        self.assertAlmostEqual(boss.x, 700, delta=2)
        self.assertEqual(player.damage_taken, PHASE_STATS[1]["leap_damage"])

    def test_leap_misses_a_player_who_runs_away(self):
        boss = ready_boss()
        player = StubPlayer(x=480, y=500)
        boss.update(DT, player, BOUNDS)
        boss._start_attack("leap")
        advance(boss, player, PHASE_STATS[1]["leap_windup"] * 1.12 + 0.1)
        player.rect.center = (100, 200)
        advance(boss, player, PHASE_STATS[1]["leap_time"] + 0.5)
        self.assertEqual(player.damage_taken, 0)

    def test_leap_never_leaves_the_arena(self):
        boss = ready_boss()
        player = StubPlayer(x=2000, y=-500)                   # nonsense position far outside
        boss.update(DT, player, BOUNDS)
        boss._start_attack("leap")
        advance(boss, player, 3.0)
        self.assertTrue(BOUNDS[0] + boss.radius - 1 <= boss.x <= BOUNDS[2] - boss.radius + 1)
        self.assertTrue(BOUNDS[1] + boss.radius - 1 <= boss.y <= BOUNDS[3] - boss.radius + 1)

    def test_every_new_skill_ends_and_returns_to_idle(self):
        for name in ("cast", "rain", "leap"):
            boss = ready_boss()
            boss._start_attack(name)
            seen = []
            for _ in range(int(4.0 / DT)):
                boss.update(DT, StubPlayer(), BOUNDS)
                if not seen or seen[-1] != boss.state:
                    seen.append(boss.state)
                if boss.state == "idle":
                    break
            self.assertEqual(seen[-1], "idle", f"{name}: {seen}")
            self.assertIn("recover", seen, f"{name} should end with a recovery")

    def test_phase_change_clears_the_new_hazards(self):
        boss = ready_boss()
        boss._start_attack("rain")
        boss.take_damage(150)
        self.assertEqual(boss.hazards, [])
        self.assertEqual(boss.state, "transition")


class TestRandomness(unittest.TestCase):
    def test_skill_choice_is_varied_and_never_three_in_a_row(self):
        boss = ready_boss(seed=5)
        history = []
        for _ in range(400):
            name = boss._pick_attack(300)
            boss._start_attack(name)
            history.append(name)
        self.assertEqual(set(history), set(SKILLS), "every skill gets used")
        for i in range(2, len(history)):
            self.assertFalse(history[i] == history[i - 1] == history[i - 2])

    def test_skill_choice_depends_on_distance(self):
        near = {name: 0 for name in SKILLS}
        far = {name: 0 for name in SKILLS}
        for seed in range(200):
            boss = ready_boss(seed=seed)
            near[boss._pick_attack(80)] += 1
            far[boss._pick_attack(500)] += 1
        self.assertGreater(near["slam"], near["charge"])
        self.assertGreater(far["charge"], far["slam"])

    def test_different_seeds_give_different_fights(self):
        orders = set()
        for seed in range(12):
            boss = ready_boss(seed=seed)
            order = []
            for _ in range(6):
                name = boss._pick_attack(300)
                boss._start_attack(name)
                order.append(name)
            orders.add(tuple(order))
        self.assertGreater(len(orders), 6)

    def test_idle_moods_vary(self):
        boss = ready_boss(seed=2)
        moods = set()
        for _ in range(80):
            boss._go_idle(1.0)
            moods.add(boss.idle_mode)
        self.assertEqual(moods, {"chase", "strafe", "taunt"})

    def test_idle_wait_time_is_randomised_a_little(self):
        boss = ready_boss(seed=3)
        waits = set()
        for _ in range(30):
            boss._go_idle(1.0)
            waits.add(round(boss.cooldown, 3))
            self.assertTrue(0.79 <= boss.cooldown <= 1.21)
        self.assertGreater(len(waits), 10)

    def test_strafing_circles_the_player_instead_of_charging_in(self):
        boss = ready_boss(seed=4)
        player = StubPlayer(x=480, y=500)
        boss.x, boss.y = 480, 300
        boss._go_idle(99)
        boss.idle_mode, boss.strafe_dir = "strafe", 1
        start_angle = math.atan2(boss.y - 500, boss.x - 480)
        advance(boss, player, 1.0)
        angle = math.atan2(boss.y - 500, boss.x - 480)
        self.assertNotAlmostEqual(angle, start_angle, places=1)

    def test_the_new_randomness_does_not_change_the_damage_numbers(self):
        for phase in (1, 2):
            self.assertEqual(PHASE_STATS[phase]["charge_damage"], 20 if phase == 1 else 24)
            self.assertEqual(PHASE_STATS[phase]["slam_damage"], 16 if phase == 1 else 20)


class TestLooks(unittest.TestCase):
    def test_he_turns_to_face_the_player(self):
        boss = ready_boss()
        boss.x, boss.y = 480, 300
        boss.update(DT, StubPlayer(x=800, y=300), BOUNDS)
        self.assertEqual(boss.facing, 1)
        boss.update(DT, StubPlayer(x=100, y=300), BOUNDS)
        self.assertEqual(boss.facing, -1)

    def test_every_state_has_a_complete_animation(self):
        boss = ready_boss()
        for state in ALL_STATES:
            boss.set_state(state)
            boss.state_time = 0.3
            anim = boss._animation()
            for key in ("pose", "angle", "sx", "sy", "lift", "shift", "hem", "shadow", "bob", "speed"):
                self.assertIn(key, anim, f"{state} is missing {key}")
            self.assertTrue(0.5 < anim["sx"] < 1.5 and 0.5 < anim["sy"] < 1.5, state)
            self.assertTrue(anim["pose"] in (None, "raise", "cast") or str(anim["pose"]).startswith("walk"), state)
            self.assertIn(anim["back"], (True, False), state)

    def test_attacks_use_poses_and_the_leap_leaves_the_ground(self):
        boss = ready_boss()
        for state, pose in (("slam_windup", "raise"), ("cast_windup", "cast"), ("rain_windup", "raise"), ("transition", "cast")):
            boss.set_state(state)
            boss.state_time = 0.3
            self.assertEqual(boss._animation()["pose"], pose, state)
        boss.set_state("leap")
        boss.state_time = PHASE_STATS[1]["leap_time"] / 2
        self.assertGreater(boss._animation()["lift"], 10)
        self.assertLess(boss._animation()["shadow"], 0.7)

    def test_death_animation_topples_him_over(self):
        boss = ready_boss()
        boss.set_state("dying")
        boss.state_time = 0.1
        early = abs(boss._animation()["angle"])
        boss.state_time = boss.DYING_TIME * 0.8
        self.assertGreater(abs(boss._animation()["angle"]), 60)
        self.assertLess(early, 10)

    def test_dust_and_after_images_appear_and_clean_themselves_up(self):
        boss = ready_boss()
        player = StubPlayer(x=480, y=520)
        boss._start_attack("charge")
        advance(boss, player, 1.3)
        self.assertTrue(boss.fx or boss.trail)
        advance(boss, player, 6.0)
        self.assertLess(len(boss.fx), 160)
        self.assertLess(len(boss.trail), 7)


@needs_pygame
class TestPosesAndDrawing(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pygame.init()
        cls.surface = pygame.Surface((960, 640))

    def test_pose_files_ship_and_pass_the_checker(self):
        for name in POSE_FILES.values():
            self.assertTrue(os.path.exists(os.path.join(ASSET_DIR, name)), name)
        errors, warnings = check_assets()
        self.assertEqual((errors, warnings), ([], []))

    def test_art_accepts_every_pose_flip_lean_and_squash(self):
        art = MinotaurArt()
        for phase in (1, 2):
            for pose in (None, "raise", "cast"):
                for flip in (False, True):
                    self.assertTrue(art.draw(self.surface, 480, 300, phase=phase, pose=pose, flip=flip,
                                             angle=-40, sx=1.1, sy=0.85, lift=6, shift=(1, -1), hem=1))
        self.assertTrue(art.draw(self.surface, 480, 300, angle=86))

    def test_leaning_and_squashing_keep_his_feet_where_they_were(self):
        """A marker pixel at the pivot must stay at the reported pivot after any lean or squash."""
        for angle in (-60, -17.5, 0, 9, 33, 86):
            for sx, sy in ((1.0, 1.0), (1.15, 0.8), (0.9, 1.12)):
                image = pygame.Surface((200, 240), pygame.SRCALPHA)
                image.fill((255, 255, 255, 255))
                pygame.draw.rect(image, (255, 0, 0, 255), (96, 200, 8, 8))          # the marker, pivot = its centre
                out, px, py = MinotaurArt._transform(image, 100, 204, sx, sy, angle)
                width, height = out.get_size()
                self.assertTrue(0 <= px < width and 0 <= py < height, (angle, sx, sy))
                found = [(x, y) for x in range(width) for y in range(height)
                         if out.get_at((x, y))[:3] == (255, 0, 0) and out.get_at((x, y))[3] > 0]
                self.assertTrue(found, f"marker lost at {angle}, {sx}, {sy}")
                mx = sum(x for x, _ in found) / len(found)
                my = sum(y for _, y in found) / len(found)
                self.assertAlmostEqual(mx, px, delta=4.5)
                self.assertAlmostEqual(my, py, delta=4.5)

    def test_faces_setting_mirrors_the_art_for_sprites_that_look_right(self):
        art_left, art_right = MinotaurArt(), MinotaurArt()
        art_left.draw(self.surface, 480, 300)
        art_right.draw(self.surface, 480, 300)
        art_right.config["faces"] = "right"
        a, b = pygame.Surface((300, 300)), pygame.Surface((300, 300))
        art_left.draw(a, 150, 150, flip=True, bob=False)
        art_right.draw(b, 150, 150, flip=False, bob=False)
        self.assertEqual(pygame.image.tobytes(a, "RGB"), pygame.image.tobytes(b, "RGB"))

    def test_missing_pose_files_fall_back_to_the_body_frame(self):
        with tempfile.TemporaryDirectory() as folder:
            shutil.copy(os.path.join(ASSET_DIR, "body_phase1_a.png"), folder)
            art = MinotaurArt(folder=folder)
            self.assertTrue(art.draw(self.surface, 480, 300, pose="raise"))
            self.assertTrue(art.draw(self.surface, 480, 300, pose="cast", phase=2))

    def test_a_wrong_sized_pose_is_reported_and_ignored(self):
        with tempfile.TemporaryDirectory() as folder:
            for name in os.listdir(ASSET_DIR):
                if name.endswith((".png", ".json")):
                    shutil.copy(os.path.join(ASSET_DIR, name), folder)
            pygame.image.save(pygame.Surface((10, 10), pygame.SRCALPHA), os.path.join(folder, "pose_raise_phase1.png"))
            errors, _ = check_assets(folder)
            self.assertTrue(any("same size" in e for e in errors), errors)
            art = MinotaurArt(folder=folder)
            self.assertTrue(art.draw(self.surface, 480, 300, pose="raise"), "still draws using the body frame")

    def test_boss_draws_every_state_with_the_real_art_and_effects(self):
        boss = ready_boss()
        boss._start_attack("rain")
        boss.fx = [[300, 300, 0, 0, 0.1, 0.5, (150, 134, 120), 8]]
        for phase in (1, 2):
            boss.phase = phase
            for state in ALL_STATES:
                boss.set_state(state)
                boss.state_time = 0.4
                boss.trail = [dict(boss._current_pose(), x=boss.x, y=boss.y, age=0.05)]
                boss.draw(self.surface)
        boss.hit_flash = 0.1
        boss.draw(self.surface)


class TestSmoothness(unittest.TestCase):
    """The animation must glide: no value may jump between two frames, whatever he is doing."""

    LIMITS = {"angle": 4.0, "sx": 0.25, "sy": 0.08, "lift": 3.0, "shift": 1.8, "shadow": 0.08}

    @staticmethod
    def _values(boss):
        p = boss._current_pose()
        return {"angle": p["angle"], "sx": p["sx"], "sy": p["sy"], "lift": p["lift"],
                "shiftx": p["shift"][0], "shifty": p["shift"][1], "shadow": p["shadow"]}

    def test_no_animation_value_jumps_between_frames_in_whole_fights(self):
        from bosses.minotaur.view import IsoView, TopDownView
        for seed, view in [(seed, TopDownView() if seed % 2 else IsoView()) for seed in range(1, 9)]:
            for phase in (1, 2):
                boss = ready_boss(seed=seed, phase=phase)
                boss.view = view
                player = StubPlayer(x=300 + seed * 60, y=480)
                previous = self._values(boss)
                for frame in range(int(35 / DT)):
                    if frame % 120 == 0:                          # the player wanders so he turns around a lot
                        player.rect.center = (100 + (frame * 7) % 800, 200 + (frame * 3) % 380)
                    boss.update(DT, player, BOUNDS)
                    if boss.state in ("dying", "dead"):
                        break
                    now = self._values(boss)
                    for key, value in now.items():
                        limit = self.LIMITS.get(key.replace("shiftx", "shift").replace("shifty", "shift"))
                        self.assertLessEqual(abs(value - previous[key]), limit,
                                             f"{key} jumped in state {boss.state} (seed {seed}, phase {phase})")
                    previous = now

    def test_springs_stay_stable_even_with_a_terrible_frame_rate(self):
        for dt in (1 / 15, 1 / 8, 1 / 4):
            boss = ready_boss(seed=3)
            player = StubPlayer()
            for _ in range(int(40 / dt)):
                boss.update(dt, player, BOUNDS)
                values = self._values(boss)
                for key, value in values.items():
                    self.assertTrue(math.isfinite(value), key)
                self.assertLess(abs(values["angle"]), 100)
                self.assertTrue(0.2 < values["sx"] < 2.0 and 0.2 < values["sy"] < 2.0)

    def test_the_landing_springs_and_settles_instead_of_snapping(self):
        boss = ready_boss(seed=2)
        boss._start_attack("slam")
        player = StubPlayer(x=900, y=590)
        advance(boss, player, PHASE_STATS[1]["slam_windup"] - 0.05)
        squash = [boss._current_pose()["sy"]]
        for _ in range(int(1.2 / DT)):
            boss.update(DT, player, BOUNDS)
            squash.append(boss._current_pose()["sy"])
        self.assertLess(min(squash), 0.95, "he squashes when he lands")
        self.assertGreater(max(squash), 1.0, "and the spring rebounds past normal")
        steps = [abs(b - a) for a, b in zip(squash, squash[1:])]
        self.assertLess(max(steps), self.LIMITS["sy"], "the squash happens over several frames, never in one")
        self.assertAlmostEqual(squash[-1], 1.0, delta=0.06)

    def test_poses_fade_into_each_other(self):
        boss = ready_boss()
        boss._go_idle(99)
        boss.idle_mode, boss.taunt = "taunt", "snort"        # a mood with a neutral pose
        advance(boss, StubPlayer(), 0.5)
        self.assertIsNone(boss._current_pose()["fade_to"])
        boss._start_attack("slam")
        mixes = []
        for _ in range(int(0.3 / DT)):
            boss.update(DT, StubPlayer(), BOUNDS)
            pose = boss._current_pose()
            mixes.append((pose["fade_to"], pose["fade_mix"]))
        self.assertTrue(any(0.05 < m < 0.95 and fade == ("raise", False) for fade, m in mixes), "a visible mid-fade")
        self.assertEqual(boss._current_pose()["pose"], "raise")
        self.assertIsNone(boss._current_pose()["fade_to"])
        values = [m for fade, m in mixes if fade]
        self.assertEqual(values, sorted(values), "the fade only goes forwards")

    def test_poses_also_fade_back_to_normal_instead_of_snapping(self):
        """Going from arms-up back to standing used to be a hard switch at the end of the fade."""
        boss = ready_boss(seed=2)
        boss._start_attack("slam")
        player = StubPlayer(x=900, y=590)
        advance(boss, player, PHASE_STATS[1]["slam_windup"] - 0.02)
        self.assertEqual(boss._current_pose()["pose"], "raise")
        saw_fade_to_standing = False
        for _ in range(int(1.5 / DT)):
            boss.update(DT, player, BOUNDS)
            pose = boss._current_pose()
            if pose["fade_to"] == (None, False) and 0.05 < pose["fade_mix"] < 0.95:
                saw_fade_to_standing = True
        self.assertTrue(saw_fade_to_standing)

    def test_turning_around_squeezes_then_flips_exactly_once(self):
        boss = ready_boss()
        boss.x, boss.y = 480, 300
        boss._go_idle(99)
        left, right = StubPlayer(x=100, y=300), StubPlayer(x=860, y=300)
        advance(boss, left, 0.5)
        self.assertFalse(boss._current_pose()["flip"])
        flips, widths = [], []
        for _ in range(int(0.6 / DT)):
            boss.update(DT, right, BOUNDS)
            pose = boss._current_pose()
            flips.append(pose["flip"])
            widths.append(pose["sx"])
        changes = sum(1 for a, b in zip(flips, flips[1:]) if a != b)
        self.assertEqual(changes, 1)
        self.assertTrue(flips[-1])
        self.assertLess(min(widths), 0.5, "he narrows while turning...")
        self.assertGreater(min(widths), 0.2, "...but never to a paper-thin sliver")
        self.assertAlmostEqual(widths[-1], 1.0, delta=0.1)

    def test_walking_fades_in_and_out(self):
        boss = ready_boss()
        boss._go_idle(99)
        boss.idle_mode = "chase"
        boss.x, boss.y = 480, 200
        advance(boss, StubPlayer(x=480, y=560), 1.5)
        self.assertGreater(boss.walk, 0.9)
        boss.idle_mode = "taunt"
        previous = boss.walk
        for _ in range(int(1.0 / DT)):
            boss.update(DT, StubPlayer(x=480, y=560), BOUNDS)
            self.assertLessEqual(boss.walk, previous + 1e-9)
            previous = boss.walk
        self.assertLess(boss.walk, 0.1)


class TestTopDownEffects(unittest.TestCase):
    """Skill, damage and other effects are drawn as seen from ABOVE: flat circles, no gravity, no 'up'."""

    @staticmethod
    def _spread(boss):
        xs = [p[0] for p in boss.fx]
        ys = [p[1] for p in boss.fx]
        return max(xs) - min(xs), max(ys) - min(ys)

    def test_dust_rings_are_true_circles_from_above(self):
        boss = ready_boss()
        boss.fx = []
        boss._dust_ring(500, 400, 120, 32)
        width, height = self._spread(boss)
        self.assertAlmostEqual(width / height, 1.0, delta=0.08)
        speeds = [(abs(p[2]), abs(p[3])) for p in boss.fx]
        self.assertAlmostEqual(max(v[0] for v in speeds), max(v[1] for v in speeds), delta=10)

    def test_the_isometric_room_still_squashes_them_to_ovals(self):
        from bosses.minotaur.view import IsoView
        boss = ready_boss()
        boss.view = IsoView()
        boss.fx = []
        boss._dust_ring(500, 400, 120, 32)
        width, height = self._spread(boss)
        self.assertAlmostEqual(height / width, 0.5, delta=0.08)

    def test_bursts_spread_evenly_in_every_direction(self):
        boss = ready_boss()
        boss.fx = []
        boss._burst(500, 400, 400, (255, 255, 255), speed=200)
        mean_vx = sum(p[2] for p in boss.fx) / len(boss.fx)
        mean_vy = sum(p[3] for p in boss.fx) / len(boss.fx)
        self.assertLess(abs(mean_vx), 12)
        self.assertLess(abs(mean_vy), 12, "nothing is thrown 'up': seen from above every direction is the same")
        spread_x = max(abs(p[2]) for p in boss.fx)
        spread_y = max(abs(p[3]) for p in boss.fx)
        self.assertAlmostEqual(spread_x, spread_y, delta=15)

    def test_particles_have_no_gravity_from_above(self):
        """A perfectly symmetric ring of particles: the only way its centre can move is gravity."""
        for iso, should_fall in ((False, False), (True, True)):
            boss = ready_boss()
            boss.set_state("dead")                      # a state that spawns no dust of its own
            if iso:
                from bosses.minotaur.view import IsoView
                boss.view = IsoView()
            boss.fx = [[500, 400, math.cos(a) * 120, math.sin(a) * 120, 0.0, 3.0, (255, 255, 255), 8]
                       for a in [math.tau * i / 64 for i in range(64)]]
            for _ in range(int(0.4 / DT)):
                boss._update_looks(DT)
            mean_y = sum(p[1] for p in boss.fx) / len(boss.fx)
            if should_fall:
                self.assertGreater(mean_y, 405, "in the isometric room things fall back down")
            else:
                self.assertAlmostEqual(mean_y, 400, delta=0.01, msg="from above they do not drift downwards")

    def test_stun_stars_circle_his_head_in_a_true_circle(self):
        boss = ready_boss()
        boss.set_state("stunned")
        rx, ry = boss._ref()
        xs, ys = [], []
        for step in range(60):
            boss.clock = step * 0.1
            for x, y in boss.star_positions():
                xs.append(x - rx)
                ys.append(y - (ry - 100))
                self.assertAlmostEqual(math.hypot(x - rx, y - (ry - 100)), 46, delta=0.01)
        self.assertAlmostEqual(max(xs) - min(xs), max(ys) - min(ys), delta=2)

    def test_ember_gather_and_rocks_stay_inside_the_arena_circle_shapes(self):
        boss = ready_boss()
        boss.fx = []
        boss.set_state("cast_windup")
        for _ in range(int(0.9 / DT)):
            boss.update(DT, StubPlayer(), BOUNDS)
        rx, ry = boss._ref()
        spawned = [p for p in boss.fx if p[6] == (255, 176, 80)]
        self.assertTrue(spawned)
        ratios = [abs(p[3]) / max(1.0, abs(p[2])) for p in spawned if abs(p[2]) > 30]
        self.assertTrue(ratios)


@needs_pygame
class TestTopDownBoulders(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pygame.init()

    @staticmethod
    def _box(rock, view=None):
        surface = pygame.Surface((960, 640))
        surface.fill((30, 30, 30))
        rock.draw_air(surface, view)
        mask = pygame.mask.from_threshold(surface, (30, 30, 30), (4, 4, 4, 255))
        mask.invert()
        rects = mask.get_bounding_rects()
        if not rects:
            return None
        left = min(r.left for r in rects)
        right = max(r.right for r in rects)
        top = min(r.top for r in rects)
        bottom = max(r.bottom for r in rects)
        return left, top, right, bottom

    def test_the_boulder_lands_on_its_spot_and_shrinks_as_it_falls(self):
        from bosses.minotaur.shockwave import RockFall
        rock = RockFall(400, 300, 60, 1.0, 14)
        sizes = []
        for t in (0.02, 0.4, 0.8, 0.98):
            rock.timer = t
            box = self._box(rock)
            sizes.append(box[2] - box[0])
            self.assertAlmostEqual((box[1] + box[3]) / 2, 300, delta=22, msg="no 'falling from above' offset on screen")
            self.assertAlmostEqual((box[0] + box[2]) / 2, 400, delta=22)
        self.assertEqual(sizes, sorted(sizes, reverse=True), "it gets smaller as it gets closer to the floor")
        self.assertGreater(sizes[0], 1.8 * sizes[-1])

    def test_the_isometric_room_still_drops_it_down_the_screen(self):
        from bosses.minotaur.shockwave import RockFall
        from bosses.minotaur.view import IsoView
        rock = RockFall(400, 300, 60, 1.0, 14)
        rock.timer = 0.5                                    # halfway down (at the very start it is above the top of the screen)
        box = self._box(rock, IsoView())
        self.assertIsNotNone(box)
        self.assertLess((box[1] + box[3]) / 2, IsoView().project(400, 300)[1] - 60, "it is high above its spot on screen")

    def test_flying_chips_make_a_flat_circle(self):
        from bosses.minotaur.shockwave import RockFall
        rock = RockFall(400, 300, 100, 0.5, 14)
        rock.state, rock.timer = "burst", 0.25
        box = self._box(rock)
        self.assertAlmostEqual((box[2] - box[0]) / (box[3] - box[1]), 1.0, delta=0.2)


@needs_pygame
class TestTopDownSparks(unittest.TestCase):
    def test_hit_sparks_fly_out_flat_and_do_not_fall(self):
        """Sparks are thrown in exact opposite pairs, so only an upward kick or gravity could move their centre."""
        import random
        from unittest import mock
        from bosses.minotaur.arena import Arena, Inputs
        from bosses.minotaur.view import IsoView
        calls = {"n": 0}

        def pairs(a, b):
            if abs(b - math.tau) < 1e-9:                        # an angle
                k = calls["n"]
                calls["n"] += 1
                return 0.3 + (k // 2) * 0.9 + (k % 2) * math.pi
            return (a + b) / 2                                    # a speed

        def hit(view):
            calls["n"] = 0
            arena = Arena(seed=1, view=view)
            for _ in range(int(2.3 / DT)):
                arena.step(DT, Inputs())
            arena.boss.state = "idle"
            arena.boss.x, arena.boss.y = 480, 300
            arena.player.x, arena.player.y = 480, 390
            arena.player.swing_cd = 0
            with mock.patch.object(random, "uniform", side_effect=pairs):
                arena.step(DT, Inputs(aim=(480, 300), attack=True))
                for _ in range(6):
                    arena.step(DT, Inputs(aim=(480, 300)))
            return arena

        flat = hit(None)
        self.assertGreaterEqual(len(flat.sparks), 4)
        mean_vy = sum(s[3] for s in flat.sparks) / len(flat.sparks)
        self.assertAlmostEqual(mean_vy, 0, delta=1e-6, msg="no upward kick: seen from above every direction is the same")
        centre_before = sum(s[1] for s in flat.sparks) / len(flat.sparks)
        for _ in range(8):
            flat._update_effects(DT)
        centre_after = sum(s[1] for s in flat.sparks) / len(flat.sparks)
        self.assertAlmostEqual(centre_after, centre_before, delta=0.01, msg="no gravity: they do not arc downwards")

        iso = hit(IsoView())
        self.assertLess(sum(s[3] for s in iso.sparks) / len(iso.sparks), -10, "the isometric room still kicks them upwards (and gravity pulls them back)")


if __name__ == "__main__":
    unittest.main()
