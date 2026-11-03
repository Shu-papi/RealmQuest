import os, sys
os.environ["SDL_VIDEODRIVER"] = "dummy"
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
import pygame
from kendi_sprites import ANIMATIONS, SPRITE_DIR, Kendi

pygame.init(); pygame.display.set_mode((960, 540))

def test_all_frames_exist():
    for name, cfg in ANIMATIONS.items():
        for i in range(1, cfg["frames"] + 1):
            assert (SPRITE_DIR / name / f"{name}_{i:02d}.png").exists(), (name, i)

def test_state_machine():
    k = Kendi(x=0)
    k.update(0.016); assert k.state == "idle"
    k.set_input(1);  k.update(0.1); assert k.state == "walk" and k.x > 0
    k.set_input(1, run=True); k.update(0.1); assert k.state == "run"
    k.set_input(-1, run=True); k.update(0.1); assert k.facing == -1
    hits = []; k.on_attack_hit = hits.append
    k.attack(); x0 = k.x; k.update(0.05)
    assert k.state == "attack" and k.x == x0          # movement locked
    for _ in range(100):
        if k.state != "attack": break
        k.update(0.02)
    assert k.state == "run" and hits == [10, 11, 12]

def test_draw_all_states():
    surf = pygame.Surface((960, 540))
    for state in ANIMATIONS:
        k = Kendi(x=480, y=450); k.state = state
        for facing in (1, -1):
            k.facing = facing; k.draw(surf)
