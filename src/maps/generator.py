"""
generator.py - Procedurally generates a tile map from a seed.

A map is a list of rows. Every entry is a tile ID (a small integer).
The same seed always gives the same map.
"""
import random

WATER, SAND, GRASS, MOUNTAIN = 0, 1, 2, 3
WALKABLE = {SAND, GRASS}

DEFAULT_W, DEFAULT_H = 30, 20


def generate_map(seed, width=DEFAULT_W, height=DEFAULT_H):
    """Return a height x width grid of tile IDs."""
    rng = random.Random(seed)
    grid = [[rng.random() for _ in range(width)] for _ in range(height)]

    # Blur a few times so neighbouring tiles become similar (makes landmasses).
    for _ in range(4):
        new = [[0.0] * width for _ in range(height)]
        for y in range(height):
            for x in range(width):
                total, count = 0.0, 0
                for dy in (-1, 0, 1):
                    for dx in (-1, 0, 1):
                        nx, ny = x + dx, y + dy
                        if 0 <= nx < width and 0 <= ny < height:
                            total += grid[ny][nx]
                            count += 1
                new[y][x] = total / count
        grid = new

    # Blurring squeezes values together, so stretch them back to 0..1.
    low = min(min(row) for row in grid)
    high = max(max(row) for row in grid)
    span = (high - low) or 1.0

    world = []
    for row in grid:
        tile_row = []
        for value in row:
            v = (value - low) / span
            if v < 0.35:
                tile_row.append(WATER)
            elif v < 0.42:
                tile_row.append(SAND)
            elif v < 0.75:
                tile_row.append(GRASS)
            else:
                tile_row.append(MOUNTAIN)
        world.append(tile_row)
    return world


def is_walkable(world, tx, ty):
    """True if tile (tx, ty) exists and the player can stand on it."""
    if ty < 0 or ty >= len(world) or tx < 0 or tx >= len(world[0]):
        return False
    return world[ty][tx] in WALKABLE


def find_spawn(world):
    """Return (tx, ty) of the walkable tile closest to the map centre, or None."""
    h, w = len(world), len(world[0])
    cx, cy = w // 2, h // 2
    best, best_dist = None, None
    for y in range(h):
        for x in range(w):
            if world[y][x] == GRASS:
                d = (x - cx) ** 2 + (y - cy) ** 2
                if best_dist is None or d < best_dist:
                    best, best_dist = (x, y), d
    return best
