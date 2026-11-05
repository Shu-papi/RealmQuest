"""STAND-IN (rebuilt so the partial PR runs on its own): shared attack pieces. Keep your real one if you have it."""
import math

import pygame


def player_pos(player):
    """Where the player is: x / y if it has them, otherwise the centre of its rect."""
    if hasattr(player, "x") and hasattr(player, "y"):
        return float(player.x), float(player.y)
    return tuple(float(v) for v in player.rect.center)


def player_radius(player):
    """How big the player's hit circle is."""
    radius = getattr(player, "radius", None)
    if radius is not None:
        return radius
    return player.rect.width / 2 if hasattr(player, "rect") else 14


class Projectile:
    """A ball that flies in a straight line, hurts the player once if it touches them, and vanishes at a wall."""

    def __init__(self, x, y, angle, speed, damage, radius=8, color=(255, 150, 60)):
        self.x, self.y = float(x), float(y)
        self.angle = angle
        self.speed = speed
        self.damage = damage
        self.radius = radius
        self.color = color
        self.alive = True

    def update(self, dt, player, bounds):
        self.x += math.cos(self.angle) * self.speed * dt
        self.y += math.sin(self.angle) * self.speed * dt
        px, py = player_pos(player)
        if math.hypot(px - self.x, py - self.y) <= self.radius + player_radius(player):
            player.take_damage(self.damage)
            self.alive = False
        left, top, right, bottom = bounds
        if not (left - 40 <= self.x <= right + 40 and top - 40 <= self.y <= bottom + 40):
            self.alive = False

    def draw(self, surface):
        pygame.draw.circle(surface, self.color, (int(self.x), int(self.y)), int(self.radius))
