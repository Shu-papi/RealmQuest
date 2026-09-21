import os
import math
import pygame
from src import settings as s
from src.utils import load_image, distance


class Spirit:
    """
    The hub's only NPC. Press F near it to talk. It asks whether the
    player wants to enter the dungeon (Y) or stay in the hub for now (N).
    """

    INTERACT_RANGE = 90

    def __init__(self, x, y):
        self.pos = pygame.Vector2(x, y)
        self.radius = 22
        self.dialogue_open = False
        self.timer = 0.0

        size = (56, 56)
        self.sprite = load_image(
            os.path.join(s.HUB_MAP_DIR, "spirit.png"), size,
            fallback_color=(180, 220, 255), fallback_shape="circle")

    def player_in_range(self, player):
        return distance((self.pos.x, self.pos.y), (player.pos.x, player.pos.y)) < self.INTERACT_RANGE

    def update(self, dt):
        self.timer += dt

    def draw(self, surface, font):
        bob = math.sin(self.timer * 2) * 5
        alpha_surf = self.sprite.copy()
        alpha_surf.set_alpha(220)
        rect = alpha_surf.get_rect(center=(int(self.pos.x), int(self.pos.y - bob)))
        surface.blit(alpha_surf, rect)

        if self.dialogue_open:
            self._draw_dialogue(surface, font)

    def _draw_dialogue(self, surface, font):
        box_w, box_h = 520, 130
        x = s.SCREEN_WIDTH // 2 - box_w // 2
        y = s.SCREEN_HEIGHT - box_h - 40
        box = pygame.Surface((box_w, box_h), pygame.SRCALPHA)
        pygame.draw.rect(box, (15, 15, 25, 230), (0, 0, box_w, box_h), border_radius=12)
        pygame.draw.rect(box, s.GOLD, (0, 0, box_w, box_h), width=2, border_radius=12)
        surface.blit(box, (x, y))

        lines = [
            "Spirit: Traveler... do you wish to enter the dungeon",
            "and begin your journey?",
        ]
        for i, line in enumerate(lines):
            text = font.render(line, True, s.WHITE)
            surface.blit(text, (x + 24, y + 18 + i * 26))

        opt_font = pygame.font.Font(None, 24)
        opt1 = opt_font.render("[Y] Enter the dungeon", True, s.GREEN)
        opt2 = opt_font.render("[N] Stay in the hub", True, s.LIGHT_GREY)
        surface.blit(opt1, (x + 24, y + 80))
        surface.blit(opt2, (x + 260, y + 80))
