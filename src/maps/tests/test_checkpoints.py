"""
Checkpoints: three on every dungeon floor (one next to the boss / mini-boss room), lit by walking
past them, and the hero rises at the nearest lit one after a fall - or back in Oakwood.
Run from the repo root:  python -m unittest discover -s src/maps/tests
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

from src.maps import dungeon_gen, dungeon_map, room_features, save_state, story   # noqa: E402

TILE = dungeon_map.TILE


def build(floor, seed):
    d = dungeon_map.Dungeon(floor, seed)
    inter = room_features.Interactables(d, save_state.SaveState())
    return d, inter


class Placement(unittest.TestCase):
    def test_every_floor_has_three_reachable_checkpoints(self):
        for floor in sorted(dungeon_gen.VALID_FLOORS):
            for seed in (1, 77, 4242):
                with self.subTest(floor=floor, seed=seed):
                    d, inter = build(floor, seed)
                    cps = inter.checkpoints
                    self.assertEqual(len(cps), room_features.CHECKPOINTS_PER_FLOOR)
                    self.assertEqual(len({(c["tx"], c["ty"]) for c in cps}), len(cps), "three different spots")
                    for c in cps:
                        r = d.rooms[c["room"]]
                        self.assertTrue(r.collidepoint(c["tx"], c["ty"]), "inside its room")
                        # the hero can walk up to it (a free tile next to it is reachable)
                        near = [(c["tx"] + ox, c["ty"] + oy) for ox, oy in ((0, 1), (1, 0), (-1, 0), (0, -1))]
                        self.assertTrue(any(p in inter.reach for p in near), "reachable")

    def test_one_checkpoint_waits_by_the_boss_or_mini_boss_room(self):
        for floor in sorted(dungeon_gen.VALID_FLOORS):
            with self.subTest(floor=floor):
                d, inter = build(floor, 9)
                roles = room_features.room_roles(d)
                threat = next((k for role in room_features.THREAT_ROLES for k in range(len(roles))
                               if roles[k] == role), len(roles) - 1)
                boss_side = [c for c in inter.checkpoints if c["boss_side"]]
                self.assertEqual(len(boss_side), 1)
                self.assertEqual(boss_side[0]["room"], d.parent[threat],
                                 "in the room right before the %s room" % roles[threat])

    def test_boss_floors_put_it_before_the_boss(self):
        d, inter = build("1-3", 5)
        roles = room_features.room_roles(d)
        cp = next(c for c in inter.checkpoints if c["boss_side"])
        self.assertEqual(roles[d.parent[roles.index("boss")]], roles[cp["room"]])


class Lighting(unittest.TestCase):
    def setUp(self):
        self.d, self.inter = build("1-1", 3)
        self.pc = types.SimpleNamespace(dead=False)

    def at(self, c):
        return types.SimpleNamespace(x=c["x"], y=c["y"] + 20)

    def test_walking_past_lights_it(self):
        c = self.inter.checkpoints[0]
        enc = types.SimpleNamespace(state=[], locked=False)
        self.inter.update(0.1, types.SimpleNamespace(x=0, y=0), self.pc, enc)
        self.assertFalse(c["lit"], "too far away")
        self.inter.update(0.1, self.at(c), self.pc, enc)
        self.assertTrue(c["lit"])
        self.assertTrue(any(e[0] == "toast" for e in self.inter.events))

    def test_not_in_the_middle_of_a_locked_fight(self):
        c = self.inter.checkpoints[0]
        self.inter.update(0.1, self.at(c), self.pc, types.SimpleNamespace(state=[], locked=True))
        self.assertFalse(c["lit"])

    def test_resting_heals_and_saves(self):
        c = self.inter.checkpoints[0]
        self.inter.light_checkpoint(c, quiet=True)
        self.assertEqual(self.inter.prompt(self.at(c)), "[E]  Rest      [Q]  Leave the dungeon")
        self.assertTrue(self.inter.use(self.at(c)))
        kinds = [e[0] for e in self.inter.events]
        self.assertIn("rest", kinds)
        self.assertIn("save", kinds)


class Respawn(unittest.TestCase):
    def setUp(self):
        self._path = save_state.SAVE_PATH
        save_state.SAVE_PATH = Path(tempfile.mkdtemp()) / "savegame.json"
        self._load = dungeon_map.Settings.load
        dungeon_map.Settings.load = classmethod(lambda cls, path=None: cls())
        self.g = dungeon_map.Game()
        self.g.begin_game(True, "Robin", "warrior")
        self.g.dialog = None
        self.g.change_floor("1-2")
        self.g.fade, self.g.fade_dir = 0.0, 0

    def tearDown(self):
        save_state.SAVE_PATH = self._path
        dungeon_map.Settings.load = self._load
        story.set_hero_name("Himmel")

    def fall(self, x, y):
        g = self.g
        g.player.place(x, y)
        g.pc.hp, g.pc.dead = 0, True

    def test_rises_at_the_nearest_lit_checkpoint(self):
        g = self.g
        a, b = g.interact.checkpoints[0], g.interact.checkpoints[1]
        g.interact.light_checkpoint(a, quiet=True)
        g.interact.light_checkpoint(b, quiet=True)
        self.fall(b["x"] + 30, b["y"] + 30)            # died right next to b
        g.respawn_after_death()
        self.assertFalse(g.pc.dead)
        self.assertEqual(g.mode, "dungeon")
        self.assertEqual(g.floor_name, "1-2")
        self.assertLess(abs(g.player.x - b["x"]) + abs(g.player.y - b["y"]), 4 * TILE)
        self.assertTrue(g.dungeon.can_stand(g.player.x, g.player.y))

    def test_no_lit_checkpoint_means_oakwood(self):
        g = self.g
        self.fall(*g.dungeon.spawn)
        g.respawn_after_death()
        self.assertFalse(g.pc.dead)
        self.assertEqual(g.mode, "village")
        self.assertTrue(any("Merlin carried you home" in t[0] for t in g.surface.toasts))

    def test_rises_by_itself_after_a_moment(self):
        g = self.g
        g.interact.light_checkpoint(g.interact.checkpoints[0], quiet=True)
        self.fall(*g.dungeon.spawn)
        g.death_tick(1.0)
        self.assertTrue(g.pc.dead, "lies there a moment first")
        g.death_tick(dungeon_map.RESPAWN_DELAY)
        self.assertFalse(g.pc.dead)

    def test_death_card_draws(self):
        g = self.g
        self.fall(*g.dungeon.spawn)
        g.death_t = 1.0
        g.draw_death_card(g.screen)                    # no errors, with and without a lit checkpoint
        g.interact.light_checkpoint(g.interact.checkpoints[0], quiet=True)
        g.draw_death_card(g.screen)


if __name__ == "__main__":
    unittest.main()
