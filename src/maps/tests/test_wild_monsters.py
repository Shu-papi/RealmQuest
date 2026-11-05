"""
The wilds use the dungeons' own monsters, tiered like the dungeons (1 Goblin, 2 Berserker, 3 Lich):
real sprites, their dungeon AI once they turn on the hero, numbers from the same config files.
Run from the repo root:  python -m unittest discover -s src/maps/tests
"""
import math
import os
import random
import sys
import types
import unittest

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
if REPO not in sys.path:
    sys.path.insert(0, REPO)

import pygame

pygame.init()
pygame.display.set_mode((1152, 648))

from src.maps import combat, night_raid, wilds   # noqa: E402

DT = 1 / 60


class OpenGround:
    """Open grass everywhere (what night_raid._Ground offers: can_stand only)."""

    def can_stand(self, x, y):
        return 0 <= x <= 5000 and 0 <= y <= 5000


class FakeWorld:
    def __init__(self):
        self.colliders, self.dyn_colliders = [], []
        self.player = types.SimpleNamespace(x=0.0, y=0.0, dash_t=0.0, root_t=0.0)
        self.toasts = []

    def toast(self, text, col=None):
        self.toasts.append(text)


def make_wilds():
    world = FakeWorld()
    save = types.SimpleNamespace(gold=0, level=1, pull_from=lambda pc: None)
    pc = combat.PlayerCombat("warrior")
    sfx = types.SimpleNamespace(play=lambda *a, **k: None)
    got = []
    w = wilds.Wilds(world, save, pc, sfx, on_xp=lambda xp, x, y: got.append(xp))
    w.ground = OpenGround()
    for g in w.groups():
        if g.host is not None:
            g.host.ground = w.ground
    return w, world, pc, got


class Tiers(unittest.TestCase):
    def test_each_tier_is_its_dungeons_family(self):
        w, *_ = make_wilds()
        family = {1: {"Slime", "Goblin Minion", "Goblin Shaman", "Wild Boar"},
                  2: {"Orc Warrior", "Orc Shaman", "Treant"},
                  3: {"Skeleton Warrior", "Skeleton Archer", "Skeleton Acolyte", "Bone Brute"}}
        for pack in w.packs:
            for m in pack.mobs:
                self.assertIn(m.name, family[pack.tier], (pack.roster, m.name))

    def test_no_placeholder_anywhere(self):
        w, *_ = make_wilds()
        for m in w.enemies():
            self.assertTrue(m.skin or isinstance(m, wilds._wild_skeleton_class()), m.name)

    def test_regular_mobs_are_tough(self):
        w, *_ = make_wilds()
        for m in w.enemies():
            self.assertGreaterEqual(m.max_hp, 150, m.name)

    def test_numbers_come_from_the_dungeon_rows(self):
        rng = random.Random(1)
        m = wilds.make_wild("orc_warrior", 0, 0, (0, 0), 50, rng, types.SimpleNamespace(bolts=[], hazards=[]))
        self.assertEqual(m.max_hp, combat.BERSERKER_MOBS["orc"][1])
        self.assertEqual(m.cfg, (combat.BERSERKER_MOBS, "orc"))


class Fighting(unittest.TestCase):
    def fight(self, roster, seconds=6.0):
        w, world, pc, got = make_wilds()
        pc.god = True
        pack = next(p for p in w.packs if p.roster == roster)
        world.player.x, world.player.y = pack.home[0] + 120, pack.home[1]
        seen = set()
        for _ in range(int(seconds / DT)):
            w.update(DT, True)
            seen |= {type(s).__name__ for s in w.bolts + w.hazards}
        return w, world, pc, pack, seen

    def test_a_goblin_pack_turns_on_the_hero(self):
        w, world, pc, pack, seen = self.fight("goblins")
        self.assertTrue(all(m.aggro for m in pack.mobs))
        hx, hy = world.player.x, world.player.y
        self.assertTrue(any(math.hypot(m.x - hx, m.y - hy) < 60 for m in pack.mobs), "they close in")

    def test_wild_shamans_throw_fireballs_on_open_ground(self):
        w, world, pc, got = make_wilds()
        rng = random.Random(2)
        group = wilds.Group("goblins", (1000, 1000), 100, rng, w)
        shaman = group.add(1000, 1000, "goblin_shaman")
        shaman.aggro = True
        player = types.SimpleNamespace(x=1180.0, y=1000.0, dash_t=0.0)
        pc.god = False
        flying = 0
        for _ in range(int(4 / DT)):
            shaman.step(DT, player, w.ground, pc, w)
            w._update_spells(DT, player, pc, w.ground)
            flying = max(flying, len(w.bolts))
            pc.hp = pc.max_hp
        self.assertGreater(flying, 0, "a fireball flew (and did not crash on the overworld ground)")

    def test_treant_roots_hold_the_overworld_hero(self):
        w, world, pc, got = make_wilds()
        from src.maps import surface_world
        hero = surface_world.Player(1100, 1000)
        rng = random.Random(4)
        group = wilds.Group("treants", (1000, 1000), 100, rng, w)
        treant = group.add(1000, 1000, "treant")
        treant.aggro = True
        held = 0.0
        for _ in range(int(8 / DT)):
            treant.step(DT, hero, w.ground, pc, w)
            w._update_spells(DT, hero, pc, w.ground)
            held = max(held, hero.root_t)
            pc.hp, pc.iframes = pc.max_hp, 0.0             # (its own punches must not shield the hero)
        self.assertGreater(held, 0, "the roots held the hero")

    def test_skeletons_chase_and_die(self):
        w, world, pc, pack, seen = self.fight("skeletons", 3.0)
        self.assertTrue(all(m.aggro for m in pack.mobs))
        m = pack.mobs[0]
        hits = 0
        while not m.dead and hits < 500:
            w.player_swing(world.player, 1.0, 0.0, 0)          # (aims anywhere: hit it directly below)
            m.take_damage(25)
            hits += 1
        self.assertTrue(m.dead)
        self.assertGreater(hits, 5, "takes a beating")

    def test_a_kill_gives_about_the_old_xp(self):
        w, world, pc, got = make_wilds()
        pack = next(p for p in w.packs if p.roster == "goblins")
        m = pack.mobs[0]
        m.take_damage(10_000)
        pack.reap()
        self.assertEqual(len(got), 1)
        self.assertLess(got[0], 30, "not 25x the old XP")
        self.assertGreaterEqual(got[0], 1)

    def test_warrior_needs_about_a_dozen_hits_for_a_minion(self):
        pc = combat.PlayerCombat("warrior")
        hp = combat.GOBLIN_MOBS["minion"][1]
        self.assertTrue(8 <= math.ceil(hp / pc.sword_dmg) <= 16, (hp, pc.sword_dmg))

    def test_events_use_the_tier_family(self):
        w, world, pc, got = make_wilds()
        for tier, names in ((1, {"Gloomgut the Great Slime"}), (2, {"Black Tusk the Warlord"}),
                            (3, {"The Hollow Widow"})):
            w.save.level = {1: 1, 2: 6, 3: 12}[tier]
            for seed in range(30):
                w.rng.seed(seed)
                w.event = None
                w._start_event()
                if w.event["kind"] == "champion":
                    break
            self.assertEqual({m.name for m in w.event["group"].mobs}, names)
            for _ in range(30):
                w.update(DT, True)

    def test_config_reload_reaches_wild_mobs(self):
        w, *_ = make_wilds()
        m = next(m for m in w.enemies() if getattr(m, "kind_name", None) == "slime")
        old = combat.GOBLIN_MOBS["slime"]
        try:
            combat.GOBLIN_MOBS["slime"] = (old[0], old[1] * 2) + old[2:]
            w.refresh_config()
            self.assertEqual(m.max_hp, old[1] * 2)
        finally:
            combat.GOBLIN_MOBS["slime"] = old


class Raiders(unittest.TestCase):
    def test_berserker_raiders_are_orcs_and_treants(self):
        rng = random.Random(5)
        names = {night_raid.RaidMonster("berserker", night_raid.PATHS["berserker"], rng).name for _ in range(30)}
        self.assertEqual(names, {combat.BERSERKER_MOBS["orc"][0], combat.BERSERKER_MOBS["treant"][0]})


if __name__ == "__main__":
    unittest.main()
