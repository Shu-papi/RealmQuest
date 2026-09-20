"""minions.py - The Lich King's skeleton minions."""
import math
import pygame


class Skeleton:
    """Chases the player and hurts on contact. Dies in one sword hit."""
    SPAWN_TIME = 0.8

    def __init__(self, x, y):
        self.x = float(x)
        self.y = float(y)
        self.radius = 14
        self.max_hp = 20
        self.hp = 20
        self.speed = 95
        self.damage = 8
        self.contact_cd = 0.0
        self.spawn_timer = self.SPAWN_TIME
        self.hit_flash = 0.0
        self.clock = 0.0

    def is_alive(self):
        return self.hp > 0

    @property
    def spawning(self):
        return self.spawn_timer > 0

    def take_damage(self, amount):
        if self.spawning or not self.is_alive():
            return 0
        self.hp = max(0, self.hp - amount)
        self.hit_flash = 0.1
        return amount

    def update(self, dt, player, bounds):
        self.clock += dt
        self.hit_flash = max(0.0, self.hit_flash - dt)
        self.contact_cd = max(0.0, self.contact_cd - dt)

        if self.spawning:
            self.spawn_timer -= dt
            return

        px, py = player.rect.centerx, player.rect.centery
        dx, dy = px - self.x, py - self.y
        dist = math.hypot(dx, dy)
        touch = self.radius + min(player.rect.width, player.rect.height) / 2

        if dist > touch - 2 and dist > 0:
            step = self.speed * dt
            self.x += dx / dist * step
            self.y += dy / dist * step

        if dist <= touch and self.contact_cd <= 0:
            player.take_damage(self.damage)
            self.contact_cd = 1.0

        left, top, right, bottom = bounds
        self.x = max(left + self.radius, min(right - self.radius, self.x))
        self.y = max(top + self.radius, min(bottom - self.radius, self.y))

    def draw(self, surface):
        cx, cy = int(self.x), int(self.y)
        if self.spawning:
            ring = int(10 + 8 * (self.spawn_timer / self.SPAWN_TIME))
            pygame.draw.circle(surface, (127, 119, 221), (cx, cy), ring, 2)
            return

        bone = (255, 255, 255) if self.hit_flash > 0 else (222, 218, 204)
        dark = (33, 29, 46)
        pygame.draw.ellipse(surface, (18, 15, 28), (cx - 12, cy + 8, 24, 8))
        pygame.draw.rect(surface, bone, (cx - 6, cy - 2, 12, 14))
        pygame.draw.line(surface, dark, (cx - 6, cy + 3), (cx + 6, cy + 3), 2)
        pygame.draw.line(surface, dark, (cx - 6, cy + 7), (cx + 6, cy + 7), 2)
        pygame.draw.line(surface, bone, (cx - 6, cy), (cx - 14, cy + 8), 3)
        pygame.draw.line(surface, bone, (cx + 6, cy), (cx + 14, cy + 8), 3)
        pygame.draw.circle(surface, bone, (cx, cy - 9), 9)
        pygame.draw.circle(surface, dark, (cx - 3, cy - 10), 3)
        pygame.draw.circle(surface, dark, (cx + 3, cy - 10), 3)
        pygame.draw.circle(surface, (93, 202, 165), (cx - 3, cy - 10), 1)
        pygame.draw.circle(surface, (93, 202, 165), (cx + 3, cy - 10), 1)
