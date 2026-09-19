"""Character prototype: warrior, mage, archer. Idle / walk / attack state machine.

Run:      python prototypes/characters/main.py
Controls: LEFT/RIGHT move, SPACE attack, 1/2/3 switch character, ESC quit

Sprite sheets are read from assets/characters/<character>_<anim>.png
(square frames side by side, e.g. 7 frames of 32x32 = 224x32).
Missing sheets are replaced by placeholder frames so this always runs.
"""
from pathlib import Path

import pygame

# ---- config (hardcoded on purpose: easy to move to JSON later) ----------
W, H, SCALE = 320, 180, 4              # low-res canvas, scaled up for the pixel look
FRAME = 32                              # sprite frame size in px (1 tile)
GROUND_Y = 150
ASSETS = Path(__file__).resolve().parents[2] / "assets" / "characters"

# One row per character. Speeds/ranges are tiles x FRAME (see docs/characters.md).
CHARACTERS = {
    "warrior": {"color": (180, 50, 50), "speed": 2 * FRAME, "damage": 15,
                "cooldown": 0.8, "ranged": False, "reach": 24},
    "mage":    {"color": (130, 70, 200), "speed": 3 * FRAME, "damage": 8,
                "cooldown": 0.6, "ranged": True, "proj_speed": 9 * FRAME, "range": 6 * FRAME},
    "archer":  {"color": (60, 150, 70), "speed": 4 * FRAME, "damage": 12,
                "cooldown": 0.6, "ranged": True, "proj_speed": 12 * FRAME, "range": 8 * FRAME},
}
SWITCH_KEYS = {pygame.K_1: "warrior", pygame.K_2: "mage", pygame.K_3: "archer"}

# name: (fps, loops?, placeholder frame count)
ANIMS = {
    "idle": (6, True, 7),
    "walk": (10, True, 6),
    "attack": (12, False, 5),
}
DAMAGE_FRAME = 2                        # attack frame (0-based) that deals damage


# ---- assets ----------------------------------------------------------------
def placeholder(char, anim, count):
    """Draw simple stand-in frames so the prototype runs without art."""
    stats = CHARACTERS[char]
    frames = []
    for i in range(count):
        s = pygame.Surface((FRAME, FRAME), pygame.SRCALPHA)
        bob = i % 2 if anim != "attack" else 0
        pygame.draw.rect(s, stats["color"], (10, 12 + bob, 12, 18 - bob))  # body
        pygame.draw.rect(s, (200, 200, 210), (12, 5 + bob, 8, 7))          # head
        if anim == "attack":
            step = [2, 4, 14, 8, 4][i % 5]
            if stats["ranged"]:                                            # bow / staff
                pygame.draw.rect(s, (230, 230, 240), (22 + step // 4, 8, 2, 16))
            else:                                                          # sword
                pygame.draw.rect(s, (230, 230, 240), (22, 16, step, 3))
        frames.append(s)
    return frames


def load_frames(char, anim):
    path = ASSETS / f"{char}_{anim}.png"
    if not path.exists():
        return placeholder(char, anim, ANIMS[anim][2])
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


class Projectile:
    """Arrow / bolt: flies straight, hits the target, or expires."""

    def __init__(self, x, direction, damage, speed, max_range):
        self.x, self.dir, self.damage = x, direction, damage
        self.speed, self.left = speed, max_range
        self.alive = True

    def update(self, dt, target):
        step = self.speed * dt
        self.x += self.dir * step
        self.left -= step
        if abs(self.x - target.x) < 8:
            target.take_hit(self.damage)
            self.alive = False
        elif self.left <= 0 or not 0 <= self.x <= W:
            self.alive = False

    def draw(self, surf):
        pygame.draw.rect(surf, (255, 220, 80), (round(self.x) - 4, GROUND_Y - 18, 8, 2))


class Character:
    def __init__(self, name, x, facing=1):
        self.name = name
        self.stats = CHARACTERS[name]
        self.x = x                                   # feet position
        self.facing = facing                         # 1 = right, -1 = left
        self.anims = {a: load_frames(name, a) for a in ANIMS}
        self.state = "idle"
        self.t = 0.0                                 # seconds in current state
        self.cooldown = 0.0
        self.hit_done = False                        # damage applied this attack?
        self.projectiles = []

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

    def strike(self, target):
        """Runs once, on the damage frame. The only melee/ranged difference."""
        s = self.stats
        if s["ranged"]:
            self.projectiles.append(Projectile(self.x + 12 * self.facing, self.facing,
                                               s["damage"], s["proj_speed"], s["range"]))
        else:
            dist = (target.x - self.x) * self.facing
            if 0 <= dist <= s["reach"]:
                target.take_hit(s["damage"])

    def update(self, dt, keys, target):
        self.t += dt
        self.cooldown = max(0.0, self.cooldown - dt)

        for p in self.projectiles:                   # keep flying during any state
            p.update(dt, target)
        self.projectiles = [p for p in self.projectiles if p.alive]

        if self.state == "attack":                   # locked until animation ends
            if self.frame_index == DAMAGE_FRAME and not self.hit_done:
                self.hit_done = True
                self.strike(target)
            fps = ANIMS["attack"][0]
            if self.t * fps >= len(self.anims["attack"]):
                self.set_state("idle")
            return

        if keys[pygame.K_SPACE] and self.cooldown == 0:
            self.cooldown = self.stats["cooldown"]
            self.set_state("attack")
            return

        move = int(keys[pygame.K_RIGHT]) - int(keys[pygame.K_LEFT])
        if move:
            self.facing = move
            self.x += move * self.stats["speed"] * dt
            self.set_state("walk")
        else:
            self.set_state("idle")

    def draw(self, surf):
        img = self.anims[self.state][self.frame_index]
        if self.facing < 0:
            img = pygame.transform.flip(img, True, False)
        surf.blit(img, (round(self.x) - img.get_width() // 2, GROUND_Y - img.get_height()))
        for p in self.projectiles:
            p.draw(surf)


# ---- main loop -------------------------------------------------------------------
def main():
    pygame.init()
    screen = pygame.display.set_mode((W * SCALE, H * SCALE))
    pygame.display.set_caption("RealmQuest - character prototype")
    canvas = pygame.Surface((W, H))
    font = pygame.font.Font(None, 14)
    clock = pygame.time.Clock()

    hero = Character("warrior", 80)
    dummy = Dummy(240)

    running = True
    while running:
        dt = clock.tick(60) / 1000
        for e in pygame.event.get():
            if e.type == pygame.QUIT or (e.type == pygame.KEYDOWN and e.key == pygame.K_ESCAPE):
                running = False
            elif e.type == pygame.KEYDOWN and e.key in SWITCH_KEYS:
                hero = Character(SWITCH_KEYS[e.key], hero.x, hero.facing)

        hero.update(dt, pygame.key.get_pressed(), dummy)
        dummy.update(dt)

        canvas.fill((30, 30, 46))
        pygame.draw.rect(canvas, (60, 60, 80), (0, GROUND_Y, W, H - GROUND_Y))
        dummy.draw(canvas)
        hero.draw(canvas)
        hud = f"{hero.name}  {hero.state}  frame {hero.frame_index}  cd {hero.cooldown:.1f}   [1] [2] [3] switch"
        canvas.blit(font.render(hud, False, (255, 255, 255)), (4, 4))

        pygame.transform.scale(canvas, screen.get_size(), screen)   # nearest-neighbor
        pygame.display.flip()

    pygame.quit()


if __name__ == "__main__":
    main()
