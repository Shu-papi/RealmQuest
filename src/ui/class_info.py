"""
class_info.py - What the class select and inventory screens SAY about each class.

!!! PLACEHOLDER: the real stats, descriptions and pictures belong to the
!!! Characters & Skills team. When they have them, update this file (or point it
!!! at their code) and replace assets/ui/class_<name>.png with their art.

The UI only reads from here; it never decides game balance.
"""
from inventory import STARTING_WEAPONS, make_weapon

CLASS_ORDER = ["warrior", "mage", "archer"]

CLASS_INFO = {
    "warrior": {
        "name": "Warrior",
        "role": "Melee only",
        "range": "Melee",
        "description": "Tough and close-range. Swords, axes, greatswords.",
        "stats": {"hp": 7, "armor": 6, "energy": 160},        # PLACEHOLDER numbers
    },
    "mage": {
        "name": "Mage",
        "role": "Magic only",
        "range": "Magic",
        "description": "Fragile but powerful. Staffs and wands.",
        "stats": {"hp": 4, "armor": 4, "energy": 260},        # PLACEHOLDER numbers
    },
    "archer": {
        "name": "Archer",
        "role": "Ranged only",
        "range": "Ranged",
        "description": "Quick and keeps distance. Bows and crossbows.",
        "stats": {"hp": 5, "armor": 5, "energy": 200},        # PLACEHOLDER numbers
    },
}


def info(character_class):
    return CLASS_INFO[character_class]


def portrait_file(character_class):
    return f"class_{character_class}.png"


def badge_file(character_class):
    return f"badge_{character_class}.png"


def starting_weapon(character_class):
    return make_weapon(STARTING_WEAPONS[character_class])
