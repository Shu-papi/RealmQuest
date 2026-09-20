"""drain_circle.py - The Lich King's life-drain ground circle (warning, then burst)."""
import math
import pygame

from ..attacks import player_pos


class DrainCircle:
    """
    A circle on the ground. It shows a warning for `duration` seconds,
    then bursts. If the player is still inside, they take damage.
    """
    BURST_TIME = 0.3

    def __init__(self, x, y, radius, duration, damage):
        self.x = float(x)
        self.y = float(y)
        self.radius = radius
        self.duration = duration
        self.damage = damage
        self.timer = 0.0
        self.state = "warning"   # warning -> burst -> done

    @property
    def alive(self):
        return self.state != "done"

    def update(self, dt, player):
        """Returns True on the frame the circle bursts and actually hurts the player."""
        self.timer += dt
        if self.state == "warning" and self.timer >= self.duration:
            self.state = "burst"
            self.timer = 0.0
            px, py = player_pos(player)
            if math.hypot(px - self.x, py - self.y) <= self.radius:
                dealt = player.take_damage(self.damage)
                # Some player classes return nothing; treat that as "was hit"
                return dealt is None or dealt > 0
        elif self.state == "burst" and self.timer >= self.BURST_TIME:
            self.state = "done"
        return False

    def draw(self, surface):
        r = int(self.radius)
        size = r * 2 + 4
        layer = pygame.Surface((size, size), pygame.SRCALPHA)
        center = (r + 2, r + 2)
        if self.state == "warning":
            progress = min(1.0, self.timer / self.duration)
            pygame.draw.circle(layer, (83, 74, 183, 70), center, r)
            pygame.draw.circle(layer, (127, 119, 221, 120), center, max(2, int(r * progress)))
            pygame.draw.circle(layer, (175, 169, 236, 230), center, r, 3)
        else:
            fade = max(0.0, 1.0 - self.timer / self.BURST_TIME)
            pygame.draw.circle(layer, (206, 203, 246, int(200 * fade)), center, r)
        surface.blit(layer, (int(self.x) - r - 2, int(self.y) - r - 2))
