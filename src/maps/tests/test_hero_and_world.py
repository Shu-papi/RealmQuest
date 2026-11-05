"""
Checks the hero (name, class, bars, dash, skills), where the new monsters appear, the
Goblin King boss in the dungeon, the music for each place, and the menu -> world flow.
Run from the repo root:  python -m unittest discover -s src/maps/tests
"""
import json
import math
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

from src.maps import combat, music, night_raid, save_state, story, wilds   # noqa: E402
from src.maps import dungeon_map                                            # noqa: E402

DT = 1 / 60


def fresh_save_path():
    return Path(tempfile.mkdtemp()) / "savegame.json"


class HeroSave(unittest.TestCase):
    def test_name_and_class_round_trip(self):
        path = fresh_save_path()
        s = save_state.SaveState()
        s.reset("Aria", "mage")
        s.gold = 12
        self.assertTrue(s.save(path))
        loaded = save_state.SaveState.load(path)
        self.assertEqual((loaded.hero_name, loaded.hero_class, loaded.gold), ("Aria", "mage", 12))

    def test_old_saves_load_as_himmel_the_warrior(self):
        path = fresh_save_path()
        path.write_text(json.dumps({"version": 1, "gold": 5, "xp": 0}), encoding="utf-8")
        s = save_state.SaveState.load(path)
        self.assertEqual((s.hero_name, s.hero_class, s.gold), ("Himmel", "warrior", 5))

    def test_names_are_cleaned(self):
        self.assertEqual(save_state.clean_name("  Sir   <Lancelot>!!  of the Lake "), "Sir Lancelot o")
        self.assertEqual(save_state.clean_name("O'Neil-Ray"), "O'Neil-Ray")
        s = save_state.SaveState()
        s.reset("", "ninja")
        self.assertEqual((s.hero_name, s.hero_class), ("Himmel", "warrior"))

    def test_class_sets_base_hp(self):
        s = save_state.SaveState()
        for cls, hp in (("warrior", 48), ("mage", 34), ("archer", 40)):
            s.reset("X", cls)
            self.assertEqual(s.max_hp, hp)


class StoryName(unittest.TestCase):
    def tearDown(self):
        story.set_hero_name("Himmel")

    def test_dialog_uses_the_chosen_name(self):
        story.set_hero_name("Aria")
        d = story.Dialog(story.INTRO_LINES, {})
        texts = " ".join(t for _w, t in d.lines)
        self.assertNotIn("Himmel", texts)
        self.assertIn("Now go, Aria.", texts)

    def test_whole_words_only_and_no_double_swap(self):
        story.set_hero_name("Himmel Jr")
        once = story.named("Go, Himmel!")
        self.assertEqual(story.named(once), "Go, Himmel Jr!")
        story.set_hero_name("Bo")
        self.assertEqual(story.named("Himmelfarb and Himmel"), "Himmelfarb and Bo")


class HeroCombat(unittest.TestCase):
    def test_apply_class_sets_bars_and_attack(self):
        pc = combat.PlayerCombat("mage")
        self.assertEqual(pc.pools.order, ["mana", "stamina"])
        pc.apply_class("warrior")
        self.assertEqual(pc.pools.order, ["stamina", "energy"])
        self.assertEqual(pc.sword_dmg, combat.SWORD_DMG + 1)
        pc.apply_class("archer")
        self.assertLess(pc.swing_cd, combat.SWORD_COOLDOWN)

    def test_dash_costs_stamina_and_stops_when_empty(self):
        pc = combat.PlayerCombat("mage")
        hero = types.SimpleNamespace(x=0, y=0, face=(1.0, 0.0), dash_t=0.0, dash_dir=(0, 1))
        dashes = 0
        for _ in range(10):
            hero.dash_t, pc.dash_cd = 0.0, 0.0
            if pc.try_dash(hero, 1, 0):
                dashes += 1
        self.assertEqual(dashes, int(pc.pools.max("stamina") // 25))
        pc.update(2.0)
        hero.dash_t, pc.dash_cd = 0.0, 0.0
        self.assertTrue(pc.try_dash(hero, 1, 0), "stamina comes back")


def floor_dungeon(name):
    return dungeon_map.Dungeon(name, seed=7)


class MinionPlacement(unittest.TestCase):
    """Goblin sprites only in the Goblin Dungeon family; Berserker / Lich floors untouched."""

    def start(self, floor, role):
        d = floor_dungeon(floor)
        enc = combat.Encounters(d)
        room = next(i for i, r in enumerate(d.room_roles) if r == role)
        rect = d.rooms[room]
        enc._start_room(room, types.SimpleNamespace(x=rect.centerx * combat.TILE, y=rect.centery * combat.TILE))
        return enc

    def test_goblin_floors_wear_goblin_sprites(self):
        enc = self.start("1-1", "guard")
        skins = {e.skin for e in enc.enemies}
        self.assertEqual(skins, {"goblin_shaman", "giant_boar"})
        enc = self.start("1-2", "miniboss")
        self.assertEqual(enc.miniboss.skin, "goblin_general")

    def test_goblin_caves_too(self):
        enc = self.start("11-1", "lair")
        self.assertIn("goblin_general", {e.skin for e in enc.enemies})

    def test_berserker_and_lich_floors_have_none(self):
        for floor, role in (("2-1", "guard"), ("3-2", "miniboss"), ("13-1", "lair"), ("15-1", "lair")):
            with self.subTest(floor=floor):
                enc = self.start(floor, role)
                self.assertTrue(all(e.skin is None for e in enc.enemies))

    def test_goblin_king_is_the_sprite_boss(self):
        from bosses.goblin_king.in_game import GoblinKingEnemy
        enc = self.start("1-3", "boss")
        self.assertIsInstance(enc.enemies[0], GoblinKingEnemy)
        enc2 = self.start("2-3", "boss")
        self.assertNotIsInstance(enc2.enemies[0], GoblinKingEnemy)

    def test_shamans_throw_fireballs(self):
        enc = self.start("1-1", "guard")
        d = enc.d
        rect = d.rooms[enc.active]
        player = types.SimpleNamespace(x=rect.centerx * combat.TILE, y=(rect.centery + 2) * combat.TILE,
                                       dash_t=0.0)
        pc = combat.PlayerCombat("warrior")
        flying = 0
        for _ in range(240):
            enc.update(DT, player, pc)
            pc.hp = pc.max_hp
            flying = max(flying, len(enc.bolts))
        self.assertGreater(flying, 0)


class OverworldMonsters(unittest.TestCase):
    def test_slime_and_boar_packs_wear_sprites(self):
        import random
        rng = random.Random(1)
        for kind, allowed in (("slime", {"slime_red", "slime_blue", "slime_green"}), ("boar", {"wild_boar"})):
            m = wilds.Mob(kind, 0, 0, (0, 0), 50, rng)
            self.assertIn(m.skin, allowed)
        for kind in ("goblin", "bandit", "stalker", "wraith"):
            self.assertIsNone(wilds.Mob(kind, 0, 0, (0, 0), 50, rng).skin, kind)

    def test_no_wolves_left(self):
        self.assertNotIn("wolf", wilds.MOBS)
        self.assertTrue(all(k != "wolf" for k, *_ in wilds.PACKS))

    def test_goblin_raiders_wear_goblin_sprites(self):
        import random
        rng = random.Random(3)
        skins = {night_raid.RaidMonster("goblin", night_raid.PATHS["goblin"], rng).skin for _ in range(20)}
        self.assertEqual(skins, {"goblin_shaman", "giant_boar"})
        self.assertIsNone(night_raid.RaidMonster("berserker", night_raid.PATHS["berserker"], rng).skin)

    def test_stun_stops_and_slow_slows(self):
        e = combat.Enemy(0, 0, "x", 10, 100, 1, (0, 0, 0))
        d = types.SimpleNamespace(can_stand=lambda x, y: True)
        player = types.SimpleNamespace(x=500, y=0)
        pc = combat.PlayerCombat()
        e.stun_t = 0.5
        e.update(DT, player, d, pc)
        self.assertEqual(e.x, 0)
        e.stun_t, e.slow_t = 0.0, 1.0
        e.update(0.1, player, d, pc)
        self.assertAlmostEqual(e.x, 100 * combat.SLOW_K * 0.1, places=3)


class GoblinKingInGame(unittest.TestCase):
    def test_fights_through_pc_hurt_and_dies(self):
        from bosses.goblin_king.in_game import GoblinKingEnemy
        d = types.SimpleNamespace(can_stand=lambda x, y: True)
        boss = GoblinKingEnemy(400, 300)
        self.assertAlmostEqual(boss.y, 300)
        player = types.SimpleNamespace(x=430, y=300, dash_t=0.0)
        pc = combat.PlayerCombat("warrior")
        pc.max_hp = pc.hp = 1000
        for _ in range(int(12 / DT)):
            pc.iframes = 0.0
            boss.update(DT, player, d, pc)
        self.assertLess(pc.hp, 1000, "his attacks land on the hero")
        boss.take_damage(boss.max_hp)
        self.assertTrue(boss.dead)

    def test_dash_dodges_his_hits(self):
        from bosses.goblin_king.in_game import GoblinKingEnemy
        d = types.SimpleNamespace(can_stand=lambda x, y: True)
        boss = GoblinKingEnemy(400, 300)
        player = types.SimpleNamespace(x=430, y=300, dash_t=0.0)
        pc = combat.PlayerCombat("warrior")
        pc.max_hp = pc.hp = 1000
        for _ in range(int(12 / DT)):
            pc.dash_inv = 1.0                     # always mid-dash
            boss.update(DT, player, d, pc)
        self.assertEqual(pc.hp, 1000)

    def test_walls_hold_him(self):
        from bosses.goblin_king.in_game import GoblinKingEnemy
        d = types.SimpleNamespace(can_stand=lambda x, y: abs(x - 400) < 30)
        boss = GoblinKingEnemy(400, 300)
        player = types.SimpleNamespace(x=900, y=300, dash_t=0.0)
        for _ in range(240):
            boss.update(DT, player, d, combat.PlayerCombat())
        self.assertLess(abs(boss.x - 400), 30)


class Music(unittest.TestCase):
    def test_places(self):
        p = music.pick_place
        self.assertEqual(p(state="menu"), "menu")
        self.assertEqual(p(victory=True), "menu")
        self.assertEqual(p(mode="village", in_village=True), "village")
        self.assertEqual(p(mode="village", in_village=False), "wilds")
        self.assertEqual(p(mode="village", night=0.9), "night")
        self.assertEqual(p(mode="village", raid=True, night=0.9), "battle")
        self.assertEqual(p(mode="village", event_near=True), "battle")
        self.assertEqual(p(mode="village", shop=True), "shop")
        self.assertEqual(p(mode="dungeon", family=1), "goblin")
        self.assertEqual(p(mode="dungeon", family=2), "berserker")
        self.assertEqual(p(mode="dungeon", family=3), "lich")
        self.assertEqual(p(mode="dungeon", family=1, boss=True), "boss")

    def test_every_track_exists(self):
        for place, name in music.TRACKS.items():
            self.assertTrue((music.MUSIC_DIR / name).is_file(), f"{place}: {name}")

    def test_switching_and_missing_files_are_safe(self):
        m = music.Music(tracks={"a": "nope.mp3", "b": music.TRACKS["menu"]})
        for place in ("a", "b", "b", "a"):
            m.play(place)
            for _ in range(60):
                m.update(DT)
        self.assertEqual(m.place, "a")


class GameFlow(unittest.TestCase):
    """The real Game: home -> new game (name + class) -> world -> skills -> dungeon -> menu."""

    def setUp(self):
        self._path = save_state.SAVE_PATH
        save_state.SAVE_PATH = fresh_save_path()
        self._load = dungeon_map.Settings.load
        dungeon_map.Settings.load = classmethod(lambda cls, path=None: cls())   # not the player's own file

    def tearDown(self):
        save_state.SAVE_PATH = self._path
        dungeon_map.Settings.load = self._load
        story.set_hero_name("Himmel")

    @staticmethod
    def key(game, k, text=None):
        if text:
            game.handle_event(pygame.event.Event(pygame.TEXTINPUT, text=text))
            return
        game.handle_event(pygame.event.Event(pygame.KEYDOWN, key=k, mod=0, unicode=""))

    def test_new_game_as_archer_reaches_the_world(self):
        g = dungeon_map.Game()
        self.assertEqual(g.state, "menu")
        self.key(g, pygame.K_RETURN)                     # NEW GAME
        self.assertEqual(g.front.screen, "name")
        self.key(g, None, "Robin")
        self.key(g, pygame.K_RETURN)
        self.assertEqual(g.front.screen, "class")
        self.key(g, pygame.K_RIGHT)
        self.key(g, pygame.K_RIGHT)
        self.key(g, pygame.K_RETURN)                     # straight into the world
        self.assertEqual((g.state, g.mode), ("playing", "village"))
        self.assertEqual((g.save.hero_name, g.save.hero_class), ("Robin", "archer"))
        self.assertEqual(g.surface.player.look, "hero_archer")
        self.assertEqual(g.player.look, "hero_archer")
        self.assertIsNotNone(g.dialog)
        self.assertTrue(any("Robin" in t for _w, t in g.dialog.lines))

        g.dialog = None
        g.fade_dir, g.fade = 0, 0.0
        g.surface.state = "play"
        before = g.pc.pools.get("energy")
        self.key(g, pygame.K_k)                          # Arrow Volley in the overworld
        self.assertLess(g.pc.pools.get("energy"), before)
        stamina = g.pc.pools.get("stamina")
        self.key(g, pygame.K_LSHIFT)                     # dash in the overworld
        self.assertLess(g.pc.pools.get("stamina"), stamina)
        self.assertGreater(g.surface.player.dash_t, 0)
        for _ in range(30):
            g.update_skills(DT)
        g.render(0.5, 0, 0, DT)                          # hero panel + skill bar draw

        g.save.xp = save_state.LEVEL_XP[5]
        g.enter_from_surface("goblin")
        self.assertEqual((g.mode, g.floor_name), ("dungeon", "1-1"))
        g.fade_dir = 0
        self.key(g, pygame.K_f)                          # Rain of Arrows in a dungeon
        self.assertGreater(len(g.fx.effects), 0)
        g.render(0.5, 0, 0, DT)

        g.return_to_menu()
        self.assertEqual(g.state, "menu")
        self.assertEqual(g.front.menu.buttons[0][1], "continue")
        self.assertTrue(save_state.SAVE_PATH.is_file())


if __name__ == "__main__":
    unittest.main()
