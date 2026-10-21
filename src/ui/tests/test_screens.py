"""
Checks the class select screen and the inventory screen.
Run from the repo root:  python -m unittest discover -s src/ui/tests
"""
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

import ui.assets as assets
from inventory import Inventory, make_weapon, CLASSES
from ui.class_info import CLASS_ORDER, CLASS_INFO, starting_weapon, portrait_file
from ui.class_select import ClassSelect, START, BACK, START_RECT, BACK_RECT
from ui.inventory_screen import InventoryScreen


class TestClassInfo(unittest.TestCase):
    def test_every_class_is_described(self):
        self.assertEqual(sorted(CLASS_ORDER), sorted(CLASSES))
        for cls in CLASSES:
            for key in ("name", "role", "range", "description", "stats"):
                self.assertIn(key, CLASS_INFO[cls])

    def test_starting_weapon_matches_class(self):
        for cls in CLASSES:
            self.assertEqual(starting_weapon(cls).weapon_class, cls)

    def test_every_class_has_a_picture(self):
        for cls in CLASSES:
            self.assertTrue(os.path.exists(os.path.join(assets.UI_ASSETS_DIR, portrait_file(cls))))


class TestClassSelect(unittest.TestCase):
    def setUp(self):
        self.picker = ClassSelect()

    def test_starts_on_warrior_and_moves(self):
        self.assertEqual(self.picker.chosen, "warrior")
        self.picker.move(+1)
        self.assertEqual(self.picker.chosen, "mage")
        self.picker.move(-2)
        self.assertEqual(self.picker.chosen, "archer")

    def test_click_card_then_start(self):
        x, y, w, h = self.picker.card_rects()[2]
        self.assertIsNone(self.picker.click((x + 10, y + 10)))
        self.assertEqual(self.picker.chosen, "archer")
        self.assertEqual(self.picker.click((START_RECT[0] + 5, START_RECT[1] + 5)), START)

    def test_back_button(self):
        self.assertEqual(self.picker.click((BACK_RECT[0] + 5, BACK_RECT[1] + 5)), BACK)

    def test_cards_fit_on_screen(self):
        for x, y, w, h in self.picker.card_rects():
            self.assertGreaterEqual(x, 0)
            self.assertLessEqual(x + w, self.picker.width)


class TestInventoryScreen(unittest.TestCase):
    def setUp(self):
        self.inv = Inventory("mage")
        self.inv.pick_up(make_weapon("fire_wand"))
        self.inv.select_slot(0)                    # staff in hand, wand in slot 2
        self.window = InventoryScreen(self.inv)

    def test_opens_looking_at_weapon_in_hand(self):
        self.assertEqual(self.window.viewing, 0)
        self.assertEqual(self.window.equip_state(), "equipped")

    def test_equip_another_slot(self):
        self.window.look_at(1)
        self.assertEqual(self.window.equip_state(), "equip")
        self.assertTrue(self.window.equip())
        self.assertEqual(self.inv.current.name, "Fire Wand")

    def test_empty_slot_cannot_be_equipped(self):
        self.window.look_at(2)
        self.assertEqual(self.window.equip_state(), "empty")
        self.assertFalse(self.window.equip())
        self.assertEqual(self.inv.current.name, "Apprentice Staff")

    def test_clicking_a_slot_twice_equips_it(self):
        x, y, w, h = self.window.slot_rects()[1]
        self.window.click((x + 5, y + 5))
        self.assertEqual(self.inv.current_index, 0)            # first click: just look
        self.window.click((x + 5, y + 5))
        self.assertEqual(self.inv.current_index, 1)            # second click: equip

    def test_move_wraps(self):
        self.window.move(-1)
        self.assertEqual(self.window.viewing, 2)


class TestDrawing(unittest.TestCase):
    def test_draw_both_screens_without_pictures(self):
        assets.ENABLED = False
        try:
            screen = pygame.Surface((960, 640))
            picker = ClassSelect()
            for _ in CLASS_ORDER:
                picker.draw(screen)
                picker.move(1)
            inv = Inventory("archer")
            window = InventoryScreen(inv)
            for i in range(3):
                window.look_at(i)
                window.draw(screen)
        finally:
            assets.ENABLED = True
            assets.clear_cache()


if __name__ == "__main__":
    unittest.main()
