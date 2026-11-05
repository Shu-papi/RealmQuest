"""
skills.py - The hero's skills: two per class plus a special, usable in the overworld and
in dungeons.

    pools  = Pools(classes.stats("mage")["bars"])     # stamina + mana / energy
    caster = SkillCaster("mage")
    fx     = SkillFX()

    caster.update(dt); pools.update(dt)
    caster.cast("skill", pools, x, y, aim, power, fx)   # slot: "skill" / "skill_2" / "special"
    fx.update(dt, targets, owner, blocked)               # moves projectiles, deals damage
    fx.draw(surface, cam_x, cam_y, t)

Targets are any objects with x, y (feet), radius, dead and take_damage(n). Optional:
stun_t / slow_t (crowd control), aggro (wakes up when hit), cc_immune (bosses).
`power` is the hero's basic-attack damage; every skill scales from it.
"""
from __future__ import annotations

import math
import random
from dataclasses import dataclass

import pygame

try:
    from . import classes
except ImportError:          # imported as a top-level module
    import classes

SLOTS = ("skill", "skill_2", "special")
BODY = 14                    # sprites stand on (x, y); their middle is this far above


@dataclass(frozen=True)
class SkillDef:
    id: str
    name: str
    slot: str
    cost: int
    cooldown: float
    desc: str
    color: tuple


CLASS_SKILLS = {
    "warrior": [
        SkillDef("whirlwind", "Whirlwind", "skill", 30, 4.0,
                 "Spin with your sword and hit everything around you.", (236, 240, 255)),
        SkillDef("shield_bash", "Shield Bash", "skill_2", 25, 6.0,
                 "Lunge forward and stun what you hit.", (214, 176, 84)),
        SkillDef("earthsplitter", "Earthsplitter", "special", 60, 25.0,
                 "SPECIAL: smash the ground in a huge cone.", (240, 150, 70)),
    ],
    "mage": [
        SkillDef("fireball", "Fireball", "skill", 22, 1.6,
                 "A blazing orb that explodes on impact.", (255, 140, 50)),
        SkillDef("frost_nova", "Frost Nova", "skill_2", 30, 7.0,
                 "A ring of ice that chills and slows nearby foes.", (150, 220, 255)),
        SkillDef("meteor", "Meteor", "special", 70, 25.0,
                 "SPECIAL: call a meteor down where you face.", (255, 90, 60)),
    ],
    "archer": [
        SkillDef("arrow_volley", "Arrow Volley", "skill", 20, 2.2,
                 "Loose three arrows in a spread.", (230, 220, 180)),
        SkillDef("piercing_shot", "Piercing Shot", "skill_2", 30, 5.0,
                 "A charged arrow that passes through every enemy.", (170, 240, 160)),
        SkillDef("rain_of_arrows", "Rain of Arrows", "special", 60, 25.0,
                 "SPECIAL: arrows rain on an area for three seconds.", (210, 230, 130)),
    ],
}


def skills_for(character_class):
    return CLASS_SKILLS.get(character_class, CLASS_SKILLS["warrior"])


# =========================================================================== resources
class Pools:
    """Stamina plus mana or energy: {name: [current, max, regen per second]}."""

    def __init__(self, bars):
        self.bars = {name: [float(mx), float(mx), float(regen)] for name, mx, regen in bars}
        self.order = [name for name, _mx, _r in bars]

    def has(self, name):
        return name in self.bars

    def get(self, name):
        return self.bars[name][0] if name in self.bars else 0.0

    def max(self, name):
        return self.bars[name][1] if name in self.bars else 0.0

    def can_spend(self, name, amount):
        return name in self.bars and self.bars[name][0] >= amount - 1e-6

    def spend(self, name, amount):
        if not self.can_spend(name, amount):
            return False
        self.bars[name][0] -= amount
        return True

    def add(self, name, amount):
        if name in self.bars:
            b = self.bars[name]
            b[0] = min(b[1], b[0] + amount)

    def refill(self):
        for b in self.bars.values():
            b[0] = b[1]

    def update(self, dt):
        for b in self.bars.values():
            b[0] = min(b[1], b[0] + b[2] * dt)


# =========================================================================== caster
class SkillCaster:
    def __init__(self, character_class):
        self.character_class = character_class
        self.resource = classes.stats(character_class)["skill_resource"]
        self.defs = {d.slot: d for d in skills_for(character_class)}
        self.cd = {slot: 0.0 for slot in SLOTS}

    def update(self, dt):
        for slot in self.cd:
            self.cd[slot] = max(0.0, self.cd[slot] - dt)

    def cooldown_fraction(self, slot):
        d = self.defs[slot]
        return self.cd[slot] / d.cooldown if d.cooldown else 0.0

    def can_cast(self, slot, pools):
        d = self.defs.get(slot)
        return d is not None and self.cd[slot] <= 0 and pools.can_spend(self.resource, d.cost)

    def cast(self, slot, pools, x, y, aim, power, fx):
        """Spend, start the cooldown and spawn the skill's effects. Returns the SkillDef or None."""
        if not self.can_cast(slot, pools):
            return None
        d = self.defs[slot]
        pools.spend(self.resource, d.cost)
        self.cd[slot] = d.cooldown
        ax, ay = aim
        n = math.hypot(ax, ay)
        ax, ay = (ax / n, ay / n) if n > 1e-6 else (0.0, 1.0)
        SPAWN[d.id](fx, x, y, ax, ay, max(1, power), d)
        fx.sounds.append(d.id)
        return d


# =========================================================================== effects
class _Effect:
    done = False

    def update(self, dt, fx, targets, owner, blocked):
        pass

    def draw(self, surf, cx, cy, t):
        pass


def _hit(fx, target, dmg, stun=0.0, slow=0.0, src=None):
    if getattr(target, "dead", False):
        return
    target.take_damage(dmg)
    if not getattr(target, "cc_immune", False):
        if stun:
            target.stun_t = max(getattr(target, "stun_t", 0.0), stun)
        if slow:
            target.slow_t = max(getattr(target, "slow_t", 0.0), slow)
    if hasattr(target, "aggro"):
        target.aggro = True
    fx.hits += 1
    fx.floaters.append([target.x, target.y - BODY - 26, str(int(dmg)), 0.8,
                        (255, 238, 150) if not stun else (255, 210, 120)])


def _in_arc(dx, dy, ax, ay, half):
    if half is None:
        return True
    d = math.hypot(dx, dy)
    if d < 1e-6:
        return True
    return (dx * ax + dy * ay) / d >= math.cos(half)


class Burst(_Effect):
    """Hits once (after `delay`) everything within `radius` (and an optional cone)."""

    def __init__(self, x, y, radius, dmg, style, color, delay=0.0, aim=(1.0, 0.0), half=None,
                 stun=0.0, slow=0.0, follow=False, life=0.4):
        self.x, self.y, self.radius, self.dmg = x, y, radius, dmg
        self.style, self.color = style, color
        self.delay, self.aim, self.half = delay, aim, half
        self.stun, self.slow, self.follow = stun, slow, follow
        self.life = self.total = life
        self.fired = False
        self.t = 0.0

    def update(self, dt, fx, targets, owner, blocked):
        self.t += dt
        if self.follow and owner is not None:
            self.x, self.y = owner.x, owner.y
        if not self.fired:
            if self.t < self.delay:
                return
            self.fired = True
            for tg in targets:
                dx, dy = tg.x - self.x, tg.y - self.y
                if math.hypot(dx, dy) <= self.radius + getattr(tg, "radius", 12) and \
                        _in_arc(dx, dy, self.aim[0], self.aim[1], self.half):
                    _hit(fx, tg, self.dmg, self.stun, self.slow)
            if self.style == "meteor":
                fx.sounds.append("boom")
        else:
            self.life -= dt
            if self.life <= 0:
                self.done = True

    def draw(self, surf, cx, cy, t):
        X, Y = int(self.x - cx), int(self.y - cy)
        R = int(self.radius)
        if self.style == "meteor" and not self.fired:
            k = min(1.0, self.t / max(0.01, self.delay))
            _ring(surf, X, Y, R, (255, 70, 50), int(90 + 120 * k), 3, squash=0.55)
            _ring(surf, X, Y, int(R * k), (255, 120, 60), 120, 2, squash=0.55)
            my = Y - BODY - int((1 - k) * 360)
            mx = X + int((1 - k) * 140)
            _glow(surf, mx, my, 34, (255, 120, 40))
            pygame.draw.circle(surf, (90, 40, 30), (mx, my), 15)
            pygame.draw.circle(surf, (255, 150, 60), (mx, my), 11)
            pygame.draw.circle(surf, (255, 240, 170), (mx - 3, my - 3), 5)
            return
        if not self.fired:
            return
        k = max(0.0, self.life / self.total)            # 1 -> 0
        grow = 1.0 - k
        if self.style == "whirl":
            layer = pygame.Surface((R * 2 + 8, R * 2 + 8), pygame.SRCALPHA)
            c = R + 4
            for i in range(3):
                a0 = t * 14 + i * 2.09
                rect = pygame.Rect(c - R, c - R, R * 2, R * 2)
                pygame.draw.arc(layer, (*self.color, int(230 * k)), rect, a0, a0 + 1.4, 6)
                pygame.draw.arc(layer, (255, 255, 255, int(160 * k)), rect.inflate(-16, -16), a0, a0 + 1.0, 2)
            surf.blit(layer, (X - c, Y - BODY - c))
        elif self.style in ("bash", "earth"):
            ang = math.atan2(self.aim[1], self.aim[0])
            rr = R * (0.55 + 0.45 * grow) if self.style == "earth" else R
            pts = [(X, Y - BODY)]
            for i in range(13):
                a = ang - self.half + 2 * self.half * i / 12
                pts.append((X + math.cos(a) * rr, Y - BODY + math.sin(a) * rr))
            layer = pygame.Surface(surf.get_size(), pygame.SRCALPHA)
            pygame.draw.polygon(layer, (*self.color, int(110 * k)), pts)
            pygame.draw.lines(layer, (255, 245, 220, int(220 * k)), False, pts[1:], 3)
            if self.style == "earth":
                rng = random.Random(int(self.x * 7 + self.y))
                for _ in range(7):
                    a = ang + rng.uniform(-self.half, self.half)
                    ln = rr * rng.uniform(0.5, 1.0)
                    pygame.draw.line(layer, (60, 36, 20, int(230 * k)), (X, Y),
                                     (X + math.cos(a) * ln, Y + math.sin(a) * ln * 0.8), 3)
            surf.blit(layer, (0, 0))
        elif self.style == "frost":
            rr = int(R * (0.3 + 0.7 * grow))
            _ring(surf, X, Y - BODY // 2, rr, self.color, int(220 * k), 6, squash=0.7)
            _ring(surf, X, Y - BODY // 2, max(1, rr - 10), (255, 255, 255), int(160 * k), 2, squash=0.7)
            for i in range(10):
                a = i * math.tau / 10 + 0.3
                sx, sy = X + math.cos(a) * rr, Y - BODY // 2 + math.sin(a) * rr * 0.7
                pygame.draw.polygon(surf, (220, 245, 255), [(sx, sy - 9), (sx + 4, sy), (sx, sy + 4), (sx - 4, sy)])
        else:                                            # explosion / meteor impact
            rr = int(R * (0.4 + 0.6 * grow))
            _glow(surf, X, Y - BODY, int(rr * 1.4), self.color)
            _ring(surf, X, Y - BODY // 2, rr, (255, 220, 140), int(230 * k), 4, squash=0.75)


class Projectile(_Effect):
    def __init__(self, x, y, ax, ay, speed, reach, dmg, style, color, radius=10, pierce=False,
                 explode=None):
        self.x, self.y = x, y
        self.vx, self.vy = ax * speed, ay * speed
        self.left = reach
        self.dmg, self.style, self.color, self.radius = dmg, style, color, radius
        self.pierce, self.explode = pierce, explode
        self.hit_ids = set()
        self.trail = []

    def _end(self, fx):
        self.done = True
        if self.explode:
            r, dmg = self.explode
            fx.add(Burst(self.x, self.y, r, dmg, "boom", (255, 120, 40), life=0.35))
            fx.sounds.append("boom")

    def update(self, dt, fx, targets, owner, blocked):
        steps = 3
        for _ in range(steps):
            self.x += self.vx * dt / steps
            self.y += self.vy * dt / steps
            if blocked is not None and blocked(self.x, self.y):
                self._end(fx)
                return
            for tg in targets:
                if id(tg) in self.hit_ids or getattr(tg, "dead", False):
                    continue
                if math.hypot(tg.x - self.x, tg.y - self.y) <= self.radius + getattr(tg, "radius", 12):
                    self.hit_ids.add(id(tg))
                    if self.explode:
                        self._end(fx)
                        return
                    _hit(fx, tg, self.dmg)
                    if not self.pierce:
                        self.done = True
                        return
        self.trail.append((self.x, self.y))
        self.trail = self.trail[-8:]
        self.left -= math.hypot(self.vx, self.vy) * dt
        if self.left <= 0:
            self._end(fx)

    def draw(self, surf, cx, cy, t):
        X, Y = int(self.x - cx), int(self.y - cy - BODY)
        sp = math.hypot(self.vx, self.vy) or 1
        ux, uy = self.vx / sp, self.vy / sp
        if self.style == "fire":
            for i, (tx, ty) in enumerate(self.trail):
                r = 2 + i
                pygame.draw.circle(surf, (255, 120 + i * 12, 40), (int(tx - cx), int(ty - cy - BODY)), r)
            _glow(surf, X, Y, 26, (255, 120, 40))
            pygame.draw.circle(surf, (200, 60, 20), (X, Y), 9)
            pygame.draw.circle(surf, (255, 190, 80), (X, Y), 6)
            pygame.draw.circle(surf, (255, 250, 210), (X - 2, Y - 2), 3)
        else:
            ln = 26 if self.style == "arrow" else 40
            tail = (X - ux * ln, Y - uy * ln)
            if self.style == "pierce":
                _glow(surf, X, Y, 22, (120, 230, 120))
                pygame.draw.line(surf, (190, 255, 180), tail, (X, Y), 5)
            pygame.draw.line(surf, (120, 84, 50), tail, (X, Y), 3)
            px, py = -uy, ux
            head = [(X + ux * 8, Y + uy * 8), (X + px * 5, Y + py * 5), (X - px * 5, Y - py * 5)]
            pygame.draw.polygon(surf, (220, 224, 236), head)
            fx_ = (tail[0] + px * 4, tail[1] + py * 4), (tail[0] - px * 4, tail[1] - py * 4)
            pygame.draw.line(surf, self.color, fx_[0], fx_[1], 3)


class Zone(_Effect):
    """Rain of Arrows: hits everything inside every `interval` seconds for `duration`."""

    def __init__(self, x, y, radius, dmg, interval, duration, color):
        self.x, self.y, self.radius, self.dmg = x, y, radius, dmg
        self.interval, self.left, self.color = interval, duration, color
        self.tick = 0.15
        self.rng = random.Random(int(x + y))
        self.streaks = []

    def update(self, dt, fx, targets, owner, blocked):
        self.left -= dt
        self.tick -= dt
        if self.tick <= 0:
            self.tick = self.interval
            for tg in targets:
                if math.hypot(tg.x - self.x, tg.y - self.y) <= self.radius + getattr(tg, "radius", 12):
                    _hit(fx, tg, self.dmg)
        for s in self.streaks:
            s[2] -= dt
        self.streaks = [s for s in self.streaks if s[2] > 0]
        for _ in range(3):
            a, r = self.rng.random() * math.tau, self.radius * math.sqrt(self.rng.random())
            self.streaks.append([self.x + math.cos(a) * r, self.y + math.sin(a) * r * 0.7, 0.25])
        if self.left <= 0:
            self.done = True

    def draw(self, surf, cx, cy, t):
        X, Y = int(self.x - cx), int(self.y - cy)
        _ring(surf, X, Y, int(self.radius), self.color, 170, 3, squash=0.7)
        for sx, sy, life in self.streaks:
            k = life / 0.25
            ex, ey = int(sx - cx), int(sy - cy)
            top = ey - int(70 * k) - 10
            pygame.draw.line(surf, (110, 80, 50), (ex - 6, top), (ex, ey - int(30 * k)), 2)
            pygame.draw.line(surf, (230, 230, 240), (ex, ey - int(30 * k)), (ex + 1, ey - int(30 * k) + 5), 2)


def _ring(surf, x, y, r, color, alpha, width, squash=1.0):
    if r <= 0:
        return
    w, h = r * 2 + width * 2, int(r * 2 * squash) + width * 2
    layer = pygame.Surface((w, h), pygame.SRCALPHA)
    pygame.draw.ellipse(layer, (*color[:3], max(0, min(255, alpha))), (0, 0, w, h), width)
    surf.blit(layer, (x - w // 2, y - h // 2))


_GLOWS = {}


def _glow(surf, x, y, r, color):
    key = (r, color)
    g = _GLOWS.get(key)
    if g is None:
        g = pygame.Surface((r * 2, r * 2), pygame.SRCALPHA)
        for i in range(r, 0, -2):
            a = int(110 * (1 - i / r) ** 1.5)
            pygame.draw.circle(g, (*color[:3], a), (r, r), i)
        _GLOWS[key] = g
    surf.blit(g, (x - r, y - r))


# =========================================================================== spawners
def _whirlwind(fx, x, y, ax, ay, p, d):
    fx.add(Burst(x, y, 96, int(p * 1.5) + 1, "whirl", d.color, follow=True, life=0.45))


def _shield_bash(fx, x, y, ax, ay, p, d):
    fx.lunge = (ax, ay)
    fx.add(Burst(x + ax * 40, y + ay * 40, 70, p * 2, "bash", d.color, delay=0.12, aim=(ax, ay),
                 half=0.9, stun=1.0, life=0.3))


def _earthsplitter(fx, x, y, ax, ay, p, d):
    fx.add(Burst(x, y, 210, p * 5 + 4, "earth", d.color, delay=0.18, aim=(ax, ay), half=0.62,
                 stun=0.6, life=0.6))
    fx.shake = 0.35


def _fireball(fx, x, y, ax, ay, p, d):
    fx.add(Projectile(x + ax * 20, y + ay * 20, ax, ay, 520, 520, 0, "fire", d.color, radius=12,
                      explode=(62, int(p * 2.5) + 1)))


def _frost_nova(fx, x, y, ax, ay, p, d):
    fx.add(Burst(x, y, 120, p + 1, "frost", d.color, slow=2.5, life=0.5))


def _meteor(fx, x, y, ax, ay, p, d):
    fx.add(Burst(x + ax * 170, y + ay * 170, 100, p * 6 + 4, "meteor", d.color, delay=0.8, life=0.5))
    fx.shake = 0.3


def _volley(fx, x, y, ax, ay, p, d):
    base = math.atan2(ay, ax)
    for off in (-0.22, 0.0, 0.22):
        a = base + off
        fx.add(Projectile(x + math.cos(a) * 18, y + math.sin(a) * 18, math.cos(a), math.sin(a), 640, 560,
                          int(p * 1.5) + 1, "arrow", d.color, radius=9))


def _piercing(fx, x, y, ax, ay, p, d):
    fx.add(Projectile(x + ax * 18, y + ay * 18, ax, ay, 820, 720, p * 3 + 1, "pierce", d.color, radius=12,
                      pierce=True))


def _rain(fx, x, y, ax, ay, p, d):
    fx.add(Zone(x + ax * 150, y + ay * 150, 110, max(1, p), 0.4, 3.0, d.color))


SPAWN = {
    "whirlwind": _whirlwind, "shield_bash": _shield_bash, "earthsplitter": _earthsplitter,
    "fireball": _fireball, "frost_nova": _frost_nova, "meteor": _meteor,
    "arrow_volley": _volley, "piercing_shot": _piercing, "rain_of_arrows": _rain,
}


class SkillFX:
    """Every live skill effect in the current place (overworld or one dungeon floor)."""

    def __init__(self):
        self.effects: list[_Effect] = []
        self.floaters: list[list] = []        # [x, y, text, life, colour] damage numbers
        self.sounds: list[str] = []           # for the Game to play
        self.hits = 0                         # hits since the Game last read it
        self.lunge = None                     # (dx, dy) when Shield Bash wants the hero to lunge
        self.shake = 0.0

    def add(self, effect):
        self.effects.append(effect)

    def clear(self):
        self.effects.clear()
        self.floaters.clear()
        self.lunge = None

    def update(self, dt, targets, owner=None, blocked=None):
        targets = [tg for tg in targets if not getattr(tg, "dead", False)]
        for e in list(self.effects):
            e.update(dt, self, targets, owner, blocked)
        self.effects = [e for e in self.effects if not e.done]
        for f in self.floaters:
            f[1] -= 40 * dt
            f[3] -= dt
        self.floaters = [f for f in self.floaters if f[3] > 0]
        self.shake = max(0.0, self.shake - dt)

    def draw(self, surf, cx, cy, t, font=None):
        for e in self.effects:
            e.draw(surf, cx, cy, t)
        if self.floaters:
            font = font or pygame.font.Font(None, 26)
            for x, y, text, life, col in self.floaters:
                img = font.render(text, True, col)
                sh = font.render(text, True, (20, 10, 10))
                a = int(255 * min(1.0, life / 0.3))
                img.set_alpha(a)
                sh.set_alpha(a)
                X, Y = int(x - cx) - img.get_width() // 2, int(y - cy)
                surf.blit(sh, (X + 2, Y + 2))
                surf.blit(img, (X, Y))
