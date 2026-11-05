"""
attacks.py - Projectiles that monsters shoot. Each needs only:
    player.rect              (a pygame.Rect: we read centerx, centery, width, height)
    player.take_damage(n)
"""
import math

import pygame

from .sprites import glow_color


def player_pos(player):
    return player.rect.centerx, player.rect.centery


def player_radius(player):
    return min(player.rect.width, player.rect.height) / 2


class _Projectile:
    """Shared flight + hit logic."""

    def __init__(self, x, y, angle, speed, damage, radius):
        self.x = float(x)
        self.y = float(y)
        self.angle = angle
        self.vx = math.cos(angle) * speed
        self.vy = math.sin(angle) * speed
        self.damage = damage
        self.radius = radius
        self.alive = True
        self.age = 0.0
        self.trail = []

    def update(self, dt, player, bounds):
        self.age += dt
        self.trail.append((self.x, self.y))
        self.trail = self.trail[-5:]
        self.x += self.vx * dt
        self.y += self.vy * dt
        left, top, right, bottom = bounds
        if (self.x < left - 40 or self.x > right + 40
                or self.y < top - 40 or self.y > bottom + 40):
            self.alive = False
            return
        px, py = player_pos(player)
        if math.hypot(px - self.x, py - self.y) <= self.radius + player_radius(player):
            player.take_damage(self.damage)
            self.alive = False


class Arrow(_Projectile):
    """A bone-tipped arrow with a ghostly glowing head and a short afterimage trail."""

    def __init__(self, x, y, angle, speed=600, damage=9, variant="bone"):
        super().__init__(x, y, angle, speed, damage, radius=6)
        self.variant = variant

    def draw(self, surface):
        glow = glow_color(self.variant, "eye", 4)
        for i, (tx, ty) in enumerate(self.trail):
            s = 2 + (i // 2)
            pygame.draw.rect(surface, glow_color(self.variant, "eye", 1),
                             (int(tx) // 2 * 2, int(ty) // 2 * 2, s, s))
        ca, sa = math.cos(self.angle), math.sin(self.angle)
        tail = (int(self.x - ca * 16), int(self.y - sa * 16))
        neck = (int(self.x + ca * 6), int(self.y + sa * 6))
        tip = (int(self.x + ca * 11), int(self.y + sa * 11))
        pygame.draw.line(surface, (128, 92, 60), tail, neck, 3)
        pygame.draw.line(surface, (80, 58, 44), (tail[0], tail[1] + 1), (neck[0], neck[1] + 1), 1)
        # red fletching
        for off in (-3, 3):
            pygame.draw.line(surface, (214, 70, 80), tail,
                             (int(tail[0] + ca * 5 - sa * off), int(tail[1] + sa * 5 + ca * off)), 2)
        # head
        pygame.draw.line(surface, (170, 172, 205), neck, tip, 4)
        pygame.draw.rect(surface, glow, (tip[0] - 2, tip[1] - 2, 4, 4))


class SoulBolt(_Projectile):
    """A slow, glowing orb of dark magic."""

    def __init__(self, x, y, angle, speed=400, damage=10, variant="bone"):
        super().__init__(x, y, angle, speed, damage, radius=9)
        self.variant = variant

    def draw(self, surface):
        for i, (tx, ty) in enumerate(self.trail):
            r = 2 + i
            pygame.draw.circle(surface, glow_color(self.variant, "glow", 1), (int(tx), int(ty)), r)
        pos = (int(self.x), int(self.y))
        pulse = 1 if int(self.age * 14) % 2 == 0 else 0
        pygame.draw.circle(surface, glow_color(self.variant, "glow", 0), pos, self.radius + 3 + pulse)
        pygame.draw.circle(surface, glow_color(self.variant, "glow", 3), pos, self.radius)
        pygame.draw.circle(surface, glow_color(self.variant, "glow", 5), pos, max(2, self.radius // 2))
