"""
Loading sprite frames into pygame surfaces.

Quality rules enforced here
---------------------------
* Frames are loaded with ``convert_alpha()`` - per-pixel transparency is preserved.
* Frames are NEVER resampled with smoothing. The only scaling allowed is an
  *integer* factor using nearest-neighbour, so pixels stay crisp and proportions
  between all five animations remain identical.
* Left-facing frames are exact mirror images (``flip``), generated once at load time
  rather than every frame.
* Every frame carries an anchor (feet / body centre) so differently-sized PNGs line
  up perfectly - see ``tools/build_anchors.py`` for why this matters.

NOTE: ``pygame.display.set_mode()`` must have been called before loading, because
``convert_alpha()`` needs an initialised display.
"""
from __future__ import annotations

import json
import warnings
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Mapping, Tuple

import pygame

from .config import ANIMATIONS, DEFAULT_ASSETS_DIR, AnimationSpec, list_frame_files

ALPHA_THRESHOLD = 40


@dataclass(frozen=True)
class SpriteFrame:
    """One drawable frame. ``anchor`` is the point inside ``image`` that is placed
    on the character's world position (bottom-centre of the body)."""

    image: pygame.Surface
    anchor: Tuple[int, int]


@dataclass(frozen=True)
class FrameSet:
    """All frames of one animation, for both facing directions."""

    right: Tuple[SpriteFrame, ...]
    left: Tuple[SpriteFrame, ...]

    def __len__(self) -> int:
        return len(self.right)

    def get(self, index: int, facing: int = 1) -> SpriteFrame:
        return (self.right if facing >= 0 else self.left)[index]


class AnimationLibrary:
    """Every animation, loaded once and shared by any number of characters.

    Args:
        assets_dir: folder containing ``idle/``, ``walk/``, ``run/``,
                    ``quick_attack/``, ``charge_attack/`` and ``anchors.json``.
        specs:      animation definitions (defaults to ``config.ANIMATIONS``).
        scale:      integer pixel-perfect zoom (1 = original size, 2 = 2x, ...).
    """

    def __init__(
        self,
        assets_dir: Path = DEFAULT_ASSETS_DIR,
        specs: Mapping[str, AnimationSpec] = ANIMATIONS,
        scale: int = 1,
    ):
        if not isinstance(scale, int) or scale < 1:
            raise ValueError("scale must be a whole number >= 1 (pixel art stays crisp only at integer zoom)")
        if pygame.display.get_surface() is None:
            raise RuntimeError("Call pygame.display.set_mode(...) before creating AnimationLibrary "
                               "(convert_alpha needs an initialised display).")
        self.assets_dir = Path(assets_dir)
        self.specs = specs
        self.scale = scale
        anchors = self._read_anchor_file()
        self._sets: Dict[str, FrameSet] = {
            name: self._load_animation(spec, anchors.get(name, {})) for name, spec in specs.items()
        }

    # ------------------------------------------------------------------ access
    def __getitem__(self, name: str) -> FrameSet:
        return self._sets[name]

    @property
    def frame_counts(self) -> Dict[str, int]:
        return {name: len(fs) for name, fs in self._sets.items()}

    # ----------------------------------------------------------------- loading
    def _read_anchor_file(self) -> Dict[str, Dict[str, List[float]]]:
        path = self.assets_dir / "anchors.json"
        if not path.exists():
            warnings.warn(f"{path} not found - falling back to bottom-centre of each frame's "
                          f"opaque pixels. Run `python tools/build_anchors.py` for exact alignment.")
            return {}
        return json.loads(path.read_text())

    def _load_animation(self, spec: AnimationSpec, anchors: Mapping[str, List[float]]) -> FrameSet:
        right: List[SpriteFrame] = []
        left: List[SpriteFrame] = []
        for file in list_frame_files(self.assets_dir, spec):
            surface = pygame.image.load(str(file)).convert_alpha()
            width = surface.get_width()
            if file.name in anchors:
                ax, bottom_row = anchors[file.name]
                ax += 0.5                                # centroid of pixel indices -> pixel-centre coordinate
                ay = bottom_row + 1                      # edge *below* the lowest body pixel
            else:
                box = surface.get_bounding_rect(min_alpha=ALPHA_THRESHOLD)
                ax, ay = box.centerx, box.bottom
            if self.scale > 1:                           # nearest-neighbour, integer only
                surface = pygame.transform.scale(surface, (width * self.scale, surface.get_height() * self.scale))
            s = self.scale
            mirrored = pygame.transform.flip(surface, True, False)
            right.append(SpriteFrame(surface, (round(ax * s), round(ay * s))))
            left.append(SpriteFrame(mirrored, (round(width * s - ax * s), round(ay * s))))
        return FrameSet(tuple(right), tuple(left))
