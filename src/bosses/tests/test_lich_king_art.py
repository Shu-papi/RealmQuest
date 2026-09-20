"""Run from the repo root:  python -m unittest discover -s src/bosses/tests"""
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

    def test_shipped_sprites_pass_the_checker(self):
        errors, warnings = art.check_assets()
        self.assertEqual(errors, [])
        self.assertEqual(warnings, [])

    def test_all_sprites_share_one_canvas_size(self):
        sizes = set()
        for name in list(art.BODY_FILES.values()) + [art.STAFF_FILE]:
            sizes.add(pygame.image.load(os.path.join(art.ASSET_DIR, name)).get_size())
        self.assertEqual(len(sizes), 1)

    def test_glow_markers_are_found(self):
        sheet = art.SpriteSheet(art.ASSET_DIR)
        for (phase, hem), frame in sheet.bodies.items():
            self.assertGreaterEqual(len(frame.markers["eye"]), 2, (phase, hem))
            self.assertGreater(len(frame.markers["core"]), 0, (phase, hem))
        self.assertGreater(len(sheet.staff.markers["orb"]), 0)

    def test_marker_pixels_are_switched_off_in_the_static_image(self):
        sheet = art.SpriteSheet(art.ASSET_DIR)
        frame = sheet.bodies[(1, 0)]
        for name, points in frame.markers.items():
            for x, y in points:
                self.assertEqual(frame.image.get_at((x, y))[:3], art.UNLIT, name)


@needs_pygame
class TestChecker(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.mkdtemp()
        for name in ("body_phase1_a.png", "staff.png", "sprite.json"):
            shutil.copy(os.path.join(art.ASSET_DIR, name), self.folder)

    def tearDown(self):
        shutil.rmtree(self.folder, ignore_errors=True)

    def _edit(self, name, fn):
        path = os.path.join(self.folder, name)
        image = pygame.image.load(path)
        fn(image)
        pygame.image.save(image, path)

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
    def test_every_pose_draws(self):
        surface = pygame.Surface((400, 400))
        renderer = art.LichKingArt()
        poses = [
            dict(phase=1), dict(phase=2),
            dict(phase=1, glow=(239, 159, 39), glow_level=3),
            dict(phase=2, glow=(212, 83, 126), glow_level=2, raise_staff=True),
            dict(phase=1, flash=True), dict(phase=2, flash=True),
            dict(phase=1, fade=0.5), dict(phase=2, fade=0.03), dict(phase=1, fade=0.0),
        ]
        for pose in poses:
            for clock in (0.0, 0.7, 5.3):
                renderer.draw(surface, 200, 200, clock=clock, **pose)
        self.assertFalse(renderer._failed)

    def test_something_is_actually_drawn(self):
        surface = pygame.Surface((400, 400))
        surface.fill((0, 0, 0))
        art.LichKingArt().draw(surface, 200, 200, clock=0.0, phase=1)
        lit = sum(1 for x in range(0, 400, 4) for y in range(0, 400, 4) if surface.get_at((x, y))[:3] != (0, 0, 0))
        self.assertGreater(lit, 500)

    def test_glow_colour_changes_the_eyes(self):
        sheet = art.SpriteSheet(art.ASSET_DIR)
        ex, ey = sheet.bodies[(1, 0)].markers["eye"][0]
        renderer = art.LichKingArt()
        seen = []
        for glow in (None, (239, 159, 39)):
            surface = pygame.Surface((400, 400))
            renderer.draw(surface, 200, 200, clock=0.0, phase=1, glow=glow, glow_level=1)
            s = sheet.scale
            ax, ay = sheet.anchor
            seen.append(surface.get_at((200 - ax * s + ex * s + 1, 200 - ay * s + ey * s + 1))[:3])
        self.assertNotEqual(seen[0], seen[1])

    def test_cached_surfaces_are_reused(self):
        surface = pygame.Surface((400, 400))
        renderer = art.LichKingArt()
        renderer.draw(surface, 200, 200, clock=0.0, phase=1)
        count = len(renderer._cache)
        renderer.draw(surface, 200, 200, clock=0.01, phase=1)
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


if __name__ == "__main__":
    unittest.main()
