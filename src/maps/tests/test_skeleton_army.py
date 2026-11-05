"""
The Lich King's skeletons outside his boss room: every room of the Lich King Dungeon and the two undead
mini dungeons (the goblins' rule: 4-6 per room, an elite on guard rooms, a big recoloured Warden as the mini-boss),
and the north-road night raid. Run from the repo root:  python -m unittest discover -s src/maps/tests

The raid tests build a real Game on a temporary save file, never on savegame.json.
"""
import os
import sys
import tempfile
import types
import unittest
from pathlib import Path

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
if REPO not in sys.path:
    sys.path.insert(0, REPO)

import pygame

pygame.init()
pygame.display.set_mode((1152, 648))

from src.maps import combat, dungeon_map, night_raid, save_state   # noqa: E402
# combat.py put src/ on the path: the game imports these as top-level packages, so the tests must too
from monsters import MONSTERS, spawn_monster                       # noqa: E402
from monsters.in_game import (ROSTER_CAPS, WARDEN_SIZE, SkeletonEnemy, SkeletonHost,   # noqa: E402
                              skeleton_roster)

DT = 1 / 60
TILE = combat.TILE


def start_room(floor, role):
    d = dungeon_map.Dungeon(floor, seed=7)
    enc = combat.Encounters(d)
    room = next(i for i, r in enumerate(d.room_roles) if r == role)
    rect = d.rooms[room]
    player = types.SimpleNamespace(x=rect.centerx * TILE, y=(rect.bottom - 3) * TILE, dash_t=0.0)
    enc._start_room(room, player)
    return enc, room, player


class Rooms(unittest.TestCase):
    def test_every_lich_room_holds_four_to_six_skeletons(self):
        for floor in ("3-1", "3-2"):
            d = dungeon_map.Dungeon(floor, seed=7)
            for k, role in enumerate(d.room_roles):
                if role in combat.SAFE_ROLES or k == len(d.rooms) - 1 and floor.endswith("-3"):
                    continue
                with self.subTest(floor=floor, role=role):
                    enc, _room, _p = start_room(floor, role)
                    regulars = [e for e in enc.enemies if e.kind == "normal"]
                    self.assertTrue(all(isinstance(e, SkeletonEnemy) for e in enc.enemies))
                    self.assertTrue(4 <= len(regulars) <= 6, len(regulars))
                    names = [e.monster.NAME for e in regulars]
                    for name, cap in ROSTER_CAPS.items():
                        self.assertLessEqual(names.count(name), cap, name)

    def test_the_roster_keeps_its_caps(self):
        import random
        rng = random.Random(3)
        for _ in range(200):
            names = skeleton_roster(rng, 6)
            self.assertEqual(len(names), 6)
            self.assertLessEqual(names.count("skeleton_brute"), 1)
            self.assertLessEqual(names.count("skeleton_acolyte"), 1)

    def test_a_guard_room_has_an_elite_brute(self):
        enc, _room, _p = start_room("3-1", "guard")
        elites = [e for e in enc.enemies if e.kind == "elite"]
        self.assertEqual(len(elites), 1)
        self.assertEqual(elites[0].monster.NAME, "skeleton_brute")

    def test_the_wardens_are_big_recoloured_minions(self):
        normal = spawn_monster("skeleton_warrior", 0, 0, spawn=False)
        for floor, role, name, variant in (("3-2", "miniboss", "Bone Warden", "cursed"),
                                           ("15-1", "lair", "Cinder Warden", "ember"),
                                           ("16-1", "lair", "Hollow Warden", "frost")):
            with self.subTest(floor=floor):
                enc, _room, _p = start_room(floor, role)
                mb = enc.miniboss
                self.assertIn(mb, enc.enemies)
                self.assertEqual((mb.name, mb.kind, mb.monster.variant), (name, "elite", variant))
                self.assertEqual(mb.monster.NAME, "skeleton_warrior")            # a minion, reused
                self.assertAlmostEqual(mb.radius, normal.radius * WARDEN_SIZE)
                self.assertGreaterEqual(mb.monster.sheet.pixel_size[1], normal.sheet.pixel_size[1] * 1.5)
                self.assertTrue(mb.cc_immune)
                self.assertGreater(mb.max_hp, max(e.max_hp for e in enc.enemies if e is not mb))

    def test_mini_dungeon_regulars_wear_their_colours(self):
        for floor, variant in (("15-1", "ember"), ("16-1", "plague")):
            enc, _room, _p = start_room(floor, "lair")
            self.assertEqual({e.monster.variant for e in enc.enemies if e.kind == "normal"}, {variant})

    def test_normal_size_monsters_are_unchanged(self):
        m = spawn_monster("skeleton_warrior", 0, 0)
        self.assertEqual((m.size, m.radius, m.FOOT), (1.0, MONSTERS["skeleton_warrior"].RADIUS,
                                                      MONSTERS["skeleton_warrior"].FOOT))

    def test_hp_is_in_game_units_and_hits_land(self):
        enc, _room, _p = start_room("3-1", "combat")
        e = enc.enemies[0]
        self.assertAlmostEqual(e.hp, e.monster.hp / e.host.hp_power)
        e.monster.state = "chase"                 # (risen from the floor)
        before = e.hp
        e.take_damage(2)
        self.assertLess(e.hp, before)

    def test_a_fight_hurts_the_hero_and_a_clear_rewards_him(self):
        enc, room, player = start_room("3-1", "combat")
        pc = combat.PlayerCombat("warrior")
        hp = pc.hp
        for _ in range(60 * 10):
            pc.update(DT)
            enc.update(DT, player, pc)
            pc.hp = max(pc.hp, 5)
        self.assertLess(pc.hp, hp)                            # through pc.hurt
        count = len(enc.enemies)
        for e in enc.enemies:
            e.monster.kill()
        enc.update(DT, player, pc)
        self.assertEqual(enc.state[room], "cleared")
        self.assertEqual(len(enc.killed), count)
        self.assertEqual(len(enc.hosts), 1)                   # still falling apart...
        for _ in range(60 * 3):
            enc.update(DT, player, pc)
        self.assertEqual(enc.hosts, [])                       # ...and gone

    def test_raised_dead_give_no_reward(self):
        host = SkeletonHost(0, 0, 800, 600, "dungeon")
        acolyte = host.add("skeleton_acolyte", 300, 300, spawn=False)
        acolyte.monster.spawn_requests.append(spawn_monster("skeleton_warrior", 200, 200))
        host.step(DT)
        raised = host.new_members()
        self.assertEqual(len(raised), 1)
        self.assertTrue(raised[0].no_reward)

    def test_retry_clears_the_skeletons(self):
        enc, _room, _p = start_room("3-1", "combat")
        enc.retry_room()
        self.assertEqual((enc.enemies, enc.hosts), ([], []))


class LichRaid(unittest.TestCase):
    def setUp(self):
        self._path = save_state.SAVE_PATH
        save_state.SAVE_PATH = Path(tempfile.mkdtemp()) / "savegame.json"
        self.g = dungeon_map.Game(tester=True)
        self.g.tester.start("warrior")
        self.g.tester.god = False
        self.g.tester.update(0)
        self.night = self.g.night

    def tearDown(self):
        save_state.SAVE_PATH = self._path

    def step(self, seconds, keep_hero=True, keep_ward=False):
        for _ in range(int(seconds * 60)):
            self.g.pc.update(DT)
            if keep_hero:
                self.g.pc.hp = self.g.pc.max_hp
            if keep_ward:
                self.night.ward = night_raid.WARD_MAX
            self.night.update(DT, False)

    def test_skeletons_march_down_the_road_and_claw_the_ward(self):
        self.g.tester.lich_raid()
        self.assertTrue(self.night.active)
        p = self.g.surface.player
        p.x, p.y = 300, 2800                                       # far away
        self.step(3)
        self.assertTrue(self.night.monsters)
        raider = self.night.monsters[0]
        self.assertEqual(type(raider).__name__, "SkeletonRaider")
        y0 = raider.y
        self.step(4)
        self.assertGreater(raider.y, y0 + 50)                      # marching south, toward Oakwood
        self.step(60)
        self.assertLess(self.night.ward, night_raid.WARD_MAX)       # they reached the ward

    def test_they_fight_the_hero_who_comes_close(self):
        self.g.tester.lich_raid()
        p = self.g.surface.player
        p.x, p.y = night_raid.PATHS["lich"][3]
        hp = self.g.pc.hp
        for _ in range(60 * 25):
            self.g.pc.update(DT)
            self.night.update(DT, False)
            self.g.pc.hp = max(self.g.pc.hp, 5)
        self.assertLess(self.g.pc.hp, hp)

    def test_the_last_wave_brings_the_barrow_warden(self):
        self.g.tester.lich_raid()
        self.night.waves_left, self.night.pending_warden = 0, True
        self.g.surface.player.x, self.g.surface.player.y = 300, 2800
        self.step(12, keep_ward=True)
        names = {m.name for m in self.night.monsters}
        self.assertIn("Barrow Warden", names)
        warden = next(m for m in self.night.monsters if m.name == "Barrow Warden")
        self.assertEqual((warden.kind, warden.monster.size, warden.monster.variant), ("elite", WARDEN_SIZE, "cursed"))

    def test_other_raids_are_unchanged(self):
        self.night.source = "goblin"
        self.night._make_host()
        self.assertIsNone(self.night.host)
        self.assertIsInstance(self.night._spawn_raider(night_raid.PATHS["goblin"]), night_raid.RaidMonster)


if __name__ == "__main__":
    unittest.main()
