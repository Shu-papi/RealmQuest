"""
Shows every monster animated.
Run from the repo root:  python src/monsters/monster_viewer.py   (needs: pip install pygame-ce)
Keys: 1 = idle   2 = move   3 = attack   F = flip left/right   Esc = quit
"""
import os
import pygame

try:                                   # imported as a package: monsters.monster_viewer
    from . import monsters_config as cfg
except ImportError:                    # run directly as a script
    import monsters_config as cfg

SCALE = 4
W, H = 1280, 420


def load_frames(info):
    sheet = pygame.image.load(os.path.join(cfg.ASSET_DIR, info["sheet"])).convert_alpha()
    fw, fh = info["frame"]
    rows = {}
    for name, r in cfg.ROWS.items():
        rows[name] = [
            pygame.transform.scale(
                sheet.subsurface(pygame.Rect(c * fw, r * fh, fw, fh)),
                (fw * SCALE, fh * SCALE))
            for c in range(cfg.FRAMES_PER_ROW)
        ]
    return rows


def main():
    pygame.init()
    screen = pygame.display.set_mode((W, H))
    pygame.display.set_caption("Goblin King monsters")
    font = pygame.font.SysFont(None, 26)
    clock = pygame.time.Clock()

    monsters = {name: load_frames(info) for name, info in cfg.MONSTERS.items()}
    anim = "idle"
    flip = False
    t = 0.0

    running = True
    while running:
        dt = clock.tick(60) / 1000
        t += dt
        for e in pygame.event.get():
            if e.type == pygame.QUIT:
                running = False
            elif e.type == pygame.KEYDOWN:
                if e.key == pygame.K_ESCAPE:
                    running = False
                elif e.key == pygame.K_1:
                    anim = "idle"
                elif e.key == pygame.K_2:
                    anim = "move"
                elif e.key == pygame.K_3:
                    anim = "attack"
                elif e.key == pygame.K_f:
                    flip = not flip

        screen.fill((44, 42, 53))
        slot = W // len(monsters)
        frame = int(t * cfg.FPS[anim]) % cfg.FRAMES_PER_ROW
        for i, (name, rows) in enumerate(monsters.items()):
            img = rows[anim][frame]
            if flip:
                img = pygame.transform.flip(img, True, False)
            cx = slot * i + slot // 2
            screen.blit(img, img.get_rect(midbottom=(cx, 330)))
            label = font.render(name.replace("_", " ").title(), True, (255, 255, 255))
            screen.blit(label, label.get_rect(center=(cx, 365)))

        hint = font.render(f"Animation: {anim}     1 idle   2 move   3 attack   F flip   Esc quit",
                           True, (200, 200, 210))
        screen.blit(hint, (12, 10))
        pygame.display.flip()

    pygame.quit()


if __name__ == "__main__":
    main()
