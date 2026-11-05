"""
room_features.py - map-side dungeon content (no monsters or bosses in here).

    decorate(dungeon)          stamps a themed layout into every room (call before build_walls)
    Interactables(dungeon, save)
        pots / crates      break with the sword, spill gold coins
        reward chests      one per room, open once Encounters marks the room "cleared"
        spike traps        floor 2+, telegraph then bite (uses pc.hurt)
        lore tablets       floor 1 and 2, E to read
        anchor core        boss floor: the Veil Anchor, exposed when the boss room is cleared
                           (still called the "keepsake" in code and in the save)
        quest items        scrap / badges / ward shards while their side quest is active
        floor key          dropped by the guard / mini-boss room, opens the stairs door (floors 1-2)
        boss seals         dropped by seal rooms and the mini-boss, open the boss gate (floor 3)
        gates              the locked stairs door / boss gate (solid until opened with E)
        healing font       shrine rooms, E restores full health once
    draw_lock_gates(...)       rune barriers on the doors of a locked room

Only reads the Encounters contract (state list) and dungeon.lock_rect, and hurts the
player through PlayerCombat.hurt, so monster/boss code can change freely.
"""
from __future__ import annotations

import math
import random

import pygame

try:
    from . import story
    from . import quests
except ImportError:
    import story
    import quests

TILE = 24
MAP_W, MAP_H = 288, 162
VOID, FLOOR, LIQUID, PATH = 0, 1, 2, 5
WALK = (FLOOR, PATH)
SURFACE_IDS = {1: "goblin", 2: "berserker", 3: "lich"}

CENTER_CLEAR = 6          # Encounters spawns monsters within +-3 tiles of a room's centre


# --------------------------------------------------------------------------- #
#  helpers
# --------------------------------------------------------------------------- #
def _blank(w, h):
    return pygame.Surface((w, h), pygame.SRCALPHA)


def _shade(c, f):
    return tuple(max(0, min(255, int(v * f))) for v in c[:3])


def _mix(a, b, t):
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))


def _outline(s, color=(12, 9, 16, 255)):
    m = pygame.mask.from_surface(s)
    o = m.to_surface(setcolor=color, unsetcolor=(0, 0, 0, 0))
    out = _blank(s.get_width() + 2, s.get_height() + 2)
    for dx, dy in ((0, 1), (2, 1), (1, 0), (1, 2)):
        out.blit(o, (dx, dy))
    out.blit(s, (1, 1))
    return out


_GLOWS: dict = {}


def glow(radius, color, strength=0.6):
    key = (radius, color, strength)
    g = _GLOWS.get(key)
    if g is None:
        g = pygame.Surface((radius * 2, radius * 2))
        for r in range(radius, 0, -2):
            f = (1 - r / radius) ** 2 * strength
            pygame.draw.circle(g, tuple(int(c * f) for c in color), (radius, radius), r)
        _GLOWS[key] = g
    return g


# --------------------------------------------------------------------------- #
#  room archetypes
# --------------------------------------------------------------------------- #
ARCHETYPES = {
    "forest": ("grove", "ruin", "pond"),
    "stone": ("pillared", "crypt", "collapsed"),
    "hell": ("lava", "bones", "altar"),
}
# random prop density per archetype (area / divisor); decorated rooms get fewer random props
PROP_DIVISOR = {"start": 95, "arena": 260}
DEFAULT_DIVISOR = 140


class _Stamp:
    def __init__(self, d, r, rng):
        self.d, self.r, self.rng = d, r, rng
        self.cx, self.cy = r.centerx, r.centery

    def ok(self, tx, ty, zone=2, clear=CENTER_CLEAR):
        r = self.r
        if not (r.x + 1 <= tx < r.right - 1 and r.y + 1 <= ty < r.bottom - 1):
            return False
        i = ty * MAP_W + tx
        if self.d.tiles[i] != FLOOR or self.d.solid[i]:
            return False
        if max(abs(tx - self.cx), abs(ty - self.cy)) < clear:
            return False
        return not self.d.near_zone(tx, ty, zone)

    def block(self, x0, y0, w, h, kind=VOID):
        """Fill a rectangle with VOID (becomes a wall) or LIQUID if every tile is free."""
        cells = [(x, y) for y in range(y0, y0 + h) for x in range(x0, x0 + w)]
        if not all(self.ok(x, y, zone=3 if kind == VOID else 2) for x, y in cells):
            return False
        for x, y in cells:
            self.d.tiles[y * MAP_W + x] = kind
        return True

    def ellipse(self, px, py, rx, ry, kind=LIQUID, jitter=0.15):
        n = 0
        for y in range(py - ry, py + ry + 1):
            for x in range(px - rx, px + rx + 1):
                if ((x - px) / rx) ** 2 + ((y - py) / ry) ** 2 <= 1.0 + self.rng.uniform(-jitter, jitter / 2):
                    if self.ok(x, y, zone=2):
                        self.d.tiles[y * MAP_W + x] = kind
                        n += 1
        return n

    def prop(self, tx, ty, kinds, spr=None):
        if not self.ok(tx, ty, zone=2) or self.d.solid[ty * MAP_W + tx]:
            return False
        if any(self.d.solid[(ty + b) * MAP_W + tx + a] for a in (-1, 0, 1) for b in (-1, 0, 1)):
            return False
        kind = kinds if isinstance(kinds, str) else self.rng.choice(kinds)
        if spr is None:
            opts = [s for k, s, _w in self.d.art.props if k == kind]
            if not opts:
                return False
            spr = self.rng.choice(opts)
        self.d.solid[ty * MAP_W + tx] = 1
        self.d.props.append((tx, ty, kind, spr))
        return True

    def quadrants(self, fx=0.32, fy=0.3):
        r = self.r
        dx, dy = max(CENTER_CLEAR + 2, int(r.w * fx)), max(CENTER_CLEAR - 1, int(r.h * fy))
        return [(self.cx + sx * dx, self.cy + sy * dy) for sx in (-1, 1) for sy in (-1, 1)]


# ---- forest -----------------------------------------------------------------
def _grove(s):
    for qx, qy in s.quadrants():
        for _ in range(s.rng.randint(4, 6)):
            s.prop(qx + s.rng.randint(-3, 3), qy + s.rng.randint(-2, 2), ("tree", "tree", "bush"))


def _ruin(s):
    for qx, qy in s.quadrants(0.3, 0.28):
        sx = 1 if qx > s.cx else -1
        # broken L-shaped wall
        s.block(qx - 2, qy - 1, 5, 3)
        s.block(qx + (2 if sx < 0 else -3), qy - 4, 2, 4) if s.rng.random() < 0.6 else None
        s.prop(qx - sx * 3, qy + 2, ("ruin", "statue"))


def _pond(s):
    q = s.quadrants()
    s.rng.shuffle(q)
    for qx, qy in q[:2]:
        s.ellipse(qx, qy, s.rng.randint(3, 5), s.rng.randint(2, 3))
        for _ in range(3):
            s.prop(qx + s.rng.randint(-6, 6), qy + s.rng.choice((-4, 4)), ("bush", "tree", "rock"))


# ---- stone ------------------------------------------------------------------
def _pillared(s):
    r = s.r
    for row in (s.cy - 6, s.cy + 6):
        for x in range(r.x + 4, r.right - 3, 5):
            s.prop(x, row, "pillar")
    for x, y in ((r.x + 3, r.y + 3), (r.right - 4, r.y + 3), (r.x + 3, r.bottom - 4), (r.right - 4, r.bottom - 4)):
        s.prop(x, y, "brazier")


def _crypt(s):
    r = s.r
    spr = _sarcophagus(s.d.theme)
    for y in (s.cy - 7, s.cy + 6):
        for x in range(r.x + 4, r.right - 3, 4):
            s.prop(x, y, "sarcophagus", spr)
    for x in (r.x + 3, r.right - 4):
        s.prop(x, s.cy - 1, "statue")


def _collapsed(s):
    r = s.r
    for _ in range(14):
        w, h = s.rng.randint(2, 4), s.rng.randint(3, 4)
        s.block(s.rng.randrange(r.x + 2, r.right - 3), s.rng.randrange(r.y + 2, r.bottom - 3), w, h)
    for _ in range(4):
        s.prop(s.rng.randrange(r.x + 2, r.right - 2), s.rng.randrange(r.y + 2, r.bottom - 2), ("crate", "barrel"))


# ---- hell -------------------------------------------------------------------
def _lava(s):
    r = s.r
    a, b = min(r.w // 2 - 4, 12), min(r.h // 2 - 3, 9)
    if a < 9 or b < 7:
        return _bones(s)
    for y in range(r.y, r.bottom):
        for x in range(r.x, r.right):
            dx, dy = x - s.cx, y - s.cy
            e = (dx / a) ** 2 + (dy / b) ** 2
            if 0.62 <= e <= 1.0 and abs(dx) > 1 and abs(dy) > 1:      # leave 4 bridges
                if s.ok(x, y, zone=1, clear=CENTER_CLEAR - 1):
                    s.d.tiles[y * MAP_W + x] = LIQUID
    for qx, qy in s.quadrants(0.42, 0.38):
        s.prop(qx, qy, ("spire", "crystal"))


def _bones(s):
    r = s.r
    for _ in range(16):
        s.prop(s.rng.randrange(r.x + 2, r.right - 2), s.rng.randrange(r.y + 2, r.bottom - 2),
               ("skulls", "skulls", "spire"))


def _altar(s):
    for qx, qy in s.quadrants(0.36, 0.32):
        s.ellipse(qx, qy, s.rng.randint(2, 4), 2)
        s.prop(qx + (3 if qx < s.cx else -3), qy, ("obelisk", "crystal"))


# ---- shared -----------------------------------------------------------------
def _antechamber(s):
    """Quiet hall before the boss gate: two rows of pillars / statues and braziers."""
    r = s.r
    kinds = {"forest": ("statue", "ruin"), "stone": ("pillar", "brazier"), "hell": ("pillar", "obelisk")}[s.d.theme.key]
    if r.w >= r.h:
        for x in range(r.x + 3, r.right - 2, 5):
            for y in (r.y + 2, r.bottom - 3):
                s.prop(x, y, kinds[0] if (x - r.x) % 10 else kinds[1])
    else:
        for y in range(r.y + 3, r.bottom - 2, 5):
            for x in (r.x + 2, r.right - 3):
                s.prop(x, y, kinds[0] if (y - r.y) % 10 else kinds[1])


def _arena(s):
    """Boss room: a ring of pillars / braziers around a wide open floor."""
    r = s.r
    kinds = {"forest": ("ruin", "statue"), "stone": ("brazier", "pillar"), "hell": ("obelisk", "brazier")}[s.d.theme.key]
    ax, ay = r.w // 2 - 3, r.h // 2 - 3
    for i in range(12):
        a = i * math.tau / 12 + math.pi / 12
        s.prop(int(s.cx + math.cos(a) * ax), int(s.cy + math.sin(a) * ay), kinds[i % 2])


STAMPS = {"grove": _grove, "ruin": _ruin, "pond": _pond, "pillared": _pillared, "crypt": _crypt,
          "collapsed": _collapsed, "lava": _lava, "bones": _bones, "altar": _altar,
          "arena": _arena, "antechamber": _antechamber, "start": lambda s: None}

# room role -> fixed stamp (everything else gets one of the theme's archetypes)
ROLE_STAMP = {"start": "start", "stairs": "start", "shrine": "start", "trap": "start",
              "boss": "arena", "miniboss": "arena", "lair": "arena", "antechamber": "antechamber"}


def room_roles(d):
    """Room roles from the dungeon generator, or the old fixed roles for a plain chain."""
    roles = getattr(d, "room_roles", None)
    if roles:
        return roles
    last = len(d.rooms) - 1
    return ["start"] + ["combat"] * (last - 1) + ["boss" if d.floor_name.endswith("-3") else "combat"]


def rng_key(d):
    return getattr(d, "rng_key", d.floor_name)


def decorate(d):
    """Pick and stamp an archetype for every room. Call after scatter_liquid()."""
    rng = random.Random("rooms" + rng_key(d))
    kinds = ARCHETYPES.get(d.theme.key, ARCHETYPES["stone"])
    roles = room_roles(d)
    offset = rng.randrange(3)
    d.room_kinds = []
    for k, r in enumerate(d.rooms):
        kind = ROLE_STAMP.get(roles[k]) or kinds[(k + offset) % 3]
        d.room_kinds.append(kind)
        STAMPS[kind](_Stamp(d, r, rng))


def prop_divisor(d, k):
    kinds = getattr(d, "room_kinds", None)
    if not kinds:
        return 80
    return PROP_DIVISOR.get(kinds[k], DEFAULT_DIVISOR)


# --------------------------------------------------------------------------- #
#  sprites
# --------------------------------------------------------------------------- #
def _sarcophagus(theme):
    s = _blank(26, 40)
    base, hi, dk = theme.wall, theme.wall_hi, theme.wall_dark
    pygame.draw.ellipse(s, (0, 0, 0, 90), (0, 30, 26, 10))
    pygame.draw.rect(s, _shade(base, 0.8), (2, 12, 22, 24))
    pygame.draw.rect(s, base, (2, 4, 22, 14), border_radius=4)
    pygame.draw.rect(s, hi, (2, 4, 22, 3), border_radius=3)
    pygame.draw.line(s, dk, (13, 6), (13, 16), 2)
    pygame.draw.line(s, dk, (9, 9), (17, 9), 2)
    pygame.draw.rect(s, dk, (2, 4, 22, 32), 1, border_radius=3)
    return _outline(s)


def _pot(col, band):
    s = _blank(20, 24)
    pygame.draw.ellipse(s, (0, 0, 0, 90), (1, 18, 18, 6))
    pygame.draw.ellipse(s, col, (2, 6, 16, 16))
    pygame.draw.rect(s, _shade(col, 0.8), (6, 2, 8, 6))
    pygame.draw.rect(s, _shade(col, 0.6), (5, 1, 10, 2))
    pygame.draw.line(s, band, (3, 13), (17, 13), 2)
    pygame.draw.ellipse(s, _mix(col, (255, 255, 255), 0.35), (5, 8, 4, 6))
    return _outline(s)


def _crate():
    s = _blank(22, 24)
    pygame.draw.ellipse(s, (0, 0, 0, 90), (0, 18, 22, 6))
    pygame.draw.rect(s, (130, 92, 52), (2, 4, 18, 17))
    pygame.draw.rect(s, (82, 56, 30), (2, 4, 18, 17), 2)
    pygame.draw.line(s, (82, 56, 30), (2, 4), (19, 20), 2)
    pygame.draw.line(s, (160, 120, 70), (3, 5), (18, 5), 1)
    return _outline(s)


def _chest(opened, big, ready):
    w = 34 if big else 26
    s = _blank(w + 6, 30)
    x0 = 3
    body, dark, gold = (112, 66, 34), (64, 36, 18), (220, 176, 70)
    if big:
        body, gold = (90, 40, 60), (240, 200, 90)
    pygame.draw.ellipse(s, (0, 0, 0, 100), (0, 22, w + 6, 8))
    pygame.draw.rect(s, body, (x0, 12, w, 13))
    pygame.draw.rect(s, dark, (x0, 12, w, 13), 2)
    if opened:
        pygame.draw.rect(s, _shade(body, 0.6), (x0, 4, w, 9))
        pygame.draw.rect(s, (255, 214, 90), (x0 + 3, 12, w - 6, 3))
    else:
        pygame.draw.rect(s, _shade(body, 1.2), (x0, 4, w, 10), border_top_left_radius=6, border_top_right_radius=6)
        pygame.draw.rect(s, dark, (x0, 4, w, 10), 2, border_top_left_radius=6, border_top_right_radius=6)
    for bx in (x0 + 4, x0 + w - 7):
        pygame.draw.rect(s, gold, (bx, 4 if not opened else 12, 3, 21 if not opened else 13))
    lock = (255, 236, 150) if ready else (110, 110, 120)
    pygame.draw.rect(s, lock, (x0 + w // 2 - 3, 12, 6, 7))
    if not opened and not ready:   # chained shut
        for i in range(5):
            pygame.draw.ellipse(s, (150, 150, 160), (x0 - 2 + i * (w // 4), 14, 7, 5), 1)
    return _outline(s)


def _tablet(theme):
    s = _blank(26, 40)
    pygame.draw.ellipse(s, (0, 0, 0, 90), (0, 32, 26, 8))
    pygame.draw.rect(s, _shade(theme.wall, 0.9), (3, 6, 20, 30), border_top_left_radius=9, border_top_right_radius=9)
    pygame.draw.rect(s, theme.wall_hi, (3, 6, 20, 30), 2, border_top_left_radius=9, border_top_right_radius=9)
    for y in range(13, 32, 5):
        pygame.draw.line(s, theme.wall_dark, (7, y), (19, y), 2)
    return _outline(s)


KEEPSAKE_COLORS = {"goblin": (120, 220, 110), "berserker": (230, 70, 60), "lich": (200, 190, 255)}


def _keepsake(sid):
    """The Veil Anchor core: a jagged crystal on a stone stub, in its dungeon's colour."""
    s = _blank(26, 34)
    c = KEEPSAKE_COLORS.get(sid, (255, 220, 120))
    dark, light = _shade(c, 0.5), _mix(c, (255, 255, 255), 0.55)
    pygame.draw.ellipse(s, (60, 56, 60), (3, 26, 20, 7))
    pygame.draw.polygon(s, dark, [(13, 1), (21, 10), (19, 27), (7, 27), (5, 10)])
    pygame.draw.polygon(s, c, [(13, 3), (19, 11), (17, 25), (13, 26), (8, 12)])
    pygame.draw.line(s, light, (12, 6), (10, 20), 2)
    if sid == "goblin":       # thorns
        for x, y, dx in ((5, 12, -4), (21, 15, 4), (6, 21, -4)):
            pygame.draw.line(s, (80, 150, 60), (x, y), (x + dx, y - 3), 2)
    elif sid == "berserker":  # a beating red core
        pygame.draw.circle(s, (255, 190, 170), (13, 16), 3)
    else:                     # bone ring
        pygame.draw.arc(s, (240, 236, 220), (4, 10, 18, 10), 3.3, 6.1, 2)
    pygame.draw.line(s, _shade(c, 0.35), (15, 9), (17, 18), 1)          # crack
    return _outline(s)


def _quest_item(item):
    s = _blank(20, 20)
    if item == "scrap":
        pygame.draw.polygon(s, (96, 82, 74), [(3, 14), (7, 6), (14, 4), (17, 10), (13, 16), (6, 17)])
        pygame.draw.polygon(s, (150, 120, 96), [(6, 13), (8, 8), (13, 7), (14, 11)])
        pygame.draw.line(s, (176, 96, 52), (5, 14), (11, 15), 2)
        pygame.draw.circle(s, (60, 54, 52), (12, 11), 2)
    elif item == "badge":
        pygame.draw.circle(s, (120, 124, 140), (10, 10), 8)
        pygame.draw.circle(s, (206, 212, 226), (10, 10), 6)
        pygame.draw.ellipse(s, (130, 90, 50), (7, 8, 6, 7))                  # acorn
        pygame.draw.rect(s, (90, 60, 30), (7, 6, 6, 3))
        pygame.draw.line(s, (90, 60, 30), (10, 4), (10, 6), 1)
    else:  # ward shard: blue ward-glass
        pygame.draw.polygon(s, (40, 80, 170), [(10, 1), (16, 9), (12, 19), (5, 15), (4, 7)])
        pygame.draw.polygon(s, (110, 170, 255), [(10, 3), (14, 9), (11, 16), (7, 13), (6, 8)])
        pygame.draw.polygon(s, (220, 240, 255), [(10, 6), (12, 9), (10, 12), (8, 9)])
    return _outline(s)


def _key_item():
    s = _blank(22, 14)
    pygame.draw.circle(s, (240, 196, 70), (5, 7), 5)
    pygame.draw.circle(s, (90, 60, 10), (5, 7), 2)
    pygame.draw.rect(s, (240, 196, 70), (9, 6, 12, 3))
    pygame.draw.rect(s, (240, 196, 70), (15, 9, 2, 4))
    pygame.draw.rect(s, (240, 196, 70), (19, 9, 2, 3))
    pygame.draw.line(s, (255, 240, 170), (10, 6), (19, 6), 1)
    return _outline(s)


def _seal_item():
    s = _blank(20, 20)
    pygame.draw.polygon(s, (120, 70, 200), [(10, 0), (19, 10), (10, 19), (1, 10)])
    pygame.draw.polygon(s, (200, 160, 255), [(10, 4), (15, 10), (10, 16), (5, 10)])
    pygame.draw.line(s, (255, 240, 255), (10, 6), (10, 14), 1)
    pygame.draw.line(s, (255, 240, 255), (7, 10), (13, 10), 1)
    return _outline(s)


def _font_sprite(theme):
    """Healing font for shrine rooms: a stone basin with glowing water."""
    s = _blank(40, 40)
    pygame.draw.ellipse(s, (0, 0, 0, 100), (2, 30, 36, 10))
    pygame.draw.rect(s, _shade(theme.wall, 0.8), (13, 20, 14, 14))
    pygame.draw.ellipse(s, theme.wall, (3, 10, 34, 16))
    pygame.draw.ellipse(s, theme.wall_hi, (3, 10, 34, 16), 2)
    pygame.draw.ellipse(s, (60, 170, 220), (8, 13, 24, 9))
    pygame.draw.ellipse(s, (170, 230, 255), (12, 14, 10, 4))
    return _outline(s)


def _gate_sprite(theme, vertical, seals):
    """Locked door (iron portcullis + padlock) or boss gate (rune slab with seal sockets).
    vertical = the doorway runs up and down (corridor enters from the side)."""
    w, h = (24, 3 * TILE + 26) if vertical else (3 * TILE + 8, 50)
    s = _blank(w, h)
    iron, dark = (96, 98, 110), (40, 40, 50)
    if seals:
        slab, hi = _mix(_shade(theme.wall, 0.9), (70, 50, 110), 0.45), _mix(theme.wall_hi, (190, 150, 255), 0.5)
        pygame.draw.rect(s, slab, (0, 0, w, h), border_radius=4)
        pygame.draw.rect(s, hi, (0, 0, w, h), 2, border_radius=4)
        pygame.draw.rect(s, dark, (3, 3, w - 6, h - 6), 1, border_radius=3)
        for k in range(4, (h if vertical else w) - 4, 9):          # carved runes
            if vertical:
                pygame.draw.line(s, _shade(hi, 0.7), (5, k), (8, k + 3), 1)
                pygame.draw.line(s, _shade(hi, 0.7), (w - 6, k + 3), (w - 9, k), 1)
            else:
                pygame.draw.line(s, _shade(hi, 0.7), (k, 5), (k + 3, 8), 1)
                pygame.draw.line(s, _shade(hi, 0.7), (k + 3, h - 6), (k, h - 9), 1)
    else:
        pygame.draw.rect(s, dark, (0, 0, w, h))
        if vertical:
            for y in range(4, h - 2, 8):
                pygame.draw.rect(s, iron, (1, y, w - 2, 3))
            pygame.draw.rect(s, iron, (w // 2 - 2, 0, 4, h))
        else:
            for x in range(4, w - 2, 8):
                pygame.draw.rect(s, iron, (x, 0, 3, h))
            for y in (8, h - 12):
                pygame.draw.rect(s, (120, 122, 134), (0, y, w, 4))
        pygame.draw.rect(s, (150, 152, 166), (0, 0, w, h), 2)
    return _outline(s)


def _up(s, k=1.35):
    """Breakables read better slightly larger than the base pixel art."""
    return pygame.transform.scale(s, (int(s.get_width() * k), int(s.get_height() * k)))


POT_STYLE = {
    "forest": ((166, 98, 60), (90, 140, 70)),
    "stone": ((140, 120, 104), (70, 90, 140)),
    "hell": ((70, 50, 52), (220, 90, 40)),
}


# --------------------------------------------------------------------------- #
#  interactables
# --------------------------------------------------------------------------- #
class Interactables:
    def __init__(self, d, save):
        self.d, self.save = d, save
        d.interact = self
        self.rng = random.Random("loot" + rng_key(d))
        self.roles = room_roles(d)
        self.did, self.floor = (int(v) for v in d.floor_name.split("-"))
        self.sid = SURFACE_IDS.get(self.did)
        self.tier = getattr(d, "tier", None) or min(3, max(1, (self.did - 1) % 3 + 1))
        self.events: list = []
        self.coins: list = []          # [x, y, z, vx, vy, vz, value, age]
        self.parts: list = []          # [x, y, vx, vy, life, color]
        self.floaters: list = []       # [x, y, text, life, color]
        self.t = 0.0
        self.snd_cd = 0.0
        self.reach = self._flood()
        th = d.theme.key
        pc_, band = POT_STYLE.get(th, POT_STYLE["stone"])
        self.pot_imgs = [_up(_pot(pc_, band)), _up(_pot(_shade(pc_, 1.15), band)), _up(_crate())]
        self.breakables = []
        self.chests = []
        self.spikes = []
        self.tablet = None
        self.keepsake = None
        self.drops = []                 # floor key / boss seals waiting in their rooms
        self.gate = None                # the locked stairs door / boss gate
        self.fonts = []                 # healing fonts in shrine rooms
        self.keys = 0
        self.seals = 0
        self._place_objectives()
        self._place_breakables()
        self._place_chests()
        self._place_spikes()
        self._place_story()
        self.qitems = []
        self._place_quest_items()

    # ---- placement -----------------------------------------------------------------
    def _place_objectives(self):
        """Key / seal drops, the gate in front of the last room and the shrine fonts."""
        d, roles = self.d, self.roles
        kind = "seal" if self.floor == 3 else "key"
        sources = ("seal", "miniboss") if kind == "seal" else ("guard", "miniboss")
        for k, role in enumerate(roles):
            r = d.rooms[k]
            if role in sources:
                self.drops.append(dict(room=k, kind=kind, x=r.centerx * TILE + TILE // 2,
                                       y=r.centery * TILE + TILE // 2, state="hidden", t=0.0))
            elif role == "shrine":
                tx, ty = r.centerx, r.centery
                d.solid[ty * MAP_W + tx] = 1
                self.fonts.append(dict(tx=tx, ty=ty, x=tx * TILE + TILE // 2, y=(ty + 1) * TILE - 2,
                                       used=False, img=_font_sprite(d.theme)))
        self.need = len(self.drops)
        last = len(d.rooms) - 1
        if roles[last] not in ("stairs", "boss") or not self.need:
            return
        parent = getattr(d, "parent", None)
        other = parent[last] if parent else last - 1
        door = getattr(d, "door_of", {}).get((last, other))
        if not door:
            return
        nx, ny, dx, dy = door
        vertical = dx != 0
        cells = [(nx, ny + o) for o in (-1, 0, 1)] if vertical else [(nx + o, ny) for o in (-1, 0, 1)]
        for x, y in cells:
            d.solid[y * MAP_W + x] = 1
        self.gate = dict(cells=cells, kind=kind, vertical=vertical, open=False, t=0.0,
                         x=nx * TILE + TILE // 2, y=ny * TILE + TILE // 2,
                         img=_gate_sprite(d.theme, vertical, kind == "seal"))

    def _flood(self):
        d = self.d
        sx, sy = int(d.spawn[0] // TILE), int(d.spawn[1] // TILE)
        seen = {(sx, sy)}
        stack = [(sx, sy)]
        while stack:
            x, y = stack.pop()
            for nx, ny in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
                if (nx, ny) in seen or not (0 <= nx < MAP_W and 0 <= ny < MAP_H):
                    continue
                i = ny * MAP_W + nx
                if d.tiles[i] in WALK and not d.solid[i]:
                    seen.add((nx, ny))
                    stack.append((nx, ny))
        return seen

    def _free(self, tx, ty, r, zone=1, clear=4):
        d = self.d
        if (tx, ty) not in self.reach or d.solid[ty * MAP_W + tx] or d.tiles[ty * MAP_W + tx] != FLOOR:
            return False
        if max(abs(tx - r.centerx), abs(ty - r.centery)) < clear:
            return False
        if d.near_zone(tx, ty, zone):
            return False
        return (tx, ty + 1) in self.reach

    def _place_breakables(self):
        d, rng = self.d, self.rng
        for k, r in enumerate(d.rooms):
            want = rng.randint(3, 6)
            for _ in range(200):
                if want <= 0:
                    break
                tx, ty = rng.randrange(r.x + 1, r.right - 1), rng.randrange(r.y + 1, r.bottom - 1)
                if not self._free(tx, ty, r):
                    continue
                if not d.edge[ty * MAP_W + tx] and rng.random() < 0.8:   # prefer hugging walls
                    continue
                if any(abs(b["tx"] - tx) + abs(b["ty"] - ty) < 2 for b in self.breakables):
                    continue
                img = rng.choice(self.pot_imgs)
                d.solid[ty * MAP_W + tx] = 1
                self.breakables.append(dict(tx=tx, ty=ty, img=img, x=tx * TILE + TILE // 2,
                                            y=(ty + 1) * TILE - 3, alive=True))
                want -= 1

    def _spot_near(self, r, gx, gy, clear=5):
        best, bd = None, 1e9
        for ty in range(r.y + 1, r.bottom - 1):
            for tx in range(r.x + 1, r.right - 1):
                if not self._free(tx, ty, r, zone=1, clear=clear):
                    continue
                dd = (tx - gx) ** 2 + (ty - gy) ** 2
                if dd < bd:
                    best, bd = (tx, ty), dd
        return best

    def _place_chests(self):
        d = self.d
        for k, r in enumerate(d.rooms):
            role = self.roles[k]
            if role not in ("combat", "guard", "seal", "miniboss", "vault", "boss", "lair"):
                continue
            big = role in ("boss", "vault", "miniboss", "lair")
            spot = self._spot_near(r, r.centerx + (0 if big else (4 if k % 2 else -4)), r.y + 3)
            if not spot:
                continue
            tx, ty = spot
            d.solid[ty * MAP_W + tx] = 1
            gold = self.rng.randint(6, 10) * self.tier * {"boss": 6, "vault": 3, "miniboss": 3, "lair": 4}.get(role, 1)
            self.chests.append(dict(room=k, tx=tx, ty=ty, x=tx * TILE + TILE // 2, y=(ty + 1) * TILE - 2,
                                    gold=gold, big=big, state="locked", pop=0.0))

    def _place_trap_hall(self, r):
        """Gauntlet: rows of spikes across the hall, each with a gap, firing in a wave."""
        d = self.d
        across = r.w >= r.h
        length = r.w if across else r.h
        for n, step in enumerate(range(3, length - 3, 3)):
            cells = []
            span = range(r.y + 1, r.bottom - 1) if across else range(r.x + 1, r.right - 1)
            gap = self.rng.randrange(span.start + 1, span.stop - 2)
            for c in span:
                if gap <= c <= gap + 1:
                    continue
                tx, ty = (r.x + step, c) if across else (c, r.y + step)
                i = ty * MAP_W + tx
                if d.tiles[i] == FLOOR and not d.solid[i] and not d.near_zone(tx, ty, 1):
                    cells.append((tx, ty))
            if cells:
                self.spikes.append(dict(cells=cells, phase=(n * 0.45) % 2.6))

    def _place_spikes(self):
        d, rng = self.d, self.rng
        for k, r in enumerate(d.rooms):
            if self.roles[k] == "trap":
                self._place_trap_hall(r)
                continue
            if self.floor < 2 or self.roles[k] not in ("combat", "guard", "seal", "vault"):
                continue
            for _ in range(rng.randint(2, 4)):
                for _try in range(60):
                    tx, ty = rng.randrange(r.x + 2, r.right - 3), rng.randrange(r.y + 2, r.bottom - 2)
                    n = rng.randint(2, 3)
                    cells = [(tx + i, ty) for i in range(n)]
                    if all(self._free(x, y, r, zone=1, clear=5) for x, y in cells) and \
                            not any((x, y) in s["cells"] for s in self.spikes for x, y in cells):
                        self.spikes.append(dict(cells=cells, phase=rng.random() * 2.6))
                        break

    def _place_story(self):
        d = self.d
        if not self.sid:
            return
        if self.floor in (1, 2):
            r = d.rooms[0]
            spot = self._spot_near(r, r.centerx + 7, r.y + 2, clear=5)
            if spot:
                tx, ty = spot
                d.solid[ty * MAP_W + tx] = 1
                self.tablet = dict(tx=tx, ty=ty, x=tx * TILE + TILE // 2, y=(ty + 1) * TILE - 2,
                                   img=_tablet(d.theme), lines=story.LORE[self.sid][self.floor - 1],
                                   flag=f"lore_{self.sid}_{self.floor}")
        elif self.floor == 3 and self.sid not in self.save.keepsakes:
            ex, ey = d.exit_pos
            r = d.rooms[-1]
            tx, ty = int(ex // TILE), int(ey // TILE) + 4
            if (tx, ty) not in self.reach:
                spot = self._spot_near(r, tx, ty, clear=0)
                if spot:
                    tx, ty = spot
            self.keepsake = dict(x=tx * TILE + TILE // 2, y=ty * TILE + TILE // 2, img=_up(_keepsake(self.sid), 1.5),
                                 state="hidden", t=0.0)

    def _place_quest_items(self):
        """Side-quest pickups, only while the quest is in progress and never twice."""
        book = quests.QuestBook(self.save)
        d = self.d
        rng = random.Random("quest" + rng_key(d))
        rooms = [k for k, role in enumerate(self.roles) if role in ("combat", "guard", "seal", "vault", "miniboss")]
        for q in book.dungeon_quests(self.sid):
            per_floor = q["dungeon"][1]
            n = per_floor[self.floor - 1] if self.floor <= len(per_floor) else 0
            picks = rng.sample(rooms, min(n, len(rooms))) if rooms else []
            for i, k in enumerate(picks):
                key = "%s_%d" % (d.floor_name, i)
                if "got_%s_%s" % (q["item"], key) in self.save.flags:
                    continue
                r = d.rooms[k]
                spot = self._spot_near(r, r.x + rng.randint(3, r.w - 4), r.y + rng.randint(3, r.h - 4), clear=5)
                if spot:
                    tx, ty = spot
                    self.qitems.append(dict(item=q["item"], key=key, x=tx * TILE + TILE // 2,
                                            y=ty * TILE + TILE // 2, img=_quest_item(q["item"]), t=rng.random() * 6))

    # ---- per frame -------------------------------------------------------------------
    def pop_events(self):
        ev, self.events = self.events, []
        return ev

    def _sound(self, name):
        if self.snd_cd <= 0:
            self.events.append(("sound", name))
            self.snd_cd = 0.07

    def _spill(self, x, y, total, burst=1.0):
        while total > 0:
            v = min(total, self.rng.choice((1, 1, 2, 5)) if total < 40 else 10)
            total -= v
            a = self.rng.random() * math.tau
            sp = self.rng.uniform(30, 110) * burst
            self.coins.append([x, y, 0.0, math.cos(a) * sp, math.sin(a) * sp * 0.6,
                               self.rng.uniform(140, 240) * burst, v, 0.0])

    def _shards(self, x, y, col, n=12):
        for _ in range(n):
            a = self.rng.random() * math.tau
            sp = self.rng.uniform(40, 150)
            self.parts.append([x, y, math.cos(a) * sp, math.sin(a) * sp - 60, self.rng.uniform(0.4, 0.8), col])

    def swing(self, player, direction):
        """Called right after the player swings the sword."""
        dx, dy = direction
        hx, hy = player.x, player.y - 10
        for b in self.breakables:
            if not b["alive"]:
                continue
            vx, vy = b["x"] - hx, b["y"] - 10 - hy
            dist = math.hypot(vx, vy) or 1.0
            if dist <= 66 and (vx * dx + vy * dy) / dist >= -0.1:
                b["alive"] = False
                self.d.solid[b["ty"] * MAP_W + b["tx"]] = 0
                self._shards(b["x"], b["y"] - 10, (150, 110, 80))
                self._sound("hit")
                self._spill(b["x"], b["y"] - 8, self.rng.randint(1, 3) * self.tier)
                if self.rng.random() < 0.05:
                    self.events.append(("potion",))

    def update(self, dt, player, pc, enc):
        self.t += dt
        self.snd_cd = max(0.0, self.snd_cd - dt)
        d = self.d
        states = getattr(enc, "state", None) or []

        # chests open once their room is cleared
        for c in self.chests:
            cleared = c["room"] < len(states) and states[c["room"]] == "cleared"
            if c["state"] == "locked" and cleared:
                c["state"] = "ready"
                self._shards(c["x"], c["y"] - 14, (255, 220, 120), 8)
            elif c["state"] == "ready" and math.hypot(player.x - c["x"], player.y - c["y"]) < 36:
                c["state"] = "open"
                c["pop"] = 0.35
                self._spill(c["x"], c["y"] - 14, c["gold"], 1.4 if c["big"] else 1.0)
                self._shards(c["x"], c["y"] - 14, (255, 230, 140), 18)
                self._sound("clear")
                self.floaters.append([c["x"], c["y"] - 40, "+%d gold" % c["gold"], 1.4, (255, 226, 130)])
            c["pop"] = max(0.0, c["pop"] - dt)

        # spikes
        for s in self.spikes:
            ph = (self.t + s["phase"]) % 2.6
            s["mode"] = "up" if ph >= 2.0 else ("warn" if ph >= 1.5 else "down")
            if s["mode"] == "up" and not pc.dead:
                ptx, pty = int(player.x // TILE), int(player.y // TILE)
                if (ptx, pty) in s["cells"]:
                    fx, fy = ptx * TILE + TILE // 2, pty * TILE + TILE // 2
                    pc.hurt(1 + self.tier, player, d, fx, fy - 6)   # the Game shows the number and plays the sound

        # keepsake
        k = self.keepsake
        if k:
            k["t"] += dt
            boss = len(d.rooms) - 1
            if k["state"] == "hidden" and boss < len(states) and states[boss] == "cleared":
                k["state"] = "shown"
                self._shards(k["x"], k["y"], (255, 230, 160), 24)
                self.events.append(("toast", "The Veil Anchor is exposed where the boss fell!", (255, 226, 140)))
            elif k["state"] == "shown" and math.hypot(player.x - k["x"], player.y - k["y"]) < 28:
                self.take_keepsake()

        # floor key / boss seals: appear when their room is cleared, picked up by walking over
        for dr in self.drops:
            dr["t"] += dt
            cleared = dr["room"] < len(states) and states[dr["room"]] == "cleared"
            if dr["state"] == "hidden" and cleared:
                dr["state"] = "shown"
                self._shards(dr["x"], dr["y"] - 10, (255, 220, 120) if dr["kind"] == "key" else (200, 150, 255), 22)
                self.events.append(("toast", "The floor key drops!" if dr["kind"] == "key" else "A boss seal glows...",
                                    (255, 226, 140) if dr["kind"] == "key" else (210, 170, 255)))
            elif dr["state"] == "shown" and math.hypot(player.x - dr["x"], player.y - dr["y"]) < 32:
                dr["state"] = "taken"
                self._shards(dr["x"], dr["y"] - 10, (255, 240, 200), 20)
                self._sound("clear")
                if dr["kind"] == "key":
                    self.keys += 1
                    self.events.append(("toast", "Got the floor key! Open the stairs door.", (255, 226, 140)))
                else:
                    self.seals += 1
                    msg = "Boss seal %d/%d" % (self.seals, self.need)
                    if self.seals >= self.need:
                        msg += "  -  the boss gate can be opened!"
                    self.events.append(("toast", msg, (210, 170, 255)))
        if self.gate:
            self.gate["t"] += dt

        # side-quest pickups
        for qi in self.qitems:
            qi["t"] += dt
        for qi in [q for q in self.qitems if math.hypot(player.x - q["x"], player.y - q["y"]) < 30]:
            self.qitems.remove(qi)
            got = quests.QuestBook(self.save).collect(qi["item"], qi["key"])
            self._shards(qi["x"], qi["y"] - 10, (255, 230, 160), 16)
            self._sound("pickup")
            if got:
                n, need, q = got
                msg = "%s  %d/%d" % (q["item_name"].capitalize(), n, need)
                if n >= need:
                    msg += "  -  return to " + story.NPC_NAMES.get(q["giver"], story.SURVIVOR).split(" the ")[0]
                self.events.append(("toast", msg, (255, 214, 120)))
                self.events.append(("save",))

        # coins: hop, land, then fly to the player
        for c in self.coins:
            c[7] += dt
            if c[2] > 0 or c[5] > 0:
                c[0] += c[3] * dt
                c[1] += c[4] * dt
                c[2] += c[5] * dt
                c[5] -= 600 * dt
                if c[2] <= 0:
                    c[2], c[5] = 0.0, (-c[5] * 0.35 if c[5] < -60 else 0.0)
                    c[3] *= 0.5
                    c[4] *= 0.5
            if c[7] > 0.45:
                dx, dy = player.x - c[0], player.y - 12 - c[1]
                dist = math.hypot(dx, dy)
                if dist < 140:
                    sp = 260 + (140 - dist) * 4
                    c[0] += dx / (dist or 1) * sp * dt
                    c[1] += dy / (dist or 1) * sp * dt
                if dist < 16:
                    self.save.gold += c[6]
                    c[6] = 0
                    self._sound("pickup")
        self.coins = [c for c in self.coins if c[6] > 0]
        for p in self.parts:
            p[0] += p[2] * dt
            p[1] += p[3] * dt
            p[3] += 380 * dt
            p[4] -= dt
        self.parts = [p for p in self.parts if p[4] > 0]
        for f in self.floaters:
            f[1] -= 30 * dt
            f[3] -= dt
        self.floaters = [f for f in self.floaters if f[3] > 0]

    def take_keepsake(self) -> bool:
        """Pick up the boss floor's keepsake if it is lying there. Also used by the exit,
        so a player who walks past it can't leave the dungeon without it."""
        k = self.keepsake
        if not k or k["state"] != "shown":
            return False
        k["state"] = "taken"
        name, lines = story.KEEPSAKES[self.sid]
        self.save.keepsakes.add(self.sid)
        self._shards(k["x"], k["y"], (255, 240, 200), 30)
        self._sound("victory")
        self.events.append(("toast", "Shattered: " + name, (255, 226, 140)))
        self.events.append(("dialog", lines))
        self.events.append(("save",))
        return True

    # ---- E key -------------------------------------------------------------------
    def _near_tablet(self, player):
        tb = self.tablet
        return tb and math.hypot(player.x - tb["x"], player.y - tb["y"]) < 48

    def _near_gate(self, player):
        g = self.gate
        return g and not g["open"] and math.hypot(player.x - g["x"], player.y - g["y"]) < 76

    def _near_font(self, player):
        return next((f for f in self.fonts if math.hypot(player.x - f["x"], player.y - f["y"]) < 52), None)

    def gate_ready(self):
        g = self.gate
        if not g:
            return True
        return self.keys >= 1 if g["kind"] == "key" else self.seals >= self.need

    def prompt(self, player):
        if self._near_tablet(player):
            return "[E]  Read the inscription"
        if self._near_gate(player):
            if self.gate["kind"] == "key":
                return "[E]  Unlock the stairs door" if self.gate_ready() else "Locked - find the floor key"
            return "[E]  Open the boss gate" if self.gate_ready() else \
                "Boss gate - seals %d/%d" % (self.seals, self.need)
        f = self._near_font(player)
        if f:
            return "[E]  Drink from the healing font" if not f["used"] else "The font is dry"
        return None

    def open_gate(self):
        g = self.gate
        g["open"] = True
        for x, y in g["cells"]:
            self.d.solid[y * MAP_W + x] = 0
        self._shards(g["x"], g["y"] - 10, (255, 230, 160) if g["kind"] == "key" else (200, 150, 255), 34)
        self._sound("clear")
        self.events.append(("toast", "The stairs door swings open." if g["kind"] == "key" else
                            "The seals blaze - the boss gate grinds open!", (255, 226, 140)))

    def use(self, player):
        if self._near_tablet(player):
            tb = self.tablet
            self.save.flags.add(tb["flag"])
            self.events.append(("dialog", tb["lines"]))
            return True
        if self._near_gate(player):
            if self.gate_ready():
                self.open_gate()
            else:
                self._sound("blip")
                self.gate["t"] = 0.0
                if self.gate["kind"] == "key":
                    self.events.append(("toast", "Locked. The floor key is somewhere on this floor.", (255, 170, 150)))
                else:
                    self.events.append(("toast", "The gate needs %d boss seals (%d/%d)." % (self.need, self.seals, self.need),
                                        (210, 170, 255)))
            return True
        f = self._near_font(player)
        if f:
            if not f["used"]:
                f["used"] = True
                self._shards(f["x"], f["y"] - 24, (170, 230, 255), 22)
                self._sound("potion")
                self.events.append(("heal",))
                self.events.append(("toast", "The cool water restores you.", (170, 230, 255)))
            return True
        return False

    def objective(self):
        """One HUD line about what opens the way on, or None."""
        g = self.gate
        if not g:
            return None
        if g["open"]:
            return ("Stairs door open - go down" if g["kind"] == "key" else "Boss gate open"), (150, 220, 150)
        if g["kind"] == "key":
            if self.keys:
                return "Floor key: found - unlock the stairs door", (255, 214, 120)
            return "Floor key: find it (guarded room)", (255, 214, 120)
        return "Boss seals: %d/%d" % (self.seals, self.need), (210, 170, 255)

    def map_markers(self):
        """[(tx, ty, kind)] for the minimap: key / seal rooms, shrines, the gate."""
        out = []
        for dr in self.drops:
            if dr["state"] != "taken":
                out.append((dr["x"] // TILE, dr["y"] // TILE, dr["kind"]))
        for f in self.fonts:
            if not f["used"]:
                out.append((f["tx"], f["ty"], "font"))
        if self.gate and not self.gate["open"]:
            out.append((self.gate["x"] // TILE, self.gate["y"] // TILE, "gate"))
        return out

    # ---- drawing ------------------------------------------------------------------
    def draw_floor(self, surf, cx, cy, t):
        """Spike traps (drawn on the floor under everything else)."""
        for s in self.spikes:
            mode = s.get("mode", "down")
            for tx, ty in s["cells"]:
                px, py = tx * TILE - cx, ty * TILE - cy
                if px < -TILE or py < -TILE or px > surf.get_width() or py > surf.get_height():
                    continue
                pygame.draw.rect(surf, (40, 36, 40), (px + 1, py + 1, TILE - 2, TILE - 2))
                pygame.draw.rect(surf, (70, 66, 72), (px + 1, py + 1, TILE - 2, TILE - 2), 1)
                for hx in (6, 12, 18):
                    for hy in (7, 16):
                        if mode == "up":
                            pygame.draw.polygon(surf, (210, 214, 224),
                                                [(px + hx - 3, py + hy + 3), (px + hx + 3, py + hy + 3), (px + hx, py + hy - 7)])
                            surf.fill((255, 255, 255), (px + hx, py + hy - 6, 1, 2))
                        elif mode == "warn":
                            k = int(t * 30) % 2
                            pygame.draw.polygon(surf, (150, 150, 160),
                                                [(px + hx - 2, py + hy + 2), (px + hx + 2, py + hy + 2), (px + hx, py + hy - 1 - k)])
                        else:
                            surf.fill((18, 16, 20), (px + hx - 1, py + hy, 3, 2))

    def sprites(self):
        """[(world_feet_y, draw(surf, cx, cy, t))] to be y-sorted with props and the player."""
        out = []
        for b in self.breakables:
            if b["alive"]:
                out.append((b["y"], self._draw_img(b["img"], b["x"], b["y"])))
        for c in self.chests:
            out.append((c["y"], self._draw_chest(c)))
        tb = self.tablet
        if tb:
            out.append((tb["y"], self._draw_img(tb["img"], tb["x"], tb["y"])))
        k = self.keepsake
        if k and k["state"] == "shown":
            out.append((k["y"] + 6, self._draw_keepsake(k)))
        for qi in self.qitems:
            out.append((qi["y"] + 4, self._draw_qitem(qi)))
        for dr in self.drops:
            if dr["state"] == "shown":
                out.append((dr["y"] + 4, self._draw_drop(dr)))
        for f in self.fonts:
            out.append((f["y"], self._draw_font(f)))
        g = self.gate
        if g and not g["open"]:
            out.append((g["y"] + (2 * TILE if g["vertical"] else TILE // 2), self._draw_gate(g)))
        return out

    _drop_imgs: dict = {}

    def _draw_drop(self, dr):
        def fn(surf, cx, cy, t):
            img = self._drop_imgs.get(dr["kind"])
            if img is None:
                img = self._drop_imgs[dr["kind"]] = pygame.transform.scale2x(
                    _key_item() if dr["kind"] == "key" else _seal_item())
            bob = math.sin(dr["t"] * 3) * 4
            x, y = dr["x"] - cx, dr["y"] - cy
            pygame.draw.ellipse(surf, (0, 0, 0), (x - 10, y - 2, 20, 6))
            surf.blit(img, (int(x - img.get_width() / 2), int(y - 24 + bob - img.get_height() / 2)))
            for i in range(3):
                a = t * 2.4 + i * math.tau / 3
                surf.fill((255, 245, 210), (int(x + math.cos(a) * 18), int(y - 24 + bob + math.sin(a) * 9), 2, 2))
        return fn

    def _draw_font(self, f):
        def fn(surf, cx, cy, t):
            img = f["img"]
            x, y = f["x"] - cx, f["y"] - cy
            surf.blit(img, (x - img.get_width() // 2, y - img.get_height() + 4))
            if not f["used"]:
                for i in range(3):
                    k = (t * 0.8 + i / 3) % 1.0
                    surf.fill((200, 240, 255), (int(x - 6 + i * 6), int(y - 26 - k * 18), 2, 2))
        return fn

    def _draw_gate(self, g):
        def fn(surf, cx, cy, t):
            img = g["img"]
            shake = int(math.sin(g["t"] * 50) * 3) if g["t"] < 0.3 else 0
            x, y = g["x"] - cx + shake, g["y"] - cy
            if g["vertical"]:
                surf.blit(img, (x - img.get_width() // 2, y - img.get_height() // 2 - 8))
            else:
                surf.blit(img, (x - img.get_width() // 2, y - img.get_height() + TILE // 2 + 4))
            # padlock / seal sockets in the middle
            mx, my = x, (y - 8 if g["vertical"] else y - 14)
            if g["kind"] == "key":
                col = (255, 214, 90) if self.keys else (200, 170, 70)
                pygame.draw.circle(surf, (40, 30, 10), (mx, my - 6), 6, 2)
                pygame.draw.rect(surf, (40, 30, 10), (mx - 8, my - 4, 16, 14))
                pygame.draw.rect(surf, col, (mx - 7, my - 3, 14, 12))
                pygame.draw.circle(surf, col, (mx, my - 6), 5, 2)
                pygame.draw.rect(surf, (40, 30, 10), (mx - 1, my + 1, 2, 5))
            else:
                n = max(1, self.need)
                for i in range(n):
                    o = (i - (n - 1) / 2) * 16
                    sx, sy = (mx, int(my + o)) if g["vertical"] else (int(mx + o), my)
                    lit = i < self.seals
                    pts = [(sx, sy - 6), (sx + 6, sy), (sx, sy + 6), (sx - 6, sy)]
                    pygame.draw.polygon(surf, (20, 14, 30), [(px, py + 1) for px, py in pts])
                    if lit:
                        pygame.draw.polygon(surf, (225, 190, 255), pts)
                        surf.fill((255, 255, 255), (sx - 1, sy - 3, 2, 2))
                    else:
                        pygame.draw.polygon(surf, (40, 30, 60), pts)
                        pygame.draw.polygon(surf, (150, 120, 200), pts, 1)
        return fn

    @staticmethod
    def _draw_qitem(qi):
        def fn(surf, cx, cy, t):
            img = qi["img"]
            bob = math.sin(qi["t"] * 3) * 3
            x, y = qi["x"] - cx, qi["y"] - cy
            pygame.draw.ellipse(surf, (0, 0, 0), (x - 7, y - 2, 14, 5))
            surf.blit(img, (int(x - img.get_width() / 2), int(y - 16 + bob - img.get_height() / 2)))
            if int(qi["t"] * 2) % 3 == 0:
                surf.fill((255, 250, 220), (int(x + 7), int(y - 22 + bob), 2, 2))
        return fn

    @staticmethod
    def _draw_img(img, x, y):
        def fn(surf, cx, cy, t):
            surf.blit(img, (x - img.get_width() // 2 - cx, y - img.get_height() + 3 - cy))
        return fn

    _chest_cache: dict = {}

    def _draw_chest(self, c):
        def fn(surf, cx, cy, t):
            key = (c["state"] == "open", c["big"], c["state"] == "ready")
            img = self._chest_cache.get(key)
            if img is None:
                img = self._chest_cache[key] = _chest(*key)
            lift = int(c["pop"] * 14)
            bob = int(math.sin(t * 6) * 1.5) if c["state"] == "ready" else 0
            surf.blit(img, (c["x"] - img.get_width() // 2 - cx, c["y"] - img.get_height() + 3 - cy - lift - bob))
        return fn

    @staticmethod
    def _draw_keepsake(k):
        def fn(surf, cx, cy, t):
            img = k["img"]
            bob = math.sin(k["t"] * 3) * 4
            x, y = k["x"] - cx, k["y"] - cy - 20 + bob
            pygame.draw.ellipse(surf, (0, 0, 0), (x - 8, k["y"] - cy - 3, 16, 6))
            surf.blit(img, (int(x - img.get_width() / 2), int(y - img.get_height() / 2)))
            for i in range(4):
                a = t * 2 + i * math.tau / 4
                sx, sy = int(x + math.cos(a) * 16), int(y + math.sin(a) * 8)
                surf.fill((255, 240, 200), (sx, sy, 2, 2))
        return fn

    def glows(self, cx, cy):
        out = []
        th = self.d.theme
        for c in self.chests:
            if c["state"] == "ready":
                out.append((c["x"] - cx, c["y"] - 14 - cy, glow(56, (255, 210, 110), 0.55)))
        tb = self.tablet
        if tb and tb["flag"] not in self.save.flags:
            k = 0.4 + 0.25 * math.sin(self.t * 3)
            out.append((tb["x"] - cx, tb["y"] - 18 - cy, glow(60, th.mote, round(k, 1))))
        k = self.keepsake
        if k and k["state"] == "shown":
            out.append((k["x"] - cx, k["y"] - 20 - cy, glow(80, (255, 220, 160), 0.7)))
        for qi in self.qitems:
            col = {"scrap": (200, 170, 130), "badge": (190, 200, 255), "shard": (110, 170, 255)}[qi["item"]]
            out.append((qi["x"] - cx, qi["y"] - 16 - cy, glow(46, col, 0.5)))
        for dr in self.drops:
            if dr["state"] == "shown":
                col = (255, 214, 110) if dr["kind"] == "key" else (190, 130, 255)
                out.append((dr["x"] - cx, dr["y"] - 24 - cy, glow(70, col, 0.7)))
        for f in self.fonts:
            if not f["used"]:
                out.append((f["x"] - cx, f["y"] - 20 - cy, glow(64, (90, 190, 255), 0.55)))
        g = self.gate
        if g and not g["open"] and g["kind"] == "seal":
            out.append((g["x"] - cx, g["y"] - 14 - cy, glow(60, (170, 110, 255), round(0.2 + 0.12 * self.seals, 2))))
        return out

    def draw_fx(self, surf, cx, cy, t):
        for x, y, z, vx, vy, vz, v, age in self.coins:
            sx, sy = int(x - cx), int(y - cy)
            if z > 0:
                pygame.draw.ellipse(surf, (0, 0, 0), (sx - 3, sy - 1, 6, 3))
            spin = abs(math.sin(age * 10 + x))
            w = max(1, int(5 * spin))
            col = (255, 214, 80) if v < 5 else (255, 240, 170)
            r = pygame.Rect(sx - w // 2, sy - int(z) - 5, w, 6 if v < 5 else 8)
            pygame.draw.ellipse(surf, (130, 90, 20), r.inflate(2, 2))
            pygame.draw.ellipse(surf, col, r)
        for x, y, vx, vy, life, col in self.parts:
            k = min(1.0, life / 0.4)
            surf.fill(_shade(col, k), (int(x - cx), int(y - cy), 2, 2))
        if self.floaters:
            font = _font()
            for x, y, text, life, col in self.floaters:
                img = font.render(text, True, col)
                img.set_alpha(int(255 * min(1.0, life / 0.4)))
                sh = font.render(text, True, (0, 0, 0))
                sh.set_alpha(img.get_alpha())
                surf.blit(sh, (int(x - cx) - img.get_width() // 2 + 1, int(y - cy) + 1))
                surf.blit(img, (int(x - cx) - img.get_width() // 2, int(y - cy)))


_FONT = None


def _font():
    global _FONT
    if _FONT is None:
        _FONT = pygame.font.Font(None, 24)
    return _FONT


# --------------------------------------------------------------------------- #
#  locked-room gates
# --------------------------------------------------------------------------- #
def draw_lock_gates(surf, d, enc, cx, cy, t, glows_out):
    """Shimmering rune barriers over the doors of the room the player is locked in."""
    lr = d.lock_rect
    state = d.__dict__.setdefault("_gate_fx", {"prev": None, "parts": []})
    col = d.theme.accent
    doors = []
    if lr is not None:
        zone = lr.inflate(TILE * 3, TILE * 3)
        doors = [(r, v) for r, v in d.doors if zone.colliderect(r)]
    elif state["prev"] is not None:       # just unlocked: burst
        zone = state["prev"].inflate(TILE * 3, TILE * 3)
        for r, v in d.doors:
            if zone.colliderect(r):
                for _ in range(26):
                    a = random.random() * math.tau
                    sp = random.uniform(40, 170)
                    state["parts"].append([r.centerx + random.uniform(-r.w, r.w) / 2,
                                           r.centery + random.uniform(-r.h, r.h) / 2,
                                           math.cos(a) * sp, math.sin(a) * sp, 0.7])
    state["prev"] = lr

    for r, vertical in doors:
        g = r.inflate(16, 8) if vertical else r.inflate(8, 16)
        layer = _blank(g.w, g.h)
        pulse = 0.6 + 0.4 * math.sin(t * 5)
        layer.fill((*col, int(70 + 50 * pulse)))
        if vertical:
            for k in range(6):
                y = int((t * 60 + k * g.h / 6) % g.h)
                pygame.draw.line(layer, (*_mix(col, (255, 255, 255), 0.6), 220), (0, y), (g.w, y), 2)
            pygame.draw.line(layer, (*_mix(col, (255, 255, 255), 0.7), 255), (g.w // 2, 0), (g.w // 2, g.h), 2)
        else:
            for k in range(6):
                x = int((t * 60 + k * g.w / 6) % g.w)
                pygame.draw.line(layer, (*_mix(col, (255, 255, 255), 0.6), 220), (x, 0), (x, g.h), 2)
            pygame.draw.line(layer, (*_mix(col, (255, 255, 255), 0.7), 255), (0, g.h // 2), (g.w, g.h // 2), 2)
        pygame.draw.rect(layer, (*col, 255), layer.get_rect(), 2)
        surf.blit(layer, (g.x - cx, g.y - cy))
        glows_out.append((g.centerx - cx, g.centery - cy, glow(70, col, 0.6)))

    dt = 1 / 60
    for p in state["parts"]:
        p[0] += p[2] * dt
        p[1] += p[3] * dt
        p[2] *= 0.95
        p[3] *= 0.95
        p[4] -= dt
        k = max(0.0, p[4] / 0.7)
        surf.fill(_mix((0, 0, 0), _mix(col, (255, 255, 255), 0.5), k), (int(p[0] - cx), int(p[1] - cy), 3, 3))
    state["parts"] = [p for p in state["parts"] if p[4] > 0]
