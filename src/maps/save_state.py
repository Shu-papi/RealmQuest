"""
save_state.py - everything the campaign remembers between floors and sessions.

One SaveState object is shared by the Game (dungeons) and the SurfaceWorld
(overworld). It is written to savegame.json in the project root.

Upgrades are applied to the existing PlayerCombat fields (max_hp, dmg_bonus,
potions), so combat.py does not need to know about saving or shops.
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path

try:
    from . import combat as _combat
except ImportError:
    import combat as _combat

from skills import classes as hero_classes      # combat.py put src/ on the import path
from inventory.gear import Gear, attr_stats, ATTR_IDS, POINTS_PER_LEVEL   # noqa: E402

DEFAULT_HERO_NAME = "Himmel"
DEFAULT_HERO_CLASS = "warrior"

try:
    import app_paths as _app_paths                                    # src/ is on the path (combat.py)
except ImportError:                                                   # pragma: no cover
    from src import app_paths as _app_paths
# the save: the repo root in development, %APPDATA%/RealmQuest in the built game; the tester uses its own file
SAVE_PATH = Path(os.environ.get("REALMQUEST_SAVE") or _app_paths.user_dir() / "savegame.json")

ARMOR_HP = 20             # max HP per armor level
BOOTS_DASH_FACTOR = 0.75  # dash cooldown multiplier per boots level
HERB_HEAL = 6             # extra potion healing per herb level
BONUS_HP = {"hp_charm": 4, "hp_blessing": 6}   # max HP from side-quest rewards (save flags)

# ---- character level ----------------------------------------------------------------
# XP comes from monsters (a share of their max HP x their tier), mini dungeons, lairs, raids and events.
# Every level gives max HP; every third level gives +1 attack (x combat.BONUS_SCALE).
# The main dungeons are meant for: Goblin Lv 5-10, Berserker Lv 15-20, the Lich King Lv 20-30.
MAX_LEVEL = 30
HP_PER_LEVEL = 12
XP_BASE = 60                       # XP from level 1 to 2 ...
XP_GROWTH = 45                     # ... and each next level costs this much more
XP_CURVE = 2.0                     # ... plus this x (level - 1)^2 (makes the high levels slow)
LEVEL_XP = [0]                     # LEVEL_XP[n - 1] = total XP needed to reach level n
# the level each main dungeon's portal asks for (see surface_world.DUNGEONS)
MAIN_MIN_LEVEL = {"goblin": 5, "berserker": 15, "lich": 20}


def build_level_xp():
    """(Re)build LEVEL_XP from XP_BASE / XP_GROWTH / XP_CURVE (hero.toml can change them)."""
    del LEVEL_XP[1:]
    for n in range(1, MAX_LEVEL):
        LEVEL_XP.append(LEVEL_XP[-1] + int(XP_BASE + XP_GROWTH * (n - 1) + XP_CURVE * (n - 1) ** 2))


build_level_xp()


def level_of(xp: int) -> int:
    lv = 1
    while lv < MAX_LEVEL and xp >= LEVEL_XP[lv]:
        lv += 1
    return lv


def level_progress(xp: int):
    """(level, xp into this level, xp needed for the next level or 0 at max)."""
    lv = level_of(xp)
    if lv >= MAX_LEVEL:
        return lv, 0, 0
    return lv, xp - LEVEL_XP[lv - 1], LEVEL_XP[lv] - LEVEL_XP[lv - 1]


@dataclass
class SaveState:
    hero_name: str = DEFAULT_HERO_NAME            # chosen on the name screen
    hero_class: str = DEFAULT_HERO_CLASS          # warrior / mage / archer
    gold: int = 0
    potions: int = field(default_factory=lambda: _combat.POTION_START)   # (read live: hero.toml)
    sword_lv: int = 0
    armor_lv: int = 0
    boots_lv: int = 0
    herb_lv: int = 0
    raids: int = 0                                # night raids beaten off
    xp: int = 0                                   # experience (see level_of)
    cleared: set = field(default_factory=set)     # surface dungeon ids: goblin / berserker / lich
    keepsakes: set = field(default_factory=set)   # same ids: Veil Anchors shattered (one per dungeon)
    flags: set = field(default_factory=set)       # story / NPC / treasure flags
    gear: Gear = None                             # worn equipment + bag (inventory.gear)
    alloc: dict = field(default_factory=dict)     # stat points spent: {"vit": 2, "pow": 1, ...}

    def __post_init__(self):
        if self.gear is None:
            self.gear = Gear(self.hero_class)

    # ---- derived stats ------------------------------------------------------
    @property
    def level(self) -> int:
        return level_of(self.xp)

    @property
    def base_hp(self) -> int:
        """Max HP of the chosen class before upgrades and levels."""
        return hero_classes.stats(self.hero_class)["hp"] if self.hero_class in hero_classes.CLASS_STATS \
            else _combat.PLAYER_MAX_HP

    @property
    def max_hp(self) -> int:
        return int(self.base_hp + ARMOR_HP * self.armor_lv + HP_PER_LEVEL * (self.level - 1)
                   + sum(v for f, v in BONUS_HP.items() if f in self.flags) + self.bonus_stats().get("hp", 0))

    # ---- stat points ----------------------------------------------------------
    @property
    def points_earned(self) -> int:
        return POINTS_PER_LEVEL * (self.level - 1)

    @property
    def stat_points(self) -> int:
        """Unspent stat points (every level gives POINTS_PER_LEVEL)."""
        return max(0, self.points_earned - sum(self.alloc.values()))

    def spend_point(self, attr: str) -> bool:
        if attr not in ATTR_IDS or self.stat_points <= 0:
            return False
        self.alloc[attr] = self.alloc.get(attr, 0) + 1
        return True

    def reset_points(self):
        self.alloc.clear()

    def bonus_stats(self) -> dict:
        """Gear + stat points, summed: {"hp", "atk", "def", "aspd", "spd", "crit", "res", "regen"}."""
        out = dict(self.gear.totals())
        for k, v in attr_stats(self.alloc).items():
            out[k] = out.get(k, 0) + v
        return out

    def level_damage(self) -> int:
        """Attack from levels (before combat.BONUS_SCALE): +1 every third level."""
        return (self.level - 1) // 3

    @property
    def stage(self) -> int:
        """How far the story has progressed (0-3 dungeons cleared)."""
        return sum(1 for d in ("goblin", "berserker", "lich") if d in self.cleared)

    def dash_factor(self) -> float:
        return BOOTS_DASH_FACTOR ** self.boots_lv

    def potion_bonus(self) -> int:
        return HERB_HEAL * self.herb_lv

    def apply_to(self, pc):
        """Push the class and upgrades onto a PlayerCombat."""
        if getattr(pc, "character_class", None) != self.hero_class:
            pc.apply_class(self.hero_class)
        if self.gear.character_class != self.hero_class:
            self.gear.character_class = self.hero_class
        bonus = self.bonus_stats()
        pc.max_hp = self.max_hp
        pc.dmg_bonus = self.sword_lv + self.level_damage() + bonus.get("atk", 0)
        pc.apply_stats(bonus)
        pc.potions = self.potions
        pc.hp = min(pc.hp, pc.max_hp)

    def pull_from(self, pc):
        """Remember things the dungeon changed (potions drunk / picked up)."""
        self.potions = pc.potions

    # ---- persistence ----------------------------------------------------------
    def reset(self, hero_name: str | None = None, hero_class: str | None = None):
        """Start over (optionally as a new hero). Sets are cleared in place so views sharing them stay valid."""
        fresh = SaveState()
        self.hero_name = clean_name(hero_name) if hero_name else DEFAULT_HERO_NAME
        self.hero_class = hero_class if hero_class in hero_classes.CLASS_STATS else DEFAULT_HERO_CLASS
        for name in ("gold", "potions", "sword_lv", "armor_lv", "boots_lv", "herb_lv", "raids", "xp"):
            setattr(self, name, getattr(fresh, name))
        self.gear = Gear(self.hero_class)
        self.alloc.clear()
        self.cleared.clear()
        self.keepsakes.clear()
        self.flags.clear()

    def to_dict(self) -> dict:
        return {
            "version": 3,
            "hero_name": self.hero_name, "hero_class": self.hero_class,
            "gold": self.gold, "potions": self.potions,
            "sword_lv": self.sword_lv, "armor_lv": self.armor_lv,
            "boots_lv": self.boots_lv, "herb_lv": self.herb_lv, "raids": self.raids, "xp": self.xp,
            "cleared": sorted(self.cleared), "keepsakes": sorted(self.keepsakes),
            "flags": sorted(self.flags),
            "gear": self.gear.to_dict(), "alloc": dict(self.alloc),
        }

    def save(self, path: Path | None = None) -> bool:
        path = path or SAVE_PATH
        try:
            tmp = path.with_suffix(".tmp")
            tmp.write_text(json.dumps(self.to_dict(), indent=2), encoding="utf-8")
            tmp.replace(path)
            return True
        except OSError:
            return False

    @classmethod
    def exists(cls, path: Path | None = None) -> bool:
        return (path or SAVE_PATH).is_file()

    @classmethod
    def load(cls, path: Path | None = None) -> "SaveState":
        """Load the save file; a missing or broken file gives a fresh state."""
        s = cls()
        try:
            data = json.loads((path or SAVE_PATH).read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return s
        if not isinstance(data, dict):
            return s
        for name in ("gold", "potions", "sword_lv", "armor_lv", "boots_lv", "herb_lv", "raids", "xp"):
            v = data.get(name)
            if isinstance(v, int) and v >= 0:
                setattr(s, name, v)
        name = data.get("hero_name")                  # saves from before heroes had names: Himmel
        if isinstance(name, str) and clean_name(name):
            s.hero_name = clean_name(name)
        if data.get("hero_class") in hero_classes.CLASS_STATS:
            s.hero_class = data["hero_class"]
        for name in ("cleared", "keepsakes", "flags"):
            v = data.get(name)
            if isinstance(v, list):
                getattr(s, name).update(str(x) for x in v)
        # saves from before gear: the class's starter weapon
        s.gear = Gear.from_dict(data["gear"], s.hero_class) if "gear" in data else Gear(s.hero_class)
        alloc = data.get("alloc")
        if isinstance(alloc, dict):
            s.alloc.update({k: v for k, v in alloc.items() if k in ATTR_IDS and isinstance(v, int) and v > 0})
            while sum(s.alloc.values()) > s.points_earned:      # never more spent than earned
                k = max(s.alloc, key=s.alloc.get)
                s.alloc[k] -= 1
                if s.alloc[k] <= 0:
                    del s.alloc[k]
        if "xp" not in data:
            # saves from before levels existed: don't strand the player behind a level gate
            nxt = next((d for d in ("goblin", "berserker", "lich") if d not in s.cleared), None)
            if nxt and nxt != "goblin":
                s.xp = LEVEL_XP[MAIN_MIN_LEVEL[nxt] - 1]
            elif nxt is None:
                s.xp = LEVEL_XP[MAIN_MIN_LEVEL["lich"] - 1]
        return s


NAME_MAX = 14


def clean_name(name) -> str:
    """Letters, digits, spaces, ' and - only; at most NAME_MAX characters; trimmed."""
    if not isinstance(name, str):
        return ""
    keep = "".join(ch for ch in name if ch.isalnum() or ch in " '-")
    return " ".join(keep.split())[:NAME_MAX].strip()


# ======================================================================================================
# CONFIG FILE: config/characters/hero.toml also holds these (src/balance.py).
# ======================================================================================================
try:
    import balance as _balance                              # src/ is on the path (combat.py)
except ImportError:                                         # pragma: no cover
    _balance = None

if _balance is not None:
    _balance.declare(
        "characters", "hero", "", "", globals(),
        {"hp_per_level": "HP_PER_LEVEL", "armor_upgrade_hp": "ARMOR_HP", "max_level": "MAX_LEVEL",
         "xp_base": "XP_BASE", "xp_growth": "XP_GROWTH", "xp_curve": "XP_CURVE"},
        docs={"hp_per_level": "Max health every level gives.",
              "armor_upgrade_hp": "Max health each Riveted Armor upgrade (shop) gives.",
              "max_level": "The highest level.",
              "xp_base": "XP from level 1 to level 2.",
              "xp_growth": "Each next level costs this much more XP...",
              "xp_curve": "...plus this x (level - 1) squared (makes the high levels slow)."},
        partial=True)
    build_level_xp()
    _balance.on_reload(build_level_xp)
