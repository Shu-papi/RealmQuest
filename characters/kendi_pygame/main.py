"""Demo: A/D or arrows = move, Shift = run, Space/J = attack, Esc = quit."""
import json
from pathlib import Path

import pygame

from kendi_sprites import Kendi

CONFIG_PATH = Path(__file__).resolve().parent / "config.json"


def load_config():
    try:
        with CONFIG_PATH.open("r", encoding="utf-8") as config_file:
            return json.load(config_file)
    except (FileNotFoundError, json.JSONDecodeError):
        return {
            "screen": {"width": 960, "height": 540, "ground_y": 450},
            "character": {"height_px": 250, "character_height": 250},
            "movement": {"walk_speed": 90, "run_speed": 220, "left_limit_px": 60},
            "ui": {"font_size": 24, "hud_color": [220, 220, 220]},
        }


def main():
    config = load_config()
    screen_cfg = config.get("screen", {})
    character_cfg = config.get("character", {})
    movement_cfg = config.get("movement", {})
    ui_cfg = config.get("ui", {})

    WIDTH = int(screen_cfg.get("width", 960))
    HEIGHT = int(screen_cfg.get("height", 540))
    GROUND_Y = int(screen_cfg.get("ground_y", 450))
    character_height = max(1.0, float(character_cfg.get("height_px", character_cfg.get("character_height", 250))))

    pygame.init()
    screen = pygame.display.set_mode((WIDTH, HEIGHT))
    pygame.display.set_caption("Kendi sprites")
    clock = pygame.time.Clock()
    font = pygame.font.SysFont(None, int(ui_cfg.get("font_size", 24)))

    kendi = Kendi(
        x=WIDTH // 2,
        y=GROUND_Y,
        height_px=character_height,
        walk_speed=float(movement_cfg.get("walk_speed", 90)),
        run_speed=float(movement_cfg.get("run_speed", 220)),
    )

    running = True
    while running:
        dt = clock.tick(60) / 1000
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    running = False
                elif event.key in (pygame.K_SPACE, pygame.K_j):
                    kendi.attack()

        kendi.handle_input(pygame.key.get_pressed())
        kendi.update(dt)

        left_limit = int(movement_cfg.get("left_limit_px", 60))
        right_limit = int(movement_cfg.get("right_limit_px", WIDTH - 60))
        kendi.x = max(left_limit, min(right_limit, kendi.x))

        screen.fill(tuple(screen_cfg.get("background_color", [27, 27, 42])))
        pygame.draw.rect(screen, tuple(screen_cfg.get("ground_color", [18, 18, 28])), (0, GROUND_Y, WIDTH, HEIGHT - GROUND_Y))
        kendi.draw(screen)

        hud = ui_cfg.get("hud_text", "state: {state}   A/D move  Shift run  Space attack")
        hud = hud.format(state=kendi.state)
        screen.blit(font.render(hud, True, tuple(ui_cfg.get("hud_color", [220, 220, 220]))), (12, 10))
        pygame.display.flip()

    pygame.quit()


if __name__ == "__main__":
    main()
