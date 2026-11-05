"""
RealmQuest monster package (real-time, Pygame).

    from monsters import spawn_monster, MonsterGroup, deal_damage       # or: from src.monsters import ...

    wolf = spawn_monster("skeleton_warrior", 300, 400)                  # one monster
    frost_archer = spawn_monster("skeleton_archer", 500, 200, variant="frost")   # re-skinned for snow areas

    group = MonsterGroup()                                              # a whole room / event / ambush
    group.spawn_wave(["skeleton_warrior"] * 3 + ["skeleton_acolyte"], bounds, player)

    # every frame
    group.update(dt, player, bounds)
    group.draw(screen)

    # when the player swings a sword or casts a spell
    for target in group.hittables():
        ...check distance...
        deal_damage(target, 20, source=(player.x, player.y))            # source adds knockback

Every monster lives in a folder or file here and has its art in assets/monsters/<name>/.
To add one, see HOW_TO_ADD_A_MONSTER.md. Only the two lines marked ADD HERE change in this file.
"""
try:
    import balance                                                          # src/ is on sys.path
except ImportError:                                                         # run as src.monsters
    from src import balance
from .base_monster import Monster
from .group import MonsterGroup, collect_requests, separate
from .skeleton import SkeletonAcolyte, SkeletonArcher, SkeletonBrute, SkeletonWarrior   # ADD HERE (1/2)
from .sprites import VARIANTS

MONSTERS = {
    "skeleton_warrior": SkeletonWarrior,
    "skeleton_archer": SkeletonArcher,
    "skeleton_brute": SkeletonBrute,
    "skeleton_acolyte": SkeletonAcolyte,
    # ADD HERE (2/2): "wolf": Wolf,
}


# Difficulty tiers: one word instead of three numbers. Use them for any area or event, e.g.
#   spawn_monster("skeleton_warrior", x, y, tier="veteran")      a mid-game crypt
#   spawn_monster("skeleton_brute", x, y, tier="elite")          a mini-boss guard
# "undying" is what the Lich King's army uses. Anything passed explicitly (hp_scale=...) wins over the tier.
TIERS = {
    "normal":  {"hp_scale": 1.0, "damage_scale": 1.0,  "speed_scale": 1.0},
    "veteran": {"hp_scale": 1.6, "damage_scale": 1.15, "speed_scale": 1.05},
    "elite":   {"hp_scale": 2.5, "damage_scale": 1.25, "speed_scale": 1.1},
    "undying": {"hp_scale": 3.0, "damage_scale": 1.3,  "speed_scale": 1.15},
}

# config/balance.toml overrides everything above: [monsters.<name>] and [tiers.<name>] (see src/balance.py)
balance.apply_monsters(MONSTERS, TIERS)


def spawn_monster(name, x, y, tier="normal", **options):
    """
    Make a monster by name. Options: variant="bone"|"cursed"|"frost"|"ember"|"plague",
    seed=, spawn=False (appear instantly instead of rising from the ground),
    tier="normal"|"veteran"|"elite"|"undying" (see TIERS), or the raw numbers
    hp_scale=1.0, damage_scale=1.0, speed_scale=1.0, loot=.
    """
    if name not in MONSTERS:
        raise ValueError(f"Unknown monster '{name}'. Choose from: {list(MONSTERS)}")
    if tier not in TIERS:
        raise ValueError(f"Unknown tier '{tier}'. Choose from: {list(TIERS)}")
    for key, value in TIERS[tier].items():
        options.setdefault(key, value)
    return MONSTERS[name](x, y, **options)


def list_monsters():
    return list(MONSTERS)


def list_variants():
    return list(VARIANTS)


def deal_damage(target, amount, source=None):
    """
    Hurt anything the player can hit: a monster (knockback from `source`) or a boss.
    Returns the damage actually dealt.
    """
    if isinstance(target, Monster):
        return target.take_damage(amount, source=source)
    return target.take_damage(amount)
