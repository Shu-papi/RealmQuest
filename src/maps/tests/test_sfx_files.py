"""
Checks the recorded sound effects (assets/sfx/): they load and get their silence trimmed, the
ambience loop toggles, and monsters / the Goblin King queue the right sounds.
Run from the repo root:  python -m unittest discover -s src/maps/tests
"""
import os
import sys
import tempfile
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

from src.maps import combat, sfx   # noqa: E402

DT = 1 / 60


def open_floor():
    return types.SimpleNamespace(can_stand=lambda x, y: True, lock_rect=None,
                                 tiles=[combat.FLOOR] * (combat.MAP_W * combat.MAP_H))


class RecordedSounds(unittest.TestCase):
    def test_every_file_exists(self):
        for name, (filename, _gain) in sfx.FILE_SOUNDS.items():
            self.assertTrue(os.path.isfile(os.path.join(sfx.SFX_DIR, filename)), name)

    def test_files_load_trimmed_and_ambience_toggles(self):
        s = sfx.Sfx(cache_dir=tempfile.mkdtemp())
        if not s.ok:
            self.skipTest("no audio device")
        for name in sfx.FILE_SOUNDS:
            self.assertIn(name, s.gain, name)
        self.assertLess(s.sounds["shaman_barrier"][0].get_length(), 3.0)    # file is 8 s
        self.assertLess(s.sounds["fireball"][0].get_length(), 1.5)          # file is 8 s
        self.assertGreater(s.sounds["goblin_ambience"][0].get_length(), 30)  # loop kept whole
        s.ambience("goblin_ambience", True)
        self.assertEqual(s.bed, "goblin_ambience")
        s.ambience("goblin_ambience", True)                                  # no restart
        s.ambience("goblin_ambience", False)
        self.assertIsNone(s.bed)

    def test_ambience_without_audio_does_nothing(self):
        s = sfx.Sfx.__new__(sfx.Sfx)
        s.ok = False
        s.ambience("goblin_ambience", True)


class MonsterSounds(unittest.TestCase):
    def setUp(self):
        self.d = open_floor()
        self.pc = combat.PlayerCombat("warrior")
        self.player = types.SimpleNamespace(x=600, y=300, dash_t=0.0)

    def test_boar_hit_queues_its_attack(self):
        boar = combat.Enemy(590, 300, "Wild Boar", 12, 96, 3, (0, 0, 0), 18)
        boar.skin = "wild_boar"
        boar.update(DT, self.player, self.d, self.pc)
        self.assertEqual(boar.pop_sounds(), ["boar_attack"])
        self.assertEqual(boar.sounds, [])

    def test_moving_slime_hops_at_most_once_per_gap(self):
        slime = combat.Enemy(100, 300, "Slime", 6, 76, 2, (0, 0, 0), 13)
        slime.skin = "slime_green"
        for _ in range(int(combat.WALK_SOUND_GAP / DT)):
            slime.update(DT, self.player, self.d, self.pc)
        self.assertEqual(slime.pop_sounds(), ["slime_walk"])

    def test_unvoiced_skins_stay_quiet(self):
        minion = combat.Enemy(590, 300, "Goblin Minion", 10, 86, 2, (0, 0, 0), 14)
        minion.skin = "goblin_minion"
        minion.update(DT, self.player, self.d, self.pc)
        self.assertEqual(minion.pop_sounds(), [])

    def test_shaman_casts_queue_their_sounds(self):
        bolts = []
        sh = combat.RangedEnemy(400, 300, "Goblin Shaman", 8, 70, 2, (0, 0, 0), 14,
                                bolts=bolts, allies=lambda: [sh])
        heard = []
        for clip in ("fireball", "barrier"):
            sh._start_cast(clip)
            while sh.cast is not None:
                self.pc.hp = self.pc.max_hp
                sh.update(DT, self.player, self.d, self.pc)
            heard += sh.pop_sounds()
        self.assertEqual(heard, ["shaman_fireball", "shaman_barrier"])


class KingSounds(unittest.TestCase):
    def test_heavy_swings_then_slams_and_the_room_hears_it(self):
        from bosses.goblin_king.in_game import GoblinKingEnemy
        king = GoblinKingEnemy(400, 300)
        target = types.SimpleNamespace(x=2000, y=300, hp=99, hurt=lambda dmg: None)
        king.boss.start_attack("heavy")
        while king.boss.state == "heavy":
            king.boss.update(DT, target)
        self.assertEqual(king.pop_sounds(), ["king_swing", "king_slam"])
        self.assertEqual(king.pop_sounds(), [])

    def test_encounters_pass_monster_sounds_on(self):
        d = open_floor()
        d.floor_name, d.rooms = "1-1", [pygame.Rect(0, 0, 10, 10)]
        enc = combat.Encounters(d)
        boar = combat.Enemy(590, 300, "Wild Boar", 12, 96, 3, (0, 0, 0), 18)
        boar.skin = "wild_boar"
        enc.enemies, enc.active = [boar], 0
        enc.update(DT, types.SimpleNamespace(x=600, y=300, dash_t=0.0), combat.PlayerCombat("warrior"))
        self.assertIn("boar_attack", enc.sound_queue)


if __name__ == "__main__":
    unittest.main()
