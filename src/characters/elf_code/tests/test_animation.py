"""
Headless tests (no pygame or window needed).   Run:  python -m unittest discover -s tests -v
"""
import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sprite_animation import (ANIMATIONS, CHARGE_ATTACK, IDLE, QUICK_ATTACK, RUN, WALK,
                              AnimationController, AnimationPlayer, discover_frame_counts)
from sprite_animation.config import DEFAULT_ASSETS_DIR, list_frame_files

COUNTS = {"idle": 16, "walk": 16, "run": 12, "quick_attack": 22, "charge_attack": 25}


def make_player():
    return AnimationPlayer(ANIMATIONS, COUNTS)


def make_controller():
    return AnimationController(make_player())


def run_for(ctrl, ms, step=16.0, **kw):
    """Tick the controller for ``ms`` milliseconds; returns all events."""
    events = []
    t = 0.0
    while t < ms:
        events += ctrl.update(step, **kw)
        t += step
    return events


class PlayerTests(unittest.TestCase):
    def test_loops_with_correct_timing(self):
        p = make_player()
        p.play(IDLE)                       # 8 fps -> 125 ms per frame
        p.update(124); self.assertEqual(p.index, 0)
        p.update(2);   self.assertEqual(p.index, 1)
        p.update(125 * 14); self.assertEqual(p.index, 15)
        p.update(125);      self.assertEqual(p.index, 0)       # wrapped

    def test_speed_is_independent_of_tick_size(self):
        a, b = make_player(), make_player()
        a.play(WALK); b.play(WALK)
        for _ in range(1000): a.update(1.0)          # 1 s in 1 ms steps
        b.update(1000.0)                              # 1 s in one giant step
        self.assertEqual(a.index, b.index)

    def test_non_looping_finishes_and_holds_last_frame(self):
        p = make_player()
        p.play(QUICK_ATTACK)
        p.update(10_000)
        self.assertTrue(p.finished)
        self.assertEqual(p.index, COUNTS["quick_attack"] - 1)

    def test_event_fires_once_on_its_frame(self):
        p = make_player()
        p.play(QUICK_ATTACK)
        fired = []
        for _ in range(200):
            fired += p.update(10)
        self.assertEqual(fired, ["fire"])

    def test_hold_loop_repeats_until_released_then_fires(self):
        p = make_player()
        p.play(CHARGE_ATTACK, holding=True)
        seen = set()
        for _ in range(400):                          # ~6 s held
            p.update(16)
            seen.add(p.index)
        self.assertTrue(max(seen) <= 11, "must not pass the held range while holding")
        self.assertFalse(p.finished)
        p.release_hold()
        events = []
        for _ in range(300):
            events += p.update(16)
        self.assertIn("fire", events)
        self.assertTrue(p.finished)

    def test_phase_start_is_clamped(self):
        p = make_player()
        p.play(RUN, phase=5.0); self.assertEqual(p.index, 11)
        p.play(RUN, phase=-1);  self.assertEqual(p.index, 0)

    def test_bad_config_is_rejected(self):
        with self.assertRaises(ValueError):
            AnimationPlayer(ANIMATIONS, dict(COUNTS, quick_attack=3))   # event on frame 6 > 3 frames


class ControllerTests(unittest.TestCase):
    def test_idle_when_still(self):
        c = make_controller(); run_for(c, 500)
        self.assertEqual(c.animation_name, IDLE)

    def test_walk_then_run_then_idle(self):
        c = make_controller()
        run_for(c, 100, move_x=1);              self.assertEqual(c.animation_name, WALK)
        run_for(c, 100, move_x=1, running=True); self.assertEqual(c.animation_name, RUN)
        run_for(c, 200);                         self.assertEqual(c.animation_name, IDLE)

    def test_facing_follows_input_and_is_remembered(self):
        c = make_controller()
        run_for(c, 50, move_x=-1); self.assertEqual(c.facing, -1)
        run_for(c, 200);           self.assertEqual(c.facing, -1)
        run_for(c, 50, move_x=1);  self.assertEqual(c.facing, 1)

    def test_idle_grace_prevents_flicker(self):
        c = make_controller()
        run_for(c, 100, move_x=1)
        c.update(16, move_x=0)                       # one tick of no input
        self.assertEqual(c.animation_name, WALK)
        c.update(16, move_x=1)
        self.assertEqual(c.animation_name, WALK)

    def test_walk_to_run_keeps_cycle_position(self):
        c = make_controller()
        run_for(c, 480, move_x=1)                    # ~mid-cycle
        before = c.player.phase
        c.update(1, move_x=1, running=True)
        self.assertEqual(c.animation_name, RUN)
        self.assertAlmostEqual(c.player.phase, before, delta=1 / COUNTS["run"] + 0.01)

    def test_quick_attack_locks_movement_and_returns_to_locomotion(self):
        c = make_controller()
        run_for(c, 100, move_x=1, running=True)
        c.request_quick_attack()
        events = run_for(c, 100, move_x=1, running=True)
        self.assertEqual(c.animation_name, QUICK_ATTACK)
        self.assertFalse(c.can_move)
        events += run_for(c, 1200, move_x=1, running=True)
        self.assertIn("fire", events)
        self.assertEqual(c.animation_name, RUN)      # straight back to running, no idle flash

    def test_attack_returns_to_idle_when_standing(self):
        c = make_controller()
        c.request_quick_attack()
        run_for(c, 1500)
        self.assertEqual(c.animation_name, IDLE)
        self.assertTrue(c.can_move)

    def test_attack_locks_facing(self):
        c = make_controller()
        c.request_quick_attack()
        run_for(c, 100, move_x=-1)
        self.assertEqual(c.facing, 1)

    def test_buffered_quick_attack_chains(self):
        c = make_controller()
        c.request_quick_attack()
        run_for(c, 800)                              # near the end
        c.request_quick_attack()                     # buffered
        events = run_for(c, 700)
        self.assertEqual(events.count("fire"), 1)    # second attack already started & fired
        self.assertEqual(c.animation_name, QUICK_ATTACK)

    def test_charge_hold_announces_once_then_release_fires(self):
        c = make_controller()
        c.press_charge()
        events = run_for(c, 3000)                    # hold for 3 s
        self.assertEqual(c.animation_name, CHARGE_ATTACK)
        self.assertEqual(events.count("charged"), 1)
        self.assertNotIn("fire", events)
        self.assertTrue(c.charge_ready)
        c.release_charge()
        events = run_for(c, 2500)
        self.assertEqual(events.count("fire"), 1)
        self.assertEqual(c.animation_name, IDLE)

    def test_early_release_cancels_charge(self):
        c = make_controller()
        c.press_charge()
        run_for(c, 120)
        c.release_charge()
        events = run_for(c, 2000)
        self.assertNotIn("fire", events)
        self.assertEqual(c.animation_name, IDLE)

    def test_cannot_start_second_attack_over_charge(self):
        c = make_controller()
        c.press_charge()
        c.press_charge()
        self.assertEqual(c.animation_name, CHARGE_ATTACK)


class AssetTests(unittest.TestCase):
    def test_counts_match_expected(self):
        self.assertEqual(discover_frame_counts(), COUNTS)

    def test_frames_are_numbered_contiguously(self):
        from sprite_animation.config import frame_number
        for spec in ANIMATIONS.values():
            nums = [frame_number(f) for f in list_frame_files(DEFAULT_ASSETS_DIR, spec)]
            self.assertEqual(nums, list(range(1, len(nums) + 1)), spec.name)

    def test_every_frame_has_an_anchor(self):
        anchors = json.loads((DEFAULT_ASSETS_DIR / "anchors.json").read_text())
        for spec in ANIMATIONS.values():
            for f in list_frame_files(DEFAULT_ASSETS_DIR, spec):
                self.assertIn(f.name, anchors[spec.name])


if __name__ == "__main__":
    unittest.main()
