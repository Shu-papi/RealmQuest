"""
dash_fx.py - the hero's dash effect: fading pale-blue afterimages along the dash, a few speed
lines streaming behind, and a small burst of air where the dash started.

    trail = DashTrail()
    trail.draw(surf, sprite, x, y, left, dashing, cam_x, cam_y, dash_dir)   # before the hero

The Player calls it from its own draw(), so it works the same in the dungeon and the overworld.
It keeps its own wall clock (like HeroSprite), so it needs no update() call. Purely visual:
`config/characters/hero.toml` dash_effect = false turns it off (combat.DASH_EFFECT).
"""
from __future__ import annotations

import math
import random

import pygame

GHOST_GAP = 0.028          # s between two afterimages while dashing
GHOST_LIFE = 0.26          # s an afterimage takes to fade out
GHOST_ALPHA = 150          # how solid a fresh afterimage is (0..255)
GHOST_TINT = (150, 205, 255)
LINE_LIFE = 0.22           # s a speed line lasts
LINE_COLOR = (215, 238, 255)
BODY = 22                  # px above the feet where the speed lines and the burst sit


def _enabled():
    try:
        from . import combat
    except ImportError:
        import combat
    return bool(getattr(combat, "DASH_EFFECT", True))


class DashTrail:
    def __init__(self):
        self.ghosts: list[list] = []     # [img, x, y, life]  (img's top-left in world pixels)
        self.lines: list[list] = []      # [x, y, dx, dy, length, life]
        self.rings: list[list] = []      # [x, y, life]
        self.gap = 0.0
        self.was_dashing = False
        self._last = None
        self._tints: dict[int, pygame.Surface] = {}

    def clear(self):
        self.ghosts.clear()
        self.lines.clear()
        self.rings.clear()
        self.was_dashing = False

    def _tint(self, img):
        key = id(img)
        out = self._tints.get(key)
        if out is None:
            out = img.copy()
            out.fill((*GHOST_TINT, 255), special_flags=pygame.BLEND_RGBA_MULT)
            out.fill((40, 60, 90, 0), special_flags=pygame.BLEND_RGBA_ADD)
            if len(self._tints) > 64:
                self._tints.clear()
            self._tints[key] = out
        return out

    def _clock(self):
        now = pygame.time.get_ticks() / 1000.0
        dt = 0.0 if self._last is None else min(0.1, max(0.0, now - self._last))
        self._last = now
        return dt

    def step(self, dt, sprite, x, y, left, dashing, dash_dir=(0.0, 1.0)):
        """Age the effect by dt and, while dashing, drop new afterimages and speed lines."""
        for g in self.ghosts:
            g[3] -= dt
        self.ghosts = [g for g in self.ghosts if g[3] > 0]
        for ln in self.lines:
            ln[5] -= dt
        self.lines = [ln for ln in self.lines if ln[5] > 0]
        for r in self.rings:
            r[2] -= dt
        self.rings = [r for r in self.rings if r[2] > 0]
        if not _enabled():
            self.was_dashing = dashing
            return
        dx, dy = dash_dir
        n = math.hypot(dx, dy) or 1.0
        dx, dy = dx / n, dy / n
        if dashing and not self.was_dashing:            # the dash starts: a puff of air
            self.rings.append([x, y - 4, 0.25])
            self.gap = 0.0
        if dashing:
            self.gap -= dt
            if self.gap <= 0:
                self.gap = GHOST_GAP
                try:
                    img, (ax, ay) = sprite.frame(left)
                    self.ghosts.append([self._tint(img), x - ax, y + 2 - ay, GHOST_LIFE])
                except Exception:                       # a sprite without frames: lines only
                    pass
                for _ in range(2):
                    side = random.uniform(-14, 14)
                    lx = x - dx * random.uniform(8, 22) - dy * side
                    ly = y - BODY + random.uniform(-10, 12) - dy * random.uniform(8, 22) + dx * side
                    self.lines.append([lx, ly, -dx, -dy, random.uniform(14, 28), LINE_LIFE])
        self.was_dashing = dashing

    def draw(self, surf, sprite, x, y, left, dashing, cam_x, cam_y, dash_dir=(0.0, 1.0)):
        """Advance by the wall clock and draw everything (call it just before the hero)."""
        self.step(self._clock(), sprite, x, y, left, dashing, dash_dir)
        for rx, ry, life in self.rings:
            k = life / 0.25
            rad = int(8 + (1 - k) * 20)
            s = pygame.Surface((rad * 2 + 4, rad + 4), pygame.SRCALPHA)
            pygame.draw.ellipse(s, (*LINE_COLOR, int(150 * k)), (2, 2, rad * 2, rad), 2)
            surf.blit(s, (int(rx - cam_x) - rad - 2, int(ry - cam_y) - rad // 2 - 2))
        for img, gx, gy, life in self.ghosts:
            img.set_alpha(int(GHOST_ALPHA * life / GHOST_LIFE))
            surf.blit(img, (round(gx - cam_x), round(gy - cam_y)))
            img.set_alpha(255)
        for lx, ly, dx, dy, length, life in self.lines:
            k = life / LINE_LIFE
            sx, sy = lx - cam_x, ly - cam_y
            end = (sx + dx * length * (0.5 + k), sy + dy * length * (0.5 + k))
            col = tuple(int(c * (0.45 + 0.55 * k)) for c in LINE_COLOR)
            pygame.draw.line(surf, col, (int(sx), int(sy)), (int(end[0]), int(end[1])), 2 if k > 0.5 else 1)
