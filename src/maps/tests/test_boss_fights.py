"""
Checks that the Minotaur and the Lich King are really in the dungeons: the boss rooms hold them, hits and
damage are converted to the game's scale, the Lich King's skeletons can be hit, the hero's root / slow work,
and their music hands over from the map music.
Run from the repo root:  python -m unittest discover -s src/maps/tests
"""
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

from src.maps import combat            # noqa: E402
from src.maps.combat import TILE       # noqa: E402
# combat.py put src/ on the path: the game (and the bosses) import these as top-level packages, so the test must too
from bosses import in_game             # noqa: E402
from bosses.minotaur import boss as mb  # noqa: E402
import audio                           # noqa: E402
from audio.testing import Recorder     # noqa: E402

DT = 1 / 60
ROOM = pygame.Rect(10, 8, 46, 29)      # tiles


def boss_floor(floor_name):
    d = types.SimpleNamespace(can_stand=lambda x, y: True, lock_rect=None, floor_name=floor_name,
                              rooms=[ROOM], tiles=[combat.FLOOR] * (combat.MAP_W * combat.MAP_H))
    return d


def hero_at(x, y):
    return types.SimpleNamespace(x=x, y=y, dash_t=0.0, afflicted=[],
                                 afflict=lambda name, secs: hero_at.log.append((name, secs)))


hero_at.log = []


class BossRooms(unittest.TestCase):
    def room_boss(self, floor_name):
        enc = combat.Encounters(boss_floor(floor_name))
        player = hero_at(ROOM.centerx * TILE, ROOM.bottom * TILE - 80)
        enc._start_room(0, player)
        self.assertEqual(len(enc.enemies), 1)
        return enc, player

    def test_the_minotaur_holds_dungeon_two(self):
        enc, _ = self.room_boss("2-3")
        boss = enc.enemies[0]
        self.assertIsInstance(boss, in_game.BossEnemy)
        self.assertEqual((boss.kind, boss.key, enc.dialog_request), ("boss", "minotaur", "minotaur"))

    def test_the_lich_king_holds_dungeon_three(self):
        enc, _ = self.room_boss("3-3")
        boss = enc.enemies[0]
        self.assertEqual((boss.kind, boss.key, enc.dialog_request), ("boss", "lich_king", "lich"))
        self.assertTrue(boss.audio_music)

    def test_dialog_portraits_are_the_real_art(self):
        for kind in ("minotaur", "lich"):
            self.assertGreater(combat.sprite(kind).get_height(), 100, kind)

    def test_hp_and_damage_are_converted_to_the_games_scale(self):
        enc, _ = self.room_boss("2-3")
        boss = enc.enemies[0]
        power = in_game.IN_GAME["minotaur"]["hp_power"]
        self.assertEqual(boss.boss.max_hp, mb.BOSS_MAX_HP)               # config/bosses/minotaur.toml, as typed
        self.assertEqual(boss.max_hp, mb.BOSS_MAX_HP / power)            # the bar (power 1 = the file's number)
        boss.boss.set_state("idle")
        before = boss.hp
        boss.take_damage(2)                                  # the hero's sword
        self.assertEqual(before - boss.hp, 2)               # shown HP drops by exactly what was dealt
        self.assertEqual(boss.boss.max_hp - boss.boss.hp, 2 * power)

    def test_boss_hits_go_through_the_heros_defence_and_i_frames(self):
        enc, player = self.room_boss("2-3")
        boss, pc = enc.enemies[0], combat.PlayerCombat("warrior")
        boss.hero.refresh(player, pc, enc.d)
        hp = pc.hp
        self.assertGreater(boss.hero.take_damage(20), 0)
        self.assertLess(pc.hp, hp)
        hp = pc.hp
        self.assertEqual(boss.hero.take_damage(20), 0)       # hurt a moment ago: i-frames
        self.assertEqual(pc.hp, hp)
        pc.iframes, pc.dash_inv = 0.0, 0.5                   # dashing: immune to the status too
        self.assertFalse(boss.hero.apply_status("root", 1.0))

    def test_root_and_slow_reach_the_hero(self):
        enc, player = self.room_boss("3-3")
        boss, pc = enc.enemies[0], combat.PlayerCombat("warrior")
        hero_at.log.clear()
        boss.hero.refresh(player, pc, enc.d)
        self.assertTrue(boss.hero.apply_status("root", 1.3))
        self.assertEqual(hero_at.log, [("root", 1.3)])

    def test_a_dying_boss_hurts_nobody(self):
        enc, player = self.room_boss("3-3")
        boss, pc = enc.enemies[0], combat.PlayerCombat("warrior")
        boss.boss.hp = 0
        boss.hero.refresh(player, pc, enc.d)
        self.assertEqual(boss.hero.take_damage(30), 0)

    def test_the_fight_plays_and_draws_in_the_room(self):
        enc, player = self.room_boss("2-3")
        pc = combat.PlayerCombat("warrior")
        screen = pygame.Surface((1152, 648))
        for _ in range(600):
            pc.update(DT)
            enc.update(DT, player, pc)
            enc.draw(screen, ROOM.x * TILE - 60, ROOM.y * TILE - 40, 0.0, player, pc)
        self.assertNotEqual(enc.enemies[0].state, "intro")           # the intro is over: the fight is on
        self.assertTrue(enc.enemies[0].boss.is_alive())

    def test_the_lich_kings_skeletons_can_be_hit_and_give_no_reward(self):
        enc, player = self.room_boss("3-3")
        boss, pc = enc.enemies[0], combat.PlayerCombat("warrior")
        for _ in range(60 * 8):                              # his intro, then his first attacks
            enc.update(DT, player, pc)
            pc.iframes, pc.hp, pc.dead = 0.0, pc.max_hp, False        # (a dead hero would freeze the boss)
        boss.boss.debug_set_hp_percent(0.45)                # phase 2: he calls his army
        for _ in range(60 * 30):
            enc.update(DT, player, pc)
            pc.iframes, pc.hp, pc.dead = 0.0, pc.max_hp, False        # (a dead hero would freeze the boss)
            if any(isinstance(e, in_game.MinionEnemy) for e in enc.enemies):
                break
        minions = [e for e in enc.enemies if isinstance(e, in_game.MinionEnemy)]
        self.assertTrue(minions, "the Lich King never called his skeletons")
        m = minions[0]
        for _ in range(60 * 3):                              # let it finish rising from the floor
            enc.update(DT, player, pc)
            pc.iframes, pc.hp, pc.dead = 0.0, pc.max_hp, False        # (a dead hero would freeze the boss)
        before = m.hp
        m.take_damage(2)
        self.assertLess(m.hp, before)
        m.minion.hp = 0
        enc.update(DT, player, pc)
        self.assertNotIn(m, enc.enemies)
        self.assertEqual([k for k in enc.killed if k[3] == "minion"], [])

    def test_resetting_the_room_stops_the_bosses_music(self):
        rec = Recorder()
        audio.set_manager(rec)
        try:
            enc, _ = self.room_boss("3-3")
            enc.active = 0
            enc.retry_room()
            self.assertTrue(("stop_music",) in rec.events, rec.events)
        finally:
            audio.set_manager(None)


class HeroStatus(unittest.TestCase):
    def setUp(self):
        from src.maps import dungeon_map
        self.dm = dungeon_map
        self.d = types.SimpleNamespace(spawn=(300.0, 300.0), can_stand=lambda x, y: True)
        self.hero = dungeon_map.Player(self.d)

    def test_rooted_hero_cannot_walk_or_dash(self):
        self.hero.afflict("root", 1.0)
        self.hero.dash_t = 0.2
        self.hero.move(1.0, 0.0, self.d, DT)
        self.assertEqual((self.hero.x, self.hero.dash_t), (300.0, 0.0))
        for _ in range(70):
            self.hero.move(1.0, 0.0, self.d, DT)
        self.assertGreater(self.hero.x, 300.0)               # the roots wore off

    def test_slow_halves_the_speed(self):
        normal = self.dm.Player(self.d)
        normal.move(1.0, 0.0, self.d, 0.1)
        self.hero.afflict("slow", 1.0)
        self.hero.move(1.0, 0.0, self.d, 0.1)
        self.assertAlmostEqual((self.hero.x - 300.0) * 2, normal.x - 300.0, places=3)


class MixerChannels(unittest.TestCase):
    def test_the_dungeon_ambience_has_a_channel_the_audio_package_leaves_alone(self):
        from audio import manager
        self.assertGreaterEqual(manager.RESERVED, manager.AMBIENCE_CHANNEL + 1)
        self.assertGreaterEqual(manager.AMBIENCE_CHANNEL, 4)           # 0-3 are its music and loops


if __name__ == "__main__":
    unittest.main()
