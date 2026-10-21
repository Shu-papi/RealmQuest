"""
Checks the weapon slots display: pick-up messages, class-lock warning, switching, pictures.
Run from the repo root:  python -m unittest discover -s src/ui/tests
"""
import os
import sys
import types
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

REAL_PYGAME = hasattr(pygame, "get_init")

import ui.assets as assets
from inventory import Inventory, make_weapon, list_weapons, CLASSES
from ui.settings_data import Settings
from ui.weapon_bar import WeaponBar, BAD, GOOD


class TestWeaponBar(unittest.TestCase):
    def setUp(self):
        self.settings = Settings()
        self.inv = Inventory("warrior")
        self.bar = WeaponBar(self.inv, self.settings)

    def test_pick_up_shows_message(self):
        picked_up, dropped = self.bar.pick_up(make_weapon("battle_axe"))
        self.assertTrue(picked_up)
        self.assertEqual(self.bar.message, "Picked up Battle Axe")
        self.assertEqual(self.bar.message_color, GOOD)

    def test_wrong_class_says_who_can_use_it(self):
        picked_up, _ = self.bar.pick_up(make_weapon("short_bow"))
        self.assertFalse(picked_up)
        self.assertEqual(self.bar.message, "Archers only!")
        self.assertEqual(self.bar.message_color, BAD)

    def test_full_inventory_says_swapped(self):
        self.bar.pick_up(make_weapon("battle_axe"))
        self.bar.pick_up(make_weapon("greatsword"))
        _, dropped = self.bar.pick_up(make_weapon("iron_sword"))
        self.assertEqual(self.bar.message, f"Swapped {dropped.name} for Iron Sword")

    def test_prompt_uses_the_players_interact_key(self):
        self.settings.rebind("interact", "f")
        self.bar.set_nearby(make_weapon("battle_axe"))
        self.assertEqual(self.bar.prompt(), "Press F to pick up Battle Axe")

    def test_prompt_warns_about_wrong_class(self):
        self.bar.set_nearby(make_weapon("fire_wand"))
        self.assertIn("Mages only", self.bar.prompt())

    def test_no_prompt_when_nothing_nearby(self):
        self.assertEqual(self.bar.prompt(), "")

    def test_picking_up_clears_the_prompt(self):
        axe = make_weapon("battle_axe")
        self.bar.set_nearby(axe)
        self.bar.pick_up(axe)
        self.assertIsNone(self.bar.nearby)

    def test_switching_pops_the_slot(self):
        self.bar.pick_up(make_weapon("battle_axe"))
        self.bar.update(1.0)                      # let the pick-up pop finish
        self.bar.switch_next()
        self.assertGreater(self.bar.pop, 0)
        self.assertEqual(self.inv.current.name, "Iron Sword")

    def test_slots_fit_on_screen(self):
        for x, y, w, h in self.bar.slot_rects() + [self.bar.info_rect()]:
            self.assertGreaterEqual(x, 0)
            self.assertLessEqual(x + w, self.bar.screen_w)
            self.assertLessEqual(y + h, self.bar.screen_h)

    def test_keys_switch_weapons(self):
        if not REAL_PYGAME:
            self.skipTest("real pygame needed for key names")
        self.bar.pick_up(make_weapon("battle_axe"))
        self.bar.handle_event(types.SimpleNamespace(type=pygame.KEYDOWN, key=pygame.K_1))
        self.assertEqual(self.inv.current_index, 0)
        self.bar.handle_event(types.SimpleNamespace(type=pygame.KEYDOWN, key=pygame.K_q))
        self.assertEqual(self.inv.current_index, 1)

    def test_draw_without_pictures(self):
        assets.ENABLED = False
        try:
            self.bar.set_nearby(make_weapon("short_bow"))
            self.bar.pick_up(make_weapon("battle_axe"))
            self.bar.draw(pygame.Surface((960, 640)))
            self.inv.drop_current()
            self.bar.draw(pygame.Surface((960, 640)))
        finally:
            assets.ENABLED = True
            assets.clear_cache()


class TestWeaponPictures(unittest.TestCase):
    def test_every_weapon_has_an_icon(self):
        for weapon_id in list_weapons():
            path = os.path.join(assets.UI_ASSETS_DIR, f"weapon_{weapon_id}.png")
            self.assertTrue(os.path.exists(path), path)

    def test_every_class_has_a_badge_and_slots_exist(self):
        for name in [f"badge_{c}.png" for c in CLASSES] + ["slot.png", "slot_selected.png"]:
            self.assertTrue(os.path.exists(os.path.join(assets.UI_ASSETS_DIR, name)), name)


if __name__ == "__main__":
    unittest.main()
