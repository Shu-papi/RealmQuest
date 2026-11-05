"""
balance_report.py - prints the game's balance from the LIVE config (config/*.toml): the hero's health and
hits per class and level, how many hits each monster family takes, how hard the bosses hit at their gate
level, and the level the hero reaches along the intended path (minis -> dungeon -> minis -> dungeon ...).

    python tools/balance_report.py                 # the tables
    python tools/balance_report.py --check         # exit 1 if a balance target is missed (see TARGETS)

Read-only: it builds no Game and writes no file.
"""
from __future__ import annotations

import math
import os
import sys
import tomllib

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")
REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO, "src", "maps"))
sys.path.insert(0, os.path.join(REPO, "src"))

import pygame  # noqa: E402

pygame.init()
pygame.display.set_mode((8, 8))

import balance  # noqa: E402
import combat  # noqa: E402
import dungeon_gen  # noqa: E402
import minis  # noqa: E402
import save_state  # noqa: E402
from skills import classes  # noqa: E402

CLASSES = ("warrior", "mage", "archer")
LEVELS = (1, 5, 10, 15, 20, 25, 30)
GATES = {"goblin": 5, "berserker": 15, "lich": 20}
RANGES = {"goblin": (5, 10), "berserker": (15, 20), "lich": (20, 30)}
FAMILY = {"goblin": 1, "berserker": 2, "lich": 3}
MOBS_PER_ROOM = sum(combat.MOBS_PER_ROOM) / 2

# what --check wants
TARGETS = {
    "hits_regular": (8, 16),          # warrior hits for a regular mob at the start of its range
    "boss_hit_max_share": 0.75,       # a boss hit bigger than this share of max HP at the gate is WARNED about
    "boss_hit_fail_share": 0.85,      # ...and one this big FAILS the check (no one-shots at the gate level)
    "mob_hit_share": (0.02, 0.14),    # a regular mob's hit as a share of max HP at the start of its range
}


def hero(cls, level):
    s = save_state.SaveState(hero_class=cls)
    s.xp = save_state.LEVEL_XP[min(level, save_state.MAX_LEVEL) - 1]
    s.gear.equipped.clear() if hasattr(s.gear, "equipped") else None
    pc = combat.PlayerCombat(cls)
    s.apply_to(pc)
    return s.max_hp, pc.sword_dmg, pc.swing_cd


def _skeletons():
    """{name: (effective HP, main hit)} for the dungeon-room skeletons."""
    from monsters import MONSTERS, TIERS
    from monsters import in_game
    rule = in_game.RULES["dungeon"]
    tier = TIERS[rule["tier"]]
    out = {}
    for name in ("skeleton_warrior", "skeleton_archer", "skeleton_acolyte", "skeleton_brute"):
        cls = MONSTERS[name]
        hp = cls.MAX_HP * tier["hp_scale"] * in_game.HP_TRIM.get(name, 1.0) / rule["hp_power"]
        dmg = max(1, round(cls.DAMAGE * tier["damage_scale"])) * rule["damage_k"]
        out[name] = (hp, dmg)
    return out


def families():
    """family -> {name: (hp, damage)} of its regular mobs, plus elites."""
    g = {k: (v[1], v[3]) for k, v in combat.GOBLIN_MOBS.items()}
    b = {k: (v[1], v[3]) for k, v in combat.BERSERKER_MOBS.items()}
    s = _skeletons()
    elites = {
        "goblin": {"War Boar": combat.GOBLIN_WAR_BOAR[1:4:2], "General Grub": combat.MINIBOSSES[1][1:4:2]},
        "berserker": {"Elder Treant": combat.ELDER_TREANT[1:4:2], "Orc Warlord": combat.ORC_WARLORD[1:4:2]},
        "lich": {},
    }
    return {"goblin": g, "berserker": b, "lich": s}, elites


def bosses():
    out = {}
    with open(os.path.join(balance.config_path(), "bosses", "goblin_king.toml"), "rb") as f:
        gk = tomllib.load(f)["dungeon"]
    out["goblin"] = ("Goblin King", gk["max_hp"], {"slam": gk["slam_damage"], "spin": gk["spin_damage"],
                                                   "ground slam": gk["ground_slam_damage"]})
    with open(os.path.join(balance.config_path(), "bosses", "minotaur.toml"), "rb") as f:
        mt = tomllib.load(f)
    hits = {"rock": mt.get("rock_damage", 0)}
    for ph, table in mt.items():
        if isinstance(table, dict):
            for k, v in table.items():
                if k.endswith("_damage") and isinstance(v, (int, float)):
                    hits["%s %s" % (ph, k[:-7])] = v * mt.get("dungeon", {}).get("damage_k", 1)
    out["berserker"] = ("Minotaur", mt["max_hp"], hits)
    with open(os.path.join(balance.config_path(), "bosses", "lich_king.toml"), "rb") as f:
        lk = tomllib.load(f)
    out["lich"] = ("Lich King", lk["max_hp"], {k[:-7]: v for k, v in lk["damage"].items()})
    return out


def dungeon_xp(floors, tier, boss_hp=0, mini=False):
    """XP for clearing these floors (every fighting room, elites, mini-bosses, the boss)."""
    fam, elites = families()
    fam_key = {1: "goblin", 2: "berserker", 3: "lich"}[min(3, tier)]
    avg_hp = sum(hp for hp, _ in fam[fam_key].values()) / len(fam[fam_key])
    elite_hp = {k: v[0] for k, v in elites[fam_key].items()}
    total = 0.0
    for name in floors:
        lay = dungeon_gen.generate(name, 7)
        for role in lay.roles:
            if role in dungeon_gen.SAFE_ROLES or role == "boss":
                continue
            total += MOBS_PER_ROOM * combat.kill_xp(avg_hp) * tier
            if role == "guard":
                total += combat.kill_xp(next(iter(elite_hp.values()), avg_hp * 1.5)) * tier * 2
            if role in ("miniboss", "lair"):
                total += combat.kill_xp(list(elite_hp.values())[-1] if elite_hp else avg_hp * 5) * tier * 2
    total += combat.kill_xp(boss_hp) * tier * 3
    if mini:
        total += minis.FIRST_CLEAR_XP * tier
    return total


def path():
    """The intended path and the level after each step."""
    bs = bosses()
    steps = [("Mossy Burrow (mini, t1)", dungeon_xp(["11-1"], 1, mini=True)),
             ("Thornwood Den (mini, t1)", dungeon_xp(["12-1"], 1, mini=True)),
             ("Goblin Dungeon", dungeon_xp(["1-1", "1-2", "1-3"], 1, bs["goblin"][1])),
             ("Old Watchtower (mini, t2)", dungeon_xp(["13-1"], 2, mini=True)),
             ("Sunken Crypt (mini, t2)", dungeon_xp(["14-1"], 2, mini=True)),
             ("Watchtower again", dungeon_xp(["13-1"], 2)),
             ("Crypt again", dungeon_xp(["14-1"], 2)),
             ("Berserker Dungeon", dungeon_xp(["2-1", "2-2", "2-3"], 2, bs["berserker"][1])),
             ("Ashen Pit (mini, t3)", dungeon_xp(["15-1"], 3, mini=True)),
             ("Bone Hollow (mini, t3)", dungeon_xp(["16-1"], 3, mini=True)),
             ("Lich floors 1-2", dungeon_xp(["3-1", "3-2"], 3)),
             ("Lich floor 3 + the Lich King", dungeon_xp(["3-3"], 3, bs["lich"][1]))]
    xp, out = 0.0, []
    for name, gain in steps:
        xp += gain
        out.append((name, gain, xp, save_state.level_of(int(xp))))
    return out


def report(check=False):
    problems, warnings = [], []
    print("HERO  (max HP / hit damage, no gear)")
    print("%-8s" % "class" + "".join("%12s" % ("Lv%d" % lv) for lv in LEVELS))
    for cls in CLASSES:
        print("%-8s" % cls + "".join("%12s" % ("%d / %d" % hero(cls, lv)[:2]) for lv in LEVELS))
    fam, elites = families()
    print("\nMONSTERS  (at the start of their range, warrior)")
    for key, mobs in fam.items():
        lo = RANGES[key][0]
        hp_h, dmg_h, _ = hero("warrior", lo)
        for name, (hp, dmg) in list(mobs.items()) + list(elites[key].items()):
            hits = math.ceil(hp / dmg_h)
            share = dmg / hp_h
            print("  %-10s %-18s HP %5d  hit %5.1f   warrior hits %3d   hit = %4.1f%% of hero HP"
                  % (key, name, hp, dmg, hits, share * 100))
            if name in mobs:
                if not TARGETS["hits_regular"][0] <= hits <= TARGETS["hits_regular"][1]:
                    problems.append("%s %s takes %d hits" % (key, name, hits))
                if not TARGETS["mob_hit_share"][0] <= share <= TARGETS["mob_hit_share"][1]:
                    problems.append("%s %s hits for %.1f%% of hero HP" % (key, name, share * 100))
    print("\nBOSSES  (at the gate level)")
    for key, (name, hp, hits) in bosses().items():
        gate = GATES[key]
        for cls in CLASSES:
            hp_h, dmg_h, cd = hero(cls, gate)
            worst = max(hits.values())
            print("  %-12s vs %-8s Lv%-2d: %d hits (%.0f s), worst hit %d = %.0f%% of %d HP"
                  % (name, cls, gate, math.ceil(hp / dmg_h), hp / dmg_h * cd, worst, worst / hp_h * 100, hp_h))
            if worst / hp_h >= TARGETS["boss_hit_fail_share"]:
                problems.append("%s's worst hit (%d) takes %.0f%% of a Lv%d %s" % (name, worst, worst / hp_h * 100,
                                                                                  gate, cls))
            elif worst / hp_h > TARGETS["boss_hit_max_share"]:
                warnings.append("%s's worst hit takes %.0f%% of a Lv%d %s%s" % (
                    name, worst / hp_h * 100, gate, cls, " (ONE-SHOT: dodge it, or level up / armour first)"
                    if worst >= hp_h else ""))
    print("\nLEVEL PATH")
    for name, gain, xp, lv in path():
        print("  %-32s +%6d XP   total %7d   -> Lv %d" % (name, gain, xp, lv))
    print("\nXP to reach: " + ", ".join("Lv%d %d" % (lv, save_state.LEVEL_XP[lv - 1]) for lv in (5, 10, 15, 20, 25, 30)
                                        if lv <= save_state.MAX_LEVEL))
    if problems:
        print("\nOUT OF TARGET:")
        for p in problems:
            print("  - " + p)
    if warnings:
        print("\nBOSS WARNINGS (by design: hard bosses):")
        for w in warnings:
            print("  - " + w)
    return 1 if (check and problems) else 0


if __name__ == "__main__":
    sys.exit(report("--check" in sys.argv))
