"""
acolyte.py - Skeleton Acolyte: a floating priest that keeps the others fighting.

It is fragile (16 HP) but it makes every fight harder while it lives, so kill it first!

BEHAVIOUR
    chase    Hovers away from you and drifts toward its friends.
    MEND     Beams life into the most wounded skeleton nearby (green beam, you can see it coming).
    RAISE    If the group is small, it raises a new Skeleton Warrior from the ground nearby.
    BOLT     If nothing else needs doing, it fires a slow bolt of dark magic at you.
    It will not start these while staggered: a hit during the wind-up interrupts it.
"""
import math

import pygame

try:
    import audio                                             # src/ is on sys.path
except ImportError:                                          # run as src.monsters
    from src import audio

from ..attacks import SoulBolt, player_pos
from ..base_monster import Monster
from ..fx import dotted_line, pixel_ring
from ..sprites import glow_color


class SkeletonAcolyte(Monster):
    NAME = "skeleton_acolyte"
    SFX_WINDUP = "acolyte_charge"
    DISPLAY_NAME = "Skeleton Acolyte"
    MAX_HP = 16
    RADIUS = 14
    SPEED = 62.0
    DAMAGE = 10
    FOOT = 36
    XP = 14
    GOLD = (4, 12)
    LOOT = (("Bone Dust", 0.5), ("Acolyte Orb", 0.25), ("Violet Robe Scrap", 0.4))

    SPAWN_TIME = 1.0
    STEP_LENGTH = 8.0               # he glides: long, slow ripples of the robe

    MEND_RANGE = 280
    MEND_AMOUNT = 14
    MEND_BELOW = 0.7                # heals friends below this fraction of their HP
    RAISE_CAP = 4                   # will not raise the dead when this many friends are alive
    RAISE_COOLDOWN = 11.0
    BOLT_RANGE = (120, 430)
    BOLT_SPEED = 400.0
    WINDUPS = {"mend": 0.9, "raise": 1.3, "bolt": 0.55}
    STRIKE_TIME = 0.25
    RECOVER_TIME = 0.5
    ACTION_COOLDOWN = 2.4

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.cooldown = self.rng.uniform(1.2, 2.2)
        self.raise_cooldown = 5.0
        self.action = None
        self.target = None              # the friend being mended
        self.raise_spot = (self.x, self.y)
        self.aim = 0.0
        self.hover_seed = self.rng.uniform(0, math.tau)

    def cast_pos(self):
        """Where his glowing casting hand is on screen."""
        return self.x + (34 if self.flip else -34), self.y - 12

    # ---------- deciding what to do ----------

    def friends(self):
        return [m for m in self.allies if m is not self and m.is_alive() and not m.spawning]

    def _wounded_friend(self):
        best, best_ratio = None, self.MEND_BELOW
        for m in self.friends():
            ratio = m.hp / m.max_hp
            if ratio < best_ratio and math.hypot(m.x - self.x, m.y - self.y) <= self.MEND_RANGE:
                best, best_ratio = m, ratio
        return best

    def _choose_action(self, dist_to_player):
        wounded = self._wounded_friend()
        if wounded is not None:
            return "mend", wounded
        if self.raise_cooldown <= 0 and len(self.friends()) < self.RAISE_CAP:
            return "raise", None
        if self.BOLT_RANGE[0] <= dist_to_player <= self.BOLT_RANGE[1]:
            return "bolt", None
        return None, None

    def think(self, dt, player, bounds):
        px, py = player_pos(player)
        dx, dy, dist = self.vector_to(px, py)
        self.face(px)
        self.raise_cooldown = max(0.0, self.raise_cooldown - dt)

        if self.state == "chase":
            self._do_chase(dt, dx, dy, dist, bounds)
            if self.cooldown <= 0:
                action, target = self._choose_action(dist)
                if action:
                    self._begin(action, target, dx, dy, bounds)
        elif self.state == "windup":
            self._do_windup(dx, dy)
        elif self.state == "strike":
            if self.state_time >= self.STRIKE_TIME:
                self.set_state("recover")
        elif self.state == "recover":
            if self.state_time >= self.RECOVER_TIME:
                self.set_state("chase")

    def _do_chase(self, dt, dx, dy, dist, bounds):
        if dist < 160 and dist > 0:
            self.move(-dx, -dy, self.speed * 1.25, dt)            # keep away from you
        elif dist > 380:
            self.move(dx, dy, self.speed, dt)
        else:
            friends = self.friends()
            if friends:                                              # drift toward the group
                fx = sum(m.x for m in friends) / len(friends)
                fy = sum(m.y for m in friends) / len(friends)
                if math.hypot(fx - self.x, fy - self.y) > 140:
                    self.move(fx - self.x, fy - self.y, self.speed * 0.6, dt)

    def _begin(self, action, target, dx, dy, bounds):
        self.action = action
        self.target = target
        cx, cy = self.cast_pos()
        self.aim = math.atan2(self.y + dy - cy, self.x + dx - cx)
        if action == "raise":
            left, top, right, bottom = bounds
            angle = self.rng.uniform(0, math.tau)
            dist = self.rng.uniform(70, 120)
            self.raise_spot = (max(left + 30, min(right - 30, self.x + math.cos(angle) * dist)),
                               max(top + 30, min(bottom - 30, self.y + math.sin(angle) * dist)))
        self.begin_windup(self.WINDUPS[action])

    def _do_windup(self, dx, dy):
        if self.action == "mend" and (self.target is None or not self.target.is_alive()):
            self._finish_action(0.5)                                # its friend died: cancelled
            return
        if self.action == "bolt":
            cx, cy = self.cast_pos()
            self.aim = math.atan2(self.y + dy - cy, self.x + dx - cx)
        if self.state_time >= self.windup_time:
            self._cast()
            self.set_state("strike")

    def _cast(self):
        if self.action == "mend":
            if self.target is not None and self.target.is_alive():
                audio.play("acolyte_mend", self.x)
                self.target.heal(int(round(self.MEND_AMOUNT * self.max_hp / self.MAX_HP)))   # tougher tier = stronger mend
        elif self.action == "raise":
            from .. import spawn_monster                              # noqa: PLC0415 (avoids a cycle)
            audio.play("acolyte_raise", self.x)
            x, y = self.raise_spot
            self.spawn_requests.append(
                spawn_monster("skeleton_warrior", x, y, variant=self.variant,
                              seed=self.rng.random(),
                              hp_scale=self.max_hp / self.MAX_HP,         # raised dead are as tough as their
                              damage_scale=self.damage / self.DAMAGE,     # master's tier (normal stays normal)
                              speed_scale=self.speed / self.SPEED))
            self.raise_cooldown = self.RAISE_COOLDOWN
        elif self.action == "bolt":
            cx, cy = self.cast_pos()
            audio.play("acolyte_bolt", self.x)
            self.projectiles.append(SoulBolt(cx, cy, self.aim, self.BOLT_SPEED, self.damage, self.variant))
        self.cooldown = self.ACTION_COOLDOWN
        self.target = None

    def _finish_action(self, cooldown):
        self.cooldown = cooldown
        self.target = None
        self.action = None
        self.set_state("chase")

    def on_hurt(self, amount):
        if self.state == "windup":                                  # a hit breaks the spell
            self.cooldown = 1.2
            self.target = None
            self.set_state("chase")

    # ---------- the magic you can see ----------

    def draw_floor(self, surface):
        super().draw_floor(surface)
        if self.state == "windup" and self.action == "raise":
            x, y = self.raise_spot
            r = 12 + 16 * self.windup_progress
            color = glow_color(self.variant, "glow", 3)
            pixel_ring(surface, (x, y), r, r * 0.55, color, phase=self.clock * 2)
            pixel_ring(surface, (x, y), r * 0.5, r * 0.28, color, phase=-self.clock * 3, count=8)

    def draw_effects(self, surface):
        if self.state in ("windup", "strike") and self.action == "mend" and self.target is not None:
            if self.target.is_alive():
                cx, cy = self.cast_pos()
                dotted_line(surface, (cx, cy), (self.target.x, self.target.y - 6),
                            (151, 196, 89), dot=3, gap=8)
                pygame.draw.circle(surface, (151, 196, 89), (int(self.target.x), int(self.target.y) - 6),
                                   int(8 + 8 * self.windup_progress), 2)
        if self.state == "windup" and self.action == "bolt":
            glow = glow_color(self.variant, "glow", 4)
            cx, cy = self.cast_pos()
            pygame.draw.circle(surface, glow, (int(cx), int(cy)), int(3 + 7 * self.windup_progress), 2)
