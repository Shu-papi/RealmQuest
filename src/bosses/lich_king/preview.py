"""
preview_lich_king.py - Look at the Lich King's art without playing the fight.

    python src/bosses/lich_king/preview.py   save lich_king_preview.png (a sheet of poses)
    python src/bosses/lich_king/preview.py --live     open a window with animation (ESC quits)
    python src/bosses/lich_king/preview.py --frame 2  save the sheet with the animation clock at 2.0 s
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import pygame
from bosses.lich_king.art import LichKingArt
from bosses.lich_king.boss import ATTACK_GLOW

FLOOR = (33, 29, 46)
BACKGROUND = (14, 12, 22)
TEXT = (238, 237, 254)

# name, kwargs for LichKingArt.draw
POSES = [
    ("Phase 1 idle",        dict(phase=1)),
    ("Volley wind-up",      dict(phase=1, glow=ATTACK_GLOW["volley"], glow_level=3)),
    ("Drain wind-up",       dict(phase=1, glow=ATTACK_GLOW["drain"], glow_level=3)),
    ("Hit flash",           dict(phase=1, flash=True)),
    ("Phase 2 idle",        dict(phase=2)),
    ("Summon wind-up",      dict(phase=2, glow=ATTACK_GLOW["summon"], glow_level=3, raise_staff=True)),
    ("Teleport fade",       dict(phase=2, fade=0.45)),
    ("Death fade",          dict(phase=1, fade=0.15)),
]


def draw_sheet(surface, art, clock, columns=4, cell=(300, 290)):
    surface.fill(BACKGROUND)
    font = pygame.font.Font(None, 24)
    for i, (name, kwargs) in enumerate(POSES):
        col, row = i % columns, i // columns
        x, y = col * cell[0], row * cell[1]
        pygame.draw.rect(surface, FLOOR, (x + 6, y + 6, cell[0] - 12, cell[1] - 12))
        art.draw(surface, x + cell[0] // 2, y + cell[1] // 2 - 4, clock=clock, **kwargs)
        label = font.render(name, True, TEXT)
        surface.blit(label, (x + 14, y + cell[1] - 30))


def main():
    live = "--live" in sys.argv
    clock_start = 1.3
    if "--frame" in sys.argv:
        clock_start = float(sys.argv[sys.argv.index("--frame") + 1])

    if live:
        os.environ.pop("SDL_VIDEODRIVER", None)
        pygame.display.quit()
    pygame.init()
    columns, cell = 4, (300, 290)
    size = (columns * cell[0], ((len(POSES) + columns - 1) // columns) * cell[1])
    screen = pygame.display.set_mode(size)
    pygame.display.set_caption("Lich King art preview")
    art = LichKingArt()

    if not live:
        draw_sheet(screen, art, clock_start, columns, cell)
        out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "lich_king_preview.png")
        pygame.image.save(screen, out)
        print("Saved", out)
        return

    timer = pygame.time.Clock()
    t = clock_start
    running = True
    while running:
        t += timer.tick(60) / 1000.0
        for e in pygame.event.get():
            if e.type == pygame.QUIT or (e.type == pygame.KEYDOWN and e.key == pygame.K_ESCAPE):
                running = False
        draw_sheet(screen, art, t, columns, cell)
        pygame.display.flip()
    pygame.quit()


if __name__ == "__main__":
    main()
