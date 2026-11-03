"""Kendi sprite animations for pygame: idle / walk / run / attack.

Usage inside any pygame game:

    from kendi_sprites import Kendi
    kendi = Kendi(x=400, y=450)          # (x, y) = where the feet are
    ...
    kendi.handle_input(pygame.key.get_pressed())   # or kendi.set_input(dir, run)
    kendi.update(dt)                               # dt in seconds
    kendi.draw(screen)
    kendi.attack()                                 # one-shot swing
"""
from pathlib import Path
from statistics import median

import pygame

SPRITE_DIR = Path(__file__).parent / "assets" / "sprites" / "kendi"

# frames: number of PNGs (name_01.png ... name_NN.png)
# fps:    playback speed
# loop:   False = play once then return to idle/walk/run
# anchor: pixel inside the frame that sits on the character's (x, y) = the feet.
#         Keeps animations with different frame sizes lined up on the ground.
ANIMATIONS = {
    "idle":   {"frames": 19, "fps": 8,  "loop": True,  "anchor": (122, 232)},
    "walk":   {"frames": 21, "fps": 12, "loop": True,  "anchor": (125, 218)},
    "run":    {"frames": 14, "fps": 14, "loop": True,  "anchor": (128, 217)},
    "attack": {"frames": 22, "fps": 24, "loop": False, "anchor": (247, 452)},
}
HIT_FRAMES = (10, 11, 12)   # 1-based attack frames where the swing connects


class Animation:
    def __init__(self, name, cfg, source_frames, scale, reference_height):
        self.name = name
        self.fps = cfg["fps"]
        self.loop = cfg["loop"]
        visible_height = median(
            image.get_bounding_rect(min_alpha=1).height for image in source_frames
        )
        self.scale = scale * reference_height / visible_height
        ax, ay = cfg["anchor"]
        self.anchor = (ax * self.scale, ay * self.scale)
        self.frames = []        # facing right
        self.frames_left = []   # pre-flipped so drawing stays cheap
        for img in source_frames:
            if self.scale != 1.0:
                size = (round(img.get_width() * self.scale), round(img.get_height() * self.scale))
                img = pygame.transform.scale(img, size)
            self.frames.append(img)
            self.frames_left.append(pygame.transform.flip(img, True, False))
        self.reset()

    def reset(self):
        self.time = 0.0
        self.done = False

    @property
    def index(self):
        i = int(self.time * self.fps)
        return i % len(self.frames) if self.loop else min(i, len(self.frames) - 1)

    def update(self, dt):
        """Advance time. Returns True on the tick a non-looping animation finishes."""
        self.time += dt
        if not self.loop and not self.done and self.time * self.fps >= len(self.frames):
            self.done = True
            return True
        return False

    def draw(self, surface, x, y, facing=1):
        img = (self.frames if facing > 0 else self.frames_left)[self.index]
        ax, ay = self.anchor
        if facing < 0:                       # mirror the anchor too
            ax = img.get_width() - ax
        surface.blit(img, (x - ax, y - ay))


class Kendi:
    def __init__(self, x=0, y=0, scale=1.0, walk_speed=90, run_speed=220, height_px=None):
        self.x, self.y = x, y
        self.walk_speed, self.run_speed = walk_speed, run_speed
        self.facing = 1                      # 1 = right, -1 = left
        self.state = "idle"
        self.dir = 0                         # -1, 0, 1
        self.running = False
        self.on_attack_hit = None            # optional callback(frame_number)
        source_frames = {
            name: [
                pygame.image.load(SPRITE_DIR / name / f"{name}_{i:02d}.png").convert_alpha()
                for i in range(1, cfg["frames"] + 1)
            ]
            for name, cfg in ANIMATIONS.items()
        }
        reference_height = median(
            image.get_bounding_rect(min_alpha=1).height for image in source_frames["idle"]
        )
        if height_px is not None:
            scale = height_px / reference_height
        self.anims = {
            name: Animation(name, cfg, source_frames[name], scale, reference_height)
            for name, cfg in ANIMATIONS.items()
        }

    # ---- input -----------------------------------------------------------
    def set_input(self, direction, run=False):
        self.dir = (direction > 0) - (direction < 0)
        self.running = bool(run)

    def handle_input(self, keys):
        """Convenience: A/D or arrow keys to move, Shift to run."""
        left = keys[pygame.K_a] or keys[pygame.K_LEFT]
        right = keys[pygame.K_d] or keys[pygame.K_RIGHT]
        run = keys[pygame.K_LSHIFT] or keys[pygame.K_RSHIFT]
        self.set_input(int(right) - int(left), run)

    def attack(self):
        if self.state != "attack":
            self._set_state("attack")

    # ---- logic -----------------------------------------------------------
    def _set_state(self, new):
        if new != self.state:
            self.state = new
            self.anims[new].reset()

    def _locomotion(self):
        if not self.dir:
            return "idle"
        return "run" if self.running else "walk"

    def update(self, dt):
        anim = self.anims[self.state]

        if self.state == "attack":           # movement is locked during the swing
            prev = anim.index
            finished = anim.update(dt)
            now = anim.index
            if now != prev and (now + 1) in HIT_FRAMES and self.on_attack_hit:
                self.on_attack_hit(now + 1)
            if finished:
                self._set_state(self._locomotion())
            return

        if self.dir:
            self.facing = self.dir
        self._set_state(self._locomotion())
        speed = {"run": self.run_speed, "walk": self.walk_speed}.get(self.state, 0)
        self.x += self.dir * speed * dt
        self.anims[self.state].update(dt)

    def draw(self, surface):
        self.anims[self.state].draw(surface, self.x, self.y, self.facing)
