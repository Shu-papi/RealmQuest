"""
player.py - The playable character (Warrior / Mage / Archer).

Fits the boss contract in src/bosses/base_boss.py exactly, so it drops into
their arena in place of the placeholder Player:

    boss.update(dt, player, bounds)     <- needs player.rect, player.take_damage(n)
    for target in boss.hittables():     <- player's attack checks these
        ...

Try it against a real boss:
    python src/characters/dev/arena.py lich_king
    python src/characters/dev/arena.py lich_king mage
"""
import json
import math
import os

import pygame

CLASS_STATS = {
    "warrior": {"hp": 120, "speed": 200, "color": (180, 50, 50),
                "attack": "melee", "damage": 15, "cooldown": 0.8, "range": 62,
                "sprite": "knight"},      # assets/characters/knight_*.png / .json
    "mage":    {"hp": 70,  "speed": 240, "color": (130, 70, 200),
                "attack": "ranged", "damage": 20, "cooldown": 0.9,
                "proj_speed": 420, "proj_range": 480},
    "archer":  {"hp": 90,  "speed": 280, "color": (60, 150, 70),
                "attack": "ranged", "damage": 12, "cooldown": 0.4,
                "proj_speed": 620, "proj_range": 560},
}
RADIUS = 14

ASSET_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))), "assets", "characters")

# One-shot animations can interrupt each other only if the newcomer is at least as important.
# (a hit interrupts a swing, but a swing can't cut a hit reaction short; death beats everything)
ANIM_PRIORITY = {"attack": 1, "hurt": 2, "dead": 3}


class SpriteAnimator:
    """Plays the animations described by assets/characters/<name>_animations.json.

    A looping *base* animation (idle / walk) runs underneath; one-shot animations
    (attack / hurt / dead) are layered on top with play() and fall back to the base
    when they finish. Frames are looked up by name, so artists can add or retime
    frames in the json without touching code.
    """

    def __init__(self, name, asset_dir=ASSET_DIR):
        with open(os.path.join(asset_dir, f"{name}_animations.json")) as fh:
            self.data = json.load(fh)
        sheet = pygame.image.load(os.path.join(asset_dir, self.data["spritesheet"]))
        try:
            sheet = sheet.convert_alpha()      # faster blits once a display exists
        except pygame.error:
            pass                               # headless / tests: keep the raw surface
        self.w, self.h = self.data["frame_size"]
        px, py = self.data["source_pivot_offset"]      # cell pixel that sits on Player.x / .y
        self.pivot = {False: (px, py), True: (self.w - 1 - px, py)}
        self.frames = {}
        for fname, r in self.data["frame_rects"].items():
            img = sheet.subsurface(pygame.Rect(r["x"], r["y"], r["w"], r["h"])).copy()
            self.frames[fname] = (img, pygame.transform.flip(img, True, False))
        self.base = "idle"
        self.name = "idle"
        self.index = 0
        self.timer = 0.0
        self.one_shot = None        # name of the running one-shot, or None
        self.finished = False       # a non-looping animation reached its last frame

    # ---- control ---------------------------------------------------------------------
    def set_base(self, name):
        """Switch the looping idle/walk animation (no-op while a one-shot is playing)."""
        if name != self.base:
            self.base = name
            if self.one_shot is None:
                self._start(name)

    def play(self, name, restart=True):
        """Start a one-shot animation unless something more important is still playing."""
        if self.one_shot:
            cur = ANIM_PRIORITY.get(self.one_shot, 0)
            if self.one_shot == "dead" or ANIM_PRIORITY.get(name, 0) < cur:
                return False
            if self.one_shot == name and not restart:
                return False
        self.one_shot = name
        self._start(name)
        return True

    def _start(self, name):
        self.name, self.index, self.timer, self.finished = name, 0, 0.0, False

    # ---- per frame -------------------------------------------------------------------
    def _duration(self, anim, index):
        d = anim["frame_duration_ms"]
        return (d[index] if isinstance(d, list) else d) / 1000.0

    def update(self, dt):
        anim = self.data["animations"][self.name]
        if self.finished:
            return
        self.timer += dt
        while self.timer >= self._duration(anim, self.index):
            self.timer -= self._duration(anim, self.index)
            if self.index + 1 < len(anim["frames"]):
                self.index += 1
            elif anim.get("loop"):
                self.index = 0
            elif anim.get("hold_last_frame"):
                self.finished = True
                return
            else:                                   # one-shot done -> back to idle/walk
                self.one_shot = None
                self._start(self.base)
                return

    def current(self, flipped=False):
        """(surface, pivot) for the frame to draw right now."""
        fname = self.data["animations"][self.name]["frames"][self.index]
        return self.frames[fname][flipped], self.pivot[flipped]


class Bolt:
    """Mage/archer shot. Only needs targets with .x .y .radius .take_damage(n)."""

    def __init__(self, x, y, angle, speed, max_range, damage, color):
        self.x, self.y = float(x), float(y)
        self.vx, self.vy = math.cos(angle) * speed, math.sin(angle) * speed
        self.left, self.damage, self.color, self.radius = max_range, damage, color, 5
        self.alive = True

    def update(self, dt, targets, bounds):
        step = math.hypot(self.vx, self.vy) * dt
        self.x += self.vx * dt
        self.y += self.vy * dt
        self.left -= step
        for t in targets:
            if math.hypot(t.x - self.x, t.y - self.y) <= self.radius + t.radius:
                t.take_damage(self.damage)
                self.alive = False
                return
        left, top, right, bottom = bounds
        if self.left <= 0 or not (left - 40 <= self.x <= right + 40
                                  and top - 40 <= self.y <= bottom + 40):
            self.alive = False

    def draw(self, surface):
        pos = (int(self.x), int(self.y))
        pygame.draw.circle(surface, self.color, pos, self.radius)
        pygame.draw.circle(surface, (255, 255, 255), pos, 2)


class Player:
    """Warrior, Mage or Archer. Same public shape the boss code already expects."""

    def __init__(self, x, y, char_class="warrior"):
        if char_class not in CLASS_STATS:
            raise ValueError(f"Unknown class '{char_class}'. Choose from: {list(CLASS_STATS)}")
        self.char_class = char_class
        self.stats = CLASS_STATS[char_class]

        self.x, self.y = float(x), float(y)
        self.rect = pygame.Rect(0, 0, RADIUS * 2, RADIUS * 2)
        self.rect.center = (round(self.x), round(self.y))

        self.max_hp = self.stats["hp"]
        self.hp = self.max_hp
        self.invuln = 0.0
        self.attack_time = 0.0     # swing/shot flash, for drawing
        self.attack_cd = 0.0
        self.facing = (0.0, -1.0)
        self.bolts = []
        self.god = False

        self.flipped = False       # sprite mirrored when aiming left
        self._updated = False      # did update() run since the last draw()?
        self._last_draw = pygame.time.get_ticks()
        self.anim = self._load_sprite(self.stats.get("sprite"))

    @staticmethod
    def _load_sprite(name):
        """Sprite animator for classes that have art; others keep the placeholder circle."""
        if not name:
            return None
        try:
            return SpriteAnimator(name)
        except (OSError, KeyError, ValueError, pygame.error) as exc:
            print(f"[player] no '{name}' sprites ({exc}); drawing placeholder circle")
            return None

    # ---- what the boss needs from us -----------------------------------
    def take_damage(self, amount):
        if self.god or self.hp <= 0 or self.invuln > 0:
            return 0
        self.hp = max(0, self.hp - amount)
        self.invuln = 0.7
        if self.anim:
            self.anim.play("dead" if self.hp <= 0 else "hurt")
        return amount

    # ---- per frame -------------------------------------------------------
    def update(self, dt, inp, bounds, boss):
        self._updated = True
        if self.hp <= 0:                       # dead: just let the death animation finish
            if self.anim:
                self.anim.update(dt)
            return
        self.invuln = max(0.0, self.invuln - dt)
        self.attack_time = max(0.0, self.attack_time - dt)
        self.attack_cd = max(0.0, self.attack_cd - dt)

        mx, my = inp["move"]
        length = math.hypot(mx, my)
        if length > 0:
            mx, my = mx / length, my / length
        self.x += mx * self.stats["speed"] * dt
        self.y += my * self.stats["speed"] * dt

        left, top, right, bottom = bounds
        self.x = max(left + RADIUS, min(right - RADIUS, self.x))
        self.y = max(top + RADIUS, min(bottom - RADIUS, self.y))
        self.rect.center = (round(self.x), round(self.y))

        ax, ay = inp["aim"]
        d = math.hypot(ax - self.x, ay - self.y)
        if d > 1:
            self.facing = ((ax - self.x) / d, (ay - self.y) / d)
        if abs(self.facing[0]) > 0.15:         # dead zone so aiming straight up/down doesn't flicker
            self.flipped = self.facing[0] < 0

        if inp["attack"] and self.attack_cd <= 0:
            self.attack_time = 0.18
            self.attack_cd = self.stats["cooldown"]
            self._attack(boss)
            if self.anim:
                self.anim.play("attack")

        for b in self.bolts:
            b.update(dt, boss.hittables(), bounds)
        self.bolts = [b for b in self.bolts if b.alive]

        if self.anim:
            self.anim.set_base("walk" if length > 0 else "idle")
            self.anim.update(dt)

    def _attack(self, boss):
        s = self.stats
        angle = math.atan2(self.facing[1], self.facing[0])
        if s["attack"] == "melee":
            for target in boss.hittables():
                dx, dy = target.x - self.x, target.y - self.y
                dist = math.hypot(dx, dy)
                if dist > s["range"] + target.radius:
                    continue
                if dist > target.radius + 20:
                    cos_a = max(-1.0, min(1.0, (dx * self.facing[0] + dy * self.facing[1]) / dist))
                    if math.acos(cos_a) > math.radians(75):
                        continue
                target.take_damage(s["damage"])
        else:
            self.bolts.append(Bolt(self.x + self.facing[0] * 18, self.y + self.facing[1] * 18,
                                   angle, s["proj_speed"], s["proj_range"], s["damage"],
                                   s["color"]))

    # ---- drawing -----------------------------------------------------------
    def draw(self, surface):
        for b in self.bolts:
            b.draw(surface)

        cx, cy = int(self.x), int(self.y)
        dead = self.hp <= 0
        if self.anim and not self._updated:
            # nobody called update() this frame (e.g. the game froze after death):
            # keep the animation running off the wall clock so the death still plays out.
            now = pygame.time.get_ticks()
            self.anim.update(min((now - self._last_draw) / 1000.0, 0.05))
        self._updated = False
        self._last_draw = pygame.time.get_ticks()

        # invulnerability flicker - but let the hit/death animation show clearly
        reacting = self.anim and self.anim.one_shot in ("hurt", "dead")
        if self.invuln > 0 and not reacting and int(self.invuln * 20) % 2 == 0:
            return

        if self.anim:
            self._draw_sprite(surface, cx, cy, dead)
        else:
            self._draw_placeholder(surface, cx, cy)

        if self.attack_time > 0 and self.stats["attack"] == "melee" and not dead:
            fx, fy = self.facing
            base = math.atan2(fy, fx)
            points = [(cx, cy)]
            for i in range(9):
                a = base - 1.1 + 2.2 * i / 8
                points.append((int(cx + math.cos(a) * self.stats["range"]),
                              int(cy + math.sin(a) * self.stats["range"])))
            pygame.draw.polygon(surface, (238, 237, 254), points, 2)

    def _draw_sprite(self, surface, cx, cy, dead):
        if not dead:
            pygame.draw.ellipse(surface, (18, 15, 28), (cx - 14, cy + 10, 28, 10))
        img, (px, py) = self.anim.current(self.flipped)
        surface.blit(img, (cx - px, cy - py))
        if not dead:                           # small aim tick just outside the sprite
            fx, fy = self.facing
            pygame.draw.line(surface, (238, 237, 254),
                             (int(cx + fx * 30), int(cy + fy * 30)),
                             (int(cx + fx * 38), int(cy + fy * 38)), 3)

    def _draw_placeholder(self, surface, cx, cy):
        color = self.stats["color"]
        pygame.draw.ellipse(surface, (18, 15, 28), (cx - 14, cy + 10, 28, 10))
        pygame.draw.circle(surface, color, (cx, cy), RADIUS)
        pygame.draw.circle(surface, (20, 20, 30), (cx, cy), RADIUS, 2)
        fx, fy = self.facing
        pygame.draw.line(surface, (238, 237, 254), (cx, cy), (int(cx + fx * 22), int(cy + fy * 22)), 3)
