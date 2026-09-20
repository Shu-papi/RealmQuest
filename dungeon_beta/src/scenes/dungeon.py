import os
import pygame
from src import settings as s
from src.entities.player import Knight
from src.entities.slime import Slime
from src.entities.king_slime import KingSlime
from src.ui.bars import draw_player_hud
from src.utils import load_image, distance


class DungeonScene:
    ROOM_SLIMES = "room_slimes"
    ROOM_BOSS = "room_boss"
    ROOM_END = "room_end"

    def __init__(self, game):
        self.game = game
        self.player = Knight(120, s.SCREEN_HEIGHT // 2)
        self.font = pygame.font.Font(None, 28)
        self.big_font = pygame.font.Font(None, 48)

        self.floor_img = load_image(
            os.path.join(s.DUNGEON_MAP_DIR, "dungeon_floor.png"), (s.SCREEN_WIDTH, s.SCREEN_HEIGHT),
            fallback_color=s.FLOOR_COLOR)
        self.portal_img = load_image(
            os.path.join(s.DUNGEON_MAP_DIR, "portal.png"), (70, 70),
            fallback_color=s.PURPLE, fallback_shape="circle")

        self.room = self.ROOM_SLIMES
        self.slimes = self._spawn_slimes()
        self.boss = None
        self.portal_pos = pygame.Vector2(s.SCREEN_WIDTH - 100, s.SCREEN_HEIGHT // 2)
        self.portal_active = False

        # simple wall border so rooms feel enclosed
        self.walls = [
            pygame.Rect(0, 0, s.SCREEN_WIDTH, 12),
            pygame.Rect(0, s.SCREEN_HEIGHT - 12, s.SCREEN_WIDTH, 12),
            pygame.Rect(0, 0, 12, s.SCREEN_HEIGHT),
            pygame.Rect(s.SCREEN_WIDTH - 12, 0, 12, s.SCREEN_HEIGHT),
        ]

    def _spawn_slimes(self):
        positions = [
            (500, 200), (700, 220), (600, 450), (800, 500),
        ]
        return [Slime(x, y) for x, y in positions]

    # ------------------------------------------------------------- helpers
    def _enemies_hit_callback(self, center, radius, damage, on_hit=None):
        hit_any = False
        targets = self.slimes if self.room == self.ROOM_SLIMES else ([self.boss] if self.boss else [])
        for enemy in targets:
            if not enemy.alive:
                continue
            if distance((center[0], center[1]), (enemy.pos.x, enemy.pos.y)) <= radius + enemy.radius:
                enemy.take_damage(damage)
                hit_any = True
        if hit_any and on_hit:
            on_hit()

    def _advance_to_boss_room(self):
        self.room = self.ROOM_BOSS
        self.player.pos.update(120, s.SCREEN_HEIGHT // 2)
        self.boss = KingSlime(s.SCREEN_WIDTH - 220, s.SCREEN_HEIGHT // 2)

    # --------------------------------------------------------------- input
    def handle_event(self, event):
        mouse_world = pygame.mouse.get_pos()
        if self.room != self.ROOM_END:
            self.player.handle_event(event, mouse_world, self._enemies_hit_callback)

    # -------------------------------------------------------------- update
    def update(self, dt):
        keys = pygame.key.get_pressed()

        if self.room == self.ROOM_END:
            return

        self.player.update(dt, keys, walls=self.walls)

        if self.room == self.ROOM_SLIMES:
            self.slimes = [sl for sl in self.slimes if sl.alive or True]
            for slime in self.slimes:
                slime.update(dt, self.player)
            self.slimes = [sl for sl in self.slimes if sl.alive]
            if len(self.slimes) == 0:
                self._advance_to_boss_room()

        elif self.room == self.ROOM_BOSS:
            if self.boss and self.boss.alive:
                self.boss.update(dt, self.player)
            elif self.boss and not self.boss.alive:
                self.portal_active = True
                if distance((self.player.pos.x, self.player.pos.y),
                             (self.portal_pos.x, self.portal_pos.y)) < 40:
                    self.room = self.ROOM_END

        if not self.player.alive:
            # simple beta behavior: respawn at room start with half health
            self.player.alive = True
            self.player.health = self.player.max_health // 2
            self.player.pos.update(120, s.SCREEN_HEIGHT // 2)

    # ---------------------------------------------------------------- draw
    def draw(self, surface):
        surface.blit(self.floor_img, (0, 0))
        for wall in self.walls:
            pygame.draw.rect(surface, s.WALL_COLOR, wall)

        if self.room == self.ROOM_END:
            self._draw_end_screen(surface)
            return

        if self.room == self.ROOM_SLIMES:
            for slime in self.slimes:
                slime.draw(surface)
            remaining = self.font.render(f"Slimes remaining: {len(self.slimes)}", True, s.WHITE)
            surface.blit(remaining, (s.SCREEN_WIDTH // 2 - remaining.get_width() // 2, 20))

        elif self.room == self.ROOM_BOSS:
            if self.boss and self.boss.alive:
                self.boss.draw(surface)
                self.boss.draw_healthbar(surface)
            elif self.portal_active:
                surface.blit(self.portal_img,
                             self.portal_img.get_rect(center=(int(self.portal_pos.x), int(self.portal_pos.y))))
                label = self.font.render("Portal open - walk in to continue", True, s.GOLD)
                surface.blit(label, (self.portal_pos.x - label.get_width() // 2, self.portal_pos.y - 60))

        self.player.draw(surface)
        draw_player_hud(surface, self.player)

    def _draw_end_screen(self, surface):
        overlay = pygame.Surface((s.SCREEN_WIDTH, s.SCREEN_HEIGHT), pygame.SRCALPHA)
        overlay.fill((10, 10, 15, 230))
        surface.blit(overlay, (0, 0))

        title = self.big_font.render("Thanks for playing the beta!", True, s.GOLD)
        surface.blit(title, (s.SCREEN_WIDTH // 2 - title.get_width() // 2, s.SCREEN_HEIGHT // 2 - 60))

        sub = self.font.render("Dungeon 2 and more classes are on the way. See you next update!",
                                True, s.WHITE)
        surface.blit(sub, (s.SCREEN_WIDTH // 2 - sub.get_width() // 2, s.SCREEN_HEIGHT // 2))

        hint = self.font.render("Press ESC to quit", True, s.LIGHT_GREY)
        surface.blit(hint, (s.SCREEN_WIDTH // 2 - hint.get_width() // 2, s.SCREEN_HEIGHT // 2 + 60))
