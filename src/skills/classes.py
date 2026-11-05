"""
classes.py - Game balance for the three hero classes (Warrior, Mage, Archer).

This is the one place the numbers live. The game (src/maps) reads it to build the
hero, and the class select screen (src/ui/class_info.py) reads it to show the cards.

Each class has:
    hp            base max HP (levels, armour and quest rewards add to it)
    speed         walk-speed multiplier (1.0 = the old hero)
    dmg_bonus     extra damage on the basic attack
    swing_cd      seconds between basic attacks (before Attack Speed from gear and Agility)
    weapon        what the basic attack is called on the HUD
    attack        the basic attack: "melee" (Knight's sword, shown by his spritesheet only),
                  "bolt" (Mage: long-range arcane bolt that costs mana) or "arrow" (Elf Archer).
                  speed / range in px; release = how far into the attack animation (0..1)
                  the shot leaves, so it matches the sprite's cast / bow-release frame
    bars          the two resource bars, in HUD order: (name, max, regen per second)
                  every class has "stamina" (dash costs it); skills cost "mana" or "energy"
    skill_resource  which bar the skills spend
    energy_on_hit   energy gained per basic attack that lands (Warrior / Archer)
"""

CLASS_ORDER = ["warrior", "mage", "archer"]

DASH_STAMINA = 25          # every dash costs this much stamina

CLASS_STATS = {
    "warrior": {
        "name": "Warrior", "hp": 48, "speed": 1.0, "dmg_bonus": 1,
        "swing_cd": 0.55, "swing_color": (236, 240, 255), "weapon": "Sword",
        "attack": {"kind": "melee"},
        "bars": [("stamina", 100, 24.0), ("energy", 100, 4.0)],
        "skill_resource": "energy", "energy_on_hit": 8.0,
    },
    "mage": {
        "name": "Mage", "hp": 34, "speed": 1.05, "dmg_bonus": 0,
        "swing_cd": 0.65, "swing_color": (196, 150, 255), "weapon": "Arcane Bolt",
        "attack": {"kind": "bolt", "resource": "mana", "cost": 6, "speed": 560, "range": 560,
                   "release": 0.45},
        "bars": [("mana", 120, 9.0), ("stamina", 80, 22.0)],
        "skill_resource": "mana", "energy_on_hit": 0.0,
    },
    "archer": {
        "name": "Archer", "hp": 40, "speed": 1.12, "dmg_bonus": 0,
        "swing_cd": 0.5, "swing_color": (170, 240, 160), "weapon": "Bow",
        "attack": {"kind": "arrow", "speed": 760, "range": 620, "release": 0.3},
        "bars": [("stamina", 110, 28.0), ("energy", 100, 5.0)],
        "skill_resource": "energy", "energy_on_hit": 5.0,
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


# ======================================================================================================
# CONFIG FILES: config/characters/<class>.toml set the numbers above (src/balance.py). Their [skills] table is
# read by skills.py; the numbers every class shares (dash, potions ...) are in config/characters/hero.toml.
# ======================================================================================================
try:
    import balance as _balance                              # src/ is on the path
except ImportError:
    try:
        from src import balance as _balance
    except ImportError:                                     # (no config reader: the defaults above)
        _balance = None

_STATS = ("name", "hp", "speed", "dmg_bonus", "swing_cd", "weapon", "energy_on_hit")
_STAT_DOCS = {
    "name": "Shown on the class card and the HUD.",
    "hp": "Base health (levels, armour and quest rewards add to it).",
    "speed": "Walk speed multiplier (1.0 = normal).",
    "dmg_bonus": "Extra damage on every basic attack (on top of hero.toml sword_damage).",
    "swing_cd": "Seconds between basic attacks (gear Attack Speed and Agility make it shorter).",
    "weapon": "What the basic attack is called on the HUD.",
    "energy_on_hit": "Energy gained per basic attack that lands (a swing that hits, an arrow that hits).",
    "attack": "The basic attack: cost (mana per bolt), speed and range (pixels), release (0-1: how far into "
              "the attack animation the shot leaves).",
    "bars": "Resource bars: name = [maximum, refill per second]. Stamina pays for dashes; skills cost mana or energy.",
}


def _stat(cls, key):
    return _balance.Prop(lambda: CLASS_STATS[cls][key], lambda v: CLASS_STATS[cls].__setitem__(key, v))


def _attack(cls):
    def get():
        return {k: v for k, v in CLASS_STATS[cls]["attack"].items() if k not in ("kind", "resource")}

    def put(table):
        CLASS_STATS[cls]["attack"].update(table)
    return _balance.Prop(get, put)


def _bars(cls):
    def get():
        return {name: [mx, regen] for name, mx, regen in CLASS_STATS[cls]["bars"]}

    def put(table):
        CLASS_STATS[cls]["bars"] = [(name, *table[name]) for name, _mx, _r in CLASS_STATS[cls]["bars"]]
    return _balance.Prop(get, put)


if _balance is not None:
    for _cls in CLASS_ORDER:
        _fields = {k: _stat(_cls, k) for k in _STATS}
        if len(CLASS_STATS[_cls]["attack"]) > 1:            # (the Warrior's sword has nothing to tune)
            _fields["attack"] = _attack(_cls)
        _fields["bars"] = _bars(_cls)
        _balance.declare("characters", _cls, CLASS_STATS[_cls]["name"].upper(),
                         "A hero class. Its skills are in [skills] at the bottom; numbers every class shares are "
                         "in hero.toml.", None, _fields, docs=_STAT_DOCS, skip=("skills",))
