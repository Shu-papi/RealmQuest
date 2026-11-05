"""Checks for the isometric view, his four-way facing, and a walk that does not skate."""
import os as _os; _os.environ["REALMQUEST_BALANCE"] = "none"      # these tests pin the code's DEFAULT numbers, not your config/ tuning
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

from bosses import Minotaur
from bosses.minotaur.boss import WALK_CYCLE_PX
from bosses.minotaur.view import IsoView, TopDownView

DT = 1 / 60
BOUNDS = (40, 110, 920, 600)
REAL_PYGAME = hasattr(pygame, "get_sdl_version")
needs_pygame = unittest.skipUnless(REAL_PYGAME, "needs real pygame (pip install pygame-ce)")


class StubPlayer:
    def __init__(self, x=480, y=500):
        self.rect = pygame.Rect(0, 0, 28, 28)
        self.rect.center = (x, y)

    def take_damage(self, amount):
        return amount


def ready_boss(seed=1, view=None):
    boss = Minotaur(seed=seed)
    if view is not None:
        boss.view = view
    for _ in range(int((Minotaur.INTRO_TIME + 0.1) / DT)):
        boss.update(DT, StubPlayer(), BOUNDS)
    return boss


class TestViews(unittest.TestCase):
    def test_projection_round_trips(self):
        view = IsoView()
        for x, y in ((40, 110), (480, 355), (920, 600), (123.4, 567.8)):
            wx, wy = view.unproject(*view.project(x, y))
            self.assertAlmostEqual(wx, x, places=6)
            self.assertAlmostEqual(wy, y, places=6)

    def test_floor_is_a_2_to_1_diamond(self):
        view = IsoView()
        cx, cy = view.project(480, 355)
        for angle in range(0, 360, 30):                      # a circle of 100 floor units
            x = 480 + 100 * math.cos(math.radians(angle))
            y = 355 + 100 * math.sin(math.radians(angle))
            sx, sy = view.project(x, y)
            ellipse = ((sx - cx) / (100 * view.k * math.sqrt(2))) ** 2 + ((sy - cy) / (50 * view.k * math.sqrt(2))) ** 2
            self.assertAlmostEqual(ellipse, 1.0, places=6)

    def test_keys_move_along_the_screen_not_along_the_floor_axes(self):
        view = IsoView()
        origin = view.project(480, 355)
        for key, expected in (((1, 0), (1, 0)), ((-1, 0), (-1, 0)), ((0, -1), (0, -1)), ((0, 1), (0, 1))):
            wx, wy = view.to_world(*key)
            sx, sy = view.project(480 + wx, 355 + wy)
            dx, dy = sx - origin[0], sy - origin[1]
            if expected[0]:
                self.assertAlmostEqual(dy, 0, places=6, msg=f"{key}: right/left must stay level")
                self.assertGreater(dx * expected[0], 0)
            else:
                self.assertAlmostEqual(dx, 0, places=6, msg=f"{key}: up/down must stay vertical")
                self.assertGreater(dy * expected[1], 0)

    def test_depth_sorts_by_how_near_the_camera(self):
        view = IsoView()
        self.assertLess(view.depth(100, 100), view.depth(500, 400))

    def test_topdown_is_the_identity(self):
        view = TopDownView()
        self.assertEqual(view.project(12, 34), (12.0, 34.0))
        self.assertEqual(view.to_world(1, -1), (1.0, -1.0))
        self.assertEqual(view.sprite_origin(100, 200, 88), (100.0, 200.0))
        self.assertEqual(IsoView().sprite_origin(100, 200, 88)[1], IsoView().project(100, 200)[1] - 88)

    @needs_pygame
    def test_a_flat_layer_lands_exactly_where_project_says(self):
        pygame.init()
        view = IsoView()
        layer = pygame.Surface((880, 490), pygame.SRCALPHA)
        points = {"A": (60, 60), "B": (800, 60), "C": (800, 430), "D": (60, 430), "mid": (440, 245)}
        for x, y in points.values():
            pygame.draw.rect(layer, (255, 0, 0, 255), (x - 6, y - 6, 12, 12))
        flat, (left, top) = view.flatten(layer, (40, 110))
        canvas = pygame.Surface((960, 640), pygame.SRCALPHA)
        canvas.blit(flat, (left, top))
        mask = pygame.mask.from_threshold(canvas, (255, 0, 0), (30, 30, 30, 255))
        found = [tuple(c.centroid()) for c in mask.connected_components() if c.count() > 8]
        for x, y in points.values():
            ex, ey = view.project(x + 40, y + 110)
            self.assertTrue(any(abs(fx - ex) <= 3 and abs(fy - ey) <= 3 for fx, fy in found), (x, y))


class TestFacing(unittest.TestCase):
    def test_flat_arena_boss_faces_four_diagonal_directions(self):
        """The arena stays flat, but the boss is isometric-style: front view when you are below him, back view when above."""
        boss = ready_boss()                                       # a plain TopDownView
        boss.x, boss.y = 480, 355
        boss._go_idle(99)
        boss.idle_mode = "taunt"
        for player_at, (horizontal, depth) in (((760, 540), (1, 1)),      # below and to the right: front, looks right
                                               ((200, 540), (-1, 1)),     # below and to the left: front, looks left
                                               ((760, 170), (1, -1)),     # above and to the right: back, looks right
                                               ((200, 170), (-1, -1))):   # above and to the left: back, looks left
            for _ in range(5):
                boss.update(DT, StubPlayer(*player_at), BOUNDS)
            self.assertEqual((boss.facing, boss.depth_dir), (horizontal, depth), player_at)

    def test_plain_two_way_mode_never_shows_his_back(self):
        boss = ready_boss(view=TopDownView(four_way=False))
        for x, y in ((100, 100), (900, 100), (100, 590), (900, 590)):
            boss.update(DT, StubPlayer(x, y), BOUNDS)
            self.assertEqual(boss.depth_dir, 1)

    def test_he_keeps_his_front_while_you_circle_level_with_him(self):
        """No flicker between front and back when you are exactly beside him."""
        boss = ready_boss()
        boss.x, boss.y = 480, 355
        boss._go_idle(99)
        boss.idle_mode = "taunt"
        for _ in range(5):
            boss.update(DT, StubPlayer(780, 520), BOUNDS)
        before = boss.depth_dir
        for i in range(120):
            boss.update(DT, StubPlayer(780, 355 + (i % 2) * 6 - 3), BOUNDS)      # level with him, wobbling a few pixels
        self.assertEqual(boss.depth_dir, before)

    @needs_pygame                                                  # reads pixels back, so it needs a real window
    def test_the_flat_arena_boss_stands_on_an_oval_shadow(self):
        """With the sprite switched off, only his floor shadow is left: an oval (about 156 x 78) or nothing at all."""
        pygame.init()
        for four_way in (True, False):
            boss = ready_boss(view=TopDownView(four_way=four_way))
            boss.x, boss.y = 480, 300
            boss.art.draw = lambda *args, **kwargs: True              # no sprite, so nothing but the shadow can show
            surface = pygame.Surface((960, 640))
            surface.fill((200, 200, 200))
            boss.draw_body(surface)
            shadow = [(x, y) for x in range(300, 660) for y in range(300, 480) if surface.get_at((x, y))[0] < 150]
            if not four_way:
                self.assertEqual(shadow, [], "the old two-way mode leaves its bar shadow to the sprite code")
                continue
            xs, ys = [p[0] for p in shadow], [p[1] for p in shadow]
            width, height = max(xs) - min(xs) + 1, max(ys) - min(ys) + 1
            self.assertTrue(140 <= width <= 170, width)
            self.assertTrue(60 <= height <= 90, height)
            self.assertAlmostEqual(width / height, 2.0, delta=0.35, msg="a 2:1 isometric oval")
            self.assertAlmostEqual((min(ys) + max(ys)) / 2, 300 + 88, delta=4, msg="centred on his feet")

    def test_iso_four_directions_follow_the_player(self):
        boss = ready_boss(view=IsoView())
        boss.x, boss.y = 480, 355
        boss._go_idle(99)
        boss.idle_mode = "taunt"                                  # stand still and look
        # on screen: world +x is down-right, +y is down-left
        for player_at, (horizontal, depth) in (((700, 355), (1, 1)),        # down-right: toward the camera, to the right
                                               ((480, 520), (-1, 1)),       # down-left
                                               ((260, 355), (-1, -1)),      # up-left: away from the camera
                                               ((480, 190), (1, -1))):      # up-right
            for _ in range(5):
                boss.update(DT, StubPlayer(*player_at), BOUNDS)
            self.assertEqual((boss.facing, boss.depth_dir), (horizontal, depth), player_at)

    def test_he_does_not_flicker_when_the_player_is_straight_ahead(self):
        boss = ready_boss(view=IsoView())
        boss.x, boss.y = 480, 355
        boss._go_idle(99)
        boss.idle_mode = "taunt"
        for _ in range(5):
            boss.update(DT, StubPlayer(480, 190 + 0), BOUNDS)         # straight up the screen: depth is clear, side is not
        before = boss.facing
        for i in range(120):
            boss.update(DT, StubPlayer(480 + (i % 2), 190), BOUNDS)
        self.assertEqual(boss.facing, before)


class TestWalkStride(unittest.TestCase):
    def _walk(self, view):
        boss = ready_boss(view=view)
        boss.x, boss.y = 300, 200
        boss._go_idle(99)
        boss.idle_mode = "chase"
        player = StubPlayer(800, 560)
        for _ in range(30):                                       # get up to speed
            boss.update(DT, player, BOUNDS)
        phase0, x0, y0 = boss.walk_phase, boss.x, boss.y
        for _ in range(int(2.0 / DT)):
            boss.update(DT, player, BOUNDS)
        dx, dy = view.screen_move(boss.x - x0, boss.y - y0)
        return (boss.walk_phase - phase0), math.hypot(dx, dy)

    def test_the_walk_cycle_follows_the_distance_he_covers_on_screen(self):
        for view in (TopDownView(), IsoView()):
            phase, distance = self._walk(view)
            expected = distance / WALK_CYCLE_PX * math.tau
            self.assertGreater(distance, 60)
            self.assertAlmostEqual(phase, expected, delta=expected * 0.05, msg=view.name)

    def test_standing_still_means_the_legs_stop(self):
        boss = ready_boss()
        boss._go_idle(99)
        boss.idle_mode = "taunt"
        for _ in range(60):
            boss.update(DT, StubPlayer(), BOUNDS)
        phase = boss.walk_phase
        for _ in range(120):
            boss.update(DT, StubPlayer(), BOUNDS)
        self.assertAlmostEqual(boss.walk_phase, phase, places=6)

    def test_no_leg_cycle_in_the_air(self):
        boss = ready_boss()
        boss._start_attack("leap")
        for _ in range(int(0.7 / DT)):
            boss.update(DT, StubPlayer(), BOUNDS)
        self.assertEqual(boss.state, "leap")
        phase = boss.walk_phase
        for _ in range(20):
            boss.update(DT, StubPlayer(), BOUNDS)
        self.assertAlmostEqual(boss.walk_phase, phase, places=6)

    def test_legs_never_flicker_faster_than_the_cap_during_a_charge(self):
        boss = ready_boss()
        boss._start_attack("charge")
        previous = boss.walk_phase
        for _ in range(int(3.0 / DT)):
            boss.update(DT, StubPlayer(), BOUNDS)
            self.assertLessEqual(boss.walk_phase - previous, DT * 2.6 * math.tau + 1e-9)
            previous = boss.walk_phase

    @needs_pygame
    def test_he_uses_walk_frames_and_back_frames_when_the_files_exist(self):
        pygame.init()
        boss = ready_boss(view=IsoView())
        self.assertGreaterEqual(boss.art.walk_frame_count(), 4)
        self.assertTrue(boss.art.has_back_view())
        boss.x, boss.y = 300, 200
        boss._go_idle(99)
        boss.idle_mode = "chase"
        seen = set()
        for _ in range(int(2.0 / DT)):
            boss.update(DT, StubPlayer(800, 560), BOUNDS)
            pose = boss._animation()["pose"]
            if pose:
                seen.add(pose)
        self.assertGreaterEqual(len(seen), 4, "he cycles through several leg frames")
        self.assertTrue(all(p.startswith("walk") for p in seen))
        boss.idle_mode = "chase"
        for _ in range(int(2.0 / DT)):
            boss.update(DT, StubPlayer(100, 120), BOUNDS)         # up the screen: he turns his back
        self.assertEqual(boss.depth_dir, -1)
        self.assertTrue(boss._animation()["back"])


@needs_pygame
class TestBackAndWalkArt(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pygame.init()
        cls.surface = pygame.Surface((960, 640))

    def test_back_views_and_walk_sheets_ship_and_pass_the_checker(self):
        import tempfile
        from bosses.minotaur.art import ASSET_DIR, BACK_FILES, WALK_FILES, check_assets
        for name in list(BACK_FILES.values()) + list(WALK_FILES.values()):
            self.assertTrue(os.path.exists(os.path.join(ASSET_DIR, name)), name)
        self.assertEqual(check_assets(), ([], []))
        sheets = [pygame.image.load(os.path.join(ASSET_DIR, name)) for name in WALK_FILES.values()]
        self.assertEqual(len({sheet.get_size() for sheet in sheets}), 1, "all four walk sheets have the same number of frames")
        self.assertEqual(sheets[0].get_size(), (448, 56))

    def test_the_checker_rejects_a_broken_walk_sheet(self):
        import shutil
        import tempfile
        from bosses.minotaur.art import ASSET_DIR, check_assets
        with tempfile.TemporaryDirectory() as folder:
            for name in os.listdir(ASSET_DIR):
                if name.endswith((".png", ".json")):
                    shutil.copy(os.path.join(ASSET_DIR, name), folder)
            pygame.image.save(pygame.Surface((100, 56), pygame.SRCALPHA), os.path.join(folder, "walk_phase1.png"))
            errors, _ = check_assets(folder)
            self.assertTrue(any("walk sheet" in e for e in errors), errors)

    def test_every_view_and_pose_draws_and_fades(self):
        from bosses.minotaur.art import MinotaurArt
        art = MinotaurArt()
        for phase in (1, 2):
            for back in (False, True):
                for pose in (None, "raise", "cast", "walk0", "walk5", "walk99"):
                    for flip in (False, True):
                        self.assertTrue(art.draw(self.surface, 480, 300, phase=phase, pose=pose, back=back, flip=flip))
        self.assertTrue(art.draw(self.surface, 480, 300, pose="walk2", back=False, fade_to=("walk6", True), fade_mix=0.5))
        front = pygame.image.tobytes(self._render(art, back=False), "RGB")
        back = pygame.image.tobytes(self._render(art, back=True), "RGB")
        self.assertNotEqual(front, back, "the back view really is a different picture")

    def _render(self, art, **kwargs):
        surface = pygame.Surface((400, 400))
        surface.fill((33, 29, 46))
        art.draw(surface, 200, 250, bob=False, **kwargs)
        return surface

    def test_without_back_or_walk_files_everything_falls_back_to_the_front(self):
        import shutil
        import tempfile
        from bosses.minotaur.art import ASSET_DIR, MinotaurArt
        with tempfile.TemporaryDirectory() as folder:
            shutil.copy(os.path.join(ASSET_DIR, "body_phase1_a.png"), folder)
            art = MinotaurArt(folder=folder)
            self.assertEqual(art.walk_frame_count(), 0)
            self.assertFalse(art.has_back_view())
            self.assertTrue(art.draw(self.surface, 480, 300, back=True, pose="walk3"))
            front = pygame.image.tobytes(self._render(art, back=False), "RGB")
            self.assertEqual(front, pygame.image.tobytes(self._render(art, back=True), "RGB"))

    def test_a_boss_with_no_walk_files_still_walks_by_bobbing(self):
        import tempfile
        from bosses.minotaur.art import MinotaurArt
        boss = ready_boss(view=IsoView())
        with tempfile.TemporaryDirectory() as folder:
            import shutil
            from bosses.minotaur.art import ASSET_DIR
            shutil.copy(os.path.join(ASSET_DIR, "body_phase1_a.png"), folder)
            boss.art = MinotaurArt(folder=folder)
            boss._go_idle(99)
            boss.idle_mode = "chase"
            boss.x, boss.y = 300, 200
            for _ in range(int(1.5 / DT)):
                boss.update(DT, StubPlayer(800, 560), BOUNDS)
                self.assertIsNone(boss._animation()["pose"])
            boss.draw_body(self.surface)


if __name__ == "__main__":
    unittest.main()
