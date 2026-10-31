"""
arena.py - Fight a real boss with the Warrior, Mage or Archer.

    python src/characters/dev/arena.py                     warrior vs first boss
    python src/characters/dev/arena.py mage                 mage vs first boss
    python src/characters/dev/arena.py archer lich_king      archer vs lich_king

Controls: WASD move, mouse aim, click/Space attack, R restart, ESC quit.
Reuses bosses/dev/arena.py's Game/UI code; only the player is swapped out.
"""
import os
import sys

import pygame

SRC_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)

from bosses import get_boss, list_bosses          # noqa: E402
from bosses.dev.arena import W, H, BOUNDS, Game, read_input, BACKGROUND   # noqa: E402
from characters.player import Player, CLASS_STATS  # noqa: E402


class CharacterGame(Game):
    """Same as bosses' Game, but the player can be warrior/mage/archer."""

    def __init__(self, boss_name, char_class):
        self.char_class = char_class
        super().__init__(boss_name)

    def reset(self):
        self.player = Player(480, 520, self.char_class)
        self.boss = get_boss(self.boss_name, 480, 230)
        self.result = None


def main():
    args = sys.argv[1:]
    char_class = args[0] if args and args[0] in CLASS_STATS else "warrior"
    remaining = [a for a in args if a != char_class]
    boss_name = remaining[0] if remaining else list_bosses()[0]
    if boss_name not in list_bosses():
        print(f"Unknown boss '{boss_name}'. Choose from: {', '.join(list_bosses())}")
        return

    pygame.init()
    screen = pygame.display.set_mode((W, H))
    pygame.display.set_caption(f"RealmQuest - {char_class} vs {boss_name}")
    clock = pygame.time.Clock()
    game = CharacterGame(boss_name, char_class)

    running = True
    while running:
        dt = min(clock.tick(60) / 1000.0, 0.05)
        events = pygame.event.get()
        for e in events:
            if e.type == pygame.QUIT or (e.type == pygame.KEYDOWN and e.key == pygame.K_ESCAPE):
                running = False
        game.update(dt, read_input(events))
        game.draw(screen)
        pygame.display.flip()

    pygame.quit()


if __name__ == "__main__":
    main()
