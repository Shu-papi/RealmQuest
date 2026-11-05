"""
RealmQuest - Surface World (Oakwood Village overworld)
=======================================================
Fantasy-medieval open surface world with three dungeon portals.
Everything is drawn procedurally, so there are NO asset files needed.

Run standalone:      python surface_world.py
Run as a module:     python -m src.maps.surface_world      (if placed in src/maps/)

Controls
    WASD / Arrows : move          E : enter portal / interact
    H : drink potion              M : toggle minimap
    ESC : quit                    F1 : (debug) clear next dungeon    F5 : (debug) reset progress

Hooking into your real dungeon scene
    run(on_enter_dungeon=my_function)
    my_function(dungeon_id) is called when the player enters an unlocked portal
    ("goblin", "berserker" or "lich"). Run your dungeon loop inside it and
    return True if the dungeon was CLEARED (this unlocks the next ones).
"""
import math
import random
import pygame

try:
    from . import village
    from . import world_lore
    from . import minis
    from . import wilds as wilds_mod
    from . import story
    from .save_state import level_progress
except ImportError:
    import village
    import world_lore
    import minis
    import wilds as wilds_mod
    import story
    from save_state import level_progress

# --------------------------------------------------------------------------- #
#  CONFIG - tweak freely
# --------------------------------------------------------------------------- #
SCREEN_W, SCREEN_H = 1280, 720
WORLD_W, WORLD_H = 4400, 3200
FPS = 60
PLAYER_SPEED = 230
INTERACT_DIST = 95

# "requires" = id of the dungeon that must be cleared first (None = always open).
# Strict chain, matching the story: Goblin -> Berserker -> Lich King.
DUNGEONS = [
    dict(id="goblin", name="Goblin Dungeon", level="Requires Lv 3",
         pos=(780, 1030), color=(70, 235, 120), requires=None, min_level=3),
    dict(id="berserker", name="Berserker Warriors Dungeon", level="Requires Lv 7",
         pos=(2060, 930), color=(255, 85, 55), requires="goblin", min_level=7),
    dict(id="lich", name="Lich King Dungeon", level="Requires Lv 12",
         pos=(1400, 330), color=(175, 95, 255), requires="berserker", min_level=12),
]
MINIS = minis.MINIS                     # the six replayable mini dungeons
DUNGEON_BY_ID = {d["id"]: d for d in DUNGEONS + MINIS}

# The Silverrun river across the south, and its two bridges (x, y, deck length, deck width, stone?)
RIVER = [(-40, 2330), (400, 2290), (800, 2380), (1000, 2400), (1300, 2350), (1700, 2440), (2080, 2420),
         (2500, 2380), (2900, 2470), (3300, 2420), (3700, 2500), (4100, 2460), (4440, 2490)]
RIVER_HALF = 40
BRIDGES = [(2080, 2420, 150, 84, True), (1000, 2400, 140, 64, False)]
# Grey cobbled roads: the old north road, the Kingsroad south to Millbrook and the east road
STONE_ROADS = [
    ([(1400, 1530), (1404, 1460), (1408, 1380), (1385, 1150), (1415, 860), (1398, 600), (1400, 420)], 64),
    ([(1930, 1708), (1990, 1880), (2050, 2120), (2080, 2300), (2080, 2420), (2090, 2560), (2140, 2720),
      (2215, 2745)], 58),
    ([(1930, 1708), (2200, 1800), (2500, 1840), (2800, 1800), (3050, 1700), (3250, 1620)], 52),
]
MILLBROOK = (2230, 2770)
DEEP_FOREST = pygame.Rect(2950, 200, 1400, 2000)

AMBIENT = (150, 160, 176)       # darkness level of the world (lower = darker)


def in_deep_forest(x, y):
    return DEEP_FOREST.collidepoint(x, y)


class Progress:
    """Tracks which dungeons are cleared. Persist `cleared` however you like."""

    def __init__(self, cleared=None):
        self.cleared = set(cleared or [])

    def is_unlocked(self, d):
        return d["requires"] is None or d["requires"] in self.cleared


# --------------------------------------------------------------------------- #
#  small helpers
# --------------------------------------------------------------------------- #
def scale_col(c, f):
    return tuple(max(0, min(255, int(v * f))) for v in c[:3])


def lerp_col(a, b, t):
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))


_glow_cache = {}


def glow(radius, color):
    """Soft radial light (black background) for additive blending."""
    key = (radius, tuple(color))
    g = _glow_cache.get(key)
    if g is None:
        g = pygame.Surface((radius * 2, radius * 2))
        for r in range(radius, 0, -2):
            f = (1 - r / radius) ** 2
            pygame.draw.circle(g, (int(color[0] * f), int(color[1] * f), int(color[2] * f)),
                               (radius, radius), r)
        _glow_cache[key] = g
    return g


def make_font(size, bold=False):
    return pygame.font.SysFont("georgia,palatinolinotype,bookantiqua,timesnewroman,serif", size, bold)


def catmull(pts, per=20):
    p = [pts[0]] + list(pts) + [pts[-1]]
    out = []
    for i in range(1, len(p) - 2):
        p0, p1, p2, p3 = p[i - 1], p[i], p[i + 1], p[i + 2]
        for s in range(per):
            t = s / per
            t2, t3 = t * t, t * t * t
            x = 0.5 * ((2 * p1[0]) + (-p0[0] + p2[0]) * t + (2 * p0[0] - 5 * p1[0] + 4 * p2[0] - p3[0]) * t2
                       + (-p0[0] + 3 * p1[0] - 3 * p2[0] + p3[0]) * t3)
            y = 0.5 * ((2 * p1[1]) + (-p0[1] + p2[1]) * t + (2 * p0[1] - 5 * p1[1] + 4 * p2[1] - p3[1]) * t2
                       + (-p0[1] + 3 * p1[1] - 3 * p2[1] + p3[1]) * t3)
            out.append((x, y))
    out.append(tuple(pts[-1]))
    return out


def draw_lock(scr, x, y, s=1.0):
    """Little padlock, centred on x,y."""
    bw, bh = int(22 * s), int(18 * s)
    sw = int(7 * s)
    col = (200, 200, 212)
    th = max(2, int(3 * s))
    pygame.draw.arc(scr, col, (x - sw, y - int(19 * s), sw * 2, int(18 * s)), 0, math.pi, th)
    pygame.draw.line(scr, col, (x - sw, y - int(10 * s)), (x - sw, y - int(2 * s)), th)
    pygame.draw.line(scr, col, (x + sw, y - int(10 * s)), (x + sw, y - int(2 * s)), th)
    body = pygame.Rect(x - bw // 2, y - int(3 * s), bw, bh)
    pygame.draw.rect(scr, (214, 168, 58), body, border_radius=max(2, int(3 * s)))
    pygame.draw.rect(scr, (84, 58, 14), body, max(1, int(2 * s)), border_radius=max(2, int(3 * s)))
    pygame.draw.circle(scr, (50, 32, 8), (x, y + int(4 * s)), max(2, int(3 * s)))
    pygame.draw.rect(scr, (50, 32, 8), (x - max(1, int(s)), y + int(4 * s), max(2, int(2 * s)), int(6 * s)))


# --------------------------------------------------------------------------- #
#  procedural sprites
# --------------------------------------------------------------------------- #
def make_oak(rng):
    w, h = 112, 132
    s = pygame.Surface((w, h), pygame.SRCALPHA)
    bx, by = w // 2, h - 8
    pygame.draw.ellipse(s, (0, 0, 0, 70), (bx - 40, by - 12, 80, 24))
    pygame.draw.rect(s, (66, 44, 26), (bx - 7, by - 44, 14, 40))
    pygame.draw.rect(s, (94, 64, 38), (bx - 7, by - 44, 8, 40))
    pygame.draw.polygon(s, (66, 44, 26), [(bx - 7, by - 6), (bx - 14, by), (bx - 4, by - 2)])
    pygame.draw.polygon(s, (66, 44, 26), [(bx + 7, by - 6), (bx + 14, by), (bx + 4, by - 2)])
    blobs = [(bx + rng.randint(-26, 26), by - 70 + rng.randint(-22, 16), rng.randint(20, 28)) for _ in range(8)]
    blobs.append((bx, by - 72, 30))
    for x, y, r in blobs:
        pygame.draw.circle(s, (14, 40, 22), (x, y), r + 2)
    for x, y, r in blobs:
        pygame.draw.circle(s, (30, 82, 40), (x, y), r)
    for x, y, r in blobs:
        pygame.draw.circle(s, (46, 112, 52), (x - 4, y - 5), int(r * 0.75))
    for x, y, r in blobs:
        pygame.draw.circle(s, (74, 156, 70), (x - 8, y - 10), int(r * 0.4))
    for _ in range(22):
        px, py = bx + rng.randint(-34, 34), by - 72 + rng.randint(-34, 24)
        if 0 <= px < w and 0 <= py < h and s.get_at((px, py))[3] > 0:
            pygame.draw.circle(s, (118, 196, 94), (px, py), rng.choice((1, 2)))
    return s


def make_pine(rng):
    w, h = 92, 150
    s = pygame.Surface((w, h), pygame.SRCALPHA)
    bx, by = w // 2, h - 8
    pygame.draw.ellipse(s, (0, 0, 0, 70), (bx - 30, by - 10, 60, 20))
    pygame.draw.rect(s, (70, 46, 28), (bx - 5, by - 24, 10, 24))
    for i in range(4):
        yb = by - 20 - i * 26
        half = 36 - i * 7
        pygame.draw.polygon(s, (12, 42, 34), [(bx - half - 2, yb + 2), (bx + half + 2, yb + 2), (bx, yb - 44)])
        pygame.draw.polygon(s, (26, 84, 62), [(bx - half, yb), (bx + half, yb), (bx, yb - 42)])
        pygame.draw.polygon(s, (44, 118, 82), [(bx - half, yb), (bx, yb), (bx, yb - 42)])
        pygame.draw.line(s, (90, 160, 120), (bx - half + 3, yb - 2), (bx - 2, yb - 38), 1)
    return s


def make_dead(rng):
    w, h = 120, 150
    s = pygame.Surface((w, h), pygame.SRCALPHA)
    bx, by = w // 2, h - 8
    col = (58, 46, 56)
    pygame.draw.ellipse(s, (0, 0, 0, 70), (bx - 34, by - 10, 68, 20))
    pygame.draw.polygon(s, col, [(bx - 8, by), (bx + 8, by), (bx + 3, by - 62), (bx - 3, by - 62)])
    pygame.draw.line(s, (92, 76, 88), (bx - 3, by - 4), (bx - 1, by - 58), 2)

    def branch(x, y, ang, length, width, depth):
        if depth == 0 or length < 8:
            return
        x2, y2 = x + math.cos(ang) * length, y + math.sin(ang) * length
        pygame.draw.line(s, col, (x, y), (x2, y2), max(1, width))
        for sgn in (-1, 1):
            if depth > 1 or sgn == rng.choice((-1, 1)):
                branch(x2, y2, ang + sgn * rng.uniform(0.35, 0.8), length * 0.74, width - 1, depth - 1)

    branch(bx, by - 58, -math.pi / 2 + rng.uniform(-0.2, 0.2), 32, 6, 5)
    branch(bx, by - 42, -math.pi / 2 - 0.9, 28, 5, 4)
    branch(bx, by - 36, -math.pi / 2 + 0.9, 28, 5, 4)
    return s


def make_gravestone(rng):
    s = pygame.Surface((26, 38), pygame.SRCALPHA)
    pygame.draw.ellipse(s, (0, 0, 0, 80), (0, 28, 26, 10))
    pygame.draw.rect(s, (112, 116, 128), (4, 12, 18, 22))
    pygame.draw.circle(s, (112, 116, 128), (13, 12), 9)
    pygame.draw.rect(s, (150, 154, 166), (4, 12, 4, 22))
    pygame.draw.line(s, (60, 62, 72), (13, 8), (13, 22), 2)
    pygame.draw.line(s, (60, 62, 72), (9, 13), (17, 13), 2)
    pygame.draw.rect(s, (62, 92, 64), (4, 30, 18, 4))
    return s


def make_boulder(rng):
    w = rng.randint(40, 62)
    h = int(w * 0.72)
    s = pygame.Surface((w, h + 8), pygame.SRCALPHA)
    pygame.draw.ellipse(s, (0, 0, 0, 80), (2, h - 8, w - 4, 16))
    pts = [(2, h - 6), (6, h * 0.35), (w * 0.3, 3), (w * 0.7, 5), (w - 3, h * 0.4), (w - 2, h - 6), (w * 0.5, h)]
    pygame.draw.polygon(s, (60, 60, 68), pts)
    pygame.draw.polygon(s, (104, 104, 112), [(p[0] + 1, p[1] + 1) for p in pts[:5]] + [(w * 0.5, h * 0.6)])
    pygame.draw.polygon(s, (140, 140, 150), [(6, h * 0.4), (w * 0.3, 6), (w * 0.5, 8), (w * 0.3, h * 0.5)])
    return s


def make_pillar():
    s = pygame.Surface((32, 92), pygame.SRCALPHA)
    pygame.draw.ellipse(s, (0, 0, 0, 80), (0, 76, 32, 14))
    pygame.draw.rect(s, (60, 66, 62), (2, 68, 28, 14))
    pygame.draw.rect(s, (86, 94, 88), (6, 14, 20, 56))
    pygame.draw.rect(s, (110, 118, 110), (6, 14, 7, 56))
    for y in range(20, 68, 12):
        pygame.draw.line(s, (60, 66, 62), (6, y), (26, y), 1)
    pygame.draw.polygon(s, (86, 94, 88), [(6, 14), (26, 14), (23, 4), (14, 9), (9, 2)])
    pygame.draw.rect(s, (60, 100, 64), (6, 52, 6, 18))
    return s


def make_torch_post():
    s = pygame.Surface((16, 52), pygame.SRCALPHA)
    pygame.draw.ellipse(s, (0, 0, 0, 80), (0, 44, 16, 8))
    pygame.draw.rect(s, (84, 56, 34), (6, 16, 4, 32))
    pygame.draw.polygon(s, (50, 50, 58), [(2, 10), (14, 10), (11, 18), (5, 18)])
    return s


def make_well():
    s = pygame.Surface((68, 80), pygame.SRCALPHA)
    pygame.draw.ellipse(s, (0, 0, 0, 80), (2, 58, 64, 20))
    pygame.draw.rect(s, (96, 98, 106), (8, 50, 52, 16))
    pygame.draw.ellipse(s, (96, 98, 106), (8, 58, 52, 16))
    pygame.draw.ellipse(s, (140, 142, 150), (8, 40, 52, 24))
    pygame.draw.ellipse(s, (30, 58, 100), (15, 44, 38, 15))
    pygame.draw.ellipse(s, (90, 130, 190), (20, 47, 14, 5))
    for x in (10, 52):
        pygame.draw.rect(s, (86, 58, 34), (x, 12, 6, 42))
    pygame.draw.rect(s, (70, 46, 28), (10, 22, 48, 4))
    pygame.draw.polygon(s, (60, 36, 24), [(2, 18), (34, 0), (66, 18)])
    pygame.draw.polygon(s, (150, 64, 52), [(5, 17), (34, 3), (63, 17)])
    pygame.draw.line(s, (200, 110, 90), (8, 15), (34, 5), 2)
    return s


def make_barrel():
    s = pygame.Surface((24, 30), pygame.SRCALPHA)
    pygame.draw.ellipse(s, (0, 0, 0, 80), (0, 22, 24, 8))
    pygame.draw.rect(s, (118, 76, 40), (3, 6, 18, 20), border_radius=4)
    pygame.draw.rect(s, (150, 100, 54), (3, 6, 6, 20), border_radius=4)
    pygame.draw.ellipse(s, (96, 62, 32), (3, 2, 18, 9))
    pygame.draw.ellipse(s, (140, 96, 52), (5, 3, 14, 6))
    for y in (11, 20):
        pygame.draw.line(s, (50, 50, 58), (3, y), (21, y), 2)
    return s


def make_crate():
    s = pygame.Surface((28, 30), pygame.SRCALPHA)
    pygame.draw.ellipse(s, (0, 0, 0, 80), (0, 22, 28, 8))
    pygame.draw.rect(s, (126, 92, 52), (2, 6, 24, 21))
    pygame.draw.rect(s, (78, 54, 28), (2, 6, 24, 21), 2)
    pygame.draw.line(s, (78, 54, 28), (2, 6), (26, 27), 2)
    pygame.draw.line(s, (78, 54, 28), (26, 6), (2, 27), 2)
    return s


def make_fence(length):
    s = pygame.Surface((length, 30), pygame.SRCALPHA)
    pygame.draw.ellipse(s, (0, 0, 0, 50), (0, 22, length, 8))
    pygame.draw.rect(s, (112, 80, 46), (0, 11, length, 4))
    pygame.draw.rect(s, (112, 80, 46), (0, 19, length, 4))
    for x in range(2, length - 2, 22):
        pygame.draw.rect(s, (90, 62, 34), (x, 4, 6, 24))
        pygame.draw.polygon(s, (90, 62, 34), [(x, 4), (x + 6, 4), (x + 3, 0)])
        pygame.draw.rect(s, (130, 96, 56), (x, 4, 2, 24))
    return s


def make_sign(lines, font, accent):
    rendered = [font.render(t, True, (250, 236, 200)) for t in lines]
    bw = max(r.get_width() for r in rendered) + 18
    bh = sum(r.get_height() for r in rendered) + 12
    s = pygame.Surface((bw, bh + 38), pygame.SRCALPHA)
    pygame.draw.ellipse(s, (0, 0, 0, 70), (bw // 2 - 14, bh + 30, 28, 8))
    pygame.draw.rect(s, (84, 56, 34), (bw // 2 - 3, bh - 2, 6, 38))
    pygame.draw.rect(s, (52, 34, 20), (0, 0, bw, bh), border_radius=4)
    pygame.draw.rect(s, (128, 90, 52), (2, 2, bw - 4, bh - 4), border_radius=3)
    pygame.draw.rect(s, accent, (2, 2, bw - 4, bh - 4), 1, border_radius=3)
    y = 6
    for r in rendered:
        s.blit(r, ((bw - r.get_width()) // 2, y))
        y += r.get_height()
    return s


def make_house(w, roof_col, wall_col, rng):
    wh = 62
    rh = int(w * 0.52) + 8
    sw, sh = w + 40, rh + wh + 30
    s = pygame.Surface((sw, sh), pygame.SRCALPHA)
    x0 = (sw - w) // 2
    base = sh - 10
    wall_top = base - wh
    timber = (88, 58, 36)
    pygame.draw.ellipse(s, (0, 0, 0, 80), (x0 - 12, base - 14, w + 24, 30))
    # walls
    pygame.draw.rect(s, wall_col, (x0, wall_top, w, wh))
    pygame.draw.rect(s, scale_col(wall_col, 0.8), (x0, wall_top, w, 12))
    for _ in range(w // 2):
        px, py = rng.randint(x0 + 4, x0 + w - 5), rng.randint(wall_top + 14, base - 14)
        s.set_at((px, py), scale_col(wall_col, 0.9))
    # stone foundation
    pygame.draw.rect(s, (104, 104, 112), (x0 - 2, base - 12, w + 4, 12))
    for i in range(x0, x0 + w, 12):
        pygame.draw.line(s, (78, 78, 88), (i, base - 12), (i, base - 1))
    pygame.draw.line(s, (78, 78, 88), (x0 - 2, base - 6), (x0 + w + 2, base - 6))
    # timber frame
    pygame.draw.rect(s, timber, (x0, wall_top, 6, wh - 12))
    pygame.draw.rect(s, timber, (x0 + w - 6, wall_top, 6, wh - 12))
    pygame.draw.rect(s, timber, (x0, wall_top + 8, w, 4))
    # door
    dw, dh = 22, 36
    dx = x0 + w // 2 - dw // 2
    dy = base - dh
    pygame.draw.circle(s, (56, 34, 18), (dx + dw // 2, dy + 2), dw // 2 + 3)
    pygame.draw.rect(s, (56, 34, 18), (dx - 3, dy + 2, dw + 6, dh - 2))
    pygame.draw.circle(s, (116, 74, 38), (dx + dw // 2, dy + 2), dw // 2)
    pygame.draw.rect(s, (116, 74, 38), (dx, dy + 2, dw, dh - 2))
    for xx in (dx + 7, dx + 14):
        pygame.draw.line(s, (86, 52, 26), (xx, dy - 6), (xx, base - 1), 1)
    pygame.draw.rect(s, (60, 60, 68), (dx, dy + 14, dw, 2))
    pygame.draw.circle(s, (232, 196, 92), (dx + dw - 5, dy + 22), 2)
    # windows with warm light
    wins = []
    ww = 20
    shutter = rng.choice(((60, 110, 90), (70, 90, 140), (130, 60, 56)))
    for wx in (x0 + 14, x0 + w - 14 - ww):
        wy = wall_top + 18
        pygame.draw.rect(s, timber, (wx - 3, wy - 3, ww + 6, ww + 6))
        pygame.draw.rect(s, (255, 206, 110), (wx, wy, ww, ww))
        pygame.draw.rect(s, (255, 238, 176), (wx + 2, wy + 2, ww // 2 - 2, ww // 2 - 2))
        pygame.draw.line(s, timber, (wx + ww // 2, wy), (wx + ww // 2, wy + ww), 2)
        pygame.draw.line(s, timber, (wx, wy + ww // 2), (wx + ww, wy + ww // 2), 2)
        pygame.draw.rect(s, shutter, (wx - 9, wy, 6, ww))
        pygame.draw.rect(s, shutter, (wx + ww + 3, wy, 6, ww))
        pygame.draw.rect(s, (96, 62, 34), (wx - 3, wy + ww + 3, ww + 6, 6))
        for k in range(4):
            pygame.draw.circle(s, rng.choice(((226, 70, 80), (240, 200, 70), (240, 120, 180))),
                               (wx + k * 6, wy + ww + 3), 2)
        wins.append((wx + ww // 2, wy + ww // 2))
    # roof
    yb = wall_top + 8
    yt = yb - rh
    pygame.draw.polygon(s, scale_col(roof_col, 0.5), [(x0 - 16, yb), (x0 + w + 16, yb), (x0 + w - 12, yt), (x0 + 12, yt)])
    pygame.draw.polygon(s, roof_col, [(x0 - 14, yb - 2), (x0 + w + 14, yb - 2), (x0 + w - 11, yt + 2), (x0 + 11, yt + 2)])
    dark, light = scale_col(roof_col, 0.72), scale_col(roof_col, 1.2)
    y, row = yb - 4, 0
    while y > yt + 6:
        t = (yb - y) / (yb - yt)
        xl, xr = int((x0 - 14) + 25 * t), int((x0 + w + 14) - 25 * t)
        pygame.draw.line(s, dark, (xl, y), (xr, y), 2)
        for xx in range(xl + (6 if row % 2 else 0), xr, 12):
            pygame.draw.line(s, dark, (xx, y), (xx, y - 8), 1)
        y -= 8
        row += 1
    pygame.draw.line(s, light, (x0 + 11, yt + 2), (x0 + w - 11, yt + 2), 3)
    pygame.draw.line(s, light, (x0 - 14, yb - 3), (x0 + 11, yt + 2), 2)
    pygame.draw.line(s, scale_col(roof_col, 0.4), (x0 - 14, yb), (x0 + w + 14, yb), 3)
    # chimney
    cxm = x0 + w - 34
    pygame.draw.rect(s, (118, 110, 106), (cxm, yt - 14, 16, 36))
    pygame.draw.rect(s, (90, 84, 82), (cxm - 2, yt - 18, 20, 6))
    for yy in range(yt - 8, yt + 20, 8):
        pygame.draw.line(s, (84, 78, 76), (cxm, yy), (cxm + 16, yy), 1)
    return s, wins, (cxm + 8, yt - 18)


class Prop:
    """A static sprite. (x, gy) = ground contact; `foot` = pixels of sprite below gy."""

    def __init__(self, img, x, gy, foot=0, lights=None):
        self.img = img
        w, h = img.get_size()
        self.rect = pygame.Rect(int(x - w // 2), int(gy + foot - h), w, h)
        self.sort_y = gy
        self.static_lights = lights or []

    def draw(self, scr, cx, cy, t):
        scr.blit(self.img, (self.rect.x - cx, self.rect.y - cy))

    def lights(self, t):
        return self.static_lights


class Torch(Prop):
    IMG = None

    def __init__(self, x, gy):
        if Torch.IMG is None:
            Torch.IMG = make_torch_post()
        super().__init__(Torch.IMG, x, gy, foot=4)
        self.ph = random.random() * 10

    def flick(self, t):
        return 0.82 + 0.18 * math.sin(t * 9 + self.ph) + 0.1 * math.sin(t * 23 + self.ph * 2)

    def draw(self, scr, cx, cy, t):
        super().draw(scr, cx, cy, t)
        fx, fy = self.rect.x + 8 - cx, self.rect.y + 11 - cy
        f = self.flick(t)
        h = int(10 * f) + 7
        pygame.draw.ellipse(scr, (255, 140, 30), (fx - 5, fy - h, 10, h + 5))
        pygame.draw.ellipse(scr, (255, 222, 100), (fx - 3, fy - h + 5, 6, h - 2))

    def lights(self, t):
        r = int(round(150 * self.flick(t) / 10) * 10)
        return [(self.rect.x + 8, self.rect.y + 20, r, (215, 130, 50))]


class Portal:
    R = 58

    def __init__(self, d):
        self.d = d
        self.x, self.y = d["pos"]
        self.color = d["color"]
        self.sort_y = self.y - 140
        self.rect = pygame.Rect(self.x - 100, self.y - 100, 200, 200)
        self.locked = True
        self._init = False
        self.flash = 0.0
        self.shake = 0.0
        self.sparks = []
        self.base_lit = self._make_base(self.color, False)
        self.base_locked = self._make_base((95, 95, 112), True)

    @staticmethod
    def _make_base(color, locked):
        s = pygame.Surface((180, 180), pygame.SRCALPHA)
        c = (90, 90)
        pygame.draw.ellipse(s, (0, 0, 0, 90), (22, 40, 140, 120))
        pygame.draw.circle(s, (46, 52, 62), c, 62)
        pygame.draw.circle(s, (106, 114, 126), c, 59)
        pygame.draw.circle(s, (72, 78, 90), c, 51)
        pygame.draw.circle(s, (14, 18, 26), c, 44)
        for i in range(24):  # stone seams
            a = i * math.pi / 12
            pygame.draw.line(s, (60, 66, 76), (c[0] + math.cos(a) * 51, c[1] + math.sin(a) * 51),
                             (c[0] + math.cos(a) * 59, c[1] + math.sin(a) * 59), 1)
        rune = (62, 62, 74) if locked else color
        core = (92, 92, 106) if locked else lerp_col(color, (255, 255, 255), 0.55)
        for i in range(8):
            a = i * math.pi / 4 + math.pi / 8
            u = (math.cos(a), math.sin(a))
            v = (-u[1], u[0])
            px, py = c[0] + u[0] * 55, c[1] + u[1] * 55
            for sz, col in ((9, (30, 34, 42)), (7, rune), (3, core)):
                pts = [(px + u[0] * sz * sa + v[0] * sz * sb, py + u[1] * sz * sa + v[1] * sz * sb)
                       for sa, sb in ((1, 1), (1, -1), (-1, -1), (-1, 1))]
                pygame.draw.polygon(s, col, pts)
        return s

    def update(self, dt, locked):
        if self._init and self.locked and not locked:
            self.flash = 1.3
            for _ in range(70):
                a = random.random() * math.tau
                sp = random.uniform(60, 220)
                self.sparks.append([self.x, self.y, math.cos(a) * sp, math.sin(a) * sp, 1.2, 1.2])
        self.locked = locked
        self._init = True
        self.flash = max(0.0, self.flash - dt)
        self.shake = max(0.0, self.shake - dt * 1.6)
        if not locked and random.random() < dt * 20:
            a = random.random() * math.tau
            r = random.uniform(0, 40)
            self.sparks.append([self.x + math.cos(a) * r, self.y + math.sin(a) * r * 0.6,
                                random.uniform(-10, 10), random.uniform(-70, -35), 1.4, 1.4])
        for sp in self.sparks:
            sp[0] += sp[2] * dt
            sp[1] += sp[3] * dt
            sp[2] *= (1 - 1.5 * dt) if self.flash > 0 else 1
            sp[4] -= dt
        self.sparks = [s for s in self.sparks if s[4] > 0]

    def lights(self, t):
        if self.locked:
            return [(self.x, self.y, 150, (70, 60, 95))]
        pulse = 0.9 + 0.1 * math.sin(t * 3)
        extra = self.flash * 0.8
        return [(self.x, self.y, 240, scale_col(self.color, 0.95 * pulse + extra))]

    def draw(self, scr, cx, cy, t):
        X, Y = int(self.x - cx), int(self.y - cy)
        if self.shake > 0:
            X += int(math.sin(t * 70) * 5 * self.shake)
        col = self.color
        scr.blit(self.base_locked if self.locked else self.base_lit, (X - 90, Y - 90))
        if not self.locked:
            pulse = 0.85 + 0.15 * math.sin(t * 3)
            pygame.draw.circle(scr, scale_col(col, 0.22), (X, Y), 43)
            scr.blit(glow(50, scale_col(col, 0.75 * pulse)), (X - 50, Y - 50), special_flags=pygame.BLEND_RGB_ADD)
            for arm in range(3):
                for i in range(16):
                    r = 3 + i * 2.5
                    ang = t * 2.2 + arm * 2.094 + i * 0.22
                    px, py = X + math.cos(ang) * r, Y + math.sin(ang) * r
                    pygame.draw.circle(scr, lerp_col((255, 255, 255), col, i / 16), (int(px), int(py)),
                                       max(1, int(3.6 - i * 0.17)))
            for i in range(12):
                a = -t * 0.9 + i * math.tau / 12
                b = 0.6 + 0.4 * math.sin(t * 4 + i)
                pygame.draw.circle(scr, scale_col(col, b + 0.3), (int(X + math.cos(a) * 47), int(Y + math.sin(a) * 47)), 2)
            pygame.draw.circle(scr, lerp_col(col, (255, 255, 255), 0.8), (X, Y), 6)
            scr.blit(glow(22, scale_col(col, 0.9)), (X - 22, Y - 22), special_flags=pygame.BLEND_RGB_ADD)
        else:
            pygame.draw.circle(scr, (12, 12, 20), (X, Y), 43)
            tint = lerp_col((70, 70, 90), col, 0.3)
            for arm in range(2):
                for i in range(12):
                    r = 4 + i * 3
                    ang = t * 0.5 + arm * math.pi + i * 0.25
                    pygame.draw.circle(scr, scale_col(tint, 0.45 + 0.03 * i),
                                       (int(X + math.cos(ang) * r), int(Y + math.sin(ang) * r)), 2)
            self._chain(scr, (X - 56, Y - 34), (X + 56, Y + 34))
            self._chain(scr, (X - 56, Y + 34), (X + 56, Y - 34))
            pygame.draw.circle(scr, (40, 40, 50), (X, Y - 2), 24)
            pygame.draw.circle(scr, (80, 80, 96), (X, Y - 2), 24, 2)
            draw_lock(scr, X, Y + 2, 1.15)
        # sparks
        for x, y, vx, vy, life, mx in self.sparks:
            f = max(0.0, life / mx)
            pygame.draw.circle(scr, scale_col(lerp_col(col, (255, 255, 255), 0.5), f), (int(x - cx), int(y - cy)), 2)
        # unlock shockwave
        if self.flash > 0:
            f = 1 - self.flash / 1.3
            r = int(30 + f * 230)
            tmp = pygame.Surface((r * 2 + 8, r * 2 + 8))
            pygame.draw.circle(tmp, scale_col(col, (1 - f)), (r + 4, r + 4), r, 7)
            scr.blit(tmp, (X - r - 4, Y - r - 4), special_flags=pygame.BLEND_RGB_ADD)

    @staticmethod
    def _chain(scr, p0, p1):
        n = int(math.dist(p0, p1) / 11)
        for i in range(n + 1):
            f = i / max(1, n)
            x, y = p0[0] + (p1[0] - p0[0]) * f, p0[1] + (p1[1] - p0[1]) * f
            rect = (x - 6, y - 3, 12, 6) if i % 2 else (x - 3, y - 6, 6, 12)
            pygame.draw.ellipse(scr, (28, 28, 34), rect, 4)
            pygame.draw.ellipse(scr, (160, 160, 174), rect, 2)


class Cave(Portal):
    """Entrance to a mini dungeon: a dark cave mouth in a mound of rock, glowing in its colour."""

    def __init__(self, d):
        super().__init__(d)
        self.sort_y = self.y + 6
        self.rect = pygame.Rect(self.x - 80, self.y - 90, 160, 120)
        self.mound = self._make_mound(d["color"], d["family"])

    @staticmethod
    def _make_mound(color, family):
        rock = {1: (96, 104, 84), 2: (118, 108, 98), 3: (78, 66, 74)}[family]
        s = pygame.Surface((150, 110), pygame.SRCALPHA)
        pygame.draw.ellipse(s, (0, 0, 0, 90), (8, 84, 134, 24))
        pts = [(8, 96), (22, 52), (46, 28), (75, 18), (104, 28), (128, 52), (142, 96)]
        pygame.draw.polygon(s, scale_col(rock, 0.65), pts)
        pygame.draw.polygon(s, rock, [(14, 92), (26, 54), (48, 32), (75, 23), (102, 32), (124, 54), (136, 92)])
        for x, y, r in ((40, 50, 9), (102, 46, 8), (62, 32, 6), (120, 74, 7), (28, 78, 7)):
            pygame.draw.circle(s, scale_col(rock, 1.18), (x, y), r)
            pygame.draw.circle(s, scale_col(rock, 0.8), (x + 2, y + 3), r - 3)
        if family == 1:     # moss and roots
            for x, y in ((30, 60), (50, 36), (96, 40), (118, 64)):
                pygame.draw.ellipse(s, (70, 120, 56), (x - 8, y - 4, 16, 8))
        elif family == 3:   # bones
            for x, y in ((34, 88), (116, 90)):
                pygame.draw.circle(s, (226, 220, 204), (x, y), 5)
                pygame.draw.rect(s, (20, 14, 18), (x - 2, y - 1, 2, 2))
        pygame.draw.ellipse(s, (6, 6, 10), (48, 52, 54, 50))           # the mouth
        pygame.draw.rect(s, (6, 6, 10), (48, 76, 54, 22))
        pygame.draw.ellipse(s, scale_col(color, 0.35), (56, 66, 38, 30))
        return s

    def lights(self, t):
        pulse = 0.85 + 0.15 * math.sin(t * 2.4 + self.x)
        return [(self.x, self.y - 10, 130, scale_col(self.color, 0.7 * pulse))]

    def draw(self, scr, cx, cy, t):
        X, Y = int(self.x - cx), int(self.y - cy)
        scr.blit(self.mound, (X - 75, Y - 96))
        k = 0.6 + 0.4 * math.sin(t * 3 + self.x)
        for ex in (-8, 8):                       # something looks out of the dark
            if int(t * 0.7 + self.x) % 5:
                scr.fill(scale_col(self.color, 0.6 + 0.4 * k), (X + ex - 2, Y - 34, 4, 3))
        for x, y, vx, vy, life, mx in self.sparks:
            f = max(0.0, life / mx)
            pygame.draw.circle(scr, scale_col(self.color, f), (int(x - cx), int(y - cy) - 30), 2)


DASH_SPEED = 640          # overworld dash (the world is drawn at 0.9x, so this matches the dungeon)


class Player:
    def __init__(self, x, y, look="hero_warrior"):
        self.x, self.y = float(x), float(y)
        self.facing = "up"
        self.flip = False
        self.walk = 0.0
        self.moving = False
        self.face = (0.0, -1.0)              # last direction moved (dash / skills aim this way)
        self.dash_t = 0.0                    # > 0 while dashing
        self.dash_dir = (0.0, 1.0)
        self.speed_k = 1.0                   # class walk speed (Archer is the quickest)
        self.blink = False                   # set by the Game while invulnerable after a hit
        self.set_look(look)
        self.sort_y = y
        self.rect = pygame.Rect(0, 0, 36, 48)

    def set_look(self, look):
        """The hero's outfit: village.LOOKS key (hero_warrior / hero_mage / hero_archer)."""
        self.look = look
        self.frames = village.make_npc_frames(village.LOOKS[look])   # same art style as the villagers

    def feet(self):
        return pygame.Rect(int(self.x) - 9, int(self.y) - 9, 18, 9)

    def draw(self, scr, cx, cy, t):
        if self.blink:
            self.sort_y = self.y
            return
        step = 0
        if self.moving:
            step = 1 if int(self.walk * 6) % 2 == 0 else 2
        img = self.frames[(self.facing, step)]
        if self.facing == "side" and self.flip:
            img = pygame.transform.flip(img, True, False)
        X, Y = int(self.x - cx), int(self.y - cy)
        sh = pygame.Surface((30, 12), pygame.SRCALPHA)
        pygame.draw.ellipse(sh, (0, 0, 0, 90), (0, 0, 30, 12))
        scr.blit(sh, (X - 15, Y - 8))
        bob = -1 if (self.moving and step) else 0
        w, h = img.get_size()
        scr.blit(img, (X - w // 2, Y - h + 4 + bob))
        self.rect.topleft = (int(self.x) - w // 2, int(self.y) - h + 4)
        self.sort_y = self.y

    def lights(self, t):
        return [(int(self.x), int(self.y) - 20, 230, (130, 118, 96))]


# --------------------------------------------------------------------------- #
#  the game / scene
# --------------------------------------------------------------------------- #
class SurfaceWorld:
    def __init__(self, screen, on_enter_dungeon=None, progress=None, save=None, on_talk=None,
                 on_landmark=None, quest_info=None):
        self.screen = screen
        self.on_enter = on_enter_dungeon
        self.progress = progress or Progress()
        self.save = save                  # shared SaveState (gold, flags); None when run standalone
        self.on_talk = on_talk            # on_talk(npc) when the player talks to a villager
        self.npc_alert = None             # npc_alert(npc_id) -> None | "news" | "quest" | "ready"
        self.on_landmark = on_landmark    # on_landmark(obj) for shrines, quest items, hens...
        self.quest_info = quest_info      # quest_info() -> dict for the HUD tracker and minimap
        self.quests = None                # QuestBook (set by the Game)
        self.region, self.region_col, self.region_t = None, (255, 255, 255), 0.0
        self._flags = set()
        self._gold = 0
        self.daynight = village.DayNight()
        self.dyn_colliders = []
        self._dress_stage = None
        self.bursts = []
        self.f_title = make_font(38, True)
        self.f_label = make_font(22, True)
        self.f_hud = make_font(24, True)
        self.f_small = make_font(18, True)
        self.f_sign = make_font(17, True)
        self.clock = pygame.time.Clock()
        self.t = 0.0
        self.hp, self.max_hp, self.potions = 40, 40, 2
        self.state = "play"
        self.fade = 0.0
        self.pending = None
        self.toasts = []
        self.show_map = True
        self.intro = 7.0
        self.fade_surf = pygame.Surface((SCREEN_W, SCREEN_H))
        self.fade_surf.fill((0, 0, 0))
        self.light_surf = pygame.Surface((SCREEN_W, SCREEN_H))
        self.vignette = self._make_vignette()
        self._loading()
        self.build()

    # ------------------------------------------------------------------ build
    def _loading(self):
        self.screen.fill((10, 16, 12))
        img = self.f_title.render("Loading Oakwood Vale...", True, (200, 230, 190))
        self.screen.blit(img, img.get_rect(center=(SCREEN_W // 2, SCREEN_H // 2)))
        pygame.display.flip()
        pygame.event.pump()

    @staticmethod
    def _make_vignette():
        sw, sh = 64, 36
        s = pygame.Surface((sw, sh))
        for y in range(sh):
            for x in range(sw):
                dx, dy = (x / (sw - 1) - 0.5) * 2, (y / (sh - 1) - 0.5) * 2
                d = math.sqrt(dx * dx * 0.8 + dy * dy * 1.1)
                f = max(0.0, min(1.0, (d - 0.45) / 0.9))
                v = int(255 - 125 * f * f)
                s.set_at((x, y), (v, v, v))
        return pygame.transform.smoothscale(s, (SCREEN_W, SCREEN_H))

    def build(self):
        rng = random.Random(7)
        self.rng = rng
        PC = (1400, 1640)
        self.PC = PC
        self.colliders = []
        self.props = []
        self.tree_marks = []
        big_circles = [(PC[0], PC[1], 200)]
        big_rects = []
        sp = Spacing()

        roads = [
            ([(1400, 1700), (1400, 1560), (1408, 1380), (1385, 1150), (1415, 860), (1398, 600), (1400, 420)], 70),
            ([(1408, 1380), (1250, 1260), (1060, 1190), (900, 1140), (800, 1105)], 56),
            ([(1385, 1150), (1600, 1075), (1850, 1020), (2040, 1010), (2060, 1000)], 56),
            ([(1320, 1660), (1130, 1690), (960, 1702), (900, 1708)], 50),
            ([(1480, 1660), (1680, 1690), (1850, 1702), (1930, 1708)], 50),
        ]
        trails = [
            [(842, 1724), (760, 1690), (690, 1620), (650, 1556)],                  # Old Mill
            [(790, 1120), (690, 1160), (600, 1196), (532, 1222)],                  # Shrine of Roots
            [(1975, 1726), (2080, 1702), (2170, 1652), (2226, 1622)],              # the Wall of Names
            [(2170, 1652), (2262, 1520), (2338, 1402), (2384, 1326)],              # Shrine of Dawn
            [(2150, 962), (2262, 880), (2362, 812), (2440, 786)],                  # Shrine of Iron
            [(1398, 600), (1250, 590), (1080, 578), (880, 586)],                   # Shrine of Frost
        ]
        roads = roads[1:] + [
            # dirt roads into the new country
            ([(960, 1702), (990, 1900), (1040, 2120), (1050, 2200)], 46),                       # Thornwood Den
            ([(1050, 2240), (1020, 2330), (1000, 2400), (1040, 2560), (1120, 2720), (1200, 2830)], 46),   # old bridge
            ([(900, 1708), (760, 1830), (600, 1960), (470, 2060)], 44),                          # Mossy Burrow
            ([(2090, 2560), (1800, 2660), (1500, 2770), (1280, 2850)], 46),                      # Old Watchtower
            ([(2292, 2790), (2450, 2795), (2600, 2830), (2720, 2858)], 46),                       # Sunken Crypt
            ([(3250, 1620), (3450, 1450), (3600, 1200), (3700, 950), (3740, 840)], 40),          # Ashen Pit
            ([(3250, 1620), (3500, 1700), (3750, 1760), (3900, 1790)], 40),                      # Bone Hollow
            ([(3450, 1450), (3300, 1150), (3350, 800), (3500, 520)], 36),                        # deep trail north
        ]
        self.roads = [(catmull(p, 20), w) for p, w in roads]
        self.stone_roads = [(catmull(p, 20), w) for p, w in STONE_ROADS]
        self.river = catmull(RIVER, 14)
        # flow direction and bank normal at every river point (for the animated current)
        self.river_flow = []
        rr = random.Random(5)
        for i, (x, y) in enumerate(self.river):
            ax, ay = self.river[max(0, i - 1)]
            bx, by = self.river[min(len(self.river) - 1, i + 1)]
            l = math.hypot(bx - ax, by - ay) or 1.0
            dx, dy = (bx - ax) / l, (by - ay) / l
            under_bridge = any(abs(x - bx_) < wd // 2 + 14 and abs(y - by_) < ln // 2 + 6
                               for bx_, by_, ln, wd, _s in BRIDGES)
            self.river_flow.append((x, y, dx, dy, -dy, dx, rr.random() * 10, under_bridge))
        self.trails = [catmull(p, 16) for p in trails]
        all_pts = [pt for pts, _ in self.roads + self.stone_roads for pt in pts]
        trail_pts = [pt for pts in self.trails for pt in pts]
        # tree canopies reach ~90px up, so keep a wider strip clear on the south side of footpaths
        self.road_cells = self._mark_cells(all_pts, 66) | self._mark_cells(trail_pts, 40) | \
            self._mark_cells([(x, y + 46) for x, y in trail_pts], 40) | \
            self._mark_cells(self.river, RIVER_HALF + 34) | \
            self._mark_cells([(x, y + 50) for x, y in self.river], RIVER_HALF)

        # ---------------------------------------------------------- ground
        g = pygame.Surface((WORLD_W, WORLD_H))
        g.fill((38, 78, 40))
        for _ in range(420):
            v = rng.randint(-6, 6)
            pygame.draw.ellipse(g, (38 + v, 78 + v * 2, 40 + v),
                                (rng.randint(-80, WORLD_W), rng.randint(-80, WORLD_H), rng.randint(80, 260), rng.randint(60, 200)))
        T = 16
        for ty in range(0, WORLD_H, T):
            for tx in range(0, WORLD_W, T):
                v = rng.randint(-7, 7)
                r = pygame.Rect(tx, ty, T, T)
                if v > 0:
                    g.fill((v, v + v // 2, v // 2), r, special_flags=pygame.BLEND_RGB_ADD)
                elif v < 0:
                    g.fill((-v, -v + (-v) // 2, (-v) // 2), r, special_flags=pygame.BLEND_RGB_SUB)
        # region tints
        for d, rad, col, a in (("lich", 650, (40, 18, 60), 130), ("berserker", 480, (96, 80, 66), 80),
                               ("goblin", 420, (14, 44, 24), 70)):
            px, py = DUNGEON_BY_ID[d]["pos"]
            tint = pygame.Surface((rad * 2, rad * 2), pygame.SRCALPHA)
            for r in range(rad, 0, -6):
                pygame.draw.circle(tint, col + (int(a * (1 - r / rad) ** 0.8),), (rad, rad), r)
            g.blit(tint, (px - rad, py - rad))
        # the Deep Forest: darker, bluer ground
        df = DEEP_FOREST
        tint = pygame.Surface((df.w + 400, df.h + 400), pygame.SRCALPHA)
        for i in range(0, 200, 4):
            pygame.draw.rect(tint, (6, 24, 22, int(150 * i / 200)), (i, i, df.w + 400 - 2 * i, df.h + 400 - 2 * i), 4,
                             border_radius=160)
        tint.fill((6, 24, 22, 150), (200, 200, df.w, df.h))
        g.blit(tint, (df.x - 200, df.y - 200))
        # sun-baked patches and ridges in the south (like the old farm country)
        for _ in range(46):
            x, y = rng.randint(200, WORLD_W - 200), rng.randint(2520, WORLD_H - 140)
            if math.dist((x, y), MILLBROOK) < 300:
                continue
            w, h = rng.randint(120, 320), rng.randint(60, 150)
            pygame.draw.ellipse(g, (118, 116, 56), (x - w // 2 - 6, y - h // 2 - 4, w + 12, h + 8))
            pygame.draw.ellipse(g, (150, 138, 72), (x - w // 2, y - h // 2, w, h))
            for _i in range(18):
                g.fill((172, 156, 86), (x + rng.randint(-w // 2 + 8, w // 2 - 8), y + rng.randint(-h // 2 + 6, h // 2 - 6), 3, 2))
        for x0, y0, x1, y1 in ((2650, 2620, 3050, 2700), (3300, 2700, 3900, 2640), (3500, 2950, 4150, 3050),
                               (400, 2650, 800, 2580), (2950, 2160, 3500, 2220)):
            pts = [(x0 + (x1 - x0) * i / 12, y0 + (y1 - y0) * i / 12 + math.sin(i * 1.3) * 16) for i in range(13)]
            pygame.draw.lines(g, (92, 62, 38), False, pts, 9)
            pygame.draw.lines(g, (150, 98, 56), False, [(x, y - 4) for x, y in pts], 4)
            pygame.draw.lines(g, (186, 132, 74), False, [(x, y - 7) for x, y in pts], 2)
        # Millbrook's fields
        self.fields = [pygame.Rect(1820, 2820, 220, 140), pygame.Rect(2380, 2930, 240, 110),
                       pygame.Rect(1600, 2920, 180, 90), pygame.Rect(2600, 2580, 180, 110)]
        for f in self.fields:
            pygame.draw.rect(g, (96, 70, 42), f.inflate(8, 8))
            pygame.draw.rect(g, (124, 92, 56), f)
            for yy in range(f.y + 6, f.bottom - 4, 10):
                pygame.draw.line(g, (96, 70, 42), (f.x + 4, yy + 3), (f.right - 4, yy + 3), 2)
                for xx in range(f.x + 8, f.right - 6, 9):
                    g.fill(rng.choice(((96, 150, 60), (120, 170, 70), (200, 180, 80))), (xx, yy - 1, 3, 3))
        # grass / flowers / pebbles
        for _ in range(8000):
            x, y = rng.randint(0, WORLD_W - 1), rng.randint(0, WORLD_H - 1)
            k = rng.random()
            if in_deep_forest(x, y) and k > 0.55:
                k = 0.3                   # no flowers in the Deep Forest
            if k < 0.55:
                c = rng.choice(((22, 58, 30), (62, 124, 58), (48, 100, 46)))
                for dx in (-2, 0, 2):
                    pygame.draw.line(g, c, (x + dx, y), (x + dx + rng.randint(-1, 1), y - rng.randint(3, 6)), 1)
            elif k < 0.78:
                c = rng.choice(((234, 198, 62), (240, 240, 230), (226, 120, 190)))
                for _i in range(rng.randint(2, 4)):
                    pygame.draw.circle(g, c, (x + rng.randint(-6, 6), y + rng.randint(-4, 4)), 1)
            elif k < 0.86:
                pygame.draw.line(g, (236, 232, 220), (x, y), (x, y + 3), 2)
                pygame.draw.ellipse(g, (196, 52, 50), (x - 3, y - 3, 7, 5))
                g.set_at((x, y - 2), (250, 240, 230))
            else:
                pygame.draw.ellipse(g, (110, 112, 108), (x, y, rng.randint(3, 6), rng.randint(2, 4)))
        # portal stone patches
        for d in DUNGEONS:
            px, py = d["pos"]
            base = {"goblin": (46, 74, 44), "berserker": (84, 74, 70), "lich": (48, 38, 60)}[d["id"]]
            pygame.draw.circle(g, scale_col(base, 0.7), (px, py + 4), 94)
            pygame.draw.circle(g, base, (px, py + 4), 88)
            for _ in range(60):
                a, r = rng.random() * math.tau, rng.random() * 84
                pygame.draw.circle(g, scale_col(base, rng.uniform(0.8, 1.25)), (int(px + math.cos(a) * r), int(py + 4 + math.sin(a) * r)), rng.randint(2, 5))
        # dirt roads and footpaths, then the river, the cobbled roads and the bridges
        self._paint_paths(g, rng, PC)
        self._paint_river(g, rng)
        self._paint_stone_roads(g, rng)
        for bx, by, ln, wd, stone in BRIDGES:
            self._paint_bridge(g, bx, by, ln, wd, stone)
        # mini dungeon clearings
        for m in MINIS:
            mx, my = m["pos"]
            pygame.draw.ellipse(g, (52, 50, 44), (mx - 96, my - 44, 192, 96))
            pygame.draw.ellipse(g, (70, 66, 56), (mx - 88, my - 40, 176, 86))
        # cobbled plaza
        pygame.draw.circle(g, (60, 58, 56), PC, 138)
        pygame.draw.circle(g, (120, 116, 108), PC, 132)
        for _ in range(520):
            a, r = rng.random() * math.tau, math.sqrt(rng.random()) * 126
            c = rng.choice(((142, 138, 128), (98, 94, 90), (130, 124, 114), (108, 104, 98)))
            pygame.draw.ellipse(g, c, (PC[0] + math.cos(a) * r - 6, PC[1] + math.sin(a) * r - 4, rng.randint(8, 13), rng.randint(6, 9)))
        pygame.draw.circle(g, (70, 68, 66), PC, 128, 3)
        pygame.draw.circle(g, (90, 88, 84), PC, 64, 3)
        # darken the world's edge
        edge = pygame.Surface((WORLD_W, WORLD_H), pygame.SRCALPHA)
        for i in range(120):
            a = int(150 * (1 - i / 120) ** 1.5)
            pygame.draw.rect(edge, (4, 10, 8, a), (i, i, WORLD_W - 2 * i, WORLD_H - 2 * i), 1)
        g.blit(edge, (0, 0))
        self.ground = g

        # -------------------------------------------------------- helpers
        def add_prop(img, x, gy, foot=0, col=None, lights=None, radius=22):
            p = Prop(img, x, gy, foot, lights)
            self.props.append(p)
            if col is not None:
                self.colliders.append(pygame.Rect(col))
            sp.add(x, gy, radius)
            return p

        # ---------------------------------------------------------- houses
        roofs = {"red": (168, 62, 50), "blue": (62, 98, 152), "brown": (132, 86, 54),
                 "teal": (54, 124, 112), "plum": (122, 66, 104)}
        walls = [(224, 208, 172), (208, 192, 160), (196, 188, 172)]
        houses = [
            (1180, 1560, 130, "red"), (1640, 1560, 130, "blue"),
            (1150, 1790, 120, "brown"), (1650, 1790, 120, "teal"),
            (858, 1598, 100, "plum"), (1946, 1596, 100, "brown"),     # beside the west / east crossroads
            (1400, 1930, 190, "red"),
            (1295, 1460, 100, "teal"), (1505, 1460, 100, "plum"),
            # Millbrook, the hamlet across the river
            (MILLBROOK[0] - 240, MILLBROOK[1] - 50, 100, "red"), (MILLBROOK[0] + 130, MILLBROOK[1] - 70, 96, "brown"),
            (MILLBROOK[0] - 110, MILLBROOK[1] + 120, 110, "red"), (MILLBROOK[0] + 110, MILLBROOK[1] + 126, 90, "red"),
            (MILLBROOK[0] + 275, MILLBROOK[1] - 40, 90, "brown"),
        ]
        self.house_rects = []
        self.smokes = []
        smoke_rng = random.Random(23)
        for hx, hy, hw, rk in houses:
            img, wins, chim = make_house(hw, roofs[rk], rng.choice(walls), rng)
            sw, sh = img.get_size()
            lights = [(hx - sw // 2 + wx, hy + 16, 80, (150, 100, 40)) for wx, wy in wins]
            prop = add_prop(img, hx, hy, foot=10, col=(hx - hw // 2, hy - 46, hw, 46), lights=lights, radius=hw // 2)
            prop._kind = "house"
            self.smokes.append(village.SmokePlume(prop.rect.x + chim[0], prop.rect.y + chim[1], smoke_rng))
            big_rects.append(pygame.Rect(hx - hw // 2 - 70, hy - sh - 20, hw + 140, sh + 20 + 80))
            self.house_rects.append(pygame.Rect(hx - hw // 2, hy - 46, hw, 46))

        # ----------------------------------------------------------- props
        add_prop(make_well(), PC[0], PC[1] + 20, foot=4, col=(PC[0] - 28, PC[1] - 8, 56, 28))._kind = "plaza well"
        for dx, dy in ((-105, -60), (105, -60), (-105, 70), (105, 70), (-62, 150), (62, 150)):
            t = Torch(PC[0] + dx, PC[1] + dy)
            self.props.append(t)
            self.colliders.append(pygame.Rect(t.rect.x + 5, t.rect.bottom - 14, 6, 8))
            sp.add(PC[0] + dx, PC[1] + dy, 14)
        for tx, ty in ((1350, 1380), (1460, 1380)):
            t = Torch(tx, ty)
            self.props.append(t)
            sp.add(tx, ty, 14)
        barrel, crate = make_barrel(), make_crate()
        for x, y, img in ((1270, 1930, barrel), (1246, 1940, crate), (1532, 1930, barrel), (1556, 1938, barrel),
                          (1118, 1580, barrel), (1700, 1578, crate), (1096, 1810, crate), (1708, 1812, barrel),
                          (1325, 1470, barrel), (1478, 1472, crate)):
            add_prop(img, x, y, foot=2, col=(x - 10, y - 10, 20, 12), radius=14)
        for x, y, ln in ((1118, 1852, 150), (1650, 1850, 150)):
            f = make_fence(ln)
            add_prop(f, x, y, foot=2, col=(x - ln // 2, y - 8, ln, 8), radius=ln // 2)._kind = "fence"

        # dungeon decor: torches + broken pillars + signs
        pil = make_pillar()
        for d in DUNGEONS:
            px, py = d["pos"]
            for dx in (-86, 86):
                t = Torch(px + dx, py + 44)
                self.props.append(t)
                self.colliders.append(pygame.Rect(t.rect.x + 5, t.rect.bottom - 14, 6, 8))
                sp.add(px + dx, py + 44, 14)
            for dx in (-132, 132):
                add_prop(pil, px + dx, py - 20, foot=8, col=(px + dx - 14, py - 28, 28, 14), radius=22)
            big_circles.append((px, py, 175))
        for m in MINIS:
            mx, my = m["pos"]
            t = Torch(mx - 92, my + 26)
            self.props.append(t)
            self.colliders.append(pygame.Rect(t.rect.x + 5, t.rect.bottom - 14, 6, 8))
            self.colliders.append(pygame.Rect(mx - 66, my - 40, 132, 30))       # the rock mound
            sp.add(mx, my, 70)
            big_circles.append((mx, my + 20, 170))
        for f in self.fields:
            big_rects.append(f.inflate(60, 120))
        big_circles.append((MILLBROOK[0], MILLBROOK[1], 330))
        add_prop(make_well(), MILLBROOK[0], MILLBROOK[1] + 40, foot=4,
                 col=(MILLBROOK[0] - 28, MILLBROOK[1] + 12, 56, 28))._kind = "well"
        signs = [
            (860, 1200, ["Goblin Dungeon", "Requires Lv 3"], DUNGEON_BY_ID["goblin"]["color"]),
            (1930, 1085, ["Berserker Warriors", "Requires Lv 7"], DUNGEON_BY_ID["berserker"]["color"]),
            (1472, 520, ["Lich King Dungeon", "Requires Lv 12"], DUNGEON_BY_ID["lich"]["color"]),
            (2050, 1890, ["Kingsroad", "Millbrook  south"], (210, 205, 190)),
            (3080, 1760, ["Deep Forest", "Beware!"], (255, 120, 100)),
            (2290, 2650, ["Millbrook"], (232, 200, 120)),
            (900, 1840, ["Caves  south-west"], (180, 220, 140)),
            (1470, 1545, ["Oakwood Village"], (232, 200, 120)),
            (1515, 1968, ["Tavern"], (232, 200, 120)),
            (872, 1756, ["Old Mill", "<- west"], (200, 190, 160)),
            (2010, 1758, ["Veil's Edge", "east ->"], (170, 200, 255)),
            (1334, 652, ["Shrine of Frost", "<- west"], (150, 190, 255)),
        ]
        # the whole house sprite (roof included), so no sign ends up drawn over a roof
        house_rects = [p.rect.inflate(20, 24) for p in self.props if getattr(p, "_kind", "") == "house"]
        # things the village adds later: the sheep meadow, the two market stalls, the refugee camp
        mx, my = village.MEADOW
        house_rects += [pygame.Rect(mx - 115, my - 130, 230, 240), pygame.Rect(1130, 1540, 140, 110),
                        pygame.Rect(1530, 1540, 140, 110), pygame.Rect(village.CAMP[0] - 110, village.CAMP[1] - 80, 220, 140)]
        # the actual road surface (8 px cells), so signs can stand right at the roadside
        lane = set()

        def mark(pts, half):
            for x, y in pts[::2]:
                for dx in range(-half, half + 1, 6):
                    for dy in range(-half, half + 1, 6):
                        if dx * dx + dy * dy <= half * half:
                            lane.add((int(x + dx) // 8, int(y + dy) // 8))
        for pts, w in self.roads + self.stone_roads:
            mark(pts, w // 2 + 8)
        for pts in self.trails:
            mark(pts, 18)
        mark(self.river, RIVER_HALF + 12)
        mark([PC], 142)

        def clear(rect):
            foot = pygame.Rect(rect.x, rect.y, rect.w, rect.h - 28)        # the board and its post
            for cx in range(foot.left // 8, foot.right // 8 + 1):
                for cy in range(foot.top // 8, foot.bottom // 8 + 1):
                    if (cx, cy) in lane:
                        return False
            return rect.collidelist(house_rects) == -1 and rect.collidelist(self.colliders) == -1

        def roadside(x, y, img):
            """Nearest spot to (x, y) where the whole sign stands clear of roads, rivers and houses."""
            w, h = img.get_size()
            for r in range(0, 420, 10):
                for i in range(max(1, r // 6)):
                    a = i * math.tau / max(1, r // 6)
                    nx, ny = int(x + math.cos(a) * r), int(y + math.sin(a) * r * 0.8)
                    if clear(pygame.Rect(nx - w // 2, ny + 34 - h, w, h)):
                        return nx, ny
            return x, y

        for x, y, lines, col in signs:
            img = make_sign(lines, self.f_sign, col)
            x, y = roadside(x, y, img)
            add_prop(img, x, y, foot=36 - 2, col=(x - 5, y - 8, 10, 8), radius=26)._kind = "sign"
            house_rects.append(self.props[-1].rect.inflate(16, 8))      # signs don't stack on each other
            # trees south of a sign would hide it behind their canopy
            big_rects.append(pygame.Rect(x - 90, y - 20, 180, 150))

        # ------------------------------------------- villagers, critters, story
        village.reserve(big_circles)
        world_lore.reserve(big_circles)
        wilds_mod.reserve(big_circles)
        village.populate(self, add_prop, random.Random(11), make_fence)
        world_lore.populate(self, add_prop, random.Random(13))

        # ----------------------------------------------------- scatter rocks
        boulders = [make_boulder(rng) for _ in range(5)]
        for _ in range(900):
            if sum(1 for p in self.props if getattr(p, "_rock", False)) >= 22:
                break
            x, y = rng.randint(1750, 2650), rng.randint(500, 1350)
            if self._free(x, y, 40, sp, big_circles, big_rects):
                img = rng.choice(boulders)
                p = add_prop(img, x, y, foot=8, col=(x - img.get_width() // 2 + 4, y - 14, img.get_width() - 8, 14), radius=34)
                p._rock = True
        for _ in range(1400):
            if sum(1 for p in self.props if getattr(p, "_rock", False)) >= 54:
                break
            x, y = rng.randint(300, WORLD_W - 300), rng.randint(2150, WORLD_H - 150)
            if self._free(x, y, 40, sp, big_circles, big_rects):
                img = rng.choice(boulders)
                p = add_prop(img, x, y, foot=8, col=(x - img.get_width() // 2 + 4, y - 14, img.get_width() - 8, 14), radius=34)
                p._rock = True
        gravestone = make_gravestone(rng)
        n = 0
        for _ in range(900):
            if n >= 14:
                break
            x, y = rng.randint(900, 1900), rng.randint(140, 620)
            if self._free(x, y, 30, sp, big_circles, big_rects) and math.dist((x, y), (1400, 330)) < 560:
                add_prop(gravestone, x, y, foot=4, col=(x - 8, y - 10, 16, 10), radius=22)
                n += 1

        # -------------------------------------------------------------- trees
        oaks = [make_oak(rng) for _ in range(5)]
        pines = [make_pine(rng) for _ in range(4)]
        deads = [make_dead(rng) for _ in range(4)]

        def pick(x, y):
            if in_deep_forest(x, y):
                r = rng.random()
                return ("pine", rng.choice(pines)) if r < 0.55 else (("dead", rng.choice(deads)) if r < 0.75
                                                                    else ("oak", rng.choice(oaks)))
            dl = math.dist((x, y), DUNGEON_BY_ID["lich"]["pos"])
            db = math.dist((x, y), DUNGEON_BY_ID["berserker"]["pos"])
            r = rng.random()
            if dl < 650:
                return ("dead", rng.choice(deads)) if r < 0.6 else (("pine", rng.choice(pines)) if r < 0.85 else ("oak", rng.choice(oaks)))
            if db < 600 or x > 1900:
                return ("pine", rng.choice(pines)) if r < 0.65 else ("oak", rng.choice(oaks))
            return ("pine", rng.choice(pines)) if r < 0.15 else ("oak", rng.choice(oaks))

        def place_tree(x, y, force=False):
            kind, img = pick(x, y)
            p = Prop(img, x, y, foot=8)
            self.props.append(p)
            self.colliders.append(pygame.Rect(x - 9, y - 12, 18, 12))
            sp.add(x, y, 26)
            self.tree_marks.append((x, y, kind))

        # border forest
        for x in range(10, WORLD_W, 64):
            for row, yy in enumerate((40, 110)):
                place_tree(x + rng.randint(-14, 14), yy + rng.randint(-8, 14))
                place_tree(x + rng.randint(-14, 14), WORLD_H - 20 - row * 70 + rng.randint(-8, 8))
        for y in range(150, WORLD_H - 100, 64):
            for row, xx in enumerate((40, 110)):
                place_tree(xx + rng.randint(-8, 14), y + rng.randint(-14, 14))
                place_tree(WORLD_W - xx + rng.randint(-14, 8), y + rng.randint(-14, 14))
        # open forest
        for _ in range(14000):
            x, y = rng.randint(160, WORLD_W - 160), rng.randint(180, WORLD_H - 120)
            dens = 0.40
            if x < 1150 and 600 < y < 1500:
                dens = 0.85
            elif in_deep_forest(x, y):
                dens = 0.88
            elif y > 2250:
                dens = 0.26
            if math.dist((x, y), PC) < 520:
                dens = 0.12
            if not self._free(x, y, 26, sp, big_circles, big_rects, trees=True):
                continue
            if rng.random() < dens:
                place_tree(x, y)

        self.portals = [Portal(d) for d in DUNGEONS] + [Cave(m) for m in MINIS]
        # the river can only be crossed on its bridges
        for x, y in self.river[::2]:
            if any(abs(x - bx) < wd // 2 + 6 and abs(y - by) < ln // 2 + 10 for bx, by, ln, wd, _s in BRIDGES):
                continue
            self.colliders.append(pygame.Rect(int(x) - 12, int(y) - RIVER_HALF + 8, 24, RIVER_HALF * 2 - 10))
        for bx, by, ln, wd, _s in BRIDGES:
            for side in (bx - wd // 2 - 2, bx + wd // 2 - 6):
                self.colliders.append(pygame.Rect(side, by - ln // 2, 8, ln))
        self.torches = [p for p in self.props if isinstance(p, Torch)]
        self.player = Player(1400, 1710)
        self.fireflies = [(rng.randint(60, WORLD_W - 60), rng.randint(60, WORLD_H - 60),
                           rng.random() * 10, rng.uniform(0.4, 1.0)) for _ in range(420)]
        self._build_minimap()

    # ------------------------------------------------------------ builders
    @staticmethod
    def _mark_cells(pts, r, cell=32):
        cells = set()
        n = int(r // cell) + 1
        for (x, y) in pts:
            cx, cy = int(x // cell), int(y // cell)
            for dx in range(-n, n + 1):
                for dy in range(-n, n + 1):
                    mx, my = (cx + dx) * cell + cell / 2, (cy + dy) * cell + cell / 2
                    if (mx - x) ** 2 + (my - y) ** 2 <= (r + cell * 0.5) ** 2:
                        cells.add((cx + dx, cy + dy))
        return cells

    def _free(self, x, y, r, sp, big_circles, big_rects, trees=False):
        if (int(x // 32), int(y // 32)) in self.road_cells:
            return False
        for (cx, cy, cr) in big_circles:
            if (x - cx) ** 2 + (y - cy) ** 2 < cr * cr:
                return False
        for rc in big_rects:
            if rc.collidepoint(x, y):
                return False
        if math.dist((x, y), (1400, 1710)) < 120:
            return False
        return sp.free(x, y, r)

    def _paint_paths(self, g, rng, PC):
        """Roads: soil edge, grass fringe, wheel ruts, cobbles near the village, puddles.
        Footpaths: narrow trodden trails with stepping stones."""
        def normals(pts):
            out = []
            for i in range(len(pts)):
                a, b = pts[max(0, i - 1)], pts[min(len(pts) - 1, i + 1)]
                dx, dy = b[0] - a[0], b[1] - a[1]
                l = math.hypot(dx, dy) or 1.0
                out.append((-dy / l, dx / l))
            return out

        # 1) soft dark soil edge under everything, slightly wobbly
        for pts in self.trails:
            for i, (x, y) in enumerate(pts):
                pygame.draw.circle(g, (64, 70, 38), (int(x), int(y)), 17 + int(math.sin(i * 0.7) * 2))
        for k, (pts, w) in enumerate(self.roads):
            for i, (x, y) in enumerate(pts):
                r = w // 2 + 6 + int(math.sin(i * 0.37 + k) * 2.5 + math.sin(i * 0.11) * 2)
                pygame.draw.circle(g, (70, 54, 34), (int(x), int(y)), r)
        # 2) path surfaces
        for pts in self.trails:
            for i, (x, y) in enumerate(pts):
                pygame.draw.circle(g, (124, 104, 68), (int(x), int(y)), 13 + int(math.sin(i * 0.9) * 1.5))
        for k, (pts, w) in enumerate(self.roads):
            for i, (x, y) in enumerate(pts):
                r = w // 2 + int(math.sin(i * 0.37 + k) * 2 + math.sin(i * 0.11) * 1.5)
                pygame.draw.circle(g, (140, 106, 68), (int(x), int(y)), r)
            for (x, y) in pts:                                    # lighter crown
                pygame.draw.circle(g, (156, 122, 80), (int(x), int(y)), int(w * 0.3))
        # 3) road detail
        for k, (pts, w) in enumerate(self.roads):
            ns = normals(pts)
            for i, ((x, y), (nx, ny)) in enumerate(zip(pts, ns)):
                near = math.dist((x, y), PC)
                if near < 300:                                    # cobbles fading out from the plaza
                    if rng.random() < (300 - near) / 300 * 1.6:
                        for _ in range(3):
                            a, r = rng.random() * math.tau, math.sqrt(rng.random()) * w * 0.46
                            c = rng.choice(((132, 126, 116), (110, 106, 100), (146, 140, 128), (120, 112, 100)))
                            px, py = x + math.cos(a) * r, y + math.sin(a) * r
                            pygame.draw.ellipse(g, (78, 72, 66), (px - 6, py - 4, 12, 9))
                            pygame.draw.ellipse(g, c, (px - 5, py - 4, 10, 7))
                    continue
                for side in (-1, 1):                              # wheel ruts
                    off = w * 0.22 * side
                    pygame.draw.circle(g, (118, 88, 54), (int(x + nx * off), int(y + ny * off)), 2)
                if i % 2 == 0:                                    # pebbles and texture
                    a, r = rng.random() * math.tau, rng.random() * w * 0.45
                    c = rng.choice(((122, 92, 58), (170, 136, 94), (108, 80, 50), (150, 146, 136)))
                    pygame.draw.circle(g, c, (int(x + math.cos(a) * r), int(y + math.sin(a) * r)), rng.randint(1, 3))
                if i % 3 == 0:                                    # grass creeping over the edges
                    for side in (-1, 1):
                        ex, ey = x + nx * (w / 2 + 1) * side, y + ny * (w / 2 + 1) * side
                        col = rng.choice(((48, 96, 44), (64, 122, 56), (40, 84, 40)))
                        for dx in (-3, -1, 1, 3):
                            pygame.draw.line(g, col, (ex + dx, ey + 2), (ex + dx + rng.randint(-2, 2), ey - rng.randint(3, 7)), 1)
                if i % 37 == 11 and rng.random() < 0.35:          # the odd puddle
                    px, py = x + nx * w * 0.12, y + ny * w * 0.12
                    pygame.draw.ellipse(g, (92, 74, 50), (px - 13, py - 6, 26, 13))
                    pygame.draw.ellipse(g, (78, 104, 120), (px - 11, py - 5, 22, 10))
                    pygame.draw.line(g, (150, 180, 196), (px - 6, py - 2), (px + 2, py - 3), 1)
        # 4) footpath detail: worn centre, grass tufts, stepping stones
        for pts in self.trails:
            for i, (x, y) in enumerate(pts):
                if i % 2 == 0:
                    pygame.draw.circle(g, (140, 118, 78), (int(x + rng.randint(-3, 3)), int(y + rng.randint(-2, 2))), 4)
                if i % 5 == 0:
                    a, r = rng.random() * math.tau, rng.random() * 9
                    gx, gy = x + math.cos(a) * r, y + math.sin(a) * r
                    for dx in (-2, 0, 2):
                        pygame.draw.line(g, (70, 118, 58), (gx + dx, gy), (gx + dx, gy - rng.randint(3, 5)), 1)
                if i % 9 == 4:
                    pygame.draw.ellipse(g, (88, 86, 82), (x - 7, y - 4, 14, 9))
                    pygame.draw.ellipse(g, (150, 146, 138), (x - 6, y - 4, 12, 7))

    def _paint_river(self, g, rng):
        pts = self.river
        for x, y in pts:
            pygame.draw.circle(g, (120, 104, 66), (int(x), int(y)), RIVER_HALF + 12)
        for x, y in pts:
            pygame.draw.circle(g, (176, 156, 104), (int(x), int(y)), RIVER_HALF + 6)
        for x, y in pts:
            pygame.draw.circle(g, (44, 80, 136), (int(x), int(y)), RIVER_HALF)
        for x, y in pts:
            pygame.draw.circle(g, (60, 104, 166), (int(x), int(y) - 2), RIVER_HALF - 10)
        for i, (x, y) in enumerate(pts):
            if i % 3 == 0:
                off = rng.randint(-RIVER_HALF + 14, RIVER_HALF - 14)
                pygame.draw.line(g, (130, 176, 220), (x - 10, y + off), (x + rng.randint(4, 16), y + off), 2)
            if i % 7 == 0:
                g.fill((200, 226, 246), (int(x), int(y) + rng.randint(-20, 20), 3, 2))

    def draw_river_flow(self, scr, camx, camy, t):
        """The Silverrun's current: light streaks drifting downstream, glints and bank foam."""
        x0, x1 = camx - 60, camx + SCREEN_W + 60
        y0, y1 = camy - 60, camy + SCREEN_H + 60
        hi, mid, foam = (150, 196, 236), (104, 150, 206), (214, 232, 246)
        for x, y, dx, dy, nx, ny, ph, covered in self.river_flow:
            if covered or not (x0 < x < x1 and y0 < y < y1):
                continue
            sx, sy = x - camx, y - camy
            for lane, spd, ln, col in ((-14, 46, 12, mid), (9, 60, 16, hi), (22, 38, 9, mid)):
                k = (t * spd / 14.0 + ph + lane * 0.13) % 1.0         # 0..1 along this segment
                if k > 0.7:
                    continue
                along = (k - 0.35) * 14
                cx_, cy_ = sx + dx * along + nx * lane, sy + dy * along + ny * lane
                pygame.draw.line(scr, col, (cx_, cy_), (cx_ + dx * ln * (0.7 - k), cy_ + dy * ln * (0.7 - k)), 2)
            if int(t * 3 + ph * 7) % 9 == 0:                          # a glint
                g = (ph * 13.7) % 1.0
                scr.fill((236, 246, 255), (int(sx + nx * (g - 0.5) * 50), int(sy + ny * (g - 0.5) * 50), 2, 2))
            w = math.sin(t * 2.2 + ph * 3)                            # foam lapping at both banks
            for side in (-1, 1):
                bxp = sx + nx * side * (RIVER_HALF - 3 + w * 2)
                byp = sy + ny * side * (RIVER_HALF - 3 + w * 2)
                if (int(ph * 10) + side) % 2 == 0:
                    pygame.draw.line(scr, foam, (bxp - dx * 4, byp - dy * 4), (bxp + dx * 4, byp + dy * 4), 1)

    def _paint_stone_roads(self, g, rng):
        """Grey cobbled roads with a dark kerb, like the old king's highways."""
        for pts, w in self.stone_roads:
            for x, y in pts:
                pygame.draw.circle(g, (66, 64, 60), (int(x), int(y)), w // 2 + 5)
        for pts, w in self.stone_roads:
            for x, y in pts:
                pygame.draw.circle(g, (138, 134, 124), (int(x), int(y)), w // 2)
        for pts, w in self.stone_roads:
            for i, (x, y) in enumerate(pts):
                for _ in range(7):
                    a, r = rng.random() * math.tau, math.sqrt(rng.random()) * (w / 2 - 4)
                    px, py = x + math.cos(a) * r, y + math.sin(a) * r
                    c = rng.choice(((156, 152, 142), (120, 116, 108), (146, 140, 128), (128, 124, 118), (166, 160, 148)))
                    pygame.draw.ellipse(g, (92, 88, 82), (px - 6, py - 4, 13, 9))
                    pygame.draw.ellipse(g, c, (px - 5, py - 4, 11, 7))
                if i % 4 == 0:      # moss in the cracks
                    a, r = rng.random() * math.tau, rng.random() * w * 0.45
                    g.fill((86, 118, 70), (int(x + math.cos(a) * r), int(y + math.sin(a) * r), 3, 2))

    def _paint_bridge(self, g, x, y, length, width, stone):
        r = pygame.Rect(x - width // 2, y - length // 2, width, length)
        pygame.draw.rect(g, (24, 44, 70), r.move(6, 8))                      # shadow on the water
        if stone:
            pygame.draw.rect(g, (96, 92, 86), r)
            for yy in range(r.y + 4, r.bottom - 4, 12):
                for xx in range(r.x + 10 + (6 if (yy // 12) % 2 else 0), r.right - 10, 14):
                    pygame.draw.rect(g, (150, 146, 136), (xx, yy, 12, 10))
                    pygame.draw.rect(g, (112, 108, 100), (xx, yy + 8, 12, 2))
            rail = (176, 172, 160)
        else:
            pygame.draw.rect(g, (84, 58, 34), r)
            for yy in range(r.y + 2, r.bottom - 2, 9):
                pygame.draw.rect(g, (138, 98, 58), (r.x + 8, yy, width - 16, 7))
                pygame.draw.line(g, (96, 66, 38), (r.x + 8, yy + 7), (r.right - 8, yy + 7), 1)
            rail = (120, 84, 50)
        for side in (r.x, r.right - 8):                                        # parapets
            pygame.draw.rect(g, (50, 46, 42), (side, r.y - 4, 8, length + 8))
            pygame.draw.rect(g, rail, (side + 1, r.y - 4, 6, length + 6))

    def _build_minimap(self):
        self.mm_w, self.mm_h = 264, 192
        self.mm_scale = min(self.mm_w / WORLD_W, self.mm_h / WORLD_H)
        s = pygame.Surface((self.mm_w, self.mm_h))
        s.fill((14, 34, 20))
        k = self.mm_scale
        for d, col in (("lich", (34, 22, 44)), ("berserker", (52, 46, 40)), ("goblin", (14, 42, 24))):
            px, py = DUNGEON_BY_ID[d]["pos"]
            pygame.draw.circle(s, col, (int(px * k), int(py * k)), int(420 * k))
        df = DEEP_FOREST
        s.fill((10, 30, 26), (int(df.x * k), int(df.y * k), int(df.w * k), int(df.h * k)))
        for x, y, kind in self.tree_marks[::2]:
            c = {"oak": (30, 86, 40), "pine": (24, 70, 56), "dead": (70, 56, 70)}[kind]
            s.fill(c, (int(x * k), int(y * k), 2, 2))
        for pts in self.trails:
            for a, b in zip(pts[::4], pts[4::4]):
                pygame.draw.line(s, (130, 112, 80), (a[0] * k, a[1] * k), (b[0] * k, b[1] * k), 1)
        for a, b in zip(self.river[::3], self.river[3::3]):
            pygame.draw.line(s, (70, 120, 190), (a[0] * k, a[1] * k), (b[0] * k, b[1] * k), 4)
        for pts, w in self.roads:
            for a, b in zip(pts[::6], pts[6::6]):
                pygame.draw.line(s, (170, 136, 92), (a[0] * k, a[1] * k), (b[0] * k, b[1] * k), 2)
        for pts, w in self.stone_roads:
            for a, b in zip(pts[::6], pts[6::6]):
                pygame.draw.line(s, (196, 192, 182), (a[0] * k, a[1] * k), (b[0] * k, b[1] * k), 2)
        for f in self.fields:
            s.fill((150, 120, 70), (int(f.x * k), int(f.y * k), max(2, int(f.w * k)), max(2, int(f.h * k))))
        pygame.draw.circle(s, (150, 146, 136), (int(self.PC[0] * k), int(self.PC[1] * k)), 5)
        for r in self.house_rects:
            s.fill((220, 170, 120), (int(r.centerx * k) - 2, int(r.centery * k) - 2, 5, 4))
        self.mm_static = s

    # ------------------------------------------------------------- gameplay
    def toast(self, text, color=(240, 230, 200)):
        self.toasts = self.toasts[-2:] + [[story.named(text), color, 4.0]]

    # shared state (SaveState when running inside the game, local otherwise)
    def stage(self):
        return sum(1 for d in DUNGEONS if d["id"] in self.progress.cleared)

    def has_flag(self, f):
        return f in (self.save.flags if self.save else self._flags)

    def set_flag(self, f):
        (self.save.flags if self.save else self._flags).add(f)

    @property
    def gold(self):
        return self.save.gold if self.save else self._gold

    def add_gold(self, n):
        if self.save:
            self.save.gold += n
        else:
            self._gold += n

    def quest_active(self, item):
        return bool(self.quests and self.quests.active(item))

    def talkers(self):
        merlin = [self.merlin] if getattr(self, "merlin", None) else []
        return self.npcs + (self.refugees if self.stage() >= 2 else []) + merlin

    def nearest_interactable(self):
        """('npc'|'treasure'|'portal', obj) closest to the player, or (None, None)."""
        px, py = self.player.x, self.player.y
        best, bd = (None, None), 1e9
        for n in self.talkers():
            d = math.dist((px, py), (n.x, n.y))
            if d < 62 and d < bd:
                best, bd = ("npc", n), d
        for tr in self.treasures:
            if not tr.opened_cache:
                d = math.dist((px, py), (tr.x, tr.y))
                if d < 56 and d < bd:
                    best, bd = ("treasure", tr), d
        for lm in self.landmarks + self.hens:
            if lm.available(self):
                d = math.dist((px, py), (lm.x, lm.y))
                if d < lm.reach and d < bd:
                    best, bd = ("landmark", lm), d
        if best[0] is None:
            pt = self.nearest_portal()
            if pt:
                best = ("portal", pt)
        return best

    def _refresh_dressing(self):
        st = self.stage()
        if st == self._dress_stage:
            return
        self._dress_stage = st
        self.dyn_colliders = [d.col for d in self.dressing if d.col and d.visible(st)]

    def open_treasure(self, tr):
        self.set_flag(tr.flag)
        tr.opened_cache = True
        self.add_gold(tr.gold)
        self.toast("Hidden cache!  +%d gold" % tr.gold, (255, 220, 110))
        for _ in range(40):
            a = random.random() * math.tau
            sp = random.uniform(40, 160)
            self.bursts.append([tr.x, tr.y - 14, math.cos(a) * sp, math.sin(a) * sp - 60, 0.9])

    @property
    def level(self):
        return self.save.level if self.save is not None else 99

    def portal_locked(self, d):
        return not self.progress.is_unlocked(d) or self.level < d.get("min_level", 1)

    def lock_reason(self, d):
        if not self.progress.is_unlocked(d):
            return "Sealed - clear the %s first" % DUNGEON_BY_ID[d["requires"]]["name"]
        return "Sealed - reach level %d first (you are level %d)" % (d["min_level"], self.level)

    def nearest_portal(self):
        best, bd = None, 1e9
        for p in self.portals:
            d = math.dist((self.player.x, self.player.y), (p.x, p.y + 6))
            if d < INTERACT_DIST and d < bd:
                best, bd = p, d
        return best

    def move_player(self, dt, keys):
        p = self.player
        dx = (keys[pygame.K_d] or keys[pygame.K_RIGHT]) - (keys[pygame.K_a] or keys[pygame.K_LEFT])
        dy = (keys[pygame.K_s] or keys[pygame.K_DOWN]) - (keys[pygame.K_w] or keys[pygame.K_UP])
        if getattr(self, "frozen", False):        # the hero has fallen: no walking
            dx = dy = 0
        speed = PLAYER_SPEED * p.speed_k
        if p.dash_t > 0:                          # a dash overrides the keys for a moment
            p.dash_t = max(0.0, p.dash_t - dt)
            dx, dy = p.dash_dir
            speed = DASH_SPEED
        p.moving = bool(dx or dy)
        if not p.moving:
            return
        n = math.hypot(dx, dy)
        p.face = (dx / n, dy / n)
        vx, vy = dx / n * speed * dt, dy / n * speed * dt
        if abs(dx) >= abs(dy) and dx:
            p.facing, p.flip = "side", dx < 0
        elif dy:
            p.facing = "down" if dy > 0 else "up"
        p.walk += dt
        dyn = self.dyn_colliders
        p.x += vx
        if p.feet().collidelist(self.colliders) != -1 or p.feet().collidelist(dyn) != -1:
            p.x -= vx
        p.y += vy
        if p.feet().collidelist(self.colliders) != -1 or p.feet().collidelist(dyn) != -1:
            p.y -= vy
        # sealed portals act as solid barriers
        for pt in self.portals:
            if pt.locked:
                ox, oy = p.x - pt.x, p.y - (pt.y + 8)
                d = math.hypot(ox, oy)
                if d < 54:
                    if d == 0:
                        ox, oy, d = 0, 1, 1
                    p.x, p.y = pt.x + ox / d * 54, pt.y + 8 + oy / d * 54
        p.x = max(40, min(WORLD_W - 40, p.x))
        p.y = max(60, min(WORLD_H - 20, p.y))

    def interact(self):
        night = getattr(self, "night", None)
        if night is not None and night.active:
            self.toast("No time for that - defend the village!", (255, 160, 140))
            return
        kind, obj = self.nearest_interactable()
        if kind == "npc":
            dx, dy = self.player.x - obj.x, self.player.y - obj.y
            self.player.facing = "side" if abs(dx) > abs(dy) else ("up" if dy > 0 else "down")
            self.player.flip = dx > 0
            if self.on_talk:
                self.on_talk(obj)
            else:
                self.toast("%s waves at you." % obj.name)
            return
        if kind == "treasure":
            self.open_treasure(obj)
            return
        if kind == "landmark":
            if self.on_landmark:
                self.on_landmark(obj)
            else:
                self.toast(getattr(obj, "name", obj.kind.capitalize()))
            return
        if kind != "portal":
            return
        pt = obj
        d = pt.d
        if pt.locked:
            pt.shake = 0.6
            if not self.progress.is_unlocked(d):
                need = DUNGEON_BY_ID[d["requires"]]["name"]
                self.toast("The seal holds... clear the %s first." % need, (255, 150, 150))
            else:
                self.toast("The seal won't yield: reach level %d first (you are level %d)." % (d["min_level"], self.level),
                           (255, 150, 150))
            return
        self.pending = pt
        self.state = "fade_out"

    def drink(self):
        if self.potions > 0 and self.hp < self.max_hp:
            self.potions -= 1
            self.hp = min(self.max_hp, self.hp + 15)
            self.toast("You drink a potion (+15 HP)", (255, 170, 170))

    def finish_dungeon(self, cleared):
        pt = self.pending
        if cleared and pt.d["id"] not in self.progress.cleared:
            self.progress.cleared.add(pt.d["id"])
            opened = [x["name"] for x in DUNGEONS if x["requires"] == pt.d["id"]]
            msg = "%s cleared!" % pt.d["name"]
            if opened:
                msg += "  Unlocked: " + ", ".join(opened)
            self.toast(msg, (255, 230, 140))
        self.player.x, self.player.y = pt.x, pt.y + 108
        self.player.facing = "down"
        self.pending = None
        self.state = "fade_in"

    def objective(self):
        for d in DUNGEONS:
            if d["id"] not in self.progress.cleared and self.progress.is_unlocked(d):
                return "Objective: enter the %s" % d["name"], d["color"]
        return "The realm is safe... for now.", (255, 230, 140)

    # ------------------------------------------------------------------ loop
    def run(self):
        while True:
            dt = min(self.clock.tick(FPS) / 1000.0, 0.05)
            self.t += dt
            for e in pygame.event.get():
                if e.type == pygame.QUIT:
                    return self.progress
                if e.type == pygame.KEYDOWN:
                    if e.key == pygame.K_ESCAPE:
                        if self.state == "placeholder":
                            self.finish_dungeon(False)
                        else:
                            return self.progress
                    elif self.state == "play":
                        if e.key == pygame.K_e:
                            self.interact()
                        elif e.key == pygame.K_h:
                            self.drink()
                        elif e.key == pygame.K_m:
                            self.show_map = not self.show_map
                        elif e.key == pygame.K_F1:
                            for d in DUNGEONS:
                                if d["id"] not in self.progress.cleared and self.progress.is_unlocked(d):
                                    self.progress.cleared.add(d["id"])
                                    break
                        elif e.key == pygame.K_F5:
                            self.progress.cleared.clear()
                    elif self.state == "placeholder" and e.key == pygame.K_c:
                        self.finish_dungeon(True)
            self.update(dt)
            self.draw()
            pygame.display.flip()

    def update(self, dt):
        if self.state == "play":
            self.move_player(dt, pygame.key.get_pressed())
        else:
            self.player.moving = False
        if self.state == "fade_out":
            self.fade += dt / 0.6
            if self.fade >= 1:
                self.fade = 1
                if self.on_enter:
                    result = self.on_enter(self.pending.d["id"])
                    self.finish_dungeon(bool(result))
                else:
                    self.state = "placeholder"
        elif self.state == "fade_in":
            self.fade -= dt / 0.7
            if self.fade <= 0:
                self.fade = 0
                self.state = "play"
        for p in self.portals:
            p.update(dt, self.portal_locked(p.d))
        self.update_life(dt)
        for tt in self.toasts:
            tt[2] -= dt
        self.toasts = [x for x in self.toasts if x[2] > 0]
        self.intro = max(0.0, self.intro - dt)

    def update_life(self, dt):
        """Villagers, animals, smoke, day/night. Safe to call while the hero stands still."""
        self.daynight.update(dt)
        self._refresh_dressing()
        for n in self.talkers():
            n.update(dt, self)
            n.alert = self.npc_alert(n.id) if self.npc_alert else None
        night = self.daynight.night()
        for lm in self.landmarks:
            if lm.kind == "sword":
                lm.flag_cache = self.has_flag(lm.flag)
            elif lm.kind == "petal":
                lm.picked = self.has_flag(lm.flag)
                lm.bloom = night
        for h in self.hens:
            if self.has_flag(h.flag) and not (h.going_home or h.homed):
                h.settle()
            h.update(dt, self)
        name, col = world_lore.region_at(self.player.x, self.player.y)
        if name != self.region:
            self.region, self.region_col, self.region_t = name, col, 3.2
        self.region_t = max(0.0, self.region_t - dt)
        for c in self.critters:
            c.update(dt, self)
        day = self.daynight.night() < 0.5
        for b in self.butterflies:
            b.visible = day
            b.update(dt, self)
        for s in self.smokes:
            s.update(dt)
        for tr in self.treasures:
            tr.opened_cache = self.has_flag(tr.flag)
        for b in self.bursts:
            b[0] += b[2] * dt
            b[1] += b[3] * dt
            b[3] += 260 * dt
            b[4] -= dt
        self.bursts = [b for b in self.bursts if b[4] > 0]

    # ------------------------------------------------------------------ draw
    def text(self, surf, s, font, col, pos, anchor="topleft", shadow=True):
        img = font.render(s, True, col)
        r = img.get_rect(**{anchor: pos})
        if shadow:
            surf.blit(font.render(s, True, (0, 0, 0)), r.move(2, 2))
        surf.blit(img, r)
        return r

    def camera(self):
        pl = self.player
        return (int(max(0, min(WORLD_W - SCREEN_W, pl.x - SCREEN_W / 2))),
                int(max(0, min(WORLD_H - SCREEN_H, pl.y - SCREEN_H / 2 - 20))))

    def draw(self):
        scr, t, pl = self.screen, self.t, self.player
        camx, camy = self.camera()
        scr.blit(self.ground, (0, 0), (camx, camy, SCREEN_W, SCREEN_H))
        self.draw_river_flow(scr, camx, camy, t)
        view = pygame.Rect(camx - 120, camy - 120, SCREEN_W + 240, SCREEN_H + 240)

        stage = self.stage()
        ents = [p for p in self.props if p.rect.colliderect(view)]
        ents += [p for p in self.portals if p.rect.colliderect(view)]
        ents += [n for n in self.talkers() if n.rect.colliderect(view)]
        ents += [c for c in self.critters if c.rect.colliderect(view)]
        ents += [b for b in self.butterflies if b.rect.colliderect(view)]
        ents += [tr for tr in self.treasures if tr.rect.colliderect(view)]
        ents += [d for d in self.dressing if d.visible(stage) and d.rect.colliderect(view)]
        ents += [lm for lm in self.landmarks if lm.visible(self) and lm.rect.colliderect(view)]
        ents += [h for h in self.hens if h.rect.colliderect(view)]
        ents.append(pl)
        ents.sort(key=lambda e: e.sort_y)
        for e in ents:
            e.draw(scr, camx, camy, t)
        for s in self.smokes:
            if view.collidepoint(s.x, s.y):
                s.draw(scr, camx, camy)
        if stage >= 1:
            for a, b in self.bunting:
                if view.collidepoint(a) or view.collidepoint(b):
                    village.draw_bunting(scr, a, b, camx, camy, t)
        raid = getattr(self, "night", None)
        wild = getattr(self, "wilds", None)
        if wild is not None:
            wild.draw_world(scr, camx, camy, t)
        if raid is not None:
            raid.draw_world(scr, camx, camy, t)
        for x, y, vx, vy, life in self.bursts:
            k = max(0.0, min(1.0, life / 0.9))
            pygame.draw.circle(scr, (int(255 * k), int(214 * k), int(90 * k)), (int(x - camx), int(y - camy)), 2)

        # lighting (ambient follows the day/night cycle)
        night = self.daynight.night()
        ls = self.light_surf
        ls.fill(self.daynight.ambient())
        lights = []
        for e in ents:
            if hasattr(e, "lights"):
                lights += e.lights(t)
        if raid is not None:
            lights += raid.lights(t)
        if wild is not None:
            lights += wild.lights(t)
        for (lx, ly, lr, lc) in lights:
            if view.collidepoint(lx, ly):
                ls.blit(glow(lr, lc), (lx - lr - camx, ly - lr - camy), special_flags=pygame.BLEND_RGB_ADD)
        scr.blit(ls, (0, 0), special_flags=pygame.BLEND_RGB_MULT)
        scr.blit(self.vignette, (0, 0), special_flags=pygame.BLEND_RGB_MULT)
        if raid is not None:
            raid.draw_glow(scr, camx, camy, t)
        fx_hook = getattr(self, "draw_fx_hook", None)      # the hero's skills (set by the Game)
        if fx_hook is not None:
            fx_hook(scr, camx, camy, t)
        # coloured portal haze
        for p in self.portals:
            if not p.locked and view.collidepoint(p.x, p.y):
                scr.blit(glow(210, scale_col(p.color, 0.30)), (p.x - 210 - camx, p.y - 210 - camy), special_flags=pygame.BLEND_RGB_ADD)
        # creeping purple mist from the north (retreats as the story advances)
        self.fog.draw(scr, camx, camy, t, stage, WORLD_W, SCREEN_W, SCREEN_H)
        # fireflies come out at dusk
        for (fx, fy, ph, spd) in (self.fireflies if night > 0.25 else ()):
            x = fx + math.sin(t * spd + ph) * 34
            y = fy + math.cos(t * spd * 0.8 + ph * 1.3) * 22
            sx, sy = int(x - camx), int(y - camy)
            if -12 < sx < SCREEN_W + 12 and -12 < sy < SCREEN_H + 12:
                b = (0.45 + 0.55 * (0.5 + 0.5 * math.sin(t * 1.6 + ph * 3))) * min(1.0, night * 1.3)
                q = round(b * 4) / 4
                if q <= 0:
                    continue
                scr.blit(glow(11, (int(110 * q), int(150 * q), int(40 * q))), (sx - 11, sy - 11), special_flags=pygame.BLEND_RGB_ADD)
                pygame.draw.circle(scr, (int(200 * q + 40), int(255 * q), int(120 * q)), (sx, sy), 2)

        # labels above portals
        for p in self.portals:
            if view.collidepoint(p.x, p.y):
                self.draw_portal_label(p, camx, camy)

        # villager name tags and "!" alerts (the one you can talk to gets the prompt instead)
        kind, obj = self.nearest_interactable()
        for n in self.talkers():
            if view.collidepoint(n.x, n.y):
                n.draw_overlay(scr, camx, camy, t, self.f_small,
                               n is not obj and math.dist((pl.x, pl.y), (n.x, n.y)) < 110)

        # prompt
        if kind and self.state == "play":
            self.draw_prompt(obj, camx, camy, kind)

        self.draw_hud(camx, camy)
        if wild is not None:
            wild.draw_hud(scr, self.f_small, self.f_label)
        if raid is not None:
            raid.draw_hud(scr, self.f_small, self.f_label)

        if self.state == "placeholder":
            self.draw_placeholder()
        if self.fade > 0:
            self.fade_surf.set_alpha(int(255 * min(1, self.fade)))
            scr.blit(self.fade_surf, (0, 0))
            if self.state == "placeholder":
                self.draw_placeholder()

    def draw_portal_label(self, p, camx, camy):
        scr = self.screen
        X, Y = int(p.x - camx), int(p.y - camy)
        locked = p.locked
        col = (150, 150, 168) if locked else p.color
        img = self.f_label.render(p.d["name"], True, (235, 235, 228) if not locked else (170, 170, 182))
        pad = 28 if locked else 0
        w, h = img.get_width() + 24 + pad, img.get_height() + 10
        r = pygame.Rect(0, 0, w, h)
        r.center = (X, Y - (122 if p.d.get("mini") else 98))
        panel = pygame.Surface((w, h), pygame.SRCALPHA)
        pygame.draw.rect(panel, (8, 14, 12, 205), (0, 0, w, h), border_radius=7)
        pygame.draw.rect(panel, col + (255,), (0, 0, w, h), 2, border_radius=7)
        self.screen.blit(panel, r)
        scr.blit(img, (r.x + 12 + pad, r.y + 5))
        if locked:
            draw_lock(scr, r.x + 22, r.y + h // 2 + 3, 0.7)
        self.text(scr, p.d["level"], self.f_small, col, (X, Y + (22 if p.d.get("mini") else 78)), "center")
        if locked:
            self.text(scr, "SEALED", self.f_small, (230, 110, 110), (X, Y + 98), "center")

    def draw_prompt(self, p, camx, camy, kind="portal"):
        scr = self.screen
        if kind == "npc":
            verb = "Talk to" if not p.shop else "Trade with"
            msg, col = "[E]  %s %s" % (verb, p.name.split(" the ")[0]), (140, 220, 150)
        elif kind == "treasure":
            msg, col = "[E]  Open the hidden cache", (255, 214, 100)
        elif kind == "landmark":
            msg, col = p.prompt(self), (200, 210, 255) if p.kind in ("shrine", "memorial", "board") else (255, 214, 100)
        elif p.locked:
            msg, col = self.lock_reason(p.d), (230, 120, 120)
        elif p.d.get("mini"):
            msg, col = "[E]  Enter %s (%s)" % (p.d["name"], p.d["level"]), p.color
        else:
            msg, col = "[E]  Enter the %s" % p.d["name"], p.color
        img = self.f_hud.render(msg, True, (245, 240, 225))
        w, h = img.get_width() + 28, img.get_height() + 12
        r = pygame.Rect(0, 0, w, h)
        r.center = (int(self.player.x - camx), int(self.player.y - camy) - 82)
        r.clamp_ip(scr.get_rect().inflate(-20, -20))
        panel = pygame.Surface((w, h), pygame.SRCALPHA)
        pygame.draw.rect(panel, (8, 14, 12, 225), (0, 0, w, h), border_radius=8)
        pygame.draw.rect(panel, col + (255,), (0, 0, w, h), 2, border_radius=8)
        scr.blit(panel, r)
        scr.blit(img, (r.x + 14, r.y + 6))

    def draw_hud(self, camx, camy):
        scr = self.screen
        hero_hud = getattr(self, "hero_hud_hook", None)     # the Game's hero panel (bars + skills)
        if hero_hud is not None:
            top = hero_hud(scr)
            pygame.draw.circle(scr, (90, 60, 10), (36, top + 17), 10)
            pygame.draw.circle(scr, (240, 196, 70), (36, top + 16), 8)
            pygame.draw.circle(scr, (255, 236, 150), (34, top + 14), 3)
            self.text(scr, "%d gold" % self.gold, self.f_hud, (255, 226, 130), (54, top + 2))
            info = self.quest_info() if self.quest_info else None
            if info:
                self.draw_tracker(info, top + 34)
            self._draw_hud_rest(camx, camy)
            return
        # HP
        pygame.draw.rect(scr, (60, 18, 22), (24, 22, 364, 26))
        pygame.draw.rect(scr, (218, 52, 62), (24, 22, int(364 * self.hp / self.max_hp), 26))
        pygame.draw.rect(scr, (20, 8, 10), (24, 22, 364, 26), 2)
        self.text(scr, "HP %d/%d" % (self.hp, self.max_hp), self.f_hud, (255, 255, 255), (34, 24))
        if self.save is not None:       # level badge and XP bar
            lv, have, need = level_progress(self.save.xp)
            self.text(scr, "Lv %d" % lv, self.f_hud, (170, 220, 255), (402, 22))
            bx = 402 + self.f_hud.size("Lv %d" % lv)[0] + 10
            pygame.draw.rect(scr, (0, 0, 0), (bx - 2, 30, 164, 12))
            pygame.draw.rect(scr, (30, 40, 70), (bx, 32, 160, 8))
            pygame.draw.rect(scr, (120, 190, 255) if need else (255, 214, 120),
                             (bx, 32, int(160 * have / need) if need else 160, 8))
        self.text(scr, "Potions: %d   (H: drink)" % self.potions, self.f_hud, (255, 255, 255), (24, 56))
        pygame.draw.circle(scr, (90, 60, 10), (36, 103), 10)
        pygame.draw.circle(scr, (240, 196, 70), (36, 102), 8)
        pygame.draw.circle(scr, (255, 236, 150), (34, 100), 3)
        self.text(scr, "%d gold" % self.gold, self.f_hud, (255, 226, 130), (54, 88))
        info = self.quest_info() if self.quest_info else None
        if info:
            self.draw_tracker(info)
        else:
            s, col = self.objective()
            self.text(scr, s, self.f_label, col, (700, 22), "midtop")
        self._draw_hud_rest(camx, camy)

    def _draw_hud_rest(self, camx, camy):
        scr = self.screen
        # region name when you walk into a new area
        if self.region_t > 0 and self.intro <= 0:
            a = min(1.0, self.region_t / 0.6, (3.2 - self.region_t) / 0.4)
            img = self.f_title.render(self.region, True, self.region_col)
            sh = self.f_title.render(self.region, True, (0, 0, 0))
            w = img.get_width()
            band = pygame.Surface((w + 120, 52), pygame.SRCALPHA)
            for i in range(60):
                al = int(150 * (i / 60))
                pygame.draw.line(band, (6, 10, 10, al), (i, 0), (i, 51))
                pygame.draw.line(band, (6, 10, 10, al), (w + 119 - i, 0), (w + 119 - i, 51))
            band.fill((6, 10, 10, 150), (60, 0, w, 52))
            band.blit(sh, (62, 10))  # region banner (drawn below the top HUD row)
            band.blit(img, (60, 8))
            pygame.draw.line(band, self.region_col + (255,), (60, 47), (60 + w, 47), 1)
            band.set_alpha(int(255 * max(0.0, a)))
            scr.blit(band, (SCREEN_W // 2 - band.get_width() // 2 + 40, 60))
        # intro banner
        if self.intro > 0:
            a = min(1.0, self.intro / 1.5)
            b = pygame.Surface((640, 92), pygame.SRCALPHA)
            pygame.draw.rect(b, (8, 14, 12, 215), (0, 0, 640, 92), border_radius=10)
            pygame.draw.rect(b, (70, 190, 100, 255), (0, 0, 640, 92), 3, border_radius=10)
            t1 = self.f_title.render("OAKWOOD VALE", True, (236, 236, 228))
            t2 = self.f_label.render("Sealed beneath the Veil  •  Three anchors must fall", True, (220, 230, 210))
            b.blit(t1, (320 - t1.get_width() // 2, 12))
            b.blit(t2, (320 - t2.get_width() // 2, 56))
            b.set_alpha(int(255 * a))
            scr.blit(b, (SCREEN_W // 2 - 320, 84))
        # toasts
        y = 150
        for text, col, life in self.toasts:
            img = self.f_hud.render(text, True, col)
            w, h = img.get_width() + 28, img.get_height() + 12
            panel = pygame.Surface((w, h), pygame.SRCALPHA)
            pygame.draw.rect(panel, (8, 14, 12, 220), (0, 0, w, h), border_radius=8)
            pygame.draw.rect(panel, col + (255,), (0, 0, w, h), 2, border_radius=8)
            panel.blit(img, (14, 6))
            panel.set_alpha(int(255 * min(1, life / 0.6)))
            scr.blit(panel, (SCREEN_W // 2 - w // 2 + 40, y))
            y += h + 6
        # minimap
        if self.show_map:
            self.draw_minimap(camx, camy)
        # bottom hint bar
        bar = pygame.Surface((SCREEN_W, 34), pygame.SRCALPHA)
        bar.fill((6, 10, 10, 200))
        scr.blit(bar, (0, SCREEN_H - 34))
        hint = getattr(self, "controls_hint", None) or \
            "WASD: move  |  Space: attack  |  E: talk / use  |  Tab: journal  |  H: potion  |  M: map  |  ESC: pause"
        self.text(scr, hint, self.f_small, (235, 235, 225), (SCREEN_W // 2, SCREEN_H - 17), "center")

    def _wrap(self, text, font, width):
        text = story.named(text)
        out, cur = [], ""
        for w in text.split(" "):
            test = (cur + " " + w).strip()
            if font.size(test)[0] <= width:
                cur = test
            else:
                out.append(cur)
                cur = w
        out.append(cur)
        return out

    def draw_tracker(self, info, top=122):
        """Quest tracker under the gold counter: main quest step + side quests in progress."""
        key = (info.get("main"), tuple(info.get("side", ())), story.hero_name())
        if getattr(self, "_tracker_key", None) != key:
            self._tracker_key, self._tracker_img = key, self._build_tracker(info)
        if self._tracker_img:
            self.screen.blit(self._tracker_img, (16, top))

    def _build_tracker(self, info):
        rows = []                                  # (text, font, colour, indent)
        main = info.get("main")
        if main:
            title, text, col = main
            rows.append((title.upper(), self.f_small, col, 0))
            for ln in self._wrap(text, self.f_small, 262):
                rows.append((ln, self.f_small, (236, 236, 226), 14))
        side = info.get("side", [])
        for title, sub, col in side[:3]:
            if rows:
                rows.append(("", None, None, 0))
            rows.append((title, self.f_small, col, 0))
            for ln in self._wrap(sub, self.f_small, 262):
                rows.append((ln, self.f_small, (200, 204, 196), 14))
        if len(side) > 3:
            rows.append(("+%d more  (Tab: journal)" % (len(side) - 3), self.f_small, (170, 170, 160), 0))
        if not rows:
            return None
        h = sum(f.get_height() + 1 if f else 5 for _t, f, _c, _i in rows) + 14
        panel = pygame.Surface((296, h), pygame.SRCALPHA)
        pygame.draw.rect(panel, (6, 12, 10, 165), (0, 0, 296, h), border_radius=8)
        pygame.draw.rect(panel, (255, 214, 90, 200), (0, 6, 3, h - 12))
        y = 7
        for text, font, col, ind in rows:
            if font is None:
                y += 5
                continue
            self.text(panel, text, font, col, (14 + ind, y))
            y += font.get_height() + 1
        return panel

    def draw_minimap(self, camx, camy):
        scr = self.screen
        pw, ph = self.mm_w + 12, self.mm_h + 34
        x0, y0 = SCREEN_W - pw - 16, 16
        pygame.draw.rect(scr, (6, 12, 10), (x0, y0, pw, ph), border_radius=8)
        scr.blit(self.mm_static, (x0 + 6, y0 + 6))
        k = self.mm_scale
        ox, oy = x0 + 6, y0 + 6
        for p in self.portals:
            c = (120, 120, 134) if p.locked else p.color
            pos = (int(ox + p.x * k), int(oy + p.y * k))
            if p.d.get("mini"):              # caves: small triangles
                pygame.draw.polygon(scr, (10, 10, 14), [(pos[0], pos[1] - 6), (pos[0] + 6, pos[1] + 4), (pos[0] - 6, pos[1] + 4)])
                pygame.draw.polygon(scr, c, [(pos[0], pos[1] - 4), (pos[0] + 4, pos[1] + 3), (pos[0] - 4, pos[1] + 3)])
                continue
            pygame.draw.circle(scr, (10, 10, 14), pos, 7)
            pygame.draw.circle(scr, c, pos, 5)
            if p.locked:
                draw_lock(scr, pos[0], pos[1] + 2, 0.45)
        wilds = getattr(self, "wilds", None)
        if wilds is not None:
            wilds.draw_minimap(scr, ox, oy, k, self.t)
        pygame.draw.rect(scr, (240, 240, 230), (ox + camx * k, oy + camy * k, SCREEN_W * k, SCREEN_H * k), 1)
        pp = (int(ox + self.player.x * k), int(oy + self.player.y * k))
        if int(self.t * 3) % 2 == 0:
            pygame.draw.circle(scr, (255, 255, 255), pp, 4)
        pygame.draw.circle(scr, (60, 140, 255), pp, 3)
        pygame.draw.rect(scr, (60, 190, 100), (x0, y0, pw, ph), 3, border_radius=8)
        for n in self.talkers():
            if n.alert:
                c = (236, 236, 236) if n.alert == "news" else (255, 214, 90)
                pygame.draw.circle(scr, (10, 10, 14), (int(ox + n.x * k), int(oy + n.y * k)), 3)
                pygame.draw.circle(scr, c, (int(ox + n.x * k), int(oy + n.y * k)), 2)
        info = self.quest_info() if self.quest_info else None
        if info:
            pulse = 3 + int(self.t * 4) % 2
            for x, y, c in info.get("targets", ()):
                px, py = int(ox + x * k), int(oy + y * k)
                pts = [(px, py - pulse - 1), (px + pulse + 1, py), (px, py + pulse + 1), (px - pulse - 1, py)]
                pygame.draw.polygon(scr, (10, 10, 14), pts)
                pts = [(px, py - pulse), (px + pulse, py), (px, py + pulse), (px - pulse, py)]
                pygame.draw.polygon(scr, c, pts)
        self.text(scr, "OAKWOOD REALM", self.f_small, (110, 220, 130), (x0 + 10, y0 + ph - 24))
        # time of day: little sun / moon
        night = self.daynight.night()
        lab = self.f_small.render(self.daynight.label(), True, (220, 228, 210))
        bx, by = x0 + pw - lab.get_width() - 34, y0 + 10
        pygame.draw.rect(scr, (6, 12, 10), (bx - 4, by - 2, lab.get_width() + 30, 22), border_radius=6)
        scr.blit(lab, (bx, by))
        ix, iy = x0 + pw - 18, by + 9
        if night < 0.5:
            pygame.draw.circle(scr, (255, 214, 90), (ix, iy), 6)
        else:
            pygame.draw.circle(scr, (220, 226, 255), (ix, iy), 6)
            pygame.draw.circle(scr, (6, 12, 10), (ix + 3, iy - 2), 5)

    def draw_placeholder(self):
        scr = self.screen
        pt = self.pending
        if not pt:
            return
        scr.fill((6, 8, 10))
        self.text(scr, "Entering the %s..." % pt.d["name"], self.f_title, pt.color, (SCREEN_W // 2, 260), "center")
        self.text(scr, "(Placeholder - connect your dungeon scene with run(on_enter_dungeon=...))",
                  self.f_label, (200, 200, 190), (SCREEN_W // 2, 330), "center")
        self.text(scr, "C: simulate clearing this dungeon     ESC: go back", self.f_label,
                  (240, 230, 160), (SCREEN_W // 2, 400), "center")


class Spacing:
    """Tiny spatial hash so props / trees don't overlap."""

    def __init__(self, cell=64):
        self.c = cell
        self.g = {}

    def add(self, x, y, r):
        self.g.setdefault((int(x // self.c), int(y // self.c)), []).append((x, y, r))

    def free(self, x, y, r):
        cx, cy = int(x // self.c), int(y // self.c)
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                for (ox, oy, orr) in self.g.get((cx + dx, cy + dy), ()):
                    if (x - ox) ** 2 + (y - oy) ** 2 < (r + orr) ** 2:
                        return False
        return True


# --------------------------------------------------------------------------- #
def run(on_enter_dungeon=None, progress=None, screen=None):
    """Start the surface world. Returns the Progress object when the player quits."""
    pygame.init()
    if screen is None:
        screen = pygame.display.set_mode((SCREEN_W, SCREEN_H))
    pygame.display.set_caption("RealmQuest - Surface World")
    return SurfaceWorld(screen, on_enter_dungeon, progress).run()


if __name__ == "__main__":
    run()
