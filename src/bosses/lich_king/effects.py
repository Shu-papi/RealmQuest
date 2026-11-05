"""
effects.py - Pixel-art spell effects for the Lich King: rune circles, cracks, soul-fire, shockwaves.

THE IDEA
    Everything is drawn on a small, low-resolution canvas (one canvas pixel = PIXEL screen pixels, the
    same chunky size as the Lich King's own sprite) and then scaled up. That makes every effect line up
    with his pixels and look like part of the same game, instead of smooth circles and thin dotted lines.

    An FxLayer has two canvases:
        solid  opaque pixels (runes, bones, flames)
        soft   translucent shapes that are DITHERED (a checkerboard of pixels) when drawn,
               the classic retro way to get "glowing areas" without smooth gradients.

USING IT
        fx = FxLayer(left, top, width, height)          # the screen area you will draw in
        rune_ring(fx, cx, cy, 80, colour, clock)
        fx.circle((cx, cy), 80, colour, soft=True)      # a dithered glowing disc
        fx.draw(screen)                                 # scale up and blit

Every function takes SCREEN coordinates; the layer converts them to its low-res grid.
Colours with an alpha (r, g, b, a) are fine on the soft canvas.
"""
import math
import random

import pygame

PIXEL = 3                                   # screen pixels per effect pixel (the Lich King sprite uses 3)

BONE = (222, 216, 196)
BONE_LIGHT = (250, 247, 235)
BONE_SHADE = (168, 160, 158)
OUTLINE = (33, 29, 46)
SAFE = (151, 196, 89)                       # "you are safe here" is always this green
SAFE_DIM = (96, 130, 62)
HEAL = (151, 196, 89)

# The spell colours of each phase: main = bright, glow = vivid, dark = shadowy, hot = near-white flash
THEMES = {
    1: dict(main=(175, 169, 236), glow=(127, 119, 221), dark=(44, 38, 104), hot=(238, 237, 254)),
    2: dict(main=(240, 120, 140), glow=(226, 75, 74), dark=(92, 24, 60), hot=(255, 215, 185)),
    3: dict(main=(255, 205, 130), glow=(255, 150, 60), dark=(150, 50, 40), hot=(255, 250, 225)),
}


def theme(phase):
    return THEMES[max(1, min(3, int(phase)))]


def with_alpha(color, alpha):
    return (color[0], color[1], color[2], int(max(0, min(255, alpha))))


def lerp_color(a, b, t):
    t = max(0.0, min(1.0, t))
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))


def ease_out(t):
    t = max(0.0, min(1.0, t))
    return 1 - (1 - t) * (1 - t)


# ----------------------------------------------------------------------
# Little bitmaps. '#' = filled.
# ----------------------------------------------------------------------

GLYPHS = [                                  # 3 x 5 "runes"
    ["#.#", "#.#", "###", "#.#", "#.#"],
    ["###", "..#", ".#.", "#..", "###"],
    ["#..", "#..", "###", "#.#", "###"],
    [".#.", "###", ".#.", ".#.", ".#."],
    ["#.#", ".#.", "###", ".#.", "#.#"],
    ["###", "#.#", "#.#", "#.#", "###"],
    ["##.", "#.#", "##.", "#.#", "##."],
    [".#.", "#.#", "#.#", "#.#", ".#."],
]

SKULL = [                                   # a tiny ghost skull (5 x 5): o = eye socket
    ".###.",
    "#####",
    "#o#o#",
    "#####",
    ".#.#.",
]

SKULL_BIG = [                               # a bigger one for things that can hurt you (7 x 6)
    ".#####.",
    "#######",
    "##o#o##",
    "#######",
    ".#####.",
    "..#.#..",
]


# ----------------------------------------------------------------------
# The layer
# ----------------------------------------------------------------------

_checker_cache = {}


def _checker_mask(width, height):
    """A white checkerboard (every other pixel opaque) at least width x height, cached."""
    if not hasattr(pygame, "mask"):                 # the fake pygame used in tests cannot do this
        return None
    bw, bh = (width + 15) // 16 * 16, (height + 15) // 16 * 16
    big = _checker_cache.get((bw, bh))
    if big is None:
        big = pygame.Surface((2, 2), pygame.SRCALPHA)
        big.set_at((0, 0), (255, 255, 255, 255))
        big.set_at((1, 1), (255, 255, 255, 255))
        cw = ch = 2
        while cw < bw:                              # double it sideways, then downwards
            nxt = pygame.Surface((cw * 2, ch), pygame.SRCALPHA)
            nxt.blit(big, (0, 0))
            nxt.blit(big, (cw, 0))
            big, cw = nxt, cw * 2
        while ch < bh:
            nxt = pygame.Surface((cw, ch * 2), pygame.SRCALPHA)
            nxt.blit(big, (0, 0))
            nxt.blit(big, (0, ch))
            big, ch = nxt, ch * 2
        _checker_cache[(bw, bh)] = big
    return big.subsurface(pygame.Rect(0, 0, width, height))


class FxLayer:
    """A low-resolution canvas for one effect. See the module docstring."""

    def __init__(self, left, top, width, height):
        self.left = int(left) // PIXEL * PIXEL              # snap to the shared pixel grid
        self.top = int(top) // PIXEL * PIXEL
        self.w = max(1, int((left + width - self.left) // PIXEL) + 2)
        self.h = max(1, int((top + height - self.top) // PIXEL) + 2)
        self.solid = pygame.Surface((self.w, self.h), pygame.SRCALPHA)
        self.soft = pygame.Surface((self.w, self.h), pygame.SRCALPHA)

    # ---- coordinates ----
    def p(self, x, y):
        return (int((x - self.left) // PIXEL), int((y - self.top) // PIXEL))

    def _surface(self, soft):
        return self.soft if soft else self.solid

    # ---- drawing (all in screen coordinates) ----
    def dot(self, x, y, color, size=1, soft=False):
        px, py = self.p(x, y)
        pygame.draw.rect(self._surface(soft), color, (px, py, size, size))

    def rect(self, x0, y0, x1, y1, color, soft=False):
        """A filled rectangle between two screen points."""
        px0, py0 = self.p(x0, y0)
        px1, py1 = self.p(x1, y1)
        pygame.draw.rect(self._surface(soft), color, (min(px0, px1), min(py0, py1),
                                                      abs(px1 - px0) + 1, abs(py1 - py0) + 1))

    def line(self, a, b, color, width=1, soft=False):
        pygame.draw.line(self._surface(soft), color, self.p(*a), self.p(*b), width)

    def circle(self, center, radius, color, width=0, soft=False):
        pygame.draw.circle(self._surface(soft), color, self.p(*center), max(1, int(radius / PIXEL)), width)

    def polygon(self, points, color, width=0, soft=False):
        pygame.draw.polygon(self._surface(soft), color, [self.p(*q) for q in points], width)

    def bitmap(self, x, y, rows, colors, soft=False):
        """Draw a text bitmap centred on (x, y). `colors` maps each character to a colour."""
        ox, oy = self.p(x, y)
        ox -= len(rows[0]) // 2
        oy -= len(rows) // 2
        surface = self._surface(soft)
        for dy, row in enumerate(rows):
            for dx, ch in enumerate(row):
                if ch in colors:
                    surface.set_at((ox + dx, oy + dy), colors[ch])

    def glyph(self, x, y, index, color):
        self.bitmap(x, y, GLYPHS[index % len(GLYPHS)], {"#": color})

    # ---- finishing ----
    def draw(self, surface):
        out = pygame.Surface((self.w, self.h), pygame.SRCALPHA)
        mask = _checker_mask(self.w, self.h)
        if mask is not None:
            self.soft.blit(mask, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
        out.blit(self.soft, (0, 0))
        out.blit(self.solid, (0, 0))
        surface.blit(pygame.transform.scale(out, (self.w * PIXEL, self.h * PIXEL)), (self.left, self.top))


class clip_to:
    """`with clip_to(surface, (left, top, right, bottom)):` limits drawing to the arena. Safe without real pygame."""

    def __init__(self, surface, bounds):
        self.surface, self.bounds, self.saved = surface, bounds, None

    def __enter__(self):
        try:
            self.saved = self.surface.get_clip()
            left, top, right, bottom = self.bounds
            self.surface.set_clip(pygame.Rect(left, top, right - left, bottom - top))
        except AttributeError:
            self.saved = None
        return self

    def __exit__(self, *exc):
        if self.saved is not None:
            self.surface.set_clip(self.saved)
        return False


# ----------------------------------------------------------------------
# Building blocks
# ----------------------------------------------------------------------

def rune_ring(fx, cx, cy, radius, color, clock, count=12, speed=0.5, line=True):
    """A ring of turning rune glyphs (with a thin circle through them)."""
    if line:
        fx.circle((cx, cy), radius, with_alpha(color, 150), width=1)
    for i in range(count):
        a = clock * speed + i * math.tau / count
        fx.glyph(cx + math.cos(a) * radius, cy + math.sin(a) * radius, i * 3 + int(clock * 0.0), color)
        mid = a + math.pi / count
        fx.dot(cx + math.cos(mid) * radius, cy + math.sin(mid) * radius, with_alpha(color, 200))


def hexagram(fx, cx, cy, radius, color, rotation):
    """Two interlocked triangles: a sigil."""
    for start in (0, math.pi / 3):
        pts = [(cx + math.cos(rotation + start + k * math.tau / 3) * radius,
                cy + math.sin(rotation + start + k * math.tau / 3) * radius) for k in range(3)]
        for k in range(3):
            fx.line(pts[k], pts[(k + 1) % 3], color)


def jagged_points(cx, cy, radius, seed, count=14, jitter=0.28):
    """The outline of a rough, irregular patch of broken ground."""
    rng = random.Random(seed)
    return [(cx + math.cos(i * math.tau / count) * radius * (1 - jitter + 2 * jitter * rng.random()),
             cy + math.sin(i * math.tau / count) * radius * (1 - jitter + 2 * jitter * rng.random()))
            for i in range(count)]


def crack_points(x, y, angle, length, seed, segments=6, kink=0.55):
    """A jagged crack that wanders away from (x, y)."""
    rng = random.Random(seed)
    pts = [(x, y)]
    seg = length / segments
    for _ in range(segments):
        angle += rng.uniform(-kink, kink)
        x += math.cos(angle) * seg
        y += math.sin(angle) * seg
        pts.append((x, y))
    return pts


def draw_polyline(fx, pts, color, width=1, upto=1.0, soft=False):
    """Draw only the first `upto` (0..1) of a polyline (so cracks can GROW)."""
    total = max(1, len(pts) - 1)
    reach = upto * total
    for i in range(total):
        if i >= reach:
            break
        a, b = pts[i], pts[i + 1]
        if reach - i < 1.0:
            f = reach - i
            b = (a[0] + (b[0] - a[0]) * f, a[1] + (b[1] - a[1]) * f)
        fx.line(a, b, color, width, soft)


def soul_ribbon(fx, a, b, clock, color, seed=0.0, dots=16, amplitude=14.0, reverse=False):
    """A wavy stream of soul-light flowing from a to b."""
    dx, dy = b[0] - a[0], b[1] - a[1]
    length = math.hypot(dx, dy) or 1.0
    nx, ny = -dy / length, dx / length
    for i in range(dots):
        t = (clock * 1.3 + i / float(dots)) % 1.0
        if reverse:
            t = 1 - t
        wave = math.sin(t * math.tau * 2 + seed) * amplitude * math.sin(t * math.pi)
        x = a[0] + dx * t + nx * wave
        y = a[1] + dy * t + ny * wave
        bright = 0.35 + 0.65 * math.sin(t * math.pi)
        fx.dot(x, y, with_alpha(lerp_color((0, 0, 0), color, bright), 255), size=2 if i % 4 == 0 else 1)


def chevron(fx, x, y, angle, size, color):
    """A '>' arrow pointing along `angle`."""
    tip = (x + math.cos(angle) * size, y + math.sin(angle) * size)
    for side in (-1, 1):
        back = (x - math.cos(angle) * size * 0.6 - math.sin(angle) * side * size,
                y - math.sin(angle) * size * 0.6 + math.cos(angle) * side * size)
        fx.line(tip, back, color)


def spike(fx, x, y, angle, length, width, color):
    """A pointed bone spike lying along `angle` from (x, y)."""
    ca, sa = math.cos(angle), math.sin(angle)
    tip = (x + ca * length, y + sa * length)
    left = (x - sa * width, y + ca * width)
    right = (x + sa * width, y - ca * width)
    fx.polygon([tip, left, right], color)


def shock_ring(fx, cx, cy, radius, main, edge, thickness=2, runes=False, clock=0.0):
    """A thick expanding shockwave ring (optionally studded with runes)."""
    fx.circle((cx, cy), radius, edge, width=thickness + 1)
    fx.circle((cx, cy), max(1, radius - PIXEL), main, width=thickness)
    if runes and radius > 24:
        count = max(8, min(40, int(radius * math.tau / 26)))
        for i in range(count):
            a = clock * 0.8 + i * math.tau / count
            fx.glyph(cx + math.cos(a) * (radius + 7), cy + math.sin(a) * (radius + 7), i, main)


def soul_skull(fx, x, y, color, tail_angle=None, flicker=0, big=False):
    """A ghost skull with a dark outline, optionally trailing soul-fire (tail_angle = direction of the tail)."""
    rows = SKULL_BIG if big else SKULL
    if tail_angle is not None:
        count = 8 if big else 5
        for k in range(1, count + 1):
            tx = x + math.cos(tail_angle) * k * 5
            ty = y + math.sin(tail_angle) * k * 5 + math.sin(flicker * 7 + k) * (3 if big else 2)
            tone = with_alpha(lerp_color(color, (0, 0, 0), k / (count + 1.0)), 255)
            fx.dot(tx, ty, OUTLINE, size=4 if (big and k < 5) else 3 if k < 4 else 2)
            fx.dot(tx, ty, tone, size=3 if (big and k < 5) else 2 if k < 4 else 1)
    for dx, dy in ((-PIXEL, 0), (PIXEL, 0), (0, -PIXEL), (0, PIXEL)):         # outline: the skull drawn dark, nudged
        fx.bitmap(x + dx, y + dy, rows, {"#": OUTLINE, "o": OUTLINE})
    fx.bitmap(x, y, rows, {"#": color, "o": OUTLINE})


# ----------------------------------------------------------------------
# One-shot bursts the boss keeps in a list (each has update / alive / draw)
# ----------------------------------------------------------------------

class ShockBurst:
    """An expanding ring of force. Used when the nova fires."""

    def __init__(self, x, y, phase, life=0.5, max_radius=280, runes=True):
        self.x, self.y = x, y
        self.colors = theme(phase)
        self.life, self.max_radius, self.runes = life, max_radius, runes
        self.age = 0.0

    @property
    def alive(self):
        return self.age < self.life

    def update(self, dt):
        self.age += dt

    def draw(self, surface):
        t = self.age / self.life
        radius = self.max_radius * ease_out(t)
        pad = int(radius) + 30
        fx = FxLayer(self.x - pad, self.y - pad, pad * 2, pad * 2)
        fade = 1.0 - t
        main = with_alpha(lerp_color(self.colors["hot"], self.colors["main"], t), 255 * min(1.0, fade * 1.6))
        edge = with_alpha(self.colors["glow"], 255 * fade)
        shock_ring(fx, self.x, self.y, radius, main, edge, thickness=max(1, int(3 * fade) + 1),
                   runes=self.runes, clock=self.age * 3)
        fx.circle((self.x, self.y), radius * 0.92, with_alpha(self.colors["glow"], 70 * fade), soft=True)
        fx.draw(surface)


class GroundCracks:
    """Glowing fissures that race out of a point and then fade (the floor splitting under a blast)."""

    def __init__(self, x, y, phase, life=1.0, count=10, length=230, seed=0.0):
        self.x, self.y = x, y
        self.colors = theme(phase)
        self.life = life
        self.age = 0.0
        rng = random.Random(seed)
        offset = rng.uniform(0, math.tau)
        self.cracks = [crack_points(x, y, offset + i * math.tau / count + rng.uniform(-0.2, 0.2),
                                    length * rng.uniform(0.6, 1.0), rng.random() * 100)
                       for i in range(count)]

    @property
    def alive(self):
        return self.age < self.life

    def update(self, dt):
        self.age += dt

    def draw(self, surface):
        t = self.age / self.life
        grow = ease_out(min(1.0, t * 3.5))
        fade = 1.0 if t < 0.4 else max(0.0, 1.0 - (t - 0.4) / 0.6)
        reach = 250
        fx = FxLayer(self.x - reach, self.y - reach, reach * 2, reach * 2)
        glow = with_alpha(lerp_color(self.colors["hot"], self.colors["glow"], t), 255 * fade)
        dark = with_alpha(OUTLINE, 255 * fade)
        for pts in self.cracks:
            draw_polyline(fx, pts, dark, width=4, upto=grow)
        for pts in self.cracks:
            draw_polyline(fx, pts, glow, width=2, upto=grow)
        for pts in self.cracks:                                        # a hot white core while they are fresh
            if t < 0.45:
                draw_polyline(fx, pts, with_alpha(self.colors["hot"], 255 * (1 - t / 0.45)), width=1, upto=grow)
        fx.draw(surface)
