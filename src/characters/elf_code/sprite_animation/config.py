"""
Animation configuration - the one place to tune speeds, looping and events.

Frame indexes are **0-based** (``..._01.png`` is index 0).  Pure Python: no pygame
import here, so everything in this file can be used and unit-tested headlessly.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Mapping, Optional, Tuple

DEFAULT_ASSETS_DIR = Path(__file__).resolve().parents[1] / "assets"


@dataclass(frozen=True)
class AnimationSpec:
    """Describes how one animation (a folder of numbered PNG frames) plays.

    Attributes:
        name:       Key used everywhere else ("idle", "walk", ...).
        folder:     Sub-folder of the assets directory that holds the PNG frames.
        fps:        Playback speed in frames per second.
        loop:       True = cycle forever; False = play once and stay on the last
                    frame, flagged ``finished``.
        frame_ms:   Optional per-frame duration overrides in milliseconds
                    ``{frame_index: ms}`` (hold an impact frame, linger on a pose...).
        events:     ``{frame_index: "event_name"}``. The event is reported by
                    ``update()`` on the exact tick that frame becomes visible - use
                    it to spawn arrows, play sounds, apply damage, shake the screen.
        hold_loop:  ``(first, last)`` frame range that repeats *while the action
                    button is held* (used by the charge attack's glowing bow).
    """

    name: str
    folder: str
    fps: float
    loop: bool = True
    frame_ms: Dict[int, float] = field(default_factory=dict)
    events: Dict[int, str] = field(default_factory=dict)
    hold_loop: Optional[Tuple[int, int]] = None

    def __post_init__(self) -> None:
        if self.fps <= 0:
            raise ValueError(f"{self.name}: fps must be > 0")
        if any(ms <= 0 for ms in self.frame_ms.values()):
            raise ValueError(f"{self.name}: frame_ms values must be > 0")
        if self.hold_loop and self.hold_loop[0] > self.hold_loop[1]:
            raise ValueError(f"{self.name}: hold_loop must be (first, last) with first <= last")

    def frame_duration(self, index: int) -> float:
        """Duration of one frame in milliseconds."""
        return self.frame_ms.get(index, 1000.0 / self.fps)


# --------------------------------------------------------------------------- #
#  The five animations.  Tweak fps / events here - no other code needs to change.
# --------------------------------------------------------------------------- #
IDLE = "idle"
WALK = "walk"
RUN = "run"
QUICK_ATTACK = "quick_attack"
CHARGE_ATTACK = "charge_attack"

LOCOMOTION = (IDLE, WALK, RUN)
ATTACKS = (QUICK_ATTACK, CHARGE_ATTACK)

ANIMATIONS: Mapping[str, AnimationSpec] = {
    # 16 frames @ 8 fps  -> calm 2 s breathing/blink loop
    IDLE: AnimationSpec(IDLE, "idle", fps=8),
    # 16 frames @ 14 fps -> ~1.14 s per walk cycle
    WALK: AnimationSpec(WALK, "walk", fps=14),
    # 12 frames @ 18 fps -> ~0.67 s per run cycle
    RUN: AnimationSpec(RUN, "run", fps=18),
    # 22 frames @ 24 fps -> ~0.92 s. Arrow leaves the bow on frame index 6.
    QUICK_ATTACK: AnimationSpec(
        QUICK_ATTACK, "quick_attack", fps=24, loop=False,
        events={6: "fire"},
    ),
    # 25 frames @ 18 fps.
    #   0-6   draw the bow (wind-up)
    #   7-11  glowing bow  -> loops while the button is held ("charged")
    #   12+   release: shard burst + piercing shot, then recovery
    CHARGE_ATTACK: AnimationSpec(
        CHARGE_ATTACK, "charge_attack", fps=18, loop=False,
        events={12: "fire"},        # "charged" is emitted once by the controller
        hold_loop=(7, 11),
    ),
}


# --------------------------------------------------------------------------- #
#  Helpers shared by the pure-Python core and the pygame loader
# --------------------------------------------------------------------------- #
def frame_number(path: Path) -> int:
    """Trailing number of a frame file name: ``elf_archer_idle_07.png`` -> 7.

    ZIP archives do not store files in order, so frames must be sorted by this
    number (a plain alphabetical sort breaks as soon as numbers reach 3 digits).
    """
    m = re.search(r"(\d+)\.png$", path.name, re.IGNORECASE)
    if not m:
        raise ValueError(f"Frame file has no trailing number: {path.name}")
    return int(m.group(1))


def list_frame_files(assets_dir: Path, spec: AnimationSpec):
    """Sorted PNG paths of one animation."""
    folder = Path(assets_dir) / spec.folder
    files = sorted(folder.glob("*.png"), key=frame_number)
    if not files:
        raise FileNotFoundError(
            f"No PNG frames for '{spec.name}' in {folder}. "
            f"Expected the extracted contents of the sprite ZIP there."
        )
    return files


def discover_frame_counts(
    assets_dir: Path = DEFAULT_ASSETS_DIR,
    specs: Mapping[str, AnimationSpec] = ANIMATIONS,
) -> Dict[str, int]:
    """Count frames per animation by listing the folders (no image decoding)."""
    return {name: len(list_frame_files(assets_dir, spec)) for name, spec in specs.items()}
