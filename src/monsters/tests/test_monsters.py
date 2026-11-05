"""
Checks the monster system: every registered monster follows the rules the game relies on,
each skeleton behaves as documented, groups work, and the Lich King can use them.

Run from the repo root:  python -m unittest discover -s src/monsters/tests
"""
import os as _os; _os.environ["REALMQUEST_BALANCE"] = "none"      # these tests pin the code's DEFAULT numbers, not your config/ tuning
import ast
import builtins
import importlib
import os
import pkgutil
import symtable
import sys
import unittest

SRC_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

try:
    import pygame
    REAL_PYGAME = hasattr(pygame, "mask")
except ImportError:                       # the boss tests ship a tiny fake pygame
    sys.path.insert(0, os.path.join(SRC_DIR, "bosses", "tests"))
    from pygame_stub import install
    install()
    import pygame
    REAL_PYGAME = False

import monsters                                                      # noqa: E402
from monsters import (MONSTERS, MonsterGroup, SkeletonAcolyte, deal_damage,  # noqa: E402
                      list_monsters, list_variants, spawn_monster)
from monsters.paths import MONSTERS_DIR, asset_dir               # noqa: E402

BOUNDS = (40, 110, 920, 600)
DT = 1 / 60


class StubPlayer:
    def __init__(self, x=480, y=500):
        self.rect = pygame.Rect(0, 0, 28, 28)
        self.rect.center = (x, y)
        self.damage_taken = 0

    def take_damage(self, amount):
        self.damage_taken += amount
        return amount


def run(monster_or_group, player, seconds):
    for _ in range(int(seconds / DT)):
        monster_or_group.update(DT, player, BOUNDS)


def ready(name, x, y, **options):
    """A monster that has finished rising from the ground."""
    monster = spawn_monster(name, x, y, **options)
    monster.update(monster.SPAWN_TIME + 0.05, StubPlayer(900, 580), BOUNDS)
    return monster


class TestRegistry(unittest.TestCase):
    def test_names_match_art_folders(self):
        for name in MONSTERS:
            with self.subTest(monster=name):
                self.assertEqual(MONSTERS[name].NAME, name)
                self.assertTrue(os.path.isdir(asset_dir(name)),
                                f"assets/monsters/{name}/ is missing")

    def test_unknown_monster_and_variant_give_clear_errors(self):
        with self.assertRaises(ValueError):
            spawn_monster("dragon", 0, 0)
        with self.assertRaises(ValueError):
            spawn_monster("skeleton_warrior", 0, 0, variant="rainbow")

    def test_scaling_options(self):
        tough = spawn_monster("skeleton_warrior", 0, 0, hp_scale=2.0, damage_scale=2.0)
        self.assertEqual(tough.max_hp, 40)
        self.assertEqual(tough.damage, 16)


class TestMonsterContract(unittest.TestCase):
    """Every monster, so a new one is checked automatically."""

    def setUp(self):
        pygame.font.init()

    def test_each_monster_has_what_the_game_needs(self):
        for name in list_monsters():
            with self.subTest(monster=name):
                m = spawn_monster(name, 300, 300)
                for attr in ("x", "y", "radius", "hp", "max_hp", "state", "xp", "variant", "shake",
                             "projectiles", "allies"):
                    self.assertTrue(hasattr(m, attr), f"{name} is missing '{attr}'")
                for method in ("update", "draw", "take_damage", "is_alive", "drop_loot",
                               "hittables", "kill", "heal", "take_spawn_requests"):
                    self.assertTrue(callable(getattr(m, method, None)), f"{name}: {method}()")
                self.assertTrue(m.DISPLAY_NAME)

    def test_each_monster_fights_draws_and_dies(self):
        surface = pygame.Surface((960, 640))
        for name in list_monsters():
            with self.subTest(monster=name):
                m = spawn_monster(name, 480, 250, seed=1)
                player = StubPlayer()
                for frame in range(60 * 15):
                    m.update(DT, player, BOUNDS)
                    if frame % 5 == 0:
                        m.draw(surface)
                    self.assertTrue(BOUNDS[0] <= m.x <= BOUNDS[2] and BOUNDS[1] <= m.y <= BOUNDS[3])
                m.take_damage(10000)
                self.assertFalse(m.is_alive())
                self.assertFalse(m.finished)                      # still shattering
                for frame in range(int((m.DYING_TIME + 0.2) / DT)):
                    m.update(DT, player, BOUNDS)
                    if frame % 4 == 0:
                        m.draw(surface)
                self.assertTrue(m.finished)
                self.assertIsInstance(m.drop_loot(), list)
                self.assertEqual(m.hittables(), [])

    def test_every_variant_draws(self):
        surface = pygame.Surface((960, 640))
        for variant in list_variants():
            for name in list_monsters():
                with self.subTest(monster=name, variant=variant):
                    m = ready(name, 300, 300, variant=variant)
                    run(m, StubPlayer(), 2.0)
                    m.draw(surface)

    def test_cannot_be_hurt_while_rising_then_can(self):
        for name in list_monsters():
            with self.subTest(monster=name):
                m = spawn_monster(name, 300, 300)
                self.assertEqual(m.take_damage(5), 0)
                self.assertEqual(m.hp, m.max_hp)
                m.update(m.SPAWN_TIME + 0.05, StubPlayer(900, 580), BOUNDS)
                self.assertEqual(m.take_damage(5), 5)

    def test_knockback_only_with_a_source(self):
        m = ready("skeleton_warrior", 400, 300, hp_scale=5)
        m.take_damage(5)
        self.assertEqual((m.kx, m.ky), (0.0, 0.0))
        deal_damage(m, 5, source=(300, 300))
        self.assertGreater(m.kx, 0)

    def test_stagger_cannot_be_chained_forever(self):
        m = ready("skeleton_warrior", 400, 300, hp_scale=20)
        player = StubPlayer(900, 580)
        m.take_damage(1)
        self.assertEqual(m.state, "stagger")
        run(m, player, 0.4)
        self.assertNotEqual(m.state, "stagger")
        m.take_damage(1)                                       # inside the shrug-off window
        self.assertNotEqual(m.state, "stagger")

    def test_loot_and_xp(self):
        m = ready("skeleton_brute", 400, 300)
        self.assertEqual(m.drop_loot(), [])
        m.kill()
        self.assertIn("Bone Dust", m.drop_loot())              # the brute always drops it
        self.assertTrue(any(i.endswith("Gold") for i in m.drop_loot()))
        self.assertGreater(m.xp, 0)


class TestWarrior(unittest.TestCase):
    def test_warns_then_lunges_and_can_be_dodged(self):
        hit = StubPlayer(400, 330)
        w = ready("skeleton_warrior", 400, 300); w.slash_cd = 999                    # (the quick basic slash has its own test)
        run(w, hit, 0.75)                                      # 0.6s first-attack delay + wind-up
        self.assertEqual(w.state, "windup")
        self.assertEqual(hit.damage_taken, 0)                  # the warning comes first
        run(w, hit, 1.0)
        self.assertEqual(hit.damage_taken, w.damage)

        dodged = StubPlayer(400, 330)
        w = ready("skeleton_warrior", 400, 300); w.slash_cd = 999                    # (the quick basic slash has its own test)
        for _ in range(int(0.8 / DT)):                        # wind-up is under way, aim locked...
            w.update(DT, dodged, BOUNDS)
        self.assertEqual(w.state, "windup")
        dodged.rect.center = (700, 330)                        # ...and we sidestep far away
        run(w, dodged, 0.5)
        self.assertEqual(dodged.damage_taken, 0)

    def test_one_hit_per_attack(self):
        p = StubPlayer(400, 330)
        w = ready("skeleton_warrior", 400, 300); w.slash_cd = 999                    # (the quick basic slash has its own test)
        run(w, p, 1.7)
        self.assertEqual(p.damage_taken, w.damage)


class TestArcher(unittest.TestCase):
    def test_keeps_its_distance(self):
        a = ready("skeleton_archer", 480, 400)
        player = StubPlayer(480, 450)
        start = a.vector_to(480, 450)[2]
        run(a, player, 1.0)
        self.assertGreater(a.vector_to(480, 450)[2], start)

    def test_fires_arrows_that_hurt_and_fly_off_screen(self):
        a = ready("skeleton_archer", 480, 200)
        player = StubPlayer(480, 450)
        seen = False
        for _ in range(60 * 8):
            a.update(DT, player, BOUNDS)
            seen = seen or bool(a.projectiles)
        self.assertTrue(seen, "the archer never shot")
        self.assertGreater(player.damage_taken, 0)
        miss = StubPlayer(100, 580)
        a2 = ready("skeleton_archer", 480, 200)
        a2.cooldown = 999                                      # so it fires nothing new
        a2.projectiles.append(monsters.attacks.Arrow(480, 200, 0.0, 380, 9))
        run(a2, miss, 3.0)
        self.assertEqual(a2.projectiles, [])

    def test_windup_aim_lock_lets_you_dodge(self):
        a = ready("skeleton_archer", 480, 200)
        player = StubPlayer(480, 450)
        while a.state != "windup":
            a.update(DT, player, BOUNDS)
        while a.state_time < a.windup_time - 0.1:
            a.update(DT, player, BOUNDS)
        player.rect.center = (120, 450)                        # sidestep after the aim locks
        run(a, player, 1.0)
        self.assertEqual(player.damage_taken, 0)


class TestBrute(unittest.TestCase):
    def test_tough_and_not_interrupted_by_hits(self):
        b = ready("skeleton_brute", 480, 300)
        self.assertEqual(b.max_hp, 90)
        player = StubPlayer(480, 360)
        while b.state != "windup":
            b.update(DT, player, BOUNDS)
        b.take_damage(10, source=(480, 360))
        self.assertEqual(b.state, "windup")                    # poise

    def test_slam_hurts_inside_the_circle_only(self):
        inside = StubPlayer(480, 360)
        b = ready("skeleton_brute", 480, 300); b.swipe_cd = 999                    # (the quick backhand has its own test)
        while b.state != "strike":                             # the moment of the slam
            b.update(DT, inside, BOUNDS)
        self.assertEqual(inside.damage_taken, b.damage)
        self.assertGreater(b.shake, 0)

        outside = StubPlayer(480, 360)
        b = ready("skeleton_brute", 480, 300); b.swipe_cd = 999                    # (the quick backhand has its own test)
        for _ in range(int(0.8 / DT)):
            b.update(DT, outside, BOUNDS)
        outside.rect.center = (120, 560)
        run(b, outside, 1.5)
        self.assertEqual(outside.damage_taken, 0)


class TestAcolyte(unittest.TestCase):
    def test_mends_a_wounded_friend(self):
        group = MonsterGroup(seed=1)
        acolyte = group.spawn("skeleton_acolyte", 480, 250, spawn=False)
        brute = group.spawn("skeleton_brute", 560, 250, spawn=False)
        brute.hp = 30
        run(group, StubPlayer(100, 580), 6.0)
        self.assertGreater(brute.hp, 30)
        self.assertTrue(acolyte.is_alive())

    def test_raises_the_dead_up_to_a_cap(self):
        group = MonsterGroup(seed=2)
        group.spawn("skeleton_acolyte", 480, 250, spawn=False)
        run(group, StubPlayer(100, 580), 12.0)
        self.assertGreaterEqual(group.alive_count(), 2)
        run(group, StubPlayer(100, 580), 90.0)
        self.assertLessEqual(group.alive_count(), SkeletonAcolyte.RAISE_CAP + 1)

    def test_a_hit_interrupts_its_spell(self):
        a = ready("skeleton_acolyte", 480, 250, hp_scale=3)
        player = StubPlayer(480, 400)
        while a.state != "windup":
            a.update(DT, player, BOUNDS)
            a.cooldown = 0
        a.take_damage(1)
        self.assertNotEqual(a.state, "windup")


class TestGroup(unittest.TestCase):
    def test_wave_spawns_away_from_the_player(self):
        group = MonsterGroup(seed=3)
        player = StubPlayer(480, 500)
        made = group.spawn_wave(["skeleton_warrior"] * 6, BOUNDS, player, min_distance=240)
        self.assertEqual(len(made), 6)
        for m in made:
            self.assertGreaterEqual(m.vector_to(480, 500)[2], 240)

    def test_monsters_spread_out_instead_of_stacking(self):
        group = MonsterGroup(seed=4)
        a = group.spawn("skeleton_warrior", 400, 300, spawn=False)
        b = group.spawn("skeleton_warrior", 400, 300, spawn=False)
        run(group, StubPlayer(900, 580), 0.2)
        self.assertGreater(a.vector_to(b.x, b.y)[2], 5)

    def test_drops_shatter_and_clear(self):
        group = MonsterGroup(seed=5)
        m = group.spawn("skeleton_warrior", 400, 300, spawn=False)
        m.take_damage(100)
        group.update(DT, StubPlayer(900, 580), BOUNDS)
        drops = group.take_drops()
        self.assertEqual(len(drops), 1)
        self.assertEqual(drops[0]["monster"], "skeleton_warrior")
        self.assertEqual(group.take_drops(), [])
        self.assertTrue(group.is_clear())
        self.assertEqual(len(group.remains), 1)
        run(group, StubPlayer(900, 580), m.DYING_TIME + 0.2)
        self.assertEqual(group.remains, [])

    def test_group_draws_everything(self):
        group = MonsterGroup(seed=6)
        group.spawn_wave(list_monsters(), BOUNDS, StubPlayer())
        surface = pygame.Surface((960, 640))
        for _ in range(120):
            group.update(DT, StubPlayer(), BOUNDS)
            group.draw(surface)


@unittest.skipUnless(REAL_PYGAME, "needs real pygame to look at the PNG files")
class TestArtFiles(unittest.TestCase):
    def test_every_monster_has_valid_art_in_every_variant(self):
        pygame.display.init()
        pygame.display.set_mode((64, 64))
        from monsters.sprites import MARKERS, get_sheet
        for name in list_monsters():
            for variant in list_variants():
                with self.subTest(monster=name, variant=variant):
                    sheet = get_sheet(name, variant)
                    self.assertIsNotNone(sheet, f"{name} art failed to load")
                    for animation in ("walk", "windup", "strike"):      # the required minimum
                        self.assertIn(animation, sheet.animations)
                    for index in range(len(sheet.frames)):
                        sheet.image(index, False, 3, False)
                        sheet.image(index, True, 0, True)
                    ax, ay = sheet.anchor
                    self.assertTrue(0 <= ax < sheet.frame_size[0] and 0 <= ay < sheet.frame_size[1])
        # the glowing eyes must really be there (so they can glow)
        sheet = get_sheet("skeleton_warrior", "bone")
        self.assertTrue(all(len(f.markers["eye"]) > 0 for f in sheet.frames))
        self.assertEqual(set(MARKERS), {"eye", "glow", "orb"})

    def test_no_half_transparent_pixels(self):
        for name in list_monsters():
            with self.subTest(monster=name):
                image = pygame.image.load(os.path.join(asset_dir(name), "frames.png"))
                w, h = image.get_size()
                for y in range(h):
                    for x in range(w):
                        self.assertIn(image.get_at((x, y))[3], (0, 255))


class TestAnimation(unittest.TestCase):
    """The pose a monster shows must follow what the AI is doing."""

    def setUp(self):
        if REAL_PYGAME:                      # the fake pygame used without pygame has no display
            pygame.display.init()
            pygame.display.set_mode((64, 64))

    def test_art_has_the_full_set_of_animations(self):
        need = {"idle": 4, "walk": 8, "windup": 3, "strike": 3, "recover": 2, "hurt": 1}
        for name in list_monsters():
            with self.subTest(monster=name):
                m = spawn_monster(name, 0, 0, spawn=False)
                if m.sheet is None:
                    self.skipTest("needs real pygame")
                for animation, count in need.items():
                    self.assertGreaterEqual(m.sheet.count(animation), count, f"{name}.{animation}")
                used = {i for frames in m.sheet.animations.values() for i in frames}
                self.assertEqual(used, set(range(len(m.sheet.frames))), "every frame is used")

    def test_pose_follows_the_ai_state(self):
        for name in list_monsters():
            with self.subTest(monster=name):
                m = ready(name, 400, 300)
                if m.sheet is None:
                    self.skipTest("needs real pygame")
                m.state = "chase"
                self.assertEqual(m.pose()[0], "idle")
                m.moving = True
                self.assertEqual(m.pose()[0], "walk")
                m.moving = False
                m.begin_windup(0.6)
                self.assertEqual(m.pose(), ("windup", 0))
                m.state_time = 0.59
                self.assertEqual(m.pose(), ("windup", m.sheet.count("windup") - 1))
                m.set_state("strike")
                self.assertEqual(m.pose(), ("strike", 0))
                m.state_time = m.STRIKE_TIME * 0.99
                self.assertEqual(m.pose(), ("strike", m.sheet.count("strike") - 1))
                m.set_state("recover")
                self.assertEqual(m.pose()[0], "recover")
                m.state_time = 100.0
                self.assertEqual(m.pose()[1], m.sheet.count("recover") - 1)   # never runs past the end
                m.set_state("stagger")
                self.assertEqual(m.pose(), ("hurt", 0))

    def test_every_windup_frame_is_shown(self):
        for name in list_monsters():
            with self.subTest(monster=name):
                m = ready(name, 400, 300)
                if m.sheet is None:
                    self.skipTest("needs real pygame")
                m.begin_windup(1.0)
                seen = set()
                for i in range(100):
                    m.state_time = i / 100.0
                    seen.add(m.pose()[1])
                self.assertEqual(seen, set(range(m.sheet.count("windup"))))

    def test_walk_cycle_advances_with_distance_walked(self):
        m = ready("skeleton_warrior", 400, 300)
        if m.sheet is None:
            self.skipTest("needs real pygame")
        steps = set()
        for _ in range(60):
            m.moving = True
            m.walk_t += 1.0
            steps.add(m.pose()[1])
        self.assertEqual(steps, set(range(m.sheet.count("walk"))))

    def test_missing_optional_animations_fall_back(self):
        """A monster drawn with only walk / windup / strike (the old minimum) must still work."""
        m = ready("skeleton_warrior", 400, 300)
        if m.sheet is None:
            self.skipTest("needs real pygame")
        sheet = m.sheet
        saved = sheet.animations
        try:
            sheet.animations = {k: saved[k] for k in ("walk", "windup", "strike")}
            self.assertEqual(sheet.frame_index("idle", 3), saved["walk"][1])
            self.assertEqual(sheet.frame_index("recover", 1), saved["strike"][0])
            self.assertEqual(sheet.frame_index("hurt", 0), saved["walk"][1])
            surface = pygame.Surface((960, 640))
            m.set_state("recover")
            m.draw(surface)
            m.set_state("stagger")
            m.draw(surface)
        finally:
            sheet.animations = saved

    def test_death_shatters_the_hurt_pose_into_chunks(self):
        for name in list_monsters():
            with self.subTest(monster=name):
                m = ready(name, 400, 300)
                if m.sheet is None:
                    self.skipTest("needs real pygame")
                m.kill()
                self.assertGreater(len(m.chunks), 20)

    def test_projectiles_leave_from_the_bow_and_the_casting_hand(self):
        archer = ready("skeleton_archer", 480, 200)
        player = StubPlayer(480, 500)
        while not archer.projectiles:
            archer.update(DT, player, BOUNDS)
        arrow = archer.projectiles[0]
        self.assertGreater(abs(arrow.x - archer.x), 15)          # from the bow, not the belly

        acolyte = ready("skeleton_acolyte", 480, 200)
        acolyte.raise_cooldown = 999
        while not acolyte.projectiles:
            acolyte.update(DT, StubPlayer(480, 480), BOUNDS)
        bolt = acolyte.projectiles[0]
        self.assertGreater(abs(bolt.x - acolyte.x), 15)          # from the glowing hand


class TestLichKingUsesMonsters(unittest.TestCase):
    def setUp(self):
        pygame.font.init()

    def _phase_two_boss(self, seed=1):
        from bosses import LichKing
        boss = LichKing(seed=seed)
        run(boss, StubPlayer(), LichKing.INTRO_TIME + 0.1)
        boss.take_damage(boss.max_hp // 2)
        run(boss, StubPlayer(), boss.TRANSITION_TIME + 0.1)
        return boss

    def test_summons_a_mixed_squad_within_budget(self):
        from bosses.lich_king.boss import MAX_MINIONS
        from bosses.lich_king.minions import minion_load
        kinds = set()
        for seed in range(12):
            boss = self._phase_two_boss(seed)
            player = StubPlayer()
            for _ in range(6):
                boss._begin_attack("summon", player, BOUNDS)
                run(boss, player, boss.windup_time + 0.05)
                kinds.update(m.NAME for m in boss.minions)
            self.assertLessEqual(minion_load(boss.minions), MAX_MINIONS + 2)
            self.assertTrue(all(m.variant == "cursed" for m in boss.minions))
        self.assertGreaterEqual(len(kinds), 3, f"only ever summoned {kinds}")

    def test_minions_shatter_when_the_boss_dies(self):
        boss = self._phase_two_boss()
        player = StubPlayer()
        boss._begin_attack("summon", player, BOUNDS)
        run(boss, player, boss.windup_time + 0.05)
        count = len(boss.minions)
        self.assertGreater(count, 0)
        boss.take_damage(10000)
        run(boss, player, 0.1)
        self.assertEqual(boss.minions, [])
        self.assertEqual(len(boss.remains), count)             # bones still flying
        run(boss, player, 2.0)
        self.assertEqual(boss.remains, [])

    def test_killed_minion_leaves_a_shatter_animation(self):
        boss = self._phase_two_boss()
        player = StubPlayer()
        boss._begin_attack("summon", player, BOUNDS)
        run(boss, player, boss.windup_time + 1.2)
        victim = boss.minions[0]
        victim.take_damage(10000)
        run(boss, player, 0.1)
        self.assertNotIn(victim, boss.minions)
        self.assertIn(victim, boss.remains)


# ----------------------------------------------------------------------
# Catches typos and broken imports in every monsters file
# ----------------------------------------------------------------------

ALWAYS_DEFINED = set(dir(builtins)) | {"__file__", "__name__", "__doc__", "__package__",
                                       "__spec__", "__loader__", "__builtins__"}


def undefined_names(source, filename):
    top = symtable.symtable(source, filename, "exec")
    defined = set(ALWAYS_DEFINED)
    for sym in top.get_symbols():
        if sym.is_assigned() or sym.is_imported() or sym.is_namespace():
            defined.add(sym.get_name())

    def collect(table):
        for sym in table.get_symbols():
            if sym.is_declared_global() and sym.is_assigned():
                defined.add(sym.get_name())
        for child in table.get_children():
            collect(child)

    collect(top)
    problems = []

    def visit(table):
        for sym in table.get_symbols():
            if sym.is_referenced() and sym.is_global() and sym.get_name() not in defined:
                problems.append((sym.get_name(), table.get_name(), table.get_lineno()))
        for child in table.get_children():
            visit(child)

    visit(top)
    return problems


class TestStaticChecks(unittest.TestCase):
    def python_files(self):
        for root, dirs, files in os.walk(MONSTERS_DIR):
            dirs[:] = [d for d in dirs if d != "__pycache__"]
            for name in sorted(files):
                if name.endswith(".py"):
                    yield os.path.join(root, name)

    def test_no_undefined_names(self):
        for path in self.python_files():
            with open(path, encoding="utf-8") as handle:
                source = handle.read()
            ast.parse(source, path)
            for name, scope, line in undefined_names(source, path):
                with self.subTest(file=os.path.relpath(path, SRC_DIR), name=name):
                    self.fail(f"{os.path.relpath(path, SRC_DIR)}: '{name}' used in '{scope}' "
                              f"(line {line}) but never defined or imported")

    def test_every_module_imports(self):
        for info in pkgutil.walk_packages([MONSTERS_DIR], prefix="monsters."):
            if ".dev." in info.name + "." or info.name.endswith(".tests") or ".tests." in info.name:
                continue
            with self.subTest(module=info.name):
                importlib.import_module(info.name)


if __name__ == "__main__":
    unittest.main()


# ----------------------------------------------------------------------
# Difficulty tiers (any area can make its skeletons tougher with one word)
# ----------------------------------------------------------------------

class TestTiers(unittest.TestCase):
    def test_normal_is_the_default_and_changes_nothing(self):
        from monsters import spawn_monster
        a = spawn_monster("skeleton_warrior", 100, 100, spawn=False)
        b = spawn_monster("skeleton_warrior", 100, 100, spawn=False, tier="normal")
        self.assertEqual((a.max_hp, a.damage, a.speed), (b.max_hp, b.damage, b.speed))
        self.assertEqual((a.max_hp, a.damage), (20, 8))

    def test_tiers_get_steadily_tougher(self):
        from monsters import TIERS, spawn_monster
        order = ["normal", "veteran", "elite", "undying"]
        stats = [spawn_monster("skeleton_brute", 0, 0, spawn=False, tier=t) for t in order]
        self.assertEqual(list(TIERS), order)
        for weaker, stronger in zip(stats, stats[1:]):
            self.assertGreater(stronger.max_hp, weaker.max_hp)
            self.assertGreaterEqual(stronger.damage, weaker.damage)
            self.assertGreaterEqual(stronger.speed, weaker.speed)

    def test_explicit_numbers_beat_the_tier(self):
        from monsters import spawn_monster
        m = spawn_monster("skeleton_warrior", 0, 0, spawn=False, tier="undying", hp_scale=1.0)
        self.assertEqual(m.max_hp, 20)
        self.assertGreater(m.damage, 8)

    def test_unknown_tier_is_an_error(self):
        from monsters import spawn_monster
        with self.assertRaises(ValueError):
            spawn_monster("skeleton_warrior", 0, 0, tier="godlike")

    def test_every_monster_accepts_every_tier(self):
        from monsters import TIERS, list_monsters, spawn_monster
        for name in list_monsters():
            for tier in TIERS:
                m = spawn_monster(name, 100, 100, tier=tier)
                for _ in range(30):
                    m.update(1 / 60, StubPlayer(), BOUNDS)

    def test_raised_dead_match_their_acolytes_tier(self):
        from monsters import spawn_monster
        for tier, factor in (("normal", 1.0), ("undying", 3.0)):
            acolyte = spawn_monster("skeleton_acolyte", 100, 100, spawn=False, tier=tier)
            acolyte.action, acolyte.raise_spot = "raise", (200, 200)
            acolyte._cast()
            (baby,) = acolyte.take_spawn_requests()
            self.assertEqual(baby.max_hp, round(20 * factor), tier)

    def test_a_tougher_acolyte_mends_more(self):
        from monsters import spawn_monster
        healed = {}
        for tier in ("normal", "undying"):
            acolyte = spawn_monster("skeleton_acolyte", 100, 100, spawn=False, tier=tier)
            friend = spawn_monster("skeleton_brute", 120, 100, spawn=False)
            friend.hp = 1
            acolyte.action, acolyte.target = "mend", friend
            acolyte._cast()
            healed[tier] = friend.hp - 1
        self.assertGreater(healed["undying"], healed["normal"])



class TestBasicAttacks(unittest.TestCase):
    def test_warrior_slashes_quickly_when_you_stand_next_to_it(self):
        p = StubPlayer(400, 330)
        w = ready("skeleton_warrior", 400, 300)
        w.cooldown = 999                                       # no big lunge: only the basic attack can hit
        run(w, p, 0.5)
        self.assertGreater(p.damage_taken, 0)
        self.assertLess(p.damage_taken, w.damage)              # weaker than the lunge

    def test_warrior_slash_does_not_hurt_from_far_away(self):
        p = StubPlayer(400, 420)
        w = ready("skeleton_warrior", 400, 300)
        w.cooldown = 999
        w.speed = 0
        run(w, p, 1.5)
        self.assertEqual(p.damage_taken, 0)

    def test_slash_is_much_faster_than_the_lunge_and_restores_the_lunge(self):
        w = ready("skeleton_warrior", 400, 300)
        self.assertLess(w.SLASH_WINDUP, w.WINDUP_TIME)
        p = StubPlayer(400, 330)
        w.cooldown = 999
        while w.state != "recover":
            w.update(DT, p, BOUNDS)
        self.assertEqual(w.kind, "slash")
        w.cooldown, w.slash_cd = 0.0, 999
        run(w, StubPlayer(400, 380), 0.5)
        self.assertEqual(w.kind, "lunge")
        self.assertEqual(w.STRIKE_TIME, type(w).STRIKE_TIME)

    def test_archer_uses_snap_shots_and_full_draws(self):
        a = ready("skeleton_archer", 480, 200)
        p = StubPlayer(480, 450)
        windups = set()
        previous = None
        for _ in range(60 * 60):
            a.update(DT, p, BOUNDS)
            if a.state == "windup" and previous != "windup":
                windups.add(round(a.windup_time, 2))
            previous = a.state
        self.assertEqual(windups, {a.SNAP_WINDUP, a.WINDUP_TIME})

    def test_snap_shot_is_faster_but_weaker(self):
        a = ready("skeleton_archer", 480, 200)
        a.snap, a.aim = True, 1.5
        a._shoot()
        snap = a.projectiles[-1]
        a.snap = False
        a._shoot()
        full = a.projectiles[-1]
        self.assertGreater(snap.vx ** 2 + snap.vy ** 2, full.vx ** 2 + full.vy ** 2)
        self.assertLess(snap.damage, full.damage)

    def test_brute_backhands_a_player_who_hugs_it(self):
        p = StubPlayer(480, 300 + 28 + 14 + 4)
        b = ready("skeleton_brute", 480, 300)
        b.cooldown = 999                                       # no slam
        b.rng.random = lambda: 0.0                             # always choose the swipe
        run(b, p, 0.6)
        self.assertGreater(p.damage_taken, 0)
        self.assertLess(p.damage_taken, b.damage)

    def test_every_basic_attack_has_a_wind_up_so_it_can_still_be_dodged(self):
        for name in ("skeleton_warrior", "skeleton_brute"):
            m = ready(name, 400, 300)
            p = StubPlayer(400, 300 + m.radius + 14 + 4)
            m.cooldown = 999
            m.rng.random = lambda: 0.0
            m.update(DT, p, BOUNDS)
            m.update(DT, p, BOUNDS)
            self.assertEqual(m.state, "windup", name)
            self.assertEqual(p.damage_taken, 0, name)
