"""
viewer.py - Look at generated maps.

Run (from the repo root):
    python src/maps/dev/viewer.py            random world
    python src/maps/dev/viewer.py 1234       a specific seed

SPACE = new random world, ESC = quit
"""
import os
import random
import sys

import pygame

MAPS_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if MAPS_DIR not in sys.path:
    sys.path.insert(0, MAPS_DIR)

from generator import generate_map, find_spawn, DEFAULT_W, DEFAULT_H  # noqa: E402
from tiles import load_tiles, draw_map, TILE_PX  # noqa: E402

SCALE = 4                                   # same 4x pixel look as the bosses
LOGICAL_W, LOGICAL_H = DEFAULT_W * TILE_PX, DEFAULT_H * TILE_PX   # 240 x 160
SCREEN_W, SCREEN_H = LOGICAL_W * SCALE, LOGICAL_H * SCALE         # 960 x 640


def main():
    pygame.init()
    screen = pygame.display.set_mode((SCREEN_W, SCREEN_H))
    clock = pygame.time.Clock()
    canvas = pygame.Surface((LOGICAL_W, LOGICAL_H))
    tiles = load_tiles()

    seed = int(sys.argv[1]) if len(sys.argv) > 1 else random.randint(0, 999999)
    world = generate_map(seed)

    running = True
    while running:
        pygame.display.set_caption(f"Map viewer - seed {seed} - SPACE: new world")
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    running = False
                elif event.key == pygame.K_SPACE:
                    seed = random.randint(0, 999999)
                    world = generate_map(seed)

        draw_map(canvas, world, tiles)
        spawn = find_spawn(world)
        if spawn:                           # little red marker where a player would start
            pygame.draw.rect(canvas, (220, 40, 40),
                             (spawn[0] * TILE_PX + 2, spawn[1] * TILE_PX + 2, 4, 4))
        pygame.transform.scale(canvas, (SCREEN_W, SCREEN_H), screen)   # crisp, no blur
        pygame.display.flip()
        clock.tick(30)

    pygame.quit()


if __name__ == "__main__":
    main()
