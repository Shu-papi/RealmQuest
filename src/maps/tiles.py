"""
tiles.py - Pixel art tiles for the map.

Each tile is TILE_PX x TILE_PX *logical* pixels (the game scales everything up
4x later, like the bosses). For now tiles are drawn from code so the map works
without any art. To use real art, drop PNGs named after the tile (water.png,
sand.png, grass.png, mountain.png) into assets/maps/ and they are used instead.
"""
import os
import random

import pygame

from generator import WATER, SAND, GRASS, MOUNTAIN

TILE_PX = 8

NAMES = {WATER: "water", SAND: "sand", GRASS: "grass", MOUNTAIN: "mountain"}

# (base colour, speckle colour)
PALETTE = {
    WATER: ((48, 96, 190), (80, 140, 225)),
    SAND: ((226, 205, 130), (196, 172, 100)),
    GRASS: ((62, 160, 72), (40, 120, 55)),
    MOUNTAIN: ((118, 118, 128), (82, 82, 92)),
}

ASSET_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "assets", "maps",
)


def _draw_tile(tile_id):
    base, speckle = PALETTE[tile_id]
    surface = pygame.Surface((TILE_PX, TILE_PX))
    surface.fill(base)
    rng = random.Random(tile_id)          # fixed, so the tile always looks the same
    for _ in range(6):
        surface.set_at((rng.randrange(TILE_PX), rng.randrange(TILE_PX)), speckle)
    return surface


def load_tiles():
    """Return {tile_id: Surface}. Uses PNGs from assets/maps/ when present."""
    tiles = {}
    for tile_id, name in NAMES.items():
        path = os.path.join(ASSET_DIR, name + ".png")
        if os.path.exists(path):
            image = pygame.image.load(path)
            tiles[tile_id] = image.convert_alpha() if pygame.display.get_surface() else image
        else:
            tiles[tile_id] = _draw_tile(tile_id)
    return tiles


def draw_map(surface, world, tiles):
    """Draw the whole map onto a (logical-resolution) surface."""
    for ty, row in enumerate(world):
        for tx, tile_id in enumerate(row):
            surface.blit(tiles[tile_id], (tx * TILE_PX, ty * TILE_PX))
