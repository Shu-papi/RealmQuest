"""
Checks the polish pass: screen shake (and its setting), hit-pause, the hero reacting to hits,
melee damage numbers, level-up and death effects, the HUD extras, loot labels, the sound
limiter and cache, and the menus with their sounds and animated heroes.
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

from src.maps import combat, dungeon_map, save_state, sfx, story   # noqa: E402
from src.maps.juice import Juice                                    # noqa: E402

DT = 1 / 60


class Shake(unittest.TestCase):
    def test_offset_follows_the_screen_shake_setting(self):
        on = Juice(types.SimpleNamespace(screen_shake=True))
        off = Juice(types.SimpleNamespace(screen_shake=False))
        for j in (on, off):
            j.add_shake(1.0)
            j.update(0.02)
        self.assertNotEqual(on.offset(), (0, 0))
        self.assertEqual(off.offset(), (0, 0))

    def test_shake_and_flash_fade_away(self):
        j = Juice()
        j.add_shake(1.0)
        j.hurt_flash()
        j.hit_pause(0.05)
        self.assertTrue(j.paused())
        for _ in range(90):
            j.update(DT)
        self.assertEqual((j.shake, j.flash, j.paused()), (0.0, 0.0, False))

    def test_particles_live_and_die(self):
        j = Juice()
        j.puff(10, 10, big=True)
        j.level_up(0, 0)
        j.sparks(5, 5)
        self.assertTrue(j.parts and j.rings)
        surf = pygame.Surface((200, 200))
        j.draw_world(surf, 0, 0)
        j.hurt_flash()
        j.draw_screen(surf)
        for _ in range(120):
            j.update(DT)
        self.assertEqual((j.parts, j.rings), ([], []))


class HitsTaken(unittest.TestCase):
    def setUp(self):
        self.pc = combat.PlayerCombat("mage")
        self.hero = types.SimpleNamespace(x=0.0, y=0.0)
        self.ground = types.SimpleNamespace(can_stand=lambda x, y: True)

    def test_hits_are_recorded_with_what_the_barrier_soaked(self):
        self.pc.barrier = types.SimpleNamespace(absorb=2, done=False, flash=0)
        self.pc.hurt(5, self.hero, self.ground, 9, 0)
        self.assertEqual(self.pc.hits, [(3, 2)])
        self.pc.iframes = 0
        self.pc.barrier = types.SimpleNamespace(absorb=50, done=False, flash=0)
        self.pc.hurt(4, self.hero, self.ground, 9, 0)
        self.assertEqual(self.pc.hits[-1], (0, 4))


class GameFeel(unittest.TestCase):
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

    def test_being_hit_flashes_shakes_and_shows_the_number(self):
        g = self.g
        p = g.hero()
        g.pc.hurt(3, p, types.SimpleNamespace(can_stand=lambda x, y: True), p.x + 10, p.y)
        g.react_to_hits()
        self.assertGreater(g.juice.flash, 0)
        self.assertGreater(g.juice.shake, 0)
        self.assertTrue(any(f[2] == "-%d" % (g.pc.max_hp - g.pc.hp) for f in g.fx.floaters))
        self.assertEqual(g.pc.hits, [])
        self.assertEqual(p.sprite.action, "hurt", "the Knight plays his hurt frames")

    def test_earthsplitter_shakes_the_camera_and_pauses(self):
        g = self.g
        g.pc.pools.refill()
        g.cast_skill("special")
        g.update_skills(DT)
        self.assertGreater(g.juice.shake, 0.3)
        self.assertTrue(g.juice.paused())

    def test_sword_hits_show_damage_numbers(self):
        g = self.g
        foe = types.SimpleNamespace(x=0.0, y=0.0, hp=20, radius=12, dead=False)
        g.skill_targets = lambda: [foe]
        before = [(foe, 20)]
        foe.hp = 17
        g.melee_feedback(before)
        self.assertTrue(any(f[2] == "3" for f in g.fx.floaters))
        self.assertTrue(g.juice.parts, "sparks")

    def test_level_up_bursts(self):
        g = self.g
        g.gain_xp(save_state.LEVEL_XP[1] + 1)
        self.assertTrue(g.juice.rings)

    def test_fallen_heroes_lie_down(self):
        for cls in ("warrior", "mage"):
            sprite = dungeon_map.HeroSprite(cls)
            sprite.set_dead(True)
            surf = pygame.Surface((200, 200), pygame.SRCALPHA)
            sprite.update(1.0, False)
            r = sprite.draw(surf, 100, 150)
            self.assertGreater(r.w, r.h * 0.9, cls + " is lying down")

    def test_overworld_fall_waits_then_uses_the_heros_name(self):
        g = self.g
        g.pc.hp, g.pc.dead = 0, True
        g.village_survival(0.5)
        self.assertTrue(g.pc.dead, "lies there a moment first")
        g.village_survival(1.0)
        self.assertFalse(g.pc.dead)
        self.assertTrue(any("Robin fell" in t[0] for t in g.surface.toasts))

    def test_hud_draws_points_and_shield(self):
        g = self.g
        g.save.xp = save_state.LEVEL_XP[3]
        g.pc.barrier = types.SimpleNamespace(absorb=5, max_absorb=10, done=False)
        g.draw_hero_panel(g.screen, 12, 12)          # no errors with both extras

    def test_loot_label_only_near_the_hero(self):
        from inventory.gear import Item
        g = self.g
        p = g.hero()
        surf = pygame.Surface((400, 300))
        calls = []
        g.loot._label = lambda *a: calls.append(a)
        g.loot.items = [{"item": Item("iron_helm"), "x": p.x + 30, "y": p.y, "vx": 0, "vy": 0,
                         "z": 0.0, "vz": 0.0, "age": 1.0},
                        {"item": Item("chainmail"), "x": p.x + 400, "y": p.y, "vx": 0, "vy": 0,
                         "z": 0.0, "vz": 0.0, "age": 1.0}]
        g.loot.draw(surf, p.x - 200, p.y - 150, 0.0, hero=p)
        self.assertEqual(len(calls), 1)

    def test_pause_menu_opens_the_character_screen(self):
        g = self.g
        g.paused = True
        g.pause_action("character")
        self.assertFalse(g.paused)
        self.assertIsNotNone(g.sheet)


class Sounds(unittest.TestCase):
    def test_every_sound_builds_and_variants_exist(self):
        s = sfx.Sfx(cache_dir=tempfile.mkdtemp())
        if not s.ok:
            self.skipTest("no audio device")
        for name in ("step", "enemy_die", "crit", "level_up", "drop_legendary", "equip", "sell",
                     "ui_move", "ui_select", "ui_back", "shield_hit"):
            self.assertIn(name, s.sounds)
        self.assertEqual(len(s.sounds["hit"]), sfx.VARIANTS)

    def test_the_cache_gives_the_same_sounds(self):
        folder = tempfile.mkdtemp()
        a = sfx.Sfx(cache_dir=folder)
        if not a.ok:
            self.skipTest("no audio device")
        self.assertTrue(any(f.startswith("realmquest_sfx_") for f in os.listdir(folder)))
        b = sfx.Sfx(cache_dir=folder)
        self.assertEqual(a.sounds["hit"][0].get_raw(), b.sounds["hit"][0].get_raw())

    def test_limiter_caps_the_same_sound(self):
        s = sfx.Sfx.__new__(sfx.Sfx)
        s.ok, s.muted, s.volume, s.last, s.gain = True, False, 1.0, {}, {}
        played = []

        class Fake:
            def __init__(self):
                self.n = 0

            def get_num_channels(self):
                return self.n

            def set_volume(self, v):
                pass

            def play(self):
                self.n += 1
                played.append(1)

        s.sounds = {"hit": [Fake()]}
        for _ in range(10):
            s.last.clear()                      # ignore the time gap: only the copy cap applies
            s.play("hit")
        self.assertEqual(len(played), sfx.MAX_SAME)
        s.sounds["hit"][0].n = 0
        s.last = {}
        s.play("hit")
        s.play("hit")                           # same moment: the time gap stops the second
        self.assertEqual(len(played), sfx.MAX_SAME + 1)


class Menus(unittest.TestCase):
    def test_front_end_plays_menu_sounds_and_animates_heroes(self):
        from ui.app_screens import FrontEnd
        from ui.settings_data import Settings
        heard = []
        hero = dungeon_map.HeroSprite("mage", height=170)
        sprites = {c: dungeon_map.HeroSprite(c, height=118) for c in ("warrior", "mage", "archer")}
        front = FrontEnd(Settings(), heroes=[hero], sprites=sprites, play=heard.append)
        key = lambda k: front.handle_event(pygame.event.Event(pygame.KEYDOWN, key=k, mod=0, unicode=""))
        key(pygame.K_DOWN)
        self.assertEqual(heard[-1], "ui_move")
        front.open("class")
        key(pygame.K_RIGHT)
        self.assertEqual(heard[-1], "ui_move")
        self.assertEqual(sprites["mage"].action, "attack", "the newly picked hero shows off")
        surf = pygame.Surface((1152, 648))
        front.update(DT)
        front.draw(surf)
        key(pygame.K_ESCAPE)
        self.assertEqual(heard[-1], "ui_back")
        front.open("menu")
        front.draw(surf)

    def test_menus_still_work_without_sounds(self):
        from ui.app_screens import FrontEnd
        from ui.settings_data import Settings
        front = FrontEnd(Settings())
        front.handle_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_DOWN, mod=0, unicode=""))
        front.draw(pygame.Surface((1152, 648)))


if __name__ == "__main__":
    unittest.main()
