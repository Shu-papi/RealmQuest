"""
AnimationPlayer - frame sequencing and timing, with no graphics dependency.

It answers one question: "given the time that has passed, which frame of which
animation should be on screen?"  Playback is driven by elapsed time (delta-time),
never by counting game ticks, so animation speed is identical at 30, 60 or 144 FPS
and a long frame hitch skips frames cleanly instead of slowing the animation down.
"""
from __future__ import annotations

from typing import List, Mapping

from .config import AnimationSpec


class AnimationPlayer:
    """Plays one animation at a time and reports frame events.

    Args:
        specs:         ``{name: AnimationSpec}`` (see :mod:`sprite_animation.config`).
        frame_counts:  ``{name: number_of_frames}`` for every spec.
    """

    def __init__(self, specs: Mapping[str, AnimationSpec], frame_counts: Mapping[str, int]):
        missing = [n for n in specs if n not in frame_counts]
        if missing:
            raise ValueError(f"No frame count for animation(s): {missing}")
        for name, spec in specs.items():
            n = frame_counts[name]
            bad = [i for i in list(spec.events) + list(spec.frame_ms) if not 0 <= i < n]
            if spec.hold_loop and not (0 <= spec.hold_loop[0] <= spec.hold_loop[1] < n):
                bad.append(spec.hold_loop)
            if bad:
                raise ValueError(f"'{name}' has only {n} frames but config references {bad}")
        self._specs = specs
        self._counts = dict(frame_counts)

        self._spec: AnimationSpec = next(iter(specs.values()))
        self._count: int = self._counts[self._spec.name]
        self.index: int = 0            # frame currently on screen
        self._elapsed: float = 0.0     # ms spent on the current frame
        self.finished: bool = False    # True once a non-looping animation ran out
        self.holding: bool = False     # True while a hold_loop should keep repeating

    # ------------------------------------------------------------------ state
    @property
    def name(self) -> str:
        return self._spec.name

    @property
    def frame_count(self) -> int:
        return self._count

    @property
    def hold_loop(self):
        """``(first, last)`` held frame range of the current animation, or None."""
        return self._spec.hold_loop

    @property
    def phase(self) -> float:
        """Progress through the animation, 0.0 <= phase < 1.0 (sub-frame accurate)."""
        frac = self._elapsed / self._spec.frame_duration(self.index)
        return min(0.9999, (self.index + min(frac, 1.0)) / self._count)

    # ---------------------------------------------------------------- control
    def play(self, name: str, phase: float = 0.0, holding: bool = False) -> List[str]:
        """Switch to ``name``.

        ``phase`` starts the animation part-way through (0.0-1.0). Use it to keep a
        walk and a run cycle in step so the legs do not "reset" when speed changes.
        Returns the events of the frame that becomes visible (usually none).
        """
        self._spec = self._specs[name]
        self._count = self._counts[name]
        self.index = max(0, min(self._count - 1, int(phase * self._count)))
        self._elapsed = 0.0
        self.finished = False
        self.holding = holding
        event = self._spec.events.get(self.index)
        return [event] if event and phase == 0.0 else []

    def release_hold(self) -> None:
        """Stop repeating the ``hold_loop`` and continue to the frames after it.

        If we are inside the loop range, jump to its last frame so the release
        responds immediately instead of waiting out the rest of the glow frames.
        """
        self.holding = False
        loop = self._spec.hold_loop
        if loop and loop[0] <= self.index <= loop[1]:
            self.index = loop[1]
            self._elapsed = 0.0

    # ----------------------------------------------------------------- update
    def update(self, dt_ms: float) -> List[str]:
        """Advance by ``dt_ms`` milliseconds; returns names of events that fired."""
        events: List[str] = []
        if self.finished or dt_ms <= 0:
            return events
        self._elapsed += dt_ms
        while True:
            duration = self._spec.frame_duration(self.index)
            if self._elapsed < duration:
                break
            self._elapsed -= duration
            if not self._advance(events):
                break
        return events

    def _advance(self, events: List[str]) -> bool:
        """Move to the next frame. Returns False when the animation has finished."""
        spec = self._spec
        nxt = self.index + 1
        if spec.hold_loop and self.holding and self.index == spec.hold_loop[1]:
            nxt = spec.hold_loop[0]                      # repeat the held section
        elif nxt >= self._count:
            if not spec.loop:
                self.finished = True
                self._elapsed = 0.0
                return False
            nxt = 0
        self.index = nxt
        event = spec.events.get(nxt)
        if event:
            events.append(event)
        return True
