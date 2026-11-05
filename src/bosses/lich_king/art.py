"""
lich_king/art.py - Loads the Lich King's sprites from PNG files and animates them.

The ARTWORK lives in  assets/bosses/lich_king/  (see the README.md in that folder).
This file only loads those PNGs and adds the live effects on top. You should not
need to edit it to change how the Lich King looks.

TWO FILE FORMATS (both work)
  POSE STRIPS (current)   frames_phase1.png, frames_phase2.png (optional) + sprite.json
        Each strip holds every pose side by side. sprite.json says how big a frame is and which
        frames belong to which pose ("animations"): idle, volley, drain, summon, recover, hurt, roar.
        Only "idle" is required; a missing pose falls back to idle.
  CLASSIC FILES (older)   body_phase1_a.png (+ _b, phase2 versions) and staff.png: a 2-frame
        cloak flutter and a separate staff that lifts when summoning.

GLOW MARKERS
    Some pixels are painted in special "marker" colours (see MARKERS below).
    The game swaps them for glowing, pulsing, colour-changing pixels while it runs.
    Because the markers are just pixels in your PNG, you can move or reshape the
    eyes, chest gem, staff orb, flames and runes by repainting them. No code changes.

LIVE EFFECTS drawn by this file (no art needed): the aura, rising embers, orbiting soul-skulls,
a rotating rune circle on the floor, energy gathering during attack wind-ups, drifting hem wisps.

Run  python src/bosses/dev/check_sprites.py lich_king  to check your files for mistakes.
"""
import json
import math
import os
import sys

import pygame
from ..paths import asset_dir
from ..pixel_art import dither_disc, dissolve_mask, DISSOLVE_STEPS

ASSET_DIR = asset_dir("lich_king")             # assets/bosses/lich_king/

WHITE = (255, 255, 255)
UNLIT = (14, 10, 24)                     # what a glow pixel looks like when it is "off"

# name -> exact RGB. Paint these in your sprite to mark glowing areas.
MARKERS = {
    "eye":       (255, 0, 255),     # eyes: always glowing
    "eye_flare": (255, 102, 255),   # eyes: extra glow while winding up an attack
    "eye_burst": (255, 176, 255),   # eyes: peak glow just before the attack fires
    "core":      (0, 255, 255),     # chest gem: main glow (pulses like a heartbeat)
    "core_rim":  (0, 136, 136),     # chest gem: dark edge
    "core_hi":   (170, 255, 255),   # chest gem: bright centre
    "orb":       (255, 255, 0),     # staff orb
    "orb_shine": (255, 255, 170),   # staff orb highlight
    "flame":     (255, 136, 0),     # base of the big soul-flame floating over his hand (position only)
    "fire":      (255, 85, 0),      # base of a small flame: crown tips, horns (position only)
    "vein":      (255, 51, 153),    # glowing runes, cracks and gems (pulse slowly)
}
POSITION_MARKERS = ("flame", "fire")      # these only say WHERE something burns; the pixel itself is removed
_MARKER_NAMES = {rgb: name for name, rgb in MARKERS.items()}

# classic format
BODY_FILES = {(1, 0): "body_phase1_a.png", (1, 1): "body_phase1_b.png",
              (2, 0): "body_phase2_a.png", (2, 1): "body_phase2_b.png"}
STAFF_FILE = "staff.png"
CONFIG_FILE = "sprite.json"
REQUIRED_FILES = ("body_phase1_a.png", STAFF_FILE)
# pose strip format
STRIP_FILES = {1: "frames_phase1.png", 2: "frames_phase2.png"}
POSES = ("idle", "volley", "drain", "summon", "recover", "hurt", "roar", "nova", "grasp")

DEFAULT_CONFIG = {
    "scale": 4,                          # each PNG pixel becomes scale x scale screen pixels
    "anchor": None,                      # [x, y] pixel that sits on the boss's position (None = middle)
    "shadow": {"y": 35, "widths": [22, 30, 22]},   # floor shadow: pixels below anchor, row widths
    "flame": None,                       # classic format: [x, y] base of the soul-flame in the left hand
    "crown_fire": [],                    # classic format, phase 2: [[x, y, extra_height], ...] fire tongues
    "frame_size": None,                  # pose strips: [width, height] of one frame
    "animations": {},                    # pose strips: {"idle": [0, 1, 2, 3], "volley": [4, 5, 6], ...}
    "orbit": None,                       # {"center": [x, y], "radius": [rx, ry], "count": {"1": 3, "2": 5}}
    "wisps": None,                       # {"y": hem row, "x": [left, right]}: soul-wisps drifting from the hem
    "staff_lift": 3,                     # pixels the staff lifts when summoning
    "bob": 1.5,                          # how far he floats up and down (in pixels)
    "aura_radius": 21,                   # radius of the dithered glow behind him
}

# Live colours (eyes, core, orb, flame, embers, aura). Phase 1 = cold, phase 2 = hellfire.
LIVE = {
    1: {"eye": (93, 202, 165), "core": (93, 202, 165), "core_hi": (225, 255, 240),
        "flame": ((60, 190, 150), (130, 235, 200), (235, 255, 245)),
        "ember": ((127, 119, 221), (175, 169, 236), (93, 202, 165)),
        "aura": ((44, 38, 104), (62, 54, 140)), "orb": (175, 169, 236),
        "vein": (93, 202, 165), "soul": (200, 196, 240), "rune": (62, 54, 140)},
    2: {"eye": (240, 70, 60), "core": (240, 70, 60), "core_hi": (255, 225, 170),
        "flame": ((230, 70, 50), (255, 150, 60), (255, 235, 150)),
        "ember": ((226, 75, 74), (255, 150, 60), (255, 215, 120)),
        "aura": ((92, 24, 60), (140, 34, 76)), "orb": (240, 110, 130),
        "vein": (255, 120, 60), "soul": (255, 170, 120), "rune": (150, 34, 70)},
}

# Phase 3 "Last Stand": the phase 2 colours blend towards this white-hot palette as `rage` goes 0 -> 1.
RAGE = {"eye": (255, 240, 200), "core": (255, 190, 70), "core_hi": (255, 255, 225),
        "flame": ((255, 160, 40), (255, 225, 110), (255, 255, 230)),
        "ember": ((255, 190, 70), (255, 235, 140), (255, 255, 225)),
        "aura": ((150, 50, 40), (225, 115, 50)), "orb": (255, 205, 130),
        "vein": (255, 225, 130), "soul": (255, 236, 200), "rune": (225, 120, 50)}

# The classic soul-flame (5 wide, 8 tall). F outer, f middle, Y hot centre.
FLAMES = [
    ["..F..", "..FF.", ".FFF.", ".FfFF", "FFfFF", "FfYfF", "FfYfF", ".FfF."],
    [".F...", ".FF..", ".FFF.", "FFfF.", "FFfFF", "FfYfF", "FfYfF", ".FfF."],
    ["...F.", "..FF.", ".FFF.", ".FFfF", "FFfFF", "FfYfF", "FfYfF", ".FfF."],
]
# The big soul-flame used with the "flame" marker (7 wide, 10 tall), base at the bottom centre.
BIG_FLAMES = [
    ["...F...", "..FFF..", "..FfF..", ".FFfFF.", ".FfYfF.", "FFfYYfF", "FfYYYfF", "FfYYYfF", ".FfYYf.", "..FfF.."],
    ["....F..", "..FFF..", ".FFfF..", ".FfffF.", ".FfYfFF", "FfYYYfF", "FfYYYfF", "FfYYYfF", ".FfYYf.", "..FfF.."],
    ["..F....", "..FFF..", "..FfFF.", ".FFfFF.", "FFfYfF.", "FfYYYfF", "FfYYYfF", "FfYYYfF", ".FfYYf.", "..FfF.."],
]
SOUL = ["..SSS..", ".SSSSS.", "SSSSSSS", "SdSSdSS", ".SSSSS.", ".S.S.S."]     # a tiny orbiting skull

_warned = False


def _lerp(a, b, t):
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))


def _blend(a, b, t):
    """Blend a colour (or a tuple of colours) towards another."""
    if isinstance(a[0], tuple):
        return tuple(_blend(x, y, t) for x, y in zip(a, b))
    return _lerp(a, b, t)


def live_colors(phase, rage=0.0):
    """The live colour table for a phase, blended towards the enraged palette by `rage` (0..1)."""
    base = LIVE[phase]
    if rage <= 0:
        return base
    return {key: _blend(value, RAGE[key], rage) for key, value in base.items()}


# ----------------------------------------------------------------------
# Loading
# ----------------------------------------------------------------------

def read_config(folder):
    """sprite.json merged over the defaults. Missing file = all defaults."""
    config = json.loads(json.dumps(DEFAULT_CONFIG))
    path = os.path.join(folder, CONFIG_FILE)
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            config.update(json.load(f))
    return config


def _load_png(path):
    image = pygame.image.load(path)
    if pygame.display.get_surface() is not None:   # needs a window; makes drawing faster
        image = image.convert_alpha()
    return image


class Frame:
    """One picture: the pixels (glow pixels switched off) + where its glow markers are."""

    def __init__(self, image):
        self.markers = {name: [] for name in MARKERS}
        self.image = image.copy()
        w, h = image.get_size()
        for y in range(h):
            for x in range(w):
                r, g, b, a = image.get_at((x, y))
                if a == 255 and (r, g, b) in _MARKER_NAMES:
                    name = _MARKER_NAMES[(r, g, b)]
                    self.markers[name].append((x, y))
                    self.image.set_at((x, y), (0, 0, 0, 0) if name in POSITION_MARKERS else UNLIT + (255,))
        self.size = (w, h)


def uses_strips(folder):
    """True when the folder uses the pose-strip format (frames_phase1.png)."""
    return os.path.exists(os.path.join(folder, STRIP_FILES[1]))


class SpriteSheet:
    """Everything loaded from the asset folder.

        sheet.poses[phase][pose_name] -> [Frame, ...]      (phase 1 or 2; "idle" always exists)
        sheet.staff                   -> Frame or None     (classic format only: the staff is its own image)
    """

    def __init__(self, folder):
        self.config = read_config(folder)
        self.scale = int(self.config["scale"])
        self.staff = None
        if uses_strips(folder):
            self._load_strips(folder)
        else:
            self._load_classic(folder)
        anchor = self.config["anchor"]
        self.anchor = tuple(anchor) if anchor else (self.size[0] // 2, self.size[1] // 2)
        # older code / tests look at the two idle frames as sheet.bodies[(phase, 0 or 1)]
        self.bodies = {(p, h): self.poses[p]["idle"][h % len(self.poses[p]["idle"])]
                       for p in (1, 2) for h in (0, 1)}

    def _load_strips(self, folder):
        size = self.config["frame_size"]
        if not size or len(size) != 2:
            raise ValueError(f"{CONFIG_FILE} needs \"frame_size\": [width, height] for pose strips")
        fw, fh = int(size[0]), int(size[1])
        self.size = (fw, fh)
        animations = self.config["animations"]
        if "idle" not in animations:
            raise ValueError(f"{CONFIG_FILE}: \"animations\" must contain \"idle\"")
        self.poses = {}
        for phase, name in STRIP_FILES.items():
            path = os.path.join(folder, name)
            if not os.path.exists(path):
                if phase == 1:
                    raise FileNotFoundError(f"missing required sprite file: {name}")
                self.poses[2] = self.poses[1]                 # phase 2 art is optional
                continue
            strip = _load_png(path)
            count = strip.get_width() // fw
            frames = []
            for i in range(count):
                cell = pygame.Surface((fw, fh), pygame.SRCALPHA)
                cell.blit(strip, (0, 0), (i * fw, 0, fw, fh))
                frames.append(Frame(cell))
            self.poses[phase] = {pose: [frames[i] for i in indexes]
                                 for pose, indexes in animations.items()}

    def _load_classic(self, folder):
        loaded = {}
        for name in set(BODY_FILES.values()) | {STAFF_FILE}:
            path = os.path.join(folder, name)
            if os.path.exists(path):
                loaded[name] = Frame(_load_png(path))
        for name in REQUIRED_FILES:
            if name not in loaded:
                raise FileNotFoundError(f"missing required sprite file: {name}")
        first = loaded["body_phase1_a.png"]
        self.size = first.size
        bodies = {key: loaded.get(name) for key, name in BODY_FILES.items()}
        # optional files fall back to the closest one that exists
        for phase in (1, 2):
            for hem in (0, 1):
                if bodies[(phase, hem)] is None:
                    bodies[(phase, hem)] = (bodies[(phase, 0)] if hem else None) or first
        self.poses = {p: {"idle": [bodies[(p, 0)], bodies[(p, 1)]]} for p in (1, 2)}
        self.staff = loaded[STAFF_FILE]


# ----------------------------------------------------------------------
# Checking (used by dev/check_sprites.py and the tests)
# ----------------------------------------------------------------------

def check_assets(folder=ASSET_DIR):
    """Look for mistakes in the sprite files. Returns (errors, warnings) as lists of text."""
    if not os.path.isdir(folder):
        return [f"folder not found: {folder}"], []
    try:
        config = read_config(folder)
    except (ValueError, OSError) as err:
        return [f"{CONFIG_FILE} is not valid JSON: {err}"], []
    if uses_strips(folder):
        return _check_strips(folder, config)
    return _check_classic(folder, config)


def _scan_image(name, image, frame_width, errors, warnings):
    """Soft pixels, near-miss marker colours, colour count and marker counts per frame."""
    w, h = image.get_size()
    soft, colours, near = 0, set(), {}
    per_frame = {}
    for y in range(h):
        for x in range(w):
            r, g, b, a = image.get_at((x, y))
            if a == 0:
                continue
            if a < 255:
                soft += 1
                continue
            colours.add((r, g, b))
            if (r, g, b) in _MARKER_NAMES:
                counts = per_frame.setdefault(x // frame_width, {m: 0 for m in MARKERS})
                counts[_MARKER_NAMES[(r, g, b)]] += 1
            else:
                for mname, (mr, mg, mb) in MARKERS.items():
                    if max(abs(r - mr), abs(g - mg), abs(b - mb)) <= 12:
                        near[mname] = near.get(mname, 0) + 1
    if soft:
        errors.append(f"{name}: {soft} semi-transparent pixels. Turn off anti-aliasing / "
                      f"soft brushes and use only fully solid or fully empty pixels")
    for mname, count in near.items():
        errors.append(f"{name}: {count} pixels are almost, but not exactly, the '{mname}' "
                      f"marker colour {MARKERS[mname]}. Re-pick the exact colour")
    art_colours = len([c for c in colours if c not in _MARKER_NAMES])
    if art_colours > 40:
        warnings.append(f"{name}: uses {art_colours} colours. Retro sprites usually look best "
                        f"with 16-32")
    return per_frame


def _check_strips(folder, config):
    """Checks for the pose-strip format (frames_phase1.png [+ frames_phase2.png] + sprite.json)."""
    errors, warnings = [], []
    size = config.get("frame_size")
    animations = config.get("animations") or {}
    if not size or len(size) != 2:
        return [f"{CONFIG_FILE}: \"frame_size\": [width, height] is required for pose strips"], warnings
    fw, fh = size
    if "idle" not in animations:
        errors.append(f"{CONFIG_FILE}: \"animations\" must contain \"idle\" (a list of frame numbers)")
    for pose in animations:
        if pose not in POSES:
            warnings.append(f"{CONFIG_FILE}: the game never plays a pose called '{pose}' "
                            f"(it uses: {', '.join(POSES)})")
    for pose, indexes in animations.items():
        if not isinstance(indexes, list) or not indexes or not all(isinstance(i, int) for i in indexes):
            errors.append(f"{CONFIG_FILE}: animation '{pose}' must be a list of frame numbers like [0, 1, 2]")

    leftovers = [n for n in list(BODY_FILES.values()) + [STAFF_FILE] if os.path.exists(os.path.join(folder, n))]
    if leftovers:
        warnings.append(f"{', '.join(leftovers)}: old-format files are ignored because {STRIP_FILES[1]} "
                        f"exists. Delete them to avoid confusion")

    counts = {}
    for phase, name in STRIP_FILES.items():
        path = os.path.join(folder, name)
        if not os.path.exists(path):
            if phase == 1:
                errors.append(f"{name}: file is missing (required)")
            continue
        try:
            image = pygame.image.load(path)
        except Exception as err:                                # noqa: BLE001
            errors.append(f"{name}: cannot open as an image ({err})")
            continue
        w, h = image.get_size()
        if h != fh:
            errors.append(f"{name}: height is {h} but {CONFIG_FILE} says frames are {fh} tall")
        if w % fw:
            errors.append(f"{name}: width {w} is not a whole number of {fw}-pixel frames")
        counts[phase] = w // fw
        per_frame = _scan_image(name, image, fw, errors, warnings)

        idle = [i for i in animations.get("idle", []) if isinstance(i, int)]
        no_eyes = [i for i in range(counts[phase]) if per_frame.get(i, {}).get("eye", 0) < 2]
        no_core = [i for i in range(counts[phase]) if not per_frame.get(i, {}).get("core", 0)]
        if no_eyes:
            warnings.append(f"{name}: frames {no_eyes} have fewer than 2 'eye' marker pixels "
                            f"(255,0,255), so the eyes will not glow there")
        if no_core:
            warnings.append(f"{name}: frames {no_core} have no 'core' marker pixels (0,255,255), "
                            f"so the chest gem will not glow there")
        if idle and not any(per_frame.get(i, {}).get("orb", 0) for i in idle):
            warnings.append(f"{name}: no 'orb' marker pixels (255,255,0) in the idle frames, "
                            f"so the staff orb will not glow")
    if len(set(counts.values())) > 1:
        errors.append(f"both strips must have the same number of frames, found {counts}")
    if counts:
        total = min(counts.values())
        for pose, indexes in animations.items():
            if isinstance(indexes, list) and any(isinstance(i, int) and not 0 <= i < total for i in indexes):
                errors.append(f"{CONFIG_FILE}: animation '{pose}' uses a frame number outside "
                              f"0-{total - 1} (the strips have {total} frames)")

    def inside(pt):
        return 0 <= pt[0] < fw and 0 <= pt[1] < fh
    anchor = config.get("anchor")
    if anchor and not inside(anchor):
        errors.append(f"{CONFIG_FILE}: anchor {anchor} is outside the {fw}x{fh} frame")
    orbit = config.get("orbit")
    if orbit and not inside(orbit["center"]):
        errors.append(f"{CONFIG_FILE}: orbit centre {orbit['center']} is outside the frame")
    return errors, warnings


def _check_classic(folder, config):
    """Checks for the classic body_phase*.png + staff.png format."""
    errors, warnings = [], []
    frames = {}
    for name in sorted(set(BODY_FILES.values()) | {STAFF_FILE}):
        path = os.path.join(folder, name)
        if not os.path.exists(path):
            if name in REQUIRED_FILES:
                errors.append(f"{name}: file is missing (required)")
            continue
        try:
            image = pygame.image.load(path)
        except Exception as err:                                # noqa: BLE001
            errors.append(f"{name}: cannot open as an image ({err})")
            continue
        frames[name] = image

    sizes = {name: img.get_size() for name, img in frames.items()}
    if len(set(sizes.values())) > 1:
        detail = ", ".join(f"{n}={w}x{h}" for n, (w, h) in sizes.items())
        errors.append(f"all sprite files must be the same size, but found: {detail}")

    for name, image in frames.items():
        w, h = image.get_size()
        soft, colours = 0, set()
        near = {}
        markers = {m: 0 for m in MARKERS}
        for y in range(h):
            for x in range(w):
                r, g, b, a = image.get_at((x, y))
                if a == 0:
                    continue
                if a < 255:
                    soft += 1
                    continue
                colours.add((r, g, b))
                if (r, g, b) in _MARKER_NAMES:
                    markers[_MARKER_NAMES[(r, g, b)]] += 1
                else:
                    for mname, (mr, mg, mb) in MARKERS.items():
                        if max(abs(r - mr), abs(g - mg), abs(b - mb)) <= 12:
                            near[mname] = near.get(mname, 0) + 1
        if soft:
            errors.append(f"{name}: {soft} semi-transparent pixels. Turn off anti-aliasing / "
                          f"soft brushes and use only fully solid or fully empty pixels")
        for mname, count in near.items():
            errors.append(f"{name}: {count} pixels are almost, but not exactly, the '{mname}' "
                          f"marker colour {MARKERS[mname]}. Re-pick the exact colour")
        art_colours = len([c for c in colours if c not in _MARKER_NAMES])
        if art_colours > 40:
            warnings.append(f"{name}: uses {art_colours} colours. Retro sprites usually look best "
                            f"with 16-32")
        if name == STAFF_FILE:
            if not markers["orb"]:
                warnings.append(f"{name}: no 'orb' marker pixels (255,255,0), so the orb will not glow")
        else:
            if markers["eye"] < 2:
                warnings.append(f"{name}: fewer than 2 'eye' marker pixels (255,0,255), "
                                f"so the eyes will not glow")
            if not markers["core"]:
                warnings.append(f"{name}: no 'core' marker pixels (0,255,255), "
                                f"so the chest gem will not glow")

    if frames:
        w, h = next(iter(sizes.values()))

        def inside(pt):
            return 0 <= pt[0] < w and 0 <= pt[1] < h
        anchor = config.get("anchor")
        if anchor and not inside(anchor):
            errors.append(f"{CONFIG_FILE}: anchor {anchor} is outside the {w}x{h} canvas")
        if config.get("flame") and not inside(config["flame"]):
            errors.append(f"{CONFIG_FILE}: flame {config['flame']} is outside the canvas")
        for tip in config.get("crown_fire", []):
            if not inside(tip):
                errors.append(f"{CONFIG_FILE}: crown_fire point {tip} is outside the canvas")
    return errors, warnings



# ----------------------------------------------------------------------
# Drawing
# ----------------------------------------------------------------------

class LichKingArt:
    """Loads the sprites (on first use) and draws one complete Lich King each frame."""

    def __init__(self, folder=ASSET_DIR):
        self.folder = folder
        self._sheet = None
        self._failed = False
        self._cache = {}
        self._layer = None
        self._rage = 0.0

    # -- loading ---------------------------------------------------------
    def _load(self):
        global _warned
        try:
            self._sheet = SpriteSheet(self.folder)
        except Exception as err:                                # noqa: BLE001
            self._failed = True
            if not _warned:
                _warned = True
                print(f"[RealmQuest] Lich King sprites could not be loaded from {self.folder}\n"
                      f"             ({err})\n"
                      f"             Run  python src/bosses/dev/check_sprites.py lich_king  for details. "
                      f"Drawing a placeholder instead.", file=sys.stderr)

    def _get(self, key, builder):
        if key not in self._cache:
            self._cache[key] = builder()
        return self._cache[key]

    def _scaled(self, frame, flash):
        image = frame.image
        if flash:
            image = image.copy()
            image.fill(WHITE, special_flags=pygame.BLEND_RGB_ADD)      # white silhouette
        s = self._sheet.scale
        return pygame.transform.scale(image, (image.get_width() * s, image.get_height() * s))

    def _aura(self, phase, step):
        from ..pixel_art import Canvas
        outer, inner = self._live(phase)["aura"]
        w, h = self._sheet.size
        ax, ay = self._sheet.anchor
        radius = int(self._sheet.config["aura_radius"]) + (0, 1, 2, 1)[step % 4] + int(6 * self._rage)
        canvas = Canvas(w, h)
        dither_disc(canvas, ax, ay, radius, outer, phase=step % 2)
        dither_disc(canvas, ax, ay, max(1, radius - 8), inner, phase=(step + 1) % 2)
        return canvas.to_surface(self._sheet.scale)

    def _live(self, phase):
        return live_colors(phase, self._rage)

    def _px(self, layer, x, y, color):
        s = self._sheet.scale
        pygame.draw.rect(layer, color, (int(x) * s, int(y) * s, s, s))

    def _pick_body(self, phase, clock, pose, progress):
        """The frame to show: a pose chosen by progress (0..1), or the looping idle."""
        frames = self._sheet.poses[phase]
        if pose and pose != "idle" and pose in frames:
            lst = frames[pose]
            index = max(0, min(len(lst) - 1, int(progress * len(lst))))
            return lst[index], (pose, index)
        idle = frames["idle"]
        index = int(clock * 1.25 * len(idle)) % len(idle)      # 2 frames = the classic 2.5 flutters / second
        return idle[index], ("idle", index)

    # -- the main entry point ---------------------------------------------
    def draw(self, surface, cx, cy, *, clock, phase, glow=None, glow_level=0,
             raise_staff=False, flash=False, fade=1.0, pose=None, progress=0.0,
             rage=0.0, alpha=1.0, ghost=False):
        """
        Draw the Lich King with his anchor point at (cx, cy).
            clock        seconds since the fight started (drives all animation)
            phase        1 or 2
            glow         colour for eyes/orb while winding up an attack, else None
            glow_level   0-3, how strong the wind-up glow is
            pose         "idle" (default), "volley", "drain", "summon", "recover", "hurt", "roar",
                         "nova" or "grasp".
                         A pose missing from the art falls back to idle.
            progress     0..1, how far through the pose we are (picks the frame inside a pose)
            raise_staff  classic art only: lift the separate staff image (summoning)
            flash        white hit flash
            fade         1.0 solid ... 0.0 gone. Pixels dissolve away in a dither
                         pattern (teleport / death) instead of a smooth fade.
            rage         0..1 enraged look (phase 3): hotter colours, faster animation, more souls and embers
            alpha        0..1 see-through copy (used for the enraged afterimages)
            ghost        True = draw only the figure: no floor shadow or rune circle
        """
        if self._sheet is None and not self._failed:
            self._load()
        if self._sheet is None:
            self._draw_placeholder(surface, cx, cy)
            return

        self._rage = max(0.0, min(1.0, rage))
        clock = clock * (1.0 + 0.6 * self._rage)          # everything animates faster when enraged
        sheet, cfg = self._sheet, self._sheet.config
        scale = sheet.scale
        width, height = sheet.size
        anchor_x, anchor_y = sheet.anchor
        live = self._live(phase)
        eye_color = glow or live["eye"]
        orb_color = glow or live["orb"]

        # floor: a slowly turning rune circle and a chunky shadow (both shrink while he fades out)
        if not ghost:
            if fade > 0.04:
                self._draw_rune_circle(surface, cx, cy, phase, clock, fade)
            rows = cfg["shadow"]["widths"]
            for i, row_width in enumerate(rows):
                w = int(row_width * fade) * scale
                pygame.draw.rect(surface, (18, 15, 28),
                                 (cx - w // 2, cy + (cfg["shadow"]["y"] + i) * scale, w, scale))

        if self._layer is None or self._layer.get_size() != (width * scale, height * scale):
            self._layer = pygame.Surface((width * scale, height * scale), pygame.SRCALPHA)
        layer = self._layer
        layer.fill((0, 0, 0, 0))

        # 1. dithered aura, pulsing
        aura_step = int(clock * 5) % 4
        rage_key = int(self._rage * 4)
        layer.blit(self._get(("aura", phase, aura_step, rage_key), lambda: self._aura(phase, aura_step)), (0, 0))

        # 2. rising embers, souls drifting behind him, wisps from the hem
        self._draw_embers(layer, clock, phase)
        self._draw_souls(layer, clock, phase, front=False)
        self._draw_wisps(layer, clock, phase)

        # 3. classic art: the staff is its own image behind the hand; it lifts when summoning
        lift = 0
        staff = sheet.staff
        if staff is not None:
            lift = -int(cfg["staff_lift"]) if raise_staff else 0
            layer.blit(self._get(("staff", flash), lambda: self._scaled(staff, flash)), (0, lift * scale))
            if not flash:
                self._draw_orb(layer, staff, lift, orb_color)

        # 4. the body in the current pose
        body, key = self._pick_body(phase, clock, pose, progress)
        layer.blit(self._get(("body", phase, key, flash), lambda: self._scaled(body, flash)), (0, 0))

        if not flash:
            if staff is None:
                self._draw_orb(layer, body, 0, orb_color)
            self._draw_eyes(layer, body, eye_color, glow_level)
            self._draw_core(layer, body, clock, phase, glow, glow_level)
            self._draw_veins(layer, body, clock, phase)
            self._draw_flames(layer, body, clock, phase)
            self._draw_charge(layer, body, clock, glow, glow_level)
            self._draw_souls(layer, clock, phase, front=True)

        # 5. pixel-dissolve when fading (teleport / death)
        if fade < 1.0:
            level = int(fade * DISSOLVE_STEPS + 0.5)
            if level <= 0:
                return
            mask = self._get(("mask", level), lambda: dissolve_mask(width, height, level, scale))
            layer.blit(mask, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)

        # 6. blit with a chunky, pixel-snapped floating bob
        bob = round(math.sin(clock * 2.2) * cfg["bob"])
        layer.set_alpha(max(0, min(255, int(255 * alpha))) if alpha < 1.0 else 255)
        surface.blit(layer, (cx - anchor_x * scale, cy - anchor_y * scale + bob * scale))
        layer.set_alpha(255)

    def _draw_placeholder(self, surface, cx, cy):
        """Shown when the sprite files are missing or broken, so the fight still works."""
        pygame.draw.rect(surface, (255, 0, 255), (cx - 60, cy - 90, 120, 180), 4)
        pygame.draw.line(surface, (255, 0, 255), (cx - 60, cy - 90), (cx + 60, cy + 90), 4)
        pygame.draw.line(surface, (255, 0, 255), (cx + 60, cy - 90), (cx - 60, cy + 90), 4)

    # -- live parts that follow the markers in the art ---------------------
    def _draw_eyes(self, layer, body, color, level):
        for x, y in body.markers["eye"]:
            self._px(layer, x, y, color)
        if level >= 1:
            for x, y in body.markers["eye_flare"]:
                self._px(layer, x, y, color)
        if level >= 2:
            for x, y in body.markers["eye_burst"]:
                self._px(layer, x, y, color)

    def _draw_core(self, layer, body, clock, phase, glow, level):
        live = self._live(phase)
        base = glow or live["core"]
        beat = 0.5 + 0.5 * math.sin(clock * (3.0 + level))       # heartbeat
        colors = {
            "core": _lerp(base, WHITE, 0.15 * beat),
            "core_rim": _lerp(base, (0, 0, 0), 0.45),
            "core_hi": _lerp(live["core_hi"], base, 0.35 * (1 - beat)),
        }
        for kind, color in colors.items():
            for x, y in body.markers[kind]:
                self._px(layer, x, y, color)

    def _draw_orb(self, layer, frame, lift, color):
        for x, y in frame.markers["orb"]:
            self._px(layer, x, y + lift, color)
        shine = _lerp(color, WHITE, 0.75)
        for x, y in frame.markers["orb_shine"]:
            self._px(layer, x, y + lift, shine)

    def _draw_veins(self, layer, body, clock, phase):
        """Runes and cracks glow in a slow ripple that travels down his body."""
        live = self._live(phase)["vein"]
        dim = _lerp((0, 0, 0), live, 0.35)
        for x, y in body.markers["vein"]:
            pulse = 0.5 + 0.5 * math.sin(clock * 3.0 - y * 0.16 + x * 0.05)
            self._px(layer, x, y, _lerp(dim, _lerp(live, WHITE, 0.35), pulse))

    def _draw_flames(self, layer, body, clock, phase):
        f_outer, f_mid, f_hot = self._live(phase)["flame"]
        colors = {"F": f_outer, "f": f_mid, "Y": f_hot}
        shape_index = int(clock * 8) % 3
        for i, (x, y) in enumerate(body.markers["flame"]):         # the big soul-flame over his hand
            shape = BIG_FLAMES[(shape_index + i) % 3]
            sway = round(math.sin(clock * 3.1 + i))
            left, top = x - 3, y - len(shape) + 1 + sway
            for dy, row in enumerate(shape):
                for dx, ch in enumerate(row):
                    if ch != ".":
                        self._px(layer, left + dx, top + dy, colors[ch])
        frame = int(clock * 9)
        for i, (x, y) in enumerate(body.markers["fire"]):          # small flames on the crown and horns
            height = 3 + (frame + i * 2) % 3
            for h in range(height):
                color = f_hot if h == 0 else (f_mid if h < height - 1 else f_outer)
                self._px(layer, x, y - h, color)
        if not (body.markers["flame"] or body.markers["fire"]):
            self._draw_classic_fire(layer, clock, phase)

    def _draw_classic_fire(self, layer, clock, phase):
        """Classic art: flame and crown fire positions come from sprite.json instead of markers."""
        cfg = self._sheet.config
        f_outer, f_mid, f_hot = self._live(phase)["flame"]
        anchor = cfg["flame"]
        if anchor and not any(f.markers["flame"] for f in self._sheet.poses[phase]["idle"]):
            shape = FLAMES[int(clock * 8) % 3]
            colors = {"F": f_outer, "f": f_mid, "Y": f_hot}
            bob = round(math.sin(clock * 3.1))
            left, top = anchor[0] - 2, anchor[1] - 7 + bob
            for dy, row in enumerate(shape):
                for dx, ch in enumerate(row):
                    if ch != ".":
                        self._px(layer, left + dx, top + dy, colors[ch])
        if phase == 2:
            frame = int(clock * 9)
            for i, (x, y, extra) in enumerate(cfg["crown_fire"]):
                height = 2 + (frame + i * 2) % 3 + extra
                for h in range(height):
                    color = f_hot if h == 0 else (f_mid if h < height - 1 else f_outer)
                    self._px(layer, x, y - h, color)

    # -- live effects that need no art --------------------------------------
    def _draw_embers(self, layer, clock, phase):
        colors = self._live(phase)["ember"]
        width, height = self._sheet.size
        ax = self._sheet.anchor[0]
        count = (7 if phase == 1 else 13) + int(10 * self._rage)
        spread = max(13, int(width * 0.18))
        for i in range(count):
            t = (clock * 0.3 + i / count) % 1.0
            x = ax + int(math.sin(i * 2.4 + clock * 0.8) * (spread + (i % 3) * 4))
            y = (height - 5) - int(t * (height - 11))
            self._px(layer, x, y, colors[int(t * 3) % 3 if t < 0.85 else 0])

    def _draw_souls(self, layer, clock, phase, front):
        """Little skulls orbiting him. `front` ones pass in front of his body, the others behind."""
        orbit = self._sheet.config["orbit"]
        if not orbit:
            return
        count = int(orbit["count"].get(str(phase), 0))
        if not count:
            return
        count += int(3 * self._rage)
        cx, cy = orbit["center"]
        rx, ry = orbit["radius"]
        speed = 0.9 if phase == 1 else 1.7
        soul = self._live(phase)["soul"]
        for i in range(count):
            theta = clock * speed + i * math.tau / count
            depth = math.sin(theta)
            if (depth >= 0) != front:
                continue
            bob = math.sin(clock * 2.3 + i * 1.7) * 2
            for k in (3, 2, 1):                                     # a fading trail
                t2 = theta - k * 0.16
                tx = cx + math.cos(t2) * rx
                ty = cy + math.sin(t2) * ry + bob
                self._px(layer, tx, ty, _lerp((0, 0, 0), soul, 0.15 + 0.12 * (4 - k)))
            x = cx + math.cos(theta) * rx - 3
            y = cy + depth * ry + bob - 3
            shade = 1.0 if front else 0.5
            body_color = _lerp((20, 16, 36), soul, shade)
            for dy, row in enumerate(SOUL):
                for dx, ch in enumerate(row):
                    if ch == "S":
                        self._px(layer, x + dx, y + dy, body_color)
                    elif ch == "d":
                        self._px(layer, x + dx, y + dy, (30, 24, 50))

    def _draw_wisps(self, layer, clock, phase):
        """Soul-wisps drifting down out of the hem: he floats, his robe is dissolving."""
        wisps = self._sheet.config["wisps"]
        if not wisps:
            return
        x0, x1 = wisps["x"]
        base = _lerp((0, 0, 0), self._live(phase)["soul"], 0.55)
        for i in range(14):
            t = (clock * 0.55 + i * 0.37) % 1.0
            if t > 0.85:
                continue
            x = x0 + (x1 - x0) * ((i * 0.618) % 1.0) + math.sin(clock * 1.3 + i) * 2
            y = wisps["y"] + t * 10
            self._px(layer, x, y, _lerp(base, (20, 16, 36), t))

    def _draw_charge(self, layer, body, clock, glow, level):
        """While winding up an attack, motes of energy stream in towards his soul-core."""
        if not glow or level < 1:
            return
        core = body.markers["core"]
        if core:
            cx = sum(p[0] for p in core) / float(len(core))
            cy = sum(p[1] for p in core) / float(len(core))
        else:
            cx, cy = self._sheet.anchor
        count = 5 * level
        for i in range(count):
            frac = (clock * 1.9 + i / float(count)) % 1.0
            ang = i * 2.399 + clock * 0.8
            radius = 3 + 32 * (1.0 - frac)
            self._px(layer, cx + math.cos(ang) * radius, cy + math.sin(ang) * radius * 0.8,
                     _lerp(glow, WHITE, frac * 0.6))

    def _draw_rune_circle(self, surface, cx, cy, phase, clock, fade):
        """A turning ring of rune-dots on the floor under him (two rings in phase 2)."""
        cfg = self._sheet.config
        scale = self._sheet.scale
        y = cy + (cfg["shadow"]["y"] + 1) * scale
        radius_x = int(max(cfg["shadow"]["widths"]) * scale * 0.95)
        rune = self._live(phase)["rune"]
        bright = _lerp(rune, WHITE, 0.45)
        rings = ((1.0, 28, 0.35, 1), (0.62, 18, -0.55, -1)) if phase == 2 else ((1.0, 28, 0.35, 1),)
        for scale_f, dots, speed, direction in rings:
            rx = radius_x * scale_f * (0.4 + 0.6 * fade)
            ry = rx * 0.3
            for i in range(dots):
                a = clock * speed + i * math.tau / dots
                size = scale + 1 if i % 4 == 0 else scale - 1
                color = bright if i % 4 == 0 else rune
                pygame.draw.rect(surface, color, (int(cx + math.cos(a) * rx) // 2 * 2,
                                                  int(y + math.sin(a) * ry) // 2 * 2, size, size))
