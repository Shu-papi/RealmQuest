"""
gear.py - Equipment the hero wears, the bag that holds the rest, and stat points.

    from inventory.gear import Gear, Item, roll_drop, shop_stock, attr_stats

    gear = Gear("mage")                       # starts with the class's starter weapon equipped
    gear.add(roll_drop(random.Random(), "mage", tier=2))
    gear.equip(0)                              # bag slot 0 -> its equipment slot (swaps)
    gear.totals()                              # {"atk": 2.6, "hp": 12, ...}

Five equipment slots: weapon, helmet, armor, boots, trinket. Weapons belong to one class
(Warrior swords, Mage staves, Archer bows); everything else fits every hero.
An item is just (base id, rarity): its name, stats and price come from the tables below,
so saves stay tiny and the numbers can be rebalanced without breaking them.

Stat keys
    hp     max HP                    def    defense (damage taken x 20 / (20 + def))
    atk    attack damage             crit   crit chance %, a crit hits twice as hard
    aspd   attack speed %            spd    move speed %
    res    max mana / energy         regen  mana / energy per second

No pygame here on purpose: pure logic, easy to test.
"""
from __future__ import annotations

import random

SLOTS = ("weapon", "helmet", "armor", "boots", "trinket")
SLOT_NAMES = {"weapon": "Weapon", "helmet": "Helmet", "armor": "Armor", "boots": "Boots",
              "trinket": "Trinket"}
BAG_SIZE = 24

#            name         colour            stat multiplier  price multiplier
RARITIES = [("Common",    (210, 210, 210), 1.0, 1.0),
            ("Uncommon",  (110, 222, 110), 1.3, 1.6),
            ("Rare",      (96, 166, 255),  1.7, 2.6),
            ("Epic",      (204, 112, 255), 2.2, 4.0),
            ("Legendary", (255, 170, 60),  2.8, 6.0)]

STAT_ORDER = ("hp", "atk", "def", "aspd", "spd", "crit", "res", "regen")
STAT_LABELS = {"hp": "Max HP", "atk": "Attack", "def": "Defense", "aspd": "Attack Speed",
               "spd": "Move Speed", "crit": "Crit Chance", "res": "Max {res}", "regen": "{res} Regen"}
PERCENT = {"aspd", "spd", "crit"}
DECIMAL = {"atk", "regen"}


def format_stat(key, value, resource="Mana", sign=True):
    """'+2.5 Attack', '+10% Move Speed' ... (resource names the Mage's / others' bar)."""
    label = STAT_LABELS[key].format(res=resource)
    num = ("%+.1f" if sign else "%.1f") % value if key in DECIMAL else ("%+d" if sign else "%d") % round(value)
    if key in PERCENT:
        num += "%"
    elif key == "regen":
        num += "/s"
    return num, label


# --------------------------------------------------------------------------- the items
# id: (name, slot, class or None, icon kind, tier 1-4, stats, base price)
BASES = {
    # Warrior swords
    "iron_sword":      ("Iron Sword",        "weapon", "warrior", "sword",      1, {"atk": 1.0}, 40),
    "steel_broadsword": ("Steel Broadsword", "weapon", "warrior", "sword",      2, {"atk": 2.0, "hp": 4}, 110),
    "knight_longsword": ("Knight's Longsword", "weapon", "warrior", "greatsword", 3, {"atk": 3.5, "hp": 8}, 240),
    "veilbreaker":     ("Veilbreaker",       "weapon", "warrior", "greatsword", 4, {"atk": 5.0, "hp": 10, "aspd": 5}, 420),
    # Mage staves
    "oak_staff":       ("Oak Staff",         "weapon", "mage",    "staff",      1, {"atk": 1.0, "res": 10}, 40),
    "crystal_staff":   ("Crystal Staff",     "weapon", "mage",    "staff",      2, {"atk": 2.0, "res": 15}, 110),
    "archmage_staff":  ("Archmage Staff",    "weapon", "mage",    "wand",       3, {"atk": 3.5, "res": 20, "regen": 1.0}, 240),
    "staff_of_veil":   ("Staff of the Veil", "weapon", "mage",    "wand",       4, {"atk": 5.0, "res": 30, "regen": 2.0}, 420),
    # Archer bows
    "hunting_bow":     ("Hunting Bow",       "weapon", "archer",  "bow",        1, {"atk": 1.0, "aspd": 4}, 40),
    "recurve_bow":     ("Recurve Bow",       "weapon", "archer",  "bow",        2, {"atk": 2.0, "aspd": 6}, 110),
    "elven_longbow":   ("Elven Longbow",     "weapon", "archer",  "crossbow",   3, {"atk": 3.5, "aspd": 8, "crit": 3}, 240),
    "veilstring_bow":  ("Veilstring Bow",    "weapon", "archer",  "crossbow",   4, {"atk": 5.0, "aspd": 10, "crit": 5}, 420),
    # Helmets
    "leather_cap":     ("Leather Cap",       "helmet", None, "helmet", 1, {"hp": 4, "def": 1}, 30),
    "iron_helm":       ("Iron Helm",         "helmet", None, "helmet", 2, {"hp": 8, "def": 2}, 90),
    "knight_helm":     ("Knight Helm",       "helmet", None, "helmet", 3, {"hp": 12, "def": 3}, 200),
    "crown_of_dawn":   ("Crown of Dawn",     "helmet", None, "crown",  4, {"hp": 16, "def": 4, "res": 10}, 360),
    # Body armor
    "padded_vest":     ("Padded Vest",       "armor",  None, "armor",  1, {"hp": 6, "def": 1}, 35),
    "chainmail":       ("Chainmail",         "armor",  None, "armor",  2, {"hp": 12, "def": 2}, 100),
    "plate_armor":     ("Plate Armor",       "armor",  None, "armor",  3, {"hp": 18, "def": 4}, 220),
    "veilguard_plate": ("Veilguard Plate",   "armor",  None, "armor",  4, {"hp": 26, "def": 6}, 400),
    # Boots
    "sandals":         ("Traveler's Sandals", "boots", None, "boots",  1, {"spd": 4}, 30),
    "leather_boots":   ("Leather Boots",     "boots",  None, "boots",  2, {"spd": 6, "def": 1}, 90),
    "swift_boots":     ("Swift Boots",       "boots",  None, "boots",  3, {"spd": 9, "aspd": 4}, 200),
    "windwalkers":     ("Windwalkers",       "boots",  None, "boots",  4, {"spd": 12, "aspd": 6, "def": 1}, 360),
    # Trinkets
    "copper_ring":     ("Copper Ring",       "trinket", None, "ring",  1, {"atk": 0.5, "crit": 2}, 35),
    "silver_ring":     ("Silver Ring",       "trinket", None, "ring",  2, {"atk": 1.0, "crit": 3}, 100),
    "ruby_ring":       ("Ruby Ring",         "trinket", None, "ring",  3, {"atk": 1.5, "crit": 5, "hp": 6}, 220),
    "veil_amulet":     ("Veil Amulet",       "trinket", None, "amulet", 4, {"atk": 2.5, "crit": 7, "hp": 10, "regen": 1.0}, 400),
}

STARTER_WEAPON = {"warrior": "iron_sword", "mage": "oak_staff", "archer": "hunting_bow"}


class Item:
    """One piece of gear: a base (see BASES) at a rarity (0 Common ... 4 Legendary)."""

    __slots__ = ("base", "rarity")

    def __init__(self, base, rarity=0):
        if base not in BASES:
            raise KeyError(f"No gear called {base!r}")
        self.base = base
        self.rarity = max(0, min(len(RARITIES) - 1, int(rarity)))

    # ---- what it is -------------------------------------------------------------
    @property
    def _row(self):
        return BASES[self.base]

    @property
    def slot(self):
        return self._row[1]

    @property
    def hero_class(self):
        """'warrior' / 'mage' / 'archer', or None when every hero can wear it."""
        return self._row[2]

    @property
    def kind(self):
        return self._row[3]

    @property
    def tier(self):
        return self._row[4]

    @property
    def rarity_name(self):
        return RARITIES[self.rarity][0]

    @property
    def color(self):
        return RARITIES[self.rarity][1]

    @property
    def name(self):
        return self._row[0] if self.rarity == 0 else f"{self.rarity_name} {self._row[0]}"

    @property
    def stats(self):
        k = RARITIES[self.rarity][2]
        out = {}
        for key, v in self._row[5].items():
            v = v * k
            out[key] = round(v, 1) if key in DECIMAL else max(1, int(round(v)))
        return out

    @property
    def price(self):
        return int(round(self._row[6] * RARITIES[self.rarity][3] / 5.0)) * 5

    @property
    def sell_value(self):
        return max(1, self.price // 3)

    def usable_by(self, character_class):
        return self.hero_class in (None, character_class)

    # ---- saving -----------------------------------------------------------------
    def to_dict(self):
        return {"base": self.base, "rarity": self.rarity}

    @classmethod
    def from_dict(cls, data):
        """An Item from saved data, or None if it is broken / no longer exists."""
        try:
            return cls(data["base"], data.get("rarity", 0))
        except (KeyError, TypeError, ValueError, AttributeError):
            return None

    def __eq__(self, other):
        return isinstance(other, Item) and (self.base, self.rarity) == (other.base, other.rarity)

    def __hash__(self):
        return hash((self.base, self.rarity))

    def __repr__(self):
        return f"Item({self.name!r})"


class Gear:
    """What the hero wears (one item per slot) plus the bag."""

    def __init__(self, character_class="warrior", starter=True):
        self.character_class = character_class
        self.equipped = {slot: None for slot in SLOTS}
        self.bag: list = []
        if starter and character_class in STARTER_WEAPON:
            self.equipped["weapon"] = Item(STARTER_WEAPON[character_class])

    # ---- bag ----------------------------------------------------------------------
    @property
    def full(self):
        return len(self.bag) >= BAG_SIZE

    def add(self, item):
        """Put an item in the bag. False when the bag is full."""
        if item is None or self.full:
            return False
        self.bag.append(item)
        return True

    def remove(self, index):
        if 0 <= index < len(self.bag):
            return self.bag.pop(index)
        return None

    def sell(self, index):
        """Take an item out of the bag; returns the gold it is worth (0 if nothing there)."""
        item = self.remove(index)
        return item.sell_value if item else 0

    # ---- equipping ----------------------------------------------------------------
    def can_equip(self, item):
        return item is not None and item.usable_by(self.character_class)

    def equip(self, index):
        """Wear bag item `index`; whatever was in that slot goes back to the bag. True if done."""
        if not (0 <= index < len(self.bag)) or not self.can_equip(self.bag[index]):
            return False
        item = self.bag[index]
        old = self.equipped[item.slot]
        self.equipped[item.slot] = item
        if old is not None:
            self.bag[index] = old             # swap in place: the old piece takes its bag spot
        else:
            self.bag.pop(index)
        return True

    def unequip(self, slot):
        """Take off a slot's item into the bag. False if empty or the bag is full."""
        item = self.equipped.get(slot)
        if item is None or self.full:
            return False
        self.equipped[slot] = None
        self.bag.append(item)
        return True

    def totals(self):
        """Every stat from everything worn, summed."""
        out = {}
        for item in self.equipped.values():
            if item is not None:
                for k, v in item.stats.items():
                    out[k] = out.get(k, 0) + v
        return out

    def compare(self, item):
        """{stat: change} if `item` replaced what is worn in its slot."""
        cur = self.equipped.get(item.slot)
        now = cur.stats if cur else {}
        new = item.stats
        return {k: new.get(k, 0) - now.get(k, 0) for k in STAT_ORDER if k in now or k in new}

    # ---- saving -------------------------------------------------------------------
    def to_dict(self):
        return {"equipped": {s: i.to_dict() for s, i in self.equipped.items() if i is not None},
                "bag": [i.to_dict() for i in self.bag]}

    @classmethod
    def from_dict(cls, data, character_class):
        g = cls(character_class, starter=False)
        if not isinstance(data, dict):
            return cls(character_class)
        eq = data.get("equipped", {})
        if isinstance(eq, dict):
            for slot, d in eq.items():
                item = Item.from_dict(d)
                if slot in g.equipped and item is not None and item.slot == slot and g.can_equip(item):
                    g.equipped[slot] = item
        for d in data.get("bag", []) if isinstance(data.get("bag"), list) else []:
            item = Item.from_dict(d)
            if item is not None:
                g.add(item)
        return g


# --------------------------------------------------------------------------- stat points
POINTS_PER_LEVEL = 2
#        id      name        what one point gives
ATTRS = [("vit", "Vitality", {"hp": 5}),
         ("pow", "Power",    {"atk": 0.5}),
         ("grd", "Guard",    {"def": 1}),
         ("agi", "Agility",  {"aspd": 3, "spd": 1.5}),
         ("spi", "Spirit",   {"res": 6, "regen": 0.3})]
ATTR_IDS = tuple(a for a, _n, _s in ATTRS)


def attr_stats(alloc):
    """Stats from spent points: {"vit": 2, "pow": 1} -> {"hp": 10, "atk": 0.5}."""
    out = {}
    for aid, _name, per in ATTRS:
        n = max(0, int(alloc.get(aid, 0)))
        if not n:
            continue
        for k, v in per.items():
            out[k] = out.get(k, 0) + v * n
    return out


SHORT_LABELS = {"aspd": "Atk Spd", "spd": "Move", "res": "Max {res}", "regen": "Regen"}


def attr_text(aid, resource="Mana"):
    """What one point gives, short enough for the stats panel: '+3% Atk Speed, +1.5% Move'."""
    per = dict((a, s) for a, _n, s in ATTRS)[aid]
    parts = []
    for k, v in per.items():
        num, label = format_stat(k, v, resource)
        if k == "spd":
            num = "%+.1f%%" % v
        parts.append("%s %s" % (num, SHORT_LABELS.get(k, label).format(res=resource)))
    return ", ".join(parts)


# --------------------------------------------------------------------------- drops and shops
RARITY_WEIGHTS = [60, 28, 9, 2.5, 0.5]


def _rarity(rng, tier, luck=0.0):
    """Higher tiers and luck push the odds toward better rarities."""
    w = [RARITY_WEIGHTS[i] * (1 + (tier - 1 + luck) * 0.35 * i) for i in range(len(RARITY_WEIGHTS))]
    return rng.choices(range(len(w)), weights=w)[0]


def roll_drop(rng, character_class, tier=1, luck=0.0):
    """A random piece of gear for this hero from about this tier (1-4).
    Weapons only of the hero's own class, so drops are never useless to them."""
    tier = max(1, min(4, int(tier)))
    pool = [b for b, row in BASES.items()
            if row[4] in (tier, max(1, tier - 1)) and row[2] in (None, character_class)]
    base = rng.choice(pool)
    return Item(base, _rarity(rng, tier, luck))


def shop_stock(character_class, stage):
    """What Torvin sells after `stage` dungeons (0-3): one piece per slot at the newest tier,
    plus the tier below at Uncommon. The same list every visit for the same stage."""
    top = max(1, min(4, stage + 1))
    stock = []
    for tier, rarity in ((top, 0), (max(1, top - 1), 1)) if top > 1 else ((1, 0), (1, 1)):
        for slot in SLOTS:
            base = next(b for b, row in BASES.items()
                        if row[1] == slot and row[4] == tier and row[2] in (None, character_class))
            stock.append(Item(base, rarity))
    return stock


def drop_tier(place_tier, boss=False):
    return max(1, min(4, place_tier + (1 if boss else 0)))


def new_rng(seed=None):
    return random.Random(seed)
