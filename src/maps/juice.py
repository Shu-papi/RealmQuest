"""
juice.py - The little things that make hits feel like hits: camera shake, a brief hit-pause,
puffs when monsters die, sparks on impact, the level-up burst and the red flash when the
hero is hurt.

    juice = Juice(settings)                  # settings.screen_shake turns the shake on / off
    juice.add_shake(0.4)                     # 0..1, adds up, fades by itself
    juice.hit_pause(0.05)                    # the Game skips gameplay updates while paused()
    juice.puff(x, y, color); juice.sparks(x, y); juice.level_up(x, y); juice.hurt_flash()
    juice.update(dt)
    dx, dy = juice.offset()                  # add to the camera
    juice.draw_world(surf, cam_x, cam_y, t)  # particles, in world coordinates
    juice.draw_screen(surf)                  # the red hurt flash, over everything but the HUD

Pure effects: nothing here changes the game's state.
"""
from __future__ import annotations

import math
import random

import pygame

BODY = 14                 # sprites stand on (x, y); their middle is this far above
MAX_SHAKE_PX = 9


class Juice:
    def __init__(self, settings=None):
        self.settings = settings
        self.shake = 0.0          # trauma 0..1
        self.hitstop = 0.0
        self.flash = 0.0          # red edge flash 0..1
        self.parts: list[list] = []   # [kind, x, y, vx, vy, life, max_life, size, color]
        self.rings: list[list] = []   # [x, y, life, max_life, radius, color]
        self.t = 0.0
        self._edge = None

    # ---- triggers ----------------------------------------------------------------
    def add_shake(self, k):
        self.shake = min(1.0, self.shake + max(0.0, k))

    def hit_pause(self, seconds):
        self.hitstop = max(self.hitstop, seconds)

    def paused(self):
        return self.hitstop > 0

    def hurt_flash(self, k=1.0):
        self.flash = min(1.0, max(self.flash, k))

    def puff(self, x, y, color=(200, 190, 180), big=False):
        """A monster dies: a ring of smoke puffs and a few bright bits."""
        n = 16 if big else 9
        for i in range(n):
            a = i * math.tau / n + random.uniform(-0.3, 0.3)
            sp = random.uniform(40, 110) * (1.6 if big else 1.0)
            life = random.uniform(0.35, 0.6)
            self.parts.append(["smoke", x, y - BODY, math.cos(a) * sp, math.sin(a) * sp * 0.6 - 20,
                               life, life, random.uniform(5, 9) * (1.4 if big else 1.0), (70, 64, 72)])
        for _ in range(6 if big else 3):
            a = random.uniform(0, math.tau)
            sp = random.uniform(80, 160)
            self.parts.append(["spark", x, y - BODY, math.cos(a) * sp, math.sin(a) * sp - 60,
                               0.4, 0.4, 3, color])
        if big:
            self.rings.append([x, y, 0.5, 0.5, 90, color])

    def sparks(self, x, y, color=(255, 236, 170), n=5):
        """Something got hit."""
        for _ in range(n):
            a = random.uniform(0, math.tau)
            sp = random.uniform(90, 200)
            self.parts.append(["spark", x, y - BODY, math.cos(a) * sp, math.sin(a) * sp, 0.22, 0.22, 2, color])

    def level_up(self, x, y):
        """Golden rings and rising motes around the hero."""
        for k in range(3):
            self.rings.append([x, y, 0.6 + k * 0.18, 0.6 + k * 0.18, 70 + k * 24, (255, 220, 120)])
        for _ in range(28):
            a = random.uniform(0, math.tau)
            r = random.uniform(6, 30)
            life = random.uniform(0.7, 1.3)
            self.parts.append(["mote", x + math.cos(a) * r, y - random.uniform(0, 20), 0, -random.uniform(50, 110),
                               life, life, random.uniform(2, 4), random.choice([(255, 226, 130), (255, 255, 220),
                                                                              (170, 220, 255)])])

    # ---- per frame -----------------------------------------------------------------
    def update(self, dt):
        self.t += dt
        self.hitstop = max(0.0, self.hitstop - dt)
        self.shake = max(0.0, self.shake - dt * 1.8)
        self.flash = max(0.0, self.flash - dt * 2.6)
        for p in self.parts:
            p[1] += p[3] * dt
            p[2] += p[4] * dt
            if p[0] == "spark":
                p[4] += 380 * dt                  # sparks fall
            else:
                p[3] *= 1 - min(1.0, dt * 3)      # smoke and motes slow down
            p[5] -= dt
        self.parts = [p for p in self.parts if p[5] > 0]
        for r in self.rings:
            r[2] -= dt
        self.rings = [r for r in self.rings if r[2] > 0]

    def offset(self):
        """Camera offset from the shake (zero when Settings > Screen Shake is off)."""
        if self.shake <= 0 or (self.settings is not None and not getattr(self.settings, "screen_shake", True)):
            return 0, 0
        k = self.shake * self.shake * MAX_SHAKE_PX         # small shakes stay subtle
        return (int(math.sin(self.t * 71.3) * k), int(math.cos(self.t * 57.1) * k))

    # ---- drawing -------------------------------------------------------------------
    def draw_world(self, surf, cx, cy, t=0.0):
        for x, y, life, mx, radius, col in self.rings:
            k = 1 - life / mx
            r = int(12 + radius * k)
            w, h = r * 2 + 6, int(r * 1.4) + 6
            layer = pygame.Surface((w, h), pygame.SRCALPHA)
            pygame.draw.ellipse(layer, (*col, int(220 * (1 - k))), (0, 0, w, h), 3)
            surf.blit(layer, (int(x - cx) - w // 2, int(y - cy) - h // 2))
        for kind, x, y, _vx, _vy, life, mx, size, col in self.parts:
            k = life / mx
            X, Y = int(x - cx), int(y - cy)
            if kind == "smoke":
                r = max(1, int(size * (1.6 - k * 0.6)))
                s = pygame.Surface((r * 2, r * 2), pygame.SRCALPHA)
                pygame.draw.circle(s, (*col, int(170 * k)), (r, r), r)
                surf.blit(s, (X - r, Y - r))
            else:
                r = max(1, int(size * (0.5 + 0.5 * k)))
                if kind == "mote" and k < 0.5 and int(self.t * 20 + x) % 2:
                    continue                                   # motes twinkle out
                pygame.draw.circle(surf, col, (X, Y), r)

    def draw_screen(self, surf):
        """Red edges when the hero is hurt."""
        if self.flash <= 0.01:
            return
        if self._edge is None or self._edge.get_size() != surf.get_size():
            self._edge = _edge_glow(surf.get_size())
        self._edge.set_alpha(int(200 * self.flash))
        surf.blit(self._edge, (0, 0))


def _edge_glow(size):
    """A red frame that fades toward the middle (drawn small, scaled up smoothly)."""
    w, h = 64, 36
    s = pygame.Surface((w, h), pygame.SRCALPHA)
    for y in range(h):
        for x in range(w):
            dx, dy = abs(x / (w - 1) - 0.5) * 2, abs(y / (h - 1) - 0.5) * 2
            d = max(dx, dy)
            a = max(0.0, (d - 0.55) / 0.45)
            s.set_at((x, y), (200, 20, 20, int(255 * a * a)))
    return pygame.transform.smoothscale(s, size)
