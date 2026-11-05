"""
village.py - life for the Oakwood overworld (used by surface_world.py).

    NPCs          villagers with wandering, facing, "!" alerts and name tags
    critters      chickens, sheep, deer, crows and butterflies
    SmokePlume    chimney smoke
    DayNight      slow day/night cycle that drives the ambient light
    Treasure      hidden caches in the forest (pay out once, tracked in save flags)
    dressing      scenery that changes as the story progresses

Everything is procedural; no asset files needed.
"""
from __future__ import annotations

import math
import random

import pygame

try:
    from . import npc_art
    from .story import NPC_BARKS
except ImportError:
    import npc_art
    from story import NPC_BARKS


# --------------------------------------------------------------------------- #
#  small helpers
# --------------------------------------------------------------------------- #
def _shade(c, f):
    return tuple(max(0, min(255, int(v * f))) for v in c[:3])


def _mix(a, b, t):
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))


def _feet_blocked(world, x, y, w=14, h=8):
    r = pygame.Rect(int(x - w / 2), int(y - h), w, h)
    return r.collidelist(world.colliders) != -1 or r.collidelist(world.dyn_colliders) != -1


def _step_toward(ent, tx, ty, speed, dt, world, solid=True):
    """Move ent toward (tx, ty). Returns False when blocked or arrived."""
    dx, dy = tx - ent.x, ty - ent.y
    d = math.hypot(dx, dy)
    if d < 2:
        return False
    vx, vy = dx / d * speed * dt, dy / d * speed * dt
    moved = False
    if not solid or not _feet_blocked(world, ent.x + vx, ent.y):
        ent.x += vx
        moved = True
    if not solid or not _feet_blocked(world, ent.x, ent.y + vy):
        ent.y += vy
        moved = True
    if abs(dx) > abs(dy):
        ent.flip = dx < 0
    return moved


# --------------------------------------------------------------------------- #
#  villager sprites (drawn in npc_art.py)
# --------------------------------------------------------------------------- #
LOOKS = npc_art.LOOKS
make_npc_frames = npc_art.make_npc_frames
portrait = npc_art.portrait


# --------------------------------------------------------------------------- #
#  NPCs
# --------------------------------------------------------------------------- #
class NPC:
    def __init__(self, npc_id, name, x, y, radius=40, shop=None, rng=None, look=None):
        self.id = npc_id
        self.name = name
        self.x, self.y = float(x), float(y)
        self.home = (x, y)
        self.radius = radius
        self.shop = shop
        self.look = look or npc_id
        self.frames = make_npc_frames(LOOKS[self.look])
        self.kid = LOOKS[self.look].get("kid", False)
        self.h = self.frames[("down", 0)].get_height()
        self.facing = "down"
        self.flip = False
        self.walk = 0.0
        self.moving = False
        self.target = None
        self.rng = rng or random.Random(npc_id)
        self.wait = self.rng.uniform(0.5, 3.0)
        self.alert = None           # None | "news" | "quest" | "ready"  (set by the world each frame)
        self.hop = 0.0              # little celebration hop
        self.bark, self.bark_t = None, 0.0
        self.bark_cd = self.rng.uniform(3.0, 9.0)
        self.sort_y = y
        self.rect = pygame.Rect(int(x) - 20, int(y) - 50, 40, 52)

    def update(self, dt, world):
        p = world.player
        dist = math.hypot(p.x - self.x, p.y - self.y)
        near = dist < 80
        self.moving = False
        if near:
            dx, dy = p.x - self.x, p.y - self.y
            if abs(dx) > abs(dy):
                self.facing, self.flip = "side", dx < 0
            else:
                self.facing = "down" if dy > 0 else "up"
        elif self.radius > 0:
            if self.target is None:
                self.wait -= dt
                if self.wait <= 0:
                    a = self.rng.random() * math.tau
                    r = self.rng.random() * self.radius
                    self.target = (self.home[0] + math.cos(a) * r, self.home[1] + math.sin(a) * r * 0.6)
            else:
                ok = _step_toward(self, self.target[0], self.target[1], 46, dt, world)
                if ok:
                    self.moving = True
                    self.walk += dt
                    dx, dy = self.target[0] - self.x, self.target[1] - self.y
                    if abs(dx) > abs(dy):
                        self.facing = "side"
                    else:
                        self.facing = "down" if dy > 0 else "up"
                else:
                    self.target = None
                    self.wait = self.rng.uniform(1.5, 4.5)
                    self.facing = "down"
        if world.stage() >= 1 and self.kid:
            self.hop = (self.hop + dt * 5) % math.tau
        # chatter when the hero walks past (not while standing right next to them)
        self.bark_t = max(0.0, self.bark_t - dt)
        self.bark_cd -= dt
        if self.bark_cd <= 0:
            self.bark_cd = self.rng.uniform(7.0, 14.0)
            st = world.stage()
            pool = [txt for lo, hi, txt in NPC_BARKS.get(self.id, ()) if lo <= st <= hi]
            if pool and 90 < dist < 420:
                self.bark, self.bark_t = self.rng.choice(pool), 3.2
        self.sort_y = self.y
        self.rect.topleft = (int(self.x) - 20, int(self.y) - 50)

    def draw(self, scr, cx, cy, t):
        step = (1 if int(self.walk * 6) % 2 == 0 else 2) if self.moving else 0
        img = self.frames[(self.facing, step)]
        if self.facing == "side" and self.flip:
            img = pygame.transform.flip(img, True, False)
        X, Y = int(self.x - cx), int(self.y - cy)
        lift = int(abs(math.sin(self.hop)) * 6) if self.hop else 0
        pygame.draw.ellipse(scr, (14, 20, 14), (X - 12, Y - 5, 24, 9))
        w, h = img.get_size()
        scr.blit(img, (X - w // 2, Y - h + 4 - lift))

    MARK = {"quest": ((255, 214, 90), "!"), "ready": ((255, 214, 90), "?"), "news": ((236, 236, 236), "!")}

    def draw_overlay(self, scr, cx, cy, t, font, near):
        X, Y = int(self.x - cx), int(self.y - cy)
        top = Y - self.h + 4
        y = top - 8
        mark = self.MARK.get(self.alert)
        if mark:
            col, ch = mark
            bob = int(math.sin(t * 5) * 3)
            r = 10 if self.alert != "news" else 8
            pygame.draw.circle(scr, (20, 16, 10), (X, top - 14 + bob), r + 2)
            pygame.draw.circle(scr, col, (X, top - 14 + bob), r)
            g = font.render(ch, True, (40, 26, 10))
            scr.blit(g, (X - g.get_width() // 2, top - 14 + bob - g.get_height() // 2 + 1))
            y = top - 30
        if near:
            img = font.render(self.name, True, (232, 244, 220))
            sh = font.render(self.name, True, (0, 0, 0))
            y -= img.get_height()
            scr.blit(sh, (X - img.get_width() // 2 + 1, y + 1))
            scr.blit(img, (X - img.get_width() // 2, y))
        elif self.bark_t > 0 and self.bark:
            a = min(1.0, self.bark_t / 0.4, (3.2 - self.bark_t) / 0.2)
            img = font.render(self.bark, True, (40, 34, 30))
            w, h = img.get_width() + 16, img.get_height() + 8
            bub = pygame.Surface((w, h + 7), pygame.SRCALPHA)
            pygame.draw.rect(bub, (250, 246, 232), (0, 0, w, h), border_radius=8)
            pygame.draw.rect(bub, (60, 50, 44), (0, 0, w, h), 2, border_radius=8)
            pygame.draw.polygon(bub, (250, 246, 232), [(w // 2 - 5, h - 2), (w // 2 + 5, h - 2), (w // 2, h + 6)])
            pygame.draw.lines(bub, (60, 50, 44), False, [(w // 2 - 5, h - 1), (w // 2, h + 6), (w // 2 + 5, h - 1)], 2)
            bub.blit(img, (8, 4))
            bub.set_alpha(int(255 * max(0.0, a)))
            scr.blit(bub, (X - w // 2, y - h - 7))


class Companion(NPC):
    """Merlin the Great Sage. He stays in Oakwood by his ward and doesn't follow Himmel.
    During a night raid he stands in the middle of the plaza and holds the ward."""
    HOME = (1500, 1610)
    WARD = (1400, 1612)

    def __init__(self, x, y, rng=None):
        super().__init__("merlin", "Merlin the Great Sage", x, y, radius=26, rng=rng, look="merlin")

    def say(self, text, t=3.6):
        self.bark, self.bark_t = text, t

    def update(self, dt, world):
        night = getattr(world, "night", None)
        if night is not None and night.active:               # hold the ward
            tx, ty = self.WARD
            d = math.hypot(tx - self.x, ty - self.y)
            self.moving = d > 4
            if self.moving:
                k = min(1.0, 140 * dt / d)
                self.x += (tx - self.x) * k
                self.y += (ty - self.y) * k
                self.walk += dt
            self.facing = "down"
            self.target = None
            self.bark_t = max(0.0, self.bark_t - dt)
            self.sort_y = self.y
            self.rect.topleft = (int(self.x) - 20, int(self.y) - 50)
            return
        if math.hypot(self.x - self.HOME[0], self.y - self.HOME[1]) > 60 and self.target is None:
            self.target = self.HOME                            # walk back after a raid
        super().update(dt, world)

    def draw(self, scr, cx, cy, t):
        super().draw(scr, cx, cy, t)
        X, Y = int(self.x - cx), int(self.y - cy)
        ox = X + (10 if not (self.facing == "side" and self.flip) else -10)
        if self.facing == "up":
            ox = X + 12
        k = 0.6 + 0.4 * math.sin(t * 3)
        pygame.draw.circle(scr, (int(150 * k), int(220 * k), 255), (ox, Y - self.h + 6), 3)

    def lights(self, t):
        return [(int(self.x) + 10, int(self.y) - self.h + 6, 70, (60, 110, 170))]


# --------------------------------------------------------------------------- #
#  critters
# --------------------------------------------------------------------------- #
def _px(rows, palette, scale):
    """Tiny pixel sprite from strings; '.' = transparent."""
    h, w = len(rows), len(rows[0])
    s = pygame.Surface((w, h), pygame.SRCALPHA)
    for y, row in enumerate(rows):
        for x, ch in enumerate(row):
            if ch != ".":
                s.set_at((x, y), palette[ch])
    return pygame.transform.scale(s, (w * scale, h * scale))


_CHICKEN_PAL = {"w": (240, 236, 226), "s": (196, 190, 180), "r": (220, 50, 50), "y": (240, 180, 60), "k": (30, 24, 24)}
CHICKEN = [
    _px(["..r...", ".rww..", "ykww..", ".wwwws", ".swwws", "..y.y."], _CHICKEN_PAL, 3),
    _px(["......", "..r...", ".rww..", "ykwwws", ".swwws", "..y.y."], _CHICKEN_PAL, 3),   # pecking
]
_SHEEP_PAL = {"w": (236, 234, 226), "s": (200, 198, 190), "k": (54, 46, 46), "e": (250, 250, 250)}
SHEEP = [
    _px([".swwwwws..", "swwwwwwwkk", "wwwwwwwwke", "swwwwwwskk", ".swwwwws..", "..k..k...."], _SHEEP_PAL, 3),
    _px([".swwwwws..", "swwwwwwwkk", "wwwwwwwwke", "swwwwwwskk", ".swwwwws..", "...k..k..."], _SHEEP_PAL, 3),
]
_DEER_PAL = {"b": (150, 98, 58), "d": (112, 70, 40), "w": (236, 226, 210), "k": (30, 22, 18), "a": (190, 170, 130)}
DEER = [
    _px(["..........a.a", "..........aa.", "w.........bk.", "wbbbbbbbbbb..", ".bbbbbbbbb...", ".d.d....d.d..", ".d.d....d.d.."], _DEER_PAL, 3),
    _px(["..........a.a", "..........aa.", "w.........bk.", "wbbbbbbbbbb..", ".bbbbbbbbb...", "d...d..d...d.", "d...d..d...d."], _DEER_PAL, 3),
]
_CROW_PAL = {"k": (30, 30, 40), "g": (60, 60, 76), "y": (220, 170, 60)}
CROW_SIT = _px([".kk..", "ykkk.", ".kkgk", "..k.k"], _CROW_PAL, 3)
CROW_FLY = [
    _px(["k...k", "gk.kg", ".kkk.", "..y.."], _CROW_PAL, 3),
    _px([".....", "kkkkk", "gkkkg", "..y.."], _CROW_PAL, 3),
]


class Critter:
    sort_y = 0

    def __init__(self, x, y, radius, rng):
        self.x, self.y = float(x), float(y)
        self.home = (x, y)
        self.radius = radius
        self.rng = rng
        self.flip = rng.random() < 0.5
        self.target = None
        self.wait = rng.uniform(0, 3)
        self.anim = rng.random() * 5
        self.moving = False
        self.sort_y = y
        self.rect = pygame.Rect(int(x) - 24, int(y) - 30, 48, 34)

    def wander(self, dt, world, speed):
        if self.target is None:
            self.wait -= dt
            if self.wait <= 0:
                a = self.rng.random() * math.tau
                r = self.rng.random() * self.radius
                self.target = (self.home[0] + math.cos(a) * r, self.home[1] + math.sin(a) * r * 0.6)
            return False
        if not _step_toward(self, self.target[0], self.target[1], speed, dt, world):
            self.target = None
            self.wait = self.rng.uniform(1.0, 4.0)
            return False
        return True

    def _sync(self):
        self.sort_y = self.y
        self.rect.topleft = (int(self.x) - 24, int(self.y) - 30)


class Chicken(Critter):
    def update(self, dt, world):
        self.anim += dt
        p = world.player
        if math.hypot(p.x - self.x, p.y - self.y) < 60:          # scurry away
            a = math.atan2(self.y - p.y, self.x - p.x)
            self.target = (self.x + math.cos(a) * 50, self.y + math.sin(a) * 50)
            _step_toward(self, *self.target, 120, dt, world)
            self.moving = True
        else:
            self.moving = self.wander(dt, world, 34)
        self._sync()

    def draw(self, scr, cx, cy, t):
        peck = not getattr(self, "moving", False) and int(self.anim * 2.5 + self.home[0]) % 5 == 0
        img = CHICKEN[1 if peck else 0]
        if not self.flip:
            img = pygame.transform.flip(img, True, False)
        X, Y = int(self.x - cx), int(self.y - cy)
        pygame.draw.ellipse(scr, (16, 24, 16), (X - 8, Y - 3, 16, 6))
        hop = -2 if getattr(self, "moving", False) and int(self.anim * 10) % 2 else 0
        scr.blit(img, (X - 9, Y - 17 + hop))


class Sheep(Critter):
    def update(self, dt, world):
        self.anim += dt
        self.moving = self.wander(dt, world, 18)
        self._sync()

    def draw(self, scr, cx, cy, t):
        img = SHEEP[int(self.anim * 4) % 2 if self.moving else 0]
        if self.flip:
            img = pygame.transform.flip(img, True, False)
        X, Y = int(self.x - cx), int(self.y - cy)
        pygame.draw.ellipse(scr, (16, 24, 16), (X - 15, Y - 4, 30, 8))
        scr.blit(img, (X - 15, Y - 17))


class Deer(Critter):
    def __init__(self, x, y, radius, rng):
        super().__init__(x, y, radius, rng)
        self.flee = 0.0
        self.alpha = 255

    def update(self, dt, world):
        self.anim += dt
        p = world.player
        d = math.hypot(p.x - self.x, p.y - self.y)
        if d < 170 and self.flee <= 0:
            self.flee = 2.2
            self.flee_dir = math.atan2(self.y - p.y, self.x - p.x)
        if self.flee > 0:
            self.flee -= dt
            a = self.flee_dir
            self.flip = math.cos(a) < 0
            _step_toward(self, self.x + math.cos(a) * 80, self.y + math.sin(a) * 80, 210, dt, world, solid=False)
            self.moving = True
            if self.flee <= 0:          # slip back to the home clearing out of sight
                if d > 420:
                    self.x, self.y = self.home
        else:
            self.moving = self.wander(dt, world, 22)
        self._sync()

    def draw(self, scr, cx, cy, t):
        img = DEER[int(self.anim * (10 if self.flee > 0 else 4)) % 2 if self.moving else 0]
        if not self.flip:
            img = pygame.transform.flip(img, True, False)
        X, Y = int(self.x - cx), int(self.y - cy)
        pygame.draw.ellipse(scr, (14, 22, 14), (X - 16, Y - 4, 32, 8))
        scr.blit(img, (X - 19, Y - 20))


class Crow(Critter):
    def __init__(self, x, y, radius, rng):
        super().__init__(x, y, radius, rng)
        self.state = "sit"
        self.vx = self.vy = 0.0
        self.alt = 0.0
        self.away = 0.0

    def update(self, dt, world):
        self.anim += dt
        p = world.player
        if self.state == "sit":
            if math.hypot(p.x - self.x, p.y - self.y) < 130:
                self.state = "fly"
                side = 1 if self.x >= p.x else -1
                self.vx = side * self.rng.uniform(120, 190)
                self.vy = self.rng.uniform(-60, -20)
                self.flip = side < 0
            elif self.rng.random() < dt * 0.4:
                self.flip = not self.flip
        elif self.state == "fly":
            self.x += self.vx * dt
            self.y += self.vy * dt
            self.alt += 90 * dt
            if self.alt > 420:
                self.state, self.away = "gone", self.rng.uniform(15, 30)
        else:
            self.away -= dt
            if self.away <= 0 and math.hypot(p.x - self.home[0], p.y - self.home[1]) > 400:
                self.x, self.y = self.home
                self.alt = 0.0
                self.state = "sit"
        self._sync()

    def draw(self, scr, cx, cy, t):
        if self.state == "gone":
            return
        X, Y = int(self.x - cx), int(self.y - cy)
        if self.state == "sit":
            img = CROW_SIT if not self.flip else pygame.transform.flip(CROW_SIT, True, False)
            pygame.draw.ellipse(scr, (16, 24, 16), (X - 6, Y - 2, 12, 5))
            scr.blit(img, (X - 7, Y - 12))
        else:
            img = CROW_FLY[int(self.anim * 12) % 2]
            sh = max(2, 8 - int(self.alt / 60))
            pygame.draw.ellipse(scr, (16, 24, 16), (X - sh, Y - 2, sh * 2, 4))
            scr.blit(img, (X - 7, Y - 12 - int(self.alt)))


class Butterfly(Critter):
    COLORS = ((250, 220, 90), (240, 130, 190), (160, 200, 255), (255, 255, 255))

    def __init__(self, x, y, radius, rng):
        super().__init__(x, y, radius, rng)
        self.col = rng.choice(self.COLORS)
        self.ph = rng.random() * 10

    def update(self, dt, world):
        self.anim += dt
        a = self.anim * 0.7 + self.ph
        self.x = self.home[0] + math.sin(a) * self.radius + math.sin(a * 2.3) * 14
        self.y = self.home[1] + math.cos(a * 0.8) * self.radius * 0.5
        self._sync()

    def draw(self, scr, cx, cy, t):
        if not getattr(self, "visible", True):
            return
        X, Y = int(self.x - cx), int(self.y - cy - 26 - math.sin(self.anim * 3) * 6)
        w = 3 if int(self.anim * 14) % 2 else 1
        pygame.draw.rect(scr, self.col, (X - w - 1, Y - 2, w, 3))
        pygame.draw.rect(scr, self.col, (X + 1, Y - 2, w, 3))
        scr.fill((40, 30, 30), (X, Y - 2, 1, 3))


# --------------------------------------------------------------------------- #
#  chimney smoke
# --------------------------------------------------------------------------- #
_PUFFS = None


def _puffs():
    global _PUFFS
    if _PUFFS is None:
        _PUFFS = []
        for r in range(3, 17):
            s = pygame.Surface((r * 2, r * 2), pygame.SRCALPHA)
            pygame.draw.circle(s, (170, 170, 176, 90), (r, r), r)
            pygame.draw.circle(s, (200, 200, 206, 70), (r - r // 3, r - r // 3), max(1, r // 2))
            _PUFFS.append(s)
    return _PUFFS


class SmokePlume:
    def __init__(self, x, y, rng):
        self.x, self.y = x, y
        self.rng = rng
        self.parts = []
        self.acc = rng.random()
        # pre-warm
        for _ in range(60):
            self.update(0.1)

    def update(self, dt):
        self.acc += dt
        while self.acc > 0.28:
            self.acc -= 0.28
            self.parts.append([self.x + self.rng.uniform(-2, 2), self.y, self.rng.uniform(6, 16),
                               self.rng.uniform(-22, -14), 0.0])
        for p in self.parts:
            p[0] += p[2] * 0.5 * (0.4 + p[4] / 3) * dt
            p[1] += p[3] * dt
            p[4] += dt
        self.parts = [p for p in self.parts if p[4] < 4.0]

    def draw(self, scr, cx, cy):
        puffs = _puffs()
        for x, y, vx, vy, age in self.parts:
            k = age / 4.0
            img = puffs[min(len(puffs) - 1, int(k * (len(puffs) - 1)))]
            img.set_alpha(int(255 * (1 - k) * min(1, age * 3)))
            r = img.get_width() // 2
            scr.blit(img, (int(x - cx) - r, int(y - cy) - r))


# --------------------------------------------------------------------------- #
#  day / night
# --------------------------------------------------------------------------- #
class DayNight:
    PERIOD = 360.0
    KEYS = [
        (0.00, (206, 182, 176)),   # dawn
        (0.10, (232, 230, 220)),   # day
        (0.52, (232, 230, 220)),
        (0.62, (214, 160, 136)),   # dusk
        (0.72, (104, 112, 156)),   # night
        (0.92, (104, 112, 156)),
        (1.00, (206, 182, 176)),
    ]

    def __init__(self, start=0.18):
        self.t = start * self.PERIOD

    def update(self, dt):
        self.t = (self.t + dt) % self.PERIOD

    @property
    def phase(self):
        return self.t / self.PERIOD

    def ambient(self):
        p = self.phase
        for (a, ca), (b, cb) in zip(self.KEYS, self.KEYS[1:]):
            if a <= p <= b:
                return _mix(ca, cb, (p - a) / (b - a))
        return self.KEYS[0][1]

    def night(self):
        """0 in full day, 1 at full night."""
        amb = self.ambient()
        return max(0.0, min(1.0, (232 - sum(amb) / 3) / 112))

    def label(self):
        p = self.phase
        if p < 0.08 or p > 0.94:
            return "Dawn"
        if p < 0.56:
            return "Day"
        if p < 0.68:
            return "Dusk"
        return "Night"


# --------------------------------------------------------------------------- #
#  hidden treasure
# --------------------------------------------------------------------------- #
def _make_chest(opened):
    s = pygame.Surface((30, 28), pygame.SRCALPHA)
    pygame.draw.ellipse(s, (0, 0, 0, 80), (0, 20, 30, 8))
    pygame.draw.rect(s, (110, 70, 36), (3, 11, 24, 13))
    pygame.draw.rect(s, (70, 44, 22), (3, 11, 24, 13), 2)
    if opened:
        pygame.draw.rect(s, (60, 36, 18), (3, 4, 24, 8))
        pygame.draw.rect(s, (230, 190, 70), (6, 11, 18, 3))
    else:
        pygame.draw.rect(s, (136, 88, 46), (3, 5, 24, 8), border_top_left_radius=5, border_top_right_radius=5)
        pygame.draw.rect(s, (70, 44, 22), (3, 5, 24, 8), 2, border_top_left_radius=5, border_top_right_radius=5)
    for x in (8, 21):
        pygame.draw.rect(s, (214, 170, 70), (x, 5 if not opened else 11, 3, 19 if not opened else 13))
    pygame.draw.rect(s, (240, 210, 110), (13, 12, 4, 5))
    return s


class Treasure:
    IMG = None

    def __init__(self, idx, x, y, gold):
        if Treasure.IMG is None:
            Treasure.IMG = (_make_chest(False), _make_chest(True))
        self.flag = "treasure_%d" % idx
        self.x, self.y = x, y
        self.gold = gold
        self.opened_cache = False   # refreshed by the world every frame from the save flags
        self.sort_y = y
        self.rect = pygame.Rect(x - 16, y - 26, 32, 30)

    def opened(self, world):
        return world.has_flag(self.flag)

    def draw(self, scr, cx, cy, t):
        img = Treasure.IMG[1 if self.opened_cache else 0]
        X, Y = int(self.x - cx), int(self.y - cy)
        scr.blit(img, (X - 15, Y - 24))
        if not self.opened_cache:
            for i in range(3):
                a = t * 2 + i * 2.1
                k = 0.5 + 0.5 * math.sin(t * 4 + i * 1.7)
                sx, sy = X + int(math.cos(a) * 16), Y - 14 + int(math.sin(a * 1.3) * 10)
                c = (int(255 * k), int(230 * k), int(120 * k))
                scr.fill(c, (sx - 1, sy, 3, 1))
                scr.fill(c, (sx, sy - 1, 1, 3))

    def lights(self, t):
        if self.opened_cache:
            return []
        return [(self.x, self.y - 12, 60, (120, 100, 40))]


# --------------------------------------------------------------------------- #
#  story-progress scenery
# --------------------------------------------------------------------------- #
def make_trophy_banner():
    s = pygame.Surface((44, 96), pygame.SRCALPHA)
    pygame.draw.ellipse(s, (0, 0, 0, 80), (6, 86, 32, 10))
    pygame.draw.rect(s, (90, 62, 36), (20, 8, 4, 84))
    pygame.draw.circle(s, (230, 190, 80), (22, 7), 4)
    pygame.draw.polygon(s, (40, 120, 60), [(24, 12), (44, 12), (44, 52), (34, 44), (24, 52)])
    pygame.draw.polygon(s, (20, 70, 36), [(24, 12), (44, 12), (44, 52), (34, 44), (24, 52)], 1)
    # crooked goblin crown on the banner
    pygame.draw.polygon(s, (230, 190, 80), [(28, 34), (28, 24), (31, 28), (34, 22), (37, 28), (40, 24), (40, 34)])
    return s


def make_tent(col):
    s = pygame.Surface((76, 60), pygame.SRCALPHA)
    pygame.draw.ellipse(s, (0, 0, 0, 80), (2, 48, 72, 12))
    pygame.draw.polygon(s, _shade(col, 0.7), [(4, 52), (38, 6), (72, 52)])
    pygame.draw.polygon(s, col, [(10, 52), (38, 8), (38, 52)])
    pygame.draw.polygon(s, (40, 30, 24), [(30, 52), (38, 30), (46, 52)])
    pygame.draw.line(s, (90, 64, 40), (38, 2), (38, 10), 3)
    return s


def make_campfire():
    s = pygame.Surface((34, 22), pygame.SRCALPHA)
    pygame.draw.ellipse(s, (0, 0, 0, 80), (0, 12, 34, 10))
    for i in range(7):
        a = i * math.tau / 7
        pygame.draw.circle(s, (110, 110, 118), (17 + int(math.cos(a) * 12), 15 + int(math.sin(a) * 5)), 3)
    pygame.draw.line(s, (90, 56, 30), (9, 16), (25, 12), 4)
    pygame.draw.line(s, (110, 70, 36), (9, 12), (25, 17), 4)
    return s


class Dressing:
    """A prop that only exists from story stage `min_stage` (until `max_stage`)."""

    def __init__(self, img, x, gy, min_stage, max_stage=9, col=None, foot=0, fire=False):
        self.img = img
        w, h = img.get_size()
        self.rect = pygame.Rect(int(x - w // 2), int(gy + foot - h), w, h)
        self.sort_y = gy
        self.min_stage, self.max_stage = min_stage, max_stage
        self.col = pygame.Rect(col) if col else None
        self.fire = fire
        self.x, self.y = x, gy

    def visible(self, stage):
        return self.min_stage <= stage <= self.max_stage

    def draw(self, scr, cx, cy, t):
        scr.blit(self.img, (self.rect.x - cx, self.rect.y - cy))
        if self.fire:
            fx, fy = int(self.x - cx), int(self.y - cy - 6)
            f = 0.8 + 0.2 * math.sin(t * 11) + 0.1 * math.sin(t * 27)
            h = int(14 * f) + 6
            pygame.draw.ellipse(scr, (255, 120, 30), (fx - 7, fy - h, 14, h + 4))
            pygame.draw.ellipse(scr, (255, 220, 100), (fx - 4, fy - h + 6, 8, h - 4))

    def lights(self, t):
        if self.fire:
            r = 170 + int(12 * math.sin(t * 9))
            return [(self.x, self.y - 10, r // 10 * 10, (220, 130, 50))]
        return []


def draw_bunting(scr, a, b, cx, cy, t, sag=26):
    """String of little flags between two world points (celebration)."""
    cols = ((220, 70, 70), (240, 200, 70), (80, 170, 90), (80, 130, 220))
    n = 14
    pts = []
    for i in range(n + 1):
        f = i / n
        x = a[0] + (b[0] - a[0]) * f
        y = a[1] + (b[1] - a[1]) * f + math.sin(f * math.pi) * sag + math.sin(t * 2 + f * 6) * 1.5
        pts.append((x - cx, y - cy))
    pygame.draw.lines(scr, (60, 50, 40), False, pts, 1)
    for i in range(n):
        x, y = pts[i]
        x2, y2 = pts[i + 1]
        mx = (x + x2) / 2
        pygame.draw.polygon(scr, cols[i % 4], [(x + 1, y), (x2 - 1, y2), (mx, (y + y2) / 2 + 9)])


class NorthFog:
    """Purple mist from the Lich King's land that creeps south over time."""

    def __init__(self, rng, world_w):
        self.blobs = []
        for i in range(16):
            w, h = rng.randint(420, 680), rng.randint(160, 260)
            s = pygame.Surface((w, h), pygame.SRCALPHA)
            for k in range(18, 0, -1):
                f = k / 18
                pygame.draw.ellipse(s, (120, 70, 170, int(9 * (1 - f) + 2)),
                                    (w * (1 - f) / 2, h * (1 - f) / 2, w * f, h * f))
            self.blobs.append([s, rng.uniform(-300, world_w), rng.uniform(0, 1), rng.uniform(8, 20)])

    LIMIT = {0: 760, 1: 900, 2: 1100}

    def draw(self, scr, cx, cy, t, stage, world_w, sw, sh):
        limit = self.LIMIT.get(stage)
        if limit is None:
            return
        for s, x0, fy, spd in self.blobs:
            w, h = s.get_size()
            x = (x0 + t * spd) % (world_w + w) - w
            y = 40 + fy * (limit - 120)
            sx, sy = int(x - cx), int(y - cy)
            if sx < sw and sx + w > 0 and sy < sh and sy + h > 0:
                scr.blit(s, (sx, sy))


# --------------------------------------------------------------------------- #
#  stalls
# --------------------------------------------------------------------------- #
def make_forge_stall():
    s = pygame.Surface((110, 86), pygame.SRCALPHA)
    pygame.draw.ellipse(s, (0, 0, 0, 80), (4, 70, 102, 16))
    # awning posts + roof
    for x in (8, 98):
        pygame.draw.rect(s, (86, 58, 34), (x, 22, 5, 56))
    pygame.draw.polygon(s, (90, 60, 40), [(0, 26), (110, 26), (100, 8), (10, 8)])
    for i in range(0, 110, 14):
        pygame.draw.line(s, (70, 46, 30), (i, 26), (i + 6, 8), 2)
    # forge: stone box with glowing coals
    pygame.draw.rect(s, (96, 92, 96), (16, 44, 36, 32))
    pygame.draw.rect(s, (70, 66, 72), (16, 44, 36, 32), 2)
    pygame.draw.rect(s, (40, 24, 20), (22, 50, 24, 10))
    pygame.draw.rect(s, (255, 130, 40), (24, 54, 20, 5))
    pygame.draw.rect(s, (255, 220, 120), (28, 55, 10, 2))
    # anvil
    pygame.draw.rect(s, (58, 58, 66), (66, 66, 12, 10))
    pygame.draw.polygon(s, (84, 86, 96), [(58, 58), (92, 58), (88, 66), (62, 66)])
    pygame.draw.line(s, (140, 144, 156), (60, 58), (90, 58), 2)
    # hanging tools / swords
    for i, x in enumerate((30, 44, 58, 72, 86)):
        pygame.draw.line(s, (170, 176, 190), (x, 28), (x, 40 + (i % 2) * 4), 2)
        pygame.draw.line(s, (120, 80, 40), (x - 3, 28), (x + 3, 28), 2)
    return s


def make_herb_stall():
    s = pygame.Surface((110, 86), pygame.SRCALPHA)
    pygame.draw.ellipse(s, (0, 0, 0, 80), (4, 70, 102, 16))
    for x in (8, 98):
        pygame.draw.rect(s, (86, 58, 34), (x, 22, 5, 56))
    # striped awning
    for i in range(8):
        col = (60, 130, 80) if i % 2 == 0 else (230, 222, 196)
        pygame.draw.polygon(s, col, [(i * 14, 26), (i * 14 + 14, 26), (i * 14 + 13, 8), (i * 14 + 1, 8)])
    for i in range(8):
        pygame.draw.circle(s, (60, 130, 80) if i % 2 == 0 else (230, 222, 196), (i * 14 + 7, 27), 7, draw_top_right=False,
                           draw_top_left=False)
    # counter
    pygame.draw.rect(s, (120, 82, 48), (12, 56, 88, 20))
    pygame.draw.rect(s, (90, 60, 34), (12, 56, 88, 4))
    # bottles + herb bundles
    for i, (x, c) in enumerate(((22, (220, 60, 70)), (34, (220, 60, 70)), (48, (90, 160, 230)),
                                (62, (140, 220, 120)), (76, (220, 60, 70)), (88, (240, 200, 80)))):
        pygame.draw.rect(s, c, (x, 46, 7, 10), border_radius=2)
        pygame.draw.rect(s, (230, 230, 240), (x + 2, 42, 3, 4))
    for x in (26, 50, 74):
        pygame.draw.line(s, (80, 140, 60), (x, 28), (x, 38), 3)
        pygame.draw.circle(s, (100, 170, 70), (x, 39), 4)
    return s


# --------------------------------------------------------------------------- #
#  populate the world
# --------------------------------------------------------------------------- #
TREASURE_SPOTS = [(430, 760, 40), (2480, 560, 55), (2470, 1560, 45), (420, 1620, 35), (1010, 430, 60)]
MEADOW = (1740, 1250)
CAMP = (990, 1470)


def reserve(big_circles):
    """Clearings that must stay free of trees (call before trees are placed)."""
    for x, y, _g in TREASURE_SPOTS:
        big_circles.append((x, y, 48))
    big_circles.append((MEADOW[0], MEADOW[1], 150))
    big_circles.append((CAMP[0], CAMP[1], 120))


def populate(world, add_prop, rng, make_fence):
    """Add stalls, fences, NPCs, critters, smoke, treasure and dressing to the world."""
    # ---- shop stalls
    add_prop(make_forge_stall(), 1200, 1630, foot=6, col=(1150, 1612, 100, 18),
             lights=[(1175, 1640, 110, (180, 90, 30))], radius=50)
    add_prop(make_herb_stall(), 1600, 1630, foot=6, col=(1550, 1612, 100, 18), radius=50)
    # ---- sheep meadow fences
    for fy in (MEADOW[1] - 80, MEADOW[1] + 80):
        f = make_fence(200)
        add_prop(f, MEADOW[0], fy, foot=2, col=(MEADOW[0] - 100, fy - 8, 200, 8), radius=60)._kind = "fence"

    # ---- villagers
    world.npcs = [
        NPC("maren", "Elder Maren", 1345, 1702, radius=24, rng=rng),
        NPC("torvin", "Torvin the Blacksmith", 1205, 1662, radius=18, shop="torvin", rng=rng),
        NPC("wren", "Wren the Herbalist", 1598, 1662, radius=18, shop="wren", rng=rng),
        NPC("pip", "Pip", 1400, 1585, radius=110, rng=rng),
        NPC("hale", "Captain Hale", 1452, 1345, radius=0, rng=rng),
        NPC("bram", "Old Bram", 1290, 1880, radius=60, rng=rng),
        NPC("lisbet", "Lisbet", 1520, 1515, radius=50, rng=rng),
    ]
    world.merlin = Companion(*Companion.HOME, rng=rng)
    world.refugees = [NPC("refugee", "Farmstead Folk", CAMP[0] + dx, CAMP[1] + dy, radius=30, rng=rng, look=lk)
                      for (dx, dy), lk in (((-50, 40), "refugee"), ((60, 50), "baker"))]

    # ---- critters
    cr = []
    for home, n in (((1050, 1630), 4), ((1770, 1640), 3)):
        for _ in range(n):
            cr.append(Chicken(home[0] + rng.randint(-30, 30), home[1] + rng.randint(-15, 15), 55, rng))
    for _ in range(5):
        cr.append(Sheep(MEADOW[0] + rng.randint(-70, 70), MEADOW[1] + rng.randint(-40, 40), 70, rng))
    for x, y in ((620, 1360), (2300, 1480), (2200, 720), (700, 520)):
        cr.append(Deer(x, y, 40, rng))
    for x, y in ((1250, 1350), (1610, 1880), (1000, 1560), (1880, 1180)):
        for _ in range(3):
            cr.append(Crow(x + rng.randint(-26, 26), y + rng.randint(-14, 14), 0, rng))
    world.butterflies = [Butterfly(1400 + rng.randint(-300, 300), 1640 + rng.randint(-250, 220), 30, rng)
                         for _ in range(12)]
    world.critters = cr

    # ---- treasure
    world.treasures = [Treasure(i, x, y, g) for i, (x, y, g) in enumerate(TREASURE_SPOTS)]
    for tr in world.treasures:
        world.colliders.append(pygame.Rect(tr.x - 12, tr.y - 8, 24, 8))

    # ---- story dressing
    green_tent, grey_tent = make_tent((150, 120, 90)), make_tent((120, 120, 110))
    world.dressing = [
        Dressing(make_trophy_banner(), 1345, 1538, 1, foot=4, col=(1340, 1532, 10, 8)),
        Dressing(green_tent, CAMP[0] - 50, CAMP[1], 2, col=(CAMP[0] - 84, CAMP[1] - 14, 68, 14)),
        Dressing(grey_tent, CAMP[0] + 55, CAMP[1] - 10, 2, col=(CAMP[0] + 21, CAMP[1] - 24, 68, 14)),
        Dressing(make_campfire(), CAMP[0], CAMP[1] + 30, 2, col=(CAMP[0] - 12, CAMP[1] + 22, 24, 8), fire=True),
    ]
    world.bunting = [((1295, 1572), (1505, 1572)), ((1295, 1702), (1505, 1702))]
    world.fog = NorthFog(rng, 2800)
