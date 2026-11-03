"""
AnimationController - decides *which* animation plays, from what the character does.

State rules
-----------
* Standing still          -> ``idle``
* Moving                  -> ``walk``  (or ``run`` while the run modifier is held)
* Quick attack            -> ``quick_attack``  (plays once, cannot be interrupted)
* Charge attack           -> ``charge_attack`` (draw bow, glow-loop while the button
                             is held, release to fire; letting go too early cancels)
* When an attack ends, the controller drops straight into whatever locomotion state
  the current input asks for (no flash of idle if the player is still running).

Smoothing details
-----------------
* ``idle_grace_ms``  - a very short pause in movement (e.g. flicking between keys)
  does not flash the idle pose.
* ``keep_phase``     - walk <-> run keep the same cycle position so legs do not reset.
* ``attack_buffer_ms`` - a quick-attack press during another attack is remembered
  briefly and fires as soon as the current one ends (responsive, combo-friendly).

No pygame here; the controller is fully testable without a window.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import List

from .config import ATTACKS, CHARGE_ATTACK, IDLE, QUICK_ATTACK, RUN, WALK
from .player import AnimationPlayer


@dataclass
class ControllerSettings:
    idle_grace_ms: float = 60.0
    attack_buffer_ms: float = 180.0
    keep_phase: bool = True


class AnimationController:
    """Drives an :class:`AnimationPlayer` from gameplay input.

    Typical use, once per frame::

        controller.update(dt_ms, move_x=+1, running=False)   # returns event names
        name, index, facing = controller.animation_name, controller.frame_index, controller.facing

    Attacks are requested with :meth:`request_quick_attack`, :meth:`press_charge`
    and :meth:`release_charge`.
    """

    def __init__(self, player: AnimationPlayer, settings: ControllerSettings = None):
        self.player = player
        self.settings = settings or ControllerSettings()
        self.facing: int = 1                    # +1 faces right (as drawn), -1 faces left
        self._idle_timer = 0.0
        self._attack_buffer = 0.0
        self._charge_announced = False
        self._pending_events: List[str] = []
        self._move_x = 0.0
        self._running = False
        self.player.play(IDLE)

    # ------------------------------------------------------------ read-only API
    @property
    def animation_name(self) -> str:
        return self.player.name

    @property
    def frame_index(self) -> int:
        return self.player.index

    @property
    def is_attacking(self) -> bool:
        return self.player.name in ATTACKS

    @property
    def can_move(self) -> bool:
        """False while an attack animation owns the character (feet are planted)."""
        return not self.is_attacking

    @property
    def is_charging(self) -> bool:
        return self.player.name == CHARGE_ATTACK and self.player.holding

    @property
    def charge_ready(self) -> bool:
        """True once the bow is fully drawn and glowing (a release will fire)."""
        loop = self.player.hold_loop
        return self.is_charging and loop is not None and self.player.index >= loop[0]

    # -------------------------------------------------------------- attack input
    def request_quick_attack(self) -> None:
        """Start a quick attack, or buffer it if an attack is already playing."""
        if self.is_attacking:
            self._attack_buffer = self.settings.attack_buffer_ms
        else:
            self._start_attack(QUICK_ATTACK)

    def press_charge(self) -> None:
        """Begin drawing the charged shot (ignored while another attack plays)."""
        if not self.is_attacking:
            self._start_attack(CHARGE_ATTACK, holding=True)

    def release_charge(self) -> None:
        """Let go of the charge button: fire if fully drawn, otherwise cancel."""
        if not self.is_charging:
            return
        if self.charge_ready:
            self.player.release_hold()          # plays on into the release frames
        else:
            self._enter_locomotion()            # released too early: bow is lowered

    # ------------------------------------------------------------------ update
    def update(self, dt_ms: float, move_x: float = 0.0, running: bool = False) -> List[str]:
        """Advance one tick. ``move_x`` is -1..1 (sign = direction), returns events."""
        events, self._pending_events = self._pending_events, []
        self._move_x, self._running = move_x, running
        self._attack_buffer = max(0.0, self._attack_buffer - dt_ms)

        if self.is_attacking:                   # attacks lock facing and movement
            events += self.player.update(dt_ms)
            events += self._announce_charge()
            if self.player.finished:
                events += self._finish_attack()
            return events

        if move_x:
            self.facing = 1 if move_x > 0 else -1
        self._update_locomotion(dt_ms)
        events += self.player.update(dt_ms)
        return events

    # ---------------------------------------------------------------- internals
    def _desired_locomotion(self) -> str:
        if not self._move_x:
            return IDLE
        return RUN if self._running else WALK

    def _update_locomotion(self, dt_ms: float) -> None:
        target = self._desired_locomotion()
        if target == self.player.name:
            self._idle_timer = 0.0
            return
        if target == IDLE:                      # brief stop: keep the moving pose a moment
            self._idle_timer += dt_ms
            if self._idle_timer < self.settings.idle_grace_ms:
                return
        self._switch_locomotion(target)

    def _switch_locomotion(self, target: str) -> None:
        current = self.player.name
        gait = (WALK, RUN)
        phase = self.player.phase if (self.settings.keep_phase and current in gait and target in gait) else 0.0
        self._pending_events += self.player.play(target, phase=phase)
        self._idle_timer = 0.0

    def _enter_locomotion(self) -> None:
        """Leave an attack immediately (no grace delay) for the state input asks for."""
        self._switch_locomotion(self._desired_locomotion())

    def _start_attack(self, name: str, holding: bool = False) -> None:
        self._pending_events += self.player.play(name, holding=holding)
        self._charge_announced = False
        self._idle_timer = 0.0

    def _announce_charge(self) -> List[str]:
        """Emit 'charged' exactly once when the bow reaches its full glow."""
        if self.charge_ready and not self._charge_announced:
            self._charge_announced = True
            return ["charged"]
        return []

    def _finish_attack(self) -> List[str]:
        if self._attack_buffer > 0.0:
            self._attack_buffer = 0.0
            self._start_attack(QUICK_ATTACK)
        else:
            self._enter_locomotion()
        events, self._pending_events = self._pending_events, []
        return events
