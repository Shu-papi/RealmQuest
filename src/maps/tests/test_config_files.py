"""
config/ : one settings file per boss, monster and hero class (read by src/balance.py at start-up).
Run from the repo root:  python -m unittest discover -s src/maps/tests

Every check starts a fresh Python, because the files are read once, when the code is first imported.
"""
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
CONFIG = os.path.join(REPO, "config")

SNAPSHOT = r'''
import json, os, sys
sys.path.insert(0, os.path.join(%(repo)r, "tools"))
import make_config_files as tool
specs = tool.load_specs()
out = {}
for (group, name), spec in specs.items():
    keys = list(spec["row_fields"]) + [k for k in spec["fields"] if k not in spec["row_fields"]]
    out[group + "/" + name] = {k: tool.value_of(spec, k) for k in keys}
print(json.dumps(out, default=list, sort_keys=True))
'''


def snapshot(config):
    """Every declared setting as the game sees it with `config` (a folder, a file or "none"), + the warnings."""
    env = dict(os.environ, REALMQUEST_BALANCE=config, PYGAME_HIDE_SUPPORT_PROMPT="1",
               SDL_VIDEODRIVER="dummy", SDL_AUDIODRIVER="dummy")
    code = SNAPSHOT % {"repo": REPO}
    # the tool forces REALMQUEST_BALANCE=none for itself; undo that so the snapshot reads `config`
    code = code.replace("import make_config_files as tool",
                        "import make_config_files as tool; os.environ['REALMQUEST_BALANCE'] = %r" % config)
    result = subprocess.run([sys.executable, "-c", code], env=env, capture_output=True, text=True,
                            cwd=tempfile.gettempdir())
    if result.returncode != 0:
        raise AssertionError(result.stderr)
    warnings = [l for l in result.stderr.splitlines() if l.startswith("[RealmQuest balance]")]
    return json.loads(result.stdout), warnings


class ConfigFiles(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.defaults, cls.default_warnings = snapshot("none")
        cls.shipped, cls.shipped_warnings = snapshot(CONFIG)

    def test_every_boss_monster_and_class_has_a_file(self):
        for group in ("bosses", "monsters", "characters"):
            self.assertTrue(os.path.isdir(os.path.join(CONFIG, group)), group)
        expected = ["bosses/goblin_king", "bosses/minotaur", "bosses/lich_king",
                    "characters/warrior", "characters/mage", "characters/archer", "characters/hero",
                    "monsters/orc_warrior", "monsters/orc_shaman", "monsters/treant", "monsters/orc_warlord",
                    "monsters/goblin_minion", "monsters/goblin_general", "monsters/skeleton_warden"]
        for key in expected:
            self.assertIn(key, self.shipped)
        for key in self.shipped:
            group, name = key.split("/")
            folder = {"overworld": os.path.join("monsters", "overworld")}.get(group, group)
            self.assertTrue(os.path.exists(os.path.join(CONFIG, folder, name + ".toml")), key)
        for name in ("skeleton_warrior", "skeleton_archer", "skeleton_acolyte", "skeleton_brute"):
            self.assertTrue(os.path.exists(os.path.join(CONFIG, "monsters", name + ".toml")), name)
        self.assertTrue(os.path.exists(os.path.join(CONFIG, "tiers.toml")))
        self.assertFalse(os.path.exists(os.path.join(CONFIG, "balance.toml")))       # split up, not read any more
        self.assertFalse(any(k.startswith("overworld/") for k in self.shipped),
                         "the wilds use the dungeon monsters' files")
        self.assertFalse(os.path.isdir(os.path.join(CONFIG, "monsters", "overworld")))

    def test_the_shipped_files_load_without_a_single_warning(self):
        self.assertEqual(self.default_warnings, [])
        self.assertEqual(self.shipped_warnings, [])

    def fresh_copy(self):
        """A copy of config/ with every generated file reset to the code's defaults (your edits stay in config/)."""
        folder = tempfile.mkdtemp()
        copy = os.path.join(folder, "config")
        shutil.copytree(CONFIG, copy)
        self.addCleanup(shutil.rmtree, folder, True)
        result = subprocess.run([sys.executable, os.path.join(REPO, "tools", "make_config_files.py"), "--force",
                                 "--root", copy], capture_output=True, text=True, cwd=tempfile.gettempdir(),
                                env=dict(os.environ, PYGAME_HIDE_SUPPORT_PROMPT="1"))
        self.assertEqual(result.returncode, 0, result.stderr)
        return copy

    def test_freshly_generated_files_hold_the_code_defaults(self):
        """The generator writes every number in the code, so loading its files gives exactly the defaults
        (config/ itself may hold your own tuning, so it is not compared)."""
        copy = self.fresh_copy()
        for hand_written in ("bosses/lich_king.toml", "tiers.toml"):       # (kept as they are: not generated)
            shutil.copyfile(os.path.join(CONFIG, hand_written), os.path.join(copy, hand_written))
        data, warnings = snapshot(copy)
        self.assertEqual(warnings, [])
        for key, settings in self.defaults.items():
            if key in ("bosses/lich_king",):          # hand-written file: your tuning
                continue
            self.assertEqual(data[key], settings, key)

    def set_value(self, copy, rel, key, new):
        """Change `key = value` in a file of the copy, keeping the note after it."""
        path = os.path.join(copy, rel)
        with open(path, encoding="utf-8") as f:
            text = f.read()
        pattern = re.compile(r"^(%s\s*=\s*)([^#\n]*?)(\s*(#.*)?)$" % re.escape(key), re.M)
        match = pattern.search(text)
        self.assertIsNotNone(match, f"{rel}: {key}")
        text = text[:match.start()] + match.group(1) + new + match.group(3) + text[match.end():]
        with open(path, "w", encoding="utf-8") as f:
            f.write(text)

    def test_an_edited_file_changes_the_game_and_a_typo_is_reported(self):
        copy = self.fresh_copy()
        edits = [
            ("monsters/orc_shaman.toml", "meteor_cooldown", "5.5"),
            ("monsters/orc_warrior.toml", "hp", "20"),
            ("characters/mage.toml", "hp", "50"),
            ("characters/hero.toml", "potion_max", "9"),
            ("bosses/goblin_king.toml", "max_hp", "777"),
            ("bosses/minotaur.toml", "rock_damage", "14"),
            ("bosses/minotaur.toml", "max_hp", "1234"),
            ("bosses/lich_king.toml", "hp_power", "20"),
        ]
        for rel, key, new in edits:
            self.set_value(copy, rel, key, new)
        self.set_value(copy, "characters/mage.toml", "meteor", "[40, 12.0]")
        self.set_value(copy, "monsters/slime.toml", "speed", "90")
        with open(os.path.join(copy, "monsters", "slime.toml"), encoding="utf-8") as f:
            text = f.read().replace("speed = 90", "sped = 90", 1)                # a typo
        with open(os.path.join(copy, "monsters", "slime.toml"), "w", encoding="utf-8") as f:
            f.write(text)
        data, warnings = snapshot(copy)
        self.assertEqual(data["monsters/orc_shaman"]["meteor_cooldown"], 5.5)
        self.assertEqual(data["monsters/orc_warrior"]["hp"], 20)
        self.assertEqual(data["characters/mage"]["hp"], 50)
        self.assertEqual(data["characters/mage"]["skills"]["meteor"], [40, 12.0])
        self.assertEqual(data["characters/hero"]["potion_max"], 9)
        self.assertEqual(data["bosses/goblin_king"]["dungeon"]["max_hp"], 777)   # (the dungeon number)
        self.assertEqual(data["bosses/minotaur"]["rock_damage"], 14)
        self.assertEqual(data["bosses/minotaur"]["max_hp"], 1234)
        self.assertEqual(data["bosses/lich_king"]["dungeon"]["hp_power"], 20)
        self.assertEqual(data["monsters/slime"]["speed"], self.defaults["monsters/slime"]["speed"])
        self.assertTrue(any("sped" in w and "Did you mean 'speed'" in w for w in warnings), warnings)

    def test_a_wrong_value_is_ignored_with_a_warning(self):
        copy = self.fresh_copy()
        path = os.path.join(copy, "monsters", "treant.toml")
        with open(path, encoding="utf-8") as f:
            text = f.read().replace("hp = 18", 'hp = "lots"', 1)
        with open(path, "w", encoding="utf-8") as f:
            f.write(text)
        data, warnings = snapshot(copy)
        self.assertEqual(data["monsters/treant"]["hp"], 18)
        self.assertTrue(any("treant" in w and "'hp'" in w for w in warnings), warnings)


if __name__ == "__main__":
    unittest.main()
