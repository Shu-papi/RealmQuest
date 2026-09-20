import pygame
import os
from src import settings as s
from src.utils import load_image, normalize, distance


class Knight:
    """The melee class: slash, hold-to-charge slash, dash, and an AoE special (Q)."""

    def __init__(self, x, y):
        self.pos = pygame.Vector2(x, y)
        self.radius = 18
        self.speed = s.KNIGHT_SPEED
        self.facing = pygame.Vector2(0, 1)

        self.max_health = s.KNIGHT_MAX_HEALTH
        self.health = self.max_health
        self.alive = True

        # Attack state
        self.attack_cooldown_timer = 0.0
        self.is_charging = False
        self.charge_time = 0.0
        self.active_hit = None  # (rect_center, radius, damage) shown for a couple frames
        self.hit_flash_timer = 0.0

        # Dash state
        self.is_dashing = False
        self.dash_timer = 0.0
        self.dash_cooldown_timer = 0.0
        self.dash_direction = pygame.Vector2(0, 0)
        self.invulnerable = False

        # Ability (Q) state
        self.ability_meter = 0.0
        self.ability_active_timer = 0.0

        self.damage_flash_timer = 0.0

        # ---- Sprites (drop your own files with these exact names) ----
        size = (48, 48)
        self.sprite_idle = load_image(
            os.path.join(s.KNIGHT_SPRITE_DIR, "knight_idle.png"), size,
            fallback_color=(90, 110, 150), fallback_shape="circle")
        self.sprite_walk = load_image(
            os.path.join(s.KNIGHT_SPRITE_DIR, "knight_walk.png"), size,
            fallback_color=(90, 110, 150), fallback_shape="circle")
        self.sprite_slash = load_image(
            os.path.join(s.KNIGHT_SPRITE_DIR, "knight_slash.png"), size,
            fallback_color=(150, 150, 200), fallback_shape="circle")
        self.sprite_sword = load_image(
            os.path.join(s.KNIGHT_SPRITE_DIR, "sword.png"), (40, 10),
            fallback_color=s.LIGHT_GREY)

    # ---------------------------------------------------------------- input
    def handle_event(self, event, mouse_world_pos, enemies_hit_callback):
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == s.MOUSE_ATTACK_BUTTON:
            if self.attack_cooldown_timer <= 0 and not self.is_dashing:
                self.is_charging = True
                self.charge_time = 0.0

        elif event.type == pygame.MOUSEBUTTONUP and event.button == s.MOUSE_ATTACK_BUTTON:
            if self.is_charging:
                self._release_slash(mouse_world_pos, enemies_hit_callback)
            self.is_charging = False

        elif event.type == pygame.KEYDOWN and event.key == s.KEY_DASH:
            self._try_dash()

        elif event.type == pygame.KEYDOWN and event.key == s.KEY_ABILITY:
            self._try_ability(enemies_hit_callback)

    def _try_dash(self):
        if self.dash_cooldown_timer <= 0 and not self.is_dashing:
            direction = self.facing.copy()
            keys = pygame.key.get_pressed()
            move = pygame.Vector2(
                (keys[s.KEY_RIGHT] - keys[s.KEY_LEFT]),
                (keys[s.KEY_DOWN] - keys[s.KEY_UP]),
            )
            if move.length_squared() > 0:
                direction = move.normalize()
            self.dash_direction = direction
            self.is_dashing = True
            self.invulnerable = True
            self.dash_timer = s.KNIGHT_DASH_TIME
            self.dash_cooldown_timer = s.KNIGHT_DASH_COOLDOWN

    def _try_ability(self, enemies_hit_callback):
        if self.ability_meter >= s.KNIGHT_ABILITY_METER_MAX:
            self.ability_meter = 0.0
            self.ability_active_timer = 0.2
            self.active_hit = (self.pos.copy(), s.KNIGHT_ABILITY_RADIUS, s.KNIGHT_ABILITY_DAMAGE)
            self.hit_flash_timer = 0.2
            enemies_hit_callback(self.pos, s.KNIGHT_ABILITY_RADIUS, s.KNIGHT_ABILITY_DAMAGE, on_hit=self._on_landed_hit)

    def _release_slash(self, mouse_world_pos, enemies_hit_callback):
        charge_pct = min(1.0, self.charge_time / s.KNIGHT_CHARGE_MAX_TIME)
        damage = s.KNIGHT_CHARGE_MIN_DAMAGE + charge_pct * (
            s.KNIGHT_CHARGE_MAX_DAMAGE - s.KNIGHT_CHARGE_MIN_DAMAGE
        )
        direction = normalize((mouse_world_pos[0] - self.pos.x, mouse_world_pos[1] - self.pos.y))
        if direction != (0, 0):
            self.facing = pygame.Vector2(direction)
        hit_center = self.pos + self.facing * s.KNIGHT_ATTACK_RANGE
        self.active_hit = (hit_center, s.KNIGHT_ATTACK_RANGE * 0.7, damage)
        self.hit_flash_timer = 0.15
        self.attack_cooldown_timer = s.KNIGHT_ATTACK_COOLDOWN
        enemies_hit_callback(hit_center, s.KNIGHT_ATTACK_RANGE * 0.7, damage, on_hit=self._on_landed_hit)

    def _on_landed_hit(self):
        """Ability meter only refills by landing hits on enemies."""
        self.ability_meter = min(s.KNIGHT_ABILITY_METER_MAX, self.ability_meter + s.KNIGHT_ABILITY_METER_PER_HIT)

    # --------------------------------------------------------------- update
    def update(self, dt, keys, walls=None):
        walls = walls or []

        if self.is_charging:
            self.charge_time += dt

        if self.is_dashing:
            self.dash_timer -= dt
            self.pos += self.dash_direction * s.KNIGHT_DASH_SPEED * dt
            if self.dash_timer <= 0:
                self.is_dashing = False
                self.invulnerable = False
        else:
            move = pygame.Vector2(
                (keys[s.KEY_RIGHT] - keys[s.KEY_LEFT]),
                (keys[s.KEY_DOWN] - keys[s.KEY_UP]),
            )
            if move.length_squared() > 0:
                move = move.normalize()
                self.facing = move.copy()
                self.pos += move * self.speed * dt

        self._clamp_to_bounds()
        for wall in walls:
            self._resolve_wall_collision(wall)

        if self.attack_cooldown_timer > 0:
            self.attack_cooldown_timer -= dt
        if self.dash_cooldown_timer > 0:
            self.dash_cooldown_timer -= dt
        if self.hit_flash_timer > 0:
            self.hit_flash_timer -= dt
            if self.hit_flash_timer <= 0:
                self.active_hit = None
        if self.damage_flash_timer > 0:
            self.damage_flash_timer -= dt

    def _clamp_to_bounds(self):
        self.pos.x = max(self.radius, min(s.SCREEN_WIDTH - self.radius, self.pos.x))
        self.pos.y = max(self.radius, min(s.SCREEN_HEIGHT - self.radius, self.pos.y))

    def _resolve_wall_collision(self, wall_rect):
        player_rect = pygame.Rect(self.pos.x - self.radius, self.pos.y - self.radius,
                                   self.radius * 2, self.radius * 2)
        if player_rect.colliderect(wall_rect):
            clipped = player_rect.clip(wall_rect)
            if clipped.width < clipped.height:
                if player_rect.centerx < wall_rect.centerx:
                    self.pos.x -= clipped.width
                else:
                    self.pos.x += clipped.width
            else:
                if player_rect.centery < wall_rect.centery:
                    self.pos.y -= clipped.height
                else:
                    self.pos.y += clipped.height

    def take_damage(self, amount):
        if self.invulnerable or not self.alive:
            return
        self.health -= amount
        self.damage_flash_timer = 0.2
        if self.health <= 0:
            self.health = 0
            self.alive = False

    # ----------------------------------------------------------------- draw
    def draw(self, surface):
        sprite = self.sprite_slash if self.hit_flash_timer > 0 else (
            self.sprite_walk if pygame.key.get_pressed()[s.KEY_UP] or
            pygame.key.get_pressed()[s.KEY_DOWN] or
            pygame.key.get_pressed()[s.KEY_LEFT] or
            pygame.key.get_pressed()[s.KEY_RIGHT] else self.sprite_idle
        )
        rect = sprite.get_rect(center=(int(self.pos.x), int(self.pos.y)))
        if self.damage_flash_timer > 0 and int(self.damage_flash_timer * 30) % 2 == 0:
            tinted = sprite.copy()
            tinted.fill((255, 120, 120, 0), special_flags=pygame.BLEND_RGBA_ADD)
            surface.blit(tinted, rect)
        else:
            surface.blit(sprite, rect)

        # simple sword indicator in facing direction
        sword_pos = self.pos + self.facing * 26
        sword_rect = self.sprite_sword.get_rect(center=(int(sword_pos.x), int(sword_pos.y)))
        surface.blit(self.sprite_sword, sword_rect)

        if self.is_dashing:
            pygame.draw.circle(surface, (200, 230, 255), (int(self.pos.x), int(self.pos.y)),
                                self.radius + 6, width=2)

        if self.active_hit:
            center, radius, _dmg = self.active_hit
            hit_surf = pygame.Surface((radius * 2, radius * 2), pygame.SRCALPHA)
            pygame.draw.circle(hit_surf, (255, 255, 255, 90), (radius, radius), radius)
            surface.blit(hit_surf, (center[0] - radius, center[1] - radius))

        if self.is_charging:
            from src.ui.bars import draw_charge_bar
            charge_pct = min(1.0, self.charge_time / s.KNIGHT_CHARGE_MAX_TIME)
            draw_charge_bar(surface, int(self.pos.x), int(self.pos.y - self.radius), charge_pct)
