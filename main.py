"""
Dungeon Beta - entry point.

Controls:
  WASD          move
  Left Click    slash (hold to charge a stronger slash, release to swing)
  Space         dash
  Q             special ability (AoE slash, meter fills by landing hits)
  F             interact / talk (used on the Spirit in the hub)
  ESC           quit
"""
import pygame
from src.scenes.game import Game


def main():
    pygame.init()
    pygame.mixer.init()
    game = Game()
    game.run()


if __name__ == "__main__":
    main()
