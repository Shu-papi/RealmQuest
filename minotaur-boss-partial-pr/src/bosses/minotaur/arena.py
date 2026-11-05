"""
minotaur/arena.py - A playable arena for the Minotaur fight: the Labyrinth's heart.

    python src/bosses/minotaur/arena.py                play it (flat arena, isometric-style boss)
    python src/bosses/minotaur/arena.py --iso-room     the optional isometric ROOM (floor turned into a diamond)
    python src/bosses/minotaur/arena.py --bot          watch a simple bot fight him
    python src/bosses/minotaur/arena.py --mute         start with the sound off
    python src/bosses/minotaur/arena.py --shot out.png [--seconds 14]
                                                       headless: run the bot, save a screenshot

Controls
    WASD / arrows   move                 mouse          aim
    left click / J / SPACE   sword       right click / K / SHIFT   dodge roll (you can't be hurt mid-roll)
    P pause   R restart   M sound on/off   ESC quit
    1  jump to phase 2   2  heal   3  kill him            (testing keys)

The arena is a 960 x 640 window with the same play area the boss tests use (40, 110, 920, 600),
so every attack (charge lane, slam circle, rocks) behaves exactly like it does in the real game.
Everything is drawn on a 4 x 4 pixel grid, like the sprites.

This file only needs the public Boss surface: update(dt, player, bounds), draw(surface),
is_alive(), is_defeated(), take_damage(), drop_loot(), and (if present) hittables() and
draw_health_bar(surface, font). Nothing else in the game imports it.
"""
import math
import os
import random
import sys
from dataclasses import dataclass

SRC_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)

os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")
import pygame  # noqa: E402

from bosses import Minotaur  # noqa: E402
from bosses.minotaur.iso_art import IsoArenaArt  # noqa: E402
from bosses.minotaur.view import IsoView, TopDownView  # noqa: E402

WINDOW = (960, 640)
BOUNDS = (40, 110, 920, 600)          # left, top, right, bottom of the floor
PX = 4                                # one art pixel = 4 x 4 screen pixels
LO_W, LO_H = WINDOW[0] // PX, WINDOW[1] // PX
FLOOR = (10, 28, 230, 150)            # the floor rectangle in art pixels (left, top, right, bottom)

TORCHES = [(144, 64), (336, 64), (624, 64), (816, 64),      # flame base positions, screen px
           (20, 244), (20, 484), (940, 244), (940, 484)]

# ---------------------------------------------------------------------------
# arena art
# ---------------------------------------------------------------------------


def _hash(x, y, salt=0):
    n = (x * 374761393 + y * 668265263 + salt * 2147483647) & 0xFFFFFFFF
    n = ((n ^ (n >> 13)) * 1274126177) & 0xFFFFFFFF
    return (n ^ (n >> 16)) & 0xFFFF


def _shade(colour, amount):
    return tuple(max(0, min(255, c + amount)) for c in colour)


HORNS_EMBLEM = [
    "X.............X",
    "XX...........XX",
    ".XX.........XX.",
    ".XXX.......XXX.",
    "..XXXXXXXXXXX..",
    "....XXXXXXX....",
    "....X.XXX.X....",
    ".....XXXXX.....",
    ".....X.X.X.....",
]


class ArenaArt:
    """Builds the stone chamber once; torches and light are drawn on top every frame."""

    def __init__(self):
        self.background = self._build_background()
        self.vignette = self._build_vignette()
        self.glows = [self._build_glow(i) for i in (0.55, 0.75, 1.0)]

    # -- floor, walls, gate ---------------------------------------------------
    def _build_background(self):
        lo = pygame.Surface((LO_W, LO_H))
        fl, ft, fr, fb = FLOOR
        rng = random.Random(11)
        tone = [(41, 36, 58), (37, 32, 53), (44, 39, 62), (35, 30, 50)]
        joint, speck_lt, speck_dk = (22, 19, 33), (53, 47, 72), (28, 24, 41)
        moss = (44, 68, 54)
        for y in range(LO_H):
            for x in range(LO_W):
                if fl <= x < fr and ft <= y < fb:
                    tx, ty = (x - fl) // 10, (y - ft) // 10
                    lx, ly = (x - fl) % 10, (y - ft) % 10
                    colour = tone[_hash(tx, ty) % 4]
                    if lx == 0 or ly == 0:
                        colour = joint
                    elif lx == 1 or ly == 1:
                        colour = _shade(colour, 7)
                    else:
                        h = _hash(x, y, 3)
                        if h % 31 == 0:
                            colour = speck_lt
                        elif h % 43 == 1:
                            colour = speck_dk
                        elif h % 97 == 2 and _hash(tx, ty, 9) % 3 == 0:
                            colour = moss
                    lo.set_at((x, y), colour)
                else:
                    lo.set_at((x, y), self._brick(x, y))
        self._draw_cracks(lo, rng)
        self._draw_border(lo)
        self._draw_mosaic(lo)
        self._draw_gate(lo)
        for bx in (22, 218):
            self._draw_banner(lo, bx)
        for tx, ty in TORCHES:                                  # iron brackets
            x, y = tx // PX, ty // PX
            for dy in range(0, 5):
                lo.set_at((x, y + dy), (58, 52, 66))
                lo.set_at((x - 1, y + dy), (34, 30, 42))
            lo.set_at((x - 2, y + 1), (58, 52, 66))
            lo.set_at((x + 1, y + 1), (58, 52, 66))
        return pygame.transform.scale(lo, WINDOW)

    @staticmethod
    def _brick(x, y):
        row = y // 4
        xo = x + (row % 2) * 4
        if y % 4 == 0 or xo % 8 == 0:
            return (19, 16, 27)
        base = [(48, 42, 63), (54, 48, 70), (43, 37, 58), (50, 44, 66)][_hash(xo // 8, row) % 4]
        if y % 4 == 1:
            base = _shade(base, 9)
        if _hash(x, y, 5) % 37 == 0:
            base = _shade(base, -10)
        return base

    @staticmethod
    def _draw_cracks(lo, rng):
        fl, ft, fr, fb = FLOOR
        for _ in range(9):
            x, y = rng.randint(fl + 6, fr - 6), rng.randint(ft + 6, fb - 6)
            angle = rng.uniform(0, math.tau)
            for _ in range(rng.randint(10, 20)):
                if fl + 2 <= x < fr - 2 and ft + 2 <= y < fb - 2:
                    lo.set_at((int(x), int(y)), (20, 17, 30))
                angle += rng.uniform(-0.6, 0.6)
                x += math.cos(angle)
                y += math.sin(angle)

    @staticmethod
    def _draw_border(lo):
        fl, ft, fr, fb = FLOOR
        dark, light = (30, 26, 43), (58, 51, 78)
        for x in range(fl, fr):
            for k in range(2):
                for y in (ft + k, fb - 1 - k):
                    lo.set_at((x, y), light if (x % 4 == 0 and k == 0) else dark)
        for y in range(ft, fb):
            for k in range(2):
                for x in (fl + k, fr - 1 - k):
                    lo.set_at((x, y), light if (y % 4 == 0 and k == 0) else dark)

    @staticmethod
    def _draw_mosaic(lo):
        """A classical labyrinth: concentric rings, each with a gap."""
        cx, cy = 120, 89
        ring, ring_hi = (62, 55, 80), (82, 74, 102)
        for i, radius in enumerate((38, 31, 25, 19, 13, 7)):
            gap_centre = i * 1.9
            for step in range(int(radius * 14)):
                angle = step / (radius * 14) * math.tau
                diff = abs((angle - gap_centre + math.pi) % math.tau - math.pi)
                if diff < 0.42 and i > 0:
                    continue
                x, y = int(round(cx + math.cos(angle) * radius)), int(round(cy + math.sin(angle) * radius * 0.92))
                lo.set_at((x, y), ring_hi if (i == 0 or angle < math.pi * 0.9) else ring)
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                lo.set_at((cx + dx, cy + dy), (120, 100, 70) if dx == dy == 0 else (84, 70, 56))

    @staticmethod
    def _draw_gate(lo):
        cx, base, radius = 120, 25, 14
        stone, stone_hi = (88, 80, 108), (112, 104, 134)
        for y in range(0, 28):
            for x in range(cx - 17, cx + 18):
                dx = x - cx
                dist = abs(dx) if y >= base else math.hypot(dx, y - base)
                if dist <= radius:
                    depth = min(1.0, (radius - dist) / radius)
                    lo.set_at((x, y), (int(8 + 6 * (1 - depth)), int(6 + 5 * (1 - depth)), int(14 + 8 * (1 - depth))))
                elif dist <= radius + 3:
                    seg = int((math.atan2(y - base, dx) + math.pi) / (math.pi / 9)) if y < base else 99 + y // 4
                    lo.set_at((x, y), stone_hi if seg % 2 == 0 else stone)
                    if dist > radius + 2.2:
                        lo.set_at((x, y), (30, 26, 42))
        for r, row in enumerate(HORNS_EMBLEM):                      # horned-skull relief above the arch
            for c, ch in enumerate(row):
                if ch == "X":
                    lo.set_at((cx - 7 + c, 1 + r), (176, 160, 134) if r < 5 else (132, 120, 104))
        for y in range(base - 2, 28):                               # a few iron bars of the portcullis
            for x in range(cx - radius + 2, cx + radius - 1, 5):
                if y > 12:
                    lo.set_at((x, y), (40, 38, 50))

    @staticmethod
    def _draw_banner(lo, cx):
        cloth, dark, gold = (118, 34, 42), (74, 20, 30), (226, 188, 64)
        for y in range(3, 21):
            half = 4 if y < 17 else max(0, 4 - (y - 16))
            for x in range(cx - half, cx + half + 1):
                edge = abs(x - cx) == half
                lo.set_at((x, y), dark if edge else cloth)
        for x in range(cx - 4, cx + 5):
            lo.set_at((x, 3), gold)
        for y in range(8, 13):                                       # a gold bull-horn crescent
            lo.set_at((cx - 2 + (y - 8) // 2, y), gold)
            lo.set_at((cx + 2 - (y - 8) // 2, y), gold)

    # -- light ---------------------------------------------------------------------
    @staticmethod
    def _build_vignette():
        lo = pygame.Surface((120, 80), pygame.SRCALPHA)
        for y in range(80):
            for x in range(120):
                dx, dy = (x - 60) / 60.0, (y - 40) / 40.0
                r = math.hypot(dx, dy) / 1.25
                alpha = int(min(205, 235 * max(0.0, r - 0.38) ** 1.5))
                lo.set_at((x, y), (4, 3, 10, alpha))
        return pygame.transform.smoothscale(lo, WINDOW)

    @staticmethod
    def _build_glow(strength):
        size = 360
        glow = pygame.Surface((size, size))
        for y in range(0, size, 2):
            for x in range(0, size, 2):
                d = math.hypot(x - size / 2, y - size / 2) / (size / 2)
                k = max(0.0, 1.0 - d) ** 2 * strength
                colour = (int(88 * k), int(46 * k), int(14 * k))
                pygame.draw.rect(glow, colour, (x, y, 2, 2))
        return glow

    def draw_torches(self, surface, clock, torches=None):
        torches = TORCHES if torches is None else torches
        for i, (tx, ty) in enumerate(torches):
            flick = 0.5 + 0.5 * math.sin(clock * 9 + i * 1.7) * math.sin(clock * 5.3 + i)
            glow = self.glows[min(2, int(flick * 3))]
            surface.blit(glow, (tx - glow.get_width() // 2, ty - glow.get_height() // 2 - 12),
                         special_flags=pygame.BLEND_RGB_ADD)
        for i, (tx, ty) in enumerate(torches):
            t = clock * 9 + i * 1.7
            height = 3 + int(1.4 * math.sin(t) + 1.2 * math.sin(t * 1.9 + 1) + 1.4)
            sway = int(round(math.sin(t * 0.7))) * PX
            x0 = tx - 2 * PX + sway
            for colour, width, extra in (((214, 70, 34), 3, 0), ((255, 150, 60), 2, 1), ((255, 226, 150), 1, 2)):
                h = max(1, height - extra)
                pygame.draw.rect(surface, colour,
                                 (tx - width * PX // 2 + sway // 2, ty - h * PX, width * PX, h * PX))


_ART = None
_ISO_ART = {}


def get_iso_art(view):
    """The isometric room for this view (built once)."""
    key = (view.k, view.sx0, view.sy0)
    if key not in _ISO_ART:
        _ISO_ART[key] = IsoArenaArt(get_art(), view)
    return _ISO_ART[key]


def get_art():
    global _ART
    if _ART is None:
        _ART = ArenaArt()
    return _ART


# ---------------------------------------------------------------------------
# the player
# ---------------------------------------------------------------------------


@dataclass
class Inputs:
    move: tuple = (0.0, 0.0)
    aim: tuple = (480.0, 300.0)
    attack: bool = False
    roll: bool = False


class Player:
    RADIUS = 14
    SPEED = 230.0
    SWING_SLOW = 0.55
    SWING_TIME = 0.20
    SWING_COOLDOWN = 0.38
    ROLL_TIME = 0.28
    ROLL_SPEED = 430.0
    ROLL_COOLDOWN = 0.70
    ROLL_IFRAMES = 0.34
    HURT_IFRAMES = 0.80

    def __init__(self, x=480, y=520):
        self.x, self.y = float(x), float(y)
        self.rect = pygame.Rect(0, 0, 28, 28)
        self.rect.center = (round(self.x), round(self.y))
        self.radius = self.RADIUS
        self.max_hp = 100
        self.hp = 100
        self.aim_angle = -math.pi / 2
        self.facing = 1
        self.swing = 0.0
        self.swing_elapsed = 0.0
        self.swing_cd = 0.0
        self.swing_angle = 0.0
        self.swing_hit = False
        self.roll_time = 0.0
        self.roll_cd = 0.0
        self.roll_dir = (0.0, -1.0)
        self.invuln = 0.0
        self.hurt_flash = 0.0
        self.trail = []
        self.walk = 0.0                       # 0 = standing, 1 = walking (fades), for the little step bob
        self.walk_phase = 0.0

    @property
    def alive(self):
        return self.hp > 0

    @property
    def rolling(self):
        return self.roll_time > 0

    def take_damage(self, amount):
        """Returns the damage actually taken (0 while rolling or recovering from a hit)."""
        if self.hp <= 0 or self.invuln > 0:
            return 0
        self.hp = max(0, self.hp - amount)
        self.invuln = self.HURT_IFRAMES
        self.hurt_flash = 0.25
        return amount

    def update(self, dt, inp, bounds):
        self.swing_cd = max(0.0, self.swing_cd - dt)
        self.roll_cd = max(0.0, self.roll_cd - dt)
        self.invuln = max(0.0, self.invuln - dt)
        self.hurt_flash = max(0.0, self.hurt_flash - dt)
        if self.swing > 0:
            self.swing = max(0.0, self.swing - dt)
            self.swing_elapsed += dt
        if not self.alive:
            self.roll_time = 0.0
            return

        mx, my = inp.move
        length = math.hypot(mx, my)
        if length > 1:
            mx, my = mx / length, my / length
        self.aim_angle = math.atan2(inp.aim[1] - self.y, inp.aim[0] - self.x)
        if abs(math.cos(self.aim_angle)) > 0.2:
            self.facing = 1 if math.cos(self.aim_angle) > 0 else -1

        if inp.roll and self.roll_cd <= 0 and not self.rolling:
            direction = (mx, my) if length > 0.1 else (math.cos(self.aim_angle), math.sin(self.aim_angle))
            norm = math.hypot(*direction) or 1.0
            self.roll_dir = (direction[0] / norm, direction[1] / norm)
            self.roll_time = self.ROLL_TIME
            self.roll_cd = self.ROLL_COOLDOWN
            self.invuln = max(self.invuln, self.ROLL_IFRAMES)
            self.swing = 0.0

        if inp.attack and self.swing_cd <= 0 and not self.rolling:
            self.swing = self.SWING_TIME
            self.swing_elapsed = 0.0
            self.swing_cd = self.SWING_COOLDOWN
            self.swing_angle = self.aim_angle
            self.swing_hit = False

        if self.rolling:
            self.roll_time = max(0.0, self.roll_time - dt)
            vx, vy = self.roll_dir[0] * self.ROLL_SPEED, self.roll_dir[1] * self.ROLL_SPEED
            self.trail.append((self.x, self.y, 0.18))
        else:
            speed = self.SPEED * (self.SWING_SLOW if self.swing > 0 else 1.0)
            vx, vy = mx * speed, my * speed
        self.trail = [(x, y, t - dt) for x, y, t in self.trail if t - dt > 0]

        walking = (not self.rolling) and math.hypot(vx, vy) > 20
        self.walk += ((1.0 if walking else 0.0) - self.walk) * min(1.0, dt * 12.0)
        self.walk_phase += dt * 15.0 * (0.4 + 0.6 * self.walk)

        left, top, right, bottom = bounds
        self.x = min(max(self.x + vx * dt, left + self.radius), right - self.radius)
        self.y = min(max(self.y + vy * dt, top + self.radius), bottom - self.radius)
        self.rect.center = (round(self.x), round(self.y))


# ---------------------------------------------------------------------------
# the arena
# ---------------------------------------------------------------------------


class Arena:
    SWORD_DAMAGE = 18
    SWORD_REACH = 86
    SWORD_ARC = math.radians(62)
    SWORD_DELAY = 0.05

    def __init__(self, seed=None, view=None):
        self.bounds = BOUNDS
        self.view = view or TopDownView()      # how the floor is drawn (see view.py); the fight itself never changes
        self.restart(seed)

    def restart(self, seed=None):
        self.seed = seed
        old_sfx = getattr(self.boss, "sfx", None) if hasattr(self, "boss") else None
        if old_sfx is not None:
            old_sfx.stop_all()                                 # cut off the old fight's roars
        self.boss = Minotaur(seed=seed)
        self.boss.view = self.view
        self._queued = []                                      # sounds waiting for their moment: [time, name]
        self.player = Player()
        self.state = "fight"                  # fight / won / lost
        self.clock = 0.0
        self.floaters = []                    # [text, x, y, age, colour, size]
        self.sparks = []                      # [x, y, vx, vy, age, colour]
        self.loot = []
        self.red_flash = 0.0
        self._last_hp = self.player.hp
        self._last_boss_state = self.boss.state

    # -- simulation ---------------------------------------------------------------
    def step(self, dt, inp):
        self.clock += dt
        p, boss = self.player, self.boss
        swing_cd, roll_cd = p.swing_cd, p.roll_cd
        if self.state != "lost":
            p.update(dt, inp, self.bounds)
        elif p.alive is False:
            p.update(dt, Inputs(aim=inp.aim), self.bounds)
        if p.swing_cd > swing_cd:                              # the cooldown jumps up the moment a swing starts
            self._sound("swing", 1.0, self._player_x())
        if p.roll_cd > roll_cd:
            self._sound("roll", 1.0, self._player_x())
        sx, _ = self.view.screen_dir(math.cos(p.aim_angle), math.sin(p.aim_angle))
        if abs(sx) > 0.2:
            p.facing = 1 if sx > 0 else -1                     # he looks left or right on SCREEN
        self._sword_hits()
        boss.update(dt, p, self.bounds)
        self._announce_skill()

        if p.hp < self._last_hp:
            self.red_flash = 0.35
            self._sound("player_down" if p.hp <= 0 else "hurt", 1.0, self._player_x())
        self._last_hp = p.hp
        self.red_flash = max(0.0, self.red_flash - dt)

        if self.state == "fight":
            if boss.is_defeated():
                self.state = "won"
                self.loot = list(boss.drop_loot() or [])
                self._sound("victory")
            elif boss.is_alive() is False:
                pass                                       # dying: let the death animation play
            elif not p.alive:
                self.state = "lost"
                self._sound_later(0.7, "defeat")           # after the fall
        self._update_effects(dt)
        self._play_queued()

    # -- sound (the boss owns the shared sound board; None or no audio = silence) ----------------
    def _sound(self, name, volume=1.0, screen_x=None):
        board = getattr(self.boss, "sfx", None)
        if board is not None:
            board.play(name, volume, screen_x)

    def _sound_later(self, delay, name):
        self._queued.append([self.clock + delay, name])

    def _play_queued(self):
        due = [q for q in self._queued if q[0] <= self.clock]
        self._queued = [q for q in self._queued if q[0] > self.clock]
        for _when, name in due:
            self._sound(name)

    def _player_x(self):
        return self.view.project(self.player.x, self.player.y)[0]

    CALLOUTS = {"charge_windup": ("CHARGE!", (255, 120, 100)), "slam_windup": ("SLAM!", (255, 170, 80)),
                "cast_windup": ("ROAR!", (255, 190, 90)), "rain_windup": ("ROCKS!", (210, 180, 140)),
                "leap_windup": ("LEAP!", (255, 150, 90)), "transition": ("ENRAGED!", (255, 80, 80))}

    def _announce_skill(self):
        """A short floating word when he starts a skill, so the wind-up pose is easy to learn."""
        state = self.boss.state
        if state != self._last_boss_state and state in self.CALLOUTS:
            text, colour = self.CALLOUTS[state]
            rx, ry = self.boss._ref()
            recent = sum(1 for f in self.floaters if f[5] == 40 and f[3] < 0.6)       # callouts still on screen
            self.floaters.append([text, rx, ry - 150 - 44 * recent, 0.0, colour, 40])
        self._last_boss_state = state

    def _targets(self):
        hittables = getattr(self.boss, "hittables", None)
        return list(hittables()) if callable(hittables) else [self.boss]

    def _sword_hits(self):
        p = self.player
        if p.swing <= 0 or p.swing_hit or p.swing_elapsed < self.SWORD_DELAY or not p.alive:
            return
        p.swing_hit = True
        for target in self._targets():
            tx, ty = target.x, target.y
            radius = getattr(target, "radius", 46)
            dx, dy = tx - p.x, ty - p.y
            dist = math.hypot(dx, dy)
            if dist > self.SWORD_REACH + radius:
                continue
            diff = abs((math.atan2(dy, dx) - p.swing_angle + math.pi) % math.tau - math.pi)
            if diff > self.SWORD_ARC and dist > radius + 26:
                continue
            dealt = target.take_damage(self.SWORD_DAMAGE)
            hx, hy = p.x + dx / (dist or 1) * min(dist, radius + 20), p.y + dy / (dist or 1) * min(dist, radius + 20)
            hx, hy = self.view.project(hx, hy)                 # effects live on the screen
            body = 70 if self.view.iso else 0                  # in isometric the hit is at chest height above the floor spot
            if dealt:
                big = dealt > self.SWORD_DAMAGE
                self._sound("hit_heavy" if big else "hit", 1.0, hx)
                self.floaters.append([str(int(dealt)) + ("!" if big else ""), hx, hy - 30 - body, 0.0,
                                      (255, 170, 60) if big else (255, 246, 214), 34 if big else 26])
                for _ in range(10 if big else 6):
                    ang = random.uniform(0, math.tau)
                    speed = random.uniform(80, 260)
                    rise = 60 if self.view.iso else 0                      # seen from above, sparks fly out flat, not upwards
                    self.sparks.append([hx, hy - body, math.cos(ang) * speed, math.sin(ang) * speed - rise, 0.0,
                                        random.choice([(255, 226, 150), (255, 150, 60), (255, 255, 255)])])
            else:
                self._sound("block", 1.0, hx)
                self.floaters.append(["BLOCKED", hx, hy - 30 - body, 0.0, (150, 156, 180), 22])

    def _update_effects(self, dt):
        for f in self.floaters:
            f[3] += dt
            f[2] -= 46 * dt
        self.floaters = [f for f in self.floaters if f[3] < 0.9]
        for s in self.sparks:
            s[4] += dt
            s[0] += s[2] * dt
            s[1] += s[3] * dt
            if self.view.iso:
                s[3] += 520 * dt                                   # isometric room: they arc and fall
            else:
                drag = max(0.0, 1.0 - 4.0 * dt)                    # top-down: they just slow down
                s[2] *= drag
                s[3] *= drag
        self.sparks = [s for s in self.sparks if s[4] < 0.45]

    # -- drawing -----------------------------------------------------------------
    def draw(self, screen, font, big_font):
        if not hasattr(self, "_world"):
            self._world = pygame.Surface(WINDOW)
        world = self._world
        boss = self.boss
        if self.view.iso:
            art = self._draw_world_iso(world)
        else:
            art = self._draw_world_topdown(world)
        world.blit(art.vignette, (0, 0))
        art.draw_torches(world, self.clock)

        shake = getattr(boss, "shake", 0.0) or 0.0
        sx = sy = 0
        if shake > 0.01:                                       # smooth, decaying wobble instead of random jitter
            amp = min(7.0, shake * 7.0)
            t = self.clock
            sx = int(round(amp * (0.6 * math.sin(t * 47) + 0.4 * math.sin(t * 83 + 1.3))))
            sy = int(round(amp * (0.6 * math.sin(t * 53 + 0.7) + 0.4 * math.sin(t * 91))))
        screen.fill((0, 0, 0))
        screen.blit(world, (sx, sy))

        for text, x, y, age, colour, size in self.floaters:
            surf = pygame.font.Font(None, size).render(text, True, colour)
            surf.set_alpha(int(255 * (1 - age / 0.9)))
            screen.blit(surf, (x - surf.get_width() // 2, y))
        if self.red_flash > 0:
            veil = pygame.Surface(WINDOW, pygame.SRCALPHA)
            veil.fill((200, 20, 30, int(110 * self.red_flash / 0.35)))
            screen.blit(veil, (0, 0))
        self._draw_hud(screen, font)
        if self.state in ("won", "lost"):
            self._draw_end_screen(screen, font, big_font)

    def _draw_world_topdown(self, world):
        art = get_art()
        world.blit(art.background, (0, 0))
        self.boss.draw(world)
        self._draw_player(world)               # always on top: he is 224 px wide, you must never lose yourself
        self._draw_slash(world)
        for x, y, vx, vy, age, colour in self.sparks:
            pygame.draw.rect(world, colour, (int(x) // PX * PX, int(y) // PX * PX, PX, PX))
        return art

    def _draw_world_iso(self, world):
        """
        The isometric picture, in three layers: the room, then everything that lies FLAT on the floor
        (hazard circles, charge lane, rings, sword swing) turned onto the floor, then everything that
        STANDS UP (him, you, fireballs, falling rocks) drawn back to front.
        """
        view, boss, p = self.view, self.boss, self.player
        art = get_iso_art(view)
        world.blit(art.background, (0, 0))

        region = self._ground_region()
        if region is not None:                                 # only flatten the part of the floor that has something on it
            if not hasattr(self, "_ground"):
                self._ground = pygame.Surface(WINDOW, pygame.SRCALPHA)
            ground = self._ground
            ground.fill((0, 0, 0, 0), region)
            for hazard in boss.hazards:
                getattr(hazard, "draw_ground", hazard.draw)(ground)
            boss.draw_ground(ground)
            self._draw_slash(ground)
            flat, position = view.flatten(ground.subsurface(region), (region.left, region.top))
            world.blit(flat, position)

        standing = [(view.depth(boss.x, boss.y), 1, "boss", boss), (view.depth(p.x, p.y), 2, "player", p)]
        for shot in boss.projectiles:
            if hasattr(shot, "x") and hasattr(shot, "y"):
                standing.append((view.depth(shot.x, shot.y), 3, "shot", shot))
        for hazard in boss.hazards:
            if hasattr(hazard, "draw_air"):
                standing.append((view.depth(hazard.x, hazard.y), 4, "air", hazard))
        standing.sort(key=lambda item: (item[0], item[1]))
        for _, _, kind, obj in standing:                       # back to front: whatever is nearer the camera covers the rest
            if kind == "boss":
                boss.draw_body(world, view)
            elif kind == "player":
                self._draw_player(world)
            elif kind == "shot":
                self._draw_shot(world, obj)
            else:
                obj.draw_air(world, view)
        boss.draw_particles(world)
        for x, y, vx, vy, age, colour in self.sparks:
            pygame.draw.rect(world, colour, (int(x) // PX * PX, int(y) // PX * PX, PX, PX))
        return art

    def _ground_region(self):
        """The part of the floor (a Rect, world coordinates) that has hazards, rings, a lane or a sword swing on it."""
        boss, p = self.boss, self.player
        rects = []
        for hazard in boss.hazards:
            r = int(getattr(hazard, "radius", 100)) + 12
            rects.append(pygame.Rect(int(hazard.x) - r, int(hazard.y) - r, 2 * r, 2 * r))
        ring = {"transition": 360, "cast_windup": 240, "rain_windup": 90, "leap_windup": 100}.get(boss.state)
        if ring:
            rects.append(pygame.Rect(int(boss.x) - ring, int(boss.y) - ring, 2 * ring, 2 * ring))
        if boss.state == "charge_windup":
            ex = boss.x + math.cos(boss.aim_angle) * boss.charge_total
            ey = boss.y + math.sin(boss.aim_angle) * boss.charge_total
            rects.append(pygame.Rect(int(min(boss.x, ex)) - 70, int(min(boss.y, ey)) - 70,
                                     int(abs(ex - boss.x)) + 140, int(abs(ey - boss.y)) + 140))
        if p.swing > 0:
            reach = int(self.SWORD_REACH) + 16
            rects.append(pygame.Rect(int(p.x) - reach, int(p.y) - reach, 2 * reach, 2 * reach))
        if not rects:
            return None
        left, top, right, bottom = self.bounds
        region = rects[0].unionall(rects[1:]).clip(pygame.Rect(left, top, right - left, bottom - top))
        return region if region.width > 2 and region.height > 2 else None

    def _draw_shot(self, surface, shot):
        """A fireball or rock flying over the floor: a glowing ball with its shadow on the ground."""
        sx, sy = self.view.project(shot.x, shot.y)
        radius = int(getattr(shot, "radius", 8))
        colour = tuple(getattr(shot, "color", (255, 150, 60)))
        pygame.draw.ellipse(surface, (10, 8, 16), (int(sx) - radius, int(sy) - radius // 2 + 2, radius * 2, max(4, radius)))
        cx, cy = int(sx), int(sy) - 20
        pygame.draw.circle(surface, tuple(max(0, c // 3) for c in colour), (cx, cy), radius + 4)
        pygame.draw.circle(surface, colour, (cx, cy), radius + 1)
        pygame.draw.circle(surface, (255, 246, 214), (cx - radius // 3, cy - radius // 3), max(2, radius // 3))

    KNIGHT = [
        "...pp.....",
        "..khhk....",
        ".khHhhk..w",
        ".kssssk..w",
        "..kbbk...w",
        ".kbbbbk.gg",
        ".kbBBbk..l",
        "..kllk....",
        "..kBBk....",
        "..kk.kk...",
    ]
    KNIGHT_COLOURS = {"k": (24, 16, 20), "h": (150, 156, 172), "H": (206, 212, 226), "p": (200, 60, 56),
                      "s": (222, 168, 134), "b": (66, 104, 182), "B": (42, 66, 124), "l": (100, 68, 46),
                      "w": (214, 220, 234), "g": (236, 204, 74)}

    def _draw_player(self, surface):
        p = self.player
        sx, sy = self.view.project(p.x, p.y)
        lift = 18 if self.view.iso else 0                      # in isometric his feet are on the floor spot, so his body is above it
        cx, cy = int(sx), int(sy) - lift
        pygame.draw.ellipse(surface, (10, 8, 16), (cx - 16, cy + 12, 32, 12))             # shadow
        if p.rolling:
            for x, y, t in p.trail:
                size = int(8 + 14 * t / 0.18)
                tx, ty = self.view.project(x, y)
                pygame.draw.rect(surface, (52, 70, 120), (int(tx) // PX * PX - size // 2, int(ty - lift) // PX * PX - size // 2, size, size))
            pygame.draw.circle(surface, (24, 16, 20), (cx, cy), 17)
            pygame.draw.circle(surface, (66, 104, 182), (cx, cy), 14)
            spin = self.clock * 22
            for k in range(3):
                a = spin + k * math.tau / 3
                pygame.draw.rect(surface, (206, 212, 226), (cx + int(math.cos(a) * 8) // PX * PX - 2, cy + int(math.sin(a) * 8) // PX * PX - 2, PX, PX))
            return
        if p.invuln > 0 and p.hurt_flash > 0 and int(self.clock * 24) % 2 == 0:
            return
        flip = p.facing < 0
        x0 = cx - 14 if not flip else cx + 14 - 10 * PX
        y0 = cy - 22 - int(round(abs(math.sin(p.walk_phase)) * 3 * p.walk))
        for r, row in enumerate(self.KNIGHT):
            for c, ch in enumerate(row):
                if ch == ".":
                    continue
                col = c if not flip else len(row) - 1 - c
                colour = self.KNIGHT_COLOURS[ch]
                if p.hurt_flash > 0:
                    colour = (255, 255, 255) if int(self.clock * 30) % 2 == 0 else (255, 90, 90)
                pygame.draw.rect(surface, colour, (x0 + col * PX, y0 + r * PX, PX, PX))

    def _draw_slash(self, surface):
        p = self.player
        if p.swing <= 0:
            return
        progress = 1.0 - p.swing / p.SWING_TIME
        steps = 14
        for i in range(steps + 1):
            frac = i / steps
            if frac > progress * 1.15:
                break
            ang = p.swing_angle - self.SWORD_ARC + 2 * self.SWORD_ARC * frac
            for ring, colour in ((self.SWORD_REACH - 6, (255, 255, 255)), (self.SWORD_REACH - 22, (170, 200, 255)),
                                 (self.SWORD_REACH - 38, (96, 130, 210))):
                if frac < progress - 0.55 and ring < self.SWORD_REACH - 10:
                    continue
                x = p.x + math.cos(ang) * ring
                y = p.y + math.sin(ang) * ring
                pygame.draw.rect(surface, colour, (int(x) // PX * PX, int(y) // PX * PX, PX, PX))

    # -- HUD ----------------------------------------------------------------------
    def _draw_hud(self, screen, font):
        draw_bar = getattr(self.boss, "draw_health_bar", None)
        if callable(draw_bar):
            draw_bar(screen, font)
        else:
            w = 500
            x = (WINDOW[0] - w) // 2
            pygame.draw.rect(screen, (20, 14, 20), (x - 2, 18, w + 4, 20))
            pygame.draw.rect(screen, (200, 50, 50), (x, 20, int(w * self.boss.hp / self.boss.max_hp), 16))
            screen.blit(font.render(self.boss.name, True, (240, 236, 250)), (x, 40))
        p = self.player
        screen.blit(font.render("HP", True, (240, 236, 250)), (56, 610))
        pygame.draw.rect(screen, (16, 12, 20), (84, 606, 224, 22))
        segments = 20
        for i in range(segments):
            if p.hp > i * p.max_hp / segments:
                pygame.draw.rect(screen, (214, 64, 72) if p.hp > p.max_hp * 0.3 else (255, 120, 60),
                                 (88 + i * 11, 610, 9, 14))
        screen.blit(font.render("ROLL", True, (240, 236, 250)), (336, 610))
        ready = 1.0 - p.roll_cd / p.ROLL_COOLDOWN
        pygame.draw.rect(screen, (16, 12, 20), (388, 610, 104, 14))
        pygame.draw.rect(screen, (96, 150, 230) if ready >= 1 else (70, 80, 110), (390, 612, int(100 * ready), 10))
        hint = "WASD | click sword | right-click roll | P pause | M sound"
        surf = pygame.font.Font(None, 22).render(hint, True, (130, 124, 150))
        screen.blit(surf, (WINDOW[0] - surf.get_width() - 56, 612))
        if self.boss.state == "intro" and getattr(self.boss, "intro", ""):
            line = font.render(self.boss.intro, True, (236, 214, 150))
            screen.blit(line, ((WINDOW[0] - line.get_width()) // 2, 82))

    def _draw_end_screen(self, screen, font, big_font):
        veil = pygame.Surface(WINDOW, pygame.SRCALPHA)
        veil.fill((6, 4, 12, 170))
        screen.blit(veil, (0, 0))
        won = self.state == "won"
        title = big_font.render("VICTORY" if won else "YOU DIED", True, (255, 214, 90) if won else (214, 64, 72))
        screen.blit(title, ((WINDOW[0] - title.get_width()) // 2, 190))
        lines = []
        if won:
            death_line = getattr(self.boss, "death_line", "")
            if death_line:
                lines.append(death_line)
            if self.loot:
                lines.append("Loot: " + ", ".join(str(item) for item in self.loot))
        lines.append("Press R to fight again, ESC to leave")
        for i, text in enumerate(lines):
            surf = font.render(text, True, (230, 224, 240))
            screen.blit(surf, ((WINDOW[0] - surf.get_width()) // 2, 290 + i * 34))


# ---------------------------------------------------------------------------
# a simple bot (for --bot, --shot and the tests)
# ---------------------------------------------------------------------------


def _escape_vector(arena):
    """Which way to run to dodge ground circles, falling boulders and fireballs. Returns (vx, vy, urgent)."""
    boss, p = arena.boss, arena.player
    vx = vy = 0.0
    urgent = False
    for hazard in boss.hazards:
        if getattr(hazard, "state", "") != "warning":
            continue
        dx, dy = p.x - hazard.x, p.y - hazard.y
        dist = math.hypot(dx, dy) or 1.0
        margin = hazard.radius + 50
        if dist < margin:
            weight = (margin - dist) / margin + 0.3
            vx += dx / dist * weight
            vy += dy / dist * weight
            if dist < hazard.radius + 20 and hazard.duration - hazard.timer < 0.3:
                urgent = True
    for shot in boss.projectiles:
        dx, dy = p.x - shot.x, p.y - shot.y
        dist = math.hypot(dx, dy)
        if dist > 150:
            continue
        ux, uy = math.cos(shot.angle), math.sin(shot.angle)
        along = dx * ux + dy * uy
        across = -dx * uy + dy * ux
        if along > 0 and abs(across) < 52:                      # it is heading for me: sidestep it
            sign = 1.0 if across >= 0 else -1.0
            vx += -uy * sign * 1.6
            vy += ux * sign * 1.6
            if dist < 75:
                urgent = True
    return vx, vy, urgent


def bot_inputs(arena):
    """Plays a careful hit-and-run: dodges every skill, hits him when it is safe."""
    boss, p = arena.boss, arena.player
    dx, dy = p.x - boss.x, p.y - boss.y
    dist = math.hypot(dx, dy) or 1.0
    to_boss = (-dx / dist, -dy / dist)
    move, attack, roll = (0.0, 0.0), False, False
    state = boss.state
    reach = arena.SWORD_REACH + boss.radius - 22

    if state == "charge_windup":
        ax, ay = math.cos(boss.aim_angle), math.sin(boss.aim_angle)
        side = dx * -ay + dy * ax
        sign = 1.0 if side >= 0 else -1.0
        move = (-ay * sign, ax * sign)
    elif state == "charge":
        ax, ay = math.cos(boss.aim_angle), math.sin(boss.aim_angle)
        side = abs(dx * -ay + dy * ax)
        along = dx * ax + dy * ay
        if side < 70 and along > -150:
            sign = 1.0 if (dx * -ay + dy * ax) >= 0 else -1.0
            move = (-ay * sign, ax * sign)
            roll = True
    elif state == "slam_windup":
        cx, cy = boss.x, boss.y + 40
        rx, ry = p.x - cx, p.y - cy
        rd = math.hypot(rx, ry) or 1.0
        move = (rx / rd, ry / rd)
        if rd < 230 and boss.state_time > 0.8:
            roll = True
    elif state == "stunned":
        move = to_boss if dist > reach - 12 else (0.0, 0.0)
        attack = dist <= reach
    elif state in ("idle", "recover"):
        if dist > reach:
            move = to_boss
        else:
            attack = True
            move = (-to_boss[1] * 0.6, to_boss[0] * 0.6)
    elif state in ("cast_windup", "leap_windup"):
        move = (-to_boss[0], -to_boss[1]) if dist < 240 else (0.0, 0.0)
    else:
        if dist < 200:
            move = (-to_boss[0], -to_boss[1])

    if state not in ("charge_windup", "charge", "slam_windup"):
        vx, vy, urgent = _escape_vector(arena)
        if vx or vy:                                             # a circle or fireball is near: run first, fight later
            length = math.hypot(vx, vy) or 1.0
            move, attack = (vx / length, vy / length), False
            roll = roll or urgent
    return Inputs(move=move, aim=(boss.x, boss.y), attack=attack, roll=roll)


# ---------------------------------------------------------------------------
# window loop
# ---------------------------------------------------------------------------


def _keyboard_inputs(events, view=None):
    view = view or TopDownView()
    keys = pygame.key.get_pressed()
    mx = (keys[pygame.K_d] or keys[pygame.K_RIGHT]) - (keys[pygame.K_a] or keys[pygame.K_LEFT])
    my = (keys[pygame.K_s] or keys[pygame.K_DOWN]) - (keys[pygame.K_w] or keys[pygame.K_UP])
    buttons = pygame.mouse.get_pressed()
    return Inputs(move=view.to_world(mx, my), aim=view.unproject(*pygame.mouse.get_pos()),
                  attack=bool(buttons[0] or keys[pygame.K_j] or keys[pygame.K_SPACE]),
                  roll=bool(buttons[2] or keys[pygame.K_k] or keys[pygame.K_LSHIFT] or keys[pygame.K_RSHIFT]))


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    shot = argv[argv.index("--shot") + 1] if "--shot" in argv else None
    seconds = float(argv[argv.index("--seconds") + 1]) if "--seconds" in argv else 14.0
    use_bot = "--bot" in argv or shot is not None
    view = IsoView() if "--iso-room" in argv else TopDownView()
    if shot:
        os.environ["SDL_VIDEODRIVER"] = "dummy"
        os.environ["SDL_AUDIODRIVER"] = "dummy"

    try:
        pygame.mixer.pre_init(44100, -16, 2, 512)           # stereo (sounds pan with the action), small buffer = little lag
    except Exception:
        pass
    pygame.init()
    screen = pygame.display.set_mode(WINDOW)
    pygame.display.set_caption("RealmQuest - The Minotaur's Labyrinth")
    font, big_font = pygame.font.Font(None, 26), pygame.font.Font(None, 110)
    arena = Arena(seed=1 if shot else None, view=view)
    if shot or "--mute" in argv:
        arena.boss.sfx.muted = True                          # a headless run is much faster than real time: no sound
    else:
        arena.boss.sfx.load()                                # read the sound files now, not in the middle of the fight

    if shot:
        for _ in range(int(seconds * 60)):
            arena.step(1 / 60, bot_inputs(arena))
        arena.draw(screen, font, big_font)
        pygame.image.save(screen, shot)
        print("saved", shot, "| boss hp", arena.boss.hp, "| player hp", arena.player.hp, "| state", arena.state)
        return

    clock, paused = pygame.time.Clock(), False
    running = True
    while running:
        dt = min(clock.tick(60) / 1000.0, 1 / 30)
        events = pygame.event.get()
        for event in events:
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    running = False
                elif event.key == pygame.K_r:
                    arena.restart()
                elif event.key == pygame.K_p:
                    paused = not paused
                    arena.boss.sfx.set_paused(paused)
                elif event.key == pygame.K_m:
                    muted = arena.boss.sfx.toggle_mute()
                    arena.floaters.append(["SOUND OFF" if muted else "SOUND ON", WINDOW[0] // 2, 150, 0.0,
                                           (190, 190, 210), 26])
                elif event.key == pygame.K_1:
                    arena.boss.debug_set_hp_percent(0.45)
                elif event.key == pygame.K_2:
                    arena.player.hp = arena.player.max_hp
                elif event.key == pygame.K_3:
                    arena.boss.take_damage(10 ** 6)
        if not paused:
            arena.step(dt, bot_inputs(arena) if use_bot else _keyboard_inputs(events, view))
        arena.draw(screen, font, big_font)
        if paused:
            label = big_font.render("PAUSED", True, (240, 236, 250))
            screen.blit(label, ((WINDOW[0] - label.get_width()) // 2, 250))
        pygame.display.flip()
    pygame.quit()


if __name__ == "__main__":
    main()
