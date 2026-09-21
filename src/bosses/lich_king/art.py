"""
lich_king/art.py - Loads the Lich King's sprites from PNG files and animates them.

The ARTWORK lives in  assets/bosses/lich_king/  (see the README.md in that folder).
This file only loads those PNGs and adds the live effects on top. You should not
need to edit it to change how the Lich King looks.

FILES (in assets/bosses/lich_king/)
    body_phase1_a.png   REQUIRED  phase 1 body, cloak-hem frame A
    body_phase1_b.png   optional  phase 1, hem frame B (the cloak flutters A <-> B)
    body_phase2_a.png   optional  phase 2 body (falls back to phase 1 if missing)
    body_phase2_b.png   optional  phase 2, hem frame B
    staff.png           REQUIRED  the staff (drawn behind the body, lifts when summoning)
    sprite.json         optional  scale, anchor point and a few placement numbers

GLOW MARKERS
    Some pixels are painted in special "marker" colours (see MARKERS below).
    The game swaps them for glowing, pulsing, colour-changing pixels while it runs.
    Because the markers are just pixels in your PNG, you can move or reshape the
    eyes, chest gem and staff orb by repainting them. No code changes.

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
    "orb":       (255, 255, 0),     # staff orb (in staff.png)
    "orb_shine": (255, 255, 170),   # staff orb highlight (in staff.png)
}
_MARKER_NAMES = {rgb: name for name, rgb in MARKERS.items()}

BODY_FILES = {(1, 0): "body_phase1_a.png", (1, 1): "body_phase1_b.png",
              (2, 0): "body_phase2_a.png", (2, 1): "body_phase2_b.png"}
STAFF_FILE = "staff.png"
CONFIG_FILE = "sprite.json"
REQUIRED_FILES = ("body_phase1_a.png", STAFF_FILE)

DEFAULT_CONFIG = {
    "scale": 4,                          # each PNG pixel becomes scale x scale screen pixels
    "anchor": None,                      # [x, y] pixel that sits on the boss's position (None = middle)
    "shadow": {"y": 35, "widths": [22, 30, 22]},   # floor shadow: pixels below anchor, row widths
    "flame": None,                       # [x, y] base of the soul-flame held in the left hand
    "crown_fire": [],                    # phase 2 only: [[x, y, extra_height], ...] fire tongues
    "staff_lift": 3,                     # pixels the staff lifts when summoning
    "bob": 1.5,                          # how far he floats up and down (in pixels)
    "aura_radius": 21,                   # radius of the dithered glow behind him
}

# Live colours (eyes, core, orb, flame, embers, aura). Phase 1 = cold, phase 2 = hellfire.
LIVE = {
    1: {"eye": (93, 202, 165), "core": (93, 202, 165), "core_hi": (225, 255, 240),
        "flame": ((60, 190, 150), (130, 235, 200), (235, 255, 245)),
        "ember": ((127, 119, 221), (175, 169, 236), (93, 202, 165)),
        "aura": ((44, 38, 104), (62, 54, 140)), "orb": (175, 169, 236)},
    2: {"eye": (240, 70, 60), "core": (240, 70, 60), "core_hi": (255, 225, 170),
        "flame": ((230, 70, 50), (255, 150, 60), (255, 235, 150)),
        "ember": ((226, 75, 74), (255, 150, 60), (255, 215, 120)),
        "aura": ((92, 24, 60), (140, 34, 76)), "orb": (240, 110, 130)},
}

# The soul-flame (5 wide, 8 tall). F outer, f middle, Y hot centre.
FLAMES = [
    ["..F..", "..FF.", ".FFF.", ".FfFF", "FFfFF", "FfYfF", "FfYfF", ".FfF."],
    [".F...", ".FF..", ".FFF.", "FFfF.", "FFfFF", "FfYfF", "FfYfF", ".FfF."],
    ["...F.", "..FF.", ".FFF.", ".FFfF", "FFfFF", "FfYfF", "FfYfF", ".FfF."],
]

_warned = False


def _lerp(a, b, t):
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))


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
    """One PNG: the picture (glow pixels switched off) + where its glow markers are."""

    def __init__(self, image):
        self.markers = {name: [] for name in MARKERS}
        self.image = image.copy()
        w, h = image.get_size()
        for y in range(h):
            for x in range(w):
                r, g, b, a = image.get_at((x, y))
                if a == 255 and (r, g, b) in _MARKER_NAMES:
                    self.markers[_MARKER_NAMES[(r, g, b)]].append((x, y))
                    self.image.set_at((x, y), UNLIT + (255,))
        self.size = (w, h)


class SpriteSheet:
    """Everything loaded from the asset folder."""

    def __init__(self, folder):
        self.config = read_config(folder)
        self.scale = int(self.config["scale"])
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
        self.bodies = {}
        for (phase, hem), name in BODY_FILES.items():
            self.bodies[(phase, hem)] = loaded.get(name)
        # optional files fall back to the closest one that exists
        for phase in (1, 2):
            for hem in (0, 1):
                if self.bodies[(phase, hem)] is None:
                    self.bodies[(phase, hem)] = (self.bodies[(phase, 0)] if hem else None) or first
        self.staff = loaded[STAFF_FILE]
        anchor = self.config["anchor"]
        self.anchor = tuple(anchor) if anchor else (self.size[0] // 2, self.size[1] // 2)


# ----------------------------------------------------------------------
# Checking (used by dev/check_sprites.py and the tests)
# ----------------------------------------------------------------------

def check_assets(folder=ASSET_DIR):
    """Look for mistakes in the sprite files. Returns (errors, warnings) as lists of text."""
    errors, warnings = [], []
    if not os.path.isdir(folder):
        return [f"folder not found: {folder}"], warnings

    try:
        config = read_config(folder)
    except (ValueError, OSError) as err:
        return [f"{CONFIG_FILE} is not valid JSON: {err}"], warnings

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
        outer, inner = LIVE[phase]["aura"]
        w, h = self._sheet.size
        ax, ay = self._sheet.anchor
        radius = int(self._sheet.config["aura_radius"]) + (0, 1, 2, 1)[step % 4]
        canvas = Canvas(w, h)
        dither_disc(canvas, ax, ay, radius, outer, phase=step % 2)
        dither_disc(canvas, ax, ay, max(1, radius - 8), inner, phase=(step + 1) % 2)
        return canvas.to_surface(self._sheet.scale)

    def _px(self, layer, x, y, color):
        s = self._sheet.scale
        pygame.draw.rect(layer, color, (x * s, y * s, s, s))

    # -- the main entry point ---------------------------------------------
    def draw(self, surface, cx, cy, *, clock, phase, glow=None, glow_level=0,
             raise_staff=False, flash=False, fade=1.0):
        """
        Draw the Lich King with his anchor point at (cx, cy).
            clock        seconds since the fight started (drives all animation)
            phase        1 or 2
            glow         colour for eyes/orb while winding up an attack, else None
            glow_level   0-3, how strong the wind-up glow is
            raise_staff  lift the staff (summoning)
            flash        white hit flash
            fade         1.0 solid ... 0.0 gone. Pixels dissolve away in a dither
                         pattern (teleport / death) instead of a smooth fade.
        """
        if self._sheet is None and not self._failed:
            self._load()
        if self._sheet is None:
            self._draw_placeholder(surface, cx, cy)
            return

        sheet, cfg = self._sheet, self._sheet.config
        scale = sheet.scale
        width, height = sheet.size
        anchor_x, anchor_y = sheet.anchor
        live = LIVE[phase]
        eye_color = glow or live["eye"]
        orb_color = glow or live["orb"]

        # floor shadow (chunky, shrinks while he fades out)
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
        layer.blit(self._get(("aura", phase, aura_step), lambda: self._aura(phase, aura_step)), (0, 0))

        # 2. rising embers
        self._draw_embers(layer, clock, phase)

        # 3. staff (behind the hand); lifts a few pixels when summoning
        lift = -int(cfg["staff_lift"]) if raise_staff else 0
        staff = sheet.staff
        layer.blit(self._get(("staff", flash), lambda: self._scaled(staff, flash)), (0, lift * scale))
        if not flash:
            for x, y in staff.markers["orb"]:
                self._px(layer, x, y + lift, orb_color)
            shine = _lerp(orb_color, WHITE, 0.75)
            for x, y in staff.markers["orb_shine"]:
                self._px(layer, x, y + lift, shine)

        # 4. body (the hem flutters between frames A and B)
        hem = int(clock * 2.5) % 2
        body = sheet.bodies[(phase, hem)]
        layer.blit(self._get(("body", phase, hem, flash), lambda: self._scaled(body, flash)), (0, 0))

        if not flash:
            self._draw_eyes(layer, body, eye_color, glow_level)
            self._draw_core(layer, body, clock, phase, glow, glow_level)
            self._draw_left_flame(layer, clock, phase)
            if phase == 2:
                self._draw_crown_fire(layer, clock)

        # 5. pixel-dissolve when fading (teleport / death)
        if fade < 1.0:
            level = int(fade * DISSOLVE_STEPS + 0.5)
            if level <= 0:
                return
            mask = self._get(("mask", level), lambda: dissolve_mask(width, height, level, scale))
            layer.blit(mask, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)

        # 6. blit with a chunky, pixel-snapped floating bob
        bob = round(math.sin(clock * 2.2) * cfg["bob"])
        surface.blit(layer, (cx - anchor_x * scale, cy - anchor_y * scale + bob * scale))

    def _draw_placeholder(self, surface, cx, cy):
        """Shown when the sprite files are missing or broken, so the fight still works."""
        pygame.draw.rect(surface, (255, 0, 255), (cx - 60, cy - 90, 120, 180), 4)
        pygame.draw.line(surface, (255, 0, 255), (cx - 60, cy - 90), (cx + 60, cy + 90), 4)
        pygame.draw.line(surface, (255, 0, 255), (cx + 60, cy - 90), (cx - 60, cy + 90), 4)

    # -- live parts --------------------------------------------------------
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
        live = LIVE[phase]
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

    def _draw_left_flame(self, layer, clock, phase):
        anchor = self._sheet.config["flame"]
        if not anchor:
            return
        f_outer, f_mid, f_hot = LIVE[phase]["flame"]
        shape = FLAMES[int(clock * 8) % 3]
        colors = {"F": f_outer, "f": f_mid, "Y": f_hot}
        bob = round(math.sin(clock * 3.1))
        left, top = anchor[0] - 2, anchor[1] - 7 + bob
        for dy, row in enumerate(shape):
            for dx, ch in enumerate(row):
                if ch != ".":
                    self._px(layer, left + dx, top + dy, colors[ch])

    def _draw_crown_fire(self, layer, clock):
        f_outer, f_mid, f_hot = LIVE[2]["flame"]
        frame = int(clock * 9)
        for i, (x, y, extra) in enumerate(self._sheet.config["crown_fire"]):
            height = 2 + (frame + i * 2) % 3 + extra
            for h in range(height):
                color = f_hot if h == 0 else (f_mid if h < height - 1 else f_outer)
                self._px(layer, x, y - h, color)

    def _draw_embers(self, layer, clock, phase):
        colors = LIVE[phase]["ember"]
        width, height = self._sheet.size
        ax = self._sheet.anchor[0]
        count = 7 if phase == 1 else 13
        for i in range(count):
            t = (clock * 0.3 + i / count) % 1.0
            x = ax + int(math.sin(i * 2.4 + clock * 0.8) * (13 + (i % 3) * 4))
            y = (height - 5) - int(t * (height - 11))
            self._px(layer, x, y, colors[int(t * 3) % 3 if t < 0.85 else 0])
