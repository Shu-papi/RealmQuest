"""
minotaur/art.py - Loads the Minotaur's sprites from PNG files and draws them.

The ARTWORK lives in  assets/bosses/minotaur/  (see the README.md in that folder).
This file only loads those PNGs; you should not need to edit it to change how the
Minotaur looks. Overwrite the PNGs and run the game.

FILES (in assets/bosses/minotaur/)
    body_phase1_a.png   REQUIRED  phase 1 body, frame A
    body_phase1_b.png   optional  phase 1 body, frame B (swapped with A to animate)
    body_phase2_a.png   optional  phase 2 (enraged) body, frame A (falls back to phase 1)
    body_phase2_b.png   optional  phase 2 body, frame B
    sprite.json         optional  scale, anchor point and a few placement numbers

If a sprite is missing or broken the game does NOT crash: draw() returns False and
boss.py draws a simple shape instead. Run
    python src/bosses/dev/check_sprites.py minotaur
to see exactly what is wrong.
"""
import json
import math
import os

import pygame

from ..paths import asset_dir

ASSET_DIR = asset_dir("minotaur")             # assets/bosses/minotaur/

BODY_FILES = {(1, 0): "body_phase1_a.png", (1, 1): "body_phase1_b.png",
              (2, 0): "body_phase2_a.png", (2, 1): "body_phase2_b.png"}
CONFIG_FILE = "sprite.json"
REQUIRED_FILES = ("body_phase1_a.png",)

DEFAULT_CONFIG = {
    "scale": 4,                                   # each PNG pixel becomes scale x scale screen pixels
    "anchor": None,                               # [x, y] pixel that sits on the boss's position (None = middle)
    "shadow": {"y": 24, "widths": [28, 36, 28]},  # floor shadow: pixels below the anchor, row widths
    "bob": 1.0,                                   # how far he bobs up and down (in sprite pixels)
}

# Additive tints (added to every pixel's colour). Transparent pixels stay transparent.
TINTS = {
    "flash": (255, 255, 255),                     # "I was hit"
    "warn": (150, 24, 24),                        # "an attack is coming"
}

SHADOW_COLOR = (10, 8, 14)

_warned = set()


def _warn_once(message):
    if message not in _warned:
        _warned.add(message)
        print(f"[minotaur art] {message}")


# ----------------------------------------------------------------------
# Config + checking (used by dev/check_sprites.py and the tests)
# ----------------------------------------------------------------------

def read_config(folder):
    """sprite.json merged over the defaults. A missing file means all defaults."""
    config = json.loads(json.dumps(DEFAULT_CONFIG))
    path = os.path.join(folder, CONFIG_FILE)
    if os.path.exists(path):
        with open(path, encoding="utf-8") as handle:
            config.update(json.load(handle))
    return config


def check_assets(folder=ASSET_DIR):
    """Look for mistakes in the sprite files. Returns (errors, warnings) as lists of text."""
    errors, warnings = [], []
    if not os.path.isdir(folder):
        return [f"folder not found: {folder}"], warnings

    try:
        config = read_config(folder)
    except (ValueError, OSError) as err:
        return [f"{CONFIG_FILE} is not valid JSON: {err}"], warnings
    if not isinstance(config["scale"], int) or config["scale"] < 1:
        errors.append(f"{CONFIG_FILE}: 'scale' must be a whole number of 1 or more")

    frames = {}
    for name in BODY_FILES.values():
        path = os.path.join(folder, name)
        if not os.path.exists(path):
            if name in REQUIRED_FILES:
                errors.append(f"{name}: file is missing (required)")
            continue
        try:
            frames[name] = pygame.image.load(path)
        except Exception as err:                                  # noqa: BLE001
            errors.append(f"{name}: cannot open as an image ({err})")

    sizes = {name: image.get_size() for name, image in frames.items()}
    if len(set(sizes.values())) > 1:
        detail = ", ".join(f"{n}={w}x{h}" for n, (w, h) in sizes.items())
        errors.append(f"all sprite files must be the same size, but found: {detail}")

    for name, image in frames.items():
        w, h = image.get_size()
        soft = transparent = 0
        for y in range(h):
            for x in range(w):
                alpha = image.get_at((x, y))[3]
                if alpha == 0:
                    transparent += 1
                elif alpha != 255:
                    soft += 1
        if soft:
            warnings.append(f"{name}: {soft} semi-transparent pixel(s). Pixel art should be "
                            f"fully solid or fully transparent (turn anti-aliasing off)")
        if transparent == 0:
            warnings.append(f"{name}: no transparent pixels. Is the background transparent?")

    anchor = config.get("anchor")
    if anchor and sizes:
        w, h = next(iter(sizes.values()))
        if not (isinstance(anchor, list) and len(anchor) == 2
                and 0 <= anchor[0] < w and 0 <= anchor[1] < h):
            errors.append(f"{CONFIG_FILE}: 'anchor' must be [x, y] inside the {w}x{h} image")
    return errors, warnings


# ----------------------------------------------------------------------
# Drawing
# ----------------------------------------------------------------------

class MinotaurArt:
    """Loads the PNGs the first time he is drawn, then draws them (cached, crisp pixels)."""

    def __init__(self, folder=ASSET_DIR):
        self.folder = folder
        self.broken = False
        self.config = None
        self.scale = 4
        self.size = (0, 0)
        self.anchor = (0, 0)
        self._raw = {}
        self._cache = {}
        self._tried = False

    # ---------- loading ----------

    def _fail(self, err):
        self.broken = True
        _warn_once(f"sprites not usable, drawing placeholder shapes instead ({err}). "
                   f"Run: python src/bosses/dev/check_sprites.py minotaur")

    def _load(self):
        self._tried = True
        try:
            self.config = read_config(self.folder)
            self.scale = max(1, int(self.config["scale"]))
            loaded = {}
            for key, name in BODY_FILES.items():
                path = os.path.join(self.folder, name)
                if os.path.exists(path):
                    loaded[key] = pygame.image.load(path)
            if (1, 0) not in loaded:
                raise FileNotFoundError(f"missing required sprite file: {REQUIRED_FILES[0]}")

            # optional files fall back to the closest one that exists
            for phase in (1, 2):
                for hem in (0, 1):
                    for source in ((phase, hem), (phase, 0), (1, hem), (1, 0)):
                        if source in loaded:
                            self._raw[(phase, hem)] = loaded[source]
                            break
            first = loaded[(1, 0)]
            self.size = (first.get_width(), first.get_height())
            anchor = self.config["anchor"]
            self.anchor = tuple(anchor) if anchor else (self.size[0] // 2, self.size[1] // 2)
        except Exception as err:                                  # noqa: BLE001
            self._fail(err)

    def _get(self, phase, hem, tint):
        """The scaled (and tinted) picture, built once and then reused."""
        key = (phase, hem, tint)
        image = self._cache.get(key)
        if image is None:
            image = self._raw[(phase, hem)]
            if pygame.display.get_surface() is not None:        # needs a window; makes drawing faster
                image = image.convert_alpha()
            image = pygame.transform.scale(
                image, (image.get_width() * self.scale, image.get_height() * self.scale))  # hard edges
            if tint:
                image = image.copy()
                image.fill(TINTS[tint] + (0,), special_flags=pygame.BLEND_RGB_ADD)
            self._cache[key] = image
        return image

    # ---------- drawing ----------

    def draw(self, surface, x, y, *, clock=0.0, phase=1, tint=None,
             lift=0, alpha=255, anim_speed=1.0):
        """
        Draw the Minotaur centred on (x, y). Returns False if the sprites could not be
        used, so the caller can draw a placeholder shape instead.

        clock       seconds, drives the idle animation
        phase       1 or 2 (picks the body files)
        tint        None, "flash" (hit) or "warn" (attack incoming)
        lift        sprite pixels to raise him (used while he winds up a slam)
        alpha       0-255, used by the death fade
        anim_speed  1 = normal; faster while charging
        """
        if not self._tried:
            self._load()
        if self.broken:
            return False
        try:
            scale = self.scale
            hem = int(clock * 2.5 * anim_speed) % 2
            image = self._get(phase, hem, tint)
            if alpha < 255:
                image = image.copy()
                image.set_alpha(alpha)

            bob = round(math.sin(clock * 3.0) * float(self.config["bob"]))
            left = int(x) - self.anchor[0] * scale
            top = int(y) - (self.anchor[1] + lift - bob) * scale

            shadow = self.config.get("shadow")
            if shadow and alpha > 100:
                for i, width in enumerate(shadow["widths"]):
                    row_y = int(y) + (shadow["y"] + i) * scale
                    pygame.draw.rect(surface, SHADOW_COLOR,
                                     (int(x) - width * scale // 2, row_y, width * scale, scale))
            surface.blit(image, (left, top))
        except Exception as err:                                  # noqa: BLE001
            self._fail(err)
            return False
        return True
