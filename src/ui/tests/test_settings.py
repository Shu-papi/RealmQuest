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
from ui.settings_screen import SettingsScreen, BACK, VIDEO_CHANGED, APPLIED, RESET_ROW


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
        self.assertEqual(self.ui.settings.music_volume, 65)
        self.ui.adjust(+1)
        self.ui.adjust(+1)
        self.assertEqual(self.ui.settings.music_volume, 75)
        self.assertEqual(self.settings.music_volume, 70, "not applied yet")

    def test_display_mode_cycles_and_apply_reports_video_changed(self):
        self.ui.switch_tab(index=1)
        seen = []
        for _ in range(4):
            self.assertIsNone(self.ui.adjust(+1), "nothing happens before Apply")
            seen.append(self.ui.settings.display_mode)
        self.assertEqual(seen, ["borderless", "borderless_fullscreen", "fullscreen", "windowed"])
        self.ui.adjust(-1)
        self.assertFalse(self.settings.fullscreen)
        self.assertEqual(self.ui.apply(), VIDEO_CHANGED)
        self.assertTrue(self.settings.fullscreen)

    def test_resolution_and_fps_limit(self):
        self.ui.switch_tab(index=1)
        self.ui.move(+1)                                          # Resolution
        self.ui.adjust(+1)
        self.assertEqual(self.ui.settings.resolution, (1280, 720))
        self.assertEqual(self.ui.apply(), VIDEO_CHANGED)
        self.assertEqual(self.settings.resolution, (1280, 720))
        self.ui.move(+2)                                          # FPS Limit: no new window needed
        self.ui.adjust(+1)
        self.assertEqual(self.ui.apply(), APPLIED)
        self.assertEqual(self.settings.fps_cap, 120)

    def test_video_settings_are_saved(self):
        self.settings.display_mode, self.settings.resolution = "borderless", (1600, 900)
        self.settings.vsync, self.settings.fps_cap = True, 0
        self.settings.save(self.path)
        loaded = Settings.load(self.path)
        self.assertEqual((loaded.display_mode, loaded.resolution, loaded.vsync, loaded.fps_cap),
                         ("borderless", (1600, 900), True, 0))

    def test_window_never_bigger_than_the_desktop(self):
        self.settings.resolution = (2560, 1440)
        self.assertEqual(self.settings.window_size((1920, 1080)), (1920, 1080))

    def test_screen_shake_toggle(self):
        self.ui.switch_tab(index=1)
        self.ui.move(+5)
        self.assertIsNone(self.ui.activate())
        self.assertFalse(self.ui.settings.screen_shake)

    def test_rebinding_a_key(self):
        self.ui.switch_tab(index=2)
        self.ui.move(+4)                       # Attack
        self.ui.activate()
        self.assertTrue(self.ui.rebinding)
        self.ui.press_key_while_rebinding("l")
        self.assertFalse(self.ui.rebinding)
        self.assertEqual(self.ui.settings.key_for("attack"), "l")

    def test_escape_cancels_rebinding(self):
        self.ui.switch_tab(index=2)
        self.ui.activate()
        self.ui.press_key_while_rebinding("escape")
        self.assertEqual(self.settings.key_for("move_up"), "w")

    def test_reset_keys_row(self):
        self.ui.settings.rebind("attack", "l")
        self.ui.switch_tab(index=2)
        self.ui.row = self.ui.rows().index(RESET_ROW)
        self.ui.activate()
        self.assertEqual(self.ui.settings.key_for("attack"), "j")

    def test_apply_saves_the_changes(self):
        self.ui.settings.sfx_volume = 10
        self.assertTrue(self.ui.dirty)
        self.assertEqual(self.ui.apply(), APPLIED)
        self.assertEqual(self.settings.sfx_volume, 10)
        self.assertEqual(Settings.load(self.path).sfx_volume, 10)
        self.assertFalse(self.ui.dirty)
        self.assertIsNone(self.ui.apply(), "nothing left to apply")

    def test_cancel_and_escape_forget_unapplied_changes(self):
        self.ui.settings.sfx_volume = 10
        self.ui.settings.display_mode = "fullscreen"
        self.assertEqual(self.ui.cancel(), BACK)
        self.assertEqual((self.settings.sfx_volume, self.settings.display_mode), (70, "windowed"))
        self.assertFalse(os.path.exists(self.path), "nothing saved")
        self.ui.settings.sfx_volume = 5
        self.assertEqual(self.ui.handle_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_ESCAPE, mod=0)),
                         BACK)
        self.assertEqual(self.settings.sfx_volume, 70)

    def test_apply_and_cancel_buttons_by_mouse_and_keyboard(self):
        from ui.settings_screen import APPLY_RECT, CANCEL_RECT
        self.ui.settings.music_volume = 20
        x, y, w, h = APPLY_RECT
        self.assertEqual(self.ui._click((x + w // 2, y + h // 2)), APPLIED)
        self.assertEqual(self.settings.music_volume, 20)
        self.ui.settings.music_volume = 90
        self.ui.button, self.ui.row = None, 0   # back on the first row
        self.ui.move(+3)                        # past the 3 volume rows: APPLY
        self.assertEqual(self.ui.button, 0)
        self.ui.adjust(+1)                      # -> CANCEL
        self.assertEqual(self.ui.activate(), BACK)
        self.assertEqual(self.settings.music_volume, 20)
        x, y, w, h = CANCEL_RECT
        self.assertEqual(self.ui._click((x + w // 2, y + h // 2)), BACK)

    def test_window_plan_for_each_mode(self):
        s = Settings()
        s.resolution = (1920, 1080)
        desktop = (1920, 1080)
        s.display_mode = "fullscreen"
        self.assertEqual(s.window_plan(desktop, {(1920, 1080), (1280, 720)}), ((1920, 1080), "fullscreen"))
        s.resolution = (2560, 1440)                 # the screen can't do it: use the desktop size
        self.assertEqual(s.window_plan(desktop, {(1920, 1080)})[0], (1920, 1080))
        s.display_mode = "borderless_fullscreen"
        self.assertEqual(s.window_plan(desktop)[0], (1920, 1080))
        s.display_mode, s.resolution = "windowed", (1280, 720)
        self.assertEqual(s.window_plan(desktop)[0], (1280, 720))
        s.resolution = (1920, 1080)                 # a framed window leaves room for the title bar
        w, h = s.window_plan(desktop)[0]
        self.assertLessEqual(h, 1000)

    def test_click_on_slider_sets_volume(self):
        tx, ty, tw, th = self.ui.slider_track(0)
        self.ui._click((tx + tw // 2, ty + th // 2))
        self.assertEqual(self.ui.settings.master_volume, 50)
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
