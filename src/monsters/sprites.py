"""
sprites.py - Loads a monster's PNG strip, recolours it for a VARIANT and animates the glow.

THE ARTWORK lives in  assets/monsters/<name>/
    frames.png    one horizontal strip, every pose side by side (all the same size)
    sprite.json   frame size, scale, the floor "anchor" pixel and which frames are which

GLOW MARKERS
    A few pixels are painted in exact marker colours. The game swaps them for glowing,
    pulsing pixels (and a different colour per variant) while it runs, so you can repaint
    the eyes, runes or orb in any pixel editor without touching code.
        eye   (255, 0, 255)      glow  (0, 255, 255)      orb  (255, 255, 0)

VARIANTS
    The same sprite can be re-skinned for different areas of the game: "bone" (default),
    "cursed", "frost", "ember" and "plague". A variant swaps the bone colours and the
    glow colours. Add your own in VARIANTS below.

Run  python src/monsters/dev/preview.py  to see every monster in every variant.
"""
import json
import os
import sys

import pygame

from .paths import asset_dir

MARKERS = {"eye": (255, 0, 255), "glow": (0, 255, 255), "orb": (255, 255, 0)}
_MARKER_NAMES = {rgb: name for name, rgb in MARKERS.items()}
UNLIT = {"eye": (14, 10, 24), "glow": (44, 36, 78), "orb": (60, 50, 90)}
GLOW_LEVELS = 6                              # how many brightness steps a glow pixel has

# The bone colours as painted in the PNGs (so a variant knows which pixels to recolour)
BONE_PAINTED = {"hi": (250, 247, 235), "mid": (222, 216, 196),
                "lo": (168, 160, 158), "crack": (112, 102, 116)}

VARIANTS = {
    "bone": {
        "bone": None,                                        # keep the painted colours
        "eye": (93, 202, 165), "glow": (175, 169, 236), "orb": (150, 140, 240),
        "embers": ((127, 119, 221), (175, 169, 236), (93, 202, 165)),
    },
    "cursed": {                                              # hellfire: the Lich King's phase 2 army
        "bone": {"hi": (246, 232, 224), "mid": (214, 190, 184), "lo": (160, 130, 138),
                 "crack": (116, 72, 84)},
        "eye": (240, 70, 60), "glow": (255, 150, 60), "orb": (240, 110, 130),
        "embers": ((226, 75, 74), (255, 150, 60), (255, 215, 120)),
    },
    "frost": {                                               # glaciers, snowy crypts
        "bone": {"hi": (240, 250, 255), "mid": (178, 216, 236), "lo": (116, 158, 196),
                 "crack": (70, 100, 150)},
        "eye": (140, 225, 255), "glow": (190, 240, 255), "orb": (170, 230, 255),
        "embers": ((140, 225, 255), (210, 245, 255), (110, 170, 240)),
    },
    "ember": {                                               # volcanoes, burnt ruins
        "bone": {"hi": (160, 138, 126), "mid": (106, 86, 84), "lo": (64, 50, 54),
                 "crack": (40, 30, 36)},
        "eye": (255, 150, 50), "glow": (255, 205, 80), "orb": (255, 170, 60),
        "embers": ((255, 110, 40), (255, 190, 70), (255, 235, 140)),
    },
    "plague": {                                              # swamps, poisoned wells
        "bone": {"hi": (226, 238, 172), "mid": (172, 198, 112), "lo": (108, 140, 80),
                 "crack": (66, 88, 58)},
        "eye": (190, 240, 60), "glow": (150, 230, 80), "orb": (210, 250, 100),
        "embers": ((150, 230, 80), (210, 250, 100), (96, 170, 70)),
    },
}


def _lerp(a, b, t):
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))


def glow_color(variant, marker, level):
    """The colour of a glow pixel at brightness `level` (0 dim ... GLOW_LEVELS-1 blazing)."""
    live = VARIANTS[variant][marker]
    dim = _lerp((0, 0, 0), live, 0.55)
    bright = _lerp(live, (255, 255, 255), 0.6)
    return _lerp(dim, bright, max(0, min(GLOW_LEVELS - 1, level)) / (GLOW_LEVELS - 1))


class Frame:
    """One pose: the picture (glow pixels switched off, bone recoloured) + marker positions."""

    def __init__(self, image, recolor):
        self.size = image.get_size()
        self.base = image.copy()
        self.markers = {name: [] for name in MARKERS}
        self.top_row = self.size[1]
        w, h = self.size
        for y in range(h):
            for x in range(w):
                r, g, b, a = image.get_at((x, y))
                if a != 255:
                    continue
                self.top_row = min(self.top_row, y)
                rgb = (r, g, b)
                if rgb in _MARKER_NAMES:
                    name = _MARKER_NAMES[rgb]
                    self.markers[name].append((x, y))
                    self.base.set_at((x, y), UNLIT[name] + (255,))
                elif rgb in recolor:
                    self.base.set_at((x, y), recolor[rgb] + (255,))


class SpriteSheet:
    """Everything loaded from one monster's asset folder, for one variant."""

    def __init__(self, name, variant="bone", size=1.0):
        folder = asset_dir(name)
        with open(os.path.join(folder, "sprite.json"), encoding="utf-8") as handle:
            config = json.load(handle)
        strip = pygame.image.load(os.path.join(folder, "frames.png"))
        if pygame.display.get_surface() is not None:
            strip = strip.convert_alpha()

        self.name = name
        self.variant = variant
        self.scale = max(1, int(round(int(config["scale"]) * size)))   # size > 1: a bigger monster (a mini-boss)
        fw, fh = config["frame_size"]
        self.frame_size = (fw, fh)
        self.anchor = tuple(config["anchor"])
        self.animations = {k: list(v) for k, v in config["animations"].items()}

        paint = VARIANTS[variant]["bone"]
        recolor = {}
        if paint:
            recolor = {BONE_PAINTED[k]: paint[k] for k in BONE_PAINTED}

        count = strip.get_width() // fw
        self.frames = []
        for i in range(count):
            cell = pygame.Surface((fw, fh), pygame.SRCALPHA)
            cell.blit(strip, (0, 0), (i * fw, 0, fw, fh))
            self.frames.append(Frame(cell, recolor))
        self.pixel_size = (fw * self.scale, fh * self.scale)
        self._cache = {}

    # Optional animations fall back, so a monster with only walk / windup / strike still works
    FALLBACKS = {"idle": ("walk", 1), "recover": ("strike", 0), "hurt": ("idle", 0)}

    def has(self, animation):
        return animation in self.animations

    def count(self, animation):
        """How many frames an animation has (after falling back if it is missing)."""
        while animation not in self.animations:
            animation, _step = self.FALLBACKS[animation]
        return len(self.animations[animation])

    def frame_index(self, animation, step):
        while animation not in self.animations:
            animation, step = self.FALLBACKS[animation]
        frames = self.animations[animation]
        return frames[step % len(frames)]

    def figure_top(self):
        """Screen pixels from the top of the picture down to the top of the standing figure."""
        return self.frames[self.frame_index("idle", 0)].top_row * self.scale

    def image(self, index, flip=False, level=3, flash=False):
        """The finished, scaled-up picture for one pose (cached)."""
        key = (index, flip, level, flash)
        cached = self._cache.get(key)
        if cached is not None:
            return cached
        frame = self.frames[index]
        small = frame.base.copy()
        for marker, pixels in frame.markers.items():
            color = glow_color(self.variant, marker, level)
            for pos in pixels:
                small.set_at(pos, color + (255,))
        big = pygame.transform.scale(small, self.pixel_size)
        if flash:
            mask = pygame.mask.from_surface(big)
            big = mask.to_surface(setcolor=(255, 255, 255, 255), unsetcolor=(0, 0, 0, 0))
        if flip:
            big = pygame.transform.flip(big, True, False)
        self._cache[key] = big
        return big

    def top_left(self, foot_x, foot_y, flip=False):
        """Screen position of the picture so the anchor pixel sits on (foot_x, foot_y)."""
        ax, ay = self.anchor
        if flip:
            ax = self.frame_size[0] - 1 - ax
        return (int(foot_x - (ax + 0.5) * self.scale), int(foot_y - (ay + 1) * self.scale))


_sheets = {}
_warned = set()


def get_sheet(name, variant="bone", size=1.0):
    """A cached SpriteSheet, or None if the art can't be loaded (monsters then draw shapes).
    size scales the pixel art (1.7 = a mini-boss), always by a whole number of screen pixels."""
    key = (name, variant, round(float(size), 3))
    if key not in _sheets:
        try:
            _sheets[key] = SpriteSheet(name, variant, size)
        except Exception as error:                                    # noqa: BLE001
            _sheets[key] = None
            if name not in _warned:
                _warned.add(name)
                print(f"[RealmQuest] Sprites for '{name}' could not be loaded ({error}).\n"
                      f"             Drawing a placeholder instead. See assets/monsters/README.md",
                      file=sys.stderr)
    return _sheets[key]
