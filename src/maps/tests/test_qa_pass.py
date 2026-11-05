"""
The QA pass (2026-11-06): balance targets from the live config, the bugs it fixed, and the paths the
built .exe uses. Run from the repo root:  python -m unittest discover -s src/maps/tests
"""
import importlib
import math
import os
import random
import subprocess
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

from src.maps import combat, dungeon_map, save_state, story, wilds   # noqa: E402
import app_paths   # noqa: E402  (combat put src/ on the path)

DT = 1 / 60


class BalanceTargets(unittest.TestCase):
    """tools/balance_report.py --check runs on the shipped config (a fresh process: it reads the files)."""

    def test_the_shipped_config_meets_the_targets(self):
        env = dict(os.environ, PYGAME_HIDE_SUPPORT_PROMPT="1")
        env.pop("REALMQUEST_BALANCE", None)
        out = subprocess.run([sys.executable, os.path.join(REPO, "tools", "balance_report.py"), "--check"],
                             capture_output=True, text=True, env=env, timeout=300)
        self.assertEqual(out.returncode, 0, out.stdout[-2500:] + out.stderr[-1500:])
        self.assertNotIn("OUT OF TARGET", out.stdout)

    def test_level_ranges(self):
        self.assertEqual(save_state.MAIN_MIN_LEVEL, {"goblin": 5, "berserker": 15, "lich": 20})
        self.assertGreaterEqual(save_state.MAX_LEVEL, 30)
        self.assertEqual(len(save_state.LEVEL_XP), save_state.MAX_LEVEL)
        steps = [b - a for a, b in zip(save_state.LEVEL_XP, save_state.LEVEL_XP[1:])]
        self.assertTrue(all(b >= a for a, b in zip(steps, steps[1:])), "each level costs at least as much")

    def test_energy_is_per_hit_not_per_damage(self):
        g = types.SimpleNamespace()
        pc = combat.PlayerCombat("warrior")
        pc.pools.bars["energy"][0] = 0.0
        game = types.SimpleNamespace(pc=pc, target_hp=lambda: 0)
        dungeon_map.Game.energy_from_hits(game, 500)            # one swing that took 500 HP off
        self.assertEqual(pc.pools.get("energy"), pc.energy_on_hit)
        self.assertLess(pc.energy_on_hit, 25, "a skill needs more than one hit")

    def test_potions_scale_with_max_health(self):
        pc = combat.PlayerCombat("warrior")
        pc.max_hp, pc.hp, pc.potions = 400, 100, 1
        pc.drink()
        self.assertEqual(pc.hp, 100 + combat.POTION_HEAL + round(400 * combat.POTION_HEAL_PERCENT / 100))


class Fixes(unittest.TestCase):
    def test_a_tier_typo_does_not_crash(self):
        from monsters import in_game
        old = dict(in_game.RULES["dungeon"])
        try:
            in_game.RULES["dungeon"]["tier"] = "elit"                     # a typo in skeleton_army.toml
            host = in_game.SkeletonHost(0, 0, 400, 400, "dungeon")
            e = host.add("skeleton_warrior", 200, 200)
            self.assertGreater(e.max_hp, 0)
        finally:
            in_game.RULES["dungeon"].update(old)

    def test_reload_keeps_warden_and_brute_health(self):
        from monsters import in_game
        host = in_game.SkeletonHost(0, 0, 600, 600, "dungeon")
        warden = in_game.make_warden(host, 300, 300, "Bone Warden")
        brute = host.add("skeleton_brute", 200, 200)
        before = (warden.monster.max_hp, brute.monster.max_hp)
        host.refresh_config()
        self.assertEqual((warden.monster.max_hp, brute.monster.max_hp), before)

    def test_wild_skeletons_do_not_flicker_at_the_leash(self):
        Wild = wilds._wild_skeleton_class()
        from monsters import in_game
        host = in_game.SkeletonHost(0, 0, 1000, 1000, "dungeon",
                                    ground=types.SimpleNamespace(can_stand=lambda x, y: True))
        home = (500, 500)
        sk = host.add("skeleton_warrior", 500 + wilds.SKELETON_LEASH - 30, 500, proxy=Wild, home=home)
        player = types.SimpleNamespace(x=sk.x + 100, y=sk.y)
        pc = combat.PlayerCombat("warrior")
        sk.aggro = False
        sk.step(DT, player, host.ground, pc, None)
        self.assertFalse(sk.aggro, "inside the leash margin: it stays calm")

    def test_calm_drops_a_wind_up(self):
        from monsters import in_game
        host = in_game.SkeletonHost(0, 0, 600, 600, "dungeon")
        e = host.add("skeleton_warrior", 300, 300)
        m = e.monster
        m.set_state("windup")
        wilds.calm_down(m)
        self.assertEqual(m.state, m.START_STATE)

    def test_raid_shamans_throw_fireballs(self):
        from src.maps import night_raid
        rng = random.Random(1)
        m = None
        while m is None or not m.ranged:
            m = night_raid.RaidMonster("goblin", night_raid.PATHS["goblin"], rng)
        night = types.SimpleNamespace(bolts=[], hit_ward=lambda *a: None)
        player = types.SimpleNamespace(x=m.x + 150, y=m.y)
        pc = combat.PlayerCombat("warrior")
        ground = types.SimpleNamespace(can_stand=lambda x, y: True)
        for _ in range(60):
            m.step(DT, player, ground, pc, night)
        self.assertTrue(night.bolts)

    def test_wild_warlord_cannot_be_stunned(self):
        m = wilds.make_wild("orc_warlord", 0, 0, (0, 0), 50, random.Random(1),
                            types.SimpleNamespace(bolts=[], hazards=[]))
        self.assertTrue(m.cc_immune)
        self.assertEqual(m.kind, "elite")

    def test_great_slime_keeps_its_size_on_reload(self):
        w = types.SimpleNamespace(bolts=[], hazards=[])
        m = wilds.make_wild("slime", 0, 0, (0, 0), 50, random.Random(1), w)
        m.cfg_radius_k = 20 / m.radius
        m.radius = 20
        m.refresh_config()
        self.assertAlmostEqual(m.radius, 20)


class GameFixes(unittest.TestCase):
    def setUp(self):
        self._path = save_state.SAVE_PATH
        save_state.SAVE_PATH = Path(tempfile.mkdtemp()) / "savegame.json"
        self._load = dungeon_map.Settings.load
        dungeon_map.Settings.load = classmethod(lambda cls, path=None: cls())
        self.g = dungeon_map.Game()
        self.g.begin_game(True, "Robin", "warrior")
        self.g.dialog = None
        self.g.fade, self.g.fade_dir = 0.0, 0

    def tearDown(self):
        save_state.SAVE_PATH = self._path
        dungeon_map.Settings.load = self._load
        story.set_hero_name("Himmel")

    def key(self, k):
        return self.g.handle_event(pygame.event.Event(pygame.KEYDOWN, key=k, mod=0, unicode=""))

    def test_no_talking_while_dead_in_the_vale(self):
        g = self.g
        called = []
        g.surface.interact = lambda: called.append(1)
        g.pc.hp, g.pc.dead = 0, True
        self.key(pygame.K_e)
        self.assertEqual(called, [])

    def test_r_does_nothing_during_a_fade(self):
        g = self.g
        g.is_dungeon_unlocked = lambda d: True
        g.change_floor("1-1")
        g.pc.hp, g.pc.dead = 0, True
        g.fade, g.fade_dir = 0.5, 1
        self.key(pygame.K_r)
        self.assertTrue(g.pc.dead, "no respawn mid-fade")

    def test_reload_keeps_bars_and_cooldowns(self):
        g = self.g
        pc = g.pc
        pc.pools.bars["stamina"][0] = pc.pools.bars["stamina"][1] * 0.25
        slot = next(iter(pc.caster.cd))
        pc.caster.cd[slot] = 7.5
        g.on_config_reloaded(["hero.toml"])
        self.assertAlmostEqual(pc.pools.get("stamina") / pc.pools.max("stamina"), 0.25, places=3)
        self.assertEqual(pc.caster.cd[slot], 7.5)

    def test_rewards_are_not_kills(self):
        g = self.g
        played = []
        g.sfx = types.SimpleNamespace(play=lambda name, *a, **k: played.append(name))
        g.village_xp(15, 100, 100, "reward")
        self.assertNotIn("enemy_die", played)
        g.village_xp(5, 100, 100)
        self.assertIn("enemy_die", played)

    def test_boss_intro_plays_once(self):
        g = self.g
        g.is_dungeon_unlocked = lambda d: True
        g.change_floor("1-3")
        enc, d = g.enc, g.dungeon
        room = enc.boss_room
        rect = d.rooms[room]
        here = types.SimpleNamespace(x=rect.centerx * combat.TILE, y=rect.centery * combat.TILE)
        enc._start_room(room, here)
        self.assertEqual(enc.dialog_request, enc.boss_kind)
        enc.dialog_request = None
        enc.retry_room()
        enc._start_room(room, here)
        self.assertIsNone(enc.dialog_request)

    def test_q_only_leaves_from_a_lit_checkpoint(self):
        g = self.g
        g.is_dungeon_unlocked = lambda d: True
        g.change_floor("1-2")
        self.key(pygame.K_q)                                   # mid-floor: nothing happens
        self.assertEqual(g.fade_dir, 0)
        self.assertEqual(g.mode, "dungeon")
        cp = g.interact.checkpoints[0]
        g.interact.light_checkpoint(cp, quiet=True)
        g.player.place(cp["x"], cp["y"] + 20)
        self.assertIn("Leave the dungeon", g.interact.prompt(g.player))
        self.key(pygame.K_q)
        self.assertEqual(g.pending, ("__surface__", 1), "heads back to Oakwood")

    def test_no_keybind_bar_in_the_vale(self):
        import inspect
        from src.maps import surface_world
        self.assertNotIn("WASD: move", inspect.getsource(surface_world.SurfaceWorld))

    def test_a_failed_save_is_reported(self):
        g = self.g
        g.save.save = lambda path=None: False
        g.autosave()
        self.assertTrue(any("Could not save" in t[0] for t in g.surface.toasts))


class Paths(unittest.TestCase):
    def test_development_paths(self):
        self.assertFalse(app_paths.frozen())
        self.assertEqual(app_paths.game_dir(), Path(REPO))
        self.assertEqual(app_paths.user_dir(), Path(REPO))

    def test_built_game_paths(self):
        tmp = Path(tempfile.mkdtemp())
        old = (getattr(sys, "frozen", None), sys.executable, os.environ.get("APPDATA"))
        try:
            sys.frozen = True
            sys.executable = str(tmp / "RealmQuest" / "RealmQuest.exe")
            os.environ["APPDATA"] = str(tmp / "appdata")
            self.assertEqual(app_paths.game_dir(), tmp / "RealmQuest")
            self.assertEqual(app_paths.user_dir(), tmp / "appdata" / "RealmQuest")
            self.assertTrue(app_paths.user_dir().is_dir())
        finally:
            if old[0] is None:
                del sys.frozen
            else:
                sys.frozen = old[0]
            sys.executable = old[1]
            if old[2] is None:
                os.environ.pop("APPDATA", None)
            else:
                os.environ["APPDATA"] = old[2]


if __name__ == "__main__":
    unittest.main()
