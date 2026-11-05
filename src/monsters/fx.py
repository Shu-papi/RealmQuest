"""
fx.py - Small retro effects every monster uses: particles, floor warnings, pixel rings.

Everything is drawn with plain squares and alpha shapes, so no extra art files are needed.
Any teammate can reuse these for spells, hazards or events.
"""
import math
import random

import pygame

DANGER = (240, 90, 70)          # the colour of "this is about to hurt you" on the floor


class Particle:
    __slots__ = ("x", "y", "vx", "vy", "life", "max_life", "color", "size", "gravity", "drag")

    def __init__(self, x, y, vx, vy, life, color, size, gravity, drag):
        self.x, self.y, self.vx, self.vy = x, y, vx, vy
        self.life = self.max_life = life
        self.color, self.size, self.gravity, self.drag = color, size, gravity, drag


class Particles:
    """A little pool of square pixel particles (sparks, bone chips, dust, souls)."""

    def __init__(self):
        self.items = []
        self._rng = random.Random()

    def __len__(self):
        return len(self.items)

    def add(self, x, y, vx=0.0, vy=0.0, life=0.5, color=(255, 255, 255),
            size=3, gravity=0.0, drag=0.0):
        self.items.append(Particle(x, y, vx, vy, life, color, size, gravity, drag))

    def burst(self, x, y, color, count=6, speed=140.0, life=0.4, size=3,
              gravity=520.0, up=60.0):
        """Throw `count` particles outwards. `up` kicks them upwards a little."""
        for _ in range(count):
            angle = self._rng.uniform(0, math.tau)
            fast = self._rng.uniform(0.35, 1.0) * speed
            self.add(x, y, math.cos(angle) * fast, math.sin(angle) * fast - up,
                     life * self._rng.uniform(0.7, 1.2), color, size, gravity, 1.5)

    def update(self, dt):
        for p in self.items:
            p.life -= dt
            p.vy += p.gravity * dt
            damp = max(0.0, 1.0 - p.drag * dt)
            p.vx *= damp
            p.vy *= damp
            p.x += p.vx * dt
            p.y += p.vy * dt
        self.items = [p for p in self.items if p.life > 0]

    def draw(self, surface, dy=0):
        for p in self.items:
            size = max(1, int(p.size * (p.life / p.max_life) + 0.5))
            pygame.draw.rect(surface, p.color,
                             (int(p.x) // 2 * 2, int(p.y + dy) // 2 * 2, size, size))


def pixel_ring(surface, center, rx, ry, color, dot=3, count=None, phase=0.0):
    """A ring of square pixels (a retro circle outline). rx != ry gives a floor ellipse."""
    cx, cy = center
    if count is None:
        count = max(14, int(max(rx, ry) / 2.2))
    for i in range(count):
        a = phase + math.tau * i / count
        x = int(cx + math.cos(a) * rx) // 2 * 2
        y = int(cy + math.sin(a) * ry) // 2 * 2
        pygame.draw.rect(surface, color, (x, y, dot, dot))


def dotted_line(surface, start, end, color, dot=3, gap=10):
    (x0, y0), (x1, y1) = start, end
    length = max(1.0, math.hypot(x1 - x0, y1 - y0))
    for i in range(int(length // gap) + 1):
        t = i * gap / length
        pygame.draw.rect(surface, color, (int(x0 + (x1 - x0) * t) // 2 * 2,
                                          int(y0 + (y1 - y0) * t) // 2 * 2, dot, dot))


def ground_circle(surface, x, y, radius, progress, color=DANGER):
    """A danger circle on the floor that fills up as `progress` goes 0 -> 1."""
    r = int(radius)
    size = r * 2 + 4
    layer = pygame.Surface((size, size), pygame.SRCALPHA)
    center = (r + 2, r + 2)
    pygame.draw.circle(layer, color + (50,), center, r)
    pygame.draw.circle(layer, color + (110,), center, max(2, int(r * min(1.0, progress))))
    pygame.draw.circle(layer, color + (230,), center, r, 3)
    surface.blit(layer, (int(x) - r - 2, int(y) - r - 2))


def ground_lane(surface, x, y, angle, length, width, progress, color=DANGER):
    """A danger lane on the floor (a rectangle starting at x, y and pointing along `angle`)."""
    ca, sa = math.cos(angle), math.sin(angle)
    half = width / 2.0

    def corners(reach):
        return [(x + ca * 0 - sa * half, y + sa * 0 + ca * half),
                (x + ca * reach - sa * half, y + sa * reach + ca * half),
                (x + ca * reach + sa * half, y + sa * reach - ca * half),
                (x + ca * 0 + sa * half, y + sa * 0 - ca * half)]

    outer = corners(length)
    inner = corners(length * min(1.0, progress))
    left = int(min(p[0] for p in outer)) - 3
    top = int(min(p[1] for p in outer)) - 3
    w = int(max(p[0] for p in outer)) - left + 6
    h = int(max(p[1] for p in outer)) - top + 6
    layer = pygame.Surface((max(2, w), max(2, h)), pygame.SRCALPHA)
    shift = lambda pts: [(px - left, py - top) for px, py in pts]      # noqa: E731
    pygame.draw.polygon(layer, color + (45,), shift(outer))
    pygame.draw.polygon(layer, color + (120,), shift(inner))
    pygame.draw.polygon(layer, color + (230,), shift(outer), 2)
    surface.blit(layer, (left, top))
