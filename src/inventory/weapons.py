"""
weapons.py - What a weapon IS, plus a few starter weapons for testing.

Every weapon belongs to ONE class. The game plan says:
  * warrior -> melee only (sword, axe, greatsword...)
  * mage    -> magic only (staff, wand, tome...)
  * archer  -> ranged only (bow, crossbow...)

The numbers below (damage, energy cost) are placeholders. The Characters &
Skills team can change them later without touching the inventory code.
"""

WARRIOR = "warrior"
MAGE = "mage"
ARCHER = "archer"
CLASSES = (WARRIOR, MAGE, ARCHER)


class Weapon:
    def __init__(self, name, weapon_class, kind, damage, energy_cost=0, weapon_id=None,
                 description=""):
        if weapon_class not in CLASSES:
            raise ValueError(
                f"{name}: weapon_class must be one of {CLASSES}, got {weapon_class!r}"
            )
        self.name = name                    # shown in the HUD, e.g. "Iron Sword"
        self.weapon_class = weapon_class    # who can use it: warrior / mage / archer
        self.kind = kind                    # sword, axe, staff, bow... (for icons later)
        self.damage = damage
        self.energy_cost = energy_cost      # energy used per attack (blue bar)
        self.weapon_id = weapon_id          # e.g. "iron_sword"; the UI finds its icon with this
        self.description = description      # one short line for the inventory screen

    def usable_by(self, character_class):
        return self.weapon_class == character_class

    def __repr__(self):
        return f"Weapon({self.name!r}, {self.weapon_class})"


# Starter weapons. make_weapon("iron_sword") gives you a FRESH copy each time.
#          id               name               class    kind          dmg  energy
_WEAPON_DATA = {
    "iron_sword":      ("Iron Sword",      WARRIOR, "sword",      10, 0),
    "battle_axe":      ("Battle Axe",      WARRIOR, "axe",        14, 0),
    "greatsword":      ("Greatsword",      WARRIOR, "greatsword", 18, 1),
    "apprentice_staff": ("Apprentice Staff", MAGE,  "staff",       8, 2),
    "fire_wand":       ("Fire Wand",       MAGE,    "wand",       12, 4),
    "short_bow":       ("Short Bow",       ARCHER,  "bow",         7, 1),
    "crossbow":        ("Crossbow",        ARCHER,  "crossbow",   11, 2),
}

# One short line each, shown on the inventory screen. Placeholder text: change freely.
_DESCRIPTIONS = {
    "iron_sword":       "A simple, reliable blade. Good for beginners.",
    "battle_axe":       "Slow, heavy swings that hit hard.",
    "greatsword":       "A huge two-handed blade. Costs a little energy.",
    "apprentice_staff": "A student's staff with a small blue crystal.",
    "fire_wand":        "Shoots bolts of fire. Hungry for energy.",
    "short_bow":        "Light and quick. Shoots from a safe distance.",
    "crossbow":         "Powerful bolts, slower to reload.",
}

# The weapon each class starts a run with.
STARTING_WEAPONS = {
    WARRIOR: "iron_sword",
    MAGE: "apprentice_staff",
    ARCHER: "short_bow",
}


def make_weapon(weapon_id):
    if weapon_id not in _WEAPON_DATA:
        raise KeyError(f"No weapon called {weapon_id!r}. Known: {list_weapons()}")
    name, weapon_class, kind, damage, energy_cost = _WEAPON_DATA[weapon_id]
    return Weapon(name, weapon_class, kind, damage, energy_cost, weapon_id=weapon_id,
                  description=_DESCRIPTIONS.get(weapon_id, ""))


def list_weapons():
    return sorted(_WEAPON_DATA)
