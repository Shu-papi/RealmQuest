"""
Tester mode (python run_map.py --tester): the F1 menu opens everything. Run from the repo root:
    python -m unittest discover -s src/maps/tests

Every test plays on a temporary save file, never on savegame.json.
"""
import os
import sys
import tempfile
import unittest
from pathlib import Path

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
if REPO not in sys.path:
    sys.path.insert(0, REPO)

import pygame

from src.maps import combat, dungeon_map, save_state, tester as tester_mod   # noqa: E402

DT = 1 / 60


def press(game, key):
    game.handle_event(pygame.event.Event(pygame.KEYDOWN, key=key, mod=0, unicode=""))


class TesterMode(unittest.TestCase):
    def setUp(self):
        self._path = save_state.SAVE_PATH
        save_state.SAVE_PATH = Path(tempfile.mkdtemp()) / "savegame_tester.json"
        self.g = dungeon_map.Game(tester=True)
        self.t = self.g.tester
        self.t.start("warrior")

    def tearDown(self):
        save_state.SAVE_PATH = self._path

    def entry(self, page, label_start):
        return next(e for e in page() if e[0].startswith(label_start))

    def run_entry(self, page, label_start):
        return self.entry(page, label_start)[2]()

    def fight(self, label):
        """Start a boss fight from the menu and let the room lock."""
        self.run_entry(self.t.boss_page, label)
        for _ in range(5):
            self.g.enc.update(DT, self.g.player, self.g.pc)

    # ---- the start ---------------------------------------------------------------------
    def test_the_hero_starts_maxed_with_everything_open(self):
        g = self.g
        self.assertEqual((g.state, g.mode), ("playing", "village"))
        self.assertIsNone(g.dialog)                                    # the opening scene is skipped
        self.assertEqual((g.save.level, g.save.hero_name), (save_state.MAX_LEVEL, "Tester"))
        self.assertEqual(g.save.gold, 9999)
        self.assertEqual(g.pc.potions, combat.POTION_MAX)
        self.assertEqual({s: i.tier for s, i in g.save.gear.equipped.items()},
                         {s: 4 for s in ("weapon", "helmet", "armor", "boots", "trinket")})
        for dungeon in (1, 2, 3):
            self.assertTrue(g.is_dungeon_unlocked(dungeon), dungeon)
        for d in dungeon_map.sw_mod.DUNGEONS:                          # the overworld portals too
            self.assertTrue(g.surface.progress.is_unlocked(d), d["id"])

    def test_turning_unlock_off_puts_the_real_gates_back(self):
        self.t.unlock_all = False
        self.t.apply_toggles()
        self.assertFalse(self.g.surface.progress.is_unlocked(dungeon_map.sw_mod.DUNGEONS[2]))
        self.assertFalse(self.g.is_dungeon_unlocked(3))

    def test_the_tester_plays_on_its_own_save_file(self):
        self.assertEqual(save_state.SAVE_PATH.name, "savegame_tester.json")
        self.assertTrue(save_state.SAVE_PATH.is_file())

    # ---- the menu ------------------------------------------------------------------------
    def test_f1_opens_the_menu_and_the_menu_takes_the_keys(self):
        g = self.g
        press(g, pygame.K_F1)
        self.assertTrue(self.t.open)
        press(g, pygame.K_DOWN)
        self.assertEqual(self.t.stack[-1][2], 1)
        press(g, pygame.K_ESCAPE)                                      # Esc closes the menu, not the pause screen
        self.assertFalse(self.t.open)
        self.assertFalse(g.paused)

    def test_without_tester_mode_there_is_no_menu(self):
        plain = dungeon_map.Game()
        self.assertIsNone(plain.tester)
        press(plain, pygame.K_F1)

    def test_the_menu_can_be_walked_and_drawn_everywhere(self):
        screen = pygame.Surface((dungeon_map.SCREEN_W, dungeon_map.SCREEN_H))
        self.t.toggle()
        for index, entry in enumerate(self.t.entries()):
            if entry[1] != "sub":
                continue
            self.t.stack = [["TESTER", self.t.main_page, index, 0]]
            self.t.choose(entry)
            self.assertGreater(len(self.t.entries()), 0, entry[0])
            for key in (pygame.K_DOWN,) * 25 + (pygame.K_UP,) * 3:     # scrolls without a crash
                press(self.g, key)
                self.t.draw(screen)
            press(self.g, pygame.K_LEFT)
            self.assertEqual(len(self.t.stack), 1)

    def test_toggles(self):
        g = self.g
        self.t.update(DT)
        self.assertTrue(g.pc.god)
        self.assertFalse(g.pc.hurt(5, g.player, g.dungeon, 0, 0))      # god mode: no damage at all
        self.t.choose(self.entry(self.t.main_page, "God mode"))
        self.t.choose(self.entry(self.t.main_page, "One-hit kills"))
        self.t.update(DT)
        self.assertFalse(g.pc.god)
        self.assertEqual(g.pc.sword_dmg, 9999)

    # ---- warping -------------------------------------------------------------------------------
    def test_every_floor_can_be_entered(self):
        for floor in tester_mod.all_floors():
            self.t.warp(floor)
            self.assertEqual((self.g.mode, self.g.floor_name), ("dungeon", floor), floor)
            self.assertTrue(self.g.dungeon.can_stand(self.g.player.x, self.g.player.y), floor)

    def test_boss_fights_start_with_the_real_bosses(self):
        from bosses.goblin_king.in_game import GoblinKingEnemy
        from bosses.in_game import BossEnemy
        for label, cls in (("Valdur", GoblinKingEnemy), ("The Minotaur", BossEnemy), ("The Lich King", BossEnemy)):
            self.fight(label)
            self.assertTrue(self.g.enc.locked, label)
            self.assertIsInstance(self.g.enc.enemies[0], cls, label)

    def test_a_boss_fight_is_fresh_every_time_and_can_be_killed(self):
        self.fight("The Minotaur")
        first = self.g.enc
        self.t.kill_all()
        for _ in range(60 * 6):                                        # his death animation, then the room clears
            self.g.enc.update(DT, self.g.player, self.g.pc)
        self.assertFalse(self.g.enc.locked)
        self.assertEqual(self.g.enc.state[-1], "cleared")
        self.run_entry(self.t.boss_page, "The Minotaur")
        self.assertIsNot(self.g.enc, first)
        self.assertEqual(self.g.enc.state[-1], "pending")

    def test_floor_tools(self):
        self.t.warp("1-1")
        g = self.g
        self.t.clear_floor()
        self.assertTrue(g.enc.exit_open())
        self.assertFalse(g.enc.locked)
        self.t.reveal_map()
        self.assertTrue(all(g.minimap.seen))
        self.t.go_exit()
        self.assertTrue(g.dungeon.can_stand(g.player.x, g.player.y))
        self.t.step_floor(1)
        self.assertEqual(g.floor_name, "1-2")

    def test_the_gate_opens(self):
        for floor in ("1-1", "1-2", "3-3"):
            self.t.warp(floor)
            gate = self.g.interact.gate
            if gate:
                self.t.open_gate()
                self.assertTrue(gate["open"], floor)
                return
        self.fail("no floor had a gate")

    def test_back_to_oakwood(self):
        self.t.warp("2-1")
        self.t.to_village()
        self.assertEqual(self.g.mode, "village")

    def test_kill_all_includes_the_lich_kings_skeletons(self):
        self.fight("The Lich King")
        enc = self.g.enc
        for _ in range(60 * 8):
            enc.update(DT, self.g.player, self.g.pc)
        enc.enemies[0].boss.debug_set_hp_percent(0.45)
        for _ in range(60 * 30):
            enc.update(DT, self.g.player, self.g.pc)
            if len(enc.enemies) > 1:
                break
        self.assertGreater(len(enc.enemies), 1)
        self.t.kill_all()
        for _ in range(60 * 6):
            enc.update(DT, self.g.player, self.g.pc)
        self.assertEqual(enc.enemies, [])

    # ---- hero, gear, story ------------------------------------------------------------------------
    def test_class_switch_regears_the_hero(self):
        self.t.set_class("mage")
        g = self.g
        self.assertEqual(g.save.hero_class, "mage")
        self.assertEqual(g.save.gear.equipped["weapon"].hero_class, "mage")
        self.assertEqual(g.pc.character_class, "mage")
        self.assertEqual(g.save.level, save_state.MAX_LEVEL)

    def test_the_bag_fills_with_items_for_my_class(self):
        self.t.fill_bag()
        bag = self.g.save.gear.bag
        self.assertGreater(len(bag), 10)
        self.assertTrue(all(i.hero_class in (None, "warrior") for i in bag))
        self.t.empty_bag()
        self.assertEqual(self.g.save.gear.bag, [])

    def test_levels_gold_potions(self):
        s = self.g.save
        s.xp = 0
        self.t.add_level(3)
        self.assertEqual(s.level, 4)
        gold = s.gold
        self.t.add_gold()
        self.assertEqual(s.gold, gold + 5000)
        self.t.max_level()
        self.assertEqual(s.level, save_state.MAX_LEVEL)

    def test_story_tools(self):
        self.t.mark_cleared()
        self.assertEqual(self.g.save.stage, 3)
        self.assertEqual(self.g.surface.progress.cleared, {"goblin", "berserker", "lich"})   # one shared set
        self.t.unclear()
        self.assertEqual(self.g.save.stage, 0)
        self.t.shop("torvin")
        self.assertIsNotNone(self.g.shop)
        self.g.shop = None
        for label, _kind, action in [e for e in self.t.story_page() if e[0].startswith("Scene")]:
            action()
            self.assertIsNotNone(self.g.dialog, label)
            self.g.dialog = None


if __name__ == "__main__":
    unittest.main()
