import pygame
from src import settings as s
from src.scenes.hub import HubScene
from src.scenes.dungeon import DungeonScene


class Game:
    def __init__(self):
        self.screen = pygame.display.set_mode((s.SCREEN_WIDTH, s.SCREEN_HEIGHT))
        pygame.display.set_caption(s.TITLE)
        self.clock = pygame.time.Clock()
        self.running = True
        self.scene = HubScene(self)

    def start_dungeon(self):
        self.scene = DungeonScene(self)

    def start_hub(self):
        self.scene = HubScene(self)

    def run(self):
        while self.running:
            dt = self.clock.tick(s.FPS) / 1000.0
            self._handle_events()
            self.scene.update(dt)
            self.scene.draw(self.screen)
            pygame.display.flip()
        pygame.quit()

    def _handle_events(self):
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False
            elif event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                self.running = False
            else:
                self.scene.handle_event(event)
