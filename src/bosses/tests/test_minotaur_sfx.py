"""
Minotaur sound-effect checks. Run from the repo root:  python -m unittest discover -s src/bosses/tests

No speakers needed: the files are checked as data, the SoundBoard is run against a fake mixer, and the boss and
arena are given a recorder instead of a real sound board, so each test can say exactly which sound should have
played, and when.
"""
import os as _os; _os.environ["REALMQUEST_BALANCE"] = "none"      # these tests pin the code's DEFAULT numbers, not your config/ tuning
import importlib.util
import os
import sys
import tempfile
import types
import unittest
import wave
from unittest import mock

SRC_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
ROOT_DIR = os.path.dirname(SRC_DIR)
if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

try:
    import pygame
except ImportError:
    from pygame_stub import install
    install()
    import pygame

from bosses import Minotaur
from bosses.minotaur import sfx as minotaur_sfx
from bosses.minotaur.boss import PHASE_STATS, STATE_SOUNDS
from bosses.minotaur.sfx import SFX_DIR, SOUND_NAMES, VOLUMES, SoundBoard

REAL_PYGAME = hasattr(pygame, "get_sdl_version")
needs_pygame = unittest.skipUnless(REAL_PYGAME, "needs real pygame (pip install pygame-ce)")

DT = 1 / 60
BOUNDS = (40, 110, 920, 600)


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

class Recorder:
    """Stands in for the SoundBoard and remembers what was asked of it."""

    def __init__(self):
        self.calls = []            # (name, volume, screen_x)
        self.stopped = 0
        self.muted = False

    def play(self, name, volume=1.0, x=None):
        self.calls.append((name, volume, x))

    def names(self):
        return [call[0] for call in self.calls]

    def stop_all(self):
        self.stopped += 1

    def set_paused(self, paused):
        pass

    def toggle_mute(self):
        self.muted = not self.muted
        return self.muted


class StubPlayer:
    def __init__(self, x=480, y=500):
        self.rect = pygame.Rect(0, 0, 28, 28)
        self.rect.center = (x, y)
        self.damage_taken = 0

    def take_damage(self, amount):
        self.damage_taken += amount
        return amount


def advance(boss, player, seconds):
    for _ in range(int(seconds / DT)):
        boss.update(DT, player, BOUNDS)


def recorded_boss(seed=1):
    boss = Minotaur(seed=seed)
    boss.sfx = Recorder()
    return boss


def idle_boss(seed=1):
    """Past the intro, with no new skills starting on their own, so a test sees only what it started."""
    boss = recorded_boss(seed)
    advance(boss, StubPlayer(), Minotaur.INTRO_TIME + 0.1)
    boss._start_attack = lambda name: None
    boss.sfx.calls.clear()
    return boss


# ---------------------------------------------------------------------------
# the sound files
# ---------------------------------------------------------------------------

class SoundFileTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        path = os.path.join(ROOT_DIR, "tools", "build_minotaur_sfx.py")
        spec = importlib.util.spec_from_file_location("build_minotaur_sfx", path)
        cls.tool = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.tool)

    def test_the_generator_and_the_game_agree_on_the_names(self):
        self.assertEqual(set(self.tool.RECIPES), set(SOUND_NAMES))

    def test_every_sound_has_all_its_files(self):
        for name in SOUND_NAMES:
            for fname in self.tool.file_names(name):
                self.assertTrue(os.path.isfile(os.path.join(SFX_DIR, fname)), f"missing {fname}")

    def test_files_are_clean_short_mono_16_bit_audio(self):
        for name in SOUND_NAMES:
            for fname in self.tool.file_names(name):
                with wave.open(os.path.join(SFX_DIR, fname), "rb") as wav:
                    self.assertEqual((wav.getnchannels(), wav.getsampwidth()), (1, 2), fname)
                    seconds = wav.getnframes() / wav.getframerate()
                    self.assertTrue(0.1 <= seconds <= 3.0, f"{fname} is {seconds:.2f}s")
                    data = wav.readframes(wav.getnframes())
                samples = [int.from_bytes(data[i:i + 2], "little", signed=True) for i in range(0, len(data), 2)]
                peak = max(abs(s) for s in samples)
                self.assertGreater(peak, 8000, f"{fname} is almost silent")
                self.assertLess(peak, 32767, f"{fname} clips")
                self.assertLess(abs(samples[-1]), 300, f"{fname} ends with a click")

    def test_every_sound_has_a_volume(self):
        self.assertEqual(set(VOLUMES), set(SOUND_NAMES))
        self.assertTrue(all(0.0 < v <= 1.0 for v in VOLUMES.values()))


# ---------------------------------------------------------------------------
# the SoundBoard (against a fake mixer)
# ---------------------------------------------------------------------------

class FakeChannel:
    def __init__(self):
        self.volume = None

    def set_volume(self, left, right=None):
        self.volume = (left, right)


class FakeSound:
    played = []

    def __init__(self, path):
        if "roll" in os.path.basename(path):
            raise RuntimeError("unreadable file")           # one broken file must not stop the others
        self.path = path

    def play(self):
        channel = FakeChannel()
        FakeSound.played.append((os.path.basename(self.path), channel))
        return channel


def fake_mixer(ready=True):
    return types.SimpleNamespace(
        get_init=lambda: (44100, -16, 2) if ready else None,
        get_num_channels=lambda: 8, set_num_channels=lambda n: None,
        Sound=FakeSound, stop=lambda: None, pause=lambda: None, unpause=lambda: None)


class SoundBoardTests(unittest.TestCase):
    def setUp(self):
        FakeSound.played = []
        self.dir = tempfile.TemporaryDirectory()
        for fname in ("slam.wav", "step_1.wav", "step_2.wav", "step_3.wav", "roll.wav", "notes.txt"):
            open(os.path.join(self.dir.name, fname), "wb").close()
        self.addCleanup(self.dir.cleanup)

    def board(self, **kwargs):
        kwargs.setdefault("volume", 1.0)
        kwargs.setdefault("seed", 1)
        return SoundBoard(directory=self.dir.name, **kwargs)

    def test_loads_files_groups_variants_and_skips_broken_ones(self):
        with mock.patch.object(pygame, "mixer", fake_mixer(), create=True):
            board = self.board().load()
        self.assertEqual(set(board.sounds), {"slam", "step"})
        self.assertEqual(len(board.sounds["step"]), 3)

    def test_a_variant_never_plays_twice_in_a_row(self):
        with mock.patch.object(pygame, "mixer", fake_mixer(), create=True):
            board = self.board()
            for _ in range(60):
                board.play("step")
        names = [name for name, _ in FakeSound.played]
        self.assertEqual(len(names), 60)
        self.assertTrue(all(a != b for a, b in zip(names, names[1:])))

    def test_volume_is_master_times_sound_times_request(self):
        with mock.patch.object(pygame, "mixer", fake_mixer(), create=True):
            board = self.board(volume=0.5)
            channel = board.play("slam", 0.5)
        expected = 0.5 * VOLUMES["slam"] * 0.5
        self.assertAlmostEqual(channel.volume[0], expected)
        self.assertAlmostEqual(channel.volume[1], expected)

    def test_sounds_pan_towards_where_they_happen(self):
        with mock.patch.object(pygame, "mixer", fake_mixer(), create=True):
            board = self.board()
            left_side = board.play("slam", 1.0, x=0).volume
            centre = board.play("slam", 1.0, x=minotaur_sfx.SCREEN_WIDTH / 2).volume
            right_side = board.play("slam", 1.0, x=minotaur_sfx.SCREEN_WIDTH).volume
        self.assertGreater(left_side[0], left_side[1])         # on the left: louder in the left ear
        self.assertAlmostEqual(centre[0], centre[1])
        self.assertGreater(right_side[1], right_side[0])
        self.assertGreater(min(left_side[1], right_side[0]), 0.3, "a hard pan must never go silent")

    def test_mute_enabled_flag_and_unknown_names(self):
        with mock.patch.object(pygame, "mixer", fake_mixer(), create=True):
            board = self.board()
            self.assertTrue(board.toggle_mute())
            self.assertIsNone(board.play("slam"))
            self.assertFalse(board.toggle_mute())
            self.assertIsNotNone(board.play("slam"))
            self.assertIsNone(board.play("no_such_sound"))
            self.assertIsNone(self.board(enabled=False).play("slam"))
        self.assertEqual(len(FakeSound.played), 1)

    def test_without_a_mixer_everything_is_a_quiet_no_op(self):
        with mock.patch.object(pygame, "mixer", fake_mixer(ready=False), create=True):
            board = self.board()
            self.assertIsNone(board.play("slam"))
            board.load()
            board.stop_all()
            board.set_paused(True)
            self.assertFalse(board.available)
        self.assertEqual(FakeSound.played, [])

    def test_a_missing_folder_is_silent_not_a_crash(self):
        with mock.patch.object(pygame, "mixer", fake_mixer(), create=True):
            board = SoundBoard(directory=os.path.join(self.dir.name, "nope"))
            self.assertIsNone(board.play("slam"))
            self.assertEqual(board.sounds, {})

    def test_the_shared_board_is_one_object(self):
        self.assertIs(minotaur_sfx.get_soundboard(), minotaur_sfx.get_soundboard())


# ---------------------------------------------------------------------------
# the boss makes the right sound at the right moment
# ---------------------------------------------------------------------------

class BossSoundTests(unittest.TestCase):
    def test_intro_roars_as_he_storms_in_and_thuds_as_he_lands(self):
        boss = recorded_boss()
        advance(boss, StubPlayer(), Minotaur.INTRO_TIME + 0.1)
        names = boss.sfx.names()
        self.assertEqual(names[0], "roar_big")
        self.assertEqual(names.count("roar_big"), 1)
        self.assertIn("thud", names)

    def test_entering_a_state_plays_its_sound_once(self):
        for state, sound in STATE_SOUNDS.items():
            boss = recorded_boss()
            boss.set_state(state)
            boss.set_state(state)                                # staying in a state is not a new event
            self.assertEqual(boss.sfx.names().count(sound), 1, f"{state} should play {sound} once")

    def test_every_sound_the_boss_asks_for_exists(self):
        self.assertTrue(set(STATE_SOUNDS.values()) <= set(SOUND_NAMES))

    def test_a_slam_winds_up_then_booms_once(self):
        boss = idle_boss()
        boss._start_slam()
        advance(boss, StubPlayer(), 2.0)
        names = boss.sfx.names()
        self.assertEqual(names.count("slam_windup"), 1)
        self.assertEqual(names.count("slam"), 1)
        self.assertLess(names.index("slam_windup"), names.index("slam"))

    def test_every_boulder_lands_with_a_sound(self):
        boss = idle_boss()
        boss._start_rain()
        advance(boss, StubPlayer(), 3.0)
        names = boss.sfx.names()
        self.assertEqual(names.count("rain_windup"), 1)
        self.assertEqual(names.count("rock"), PHASE_STATS[1]["rain_count"])

    def test_the_roar_ends_with_a_fireball_whoosh(self):
        boss = idle_boss()
        boss._start_attack = lambda name: None
        boss.set_state("cast_windup")
        advance(boss, StubPlayer(), 1.6)
        names = boss.sfx.names()
        self.assertEqual(names.count("cast_windup"), 1)
        self.assertEqual(names.count("fireball"), 1)

    def test_a_leap_jumps_then_lands_with_a_boom(self):
        boss = idle_boss()
        boss.set_state("leap_windup")
        advance(boss, StubPlayer(), 2.0)
        names = boss.sfx.names()
        order = [n for n in names if n in ("leap_windup", "leap", "slam")]
        self.assertEqual(order, ["leap_windup", "leap", "slam"])

    def test_a_charge_goes_windup_run_crash_stun(self):
        boss = recorded_boss()
        advance(boss, StubPlayer(), Minotaur.INTRO_TIME + 0.1)
        boss.sfx.calls.clear()
        boss._start_attack("charge")
        boss._start_attack = lambda name: None
        advance(boss, StubPlayer(), 4.2)
        order = [n for n in boss.sfx.names() if n in ("charge_windup", "charge", "crash", "stun")]
        self.assertEqual(order, ["charge_windup", "charge", "crash", "stun"])

    def test_walking_makes_footsteps(self):
        boss = idle_boss()
        boss.idle_mode = "chase"
        advance(boss, StubPlayer(), 2.0)
        self.assertGreaterEqual(boss.sfx.names().count("step"), 4)

    def test_footsteps_are_panned_to_the_screen_position(self):
        boss = idle_boss()
        boss.idle_mode = "chase"
        advance(boss, StubPlayer(), 1.0)
        pans = [x for name, _vol, x in boss.sfx.calls if name == "step"]
        self.assertTrue(pans and all(0 <= x <= 960 for x in pans))

    def test_taunting_stomps(self):
        boss = idle_boss()
        boss.idle_mode, boss.taunt, boss._fx_timer = "taunt", "stomp", 0.0
        advance(boss, StubPlayer(), 1.0)
        self.assertGreaterEqual(boss.sfx.names().count("stomp"), 2)

    def test_taunting_snorts_and_roars_play_once_when_the_taunt_starts(self):
        for sound in ("snort", "roar"):
            boss = recorded_boss(seed=3)
            for _ in range(500):
                boss.sfx.calls.clear()
                boss._go_idle(1.0)
                if boss.idle_mode == "taunt" and boss.taunt == sound:
                    self.assertEqual(boss.sfx.names(), [sound])
                    break
            else:
                self.fail(f"never rolled a {sound} taunt")

    def test_the_phase_change_roars_and_death_groans_then_thuds(self):
        boss = recorded_boss()
        advance(boss, StubPlayer(), Minotaur.INTRO_TIME + 0.1)
        boss.take_damage(150)
        advance(boss, StubPlayer(), boss.TRANSITION_TIME + 0.1)
        self.assertEqual(boss.sfx.names().count("roar_big"), 2, "intro roar + phase-change roar")
        boss._start_attack = lambda name: None
        boss.sfx.calls.clear()
        boss.take_damage(10 ** 6)
        advance(boss, StubPlayer(), boss.DYING_TIME + 0.1)
        order = [n for n in boss.sfx.names() if n in ("death", "thud")]
        self.assertEqual(order, ["death", "thud"])

    def test_a_silent_boss_fights_exactly_like_a_loud_one(self):
        quiet, loud = Minotaur(seed=4), Minotaur(seed=4)
        quiet.sfx, loud.sfx = None, Recorder()
        p1, p2 = StubPlayer(), StubPlayer()
        for _ in range(int(25 / DT)):
            quiet.update(DT, p1, BOUNDS)
            loud.update(DT, p2, BOUNDS)
        self.assertEqual((quiet.x, quiet.y, quiet.state, quiet.hp), (loud.x, loud.y, loud.state, loud.hp))
        self.assertEqual(p1.damage_taken, p2.damage_taken)
        self.assertTrue(loud.sfx.calls, "the loud boss should have made noise")


# ---------------------------------------------------------------------------
# the arena adds the player's sounds
# ---------------------------------------------------------------------------

def _arena(seed=1):
    from bosses.minotaur.arena import Arena
    arena = Arena(seed=seed)
    arena.boss.sfx = Recorder()
    return arena


def _inputs(**kwargs):
    from bosses.minotaur.arena import Inputs
    return Inputs(**kwargs)


def _run_intro(arena):
    for _ in range(int(4 / DT)):
        arena.step(DT, _inputs(aim=(arena.boss.x, arena.boss.y)))
        if arena.boss.state != "intro":
            break
    arena.boss.sfx.calls.clear()


@needs_pygame
class ArenaSoundTests(unittest.TestCase):
    def test_a_swing_makes_one_swing_sound(self):
        arena = _arena()
        _run_intro(arena)
        for _ in range(8):                                    # holding the button: still one swing inside its cooldown
            arena.step(DT, _inputs(aim=(480, 300), attack=True))
        self.assertEqual(arena.boss.sfx.names().count("swing"), 1)

    def test_a_roll_alone_makes_one_roll_sound(self):
        arena = _arena()
        _run_intro(arena)
        for _ in range(5):
            arena.step(DT, _inputs(aim=(480, 300), roll=True))
        self.assertEqual(arena.boss.sfx.names().count("roll"), 1)

    def test_hitting_blocking_and_the_stun_bonus(self):
        arena = _arena()
        arena.player.x, arena.player.y = arena.boss.x, arena.boss.y + 100
        for _ in range(12):                                   # still in his intro: he can't be hurt
            arena.step(DT, _inputs(aim=(arena.boss.x, arena.boss.y), attack=True))
        self.assertIn("block", arena.boss.sfx.names())
        self.assertNotIn("hit", arena.boss.sfx.names())

        arena = _arena(seed=2)
        _run_intro(arena)
        arena.boss._start_attack = lambda name: None
        arena.player.x, arena.player.y = arena.boss.x, arena.boss.y + 100
        for _ in range(12):
            arena.step(DT, _inputs(aim=(arena.boss.x, arena.boss.y), attack=True))
        self.assertIn("hit", arena.boss.sfx.names())

        arena.boss.set_state("stunned")                       # the 1.5x hit has its own, heavier sound
        arena.boss.sfx.calls.clear()
        arena.player.swing_cd = 0.0                           # ready to swing again
        for _ in range(12):
            arena.step(DT, _inputs(aim=(arena.boss.x, arena.boss.y), attack=True))
        self.assertIn("hit_heavy", arena.boss.sfx.names())

    def test_taking_damage_and_dying(self):
        arena = _arena()
        _run_intro(arena)
        arena.player.take_damage(10)
        arena.step(DT, _inputs())
        self.assertEqual(arena.boss.sfx.names().count("hurt"), 1)

        arena.player.invuln = 0.0
        arena.player.take_damage(arena.player.hp + 50)
        arena.step(DT, _inputs())
        self.assertIn("player_down", arena.boss.sfx.names())
        self.assertNotIn("defeat", arena.boss.sfx.names(), "the defeat jingle waits for the fall")
        for _ in range(int(1.0 / DT)):
            arena.step(DT, _inputs())
        self.assertEqual(arena.state, "lost")
        self.assertEqual(arena.boss.sfx.names().count("defeat"), 1)

    def test_winning_plays_the_fanfare_once(self):
        arena = _arena()
        _run_intro(arena)
        arena.boss._start_attack = lambda name: None
        arena.boss.take_damage(150)
        for _ in range(int((arena.boss.TRANSITION_TIME + 0.2) / DT)):
            arena.step(DT, _inputs(aim=(480, 300)))
        arena.boss.take_damage(10 ** 6)
        for _ in range(int((arena.boss.DYING_TIME + 1.0) / DT)):
            arena.step(DT, _inputs(aim=(480, 300)))
        self.assertEqual(arena.state, "won")
        self.assertEqual(arena.boss.sfx.names().count("victory"), 1)

    def test_restart_cuts_off_the_old_fights_sounds(self):
        arena = _arena()
        recorder = arena.boss.sfx
        arena.restart()
        self.assertEqual(recorder.stopped, 1)


if __name__ == "__main__":
    unittest.main()
