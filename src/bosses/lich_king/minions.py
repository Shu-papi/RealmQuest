"""
minions.py - The Lich King's minions.

The monsters themselves now live in the shared  src/monsters/  package so every area and event
can use them. This file only holds what is specific to the Lich King: WHICH minions he calls and
how many he can control at once.

    Skeleton   still works (it is the Skeleton Warrior), so old code keeps running.

HIS ARMY IS "UNDYING" TIER: roughly 3x the health, 30% more damage and 15% faster than the same skeleton
in a normal area (see TIERS in monsters/__init__.py). Other areas can pick a gentler tier.
"""
try:
    import balance                                                          # src/ is on sys.path
except ImportError:
    from src import balance
try:
    from monsters import spawn_monster, separate, collect_requests         # src/ is on sys.path
    from monsters import SkeletonWarrior
except ImportError:                                                         # run as src.bosses
    from src.monsters import spawn_monster, separate, collect_requests
    from src.monsters import SkeletonWarrior

__all__ = ["Skeleton", "MINION_COST", "MINION_TIER", "minion_load", "pick_summons", "spawn_monster",
           "separate", "collect_requests"]

Skeleton = SkeletonWarrior                    # the old name, kept so nothing breaks

MINION_TIER = "undying"

# How much of his "army budget" each minion uses (he can control MAX_MINIONS worth at once)
MINION_COST = {
    "skeleton_warrior": 1,
    "skeleton_archer": 1,
    "skeleton_acolyte": 1,
    "skeleton_brute": 2,
}
# How likely he is to call each one, and the most that may be alive together
SUMMON_WEIGHT = {"skeleton_warrior": 5.0, "skeleton_archer": 3.0, "skeleton_acolyte": 2.0, "skeleton_brute": 1.5}
SUMMON_LIMIT = {"skeleton_warrior": 6, "skeleton_archer": 3, "skeleton_acolyte": 2, "skeleton_brute": 2}


# config/bosses/lich_king.toml:  [summons] tier = "..."   and   [summons.<monster>] cost / weight / limit
_tier = {"minion_tier": MINION_TIER}
balance.apply_summons(MINION_COST, SUMMON_WEIGHT, SUMMON_LIMIT, _tier)
MINION_TIER = _tier["minion_tier"]


@balance.on_reload
def _after_reload():
    global MINION_TIER
    MINION_TIER = _tier["minion_tier"]


def minion_load(minions):
    """How much of the army budget these living minions use."""
    return sum(MINION_COST.get(getattr(m, "NAME", ""), 1) for m in minions if m.is_alive())


def pick_summons(rng, minions, budget, picks=3):
    """Choose which monsters to call now: a mixed squad that fits in the free budget."""
    alive = [getattr(m, "NAME", "") for m in minions if m.is_alive()]
    chosen = []
    free = budget - minion_load(minions)
    for _ in range(picks):
        options = [n for n in MINION_COST
                   if MINION_COST[n] <= free
                   and (alive + chosen).count(n) < SUMMON_LIMIT[n]]
        if not options:
            break
        name = rng.choices(options, weights=[SUMMON_WEIGHT[n] for n in options])[0]
        chosen.append(name)
        free -= MINION_COST[name]
    return chosen
