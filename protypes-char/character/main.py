"""Warrior prototype: idle / walk / attack state machine.

Run:      python prototypes/characters/main.py
Controls: LEFT/RIGHT move, SPACE attack, ESC quit

Sprite sheets are read from assets/characters/warrior_<anim>.png
(square frames side by side, e.g. 7 frames of 32x32 = 224x32).
Missing sheets are replaced by placeholder frames so this always runs.
"""
from pathlib import Path

import pygame

# ---- config (hardcoded on purpose: easy to move to JSON later) ----------
W, H, SCALE = 320, 180, 4              # low-res canvas, scaled up for the pixel look
FRAME = 32                              # sprite frame size in px
GROUND_Y = 150
ASSETS = Path(__file__).resolve().parents[2] / "assets" / "characters"

STATS = {"speed": 2 * FRAME, "damage": 15, "cooldown": 0.8, "reach": 24}

# name: (fps, loops?, placeholder frame count)
ANIMS = {
    "idle": (6, True, 7),
    "walk": (10, True, 6),
    "attack": (12, False, 5),
}
DAMAGE_FRAME = 2                        # attack frame (0-based) that deals damage


# ---- assets ----------------------------------------------------------------
def placeholder(name, count):
    """Draw simple stand-in frames so the prototype runs without art."""
    frames = []
    for i in range(count):
        s = pygame.Surface((FRAME, FRAME), pygame.SRCALPHA)
        bob = i % 2 if name != "attack" else 0
        pygame.draw.rect(s, (180, 50, 50), (10, 12 + bob, 12, 18 - bob))   # body
        pygame.draw.rect(s, (200, 200, 210), (12, 5 + bob, 8, 7))          # head
        if name == "attack":
            reach = [2, 4, 14, 8, 4][i % 5]                                # sword length
            pygame.draw.rect(s, (230, 230, 240), (22, 16, reach, 3))
        frames.append(s)
    return frames


def load_frames(name):
    path = ASSETS / f"warrior_{name}.png"
    if not path.exists():
        return placeholder(name, ANIMS[name][2])
    sheet = pygame.image.load(path).convert_alpha()
    size = sheet.get_height()                       # frames are square
    count = sheet.get_width() // size
    return [sheet.subsurface((i * size, 0, size, size)) for i in range(count)]


# ---- game objects ------------------------------------------------------------
class Dummy:
    """Target that takes damage."""

    def __init__(self, x):
        self.x, self.hp, self.flash = x, 100, 0.0

    def take_hit(self, dmg):
        self.hp -= dmg
        self.flash = 0.1
        if self.hp <= 0:
            self.hp = 100                            # respawn

    def update(self, dt):
        self.flash = max(0.0, self.flash - dt)

    def draw(self, surf):
        color = (255, 255, 255) if self.flash > 0 else (120, 90, 60)
        pygame.draw.rect(surf, color, (self.x - 8, GROUND_Y - 28, 16, 28))
        pygame.draw.rect(surf, (60, 0, 0), (self.x - 12, GROUND_Y - 36, 24, 3))
        pygame.draw.rect(surf, (0, 200, 0), (self.x - 12, GROUND_Y - 36, 24 * self.hp / 100, 3))


class Warrior:
    def __init__(self, x):
        self.x = x                                   # feet position
        self.facing = 1                              # 1 = right, -1 = left
        self.anims = {name: load_frames(name) for name in ANIMS}
        self.state = "idle"
        self.t = 0.0                                 # seconds in current state
        self.cooldown = 0.0
        self.hit_done = False                        # damage applied this attack?

    # state machine ---------------------------------------------------------
    def set_state(self, state):
        if state != self.state:
            self.state, self.t, self.hit_done = state, 0.0, False

    @property
    def frame_index(self):
        fps, loops, _ = ANIMS[self.state]
        n = len(self.anims[self.state])
        i = int(self.t * fps)
        return i % n if loops else min(i, n - 1)

    def update(self, dt, keys, target):
        self.t += dt
        self.cooldown = max(0.0, self.cooldown - dt)

        if self.state == "attack":                   # locked until animation ends
            if self.frame_index == DAMAGE_FRAME and not self.hit_done:
                self.hit_done = True
                dist = (target.x - self.x) * self.facing
                if 0 <= dist <= STATS["reach"]:
                    target.take_hit(STATS["damage"])
            fps = ANIMS["attack"][0]
            if self.t * fps >= len(self.anims["attack"]):
                self.set_state("idle")
            return

        if keys[pygame.K_SPACE] and self.cooldown == 0:
            self.cooldown = STATS["cooldown"]
            self.set_state("attack")
            return

        move = int(keys[pygame.K_RIGHT]) - int(keys[pygame.K_LEFT])
        if move:
            self.facing = move
            self.x += move * STATS["speed"] * dt
            self.set_state("walk")
        else:
            self.set_state("idle")

    def draw(self, surf):
        img = self.anims[self.state][self.frame_index]
        if self.facing < 0:
            img = pygame.transform.flip(img, True, False)
        surf.blit(img, (round(self.x) - img.get_width() // 2, GROUND_Y - img.get_height()))


# ---- main loop -------------------------------------------------------------------
def main():
    pygame.init()
    screen = pygame.display.set_mode((W * SCALE, H * SCALE))
    pygame.display.set_caption("RealmQuest - warrior prototype")
    canvas = pygame.Surface((W, H))
    font = pygame.font.Font(None, 14)
    clock = pygame.time.Clock()

    warrior = Warrior(80)
    dummy = Dummy(200)

    running = True
    while running:
        dt = clock.tick(60) / 1000
        for e in pygame.event.get():
            if e.type == pygame.QUIT or (e.type == pygame.KEYDOWN and e.key == pygame.K_ESCAPE):
                running = False

        warrior.update(dt, pygame.key.get_pressed(), dummy)
        dummy.update(dt)

        canvas.fill((30, 30, 46))
        pygame.draw.rect(canvas, (60, 60, 80), (0, GROUND_Y, W, H - GROUND_Y))
        dummy.draw(canvas)
        warrior.draw(canvas)
        hud = f"{warrior.state}  frame {warrior.frame_index}  cd {warrior.cooldown:.1f}"
        canvas.blit(font.render(hud, False, (255, 255, 255)), (4, 4))

        pygame.transform.scale(canvas, screen.get_size(), screen)   # nearest-neighbor
        pygame.display.flip()

    pygame.quit()


if __name__ == "__main__":
    main()
