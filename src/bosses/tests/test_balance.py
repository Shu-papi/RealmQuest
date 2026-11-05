"""Run from the repo root:  python -m unittest discover -s src/bosses/tests

Tests for config/balance.toml (src/balance.py). Each check starts a fresh Python, because the config is read
when the boss / monster packages are imported.
"""
import json
import os
import subprocess
import sys
import tempfile
import textwrap
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
SRC_DIR = os.path.dirname(os.path.dirname(HERE))
REPO = os.path.dirname(SRC_DIR)
SHIPPED = os.path.join(REPO, "config")          # the config folder: one file per boss / monster / class

SNAPSHOT = r'''
import json, sys
sys.path.insert(0, %(src)r)
try:
    import pygame
except ImportError:
    sys.path.insert(0, %(tests)r)
    from pygame_stub import install
    install()
import balance, monsters
from bosses.lich_king import boss as B, minions as M

def plain(v):
    if isinstance(v, dict):
        return {str(k): plain(x) for k, x in v.items()}
    if isinstance(v, (list, tuple)):
        return [plain(x) for x in v]
    return v

out = {
    "boss": {n: plain(getattr(B, n)) for n in B.TUNABLE},
    "phases": plain(B.PHASE_STATS),
    "monsters": {n: plain(balance.monster_settings(c)) | {"_live": {k: plain(getattr(c, k)) for k in balance.monster_settings(c)}}
                 for n, c in monsters.MONSTERS.items()},
    "tiers": plain(monsters.TIERS),
    "summons": {"cost": M.MINION_COST, "weight": M.SUMMON_WEIGHT, "limit": M.SUMMON_LIMIT, "tier": M.MINION_TIER},
    "king": {"hp": B.LichKing().max_hp, "name": B.LichKing().name, "intro": B.LichKing.INTRO_TIME,
             "radius": B.LichKing().radius},
}
print(json.dumps(out, sort_keys=True))
'''


def snapshot(config_path):
    """Everything tunable, as the game sees it with this config. Returns (data, warnings printed)."""
    code = SNAPSHOT % {"src": SRC_DIR, "tests": HERE}
    env = dict(os.environ, REALMQUEST_BALANCE=config_path, PYGAME_HIDE_SUPPORT_PROMPT="1")   # (no pygame banner in the JSON)
    result = subprocess.run([sys.executable, "-c", code], env=env, capture_output=True, text=True, cwd=tempfile.gettempdir())
    if result.returncode != 0:
        raise AssertionError(result.stderr)
    warnings = [l for l in result.stderr.splitlines() if l.startswith("[RealmQuest balance]")]
    return json.loads(result.stdout), warnings


def write_config(text):
    handle = tempfile.NamedTemporaryFile("w", suffix=".toml", delete=False, encoding="utf-8")
    handle.write(textwrap.dedent(text))
    handle.close()
    return handle.name


class TestBalanceConfig(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.defaults, warnings = snapshot("none")
        assert warnings == [], warnings

    def run_config(self, text):
        path = write_config(text)
        self.addCleanup(os.remove, path)
        return snapshot(path)

    # ---- the shipped file ----

    def test_the_shipped_config_exists_and_has_no_mistakes(self):
        self.assertTrue(os.path.exists(SHIPPED))
        data, warnings = snapshot(SHIPPED)
        self.assertEqual(warnings, [])

    def test_a_freshly_generated_config_changes_nothing(self):
        """The generator writes every number in the code, so loading it must give exactly the defaults."""
        generated = subprocess.run([sys.executable, os.path.join(REPO, "tools", "make_balance_config.py"), "--stdout"],
                                   capture_output=True, text=True, cwd=tempfile.gettempdir(),
                                   env=dict(os.environ, PYGAME_HIDE_SUPPORT_PROMPT="1"))
        self.assertEqual(generated.returncode, 0, generated.stderr)
        data, warnings = self.run_config(generated.stdout)
        self.assertEqual(warnings, [])
        self.assertEqual(data, self.defaults)

    def test_every_setting_in_the_code_is_in_the_generated_file(self):
        generated = subprocess.run([sys.executable, os.path.join(REPO, "tools", "make_balance_config.py"), "--stdout"],
                                   capture_output=True, text=True, cwd=tempfile.gettempdir(),
                                   env=dict(os.environ, PYGAME_HIDE_SUPPORT_PROMPT="1")).stdout
        import tomllib
        table = tomllib.loads(generated)

        def keys(node, found):
            for key, value in node.items():
                found.add(key)
                if isinstance(value, dict):
                    keys(value, found)
            return found
        found = keys(table["boss"], set())
        for name in self.defaults["boss"]:
            self.assertIn(name.lower().replace("boss_", ""), found, name)
        for number in ("1", "2", "3"):
            for key in self.defaults["phases"][number]:
                self.assertIn(key, table["boss"]["phase" + number], key)
        for monster, values in self.defaults["monsters"].items():
            for const in values["_live"]:
                self.assertIn(const.lower(), table["monsters"][monster], f"{monster}.{const}")

    # ---- changing things ----

    def test_boss_settings_change_the_boss(self):
        data, warnings = self.run_config("""
            [boss]
            max_hp = 9999
            name = "Lich Emperor"
            radius = 60
            [boss.timing]
            phase_3_at = 0.4
            intro_time = 0.5
            [boss.damage]
            volley_damage = 99
            [boss.colors.attack_glow]
            volley = [1, 2, 3]
        """)
        self.assertEqual(warnings, [])
        self.assertEqual((data["king"]["hp"], data["king"]["name"], data["king"]["radius"]), (9999, "Lich Emperor", 60))
        self.assertEqual(data["king"]["intro"], 0.5)
        self.assertEqual(data["boss"]["PHASE_3_AT"], 0.4)
        self.assertEqual(data["boss"]["VOLLEY_DAMAGE"], 99)
        self.assertEqual(data["boss"]["ATTACK_GLOW"]["volley"], [1, 2, 3])
        self.assertEqual(data["boss"]["ATTACK_GLOW"]["drain"], self.defaults["boss"]["ATTACK_GLOW"]["drain"])

    def test_phase_settings_change_only_that_phase(self):
        data, warnings = self.run_config("""
            [boss.phase3]
            combo = 7
            barrage_interval = 0.02
            minion_cap = 9
        """)
        self.assertEqual(warnings, [])
        self.assertEqual(data["phases"]["3"]["combo"], 7)
        self.assertEqual(data["phases"]["3"]["barrage_interval"], 0.02)
        self.assertEqual(data["phases"]["2"], self.defaults["phases"]["2"])
        self.assertEqual(data["phases"]["3"]["bolts"], self.defaults["phases"]["3"]["bolts"])

    def test_monster_settings_change_that_monster_only(self):
        data, warnings = self.run_config("""
            [monsters.skeleton_warrior]
            max_hp = 77
            windup_time = 0.1
            gold = [3, 4]
            loot = [["Golden Bone", 1.0]]
            [monsters.skeleton_acolyte.windups]
            bolt = 0.2
        """)
        self.assertEqual(warnings, [])
        warrior = data["monsters"]["skeleton_warrior"]["_live"]
        self.assertEqual((warrior["MAX_HP"], warrior["WINDUP_TIME"], warrior["GOLD"]), (77, 0.1, [3, 4]))
        self.assertEqual(warrior["LOOT"], [["Golden Bone", 1.0]])
        self.assertEqual(data["monsters"]["skeleton_acolyte"]["_live"]["WINDUPS"]["bolt"], 0.2)
        self.assertEqual(data["monsters"]["skeleton_acolyte"]["_live"]["WINDUPS"]["mend"], 0.9)
        self.assertEqual(data["monsters"]["skeleton_archer"], self.defaults["monsters"]["skeleton_archer"])

    def test_tiers_can_be_changed_and_new_ones_added(self):
        data, warnings = self.run_config("""
            [tiers.undying]
            hp_scale = 10.0
            [tiers.nightmare]
            hp_scale = 6.0
            damage_scale = 2.0
        """)
        self.assertEqual(warnings, [])
        self.assertEqual(data["tiers"]["undying"]["hp_scale"], 10.0)
        self.assertEqual(data["tiers"]["undying"]["damage_scale"], self.defaults["tiers"]["undying"]["damage_scale"])
        self.assertEqual(data["tiers"]["nightmare"], {"hp_scale": 6.0, "damage_scale": 2.0, "speed_scale": 1.0})

    def test_his_army_can_be_changed(self):
        data, warnings = self.run_config("""
            [boss.summons]
            tier = "elite"
            [boss.summons.skeleton_brute]
            cost = 3
            weight = 0.5
            limit = 1
        """)
        self.assertEqual(warnings, [])
        self.assertEqual(data["summons"]["tier"], "elite")
        self.assertEqual(data["summons"]["cost"]["skeleton_brute"], 3)
        self.assertEqual(data["summons"]["weight"]["skeleton_brute"], 0.5)
        self.assertEqual(data["summons"]["limit"]["skeleton_warrior"], self.defaults["summons"]["limit"]["skeleton_warrior"])

    # ---- mistakes never crash the game ----

    def test_a_broken_file_falls_back_to_the_defaults(self):
        data, warnings = self.run_config("this is [not valid toml")
        self.assertEqual(data, self.defaults)
        self.assertEqual(len(warnings), 1)

    def test_a_missing_file_falls_back_to_the_defaults(self):
        data, warnings = snapshot(os.path.join(tempfile.gettempdir(), "no_such_balance_file.toml"))
        self.assertEqual(data, self.defaults)
        self.assertEqual(len(warnings), 1)

    def test_wrong_types_and_negative_numbers_are_ignored_with_a_warning(self):
        data, warnings = self.run_config("""
            [boss]
            max_hp = "lots"
            [boss.phase3]
            combo = 2.5
            bolts = -4
            speed = true
            [monsters.skeleton_warrior]
            max_hp = -5
            gold = [1, 2, 3]
        """)
        self.assertEqual(data, self.defaults)
        self.assertEqual(len(warnings), 6, warnings)

    def test_unknown_names_are_reported_with_a_suggestion(self):
        data, warnings = self.run_config("""
            [boss]
            max_hpp = 5
            [boss.phase9]
            combo = 1
            [monsters.skeleton_warior]
            max_hp = 5
            [monsters.skeleton_warrior]
            wind_up_time = 1
            [tiers.undying]
            hp = 3
            [stuff]
            a = 1
        """)
        self.assertEqual(data, self.defaults)
        text = "\n".join(warnings)
        self.assertIn("Did you mean 'max_hp'", text)
        self.assertIn("Did you mean 'skeleton_warrior'", text)
        self.assertIn("Did you mean 'windup_time'", text)
        self.assertIn("[stuff]", text)

    def test_an_int_setting_accepts_a_whole_number_written_as_a_decimal(self):
        data, warnings = self.run_config("""
            [boss.phase3]
            combo = 5.0
            speed = 200
        """)
        self.assertEqual(warnings, [])
        self.assertEqual(data["phases"]["3"]["combo"], 5)
        self.assertEqual(data["phases"]["3"]["speed"], 200.0)

    def test_the_boss_really_uses_the_changed_numbers(self):
        """Not just the constants: a changed volley size / damage shows up in an actual fight."""
        code = textwrap.dedent(r'''
            import sys
            sys.path.insert(0, %(src)r); sys.path.insert(0, %(tests)r)
            from pygame_stub import install; install()
            import pygame
            from bosses import LichKing
            from bosses.dev.arena import BOUNDS
            class P:
                def __init__(self):
                    self.rect = pygame.Rect(0, 0, 28, 28); self.rect.center = (480, 560)
                def take_damage(self, n): return n
            boss = LichKing(seed=1)
            for _ in range(130): boss.update(1 / 60, P(), BOUNDS)
            boss._begin_attack("volley", P(), BOUNDS)
            for _ in range(120): boss.update(1 / 60, P(), BOUNDS)
            print(boss.max_hp, boss.stats["bolts"], boss.projectiles[0].damage if boss.projectiles else None)
        ''') % {"src": SRC_DIR, "tests": HERE}
        path = write_config("""
            [boss]
            max_hp = 1234
            [boss.damage]
            volley_damage = 41
            [boss.phase1]
            bolts = 3
        """)
        self.addCleanup(os.remove, path)
        result = subprocess.run([sys.executable, "-c", code], env=dict(os.environ, REALMQUEST_BALANCE=path),
                                capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.split(), ["1234", "3", "41"])


if __name__ == "__main__":
    unittest.main()
