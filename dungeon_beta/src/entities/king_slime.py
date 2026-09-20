import os
import math
import pygame
from src import settings as s
from src.utils import load_image, distance, normalize


class KingSlime:
    """
    Boss enemy: bigger than a regular slime, wears a crown, and has its
    own telegraphed jump-slam attack instead of simple contact damage.
    Its healthbar is drawn full-width at the bottom of the screen.
    """

    def __init__(self, x, y):
        self.pos = pygame.Vector2(x, y)
        self.radius = 46
        self.speed = s.KING_SLIME_SPEED
        self.max_health = s.KING_SLIME_MAX_HEALTH
        self.health = self.max_health
        self.alive = True
        self.name = "King Slime"

        # State machine: "chase" -> "telegraph" -> "jump" -> "land" -> "chase"
        self.state = "chase"
        self.state_timer = 0.0
        self.jump_cooldown = 1.5
        self.jump_target = pygame.Vector2(x, y)
        self.start_pos = pygame.Vector2(x, y)
        self.contact_cooldown = 0.0
        self.hop_timer = 0.0

        size = (110, 110)
        self.sprite_idle = load_image(
            os.path.join(s.KING_SLIME_SPRITE_DIR, "king_slime_idle.png"), size,
            fallback_color=(60, 90, 200), fallback_shape="circle")
        self.sprite_telegraph = load_image(
            os.path.join(s.KING_SLIME_SPRITE_DIR, "king_slime_telegraph.png"), size,
            fallback_color=(200, 60, 60), fallback_shape="circle")
        self.sprite_jump = load_image(
            os.path.join(s.KING_SLIME_SPRITE_DIR, "king_slime_jump.png"), size,
            fallback_color=(90, 130, 255), fallback_shape="circle")
        self.sprite_attack = load_image(
            os.path.join(s.KING_SLIME_SPRITE_DIR, "king_slime_attack.png"), (140, 140),
            fallback_color=(230, 90, 90), fallback_shape="circle")

    def update(self, dt, player):
        if not self.alive:
            return
        self.hop_timer += dt

        if self.contact_cooldown > 0:
            self.contact_cooldown -= dt

        if self.state == "chase":
            d = distance((self.pos.x, self.pos.y), (player.pos.x, player.pos.y))
            if d > 4:
                direction = normalize((player.pos.x - self.pos.x, player.pos.y - self.pos.y))
                self.pos.x += direction[0] * self.speed * dt
                self.pos.y += direction[1] * self.speed * dt
            if d < self.radius + player.radius and self.contact_cooldown <= 0:
                player.take_damage(s.KING_SLIME_CONTACT_DAMAGE)
                self.contact_cooldown = 0.8

            self.jump_cooldown -= dt
            if self.jump_cooldown <= 0:
                self.state = "telegraph"
                self.state_timer = s.KING_SLIME_JUMP_TELEGRAPH
                self.jump_target = pygame.Vector2(player.pos.x, player.pos.y)
                self.start_pos = pygame.Vector2(self.pos.x, self.pos.y)

        elif self.state == "telegraph":
            # unique wind-up: crouches and flashes red before leaping
            self.state_timer -= dt
            if self.state_timer <= 0:
                self.state = "jump"
                self.state_timer = 0.4

        elif self.state == "jump":
            # unique jumping animation: arcs toward the last known player position
            self.state_timer -= dt
            t = 1 - max(0.0, self.state_timer / 0.4)
            self.pos.x = self.start_pos.x + (self.jump_target.x - self.start_pos.x) * t
            self.pos.y = self.start_pos.y + (self.jump_target.y - self.start_pos.y) * t
            if self.state_timer <= 0:
                self.state = "land"
                self.state_timer = 0.25
                d = distance((self.pos.x, self.pos.y), (player.pos.x, player.pos.y))
                if d < s.KING_SLIME_JUMP_RADIUS:
                    player.take_damage(s.KING_SLIME_JUMP_DAMAGE)

        elif self.state == "land":
            # unique slam/attack animation on impact
            self.state_timer -= dt
            if self.state_timer <= 0:
                self.state = "chase"
                self.jump_cooldown = s.KING_SLIME_JUMP_COOLDOWN

        self._clamp_to_bounds()

    def _clamp_to_bounds(self):
        self.pos.x = max(self.radius, min(s.SCREEN_WIDTH - self.radius, self.pos.x))
        self.pos.y = max(self.radius, min(s.SCREEN_HEIGHT - self.radius, self.pos.y))

    def take_damage(self, amount):
        self.health -= amount
        if self.health <= 0:
            self.health = 0
            self.alive = False

    def draw(self, surface):
        bob = math.sin(self.hop_timer * 4) * 3 if self.state == "chase" else 0
        if self.state == "telegraph":
            sprite = self.sprite_telegraph
        elif self.state == "jump":
            sprite = self.sprite_jump
        elif self.state == "land":
            sprite = self.sprite_attack
        else:
            sprite = self.sprite_idle

        rect = sprite.get_rect(center=(int(self.pos.x), int(self.pos.y - bob)))
        surface.blit(sprite, rect)

        if self.state == "telegraph" and int(self.state_timer * 20) % 2 == 0:
            ring = pygame.Surface((s.KING_SLIME_JUMP_RADIUS * 2, s.KING_SLIME_JUMP_RADIUS * 2), pygame.SRCALPHA)
            pygame.draw.circle(ring, (255, 60, 60, 90), (s.KING_SLIME_JUMP_RADIUS, s.KING_SLIME_JUMP_RADIUS),
                                s.KING_SLIME_JUMP_RADIUS)
            surface.blit(ring, (self.jump_target.x - s.KING_SLIME_JUMP_RADIUS,
                                 self.jump_target.y - s.KING_SLIME_JUMP_RADIUS))

    def draw_healthbar(self, surface):
        from src.ui.bars import draw_boss_healthbar
        draw_boss_healthbar(surface, self.name, self.health, self.max_health)
