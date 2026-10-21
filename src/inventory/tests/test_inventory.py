"""
Checks the weapon inventory follows the game plan.
Run from the repo root:  python -m unittest discover -s src/inventory/tests
"""
import os
import sys
import unittest

SRC_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)

from inventory import Inventory, Weapon, make_weapon, list_weapons, CLASSES


class TestStarting(unittest.TestCase):
    def test_has_at_least_three_slots(self):
        for cls in CLASSES:
            self.assertGreaterEqual(len(Inventory(cls).slots), 3)

    def test_each_class_starts_with_its_own_weapon(self):
        for cls in CLASSES:
            inv = Inventory(cls)
            self.assertIsNotNone(inv.current)
            self.assertEqual(inv.current.weapon_class, cls)

    def test_unknown_class_is_rejected(self):
        with self.assertRaises(ValueError):
            Inventory("ninja")


class TestClassLock(unittest.TestCase):
    def test_warrior_cannot_pick_up_bow(self):
        inv = Inventory("warrior")
        picked_up, dropped = inv.pick_up(make_weapon("short_bow"))
        self.assertFalse(picked_up)
        self.assertIsNone(dropped)
        self.assertEqual(len(inv.weapons()), 1)

    def test_mage_cannot_pick_up_sword(self):
        picked_up, _ = Inventory("mage").pick_up(make_weapon("iron_sword"))
        self.assertFalse(picked_up)

    def test_archer_can_pick_up_crossbow(self):
        picked_up, _ = Inventory("archer").pick_up(make_weapon("crossbow"))
        self.assertTrue(picked_up)


class TestPickUpAndSwap(unittest.TestCase):
    def test_pick_up_fills_free_slot_and_equips_it(self):
        inv = Inventory("warrior")
        axe = make_weapon("battle_axe")
        inv.pick_up(axe)
        self.assertIs(inv.current, axe)
        self.assertEqual(len(inv.weapons()), 2)

    def test_full_inventory_swaps_with_held_weapon(self):
        inv = Inventory("warrior")
        inv.pick_up(make_weapon("battle_axe"))
        inv.pick_up(make_weapon("greatsword"))
        self.assertTrue(inv.is_full())

        held = inv.current
        new_sword = make_weapon("iron_sword")
        picked_up, dropped = inv.pick_up(new_sword)
        self.assertTrue(picked_up)
        self.assertIs(dropped, held)          # old weapon goes on the floor
        self.assertIs(inv.current, new_sword)
        self.assertEqual(len(inv.weapons()), 3)

    def test_drop_current_empties_slot(self):
        inv = Inventory("mage")
        dropped = inv.drop_current()
        self.assertEqual(dropped.weapon_class, "mage")
        self.assertIsNone(inv.current)


class TestSwitching(unittest.TestCase):
    def setUp(self):
        self.inv = Inventory("archer")                      # slot 0: Short Bow
        self.inv.pick_up(make_weapon("crossbow"))           # slot 1
        self.inv.select_slot(0)

    def test_switch_next_and_wraps_around(self):
        self.assertEqual(self.inv.switch_next().name, "Crossbow")
        self.assertEqual(self.inv.switch_next().name, "Short Bow")   # skips empty slot 2

    def test_switch_prev(self):
        self.assertEqual(self.inv.switch_prev().name, "Crossbow")

    def test_select_empty_slot_does_nothing(self):
        self.inv.select_slot(2)
        self.assertEqual(self.inv.current.name, "Short Bow")

    def test_switch_with_one_weapon_stays_put(self):
        inv = Inventory("warrior")
        self.assertEqual(inv.switch_next().name, "Iron Sword")


class TestWeapons(unittest.TestCase):
    def test_every_starter_weapon_builds(self):
        for weapon_id in list_weapons():
            self.assertIn(make_weapon(weapon_id).weapon_class, CLASSES)

    def test_make_weapon_remembers_its_id(self):
        self.assertEqual(make_weapon("fire_wand").weapon_id, "fire_wand")

    def test_every_weapon_has_a_description(self):
        for weapon_id in list_weapons():
            self.assertTrue(make_weapon(weapon_id).description, weapon_id)

    def test_make_weapon_gives_fresh_copies(self):
        self.assertIsNot(make_weapon("iron_sword"), make_weapon("iron_sword"))

    def test_bad_weapon_class_is_rejected(self):
        with self.assertRaises(ValueError):
            Weapon("Laser Gun", "robot", "gun", 99)


if __name__ == "__main__":
    unittest.main()
