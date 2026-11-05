"""
Checks the monsters: the mobs self-test (slimes, wild boar, goblin shaman) and the
goblin_army sheets (goblin general, giant boar, slimes) used by monsters_config.py.
Run from the repo root:  python -m unittest discover -s src/monsters/tests
"""
import os as _os; _os.environ["REALMQUEST_BALANCE"] = "none"      # these tests pin the code's DEFAULT numbers, not your config/ tuning
import contextlib
import io
import os
import sys
import tempfile
import unittest

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

SRC_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)

import pygame

from monsters import mobs
from monsters import monsters_config as cfg


class MobsSelfTest(unittest.TestCase):
    def test_full_self_test_passes(self):
        """Runs `python src/monsters/mobs.py --test`: loading, loops, attacks, AI, screenshots."""
        with tempfile.TemporaryDirectory() as out:
            log = io.StringIO()
            with contextlib.redirect_stdout(log):
                code = mobs.main(["--test", "--out", out])
            self.assertEqual(code, 0, log.getvalue())
            self.assertIn("ALL TESTS PASSED", log.getvalue())
            for name in ("test_scene.png", "test_attacks.png", "test_contact_sheet.png"):
                self.assertTrue(os.path.isfile(os.path.join(out, name)), name)

    def test_every_mob_sheet_is_in_assets(self):
        for key in mobs.MOB_KEYS:
            for name, spec in mobs.clip_specs(key).items():
                path = os.path.join(mobs.DEFAULT_ASSETS, spec["file"])
                self.assertTrue(os.path.isfile(path), path)


class GoblinArmySheets(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pygame.init()
        pygame.display.set_mode((64, 64))

    @classmethod
    def tearDownClass(cls):
        pygame.quit()

    def test_sheets_match_config_layout(self):
        for name, info in cfg.MONSTERS.items():
            with self.subTest(monster=name):
                path = os.path.join(cfg.ASSET_DIR, info["sheet"])
                self.assertTrue(os.path.isfile(path), path)
                sheet = pygame.image.load(path)
                fw, fh = info["frame"]
                self.assertEqual(sheet.get_size(), (fw * cfg.FRAMES_PER_ROW, fh * len(cfg.ROWS)))

    def test_every_frame_has_pixels(self):
        from monsters import monster_viewer
        for name, info in cfg.MONSTERS.items():
            rows = monster_viewer.load_frames(info)
            for anim in cfg.ROWS:
                self.assertEqual(len(rows[anim]), cfg.FRAMES_PER_ROW)
                for i, frame in enumerate(rows[anim]):
                    self.assertGreater(pygame.mask.from_surface(frame).count(), 0, f"{name} {anim} {i}")

    def test_stats_are_sane(self):
        for name, info in cfg.MONSTERS.items():
            with self.subTest(monster=name):
                self.assertGreater(info["hp"], 0)
                self.assertGreater(info["speed"], 0)
                atk = info["attack"]
                self.assertGreater(atk["damage"], 0)
                self.assertGreater(atk["cooldown"], 0)
                self.assertGreater(atk["reach"], 0)


if __name__ == "__main__":
    unittest.main()
