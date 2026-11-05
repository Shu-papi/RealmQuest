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
    pose_raise_phase1.png / pose_raise_phase2.png   optional  fists overhead (slam, rock rain, leap)
    pose_cast_phase1.png  / pose_cast_phase2.png    optional  arms flung wide (roar, fireball cast)
    walk_phase1.png / walk_phase2.png               optional  walk cycle: N frames side by side (N x width, 1 x height)
    back_phase1.png / back_phase2.png               optional  seen from behind (isometric view)
    pose_raise_back_phaseN.png, pose_cast_back_phaseN.png, walk_back_phaseN.png   optional  the same, from behind
    sprite.json         optional  scale, anchor point and a few placement numbers

The sprite is also animated in code: draw() can lean it, squash and stretch it, flip it to face the
player and lift it off the ground, all on the same chunky pixel grid. Missing pose files simply fall
back to the normal body frame, so the game works with only body_phase1_a.png.

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
POSE_FILES = {("raise", 1): "pose_raise_phase1.png", ("raise", 2): "pose_raise_phase2.png",
              ("cast", 1): "pose_cast_phase1.png", ("cast", 2): "pose_cast_phase2.png"}
BACK_FILES = {(None, 1): "back_phase1.png", (None, 2): "back_phase2.png",
              ("raise", 1): "pose_raise_back_phase1.png", ("raise", 2): "pose_raise_back_phase2.png",
              ("cast", 1): "pose_cast_back_phase1.png", ("cast", 2): "pose_cast_back_phase2.png"}
WALK_FILES = {(False, 1): "walk_phase1.png", (False, 2): "walk_phase2.png",
              (True, 1): "walk_back_phase1.png", (True, 2): "walk_back_phase2.png"}      # (from behind?, phase)
CONFIG_FILE = "sprite.json"
REQUIRED_FILES = ("body_phase1_a.png",)

DEFAULT_CONFIG = {
    "scale": 4,                                   # each PNG pixel becomes scale x scale screen pixels
    "anchor": None,                               # [x, y] pixel that sits on the boss's position (None = middle)
    "shadow": {"y": 24, "widths": [28, 36, 28]},  # floor shadow: pixels below the anchor, row widths
    "bob": 1.0,                                   # how far he bobs up and down (in sprite pixels)
    "pivot": None,                                # [x, y] pixel he leans / squashes around (None = his feet)
    "faces": "left",                              # which way the PNG looks; he is flipped to face the player
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
    for name in list(BODY_FILES.values()) + list(POSE_FILES.values()) + list(BACK_FILES.values()):
        path = os.path.join(folder, name)
        if not os.path.exists(path):
            if name in REQUIRED_FILES:
                errors.append(f"{name}: file is missing (required)")
            continue
        try:
            frames[name] = pygame.image.load(path)
        except Exception as err:                                  # noqa: BLE001
            errors.append(f"{name}: cannot open as an image ({err})")

    sheets = {}
    for name in WALK_FILES.values():
        path = os.path.join(folder, name)
        if os.path.exists(path):
            try:
                sheets[name] = pygame.image.load(path)
            except Exception as err:                              # noqa: BLE001
                errors.append(f"{name}: cannot open as an image ({err})")

    sizes = {name: image.get_size() for name, image in frames.items()}
    for name, image in sheets.items():
        w, h = image.get_size()
        if sizes:
            fw, fh = next(iter(sizes.values()))
            if h != fh or w % fw or w // fw < 2:
                errors.append(f"{name}: a walk sheet must be 2 or more frames of {fw}x{fh} side by side "
                              f"(width a multiple of {fw}, height {fh}), but it is {w}x{h}")
        frames[name] = image                      # also check for soft pixels below
    if len({size for name, size in sizes.items()}) > 1:
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
        self._poses = {}
        self._backs = {}
        self._walk = {}
        self._cache = {}
        self._tried = False
        self.pivot = (0, 0)

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
            pivot = self.config.get("pivot")
            self.pivot = tuple(pivot) if pivot else (self.anchor[0], self.size[1] - 4)   # his feet

            # optional poses: a missing or different-sized file is skipped (the body frame is used instead)
            for key, name in POSE_FILES.items():
                path = os.path.join(self.folder, name)
                if os.path.exists(path):
                    try:
                        image = pygame.image.load(path)
                        if image.get_size() == self.size:
                            self._poses[key] = image
                        else:
                            _warn_once(f"{name} is {image.get_size()}, expected {self.size}; ignoring it")
                    except Exception as err:                          # noqa: BLE001
                        _warn_once(f"{name} could not be loaded ({err}); ignoring it")

            # optional back views and walk cycles
            for key, name in BACK_FILES.items():
                path = os.path.join(self.folder, name)
                if os.path.exists(path):
                    try:
                        image = pygame.image.load(path)
                        if image.get_size() == self.size:
                            self._backs[key] = image
                        else:
                            _warn_once(f"{name} is {image.get_size()}, expected {self.size}; ignoring it")
                    except Exception as err:                          # noqa: BLE001
                        _warn_once(f"{name} could not be loaded ({err}); ignoring it")
            for key, name in WALK_FILES.items():
                path = os.path.join(self.folder, name)
                if os.path.exists(path):
                    try:
                        sheet = pygame.image.load(path)
                        width, height = self.size
                        if sheet.get_height() == height and sheet.get_width() % width == 0 and sheet.get_width() // width >= 2:
                            self._walk[key] = [sheet.subsurface((i * width, 0, width, height)).copy()
                                               for i in range(sheet.get_width() // width)]
                        else:
                            _warn_once(f"{name} is {sheet.get_size()}, expected N frames of {self.size}; ignoring it")
                    except Exception as err:                          # noqa: BLE001
                        _warn_once(f"{name} could not be loaded ({err}); ignoring it")
        except Exception as err:                                  # noqa: BLE001
            self._fail(err)

    def walk_frame_count(self):
        """How many frames the walk cycle has (0 = no walk files, he just bobs along)."""
        if not self._tried:
            self._load()
        if self.broken:
            return 0
        return len(self._walk.get((False, 1)) or self._walk.get((False, 2)) or ())

    def has_back_view(self):
        if not self._tried:
            self._load()
        return not self.broken and (None, 1) in self._backs

    def _source(self, phase, hem, pose, back=False):
        """
        The raw (small) picture for a pose. pose is None (standing), "raise", "cast" or "walkN"
        (walk frame N); back = seen from behind. Anything without a file falls back to the closest one.
        """
        if pose and pose.startswith("walk"):
            frames = (self._walk.get((back, phase)) or self._walk.get((back, 1))
                      or self._walk.get((False, phase)) or self._walk.get((False, 1)))
            if frames:
                try:
                    return frames[int(pose[4:]) % len(frames)]
                except ValueError:
                    pass
            pose = None
        if back:
            for key in ((pose, phase), (pose, 1), (None, phase), (None, 1)):
                if key in self._backs:
                    return self._backs[key]
        if pose and (pose, phase) in self._poses:
            return self._poses[(pose, phase)]
        if pose and (pose, 1) in self._poses:
            return self._poses[(pose, 1)]
        return self._raw[(phase, hem)]

    def _base(self, phase, hem, pose, flip, back=False):
        """The picture scaled up to screen size (hard pixel edges). Built once, then reused."""
        key = (phase, hem, pose, flip, back)
        hit = self._cache.get(key)
        if hit is None:
            image = self._source(phase, hem, pose, back)
            if pygame.display.get_surface() is not None:             # needs a window; makes drawing faster
                image = image.convert_alpha()
            if flip:
                image = pygame.transform.flip(image, True, False)
            image = pygame.transform.scale(image, (image.get_width() * self.scale, image.get_height() * self.scale))
            if len(self._cache) > 400:
                self._cache.clear()
            hit = self._cache[key] = image
        return hit

    def _crossfade(self, phase, hem, pose_from, back_from, pose_to, back_to, mix, flip):
        """
        A smooth change between two poses. Pixels only in the old pose fade out, pixels only in the
        new pose fade in, and pixels in both change colour. Cached per tenth of the way through.
        """
        step = max(1, min(9, int(mix * 10)))
        key = ("fade", phase, hem, pose_from, back_from, pose_to, back_to, step, flip)
        hit = self._cache.get(key)
        if hit is not None:
            return hit
        old = self._base(phase, hem, pose_from, flip, back_from)
        new = self._base(phase, hem, pose_to, flip, back_to)
        weight = step / 10.0
        try:
            m_old, m_new = pygame.mask.from_surface(old), pygame.mask.from_surface(new)
            both = m_old.overlap_mask(m_new, (0, 0))
            only_old, only_new = m_old.copy(), m_new.copy()
            only_old.erase(both, (0, 0))
            only_new.erase(both, (0, 0))
            clear = (0, 0, 0, 0)
            result = pygame.Surface(old.get_size(), pygame.SRCALPHA)
            shared = both.to_surface(setsurface=old, unsetcolor=clear)
            top = both.to_surface(setsurface=new, unsetcolor=clear)
            top.set_alpha(int(255 * weight))
            shared.blit(top, (0, 0))
            result.blit(shared, (0, 0))
            fading_out = only_old.to_surface(setsurface=old, unsetcolor=clear)
            fading_out.set_alpha(int(255 * (1 - weight)))
            result.blit(fading_out, (0, 0))
            fading_in = only_new.to_surface(setsurface=new, unsetcolor=clear)
            fading_in.set_alpha(int(255 * weight))
            result.blit(fading_in, (0, 0))
        except Exception:                                             # noqa: BLE001 - old pygame: just switch
            result = new if weight >= 0.5 else old
        self._cache[key] = result
        return result

    @staticmethod
    def _transform(image, pivot_x, pivot_y, sx, sy, angle):
        """
        Squash / stretch, then lean (clockwise degrees), both around the pivot point.
        Works at screen size, so every tiny change shows up as a tiny movement. Returns
        (new image, new pivot x, new pivot y).
        """
        width, height = image.get_size()
        if abs(sx - 1.0) > 0.002 or abs(sy - 1.0) > 0.002:
            size = (max(1, round(width * sx)), max(1, round(height * sy)))
            image = pygame.transform.scale(image, size)
            pivot_x, pivot_y = pivot_x * size[0] / width, pivot_y * size[1] / height
            width, height = size
        if abs(angle) > 0.05:
            rotated = pygame.transform.rotate(image, -angle)          # pygame turns anticlockwise
            theta = math.radians(-angle)
            vx, vy = pivot_x - width / 2.0, pivot_y - height / 2.0
            rx = vx * math.cos(theta) + vy * math.sin(theta)
            ry = -vx * math.sin(theta) + vy * math.cos(theta)
            pivot_x, pivot_y = rotated.get_width() / 2.0 + rx, rotated.get_height() / 2.0 + ry
            image = rotated
        return image, pivot_x, pivot_y

    # ---------- drawing ----------

    def draw(self, surface, x, y, *, clock=0.0, phase=1, tint=None, tint_amount=1.0,
             lift=0, alpha=255, anim_speed=1.0,
             pose=None, back=False, fade_to=None, fade_mix=0.0, flip=False, angle=0.0, sx=1.0, sy=1.0,
             shift=(0.0, 0.0), hem=None, shadow=True, shadow_scale=1.0, bob=True):
        """
        Draw the Minotaur centred on (x, y). Returns False if the sprites could not be
        used, so the caller can draw a placeholder shape instead.

        clock       seconds, drives the idle animation
        phase       1 or 2 (picks the body files)
        tint        None, "flash" (hit) or "warn" (attack incoming)
        tint_amount 0-1, how strongly the tint shows (so it can pulse and fade smoothly)
        lift        sprite pixels to raise him (slam wind-up, leaps)
        alpha       0-255, used by the death fade
        anim_speed  1 = normal; faster while charging

        pose        None (standing), "raise" (fists overhead), "cast" (arms wide) or "walk0".."walkN"
        back        True = seen from behind (isometric view; needs the back_* files, else the front is used)
        fade_to     (pose, back) to fade towards, fade_mix (0-1) says how far along the fade is
        flip        mirror him (the PNG looks left, so flip=True makes him face right)
        angle       lean in degrees, clockwise on screen, around his feet
        sx, sy      squash / stretch (1.0 = normal), around his feet
        shift       (x, y) nudge in sprite pixels (fractions are fine and move smoothly)
        hem         force frame A (0) or B (1); None = swap with the clock like the old behaviour
        shadow, shadow_scale, bob   switch off the floor shadow / shrink it / switch off the idle bob
        """
        if not self._tried:
            self._load()
        if self.broken:
            return False
        try:
            scale = self.scale
            if str(self.config.get("faces", "left")).lower() == "right":
                flip = not flip                                   # the PNG looks right, so "facing left" is the mirrored one
            flip = bool(flip)
            if hem is None:
                hem = int(clock * 2.5 * anim_speed) % 2
            back = bool(back)
            if fade_to is not None and tuple(fade_to) != (pose, back) and fade_mix > 0.04:
                if fade_mix >= 0.96:
                    image = self._base(phase, hem, fade_to[0], flip, bool(fade_to[1]))
                else:
                    image = self._crossfade(phase, hem, pose, back, fade_to[0], bool(fade_to[1]), fade_mix, flip)
            else:
                image = self._base(phase, hem, pose, flip, back)
            owned = False                                         # True once `image` is our own copy

            pivot_art_x = self.size[0] - 1 - self.pivot[0] if flip else self.pivot[0]
            anchor_x = self.size[0] - 1 - self.anchor[0] if flip else self.anchor[0]
            pivot_x, pivot_y = pivot_art_x * scale, self.pivot[1] * scale
            transformed, pivot_x, pivot_y = self._transform(image, pivot_x, pivot_y, sx, sy, angle)
            owned = transformed is not image
            image = transformed

            if tint and tint_amount > 0.01:
                if not owned:
                    image, owned = image.copy(), True
                k = min(1.0, tint_amount)
                image.fill(tuple(int(c * k) for c in TINTS[tint]) + (0,), special_flags=pygame.BLEND_RGB_ADD)
            if alpha < 255:
                if not owned:
                    image, owned = image.copy(), True
                image.set_alpha(max(0, int(alpha)))

            wobble = math.sin(clock * 3.0) * float(self.config["bob"]) if bob else 0.0
            foot_x = x + (pivot_art_x - anchor_x + shift[0]) * scale
            foot_y = y + (self.pivot[1] - self.anchor[1] - lift + wobble + shift[1]) * scale
            left = round(foot_x - pivot_x)
            top = round(foot_y - pivot_y)

            shadow_cfg = self.config.get("shadow")
            if shadow and shadow_cfg and alpha > 100:
                grow = max(0.2, shadow_scale)
                for i, width in enumerate(shadow_cfg["widths"]):
                    row_y = round(y) + (shadow_cfg["y"] + i) * scale
                    w = max(scale, int(width * grow * scale))
                    pygame.draw.rect(surface, SHADOW_COLOR, (round(x) - w // 2, row_y, w, scale))
            surface.blit(image, (left, top))
        except Exception as err:                                  # noqa: BLE001
            self._fail(err)
            return False
        return True
