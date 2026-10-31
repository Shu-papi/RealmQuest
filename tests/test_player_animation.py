"""
Tests for the Warrior sprite animations in src/characters/player.py.

Run from the repo root (no window needed):
    python -m pytest tests/test_player_animation.py
    python tests/test_player_animation.py
"""
import json
import os
import sys

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

import pygame  # noqa: E402

from characters.player import ASSET_DIR, Player  # noqa: E402

BOUNDS = (0, 0, 960, 640)
IDLE_INPUT = {"move": (0, 0), "aim": (480, 0), "attack": False}


class Dummy:
    """Minimal boss target: same attributes player.py needs."""
    x, y, radius = 480.0, 460.0, 20

    def __init__(self):
        self.hp = 1000

    def take_damage(self, n):
        self.hp -= n


class DummyBoss:
    def __init__(self):
        self.target = Dummy()

    def hittables(self):
        return [self.target]


def setup_module(_=None):
    pygame.init()
    pygame.display.set_mode((960, 640))


def make():
    setup_module()
    return Player(480, 520, "warrior"), DummyBoss()


def step(p, boss, seconds, **inp):
    state = {**IDLE_INPUT, **inp}
    for _ in range(round(seconds * 60)):
        p.update(1 / 60, state, BOUNDS, boss)


def test_manifest_is_consistent():
    with open(os.path.join(ASSET_DIR, "knight_animations.json")) as fh:
        data = json.load(fh)
    sheet = pygame.image.load(os.path.join(ASSET_DIR, data["spritesheet"]))
    assert {"idle", "walk", "attack", "hurt", "dead"} <= set(data["animations"])
    for anim in data["animations"].values():
        for f in anim["frames"]:
            r = data["frame_rects"][f]
            assert pygame.Rect(0, 0, *sheet.get_size()).contains(
                pygame.Rect(r["x"], r["y"], r["w"], r["h"])), f
        durations = anim["frame_duration_ms"]
        assert not isinstance(durations, list) or len(durations) == len(anim["frames"])


def test_every_behaviour_has_its_own_strip():
    for name in ("idle", "walk", "attack", "hurt", "dead"):
        assert os.path.exists(os.path.join(ASSET_DIR, "animations", f"knight_{name}.png")), name


def test_only_warrior_has_sprites():
    setup_module()
    assert Player(0, 0, "warrior").anim is not None
    assert Player(0, 0, "mage").anim is None
    assert Player(0, 0, "archer").anim is None


def test_idle_and_walk():
    p, boss = make()
    step(p, boss, 0.1)
    assert p.anim.name == "idle"
    step(p, boss, 0.3, move=(1, 0))
    assert p.anim.name == "walk"
    step(p, boss, 0.3)
    assert p.anim.name == "idle"


def test_walk_cycles_through_all_frames():
    p, boss = make()
    seen = set()
    for _ in range(60):
        step(p, boss, 1 / 60, move=(1, 0))
        seen.add(p.anim.index)
    assert seen == {0, 1, 2, 3}


def test_attack_plays_once_then_returns():
    p, boss = make()
    step(p, boss, 1 / 60, attack=True, aim=(480, 400))
    assert p.anim.name == "attack"
    assert boss.target.hp < 1000                      # gameplay unchanged: damage lands on click
    step(p, boss, 0.1)
    assert p.anim.name == "attack" and p.anim.index >= 1
    step(p, boss, 0.4)
    assert p.anim.name == "idle" and p.anim.one_shot is None


def test_hurt_reaction_and_priority():
    p, boss = make()
    assert p.take_damage(10) == 10
    assert p.anim.name == "hurt"
    step(p, boss, 1 / 60, attack=True)                # attacking can't cut the reaction short...
    assert p.anim.name == "hurt"
    step(p, boss, 0.3)
    assert p.anim.name == "idle"                      # ...which ends on its own
    assert p.take_damage(10) == 0                     # still invulnerable (existing behaviour)


def test_hurt_interrupts_attack():
    p, boss = make()
    step(p, boss, 1 / 60, attack=True)
    assert p.anim.name == "attack"
    p.take_damage(5)
    assert p.anim.name == "hurt"


def test_death_holds_last_frame():
    p, boss = make()
    p.take_damage(p.max_hp)
    assert p.hp == 0 and p.anim.name == "dead"
    step(p, boss, 1.5)
    assert p.anim.finished and p.anim.index == 3
    step(p, boss, 1.0, move=(1, 0), attack=True)      # dead players don't move or swing
    assert p.anim.name == "dead" and p.x == 480.0
    assert p.take_damage(10) == 0


def test_death_plays_even_if_game_stops_calling_update():
    p, _ = make()
    screen = pygame.Surface((960, 640), pygame.SRCALPHA)
    p.take_damage(p.max_hp)
    for _ in range(14):                               # ~0.5 s of draw-only frames
        pygame.time.wait(40)
        p.draw(screen)
    assert p.anim.index == 3


def test_sprite_flips_toward_aim():
    p, boss = make()
    step(p, boss, 1 / 60, aim=(100, 520))
    assert p.flipped
    step(p, boss, 1 / 60, aim=(900, 520))
    assert not p.flipped
    step(p, boss, 1 / 60, aim=(p.x + 1, 100))         # almost straight up keeps the last side
    assert not p.flipped


def test_draw_puts_pixels_on_screen():
    p, boss = make()
    screen = pygame.Surface((960, 640))
    screen.fill((0, 0, 0))
    for name in ("idle", "walk", "attack", "hurt", "dead"):
        screen.fill((0, 0, 0))
        p.anim.one_shot = None if name != "dead" else "dead"
        p.anim.base = "walk" if name == "walk" else "idle"
        p.anim._start(name)
        p.invuln = 0.0
        p.draw(screen)
        assert pygame.mask.from_threshold(screen, (0, 0, 0), (1, 1, 1, 255)).count() < 960 * 640, name


if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for t in tests:
        t()
        print("ok  ", t.__name__)
