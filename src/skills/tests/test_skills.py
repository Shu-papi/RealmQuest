"""
Checks the hero skills: costs, cooldowns, refusing without mana / energy, every skill
damaging enemies in range (and not out of range), stun / slow, and walls stopping projectiles.
Run from the repo root:  python -m unittest discover -s src/skills/tests
"""
import os
import sys
import types
import unittest

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
SRC_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)

import pygame

from skills import classes
from skills.skills import CLASS_SKILLS, SLOTS, Pools, SkillCaster, SkillFX

DT = 1 / 60


class Dummy:
    def __init__(self, x, y, hp=500, boss=False):
        self.x, self.y, self.hp, self.max_hp = x, y, hp, hp
        self.radius = 14
        self.stun_t = self.slow_t = 0.0
        self.aggro = False
        if boss:
            self.cc_immune = True

    @property
    def dead(self):
        return self.hp <= 0

    def take_damage(self, n):
        self.hp -= n


def run(fx, targets, seconds, blocked=None, owner=None):
    owner = owner or types.SimpleNamespace(x=0.0, y=0.0)
    for _ in range(int(seconds / DT)):
        fx.update(DT, targets, owner, blocked)


def cast(cls, slot, targets, seconds=4.0, aim=(1.0, 0.0), power=3, blocked=None):
    st = classes.stats(cls)
    pools, caster, fx = Pools(st["bars"]), SkillCaster(cls), SkillFX()
    d = caster.cast(slot, pools, 0.0, 0.0, aim, power, fx)
    run(fx, targets, seconds, blocked)
    return d, pools, caster, fx


class ClassData(unittest.TestCase):
    def test_every_class_has_two_skills_and_a_special(self):
        for cls in classes.CLASS_ORDER:
            slots = [s.slot for s in CLASS_SKILLS[cls]]
            self.assertEqual(slots, list(SLOTS), cls)

    def test_resource_bars(self):
        bars = {cls: [name for name, _m, _r in classes.stats(cls)["bars"]] for cls in classes.CLASS_ORDER}
        self.assertEqual(sorted(bars["mage"]), ["mana", "stamina"])
        self.assertEqual(sorted(bars["warrior"]), ["energy", "stamina"])
        self.assertEqual(sorted(bars["archer"]), ["energy", "stamina"])
        self.assertEqual(classes.stats("mage")["skill_resource"], "mana")
        self.assertEqual(classes.stats("warrior")["skill_resource"], "energy")


class Casting(unittest.TestCase):
    def test_cost_and_cooldown(self):
        st = classes.stats("mage")
        pools, caster, fx = Pools(st["bars"]), SkillCaster("mage"), SkillFX()
        full = pools.get("mana")
        d = caster.cast("skill", pools, 0, 0, (1, 0), 3, fx)
        self.assertIsNotNone(d)
        self.assertEqual(pools.get("mana"), full - d.cost)
        self.assertIsNone(caster.cast("skill", pools, 0, 0, (1, 0), 3, fx), "still on cooldown")
        for _ in range(int((d.cooldown + 0.1) / DT)):
            caster.update(DT)
        self.assertIsNotNone(caster.cast("skill", pools, 0, 0, (1, 0), 3, fx))

    def test_refused_without_enough_resource(self):
        st = classes.stats("warrior")
        pools, caster, fx = Pools(st["bars"]), SkillCaster("warrior"), SkillFX()
        pools.spend("energy", pools.get("energy") - 10)
        self.assertIsNone(caster.cast("special", pools, 0, 0, (1, 0), 3, fx))
        self.assertEqual(fx.effects, [])
        self.assertEqual(caster.cd["special"], 0.0, "a refused cast doesn't start the cooldown")

    def test_resources_regenerate(self):
        pools = Pools(classes.stats("mage")["bars"])
        pools.spend("mana", 50)
        before = pools.get("mana")
        pools.update(1.0)
        self.assertGreater(pools.get("mana"), before)
        pools.update(100.0)
        self.assertEqual(pools.get("mana"), pools.max("mana"))


class SkillsHit(unittest.TestCase):
    """Each skill hits a dummy where it should land, and misses one far away."""

    WHERE = {   # where a target should stand (aiming right) to be hit
        "whirlwind": (60, 0), "shield_bash": (70, 0), "earthsplitter": (150, 0),
        "fireball": (200, 0), "frost_nova": (80, 0), "meteor": (170, 0),
        "arrow_volley": (250, 0), "piercing_shot": (300, 0), "rain_of_arrows": (150, 0),
    }

    def test_every_skill(self):
        for cls in classes.CLASS_ORDER:
            for d in CLASS_SKILLS[cls]:
                with self.subTest(skill=d.id):
                    near = Dummy(*self.WHERE[d.id])
                    far = Dummy(-900, 900)
                    cast(cls, d.slot, [near, far])
                    self.assertLess(near.hp, near.max_hp, f"{d.id} should hit")
                    self.assertEqual(far.hp, far.max_hp, f"{d.id} should miss")

    def test_cone_skills_miss_behind(self):
        for cls, slot in (("warrior", "special"), ("warrior", "skill_2")):
            behind = Dummy(-80, 0)
            cast(cls, slot, [behind], aim=(1.0, 0.0))
            self.assertEqual(behind.hp, behind.max_hp)

    def test_piercing_shot_passes_through(self):
        a, b = Dummy(150, 0), Dummy(300, 0)
        cast("archer", "skill_2", [a, b])
        self.assertLess(a.hp, a.max_hp)
        self.assertLess(b.hp, b.max_hp)

    def test_stun_and_slow(self):
        t = Dummy(70, 0)
        cast("warrior", "skill_2", [t], seconds=0.3)
        self.assertGreater(t.stun_t, 0)
        t2 = Dummy(80, 0)
        cast("mage", "skill_2", [t2], seconds=0.3)
        self.assertGreater(t2.slow_t, 0)
        boss = Dummy(70, 0, boss=True)
        cast("warrior", "skill_2", [boss], seconds=0.3)
        self.assertEqual(boss.stun_t, 0.0, "bosses can't be stunned")

    def test_hit_wakes_monsters(self):
        t = Dummy(60, 0)
        cast("warrior", "skill", [t], seconds=0.3)
        self.assertTrue(t.aggro)

    def test_walls_stop_projectiles(self):
        t = Dummy(300, 0)
        wall = lambda x, y: x > 100
        cast("archer", "skill_2", [t], blocked=wall)
        self.assertEqual(t.hp, t.max_hp)

    def test_shield_bash_asks_for_a_lunge(self):
        _d, _p, _c, fx = cast("warrior", "skill_2", [], seconds=0.0)
        self.assertEqual(fx.lunge, (1.0, 0.0))

    def test_damage_scales_with_power(self):
        weak, strong = Dummy(200, 0), Dummy(200, 0)
        cast("mage", "skill", [weak], power=2)
        cast("mage", "skill", [strong], power=6)
        self.assertGreater(strong.max_hp - strong.hp, weak.max_hp - weak.hp)


class Drawing(unittest.TestCase):
    def test_every_effect_draws(self):
        pygame.init()
        screen = pygame.Surface((800, 600))
        for cls in classes.CLASS_ORDER:
            st = classes.stats(cls)
            pools, caster, fx = Pools(st["bars"]), SkillCaster(cls), SkillFX()
            for slot in SLOTS:
                caster.cast(slot, pools, 400, 300, (1, 0), 3, fx)
            dummy = Dummy(500, 300)
            for i in range(40):
                fx.update(DT, [dummy], types.SimpleNamespace(x=400, y=300))
                fx.draw(screen, 0, 0, i * DT)


if __name__ == "__main__":
    unittest.main()
