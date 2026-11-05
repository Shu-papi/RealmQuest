"""
Live config: saving a file under config/ changes the running game (balance.reload + ConfigWatcher),
a deleted line goes back to the code default, and monsters / bosses already alive pick the new
numbers up with the same share of health left.
Run from the repo root:  python -m unittest discover -s src/maps/tests
"""
import os
import re
import shutil
import sys
import tempfile
import unittest

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
if REPO not in sys.path:
    sys.path.insert(0, REPO)

import pygame

pygame.init()
pygame.display.set_mode((1152, 648))

from src.maps import combat   # noqa: E402  (puts src/ on the path)
import balance                # noqa: E402
from bosses.goblin_king import boss_config as gk_cfg            # noqa: E402
from bosses.goblin_king.in_game import GoblinKingEnemy           # noqa: E402

CONFIG = os.path.join(REPO, "config")


def set_value(path, key, value):
    """Change `key = ...` in a TOML file (keeps its comment)."""
    with open(path, encoding="utf-8") as f:
        text = f.read()
    new, n = re.subn(r"(?m)^(%s\s*=\s*)[^#\n]*?(\s*(#.*)?)$" % re.escape(key),
                     lambda m: m.group(1) + value + m.group(2), text, count=1)
    assert n == 1, (path, key)
    with open(path, "w", encoding="utf-8") as f:
        f.write(new)


def drop_line(path, key):
    with open(path, encoding="utf-8") as f:
        lines = [ln for ln in f if not re.match(r"%s\s*=" % re.escape(key), ln)]
    with open(path, "w", encoding="utf-8") as f:
        f.writelines(lines)


class LiveReload(unittest.TestCase):
    def setUp(self):
        self.tmp = os.path.join(tempfile.mkdtemp(), "config")
        shutil.copytree(CONFIG, self.tmp)
        self._env = os.environ.get("REALMQUEST_BALANCE")
        os.environ["REALMQUEST_BALANCE"] = self.tmp
        self.assertEqual(balance.reload(), [], "the shipped files load clean")

    def tearDown(self):
        if self._env is None:
            os.environ.pop("REALMQUEST_BALANCE", None)
        else:
            os.environ["REALMQUEST_BALANCE"] = self._env
        balance.reload()
        shutil.rmtree(os.path.dirname(self.tmp), ignore_errors=True)

    def file(self, *parts):
        return os.path.join(self.tmp, *parts)

    def test_an_edit_applies_without_a_restart(self):
        set_value(self.file("characters", "hero.toml"), "sword_reach", "123")
        set_value(self.file("characters", "hero.toml"), "dash_speed", "700.0")
        self.assertEqual(balance.reload(), [])
        self.assertEqual(combat.SWORD_REACH, 123)
        self.assertEqual(combat.DASH_SPEED, 700.0)

    def test_a_deleted_line_goes_back_to_the_default(self):
        set_value(self.file("characters", "hero.toml"), "sword_reach", "123")
        balance.reload()
        drop_line(self.file("characters", "hero.toml"), "sword_reach")
        balance.reload()
        self.assertEqual(combat.SWORD_REACH, 90, "the code default")

    def test_rows_and_class_stats_reload(self):
        set_value(self.file("monsters", "goblin_minion.toml"), "hp", "40")
        set_value(self.file("characters", "warrior.toml"), "hp", "77")
        balance.reload()
        self.assertEqual(combat.GOBLIN_MOBS["minion"][1], 40)
        self.assertEqual(combat.hero_classes.stats("warrior")["hp"], 77)

    def test_a_living_monster_keeps_its_share_of_health(self):
        name, hp, speed, dmg, col, rad = combat.GOBLIN_MOBS["minion"]
        e = combat.Enemy(0, 0, name, hp, speed, dmg, col, rad)
        e.cfg = (combat.GOBLIN_MOBS, "minion")
        e.hp = hp / 2
        set_value(self.file("monsters", "goblin_minion.toml"), "hp", "40")
        set_value(self.file("monsters", "goblin_minion.toml"), "speed", "120")
        balance.reload()
        e.refresh_config()
        self.assertEqual(e.max_hp, 40)
        self.assertEqual(e.hp, 20)
        self.assertEqual(e.speed, 120)

    def test_orc_reach_from_the_file_reaches_the_orcs(self):
        set_value(self.file("monsters", "orc_warrior.toml"), "reach", "55")
        balance.reload()
        orc = combat.OrcEnemy(0, 0, *combat.BERSERKER_MOBS["orc"])
        self.assertEqual(orc.reach, 55)

    def test_the_goblin_king_refreshes_while_alive(self):
        boss = GoblinKingEnemy(400, 400)
        boss.boss.hp = boss.boss.max_hp // 2
        set_value(self.file("bosses", "goblin_king.toml"), "slam_reach", "300")
        set_value(self.file("bosses", "goblin_king.toml"), "max_hp", "4000")
        balance.reload()
        self.assertEqual(gk_cfg.HEAVY["hits"][12][0], 300)
        boss.refresh_config()
        dk = gk_cfg.IN_GAME["dist_k"]
        self.assertAlmostEqual(boss.boss.hits["heavy"][12][0], 300 * dk)
        self.assertEqual(boss.max_hp, 4000)
        self.assertEqual(boss.hp, 2000)

    def test_a_typo_is_reported_back(self):
        set_value(self.file("monsters", "goblin_minion.toml"), "hp", '"lots"')
        warnings = balance.reload()
        self.assertTrue(any("goblin_minion" in w and "'hp'" in w for w in warnings), warnings)
        self.assertEqual(combat.GOBLIN_MOBS["minion"][1], 10, "kept the default")

    def test_the_watcher_notices_a_save(self):
        clock = [0.0]
        watch = balance.ConfigWatcher(interval=0.5, settle=0.3, clock=lambda: clock[0])
        self.assertIsNone(watch.poll())
        path = self.file("bosses", "goblin_king.toml")
        st = os.stat(path)
        os.utime(path, (st.st_atime, st.st_mtime + 5))
        seen = None
        for _ in range(10):
            clock[0] += 0.5
            seen = watch.poll() or seen
        self.assertEqual(seen, ["goblin_king.toml"])
        clock[0] += 5
        self.assertIsNone(watch.poll(), "reported once")


if __name__ == "__main__":
    unittest.main()
