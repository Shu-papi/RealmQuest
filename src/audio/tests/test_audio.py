"""
Checks the audio system: the sound FILES are sound, every sound the game asks for exists, the manager copes with a
busy fight (spam limits, crossfades, ducking, no sound card) and the Lich King and the skeletons play the right
sound at the right moment.

No sound device is needed: a pretend mixer stands in for pygame's.

Run from the repo root:  python -m unittest discover -s src/audio/tests
"""
import ast
import os
import sys
import tempfile
import unittest
import wave

SRC_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

try:
    import pygame
except ImportError:                       # the boss tests ship a tiny fake pygame
    sys.path.insert(0, os.path.join(SRC_DIR, "bosses", "tests"))
    from pygame_stub import install
    install()
    import pygame

import audio                                                              # noqa: E402
from audio import manager as manager_module, sounds                       # noqa: E402
from audio.manager import AudioManager, pan_gains                         # noqa: E402
from audio.paths import MUSIC_DIR, SFX_DIR                                # noqa: E402
from audio.testing import Recorder                                        # noqa: E402
from bosses import LichKing                                               # noqa: E402
from bosses.dev.arena import BOUNDS                                       # noqa: E402
from bosses.lich_king import boss as boss_module                          # noqa: E402
from bosses.lich_king.boss import EXHAUST_BONUS, PHASE_STATS              # noqa: E402
from bosses.lich_king.drain_circle import DrainCircle, SoulRain           # noqa: E402
from bosses.lich_king.grasping_hand import GraspingHand                   # noqa: E402
from monsters import spawn_monster                                        # noqa: E402

DT = 1 / 60


def sfx_files():
    return sorted(f for f in os.listdir(SFX_DIR) if f.endswith(".wav"))


def music_files():
    return sorted(f for f in os.listdir(MUSIC_DIR) if f.endswith(".wav"))


def sfx_names_on_disk():
    names = set()
    for filename in sfx_files():
        stem = filename[:-4]
        names.add(stem.split("__v")[0])
    return names


def read_samples(path):
    with wave.open(path, "rb") as handle:
        info = (handle.getnchannels(), handle.getsampwidth(), handle.getframerate(), handle.getnframes())
        raw = handle.readframes(handle.getnframes())
    count = len(raw) // 2
    values = [int.from_bytes(raw[i * 2:i * 2 + 2], "little", signed=True) for i in range(count)]
    return info, values


# ----------------------------------------------------------------------------------------------------------
# the files
# ----------------------------------------------------------------------------------------------------------

class TestSoundFiles(unittest.TestCase):
    def test_every_file_is_a_clean_mono_16_bit_wav(self):
        for folder, names in ((SFX_DIR, sfx_files()), (MUSIC_DIR, music_files())):
            for filename in names:
                with self.subTest(file=filename):
                    (channels, width, rate, frames), values = read_samples(os.path.join(folder, filename))
                    self.assertEqual((channels, width, rate), (1, 2, 22050))
                    self.assertGreater(frames, 0)
                    peak = max(abs(v) for v in values)
                    self.assertGreater(peak, 6000, "this file is (nearly) silent")
                    self.assertLess(peak, 32767, "this file clips")

    def test_sound_effects_are_short_and_music_is_a_proper_loop_length(self):
        for filename in sfx_files():
            (_, _, rate, frames), _ = read_samples(os.path.join(SFX_DIR, filename))
            with self.subTest(file=filename):
                self.assertLess(frames / rate, 8.0)
        for filename in music_files():
            (_, _, rate, frames), _ = read_samples(os.path.join(MUSIC_DIR, filename))
            with self.subTest(file=filename):
                self.assertGreater(frames / rate, 10.0)

    def test_loops_do_not_click_where_they_wrap_round(self):
        """The jump across the loop point must look like any other step in the wave (no click)."""
        loops = [os.path.join(MUSIC_DIR, f) for f in music_files()] + [os.path.join(SFX_DIR, "ward_hum.wav")]
        for path in loops:
            _, values = read_samples(path)
            steps = sorted(abs(b - a) for a, b in zip(values, values[1:]))
            biggest_normal = steps[int(len(steps) * 0.995)]
            seam = abs(values[0] - values[-1])
            with self.subTest(file=os.path.basename(path)):
                self.assertLessEqual(seam, biggest_normal * 1.6 + 200)

    def test_sounds_with_variants_have_consecutive_numbers(self):
        groups = {}
        for filename in sfx_files():
            stem = filename[:-4]
            if "__v" in stem:
                name, number = stem.split("__v")
                groups.setdefault(name, []).append(int(number))
        for name, numbers in groups.items():
            with self.subTest(sound=name):
                self.assertEqual(sorted(numbers), list(range(1, len(numbers) + 1)))
                self.assertGreater(len(numbers), 1)

    def test_every_mixer_entry_has_a_file(self):
        on_disk = sfx_names_on_disk()
        for name in list(sounds.SOUNDS) + list(sounds.LOOPS):
            with self.subTest(sound=name):
                self.assertIn(name, on_disk)
        for track in sounds.MUSIC:
            with self.subTest(track=track):
                self.assertTrue(os.path.exists(os.path.join(MUSIC_DIR, track + ".wav")))

    def test_every_sound_file_has_a_mixer_entry(self):
        """A file nobody tuned would play at the default volume: list them so none sneak in by accident."""
        for name in sfx_names_on_disk():
            with self.subTest(sound=name):
                self.assertIn(name, sounds.SOUNDS if name not in sounds.LOOPS else sounds.LOOPS)

    def test_mixer_numbers_make_sense(self):
        for name, entry in sounds.SOUNDS.items():
            with self.subTest(sound=name):
                self.assertTrue(0 < entry["gain"] <= 1.0)
                self.assertGreaterEqual(entry["cooldown"], 0)
                self.assertGreaterEqual(entry["voices"], 1)
                self.assertIn(entry["priority"], (0, 1, 2, 3))
                if entry["duck"]:
                    amount, seconds = entry["duck"]
                    self.assertTrue(0 < amount <= 1.0 and seconds > 0)


# ----------------------------------------------------------------------------------------------------------
# every sound the code asks for is real (catches typos in rarely-run code)
# ----------------------------------------------------------------------------------------------------------

def asked_for_sounds():
    """(file, line, kind, name) for every literal sound name used by the game's code."""
    found = []
    for root, dirs, files in os.walk(SRC_DIR):
        dirs[:] = [d for d in dirs if d not in ("__pycache__", "tests", "dev")]
        if os.path.basename(root) == "audio":
            continue
        for filename in files:
            if not filename.endswith(".py"):
                continue
            path = os.path.join(root, filename)
            with open(path, encoding="utf-8") as handle:
                tree = ast.parse(handle.read(), path)
            for node in ast.walk(tree):
                if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) \
                        and isinstance(node.func.value, ast.Name) and node.func.value.id == "audio" \
                        and node.func.attr in ("play", "loop", "music") and node.args:
                    first = node.args[0]
                    if isinstance(first, ast.Constant) and isinstance(first.value, str):
                        found.append((path, node.lineno, node.func.attr, first.value))
                elif isinstance(node, ast.Assign) and len(node.targets) == 1 \
                        and isinstance(node.targets[0], ast.Name) and node.targets[0].id.startswith("SFX_") \
                        and isinstance(node.value, ast.Constant) and isinstance(node.value.value, str):
                    found.append((path, node.lineno, "play", node.value.value))
    return found


class TestTheCodeAsksForRealSounds(unittest.TestCase):
    def test_the_scan_finds_the_calls(self):
        self.assertGreater(len(asked_for_sounds()), 25)

    def test_every_sound_named_in_the_code_has_a_file(self):
        on_disk = sfx_names_on_disk()
        for path, line, kind, name in asked_for_sounds():
            where = f"{os.path.relpath(path, SRC_DIR)}:{line}"
            with self.subTest(where=where, sound=name):
                if kind == "music":
                    self.assertTrue(os.path.exists(os.path.join(MUSIC_DIR, name + ".wav")), where)
                else:
                    self.assertIn(name, on_disk, where)

    def test_every_lich_king_attack_has_a_windup_sound(self):
        on_disk = sfx_names_on_disk()
        for phase, stats in PHASE_STATS.items():
            for key in stats:
                if key.endswith("_windup"):
                    with self.subTest(phase=phase, attack=key):
                        self.assertIn(key, on_disk)

    def test_the_music_for_every_phase_exists(self):
        for phase in (1, 2, 3):
            self.assertTrue(os.path.exists(os.path.join(MUSIC_DIR, f"lich_p{phase}.wav")))


# ----------------------------------------------------------------------------------------------------------
# the manager, with a pretend mixer
# ----------------------------------------------------------------------------------------------------------

class FakeSound:
    def __init__(self, path):
        if not os.path.exists(path) or os.path.isdir(path):
            raise FileNotFoundError(path)
        self.path = path


class FakeChannel:
    def __init__(self, index):
        self.index = index
        self.sound = None
        self.busy = False
        self.volume = (1.0, 1.0)
        self.loops = 0
        self.fadeouts = []
        self.plays = 0

    def play(self, sound, loops=0, **_):
        self.sound, self.busy, self.loops, self.volume = sound, True, loops, (1.0, 1.0)
        self.plays += 1

    def set_volume(self, left, right=None):
        self.volume = (left, left if right is None else right)

    def get_busy(self):
        return self.busy

    def get_sound(self):
        return self.sound

    def stop(self):
        self.busy, self.sound = False, None

    def fadeout(self, ms):
        self.fadeouts.append(ms)
        self.busy = False


class FakeMixer:
    def __init__(self, available=True):
        self.available = available
        self.inited = False
        self.channels = {}
        self.reserved = 0
        self.count = 0

    def get_init(self):
        return (22050, -16, 2) if self.inited else None

    def pre_init(self, *args):
        pass

    def init(self):
        if not self.available:
            raise RuntimeError("no sound card")
        self.inited = True

    def set_num_channels(self, n):
        self.count = n

    def set_reserved(self, n):
        self.reserved = n

    def Channel(self, index):
        return self.channels.setdefault(index, FakeChannel(index))

    Sound = staticmethod(FakeSound)

    def find_channel(self, force=False):
        for i in range(self.reserved, self.count):
            if not self.Channel(i).busy:
                return self.Channel(i)
        return self.Channel(self.reserved) if force else None


class FakePygame:
    def __init__(self, available=True):
        self.mixer = FakeMixer(available)


class Clock:
    def __init__(self):
        self.now = 1000.0

    def __call__(self):
        return self.now


class Settings:
    def __init__(self, sfx, music):
        self.values = {"sfx": sfx, "music": music}

    def effective_volume(self, kind):
        return self.values[kind]


def real_manager(available=True):
    clock = Clock()
    pg = FakePygame(available)
    manager = AudioManager(pg, SFX_DIR, MUSIC_DIR, clock)
    return manager, pg, clock


class TestManager(unittest.TestCase):
    def test_no_sound_card_means_silence_not_a_crash(self):
        manager, _, _ = real_manager(available=False)
        self.assertFalse(manager.init())
        self.assertFalse(manager.play("boss_hit"))
        self.assertFalse(manager.play_music("lich_p1"))
        manager.loop("ward_hum", True)
        manager.stop_all()
        self.assertFalse(audio.init(pygame_module=FakePygame(available=False)))
        audio.play("boss_hit")                                      # the module-level calls are harmless too
        audio.music("lich_p1")
        audio.stop_all()

    def test_every_sound_file_loads(self):
        manager, _, _ = real_manager()
        self.assertTrue(manager.init())
        self.assertEqual(manager.warnings, [])
        self.assertEqual(set(manager.sounds), sfx_names_on_disk())
        self.assertGreater(len(manager.sounds["bone_hit"]), 1)      # the variants were grouped under one name

    def test_a_broken_file_is_skipped_not_fatal(self):
        with tempfile.TemporaryDirectory() as folder:
            open(os.path.join(folder, "good.wav"), "w").close()
            os.mkdir(os.path.join(folder, "bad.wav"))               # cannot be opened as a file
            manager = AudioManager(FakePygame(), folder, folder, Clock())
            self.assertTrue(manager.init())
            self.assertIn("good", manager.sounds)
            self.assertTrue(manager.warnings)

    def test_variants_are_random_but_never_the_same_one_twice_in_a_row(self):
        manager, pg, clock = real_manager()
        manager.init()
        picks = []
        for _ in range(30):
            clock.now += 1.0
            self.assertTrue(manager.play("bone_hit"))
            picks.append(next(c.sound.path for c in pg.mixer.channels.values() if c.busy and c.index >= 4))
            for c in pg.mixer.channels.values():
                c.stop()
        self.assertGreater(len(set(picks)), 1)
        self.assertTrue(all(a != b for a, b in zip(picks, picks[1:])))

    def test_the_same_sound_cannot_machine_gun(self):
        manager, _, clock = real_manager()
        manager.init()
        self.assertTrue(manager.play("boss_hit"))
        self.assertFalse(manager.play("boss_hit"))                  # same instant
        clock.now += 0.06
        self.assertTrue(manager.play("boss_hit"))

    def test_only_so_many_copies_play_at_once(self):
        manager, _, clock = real_manager()
        manager.init()
        limit = sounds.spec("boss_hit")["voices"]
        for _ in range(limit):
            clock.now += 0.06
            self.assertTrue(manager.play("boss_hit"))
        clock.now += 0.06
        self.assertFalse(manager.play("boss_hit"))

    def test_spam_is_dropped_but_important_sounds_are_not(self):
        manager, _, clock = real_manager()
        manager.init()
        spam = [n for n, e in sounds.SOUNDS.items() if e["priority"] == 0]
        self.assertGreater(len(spam), manager_module.BURST_LIMIT)
        started = sum(1 for name in spam if manager.play(name))
        self.assertEqual(started, manager_module.BURST_LIMIT)       # a storm is thinned out...
        self.assertTrue(manager.play("bone_hit"))                   # ...but normal sounds still get through
        self.assertTrue(manager.play("ward_break"))                 # ...and so do the big ones

    def test_an_important_sound_replaces_its_own_old_copy_instead_of_being_dropped(self):
        manager, pg, clock = real_manager()
        manager.init()
        self.assertTrue(manager.play("roar_phase2"))
        clock.now += 0.1
        self.assertTrue(manager.play("roar_phase2"))
        self.assertEqual(sum(1 for c in pg.mixer.channels.values() if c.busy and c.index >= 4), 1)

    def test_a_full_mixer_drops_normal_sounds_and_steals_for_important_ones(self):
        manager, pg, clock = real_manager()
        manager.init()
        for i in range(manager_module.RESERVED, manager_module.RESERVED + manager_module.SFX_CHANNELS):
            pg.mixer.Channel(i).busy = True
        self.assertFalse(manager.play("bone_hit"))
        self.assertTrue(manager.play("ward_break"))

    def test_sounds_pan_with_the_screen_position(self):
        self.assertEqual(pan_gains(None), (1.0, 1.0))
        self.assertEqual(pan_gains(480), (1.0, 1.0))
        left, right = pan_gains(0)
        self.assertEqual(left, 1.0)
        self.assertLess(right, 0.5)
        left, right = pan_gains(960)
        self.assertLess(left, 0.5)
        self.assertEqual(right, 1.0)
        self.assertEqual(pan_gains(5000), pan_gains(960))
        manager, pg, _ = real_manager()
        manager.init()
        manager.play("boss_hit", x=900)
        channel = next(c for c in pg.mixer.channels.values() if c.busy)
        self.assertLess(channel.volume[0], channel.volume[1])

    def test_volume_follows_the_players_sliders(self):
        manager, pg, clock = real_manager()
        manager.init()
        manager.apply_settings(Settings(sfx=0.5, music=0.25))
        manager.play("boss_hit")
        channel = next(c for c in pg.mixer.channels.values() if c.busy)
        self.assertAlmostEqual(channel.volume[0], sounds.spec("boss_hit")["gain"] * 0.5)
        manager.play_music("lich_p1", fade=0.5)
        clock.now += 1.0
        manager.tick()
        music = pg.mixer.Channel(0)
        self.assertAlmostEqual(music.volume[0], sounds.MUSIC["lich_p1"] * 0.25, places=3)

    def test_mute_silences_everything_and_unmute_brings_the_music_back(self):
        manager, pg, clock = real_manager()
        manager.init()
        manager.play_music("lich_p1", fade=0.5)
        clock.now += 1.0
        manager.tick()
        manager.set_muted(True)
        self.assertFalse(manager.play("boss_hit"))
        self.assertEqual(pg.mixer.Channel(0).volume[0], 0.0)
        manager.set_muted(False)
        self.assertGreater(pg.mixer.Channel(0).volume[0], 0.0)
        self.assertTrue(pg.mixer.Channel(0).busy)

    def test_a_charge_up_can_be_cut_off_when_the_attack_fires(self):
        manager, pg, clock = real_manager()
        manager.init()
        manager.play("volley_windup", max_seconds=0.5)
        channel = next(c for c in pg.mixer.channels.values() if c.busy)
        clock.now += 0.4
        manager.tick()
        self.assertEqual(channel.fadeouts, [])
        clock.now += 0.2
        manager.tick()
        self.assertEqual(channel.fadeouts, [manager_module.CUT_FADE_MS])

    def test_music_loops_and_crossfades_between_phases(self):
        manager, pg, clock = real_manager()
        manager.init()
        self.assertTrue(manager.play_music("lich_p1", fade=1.0))
        first = pg.mixer.Channel(0)
        self.assertEqual(first.loops, -1)
        self.assertEqual(first.volume[0], 0.0)                      # fades IN
        clock.now += 1.0
        manager.tick()
        self.assertAlmostEqual(first.volume[0], sounds.MUSIC["lich_p1"], places=3)
        manager.play_music("lich_p1")                               # asking again does nothing
        self.assertEqual(first.plays, 1)
        manager.play_music("lich_p2", fade=1.0)
        second = pg.mixer.Channel(1)
        self.assertEqual(second.loops, -1)
        clock.now += 0.5
        manager.tick()
        self.assertTrue(first.busy and second.busy)                 # both audible mid-crossfade
        self.assertLess(first.volume[0], sounds.MUSIC["lich_p1"])
        self.assertGreater(second.volume[0], 0.0)
        clock.now += 0.6
        manager.tick()
        self.assertFalse(first.busy)                                # the old track stops once it has faded out
        self.assertTrue(second.busy)
        manager.play_music("lich_p3", fade=0.5)                     # and the freed channel is reused
        self.assertTrue(first.busy)

    def test_stop_music_fades_out(self):
        manager, pg, clock = real_manager()
        manager.init()
        manager.play_music("lich_p1", fade=0.1)
        clock.now += 1.0
        manager.tick()
        manager.stop_music(fade=1.0)
        clock.now += 0.5
        manager.tick()
        self.assertTrue(pg.mixer.Channel(0).busy)
        clock.now += 0.6
        manager.tick()
        self.assertFalse(pg.mixer.Channel(0).busy)
        self.assertIsNone(manager.current_music)

    def test_an_unknown_track_is_ignored(self):
        manager, _, _ = real_manager()
        manager.init()
        self.assertFalse(manager.play_music("no_such_track"))

    def test_a_looping_sound_follows_a_condition(self):
        manager, pg, clock = real_manager()
        manager.init()
        for _ in range(5):
            manager.loop("ward_hum", True)                          # called every frame: only the first one acts
        channel = pg.mixer.Channel(2)
        self.assertEqual((channel.loops, channel.plays), (-1, 1))
        clock.now += 1.0
        manager.loop("ward_hum", True)
        self.assertGreater(channel.volume[0], 0.0)
        manager.loop("ward_hum", False)
        clock.now += 1.0
        manager.loop("ward_hum", False)
        self.assertFalse(channel.busy)
        manager.loop("ward_hum", True)                              # and it can come back
        self.assertTrue(channel.busy)

    def test_a_flood_of_sounds_never_steals_the_music_channel(self):
        manager, pg, clock = real_manager()
        manager.init()
        manager.play_music("lich_p1", fade=0.1)
        clock.now += 1.0
        manager.tick()
        for i in range(80):                                   # far more sounds than there are channels
            clock.now += 0.01
            manager.play("roar_phase2" if i % 7 == 0 else "bone_hit")
            manager.play("lich_death")
        self.assertTrue(manager.channels[0].get_busy())

    def test_big_sounds_duck_the_music_and_it_comes_back(self):
        manager, pg, clock = real_manager()
        manager.init()
        manager.play_music("lich_p1", fade=0.1)
        clock.now += 1.0
        manager.tick()
        full = pg.mixer.Channel(0).volume[0]
        manager.play("roar_phase2")
        for _ in range(3):
            clock.now += 0.1
            manager.tick()
        self.assertLess(pg.mixer.Channel(0).volume[0], full * 0.85)
        for _ in range(60):
            clock.now += 0.1
            manager.tick()
        self.assertAlmostEqual(pg.mixer.Channel(0).volume[0], full, places=3)

    def test_stop_all_silences_everything(self):
        manager, pg, clock = real_manager()
        manager.init()
        manager.play_music("lich_p1", fade=0.1)
        manager.loop("ward_hum", True)
        manager.play("boss_hit")
        manager.stop_all(fade=0.0)
        self.assertFalse(any(c.busy for c in pg.mixer.channels.values()))
        self.assertEqual((manager.music_faders, manager.loop_faders), ({}, {}))

    def test_the_module_functions_work_through_a_real_init(self):
        try:
            self.assertTrue(audio.init(Settings(1.0, 1.0), FakePygame()))
            self.assertTrue(audio.is_ready())
            self.assertTrue(audio.play("boss_hit"))
            self.assertTrue(audio.music("lich_p1"))
            self.assertTrue(audio.toggle_muted())
            self.assertFalse(audio.toggle_muted())
        finally:
            audio.shutdown()
        self.assertFalse(audio.is_ready())
        self.assertFalse(audio.play("boss_hit"))


# ----------------------------------------------------------------------------------------------------------
# the Lich King plays the right sounds
# ----------------------------------------------------------------------------------------------------------

class StubPlayer:
    def __init__(self, x=480, y=500):
        self.rect = pygame.Rect(0, 0, 28, 28)
        self.rect.center = (x, y)
        self.hits = 0

    def take_damage(self, amount):
        self.hits += 1
        return amount


class RootablePlayer(StubPlayer):
    def apply_status(self, name, seconds):
        return True


class ImmunePlayer(RootablePlayer):
    def apply_status(self, name, seconds):
        return False


def advance(boss, player, seconds):
    for _ in range(int(seconds / DT)):
        boss.update(DT, player, BOUNDS)


def phase_boss(phase, player):
    boss = LichKing(seed=1)
    advance(boss, player, LichKing.INTRO_TIME + 0.1)
    if phase >= 2:
        boss.debug_set_hp_percent(0.5)
        advance(boss, player, boss.TRANSITION_TIME + 0.1)
    if phase >= 3:
        boss.debug_set_hp_percent(boss.PHASE_3_HP)
        advance(boss, player, boss.TRANSITION_TIME + 0.1)
    boss.force_next = None
    boss.state, boss.cooldown = "idle", 99.0
    return boss


class RecorderCase(unittest.TestCase):
    def setUp(self):
        self.rec = Recorder()
        audio.set_manager(self.rec)

    def tearDown(self):
        audio.set_manager(None)


class TestLichKingSounds(RecorderCase):
    def test_he_rises_to_the_sound_of_the_crypt_and_phase_one_music_starts(self):
        boss = LichKing(seed=1)
        advance(boss, StubPlayer(), 0.1)
        self.assertIn("lich_intro", self.rec.names())
        self.assertEqual(self.rec.tracks(), ["lich_p1"])
        advance(boss, StubPlayer(), 1.0)
        self.assertEqual(self.rec.count("lich_intro"), 1)           # only once

    def test_every_attack_announces_itself_and_the_warning_ends_when_the_attack_fires(self):
        player = StubPlayer()
        for attack in ("volley", "drain", "rain", "summon", "nova", "grasp", "barrage"):
            for phase in (1, 2, 3):
                if phase == 1 and attack in ("nova", "grasp", "barrage", "summon"):
                    continue
                with self.subTest(attack=attack, phase=phase):
                    self.rec.clear()
                    boss = phase_boss(phase, player)
                    self.rec.clear()
                    boss._begin_attack(attack, player, BOUNDS)
                    play = [e for e in self.rec.events if e[0] == "play" and e[1] == f"{attack}_windup"]
                    self.assertEqual(len(play), 1)
                    self.assertAlmostEqual(play[0][3], PHASE_STATS[phase][f"{attack}_windup"])

    def test_the_release_sounds_are_played_when_the_attacks_fire(self):
        player = StubPlayer()
        boss = phase_boss(2, player)
        boss.minions = []
        for attack, release in (("nova", "nova_blast"), ("summon", "summon_rise")):
            with self.subTest(attack=attack):
                self.rec.clear()
                boss._begin_attack(attack, player, BOUNDS)
                advance(boss, player, boss.windup_time + 0.1)
                self.assertEqual(self.rec.count(release), 1)

    def test_shots_are_explosions_not_zaps(self):
        """A volley is ONE blast, a barrage opens with one big blast then a thud per shot (no blips, no pings)."""
        player = StubPlayer()
        boss = phase_boss(3, player)
        boss.minions = []
        boss._begin_attack("volley", player, BOUNDS)
        advance(boss, player, boss.windup_time + 0.05)
        self.assertEqual(self.rec.count("volley_fire"), 1)
        boss = phase_boss(3, player)
        self.rec.clear()
        boss._begin_attack("barrage", player, BOUNDS)
        advance(boss, player, 4.0)
        self.assertEqual(self.rec.count("barrage_blast"), 1)
        self.assertEqual(self.rec.count("barrage_bolt"), PHASE_STATS[3]["barrage_bolts"])

    def test_the_phase_three_nova_booms_twice(self):
        player = StubPlayer()
        boss = phase_boss(3, player)
        self.rec.clear()
        boss._begin_attack("nova", player, BOUNDS)
        advance(boss, player, 3.0)
        self.assertEqual(self.rec.count("nova_blast"), 2)

    def test_phase_changes_roar_and_the_music_gets_angrier(self):
        player = StubPlayer()
        boss = phase_boss(1, player)
        self.rec.clear()
        boss.debug_set_hp_percent(0.5)
        self.assertEqual((self.rec.count("roar_phase2"), self.rec.tracks()), (1, ["lich_p2"]))
        advance(boss, player, boss.TRANSITION_TIME + 0.1)
        boss.debug_set_hp_percent(boss.PHASE_3_HP)
        self.assertEqual((self.rec.count("roar_phase3"), self.rec.tracks()), (1, ["lich_p2", "lich_p3"]))

    def test_hits_sound_different_when_he_is_open(self):
        player = StubPlayer()
        boss = phase_boss(1, player)
        self.rec.clear()
        boss.take_damage(20)
        self.assertEqual(self.rec.names(), ["boss_hit"])
        boss.set_state("exhausted")
        self.assertIn("exhaust_open", self.rec.names())             # the gong
        self.rec.clear()
        boss.take_damage(20)
        self.assertEqual(self.rec.names(), ["boss_hit_open"])

    def test_no_hit_sound_when_nothing_was_hurt(self):
        boss = LichKing(seed=1)
        self.rec.clear()
        boss.take_damage(20)                                        # still rising: can't be hurt
        self.assertNotIn("boss_hit", self.rec.names())

    def test_the_soul_ward_hums_deflects_and_shatters(self):
        player = StubPlayer()
        boss = phase_boss(3, player)
        boss.minions = [boss_module.spawn_monster("skeleton_warrior", 200 + 60 * i, 300, spawn=False) for i in range(3)]
        self.rec.clear()
        advance(boss, player, 0.1)
        self.assertEqual(self.rec.count("ward_up"), 1)
        self.assertTrue(self.rec.loops["ward_hum"])
        self.assertEqual(boss.take_damage(50), 0)
        self.assertEqual(self.rec.count("ward_deflect"), 1)
        self.assertEqual(self.rec.count("boss_hit"), 0)
        for m in boss.minions:
            m.kill()
        advance(boss, player, 0.1)
        self.assertEqual(self.rec.count("ward_break"), 1)
        self.assertFalse(self.rec.loops["ward_hum"])
        self.rec.clear()
        boss.take_damage(20)
        self.assertEqual(self.rec.names(), ["boss_hit_open"])       # the stun window is audible too

    def test_the_ward_up_sound_is_not_played_every_frame(self):
        player = StubPlayer()
        boss = phase_boss(3, player)
        boss.minions = [boss_module.spawn_monster("skeleton_warrior", 300, 300, spawn=False)]
        self.rec.clear()
        advance(boss, player, 1.0)
        self.assertEqual(self.rec.count("ward_up"), 1)

    def test_teleporting_makes_a_sound_going_and_coming(self):
        player = StubPlayer()
        boss = phase_boss(2, player)
        self.rec.clear()
        boss.set_state("teleport_out")
        advance(boss, player, 1.0)
        self.assertEqual((self.rec.count("teleport_out"), self.rec.count("teleport_in")), (1, 1))

    def test_death_fades_the_music_and_ends_with_the_victory_sting(self):
        player = StubPlayer()
        boss = phase_boss(2, player)
        self.rec.clear()
        boss.take_damage(10 ** 6)
        self.assertEqual(self.rec.count("lich_death"), 1)
        self.assertIn(("stop_music",), self.rec.events)
        self.assertEqual(self.rec.count("victory_sting"), 0)        # not yet: he is still dissolving
        advance(boss, player, boss.DYING_TIME + 0.2)
        self.assertEqual(self.rec.count("victory_sting"), 1)
        advance(boss, player, 2.0)
        self.assertEqual(self.rec.count("victory_sting"), 1)

    def test_drain_circles_and_soul_rain_burst_with_their_own_sounds(self):
        player = StubPlayer(100, 100)
        circle = DrainCircle(100, 100, 85, 0.1, 18)
        rain = SoulRain(100, 100, 58, 0.1, 14)
        for hazard in (circle, rain):
            for _ in range(10):
                hazard.update(DT, player)
        self.assertEqual(self.rec.names(), ["drain_burst", "rain_burst"])

    def test_the_hands_burst_and_clamp_only_when_they_really_root_you(self):
        for player_class, expected in ((RootablePlayer, ["grasp_burst", "grasp_root"]),
                                       (ImmunePlayer, ["grasp_burst"]), (StubPlayer, ["grasp_burst"])):
            with self.subTest(player=player_class.__name__):
                self.rec.clear()
                hand = GraspingHand(100, 100, 42, 0.1, 12, 1.0)
                player = player_class(100, 100)
                for _ in range(10):
                    hand.update(DT, player)
                self.assertEqual(self.rec.names(), expected)

    def test_draining_you_heals_him_with_a_sound(self):
        player = StubPlayer()
        boss = phase_boss(1, player)
        self.rec.clear()
        boss.on_hazard_hit(DrainCircle(1, 1, 1, 1, 1))
        self.assertEqual(self.rec.names(), ["drain_heal"])
        self.rec.clear()
        boss.on_hazard_hit(SoulRain(1, 1, 1, 1, 1))
        self.assertEqual(self.rec.names(), [])

    def test_a_whole_fight_plays_without_ever_raising_an_error(self):
        player = StubPlayer()
        boss = LichKing(seed=3)
        for step in range(int(40 / DT)):
            if step % 20 == 0:
                for target in boss.hittables():
                    target.take_damage(60)
            boss.update(DT, player, BOUNDS)
        self.assertGreater(len(self.rec.names()), 40)
        self.assertGreater(boss.phase, 1)
        self.assertEqual(self.rec.tracks()[0], "lich_p1")


# ----------------------------------------------------------------------------------------------------------
# skeletons play sounds in every area, not just in the boss fight
# ----------------------------------------------------------------------------------------------------------

class TestMonsterSounds(RecorderCase):
    def run_until(self, monster, player, wanted, seconds=8.0):
        for _ in range(int(seconds / DT)):
            monster.update(DT, player, BOUNDS)
            if all(name in self.rec.names() for name in wanted):
                return True
        return False

    def test_rising_from_the_ground_makes_a_sound_but_appearing_instantly_does_not(self):
        spawn_monster("skeleton_warrior", 300, 300)
        self.assertEqual(self.rec.names(), ["monster_spawn"])
        self.rec.clear()
        spawn_monster("skeleton_warrior", 300, 300, spawn=False)
        self.assertEqual(self.rec.names(), [])

    def test_being_hit_and_falling_apart(self):
        for name, hurt, die in (("skeleton_warrior", "bone_hit", "bone_shatter"),
                                ("skeleton_archer", "bone_hit", "bone_shatter"),
                                ("skeleton_acolyte", "bone_hit", "bone_shatter"),
                                ("skeleton_brute", "brute_hit", "brute_shatter")):
            with self.subTest(monster=name):
                monster = spawn_monster(name, 300, 300, spawn=False)
                self.rec.clear()
                monster.take_damage(1)
                self.assertEqual(self.rec.names(), [hurt])
                self.rec.clear()
                monster.take_damage(10 ** 6)
                self.assertEqual(self.rec.names(), [die])           # the killing blow is only the shatter

    def test_a_boss_killing_its_army_makes_every_one_shatter(self):
        army = [spawn_monster("skeleton_warrior", 100 + 50 * i, 300, spawn=False) for i in range(4)]
        self.rec.clear()
        for m in army:
            m.kill()
        self.assertEqual(self.rec.names(), ["bone_shatter"] * 4)

    def test_a_dead_monster_is_silent_when_hit_again(self):
        monster = spawn_monster("skeleton_warrior", 300, 300, spawn=False)
        monster.take_damage(10 ** 6)
        self.rec.clear()
        monster.take_damage(5)
        self.assertEqual(self.rec.names(), [])

    def test_the_warrior_rattles_then_swings(self):
        monster = spawn_monster("skeleton_warrior", 480, 300, spawn=False)
        self.rec.clear()
        self.assertTrue(self.run_until(monster, StubPlayer(480, 330), ["skeleton_windup", "sword_swish"]))
        names = self.rec.names()
        self.assertLess(names.index("skeleton_windup"), names.index("sword_swish"))

    def test_the_archer_draws_then_shoots(self):
        monster = spawn_monster("skeleton_archer", 200, 300, spawn=False)
        self.rec.clear()
        self.assertTrue(self.run_until(monster, StubPlayer(600, 330), ["bow_draw", "arrow_shoot"]))

    def test_the_brute_has_a_big_slam_and_a_quick_backhand(self):
        monster = spawn_monster("skeleton_brute", 480, 300, spawn=False)
        self.rec.clear()
        self.assertTrue(self.run_until(monster, StubPlayer(480, 340), ["brute_windup"]))
        self.assertTrue(self.run_until(monster, StubPlayer(480, 340), ["brute_slam"] , 12.0)
                        or "brute_swipe" in self.rec.names())

    def test_the_acolytes_healing_and_raising_each_have_a_sound(self):
        for action, expected in (("mend", "acolyte_mend"), ("raise", "acolyte_raise")):
            with self.subTest(action=action):
                acolyte = spawn_monster("skeleton_acolyte", 300, 300, spawn=False)
                friend = spawn_monster("skeleton_warrior", 340, 300, spawn=False)
                friend.hp = 1
                acolyte.action, acolyte.target = action, friend
                acolyte.raise_spot = (300, 340)
                acolyte.aim = 0.0
                self.rec.clear()
                acolyte._cast()
                expected_all = [expected] + (["monster_spawn"] if action == "raise" else [])   # the raised dead claw out too
                self.assertEqual(self.rec.names(), expected_all)

    def test_a_new_monster_gets_sounds_for_free_and_can_choose_its_own(self):
        from monsters.base_monster import Monster

        class Ghoul(Monster):
            NAME = "skeleton_warrior"                               # (borrows a real sprite sheet)
            SFX_HURT = "brute_hit"

            def think(self, dt, player, bounds):
                pass

        ghoul = Ghoul(300, 300, spawn=False)
        self.rec.clear()
        ghoul.take_damage(1)
        ghoul.take_damage(10 ** 6)
        self.assertEqual(self.rec.names(), ["brute_hit", "bone_shatter"])


if __name__ == "__main__":
    unittest.main()
