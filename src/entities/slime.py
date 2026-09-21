import os
import pygame
from src import settings as s
from src.utils import load_image, distance, normalize


class Slime:
    """Basic dungeon enemy. Has a small stylish healthbar above its head."""

    def __init__(self, x, y):
        self.pos = pygame.Vector2(x, y)
        self.radius = 16
        self.speed = s.SLIME_SPEED
        self.max_health = s.SLIME_MAX_HEALTH
        self.health = self.max_health
        self.alive = True
        self.contact_cooldown = 0.0
        self.hop_timer = 0.0
        self.hop_offset = 0.0

        size = (40, 40)
        self.sprite_idle = load_image(
            os.path.join(s.SLIME_SPRITE_DIR, "slime_idle.png"), size,
            fallback_color=s.BLUE, fallback_shape="circle")
        self.sprite_attack = load_image(
            os.path.join(s.SLIME_SPRITE_DIR, "slime_attack.png"), size,
            fallback_color=(140, 170, 255), fallback_shape="circle")

    def update(self, dt, player):
        if not self.alive:
            return
        # simple bobbing hop animation
        import math
        self.hop_timer += dt
        self.hop_offset = math.sin(self.hop_timer * 6) * 3

        d = distance((self.pos.x, self.pos.y), (player.pos.x, player.pos.y))
        if d < s.SLIME_AGGRO_RANGE and d > 2:
            direction = normalize((player.pos.x - self.pos.x, player.pos.y - self.pos.y))
            self.pos.x += direction[0] * self.speed * dt
            self.pos.y += direction[1] * self.speed * dt

        if self.contact_cooldown > 0:
            self.contact_cooldown -= dt

        # contact damage to player
        if d < self.radius + player.radius and self.contact_cooldown <= 0:
            player.take_damage(s.SLIME_CONTACT_DAMAGE)
            self.contact_cooldown = s.SLIME_CONTACT_COOLDOWN

    def take_damage(self, amount):
        self.health -= amount
        if self.health <= 0:
            self.health = 0
            self.alive = False

    def draw(self, surface):
        sprite = self.sprite_attack if self.contact_cooldown > 0.4 else self.sprite_idle
        rect = sprite.get_rect(center=(int(self.pos.x), int(self.pos.y - self.hop_offset)))
        surface.blit(sprite, rect)
        from src.ui.bars import draw_mini_healthbar
        draw_mini_healthbar(surface, int(self.pos.x), int(self.pos.y - self.radius - 14 - self.hop_offset),
                             self.health, self.max_health)
