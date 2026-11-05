"""
preview.py - Look at every monster's animations.

    python src/monsters/dev/preview.py                 opens a window (live animation + all frames)
    python src/monsters/dev/preview.py --png out.png   saves a picture of every frame (no window needed)
    python src/monsters/dev/preview.py --png out.png --variant frost

In the window:  UP / DOWN  change monster     LEFT / RIGHT  change variant
                SPACE  pause     ESC  quit
Each row is one animation: idle, walk, windup, strike, recover, hurt.
"""
import os
import sys

import pygame

SRC_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)

from monsters import list_monsters, list_variants, spawn_monster  # noqa: E402

BACKGROUND = (33, 29, 46)
GRID = (52, 46, 74)
LABEL = (238, 237, 254)
DIM = (150, 148, 170)
ROWS = ["idle", "walk", "windup", "strike", "recover", "hurt"]


def sheet_of(name, variant):
    return spawn_monster(name, 0, 0, variant=variant, spawn=False).sheet


def block_size(sheet):
    w, h = sheet.pixel_size
    frames = max(sheet.count(r) for r in ROWS)
    return frames * (w + 4) + 110, len(ROWS) * (h + 4) + 28


def draw_block(surface, name, variant, font, x0, y0, level=3):
    """Every frame of one monster, one animation per row."""
    sheet = sheet_of(name, variant)
    if sheet is None:
        return
    w, h = sheet.pixel_size
    surface.blit(font.render(f"{name}  [{variant}]", True, LABEL), (x0, y0))
    y = y0 + 22
    for row in ROWS:
        surface.blit(font.render(row, True, DIM), (x0, y + h // 2 - 6))
        for step in range(sheet.count(row)):
            x = x0 + 80 + step * (w + 4)
            pygame.draw.rect(surface, GRID, (x, y, w, h), 1)
            surface.blit(sheet.image(sheet.frame_index(row, step), False, level, False), (x, y))
        y += h + 4


def save_png(path, variant):
    pygame.font.init()
    font = pygame.font.Font(None, 22)
    names = list_monsters()
    sizes = [block_size(sheet_of(n, variant)) for n in names]
    width = max(s[0] for s in sizes) + 20
    height = sum(s[1] for s in sizes) + 20
    out = pygame.Surface((width, height))
    out.fill(BACKGROUND)
    y = 10
    for name, size in zip(names, sizes):
        draw_block(out, name, variant, font, 10, y)
        y += size[1]
    pygame.image.save(out, path)
    print("saved", path)


def main():
    args = sys.argv[1:]
    variant = args[args.index("--variant") + 1] if "--variant" in args else "bone"
    pygame.init()
    if "--png" in args:
        save_png(args[args.index("--png") + 1], variant)
        return
    import audio
    from bosses.dev.arena import load_settings
    audio.init(load_settings())

    names, variants = list_monsters(), list_variants()
    screen = pygame.display.set_mode((1300, 720))
    pygame.display.set_caption("RealmQuest monsters")
    font = pygame.font.Font(None, 22)
    clock = pygame.time.Clock()
    n, v = 0, variants.index(variant)
    paused, running, t = False, True, 0.0
    while running:
        for e in pygame.event.get():
            if e.type == pygame.QUIT or (e.type == pygame.KEYDOWN and e.key == pygame.K_ESCAPE):
                running = False
            elif e.type == pygame.KEYDOWN:
                if e.key == pygame.K_DOWN:
                    n = (n + 1) % len(names)
                elif e.key == pygame.K_UP:
                    n = (n - 1) % len(names)
                elif e.key == pygame.K_RIGHT:
                    v = (v + 1) % len(variants)
                elif e.key == pygame.K_LEFT:
                    v = (v - 1) % len(variants)
                elif e.key == pygame.K_SPACE:
                    paused = not paused
        if not paused:
            t += clock.get_time() / 1000.0
        screen.fill(BACKGROUND)
        draw_block(screen, names[n], variants[v], font, 10, 10, level=2 + int(t * 3) % 3)
        sheet = sheet_of(names[n], variants[v])
        if sheet:
            # live animation: each animation plays at about the speed it has in the game
            w, h = sheet.pixel_size
            speeds = {"idle": 5, "walk": 10, "windup": 6, "strike": 12, "recover": 4, "hurt": 3}
            x, y = 10, 22 + len(ROWS) * (h + 4) + 30
            for row in ROWS:
                step = int(t * speeds[row]) % sheet.count(row)
                screen.blit(sheet.image(sheet.frame_index(row, step), False, 3, False), (x, y))
                screen.blit(font.render(row, True, DIM), (x, y + h + 2))
                x += w + 12
        pygame.display.flip()
        clock.tick(60)
    pygame.quit()


if __name__ == "__main__":
    main()
