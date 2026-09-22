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
import math

import pygame

CLASS_STATS = {
    "warrior": {"hp": 120, "speed": 200, "color": (180, 50, 50),
                "attack": "melee", "damage": 15, "cooldown": 0.8, "range": 62},
    "mage":    {"hp": 70,  "speed": 240, "color": (130, 70, 200),
                "attack": "ranged", "damage": 20, "cooldown": 0.9,
                "proj_speed": 420, "proj_range": 480},
    "archer":  {"hp": 90,  "speed": 280, "color": (60, 150, 70),
                "attack": "ranged", "damage": 12, "cooldown": 0.4,
                "proj_speed": 620, "proj_range": 560},
}
RADIUS = 14


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

    # ---- what the boss needs from us -----------------------------------
    def take_damage(self, amount):
        if self.god or self.hp <= 0 or self.invuln > 0:
            return 0
        self.hp = max(0, self.hp - amount)
        self.invuln = 0.7
        return amount

    # ---- per frame -------------------------------------------------------
    def update(self, dt, inp, bounds, boss):
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

        if inp["attack"] and self.attack_cd <= 0:
            self.attack_time = 0.18
            self.attack_cd = self.stats["cooldown"]
            self._attack(boss)

        for b in self.bolts:
            b.update(dt, boss.hittables(), bounds)
        self.bolts = [b for b in self.bolts if b.alive]

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
        if self.invuln > 0 and int(self.invuln * 20) % 2 == 0:
            return
        color = self.stats["color"]
        pygame.draw.ellipse(surface, (18, 15, 28), (cx - 14, cy + 10, 28, 10))
        pygame.draw.circle(surface, color, (cx, cy), RADIUS)
        pygame.draw.circle(surface, (20, 20, 30), (cx, cy), RADIUS, 2)
        fx, fy = self.facing
        pygame.draw.line(surface, (238, 237, 254), (cx, cy), (int(cx + fx * 22), int(cy + fy * 22)), 3)

        if self.attack_time > 0 and self.stats["attack"] == "melee":
            base = math.atan2(fy, fx)
            points = [(cx, cy)]
            for i in range(9):
                a = base - 1.1 + 2.2 * i / 8
                points.append((int(cx + math.cos(a) * self.stats["range"]),
                              int(cy + math.sin(a) * self.stats["range"])))
            pygame.draw.polygon(surface, (238, 237, 254), points, 2)
