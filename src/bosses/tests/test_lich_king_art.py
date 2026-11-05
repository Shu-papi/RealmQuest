"""Run from the repo root:  python -m unittest discover -s src/bosses/tests"""
import json
import os
import shutil
import tempfile
import unittest

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
from bosses.lich_king import art
from bosses.dev.arena import BOUNDS

DT = 1 / 60
CLASSIC = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixtures", "classic_lich_king")
EXPECTED_POSES = {"idle": 4, "volley": 3, "drain": 2, "summon": 3, "recover": 2, "hurt": 1, "roar": 2,
                  "nova": 3, "grasp": 2}
# The fake pygame used on machines without pygame cannot load or scale images.
REAL_PYGAME = hasattr(pygame, "get_sdl_version")
needs_pygame = unittest.skipUnless(REAL_PYGAME, "needs real pygame (pip install pygame)")


class StubPlayer:
    def __init__(self):
        self.rect = pygame.Rect(0, 0, 28, 28)
        self.rect.center = (480, 500)

    def take_damage(self, amount):
        return amount


@needs_pygame
class TestSpriteFiles(unittest.TestCase):
    """The PNG files in assets/bosses/lich_king/ are what the game draws."""

    def setUp(self):
        self.sheet = art.SpriteSheet(art.ASSET_DIR)

    def test_shipped_sprites_pass_the_checker(self):
        errors, warnings = art.check_assets()
        self.assertEqual(errors, [])
        self.assertEqual(warnings, [])

    def test_shipped_art_uses_pose_strips(self):
        self.assertTrue(art.uses_strips(art.ASSET_DIR))

    def test_every_pose_has_the_expected_number_of_frames_in_both_phases(self):
        for phase in (1, 2):
            for pose, count in EXPECTED_POSES.items():
                self.assertEqual(len(self.sheet.poses[phase][pose]), count, (phase, pose))

    def test_every_frame_has_the_canvas_size_from_sprite_json(self):
        size = tuple(self.sheet.config["frame_size"])
        for phase in (1, 2):
            for frames in self.sheet.poses[phase].values():
                for frame in frames:
                    self.assertEqual(frame.size, size)

    def test_glow_markers_are_found_in_every_frame(self):
        for phase in (1, 2):
            for pose, frames in self.sheet.poses[phase].items():
                for i, frame in enumerate(frames):
                    where = (phase, pose, i)
                    self.assertGreaterEqual(len(frame.markers["eye"]), 2, where)
                    self.assertGreater(len(frame.markers["core"]), 0, where)
                    self.assertGreater(len(frame.markers["orb"]), 0, where)
                    self.assertEqual(len(frame.markers["flame"]), 1, where)      # his soul-flame
                    self.assertGreater(len(frame.markers["vein"]), 0, where)

    def test_phase_two_has_fire_on_the_crown_and_horns(self):
        for frame in self.sheet.poses[2]["idle"]:
            self.assertGreaterEqual(len(frame.markers["fire"]), 5)

    def test_marker_pixels_are_switched_off_in_the_static_image(self):
        frame = self.sheet.poses[1]["idle"][0]
        for name, points in frame.markers.items():
            for x, y in points:
                expected = (0, 0, 0, 0) if name in art.POSITION_MARKERS else art.UNLIT + (255,)
                self.assertEqual(tuple(frame.image.get_at((x, y))), expected, name)


@needs_pygame
class TestStripChecker(unittest.TestCase):
    """The checker for pose strips, on a temporary copy of the shipped art."""

    def setUp(self):
        self.folder = tempfile.mkdtemp()
        for name in ("frames_phase1.png", "sprite.json"):
            shutil.copy(os.path.join(art.ASSET_DIR, name), self.folder)

    def tearDown(self):
        shutil.rmtree(self.folder, ignore_errors=True)

    def _config(self, **changes):
        path = os.path.join(self.folder, "sprite.json")
        with open(path, encoding="utf-8") as f:
            config = json.load(f)
        config.update(changes)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(config, f)

    def _edit(self, fn, name="frames_phase1.png"):
        path = os.path.join(self.folder, name)
        image = pygame.image.load(path)
        fn(image)
        pygame.image.save(image, path)

    def test_phase_one_only_is_valid_and_phase_two_falls_back(self):
        self.assertEqual(art.check_assets(self.folder), ([], []))
        surface = pygame.Surface((400, 400))
        renderer = art.LichKingArt(self.folder)
        for phase in (1, 2):
            renderer.draw(surface, 200, 200, clock=1.0, phase=phase, pose="volley", progress=0.5)
        self.assertFalse(renderer._failed)

    def test_missing_poses_fall_back_to_idle(self):
        with open(os.path.join(self.folder, "sprite.json"), encoding="utf-8") as f:
            config = json.load(f)
        self._config(animations={"idle": config["animations"]["idle"]})
        self.assertEqual(art.check_assets(self.folder), ([], []))
        renderer = art.LichKingArt(self.folder)
        surface = pygame.Surface((400, 400))
        for pose in ("volley", "drain", "summon", "recover", "hurt", "roar", "nonsense"):
            renderer.draw(surface, 200, 200, clock=0.3, phase=1, pose=pose, progress=0.7)
        self.assertFalse(renderer._failed)

    def test_reports_missing_required_strip(self):
        os.remove(os.path.join(self.folder, "frames_phase1.png"))
        os.makedirs(os.path.join(self.folder, "x"), exist_ok=True)
        shutil.copy(os.path.join(art.ASSET_DIR, "frames_phase2.png"), self.folder)
        # with frames_phase1.png gone the folder is no longer a strip folder: it is reported as a classic one
        errors, _ = art.check_assets(self.folder)
        self.assertTrue(errors)

    def test_warns_about_leftover_old_format_files(self):
        shutil.copy(os.path.join(CLASSIC, "staff.png"), self.folder)
        _, warnings = art.check_assets(self.folder)
        self.assertTrue(any("staff.png" in w and "ignored" in w for w in warnings))

    def test_reports_soft_pixels(self):
        self._edit(lambda im: im.set_at((5, 5), (90, 90, 90, 100)))
        errors, _ = art.check_assets(self.folder)
        self.assertTrue(any("semi-transparent" in e for e in errors))

    def test_reports_marker_colour_that_is_slightly_off(self):
        self._edit(lambda im: im.set_at((5, 5), (250, 4, 251, 255)))
        errors, _ = art.check_assets(self.folder)
        self.assertTrue(any("almost" in e and "eye" in e for e in errors))

    def test_reports_wrong_frame_height(self):
        path = os.path.join(self.folder, "frames_phase1.png")
        image = pygame.image.load(path)
        pygame.image.save(pygame.transform.scale(image, (image.get_width(), 64)), path)
        errors, _ = art.check_assets(self.folder)
        self.assertTrue(any("tall" in e for e in errors))

    def test_reports_width_that_is_not_whole_frames(self):
        path = os.path.join(self.folder, "frames_phase1.png")
        image = pygame.image.load(path)
        pygame.image.save(image.subsurface(pygame.Rect(0, 0, image.get_width() - 7, image.get_height())), path)
        errors, _ = art.check_assets(self.folder)
        self.assertTrue(any("whole number" in e for e in errors))

    def test_reports_frame_numbers_outside_the_strip(self):
        self._config(animations={"idle": [0, 1, 2, 3], "volley": [4, 5, 99]})
        errors, _ = art.check_assets(self.folder)
        self.assertTrue(any("volley" in e and "outside" in e for e in errors))

    def test_reports_missing_idle(self):
        self._config(animations={"volley": [4, 5, 6]})
        errors, _ = art.check_assets(self.folder)
        self.assertTrue(any("idle" in e for e in errors))

    def test_warns_about_unknown_pose_names(self):
        self._config(animations={"idle": [0, 1, 2, 3], "dance": [4, 5]})
        _, warnings = art.check_assets(self.folder)
        self.assertTrue(any("dance" in w for w in warnings))

    def test_reports_missing_frame_size(self):
        self._config(frame_size=None)
        errors, _ = art.check_assets(self.folder)
        self.assertTrue(any("frame_size" in e for e in errors))

    def test_reports_anchor_outside_frame(self):
        self._config(anchor=[500, 500])
        errors, _ = art.check_assets(self.folder)
        self.assertTrue(any("anchor" in e for e in errors))

    def test_warns_when_a_frame_has_no_glowing_eyes(self):
        def wipe_eyes(image):
            for x in range(96):                             # the first frame only
                for y in range(image.get_height()):
                    if tuple(image.get_at((x, y)))[:3] == art.MARKERS["eye"]:
                        image.set_at((x, y), (90, 90, 90, 255))
        self._edit(wipe_eyes)
        _, warnings = art.check_assets(self.folder)
        self.assertTrue(any("eye" in w and "[0]" in w for w in warnings))

    def test_reports_broken_json(self):
        with open(os.path.join(self.folder, "sprite.json"), "w") as f:
            f.write("{ not json")
        errors, _ = art.check_assets(self.folder)
        self.assertTrue(any("JSON" in e for e in errors))


@needs_pygame
class TestClassicFormat(unittest.TestCase):
    """The older body_phase*.png + staff.png format must keep working (kept as fixtures)."""

    def setUp(self):
        self.folder = tempfile.mkdtemp()
        for name in ("body_phase1_a.png", "staff.png", "sprite.json"):
            shutil.copy(os.path.join(CLASSIC, name), self.folder)

    def tearDown(self):
        shutil.rmtree(self.folder, ignore_errors=True)

    def _edit(self, name, fn):
        path = os.path.join(self.folder, name)
        image = pygame.image.load(path)
        fn(image)
        pygame.image.save(image, path)

    def test_full_classic_folder_is_valid_and_draws(self):
        full = tempfile.mkdtemp()
        try:
            for name in os.listdir(CLASSIC):
                shutil.copy(os.path.join(CLASSIC, name), full)
            self.assertEqual(art.check_assets(full), ([], []))
            sheet = art.SpriteSheet(full)
            self.assertIsNotNone(sheet.staff)
            self.assertEqual(len(sheet.poses[1]["idle"]), 2)
            surface = pygame.Surface((400, 400))
            renderer = art.LichKingArt(full)
            for phase in (1, 2):
                for pose in (None, "volley", "summon"):          # new poses fall back to idle
                    renderer.draw(surface, 200, 200, clock=0.7, phase=phase, pose=pose, progress=0.5,
                                  raise_staff=pose == "summon", glow=(239, 159, 39), glow_level=3)
            self.assertFalse(renderer._failed)
        finally:
            shutil.rmtree(full, ignore_errors=True)

    def test_minimal_folder_is_valid_and_draws(self):
        self.assertEqual(art.check_assets(self.folder), ([], []))
        surface = pygame.Surface((400, 400))
        renderer = art.LichKingArt(self.folder)
        for phase in (1, 2):                      # optional files fall back gracefully
            renderer.draw(surface, 200, 200, clock=1.0, phase=phase)
        self.assertFalse(renderer._failed)

    def test_reports_missing_required_file(self):
        os.remove(os.path.join(self.folder, "staff.png"))
        errors, _ = art.check_assets(self.folder)
        self.assertTrue(any("staff.png" in e and "missing" in e for e in errors))

    def test_reports_soft_pixels(self):
        self._edit("body_phase1_a.png", lambda im: im.set_at((5, 5), (90, 90, 90, 100)))
        errors, _ = art.check_assets(self.folder)
        self.assertTrue(any("semi-transparent" in e for e in errors))

    def test_reports_marker_colour_that_is_slightly_off(self):
        self._edit("body_phase1_a.png", lambda im: im.set_at((5, 5), (250, 4, 251, 255)))
        errors, _ = art.check_assets(self.folder)
        self.assertTrue(any("almost" in e and "eye" in e for e in errors))

    def test_reports_size_mismatch(self):
        path = os.path.join(self.folder, "staff.png")
        pygame.image.save(pygame.transform.scale(pygame.image.load(path), (20, 20)), path)
        errors, _ = art.check_assets(self.folder)
        self.assertTrue(any("same size" in e for e in errors))

    def test_reports_anchor_outside_canvas(self):
        with open(os.path.join(self.folder, "sprite.json"), "w") as f:
            f.write('{"anchor": [500, 500]}')
        errors, _ = art.check_assets(self.folder)
        self.assertTrue(any("anchor" in e for e in errors))

    def test_reports_broken_json(self):
        with open(os.path.join(self.folder, "sprite.json"), "w") as f:
            f.write("{ not json")
        errors, _ = art.check_assets(self.folder)
        self.assertTrue(any("JSON" in e for e in errors))


@needs_pygame
class TestArtDrawing(unittest.TestCase):
    def test_every_pose_draws_in_both_phases(self):
        surface = pygame.Surface((500, 500))
        renderer = art.LichKingArt()
        for phase in (1, 2):
            for pose in list(EXPECTED_POSES) + [None, "nonsense"]:
                for progress in (0.0, 0.34, 0.67, 0.999, 1.0):
                    renderer.draw(surface, 250, 250, clock=progress * 3, phase=phase, pose=pose,
                                  progress=progress, glow=(239, 159, 39), glow_level=3, rage=progress)
        self.assertFalse(renderer._failed)

    def test_every_look_draws(self):
        surface = pygame.Surface((400, 400))
        renderer = art.LichKingArt()
        looks = [
            dict(phase=1), dict(phase=2),
            dict(phase=1, glow=(239, 159, 39), glow_level=3),
            dict(phase=2, glow=(212, 83, 126), glow_level=2, raise_staff=True),
            dict(phase=1, flash=True), dict(phase=2, flash=True, pose="hurt"),
            dict(phase=1, fade=0.5), dict(phase=2, fade=0.03), dict(phase=1, fade=0.0),
        ]
        for look in looks:
            for clock in (0.0, 0.7, 5.3):
                renderer.draw(surface, 200, 200, clock=clock, **look)
        self.assertFalse(renderer._failed)

    def test_something_is_actually_drawn(self):
        surface = pygame.Surface((500, 500))
        surface.fill((0, 0, 0))
        art.LichKingArt().draw(surface, 250, 250, clock=0.0, phase=1)
        lit = sum(1 for x in range(0, 500, 4) for y in range(0, 500, 4) if surface.get_at((x, y))[:3] != (0, 0, 0))
        self.assertGreater(lit, 800)

    def test_each_pose_looks_different(self):
        """The poses are real changes in the picture, not copies of idle."""
        renderer = art.LichKingArt()
        pictures = {}
        for pose in EXPECTED_POSES:
            surface = pygame.Surface((500, 500))
            renderer.draw(surface, 250, 250, clock=0.0, phase=1, pose=pose, progress=0.0)
            pictures[pose] = pygame.image.tostring(surface, "RGB")
        self.assertEqual(len(set(pictures.values())), len(EXPECTED_POSES))

    def test_progress_walks_through_the_frames_of_a_pose(self):
        renderer = art.LichKingArt()
        renderer._load()
        picked = [renderer._pick_body(1, 0.0, "summon", p)[1][1] for p in (0.0, 0.4, 0.8, 1.0)]
        self.assertEqual(picked, [0, 1, 2, 2])
        idle = {renderer._pick_body(1, c / 10.0, None, 0.0)[1][1] for c in range(40)}
        self.assertEqual(idle, {0, 1, 2, 3})

    def test_glow_colour_changes_the_eyes(self):
        sheet = art.SpriteSheet(art.ASSET_DIR)
        ex, ey = sheet.bodies[(1, 0)].markers["eye"][0]
        renderer = art.LichKingArt()
        seen = []
        for glow in (None, (239, 159, 39)):
            surface = pygame.Surface((500, 500))
            renderer.draw(surface, 250, 250, clock=0.0, phase=1, glow=glow, glow_level=1)
            s = sheet.scale
            ax, ay = sheet.anchor
            seen.append(surface.get_at((250 - ax * s + ex * s + 1, 250 - ay * s + ey * s + 1))[:3])
        self.assertNotEqual(seen[0], seen[1])

    def test_live_effects_change_the_picture_over_time(self):
        """Souls orbit, flames flicker, veins ripple: two moments must not be identical."""
        renderer = art.LichKingArt()
        shots = []
        for clock in (0.0, 0.9):
            surface = pygame.Surface((500, 500))
            renderer.draw(surface, 250, 250, clock=clock, phase=2)
            shots.append(pygame.image.tostring(surface, "RGB"))
        self.assertNotEqual(shots[0], shots[1])

    def test_effects_can_be_switched_off_in_sprite_json(self):
        folder = tempfile.mkdtemp()
        try:
            for name in ("frames_phase1.png", "sprite.json"):
                shutil.copy(os.path.join(art.ASSET_DIR, name), folder)
            path = os.path.join(folder, "sprite.json")
            with open(path, encoding="utf-8") as f:
                config = json.load(f)
            config["orbit"] = None
            config["wisps"] = None
            with open(path, "w", encoding="utf-8") as f:
                json.dump(config, f)
            renderer = art.LichKingArt(folder)
            renderer.draw(pygame.Surface((500, 500)), 250, 250, clock=1.3, phase=1)
            self.assertFalse(renderer._failed)
        finally:
            shutil.rmtree(folder, ignore_errors=True)

    def test_enraged_colours_blend_from_the_phase_colours_to_white_hot(self):
        self.assertEqual(art.live_colors(2, 0.0), art.LIVE[2])
        hot = art.live_colors(2, 1.0)
        self.assertEqual(hot["eye"], art.RAGE["eye"])
        self.assertEqual(hot["flame"], art.RAGE["flame"])                 # nested colour tuples blend too
        half = art.live_colors(2, 0.5)
        for key in ("eye", "core", "vein"):
            for channel in range(3):
                low, high = sorted((art.LIVE[2][key][channel], art.RAGE[key][channel]))
                self.assertTrue(low <= half[key][channel] <= high)

    def test_rage_changes_the_picture_and_adds_more_going_on(self):
        renderer = art.LichKingArt()
        calm, angry = pygame.Surface((500, 500)), pygame.Surface((500, 500))
        for surface in (calm, angry):
            surface.fill((0, 0, 0))
        renderer.draw(calm, 250, 250, clock=1.0, phase=2, rage=0.0)
        renderer.draw(angry, 250, 250, clock=1.0, phase=2, rage=1.0)
        self.assertNotEqual(pygame.image.tostring(calm, "RGB"), pygame.image.tostring(angry, "RGB"))
        renderer.draw(angry, 250, 250, clock=2.0, phase=1, rage=5.0)     # out-of-range values are clamped
        self.assertFalse(renderer._failed)

    def test_ghosts_are_see_through_and_have_no_floor_shadow(self):
        renderer = art.LichKingArt()
        solid, ghost = pygame.Surface((500, 500)), pygame.Surface((500, 500))
        for surface in (solid, ghost):
            surface.fill((0, 0, 0))
        renderer.draw(solid, 250, 250, clock=1.0, phase=2, rage=1.0)
        renderer.draw(ghost, 250, 250, clock=1.0, phase=2, rage=1.0, alpha=0.3, ghost=True)

        def brightness(surface):
            return sum(sum(surface.get_at((x, y))[:3]) for x in range(0, 500, 3) for y in range(0, 500, 3))
        self.assertLess(brightness(ghost), brightness(solid) * 0.6)
        renderer.draw(solid, 250, 250, clock=1.0, phase=2, alpha=0.5)     # the layer is reusable afterwards
        self.assertEqual(renderer._layer.get_alpha(), 255)

    def test_cached_surfaces_are_reused(self):
        surface = pygame.Surface((500, 500))
        renderer = art.LichKingArt()
        renderer.draw(surface, 250, 250, clock=0.0, phase=1)
        count = len(renderer._cache)
        renderer.draw(surface, 250, 250, clock=0.01, phase=1)
        self.assertEqual(len(renderer._cache), count)


class TestMissingArt(unittest.TestCase):
    def test_broken_folder_shows_placeholder_instead_of_crashing(self):
        surface = pygame.Surface((400, 400))
        renderer = art.LichKingArt(folder=os.path.join(tempfile.gettempdir(), "no_such_sprites"))
        renderer.draw(surface, 200, 200, clock=0.0, phase=1)
        renderer.draw(surface, 200, 200, clock=0.1, phase=2)
        self.assertTrue(renderer._failed)


class TestBossDrawing(unittest.TestCase):
    def test_boss_draws_in_every_state_of_the_fight(self):
        """Play a whole fight (both phases, death) and draw a frame every tick."""
        surface = pygame.Surface((960, 640))
        boss = LichKing(seed=3)
        player = StubPlayer()
        seen = set()
        for i in range(60 * 40):
            if i == 60 * 8:
                boss.debug_set_hp_percent(0.5)
            if i == 60 * 30:
                boss.hp = 1
                boss.take_damage(50)
            if i % 300 == 150:
                boss.take_damage(1)         # hit flash
            boss.update(DT, player, BOUNDS)
            boss.draw(surface)
            seen.add(boss.state)
        for state in ("intro", "idle", "windup", "transition", "dying"):
            self.assertIn(state, seen)


class TestBossUsesThePoses(unittest.TestCase):
    """Each moment of the fight shows the pose that matches what he is doing."""

    def setUp(self):
        self.boss = LichKing(seed=1)
        self.player = StubPlayer()
        for _ in range(int((LichKing.INTRO_TIME + 0.1) / DT)):
            self.boss.update(DT, self.player, BOUNDS)

    def _look(self):
        return self.boss._look()

    def test_idle_has_no_special_pose(self):
        self.boss.state = "idle"
        self.assertIsNone(self._look()["pose"])

    def test_each_attack_windup_uses_its_own_pose_and_progress(self):
        for attack in ("volley", "drain", "summon", "nova", "grasp"):
            self.boss.state, self.boss.attack_name = "windup", attack
            self.boss.windup_time, self.boss.state_time = 1.0, 0.5
            look = self._look()
            self.assertEqual(look["pose"], attack)
            self.assertAlmostEqual(look["progress"], 0.5)

    def test_recover_transition_and_dying_poses(self):
        self.boss.state, self.boss.state_time = "recover", 0.0
        self.assertEqual(self._look()["pose"], "recover")
        self.boss.state = "transition"
        self.assertEqual(self._look()["pose"], "roar")
        self.boss.state = "dying"
        self.assertEqual(self._look()["pose"], "hurt")

    def test_a_hit_makes_him_flinch_but_never_hides_a_windup(self):
        self.boss.state, self.boss.hit_flash = "idle", 0.1
        self.assertEqual(self._look()["pose"], "hurt")
        self.boss.state, self.boss.attack_name = "windup", "volley"
        self.boss.windup_time, self.boss.state_time = 1.0, 0.2
        self.assertEqual(self._look()["pose"], "volley")

    @needs_pygame
    def test_transformation_and_death_effects_are_drawn(self):
        for state, method in (("transition", "_draw_transformation_rings"), ("dying", "_draw_death_burst")):
            self.boss.state = state
            lit = 0
            for t in (0.2, 0.5, 0.8, 1.2, 1.6):
                self.boss.state_time = t
                surface = pygame.Surface((960, 640))
                getattr(self.boss, method)(surface, 480, 250)
                lit += sum(1 for x in range(0, 960, 3) for y in range(0, 640, 3)
                           if surface.get_at((x, y))[:3] != (0, 0, 0))
            self.assertGreater(lit, 50, method)

    def test_fight_whole_playthrough_with_the_new_poses(self):
        surface = pygame.Surface((960, 640))
        boss = LichKing(seed=5)
        poses = set()
        for i in range(60 * 45):
            if i == 60 * 10:
                boss.debug_set_hp_percent(0.5)
            boss.update(DT, self.player, BOUNDS)
            poses.add(boss._look()["pose"])
            if i % 7 == 0:
                boss.draw(surface)
        self.assertTrue({"volley", "drain", "recover", "roar"} <= poses, poses)


if __name__ == "__main__":
    unittest.main()
