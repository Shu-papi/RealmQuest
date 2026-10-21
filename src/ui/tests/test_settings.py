"""
Checks the settings (volumes, video, key bindings), saving/loading, and the settings screen.
Run from the repo root:  python -m unittest discover -s src/ui/tests
"""
import json
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

import ui.assets as assets
from ui.settings_data import Settings, KEY_ACTIONS
from ui.settings_screen import SettingsScreen, BACK, VIDEO_CHANGED, RESET_ROW


class TempFileTest(unittest.TestCase):
    def setUp(self):
        folder = tempfile.mkdtemp()
        self.path = os.path.join(folder, "settings.json")


class TestSettingsData(TempFileTest):
    def test_defaults(self):
        s = Settings()
        self.assertEqual(s.key_for("move_up"), "w")
        self.assertFalse(s.fullscreen)

    def test_volume_is_kept_between_0_and_100(self):
        s = Settings()
        s.set_volume("music_volume", 150)
        self.assertEqual(s.music_volume, 100)
        s.set_volume("music_volume", -20)
        self.assertEqual(s.music_volume, 0)

    def test_effective_volume_uses_master(self):
        s = Settings()
        s.master_volume, s.sfx_volume = 50, 50
        self.assertAlmostEqual(s.effective_volume("sfx"), 0.25)

    def test_rebind_swaps_when_key_already_used(self):
        s = Settings()
        s.rebind("attack", "w")                 # w was Move Up
        self.assertEqual(s.key_for("attack"), "w")
        self.assertEqual(s.key_for("move_up"), "j")   # got Attack's old key
        self.assertEqual(len(set(s.key_bindings.values())), len(KEY_ACTIONS))

    def test_save_and_load_round_trip(self):
        s = Settings()
        s.music_volume, s.fullscreen = 30, True
        s.rebind("dash", "left shift")
        self.assertTrue(s.save(self.path))
        loaded = Settings.load(self.path)
        self.assertEqual(loaded.to_dict(), s.to_dict())

    def test_missing_or_broken_file_gives_defaults(self):
        self.assertEqual(Settings.load(self.path).to_dict(), Settings().to_dict())
        with open(self.path, "w") as f:
            f.write("{ not json")
        self.assertEqual(Settings.load(self.path).to_dict(), Settings().to_dict())

    def test_bad_values_in_file_are_ignored(self):
        with open(self.path, "w") as f:
            json.dump({"music_volume": "loud", "fullscreen": "yes", "key_bindings": {"attack": 5}}, f)
        loaded = Settings.load(self.path)
        self.assertEqual(loaded.music_volume, 70)
        self.assertFalse(loaded.fullscreen)
        self.assertEqual(loaded.key_for("attack"), "j")


class TestSettingsScreen(TempFileTest):
    def setUp(self):
        super().setUp()
        self.settings = Settings()
        self.ui = SettingsScreen(self.settings, save_path=self.path)

    def test_three_tabs_and_switching(self):
        self.assertEqual(self.ui.tab_id, "audio")
        self.ui.switch_tab(+1)
        self.assertEqual(self.ui.tab_id, "video")
        self.ui.switch_tab(+1)
        self.assertEqual(self.ui.tab_id, "controls")
        self.ui.switch_tab(+1)
        self.assertEqual(self.ui.tab_id, "audio")

    def test_audio_has_master_music_sfx(self):
        self.assertEqual(self.ui.rows(), ["master_volume", "music_volume", "sfx_volume"])

    def test_left_right_changes_volume(self):
        self.ui.move(+1)                       # Music
        self.ui.adjust(-1)
        self.assertEqual(self.settings.music_volume, 65)
        self.ui.adjust(+1)
        self.ui.adjust(+1)
        self.assertEqual(self.settings.music_volume, 75)

    def test_fullscreen_toggle_reports_video_changed(self):
        self.ui.switch_tab(index=1)
        self.assertEqual(self.ui.adjust(-1), VIDEO_CHANGED)     # left = ON
        self.assertTrue(self.settings.fullscreen)
        self.assertIsNone(self.ui.adjust(-1))                    # already on: nothing changes

    def test_screen_shake_toggle(self):
        self.ui.switch_tab(index=1)
        self.ui.move(+1)
        self.assertIsNone(self.ui.activate())
        self.assertFalse(self.settings.screen_shake)

    def test_rebinding_a_key(self):
        self.ui.switch_tab(index=2)
        self.ui.move(+4)                       # Attack
        self.ui.activate()
        self.assertTrue(self.ui.rebinding)
        self.ui.press_key_while_rebinding("l")
        self.assertFalse(self.ui.rebinding)
        self.assertEqual(self.settings.key_for("attack"), "l")

    def test_escape_cancels_rebinding(self):
        self.ui.switch_tab(index=2)
        self.ui.activate()
        self.ui.press_key_while_rebinding("escape")
        self.assertEqual(self.settings.key_for("move_up"), "w")

    def test_reset_keys_row(self):
        self.settings.rebind("attack", "l")
        self.ui.switch_tab(index=2)
        self.ui.row = self.ui.rows().index(RESET_ROW)
        self.ui.activate()
        self.assertEqual(self.settings.key_for("attack"), "j")

    def test_close_saves_and_goes_back(self):
        self.settings.sfx_volume = 10
        self.assertEqual(self.ui.close(), BACK)
        self.assertEqual(Settings.load(self.path).sfx_volume, 10)

    def test_click_on_slider_sets_volume(self):
        tx, ty, tw, th = self.ui.slider_track(0)
        self.ui._click((tx + tw // 2, ty + th // 2))
        self.assertEqual(self.settings.master_volume, 50)
        self.assertEqual(self.ui.dragging, 0)

    def test_everything_fits_inside_the_panel(self):
        from ui.settings_screen import PANEL, PANEL_BORDER
        px, py, pw, ph = PANEL
        for tab in range(3):
            self.ui.switch_tab(index=tab)
            for i in range(len(self.ui.rows())):
                x, y, w, h = self.ui.row_rect(i)
                self.assertGreaterEqual(x, px + PANEL_BORDER)
                self.assertLessEqual(x + w, px + pw - PANEL_BORDER)
                self.assertLessEqual(y + h, py + ph - PANEL_BORDER)

    def test_draw_every_tab(self):
        assets.ENABLED = False                 # the stub can't load pictures
        try:
            screen = pygame.Surface((960, 640))
            for tab in range(3):
                self.ui.switch_tab(index=tab)
                self.ui.draw(screen)
            self.ui.rebinding = True
            self.ui.draw(screen)
        finally:
            assets.ENABLED = True
            assets.clear_cache()


if __name__ == "__main__":
    unittest.main()
