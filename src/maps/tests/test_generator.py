import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from generator import (  # noqa: E402
    generate_map, find_spawn, is_walkable, WATER, MOUNTAIN, GRASS,
)


class MapGeneratorTests(unittest.TestCase):
    def test_same_seed_same_map(self):
        self.assertEqual(generate_map(42), generate_map(42))

    def test_different_seed_different_map(self):
        self.assertNotEqual(generate_map(1), generate_map(2))

    def test_size(self):
        world = generate_map(7, width=12, height=9)
        self.assertEqual(len(world), 9)
        self.assertTrue(all(len(row) == 12 for row in world))

    def test_only_valid_tile_ids(self):
        for seed in range(20):
            for row in generate_map(seed):
                self.assertTrue(all(0 <= t <= 3 for t in row))

    def test_spawn_is_walkable(self):
        for seed in range(20):
            world = generate_map(seed)
            spawn = find_spawn(world)
            if spawn:
                self.assertEqual(world[spawn[1]][spawn[0]], GRASS)
                self.assertTrue(is_walkable(world, *spawn))

    def test_out_of_bounds_not_walkable(self):
        world = generate_map(3)
        self.assertFalse(is_walkable(world, -1, 0))
        self.assertFalse(is_walkable(world, 0, 999))


if __name__ == "__main__":
    unittest.main()
