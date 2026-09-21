"""
attacks.py - Generic attacks ANY boss can use (boss-specific ones live in the boss's folder).

Every attack only needs two things from the player:
    player.rect          (a pygame.Rect: we read centerx, centery, width, height)
    player.take_damage(amount)
"""
import math
import pygame


def player_pos(player):
    return player.rect.centerx, player.rect.centery


def player_radius(player):
    return min(player.rect.width, player.rect.height) / 2


class Projectile:
    """A glowing bolt that flies in a straight line."""

    def __init__(self, x, y, angle, speed, damage, radius=8, color=(175, 169, 236)):
        self.x = float(x)
        self.y = float(y)
        self.vx = math.cos(angle) * speed
        self.vy = math.sin(angle) * speed
        self.damage = damage
        self.radius = radius
        self.color = color
        self.alive = True

    def update(self, dt, player, bounds):
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

    def draw(self, surface):
        pos = (int(self.x), int(self.y))
        pygame.draw.circle(surface, (83, 74, 183), pos, self.radius + 3)
        pygame.draw.circle(surface, self.color, pos, self.radius)
        pygame.draw.circle(surface, (238, 237, 254), pos, max(2, self.radius // 3))
