"""
class_info.py - What the class select and inventory screens SAY about each class.

The numbers come from the game itself (src/skills/classes.py and src/skills/skills.py),
so the cards always show what the hero really gets in the world.
The UI only reads from here; it never decides game balance.
"""
from inventory import STARTING_WEAPONS, make_weapon
from skills import classes as _classes
from skills.skills import skills_for

CLASS_ORDER = list(_classes.CLASS_ORDER)

_TEXT = {
    "warrior": {
        "role": "Steel and shield",
        "range": "Melee",
        "description": "Tough and close-range. Whirls through crowds and bashes foes senseless.",
    },
    "mage": {
        "role": "Fire and frost",
        "range": "Magic",
        "description": "Fragile but deadly. Burns, freezes and calls meteors from the sky.",
    },
    "archer": {
        "role": "Swift and sharp",
        "range": "Ranged",
        "description": "The quickest hero. Volleys, piercing shots and a rain of arrows.",
    },
}


def _build(cls):
    st = _classes.stats(cls)
    bars = {name: mx for name, mx, _regen in st["bars"]}
    resource = st["skill_resource"]
    return {
        "name": st["name"],
        **_TEXT[cls],
        "stats": {"hp": st["hp"], "stamina": bars["stamina"], resource: bars[resource],
                  "speed": int(round(st["speed"] * 100))},
        "resource": resource,                     # "mana" or "energy": what the skills cost
        "bars": [name for name, _mx, _r in st["bars"]],
        "skills": [(s.slot, s.name, s.desc) for s in skills_for(cls)],
    }


CLASS_INFO = {cls: _build(cls) for cls in CLASS_ORDER}


def info(character_class):
    return CLASS_INFO[character_class]


def portrait_file(character_class):
    return f"class_{character_class}.png"


def badge_file(character_class):
    return f"badge_{character_class}.png"


def starting_weapon(character_class):
    return make_weapon(STARTING_WEAPONS[character_class])
