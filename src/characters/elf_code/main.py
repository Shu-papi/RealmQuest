#!/usr/bin/env python3
"""
Interactive demo for the elf archer animations.

    python main.py              # 1x (original size)
    python main.py --scale 2    # crisp 2x pixel-perfect zoom

Controls
--------
    A / D  or  Left / Right    move (walk)
    Shift (hold)               run
    J  or  Z                   quick attack
    K  or  X  (hold, release)  charge attack: hold to draw + glow, release to fire
    F1                         toggle debug overlay (anchor, ground, state, frame, events)
    Esc                        quit
"""
import argparse
import sys

import pygame

from sprite_animation import AnimationLibrary, AnimatedCharacter

WIDTH, HEIGHT = 1000, 600
FPS_CAP = 120
SKY_TOP, SKY_BOTTOM = (28, 34, 58), (92, 112, 150)
GROUND_COLOR, GROUND_EDGE = (46, 70, 52), (86, 120, 80)


def draw_background(screen, ground_y):
    for y in range(ground_y):                                   # cheap vertical gradient
        t = y / ground_y
        color = tuple(int(a + (b - a) * t) for a, b in zip(SKY_TOP, SKY_BOTTOM))
        pygame.draw.line(screen, color, (0, y), (WIDTH, y))
    pygame.draw.rect(screen, GROUND_COLOR, (0, ground_y, WIDTH, HEIGHT - ground_y))
    pygame.draw.line(screen, GROUND_EDGE, (0, ground_y), (WIDTH, ground_y), 2)


def draw_debug(screen, font, hero, ground_y, last_events):
    c = hero.controller
    frame = hero.current_frame
    x, y = round(hero.x), round(hero.y)
    # frame bounds + anchor cross
    rect = pygame.Rect(x - frame.anchor[0], y - frame.anchor[1], *frame.image.get_size())
    pygame.draw.rect(screen, (255, 200, 60), rect, 1)
    pygame.draw.line(screen, (255, 80, 80), (x - 12, y), (x + 12, y), 1)
    pygame.draw.line(screen, (80, 200, 255), (x, y - 12), (x, y + 12), 1)
    lines = [
        f"animation : {c.animation_name}",
        f"frame     : {c.frame_index + 1}/{len(hero.library[c.animation_name])}",
        f"facing    : {'right' if c.facing > 0 else 'left'}",
        f"can move  : {c.can_move}",
        f"charging  : {c.is_charging}  ready: {c.charge_ready}",
        f"events    : {', '.join(last_events) or '-'}",
    ]
    for i, text in enumerate(lines):
        screen.blit(font.render(text, True, (255, 255, 255)), (12, 40 + i * 18))


def main():
    parser = argparse.ArgumentParser(description="Elf archer animation demo")
    parser.add_argument("--scale", type=int, default=1, help="integer pixel-perfect zoom (default 1)")
    args = parser.parse_args()

    pygame.init()
    screen = pygame.display.set_mode((WIDTH, HEIGHT))           # must exist before loading images
    pygame.display.set_caption("Elf Archer - animation demo")
    font = pygame.font.SysFont("consolas,menlo,monospace", 15)
    clock = pygame.time.Clock()

    try:
        library = AnimationLibrary(scale=args.scale)
    except (FileNotFoundError, ValueError, RuntimeError) as err:
        print(f"Could not load sprites: {err}", file=sys.stderr)
        sys.exit(1)

    ground_y = HEIGHT - 110
    hero = AnimatedCharacter(library, x=WIDTH // 2, y=ground_y, bounds=(60, WIDTH - 60))
    show_debug, last_events = False, []

    running = True
    while running:
        dt = min(clock.tick(FPS_CAP) / 1000.0, 0.05)            # cap dt so a hitch can't teleport anything

        for event in pygame.event.get():
            if event.type == pygame.QUIT or (event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE):
                running = False
            elif event.type == pygame.KEYDOWN:
                if event.key in (pygame.K_j, pygame.K_z):
                    hero.quick_attack()
                elif event.key in (pygame.K_k, pygame.K_x):
                    hero.start_charge()
                elif event.key == pygame.K_F1:
                    show_debug = not show_debug
            elif event.type == pygame.KEYUP and event.key in (pygame.K_k, pygame.K_x):
                hero.release_charge()

        keys = pygame.key.get_pressed()
        move_x = (keys[pygame.K_d] or keys[pygame.K_RIGHT]) - (keys[pygame.K_a] or keys[pygame.K_LEFT])
        run = keys[pygame.K_LSHIFT] or keys[pygame.K_RSHIFT]

        events = hero.update(dt, move_x, run)
        if events:
            last_events = events                                 # hook: spawn arrows / sounds here

        draw_background(screen, ground_y)
        hero.draw(screen)
        if show_debug:
            draw_debug(screen, font, hero, ground_y, last_events)
        hud = "A/D move   Shift run   J quick attack   K hold+release charge   F1 debug   Esc quit"
        screen.blit(font.render(hud, True, (235, 235, 235)), (12, 12))
        pygame.display.flip()

    pygame.quit()


if __name__ == "__main__":
    main()
