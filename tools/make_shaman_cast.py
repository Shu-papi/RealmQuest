"""
make_shaman_cast.py - builds the Goblin Shaman's cast sheet and fireball sprite.

The original fireball sheet (assets/monsters/mobs/attack/attack_goblin_shaman_fireball.png)
has the fireball painted into the frames, flying away on its own, so it never lined up
with the real projectile the game shoots. This script splits it in two:

    attack/attack_goblin_shaman_cast.png   the shaman raising and firing his staff
                                           (same 1024x1024 layout, fire beyond the staff erased)
    attack/goblin_shaman_fireball_bolt.png the fireball + ember trail from frame 4, facing right
                                           (the game's projectile wears this)

Run from the repo root:  python tools/make_shaman_cast.py
"""
import os
import sys

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
import pygame

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ATTACK = os.path.join(ROOT, "assets", "monsters", "mobs", "attack")
SRC = os.path.join(ATTACK, "attack_goblin_shaman_fireball.png")
CAST = os.path.join(ATTACK, "attack_goblin_shaman_cast.png")
BOLT = os.path.join(ATTACK, "goblin_shaman_fireball_bolt.png")

CELL, ROW_Y, FRAMES = 256, 384, 4
STAFF_EDGE = 116      # x inside a cell: the staff ends here, everything right of it is flying fire
BOLT_FRAME = 3        # the frame where the whole fireball is out in the air


def main():
    pygame.init()
    pygame.display.set_mode((8, 8))
    sheet = pygame.image.load(SRC).convert_alpha()
    cast = sheet.copy()
    for i in range(FRAMES):
        x0 = i * CELL + STAFF_EDGE
        cast.fill((0, 0, 0, 0), pygame.Rect(x0, ROW_Y, CELL - STAFF_EDGE, CELL))
    pygame.image.save(cast, CAST)

    cell = sheet.subsurface(pygame.Rect(BOLT_FRAME * CELL, ROW_Y, CELL, CELL))
    fire = cell.subsurface(pygame.Rect(STAFF_EDGE + 4, 0, CELL - STAFF_EDGE - 4, CELL))
    bolt = fire.subsurface(fire.get_bounding_rect()).copy()
    pygame.image.save(bolt, BOLT)
    print("wrote", os.path.relpath(CAST, ROOT), "and", os.path.relpath(BOLT, ROOT), bolt.get_size())
    return 0


if __name__ == "__main__":
    sys.exit(main())
