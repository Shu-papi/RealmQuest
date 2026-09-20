import os
import pygame
from src import settings as s
from src.entities.player import Knight
from src.entities.spirit import Spirit
from src.ui.bars import draw_player_hud
from src.utils import load_image


class ClassButton:
    def __init__(self, name, x, y, unlocked):
        self.name = name
        self.rect = pygame.Rect(x, y, 96, 96)
        self.unlocked = unlocked


class HubScene:
    def __init__(self, game):
        self.game = game
        self.player = Knight(s.SCREEN_WIDTH // 2, s.SCREEN_HEIGHT // 2 + 80)
        self.spirit = Spirit(s.SCREEN_WIDTH // 2, 220)
        self.font = pygame.font.Font(None, 26)
        self.small_font = pygame.font.Font(None, 20)

        self.class_buttons = [
            ClassButton("Knight", s.SCREEN_WIDTH // 2 - 160, 40, True),
            ClassButton("Archer", s.SCREEN_WIDTH // 2 - 48, 40, False),
            ClassButton("Mage", s.SCREEN_WIDTH // 2 + 64, 40, False),
        ]
        self.selected_class = "Knight"  # defaults to Knight on arrival

        self.bg = load_image(
            os.path.join(s.HUB_MAP_DIR, "hub_floor.png"), (s.SCREEN_WIDTH, s.SCREEN_HEIGHT),
            fallback_color=s.HUB_FLOOR_COLOR)

    def handle_event(self, event):
        mouse_world = pygame.mouse.get_pos()
        self.player.handle_event(event, mouse_world, self._noop_aoe)

        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            for btn in self.class_buttons:
                if btn.rect.collidepoint(event.pos):
                    if btn.unlocked:
                        self.selected_class = btn.name
                    # locked classes just show a "beta locked" tooltip via draw()

        if event.type == pygame.KEYDOWN:
            if event.key == s.KEY_INTERACT and self.spirit.player_in_range(self.player):
                self.spirit.dialogue_open = not self.spirit.dialogue_open

            if self.spirit.dialogue_open:
                if event.key == pygame.K_y:
                    self.spirit.dialogue_open = False
                    self.game.start_dungeon()
                elif event.key == pygame.K_n:
                    self.spirit.dialogue_open = False

    def _noop_aoe(self, *args, **kwargs):
        # In the hub there's nothing to hit; the knight can still practice
        # his moves, but no enemies_hit_callback logic is needed here.
        pass

    def update(self, dt):
        keys = pygame.key.get_pressed()
        if not self.spirit.dialogue_open:
            self.player.update(dt, keys)
        self.spirit.update(dt)

    def draw(self, surface):
        surface.blit(self.bg, (0, 0))

        # class select panel
        for btn in self.class_buttons:
            color = s.GOLD if btn.name == self.selected_class else s.GREY
            pygame.draw.rect(surface, (25, 25, 30), btn.rect, border_radius=10)
            pygame.draw.rect(surface, color, btn.rect, width=3, border_radius=10)
            label = self.small_font.render(btn.name, True, s.WHITE)
            surface.blit(label, (btn.rect.centerx - label.get_width() // 2, btn.rect.bottom + 4))
            if not btn.unlocked:
                lock_label = self.small_font.render("Beta locked", True, s.LIGHT_GREY)
                surface.blit(lock_label, (btn.rect.centerx - lock_label.get_width() // 2, btn.rect.top - 20))

        self.spirit.draw(surface, self.font)

        if self.spirit.player_in_range(self.player) and not self.spirit.dialogue_open:
            prompt = self.small_font.render("[F] Talk", True, s.WHITE)
            surface.blit(prompt, (self.spirit.pos.x - prompt.get_width() // 2, self.spirit.pos.y + 40))

        self.player.draw(surface)
        draw_player_hud(surface, self.player)

        title = self.font.render("Hub - Select a class, then talk to the Spirit (F) to enter the dungeon",
                                  True, s.WHITE)
        surface.blit(title, (s.SCREEN_WIDTH // 2 - title.get_width() // 2, s.SCREEN_HEIGHT - 34))
