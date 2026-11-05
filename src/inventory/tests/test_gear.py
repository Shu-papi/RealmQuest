"""
Checks gear: items and rarities, equipping / swapping / selling, class-locked weapons,
stat totals, stat points, drops and the shop stock, and saving.
Run from the repo root:  python -m unittest discover -s src/inventory/tests
"""
import os
import random
import sys
import unittest

SRC = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if SRC not in sys.path:
    sys.path.insert(0, SRC)

from inventory.gear import (BAG_SIZE, BASES, SLOTS, Gear, Item, attr_stats, roll_drop,  # noqa: E402
                            shop_stock)


class Items(unittest.TestCase):
    def test_rarity_raises_stats_name_and_price(self):
        plain, epic = Item("steel_broadsword", 0), Item("steel_broadsword", 3)
        self.assertEqual(plain.name, "Steel Broadsword")
        self.assertEqual(epic.name, "Epic Steel Broadsword")
        self.assertGreater(epic.stats["atk"], plain.stats["atk"])
        self.assertGreater(epic.price, plain.price)
        self.assertLess(plain.sell_value, plain.price)

    def test_every_base_is_valid(self):
        for base, row in BASES.items():
            item = Item(base)
            self.assertIn(item.slot, SLOTS, base)
            self.assertTrue(item.stats, base)

    def test_save_round_trip_and_bad_data(self):
        item = Item("ruby_ring", 2)
        self.assertEqual(Item.from_dict(item.to_dict()), item)
        self.assertIsNone(Item.from_dict({"base": "no_such_thing"}))
        self.assertIsNone(Item.from_dict("junk"))


class Equipping(unittest.TestCase):
    def test_starts_with_the_class_weapon(self):
        for cls, base in (("warrior", "iron_sword"), ("mage", "oak_staff"), ("archer", "hunting_bow")):
            self.assertEqual(Gear(cls).equipped["weapon"].base, base)

    def test_equip_swaps_with_what_is_worn(self):
        g = Gear("warrior")
        g.add(Item("steel_broadsword"))
        self.assertTrue(g.equip(0))
        self.assertEqual(g.equipped["weapon"].base, "steel_broadsword")
        self.assertEqual([i.base for i in g.bag], ["iron_sword"])

    def test_weapons_are_class_locked_armor_is_not(self):
        g = Gear("mage")
        g.add(Item("iron_sword"))
        g.add(Item("chainmail"))
        self.assertFalse(g.equip(0), "a mage can't wield a sword")
        self.assertTrue(g.equip(1))
        self.assertEqual(g.equipped["armor"].base, "chainmail")

    def test_totals_and_unequip(self):
        g = Gear("archer")
        g.add(Item("iron_helm"))
        g.equip(0)
        t = g.totals()
        self.assertEqual(t["hp"], 8)
        self.assertEqual(t["aspd"], 4)
        self.assertTrue(g.unequip("helmet"))
        self.assertNotIn("hp", g.totals())

    def test_bag_fills_up_and_selling_pays(self):
        g = Gear("warrior")
        for _ in range(BAG_SIZE):
            self.assertTrue(g.add(Item("sandals")))
        self.assertFalse(g.add(Item("sandals")))
        self.assertFalse(g.unequip("weapon"), "no room to take it off")
        self.assertEqual(g.sell(0), Item("sandals").sell_value)
        self.assertEqual(len(g.bag), BAG_SIZE - 1)

    def test_compare_shows_the_change(self):
        g = Gear("warrior")
        diff = g.compare(Item("steel_broadsword"))
        self.assertEqual(diff["atk"], 1.0)
        self.assertEqual(diff["hp"], 4)

    def test_gear_save_round_trip(self):
        g = Gear("archer")
        g.add(Item("windwalkers", 4))
        g.equip(0)
        g.add(Item("chainmail", 1))
        back = Gear.from_dict(g.to_dict(), "archer")
        self.assertEqual(back.equipped["boots"], Item("windwalkers", 4))
        self.assertEqual(back.bag, [Item("chainmail", 1)])


class PointsDropsShop(unittest.TestCase):
    def test_stat_points(self):
        self.assertEqual(attr_stats({"vit": 2, "pow": 1, "agi": 2}), {"hp": 10, "atk": 0.5, "aspd": 6, "spd": 3.0})

    def test_drops_suit_the_hero(self):
        rng = random.Random(3)
        for _ in range(200):
            item = roll_drop(rng, "mage", tier=3)
            self.assertTrue(item.usable_by("mage"))
            self.assertIn(item.tier, (2, 3))

    def test_bosses_and_higher_tiers_drop_better(self):
        rng = random.Random(5)
        low = sum(roll_drop(rng, "warrior", 1).rarity for _ in range(600))
        high = sum(roll_drop(rng, "warrior", 4, luck=1.5).rarity for _ in range(600))
        self.assertGreater(high, low)

    def test_shop_stock_grows_with_the_story(self):
        early, late = shop_stock("archer", 0), shop_stock("archer", 3)
        self.assertEqual(len(early), 2 * len(SLOTS))
        self.assertEqual(max(i.tier for i in early), 1)
        self.assertEqual(max(i.tier for i in late), 4)
        self.assertTrue(all(i.usable_by("archer") for i in late))


if __name__ == "__main__":
    unittest.main()
