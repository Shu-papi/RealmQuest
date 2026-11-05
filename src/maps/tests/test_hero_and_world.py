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


class BasicAttacks(unittest.TestCase):
    """Knight: sword in front only. Mage: long-range arcane bolt for mana. Elf: long-range arrow."""

    def setUp(self):
        from skills.skills import SkillFX
        self.fx = SkillFX()
        self.hero = types.SimpleNamespace(x=0.0, y=0.0, face=(1.0, 0.0), dir="right")
        self.swings = []
        self.enc = types.SimpleNamespace(player_swing=lambda *a: self.swings.append(a))

    def target(self, x):
        t = types.SimpleNamespace(x=x, y=0.0, radius=12, dead=False, hp=10)
        t.take_damage = lambda n: setattr(t, "hp", t.hp - n)
        return t

    def fly(self, targets, seconds=1.2):
        for _ in range(int(seconds / DT)):
            self.fx.update(DT, targets, self.hero)

    def test_knight_swings_without_any_projectile(self):
        pc = combat.PlayerCombat("warrior")
        self.assertTrue(pc.try_attack(self.hero, self.enc, (1, 0), self.fx))
        self.assertEqual(len(self.swings), 1)
        self.assertEqual(self.fx.effects, [])

    def test_mage_bolt_costs_mana_and_hits_far_away(self):
        pc = combat.PlayerCombat("mage")
        far = self.target(420)
        mana = pc.pools.get("mana")
        self.assertTrue(pc.try_attack(self.hero, self.enc, (1, 0), self.fx, release=0.1))
        self.assertEqual(self.swings, [], "no sword swing")
        self.assertEqual(pc.pools.get("mana"), mana - pc.basic["cost"])
        self.fly([far])
        self.assertLess(far.hp, 10)

    def test_mage_cannot_cast_bolts_without_mana(self):
        pc = combat.PlayerCombat("mage")
        pc.pools.bars["mana"][0] = 1
        self.assertFalse(pc.try_attack(self.hero, self.enc, (1, 0), self.fx))
        self.assertEqual(self.fx.effects, [])

    def test_archer_arrow_hits_far_away_and_counts_for_energy(self):
        pc = combat.PlayerCombat("archer")
        far = self.target(500)
        self.assertTrue(pc.try_attack(self.hero, self.enc, (1, 0), self.fx))
        self.assertEqual(self.swings, [])
        self.fly([far])
        self.assertLess(far.hp, 10)
        self.assertGreater(self.fx.basic_dealt, 0)

    def test_ground_skills_land_on_the_cursor(self):
        from skills.skills import SkillCaster, SkillFX, Pools
        from skills import classes
        for cls, slot in (("mage", "special"), ("archer", "special")):
            fx = SkillFX()
            pools = Pools(classes.stats(cls)["bars"])
            SkillCaster(cls).cast(slot, pools, 0, 0, (0, 1), 3, fx, reach=250)
            spot = fx.effects[0]
            self.assertAlmostEqual(math.hypot(spot.x, spot.y), 250, delta=1)


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
        from monsters import game_sprites
        regulars = {"goblin_minion", "goblin_shaman", "wild_boar"} | set(combat.SLIME_SKINS)
        enc = self.start("1-1", "guard")
        skins = {e.skin for e in enc.enemies}
        self.assertIn("giant_boar", skins)
        self.assertTrue(skins <= regulars | {"giant_boar"}, skins)
        self.assertTrue(skins <= set(game_sprites.SKINS), skins)
        enc = self.start("1-2", "miniboss")
        self.assertEqual(enc.miniboss.skin, "goblin_general")
        self.assertEqual(enc.miniboss.name, "General Grub")

    def test_every_monster_room_has_4_to_6_mobs_spread_on_open_floor(self):
        lo, hi = combat.MOBS_PER_ROOM
        for floor in ("1-1", "1-2", "1-3", "2-1", "3-2", "11-1"):
            d = floor_dungeon(floor)
            for room, role in enumerate(d.room_roles):
                if role in combat.SAFE_ROLES or role == "boss":
                    continue
                with self.subTest(floor=floor, room=room, role=role):
                    enc = combat.Encounters(d)
                    rect = d.rooms[room]
                    hero = types.SimpleNamespace(x=(rect.left + 1.5) * combat.TILE,
                                                 y=(rect.centery + 0.5) * combat.TILE)
                    enc._start_room(room, hero)
                    mobs = [e for e in enc.enemies if getattr(e, "kind", "normal") != "elite"]
                    self.assertTrue(lo <= len(mobs) <= hi, len(mobs))
                    for e in mobs:
                        self.assertTrue(combat.free(d, e.x, e.y, 10, 10))
                        self.assertTrue(d.lock_rect.collidepoint(e.x, e.y))
                        self.assertGreaterEqual(math.hypot(e.x - hero.x, e.y - hero.y), combat.SPAWN_SAFE)
                    d.lock_rect = None

    def test_goblin_rooms_are_random(self):
        d = floor_dungeon("1-1")
        enc = combat.Encounters(d)
        names = set()
        rosters = set()
        for _ in range(60):
            r = enc._goblin_roster(6)
            self.assertLessEqual(r.count("shaman"), combat.MAX_SHAMANS)
            names.update(r)
            rosters.add(tuple(r))
        self.assertEqual(names, {"minion", "shaman", "slime", "boar"})
        self.assertGreater(len(rosters), 20, "rooms are not all the same")
        rect = d.rooms[1]
        a = enc._spawn_spots(rect, 5, types.SimpleNamespace())
        b = enc._spawn_spots(rect, 5, types.SimpleNamespace())
        self.assertNotEqual(a, b, "spawn spots change from room to room")
        skins = {enc._goblin_mob(k, 0, 0).skin for k in ("minion", "boar")}
        self.assertEqual(skins, {"goblin_minion", "wild_boar"})
        self.assertIn(enc._goblin_mob("slime", 0, 0).skin, combat.SLIME_SKINS)

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
        d = floor_dungeon("1-1")
        enc = combat.Encounters(d)
        enc._goblin_roster = lambda n: ["shaman"] * n          # make sure this room has shamans
        room = next(i for i, r in enumerate(d.room_roles) if r == "guard")
        rect = d.rooms[room]
        enc._start_room(room, types.SimpleNamespace(x=rect.centerx * combat.TILE, y=rect.centery * combat.TILE))
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


class ShamanCasts(unittest.TestCase):
    """The shaman's fireball leaves on the cast sheet's hit frame; its barrier shields the group."""

    def setUp(self):
        self.d = types.SimpleNamespace(can_stand=lambda x, y: True, lock_rect=None,
                                       tiles=[combat.FLOOR] * (combat.MAP_W * combat.MAP_H))
        self.pc = combat.PlayerCombat("warrior")
        self.player = types.SimpleNamespace(x=600, y=300, dash_t=0.0)
        self.group = []
        self.bolts = []
        self.sh = combat.RangedEnemy(400, 300, "Goblin Shaman", 8, 70, 2, (0, 0, 0), 14,
                                     bolts=self.bolts, allies=lambda: self.group)
        self.near = combat.Enemy(450, 330, "Goblin Minion", 10, 0, 2, (0, 0, 0), 14)
        self.far = combat.Enemy(400 + combat.BARRIER_RANGE + 60, 300, "Wild Boar", 12, 0, 3, (0, 0, 0), 18)
        self.boss = types.SimpleNamespace(x=420, y=300, dead=False, kind="boss")
        self.group += [self.sh, self.near, self.far, self.boss]

    def run_for(self, secs):
        for _ in range(int(round(secs / DT))):
            self.pc.hp = self.pc.max_hp
            self.sh.update(DT, self.player, self.d, self.pc)

    def test_fireball_waits_for_the_release_frame(self):
        self.sh.barrier_cd, self.sh.attack_cd = 99, 0.0
        self.run_for(DT)
        self.assertEqual(self.sh.cast["clip"], "fireball")
        release, length = combat.RangedEnemy.FIREBALL
        self.run_for(release - 2 * DT)
        self.assertEqual(self.bolts, [], "no fireball before the staff fires")
        self.run_for(3 * DT)
        self.assertEqual(len(self.bolts), 1)
        b = self.bolts[0]
        self.assertGreater(b.x, self.sh.x, "leaves from the staff, in front of him")
        self.assertGreater(b.lift, combat.EnemyBolt.BODY_LIFT, "starts up at the orb")
        x0 = self.sh.x
        self.run_for(length)
        self.assertIsNone(self.sh.cast)
        self.assertEqual(len(self.bolts), 1, "one fireball per cast")
        self.assertEqual(self.sh.x, x0, "stands still while casting")

    def test_barrier_shields_self_and_nearby_minions_not_far_ones_or_bosses(self):
        self.sh.barrier_cd = self.sh.attack_cd = 0.0
        self.run_for(DT)
        self.assertEqual(self.sh.cast["clip"], "barrier")
        self.assertEqual(self.sh.attack_clip, "barrier")
        self.run_for(combat.RangedEnemy.BARRIER[0] + DT)
        self.assertEqual(self.sh.shield, combat.BARRIER_SHIELD)
        self.assertEqual(self.near.shield, combat.BARRIER_SHIELD)
        self.assertEqual(self.far.shield, 0)
        self.assertFalse(hasattr(self.boss, "shield"))

    def test_shield_soaks_damage_then_breaks_and_expires(self):
        e = self.near
        e.give_shield(6, 6.0)
        e.take_damage(4)
        self.assertEqual((e.hp, e.shield), (10, 2))
        e.take_damage(5)
        self.assertEqual((e.hp, e.shield), (7, 0))
        e.give_shield(6, 1.0)
        e.cc_tick(1.1)
        self.assertEqual(e.shield, 0)
        e.take_damage(3)
        self.assertEqual(e.hp, 4)

    def test_stun_breaks_the_spell(self):
        self.sh.barrier_cd, self.sh.attack_cd = 99, 0.0
        self.run_for(DT)
        self.sh.stun_t = 1.0
        self.run_for(combat.RangedEnemy.FIREBALL[1])
        self.assertIsNone(self.sh.cast)
        self.assertEqual(self.bolts, [])


class GoblinKingPhase2(unittest.TestCase):
    """At half HP Valdur roars (can't be hurt), then his minions join the fight."""

    def setUp(self):
        from bosses.goblin_king import boss_config as gk_cfg
        self.gk_cfg = gk_cfg
        d = floor_dungeon("1-3")
        self.enc = combat.Encounters(d)
        room = self.enc.boss_room
        rect = d.rooms[room]
        self.player = types.SimpleNamespace(x=rect.centerx * combat.TILE, y=rect.centery * combat.TILE,
                                            dash_t=0.0)
        self.enc._start_room(room, self.player)
        self.boss = self.enc.enemies[0]
        self.pc = combat.PlayerCombat("warrior")

    def tick(self, seconds):
        for _ in range(int(seconds / DT)):
            self.pc.hp = self.pc.max_hp
            self.enc.update(DT, self.player, self.pc)

    def test_half_hp_roar_then_minions_once(self):
        b, enc = self.boss, self.enc
        b.take_damage(b.max_hp // 2 - 1)                 # still above half
        self.assertEqual(b.phase, 1)
        b.take_damage(2)
        self.assertEqual(b.phase, 2)
        self.assertTrue(b.summoning)
        self.assertIn("Enraged", b.name)
        hp = b.hp
        b.take_damage(50)
        self.assertEqual(b.hp, hp, "can't be hurt while he roars")
        self.tick(0.1)
        self.assertIn("roar", enc.sound_queue)
        self.assertEqual(len(enc.summon_spots), len(self.gk_cfg.PHASE2_SUMMONS))
        self.tick(self.gk_cfg.SUMMON_TIME + 0.1)
        minions = [e for e in enc.enemies if getattr(e, "summoned", False)]
        self.assertEqual(len(minions), len(self.gk_cfg.PHASE2_SUMMONS))
        kinds = {e.skin for e in minions}
        self.assertIn("goblin_minion", kinds)
        self.assertIn("goblin_shaman", kinds)
        for m in minions:
            self.assertTrue(enc.d.lock_rect.collidepoint(m.x, m.y))
            self.assertTrue(combat.free(enc.d, m.x, m.y, 10, 10))
        self.assertFalse(b.summoning)
        b.take_damage(1)
        self.assertEqual(b.hp, hp - 1, "hittable again")
        self.tick(1.0)
        self.assertEqual(len([e for e in enc.enemies if getattr(e, "summoned", False)]), len(minions),
                         "summons only once")

    def test_killing_the_king_scatters_his_minions(self):
        b, enc = self.boss, self.enc
        b.take_damage(b.max_hp // 2 + 1)
        self.tick(self.gk_cfg.SUMMON_TIME + 0.2)
        self.assertGreater(len(enc.enemies), 1)
        b.take_damage(b.max_hp)
        self.tick(DT)
        self.assertEqual(enc.enemies, [])
        self.assertEqual(enc.state[enc.boss_room], "cleared")
        self.assertEqual(enc.outro_request, "goblin_king")
        self.assertEqual([k[3] for k in enc.killed], ["boss"])


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
        # the team's merged Elf Archer, not generated villager art
        self.assertEqual((g.surface.player.sprite.cls, g.player.sprite.cls), ("archer", "archer"))
        self.assertIn("charge_attack", g.player.sprite.clips)
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


class GearAndStats(unittest.TestCase):
    """Gear and stat points change the hero; the save keeps them; barriers and defense soak hits."""

    def setUp(self):
        from inventory.gear import Item
        self.Item = Item

    def test_gear_and_points_reach_combat_and_survive_saving(self):
        s = save_state.SaveState()
        s.reset("Aria", "archer")
        s.xp = save_state.LEVEL_XP[4]                       # level 5: 8 stat points
        self.assertEqual(s.stat_points, 8)
        pc = combat.PlayerCombat("archer")
        s.apply_to(pc)
        hp0, atk0, cd0, spd0 = pc.max_hp, pc.attack_power, pc.swing_cd, pc.speed_k
        s.gear.add(self.Item("chainmail", 2))
        s.gear.equip(0)
        for a in ("vit", "pow", "agi", "agi"):
            self.assertTrue(s.spend_point(a))
        s.apply_to(pc)
        self.assertGreater(pc.max_hp, hp0)
        self.assertGreater(pc.attack_power, atk0)
        self.assertLess(pc.swing_cd, cd0, "agility attacks faster")
        self.assertGreater(pc.speed_k, spd0)
        self.assertGreater(pc.defense, 0)
        path = fresh_save_path()
        s.save(path)
        back = save_state.SaveState.load(path)
        self.assertEqual(back.gear.equipped["armor"], self.Item("chainmail", 2))
        self.assertEqual(back.alloc, {"vit": 1, "pow": 1, "agi": 2})
        self.assertEqual(back.stat_points, 4)

    def test_old_saves_get_the_starter_weapon(self):
        path = fresh_save_path()
        path.write_text(json.dumps({"hero_class": "mage", "xp": 0}), encoding="utf-8")
        s = save_state.SaveState.load(path)
        self.assertEqual(s.gear.equipped["weapon"].base, "oak_staff")

    def test_basic_attacks_are_slower(self):
        for cls in ("warrior", "mage", "archer"):
            self.assertGreaterEqual(combat.PlayerCombat(cls).swing_cd, 0.5, cls)

    def test_barrier_soaks_damage_then_breaks(self):
        pc = combat.PlayerCombat("mage")
        hero = types.SimpleNamespace(x=0.0, y=0.0)
        ground = types.SimpleNamespace(can_stand=lambda x, y: True)
        pc.barrier = types.SimpleNamespace(absorb=5, done=False, flash=0)
        pc.hurt(3, hero, ground, 10, 0)
        self.assertEqual((pc.hp, pc.barrier.absorb), (pc.max_hp, 2))
        pc.iframes = 0
        pc.hurt(4, hero, ground, 10, 0)
        self.assertEqual(pc.hp, pc.max_hp - 2, "what the barrier can't hold gets through")

    def test_defense_softens_hits(self):
        pc = combat.PlayerCombat("warrior")
        pc.defense = 20                                     # halves damage
        hero = types.SimpleNamespace(x=0.0, y=0.0)
        ground = types.SimpleNamespace(can_stand=lambda x, y: True)
        taken = 0
        for _ in range(400):
            pc.hp, pc.iframes = pc.max_hp, 0
            pc.hurt(4, hero, ground, 10, 0)
            taken += pc.max_hp - pc.hp
        self.assertAlmostEqual(taken / 400, 2.0, delta=0.25)


class GearInGame(GameFlow):
    """The real Game: the character screen, buying gear and picking up drops."""

    def start(self, cls="warrior"):
        g = dungeon_map.Game()
        g.begin_game(True, "Robin", cls)
        g.dialog = None
        g.fade, g.fade_dir = 0.0, 0                          # the opening fade-in is over
        return g

    def test_character_screen_equips_and_spends_points(self):
        from inventory.gear import Item
        g = self.start("warrior")
        g.save.xp = save_state.LEVEL_XP[2]                 # level 3: 4 points
        g.save.gear.add(Item("plate_armor"))
        g.refresh_stats()
        hp = g.pc.max_hp
        self.key(g, pygame.K_i)
        self.assertIsNotNone(g.sheet)
        self.key(g, pygame.K_RETURN)                         # bag slot 0: wear the plate armor
        self.assertEqual(g.save.gear.equipped["armor"].base, "plate_armor")
        self.assertEqual(g.pc.max_hp, hp + 18)
        self.key(g, pygame.K_TAB)
        self.key(g, pygame.K_TAB)                            # stat points
        self.key(g, pygame.K_RETURN)                         # +1 Vitality
        self.assertEqual(g.save.alloc.get("vit"), 1)
        self.assertEqual(g.pc.max_hp, hp + 23)
        self.key(g, pygame.K_ESCAPE)
        self.assertIsNone(g.sheet)
        g.sheet = None
        g.open_sheet()
        g.sheet.draw(g.screen)                               # draws without errors

    def test_torvin_sells_gear_into_the_bag(self):
        g = self.start("mage")
        g.save.gold = 1000
        g.open_shop("torvin")
        self.key(g, pygame.K_d)                              # Gear tab
        self.assertTrue(g.shop.on_gear)
        self.key(g, pygame.K_RETURN)
        self.assertEqual(len(g.save.gear.bag), 1)
        self.assertTrue(g.save.gear.bag[0].usable_by("mage"))
        self.assertLess(g.save.gold, 1000)
        g.shop.draw(g.screen, 0.0)

    def test_drops_are_picked_up(self):
        from inventory.gear import Item
        g = self.start("archer")
        p = g.surface.player
        g.update_loot(0.0)                                   # settle the place first
        g.loot.drop(Item("recurve_bow", 2), p.x, p.y)
        for _ in range(90):
            g.update_loot(DT)
        self.assertEqual(g.save.gear.bag, [Item("recurve_bow", 2)])

    def test_bosses_always_drop_gear(self):
        g = self.start("warrior")
        g.roll_loot(100, 100, 2, "boss")
        self.assertEqual(len(g.loot.items), 1)
        self.assertGreaterEqual(g.loot.items[0]["item"].tier, 2)


if __name__ == "__main__":
    unittest.main()
