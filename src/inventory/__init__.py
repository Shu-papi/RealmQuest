"""
RealmQuest inventory package (weapon slots, class-locked weapons).

    from inventory import Inventory, make_weapon

    inv = Inventory("mage")
    picked_up, dropped = inv.pick_up(make_weapon("fire_wand"))
    inv.switch_next()
    print(inv.current.name)

Run the tests from the repo root:
    python -m unittest discover -s src/inventory/tests
"""
from .weapons import (
    Weapon, make_weapon, list_weapons,
    WARRIOR, MAGE, ARCHER, CLASSES, STARTING_WEAPONS,
)
from .inventory import Inventory, DEFAULT_SLOTS
