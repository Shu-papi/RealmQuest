"""
classes.py - Game balance for the three hero classes (Warrior, Mage, Archer).

This is the one place the numbers live. The game (src/maps) reads it to build the
hero, and the class select screen (src/ui/class_info.py) reads it to show the cards.

Each class has:
    hp            base max HP (levels, armour and quest rewards add to it)
    speed         walk-speed multiplier (1.0 = the old hero)
    dmg_bonus     extra damage on the basic attack
    swing_cd      seconds between basic attacks
    swing_color   colour of the basic attack's slash
    weapon        what the basic attack is called on the HUD
    bars          the two resource bars, in HUD order: (name, max, regen per second)
                  every class has "stamina" (dash costs it); skills cost "mana" or "energy"
    skill_resource  which bar the skills spend
    energy_on_hit   energy gained per point of basic-attack damage (Warrior / Archer)
"""

CLASS_ORDER = ["warrior", "mage", "archer"]

DASH_STAMINA = 25          # every dash costs this much stamina

CLASS_STATS = {
    "warrior": {
        "name": "Warrior", "hp": 48, "speed": 1.0, "dmg_bonus": 1,
        "swing_cd": 0.32, "swing_color": (236, 240, 255), "weapon": "Sword",
        "bars": [("stamina", 100, 24.0), ("energy", 100, 4.0)],
        "skill_resource": "energy", "energy_on_hit": 4.0,
    },
    "mage": {
        "name": "Mage", "hp": 34, "speed": 1.05, "dmg_bonus": 0,
        "swing_cd": 0.36, "swing_color": (196, 150, 255), "weapon": "Staff",
        "bars": [("mana", 120, 9.0), ("stamina", 80, 22.0)],
        "skill_resource": "mana", "energy_on_hit": 0.0,
    },
    "archer": {
        "name": "Archer", "hp": 40, "speed": 1.12, "dmg_bonus": 0,
        "swing_cd": 0.24, "swing_color": (170, 240, 160), "weapon": "Dagger",
        "bars": [("stamina", 110, 28.0), ("energy", 100, 5.0)],
        "skill_resource": "energy", "energy_on_hit": 3.0,
    },
}

BAR_COLORS = {
    "hp": (214, 52, 52),
    "stamina": (226, 190, 60),
    "mana": (70, 120, 236),
    "energy": (236, 128, 40),
}


def stats(character_class):
    return CLASS_STATS.get(character_class, CLASS_STATS["warrior"])
