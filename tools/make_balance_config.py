"""
make_balance_config.py - (re)writes config/balance.toml from the numbers that are in the code.

    python tools/make_balance_config.py              write config/balance.toml  (asks before overwriting!)
    python tools/make_balance_config.py --stdout     just print it
    python tools/make_balance_config.py --force      overwrite without asking

You only need this when a developer ADDS a setting in the code (so it shows up in the file with its
description), or when you want to reset the config file to the defaults. Players and designers just edit
config/balance.toml by hand.
"""
import json
import os
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO, "src"))
os.environ["REALMQUEST_BALANCE"] = "none"                # we want the numbers that are IN THE CODE

try:
    import pygame                                        # noqa: F401
except ImportError:                                      # no pygame installed: the test stub is enough to read numbers
    sys.path.insert(0, os.path.join(REPO, "src", "bosses", "tests"))
    from pygame_stub import install
    install()

import balance                                           # noqa: E402
from bosses.lich_king import boss as B                   # noqa: E402
from bosses.lich_king import minions as M                # noqa: E402
import monsters                                          # noqa: E402

# ----------------------------------------------------------------------
# What each setting means (shown as the comment next to it)
# ----------------------------------------------------------------------

BOSS_GROUPS = [
    ("", "boss", "WHO HE IS", [
        ("name", "BOSS_NAME", "Shown above his health bar."),
        ("max_hp", "BOSS_MAX_HP", "Health pool. Phase 2 starts at phase_2_at of this, phase 3 at phase_3_at."),
        ("radius", "BOSS_RADIUS", "His hit circle (pixels). Bigger = easier to hit."),
        ("intro", "BOSS_INTRO", "Line shown when the fight starts."),
        ("death_line", "BOSS_DEATH_LINE", "Line shown when he dies."),
        ("loot", "BOSS_LOOT", "Items he drops, as a list of text."),
    ]),
    ("timing", "boss.timing", "PHASES AND TIMING (seconds)", [
        ("phase_2_at", "PHASE_2_AT", "Phase 2 begins when his HP drops to this fraction (0.5 = 50%)."),
        ("phase_3_at", "PHASE_3_AT", "Phase 3 (Last Stand) begins at this fraction."),
        ("intro_time", "INTRO_TIME", "He rises from the floor and can't be hurt for this long."),
        ("transition_time", "TRANSITION_TIME", "The roar between phases (can't be hurt)."),
        ("teleport_time", "TELEPORT_TIME", "Fade-out time of a teleport (and fade-in again)."),
        ("dying_time", "DYING_TIME", "Length of his death animation."),
        ("aim_lock", "AIM_LOCK", "Volley and Barrage stop tracking you this long before firing. Bigger = easier to dodge."),
        ("combo_pause", "COMBO_PAUSE", "Pause between the attacks of one chain. Smaller = more overwhelming."),
    ]),
    ("window", "boss.window", "THE PLAYER'S WINDOW (after every chain he is exhausted)", [
        ("exhaust_bonus", "EXHAUST_BONUS", "Damage multiplier while he is exhausted or stunned (1.5 = +50%)."),
    ]),
    ("ward", "boss.ward", "PHASE 3: THE SOUL WARD (invulnerable while any summon lives)", [
        ("shield_break_window", "SHIELD_BREAK_WINDOW", "Seconds he is STUNNED (and takes bonus damage) after the last summon dies."),
        ("rearm_after", "REARM_AFTER", "Seconds with no army before he calls a fresh wave."),
        ("wave_raise_budget", "WAVE_RAISE_BUDGET", "Dead an acolyte may raise per wave (so the ward can't last forever)."),
    ]),
    ("damage", "boss.damage", "ATTACK DAMAGE (health the player loses per hit)", [
        ("volley_damage", "VOLLEY_DAMAGE", "One bolt of the Shadow Volley."),
        ("drain_damage", "DRAIN_DAMAGE", "Life Drain circle (it also heals him; see drain_heal in the phases)."),
        ("nova_damage", "NOVA_DAMAGE", "One bone shard of the Bone Nova."),
        ("grasp_damage", "GRASP_DAMAGE", "A Grasping Hand."),
        ("barrage_damage", "BARRAGE_DAMAGE", "One bolt of the Soul Barrage."),
        ("rain_damage", "RAIN_DAMAGE", "One Soul Rain circle."),
    ]),
    ("shapes", "boss.shapes", "ATTACK SHAPES (pixels / counts)", [
        ("drain_radius", "DRAIN_RADIUS", "Size of a Life Drain circle."),
        ("grasp_radius", "GRASP_RADIUS", "Size of a Grasping Hand."),
        ("volley_spread_deg", "VOLLEY_SPREAD_DEG", "Angle between the bolts of a Shadow Volley (degrees)."),
        ("nova_gap_shards", "NOVA_GAP_SHARDS", "How many shards wide the Bone Nova's safe gap is. Smaller = harder."),
        ("nova_second_ring", "NOVA_SECOND_RING", "Seconds between the two rings of the phase 3 nova."),
        ("rain_stagger", "RAIN_STAGGER", "Seconds between one Soul Rain circle bursting and the next."),
        ("grasp_stagger", "GRASP_STAGGER", "Seconds between one Grasping Hand bursting and the next."),
    ]),
    ("colors", "boss.colors", "COLOURS (red, green, blue: 0-255)", [
        ("attack_glow", "ATTACK_GLOW", "The glow colour of each attack's wind-up."),
        ("exhaust_glow", "EXHAUST_GLOW", "'Hit me now' gold."),
        ("shield", "SHIELD", "The Soul Ward violet."),
        ("shield_hot", "SHIELD_HOT", "The Soul Ward highlight."),
    ]),
]

PHASE_TITLES = {
    1: "PHASE 1 (100% - phase_2_at)",
    2: "PHASE 2 (phase_2_at - phase_3_at)",
    3: "PHASE 3: LAST STAND (below phase_3_at)",
}

PHASE_DESC = {
    "speed": "How fast he walks after you (pixels per second).",
    "idle": "Pause before a new chain starts (seconds).",
    "recover": "Pause after each attack (seconds).",
    "teleport": "Chance (0-1) that he teleports after a chain.",
    "combo": "Extra attacks chained after the first. Chain length = combo + 1.",
    "exhaust": "Seconds he stands open after a chain (takes exhaust_bonus damage).",
    "minion_cap": "Army size he can control (a brute counts as 2). 0 = he never summons.",
    "summon_picks": "How many minions one Summon calls.",
    "volley_windup": "Shadow Volley wind-up (seconds). Smaller = less warning.",
    "bolts": "Bolts in a Shadow Volley.",
    "bolt_speed": "Volley bolt speed (pixels per second).",
    "drain_windup": "Life Drain wind-up.",
    "drain_circles": "Life Drain circles.",
    "drain_heal": "Health he heals when a Drain circle hits you.",
    "rain_windup": "Soul Rain wind-up.",
    "rain_circles": "Soul Rain circles.",
    "rain_radius": "Size of each rain circle.",
    "summon_windup": "Summon wind-up.",
    "nova_windup": "Bone Nova wind-up.",
    "nova_rings": "Rings in a Bone Nova (2 = the phase 3 double nova).",
    "nova_shards": "Shards per ring. More = smaller gaps.",
    "nova_speed": "Shard speed.",
    "grasp_windup": "Grasping Hands wind-up.",
    "grasp_hands": "Hands per attack (one is always under you).",
    "grasp_root": "Seconds a hand roots you in place.",
    "barrage_windup": "Soul Barrage wind-up.",
    "barrage_bolts": "Bolts in a barrage.",
    "barrage_speed": "Barrage bolt speed.",
    "barrage_sweep": "Width of the barrage wedge in degrees. Wider = less safe space.",
    "barrage_interval": "Seconds between barrage bolts. Smaller = spammier.",
}

SUMMON_DESC = {
    "cost": "Army budget it uses (he controls minion_cap worth at once).",
    "weight": "How likely he is to call it (higher = more often).",
    "limit": "Most of this kind alive at once.",
}

MONSTER_DESC = {
    "MAX_HP": "Health at tier 'normal' (a tier multiplies this, see [tiers]).",
    "RADIUS": "Hit circle (pixels).",
    "SPEED": "Walking speed (pixels per second).",
    "DAMAGE": "Damage of its main attack (tier 'normal').",
    "XP": "Experience it gives.",
    "GOLD": "Gold dropped: [min, max].",
    "LOOT": "Drops: [item, chance 0-1] pairs.",
    "SPAWN_TIME": "Seconds it takes to rise from the ground (can't be hurt meanwhile).",
    "DYING_TIME": "Length of its death animation.",
    "STAGGER_TIME": "How long a hit interrupts it.",
    "STAGGER_COOLDOWN": "After a stagger it shrugs hits off this long (no stun-lock).",
    "STRIKE_TIME": "Duration of the attack itself.",
    "RECOVER_TIME": "Seconds it is open for a counter-attack after attacking.",
    "POISE": "true = hits never interrupt it.",
    "KNOCKBACK": "How far a hit pushes it.",
    "KNOCKBACK_RESIST": "0 = normal, 1 = immovable.",
    "WINDUP_TIME": "WARNING time before the main attack. Smaller = harder to dodge.",
    "AIM_LOCK": "It stops tracking you this long before attacking. Smaller = harder to dodge.",
    "ATTACK_RANGE": "Starts its main attack from this far away.",
    "ATTACK_COOLDOWN": "Seconds between main attacks.",
    "LUNGE_SPEED": "Warrior: speed of the lunge.",
    "SLASH_RANGE": "Warrior basic attack: starts when you are this close.",
    "SLASH_WINDUP": "Warrior basic attack: warning time.",
    "SLASH_STRIKE": "Warrior basic attack: duration.",
    "SLASH_RECOVER": "Warrior basic attack: recovery.",
    "SLASH_LUNGE": "Warrior basic attack: hop speed.",
    "SLASH_DAMAGE": "Warrior basic attack: fraction of its normal damage.",
    "SLASH_COOLDOWN": "Warrior basic attack: seconds between slashes.",
    "PREFERRED": "Archer: it likes to stand between these distances from you: [near, far].",
    "SHOOT_RANGE": "Archer: [closest, farthest] distance it will shoot from.",
    "ARROW_SPEED": "Archer: arrow speed.",
    "COOLDOWN": "Archer: [min, max] seconds between shots.",
    "SNAP_CHANCE": "Archer basic attack: chance (0-1) that a shot is a quick snap shot.",
    "SNAP_WINDUP": "Archer basic attack: warning time.",
    "SNAP_SPEED": "Archer basic attack: arrow speed.",
    "SNAP_DAMAGE": "Archer basic attack: fraction of its normal damage.",
    "SNAP_COOLDOWN": "Archer basic attack: [min, max] seconds before the next shot.",
    "SLAM_RADIUS": "Brute: size of the hammer slam circle.",
    "SLAM_REACH": "Brute: how far in front of it the slam lands.",
    "SWIPE_RANGE": "Brute basic attack: starts when you are this close.",
    "SWIPE_WINDUP": "Brute basic attack: warning time.",
    "SWIPE_REACH": "Brute basic attack: how far in front it reaches.",
    "SWIPE_DAMAGE": "Brute basic attack: fraction of the slam damage.",
    "SWIPE_COOLDOWN": "Brute basic attack: seconds between swipes.",
    "SWIPE_CHANCE": "Brute basic attack: chance (0-1) to backhand instead of slamming when you are close.",
    "MEND_RANGE": "Acolyte: heals friends within this distance.",
    "MEND_AMOUNT": "Acolyte: health restored (tier 'normal').",
    "MEND_BELOW": "Acolyte: heals friends below this fraction of their health.",
    "RAISE_CAP": "Acolyte: won't raise the dead when this many friends are alive.",
    "RAISE_COOLDOWN": "Acolyte: seconds between raising the dead.",
    "BOLT_RANGE": "Acolyte: [closest, farthest] distance it fires soul bolts from.",
    "BOLT_SPEED": "Acolyte: soul bolt speed.",
    "WINDUPS": "Acolyte: warning time of each action.",
    "ACTION_COOLDOWN": "Acolyte: seconds between actions.",
}

TIER_DESC = {
    "normal": "Everyday monsters of the open world.",
    "veteran": "A mid-game crypt.",
    "elite": "Mini-boss guards.",
    "undying": "The Lich King's army.",
}
TIER_KEY_DESC = {"hp_scale": "Health multiplier.", "damage_scale": "Damage multiplier.",
                 "speed_scale": "Speed multiplier."}

# ----------------------------------------------------------------------
# writing TOML
# ----------------------------------------------------------------------


def fmt(value):
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, float):
        text = repr(value)
        return text if any(c in text for c in ".en") else text + ".0"
    if isinstance(value, int):
        return str(value)
    if isinstance(value, str):
        return json.dumps(value)
    if isinstance(value, (list, tuple)):
        return "[" + ", ".join(fmt(item) for item in value) + "]"
    raise TypeError(f"cannot write {value!r}")


def header(lines, title):
    lines += ["", "# " + "=" * 74, "# " + title, "# " + "=" * 74]


def setting(lines, key, value, desc):
    text = f"{key} = {fmt(value)}"
    lines.append(f"{text:<40}  # {desc}" if desc else text)


def build():
    L = ["""# ==========================================================================
#  RealmQuest  -  BALANCE CONFIG   (the Lich King, the minions, everything)
# ==========================================================================
#  Change a number, save, restart the game. That's it.
#
#   * Lines starting with # are notes. Anything after a # on a line is a note too.
#   * Keep the format:   name = value       (text goes in "quotes", lists in [brackets])
#   * Delete a line and the game uses its built-in default for it.
#   * A mistake never crashes the game: the bad line is ignored and a warning is
#     printed in the console, e.g.  [RealmQuest balance] [boss.phase3] 'combo' ...
#   * Want a quick reset? Run  python tools/make_balance_config.py --force
#
#  Times are in SECONDS, distances in PIXELS, "damage" is the health the player loses.
#  Handy tuning knobs:
#     make the boss tankier ........ [boss]         max_hp
#     make attacks spammier ........ [boss.phaseN]  idle, recover, combo, *_windup
#     make attacks easier to dodge . [boss.timing]   aim_lock      [boss.phaseN] *_windup
#     make the minions tougher ..... [tiers.*]       hp_scale / damage_scale   (his army: [boss.summons] tier)
#     tweak ONE monster ............ [monsters.skeleton_warrior] (and the others)
# =========================================================================="""]

    # ---- boss ----
    L += ["", "# " + "#" * 74, "#   THE LICH KING", "# " + "#" * 74]
    for sub, path, title, items in BOSS_GROUPS:
        header(L, f"{title}")
        L.append(f"[{path}]")
        for key, const, desc in items:
            value = B.__dict__[const]
            if isinstance(value, dict):                       # ATTACK_GLOW: a table of colours
                continue
            setting(L, key, value, desc)
        for key, const, desc in items:
            value = B.__dict__[const]
            if isinstance(value, dict):
                L += ["", f"[{path}.{key}]   # {desc}"]
                for k, v in value.items():
                    setting(L, k, v, "")
    for number in sorted(B.PHASE_STATS):
        header(L, PHASE_TITLES[number])
        L.append(f"[boss.phase{number}]")
        for key, value in B.PHASE_STATS[number].items():
            setting(L, key, value, PHASE_DESC.get(key, ""))
    header(L, "HIS ARMY: which minions he calls (and how often)")
    L.append("[boss.summons]")
    setting(L, "tier", M.MINION_TIER, "Which [tiers.*] his minions use (health / damage / speed multipliers).")
    for name in M.MINION_COST:
        L += ["", f"[boss.summons.{name}]"]
        setting(L, "cost", M.MINION_COST[name], SUMMON_DESC["cost"])
        setting(L, "weight", M.SUMMON_WEIGHT[name], SUMMON_DESC["weight"])
        setting(L, "limit", M.SUMMON_LIMIT[name], SUMMON_DESC["limit"])

    # ---- tiers ----
    L += ["", "# " + "#" * 74, "#   DIFFICULTY TIERS (used by every area / event / boss that spawns monsters)",
          "#   spawn_monster(\"skeleton_warrior\", x, y, tier=\"veteran\")   ->  picks the numbers below.",
          "#   You can add your own, e.g. [tiers.nightmare]", "# " + "#" * 74]
    for name, values in monsters.TIERS.items():
        L += ["", f"[tiers.{name}]   # {TIER_DESC.get(name, '')}"]
        for key, value in values.items():
            setting(L, key, value, TIER_KEY_DESC.get(key, ""))

    # ---- monsters ----
    L += ["", "# " + "#" * 74, "#   MONSTERS (stats at tier 'normal'; a tier multiplies health / damage / speed)",
          "# " + "#" * 74]
    for name, cls in monsters.MONSTERS.items():
        header(L, f"{cls.DISPLAY_NAME.upper()}")
        L.append(f"[monsters.{name}]")
        dicts = []
        for const, value in balance.monster_settings(cls).items():
            if isinstance(value, dict):
                dicts.append((const, value))
                continue
            setting(L, const.lower(), value, MONSTER_DESC.get(const, ""))
        for const, value in dicts:
            L += ["", f"[monsters.{name}.{const.lower()}]   # {MONSTER_DESC.get(const, '')}"]
            for k, v in value.items():
                setting(L, k, v, "")
    return "\n".join(L) + "\n"


def main(argv):
    text = build()
    if "--stdout" in argv:
        sys.stdout.write(text)
        return 0
    path = os.path.join(REPO, "config", "balance.toml")
    if os.path.exists(path) and "--force" not in argv:
        if input(f"{path} exists and will be overwritten (your edits are lost). Continue? [y/N] ").lower() != "y":
            print("Cancelled.")
            return 1
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(text)
    print("Wrote", path)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
