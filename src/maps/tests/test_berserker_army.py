"""
The Berserker Dungeon's monsters: Orc Warriors (axe slash), Orc Shamans (a meteor every 3 s), Treants
(roots that hold the hero), the Elder Treant elite and the Orc Warlord mini-boss (a bigger, recoloured orc).
Run from the repo root:  python -m unittest discover -s src/maps/tests
"""
import json
import math
import os
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

from src.maps import combat, dungeon_map   # noqa: E402
from monsters import game_sprites           # noqa: E402  (combat.py put src/ on the path)

DT = 1 / 60
TILE = combat.TILE
NEW_SKINS = ("orc_warrior", "orc_shaman", "orc_warlord", "treant")


def floor():
    return types.SimpleNamespace(can_stand=lambda x, y: True)


class Hero:
    """The bits of the dungeon's Player that monsters use (and root)."""

    def __init__(self, x=0.0, y=0.0):
        self.x, self.y = x, y
        self.dash_t = 0.0
        self.root_t = 0.0

    def afflict(self, name, seconds):
        if name == "root":
            self.root_t = max(self.root_t, seconds)


def start_room(floor_name, role):
    d = dungeon_map.Dungeon(floor_name, seed=7)
    enc = combat.Encounters(d)
    room = next(i for i, r in enumerate(d.room_roles) if r == role)
    rect = d.rooms[room]
    enc._start_room(room, Hero(rect.centerx * TILE, (rect.bottom - 3) * TILE))
    return enc


class Sprites(unittest.TestCase):
    def test_every_new_skin_loads_with_its_clips(self):
        for key in NEW_SKINS:
            with self.subTest(skin=key):
                anims = game_sprites.skin(key)
                for clip in ("idle", "walk", "attack"):
                    self.assertIn(clip, anims)
                    self.assertTrue(anims[clip].frames[1])
                cfg = game_sprites.sheet_config(key)
                hit = cfg["animations"]["attack"]["hit_frame"]
                self.assertLess(hit, len(cfg["animations"]["attack"]["frames"]))
        self.assertIn("cast", game_sprites.skin("orc_shaman"))

    def test_the_warlord_is_a_recoloured_orc(self):
        orc = game_sprites.skin("orc_warrior")["idle"].frames[1][0]
        lord = game_sprites.skin("orc_warlord")["idle"].frames[1][0]
        self.assertEqual(orc.get_size(), lord.get_size())
        w, h = orc.get_size()
        differ = sum(1 for x in range(0, w, 2) for y in range(0, h, 2) if orc.get_at((x, y)) != lord.get_at((x, y)))
        self.assertGreater(differ, 50)

    def test_the_generator_wrote_its_configs(self):
        for key in NEW_SKINS:
            folder, name, _k = game_sprites.SHEET_SKINS[key]
            with open(os.path.join(folder, name), encoding="utf-8") as f:
                self.assertEqual(json.load(f)["made_by"], "tools/make_berserker_sprites.py")


class Rooms(unittest.TestCase):
    def test_rooms_hold_orcs_shamans_and_treants(self):
        for floor_name, role in (("2-1", "combat"), ("2-2", "combat"), ("14-1", "combat")):
            with self.subTest(floor=floor_name):
                enc = start_room(floor_name, role)
                regulars = [e for e in enc.enemies if getattr(e, "kind", "normal") == "normal"]
                self.assertTrue(4 <= len(regulars) <= 6)
                self.assertTrue({e.skin for e in regulars} <= {"orc_warrior", "orc_shaman", "treant"})
                self.assertLessEqual(sum(e.skin == "orc_shaman" for e in regulars), combat.MAX_SHAMANS)

    def test_guard_room_has_an_elder_treant(self):
        enc = start_room("2-1", "guard")
        elite = [e for e in enc.enemies if getattr(e, "kind", "") == "elite"]
        self.assertEqual([(e.name, e.skin, e.skin_scale) for e in elite], [("Elder Treant", "treant", combat.ELDER_SCALE)])

    def test_the_mini_boss_is_the_orc_warlord(self):
        for floor_name, role in (("2-2", "miniboss"), ("13-1", "lair"), ("14-1", "lair")):
            with self.subTest(floor=floor_name):
                enc = start_room(floor_name, role)
                mb = enc.miniboss
                self.assertIn(mb, enc.enemies)
                self.assertIsInstance(mb, combat.OrcEnemy)
                self.assertEqual((mb.name, mb.skin, mb.kind), ("Orc Warlord", "orc_warlord", "elite"))
                self.assertEqual(mb.skin_scale, combat.WARLORD_SCALE)
                self.assertGreater(mb.skin_scale, 1.0)
                self.assertTrue(mb.cc_immune)

    def test_hazards_clear_on_retry(self):
        enc = start_room("2-1", "combat")
        enc.hazards.append(combat.MeteorStrike(0, 0, 4))
        enc.retry_room()
        self.assertEqual(enc.hazards, [])


class OrcSlash(unittest.TestCase):
    def setUp(self):
        self.orc = combat.OrcEnemy(100, 100, "Orc Warrior", 12, 84, 3, (0, 0, 0), 15)
        self.orc.skin = "orc_warrior"
        self.pc = combat.PlayerCombat("warrior")

    def test_it_winds_up_before_the_hit(self):
        hero = Hero(130, 100)
        hp = self.pc.hp
        self.orc.update(DT, hero, floor(), self.pc)              # the swing starts
        self.assertIsNotNone(self.orc.swing)
        self.assertEqual(self.pc.hp, hp)                         # ...but nothing lands yet
        for _ in range(int(self.orc.release / DT) + 2):
            self.orc.update(DT, hero, floor(), self.pc)
        self.assertLess(self.pc.hp, hp)

    def test_stepping_behind_it_dodges_the_slash(self):
        hero = Hero(130, 100)
        self.orc.update(DT, hero, floor(), self.pc)              # it aims to the right...
        hero.x = 70                                              # ...the hero slips behind it
        hp = self.pc.hp
        for _ in range(int(self.orc.length / DT) + 2):
            self.orc.update(DT, hero, floor(), self.pc)
        self.assertEqual(self.pc.hp, hp)


class Meteors(unittest.TestCase):
    def test_a_shaman_casts_every_three_seconds(self):
        hazards = []
        shaman = combat.OrcShaman(100, 100, "Orc Shaman", 9, 66, 2, (0, 0, 0), 14, hazards=hazards)
        shaman.attack_cd = 0.0
        hero = Hero(300, 100)
        pc = combat.PlayerCombat("warrior")
        times = []
        t = 0.0
        while t < 7.0:                                           # casts at ~0.5, 3.5 and 6.5 s
            n = len(hazards)
            shaman.update(DT, hero, floor(), pc)
            t += DT
            if len(hazards) > n:
                times.append(t)
        self.assertEqual(len(times), 3)
        self.assertAlmostEqual(times[1] - times[0], combat.METEOR_CD, delta=0.05)

    def test_a_meteor_hurts_only_inside_its_circle_and_only_on_impact(self):
        pc = combat.PlayerCombat("warrior")
        inside, outside = Hero(10, 0), Hero(combat.METEOR_R + 20, 0)
        for hero, should_hurt in ((inside, True), (outside, False)):
            pc.reset()
            m = combat.MeteorStrike(0, 0, combat.METEOR_DMG)
            m.update(combat.METEOR_FALL * 0.5, hero, floor(), pc)
            self.assertEqual(pc.hp, pc.max_hp)                  # still falling
            m.update(combat.METEOR_FALL, hero, floor(), pc)
            self.assertEqual(pc.hp < pc.max_hp, should_hurt)
            self.assertIn("boom", m.pop_sounds())


class Roots(unittest.TestCase):
    def test_a_treant_roots_the_hero_who_stands_in_it(self):
        hazards = []
        treant = combat.TreantEnemy(100, 100, "Treant", 18, 48, 3, (0, 0, 0), 18, hazards=hazards)
        treant.root_cd = 0.0
        hero = Hero(250, 100)
        pc = combat.PlayerCombat("warrior")
        for _ in range(60):
            treant.update(DT, hero, floor(), pc)
            for h in hazards:
                h.update(DT, hero, floor(), pc)
        self.assertTrue(hazards)
        for _ in range(int(combat.ROOT_DELAY / DT) + 5):
            for h in hazards:
                h.update(DT, hero, floor(), pc)
        self.assertGreater(hero.root_t, 0)
        self.assertLess(pc.hp, pc.max_hp)

    def test_outside_or_dashing_escapes_the_roots(self):
        pc = combat.PlayerCombat("warrior")
        away = Hero(combat.ROOT_R + 30, 0)
        snare = combat.RootSnare(0, 0)
        snare.update(combat.ROOT_DELAY + 0.01, away, floor(), pc)
        self.assertEqual(away.root_t, 0)
        dasher = Hero(0, 0)
        pc.dash_inv = 0.5
        snare = combat.RootSnare(0, 0)
        snare.update(combat.ROOT_DELAY + 0.01, dasher, floor(), pc)
        self.assertEqual(dasher.root_t, 0)


if __name__ == "__main__":
    unittest.main()
