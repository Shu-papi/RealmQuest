"""
archer.py - Skeleton Archer: stays away from you and shoots.

BEHAVIOUR
    chase    Keeps a comfortable distance: backs off if you get close, walks in if you are far,
             and sidesteps while it waits for its next shot.
    windup   Draws the bow (a glow grows at the bow tip). It stops tracking you a split second
             before it shoots, so a well-timed sidestep or dash dodges it. There is no aim line.
    strike   Releases an arrow (glowing head, fast).
    BASIC ATTACK  "snap shot": about 4 shots in 10 are a quick snap shot instead of a full draw
             (tiny wind-up, faster arrow, 70% damage, shorter pause), so it keeps up the pressure.
    recover  Short pause. Weak up close: it only has 14 HP.
"""
import math

import pygame

from ..attacks import Arrow, player_pos
from ..base_monster import Monster
from ..sprites import glow_color


class SkeletonArcher(Monster):
    NAME = "skeleton_archer"
    SFX_WINDUP = "bow_draw"
    SFX_STRIKE = "arrow_shoot"
    DISPLAY_NAME = "Skeleton Archer"
    MAX_HP = 14
    RADIUS = 13
    SPEED = 72.0
    DAMAGE = 9
    FOOT = 30
    XP = 8
    GOLD = (1, 5)
    LOOT = (("Bone Dust", 0.5), ("Bone Arrows", 0.3), ("Hooded Cloak Scrap", 0.12))

    PREFERRED = (200, 330)          # it likes to stand between these distances from you
    SHOOT_RANGE = (90, 480)
    WINDUP_TIME = 0.5
    SNAP_CHANCE = 0.4
    SNAP_WINDUP = 0.2
    SNAP_SPEED = 720.0
    SNAP_DAMAGE = 0.7
    SNAP_COOLDOWN = (0.5, 0.9)
    STRIKE_TIME = 0.18
    RECOVER_TIME = 0.45
    AIM_LOCK = 0.15
    ARROW_SPEED = 650.0
    COOLDOWN = (0.9, 1.5)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.cooldown = self.rng.uniform(0.8, 1.6)
        self.aim = 0.0
        self.snap = False
        self.target = (self.x, self.y)
        self.strafe = self.rng.choice((-1, 1))
        self.strafe_timer = self.rng.uniform(1.5, 3.0)

    def think(self, dt, player, bounds):
        px, py = player_pos(player)
        dx, dy, dist = self.vector_to(px, py)
        self.face(px)
        self.target = (px, py)

        if self.state == "chase":
            self._do_chase(dt, dx, dy, dist)
        elif self.state == "windup":
            if self.state_time < self.windup_time - self.AIM_LOCK:
                self.aim = self._aim_at(px, py)
            if self.state_time >= self.windup_time:
                self._shoot()
                self.set_state("strike")
        elif self.state == "strike":
            if self.state_time >= self.STRIKE_TIME:
                self.cooldown = self.rng.uniform(*(self.SNAP_COOLDOWN if self.snap else self.COOLDOWN))
                self.set_state("recover")
        elif self.state == "recover":
            if self.state_time >= self.RECOVER_TIME:
                self.set_state("chase")

    def _do_chase(self, dt, dx, dy, dist):
        near, far = self.PREFERRED
        self.strafe_timer -= dt
        if self.strafe_timer <= 0:
            self.strafe = -self.strafe
            self.strafe_timer = self.rng.uniform(1.5, 3.0)
        if dist < near and dist > 0:
            self.move(-dx, -dy, self.speed * 1.15, dt)           # back away
        elif dist > far:
            self.move(dx, dy, self.speed, dt)                     # close in
        elif dist > 0:
            self.move(-dy * self.strafe, dx * self.strafe, self.speed * 0.45, dt)   # sidestep
        if self.cooldown <= 0 and self.SHOOT_RANGE[0] <= dist <= self.SHOOT_RANGE[1]:
            self.aim = self._aim_at(*self.target)
            self.snap = self.rng.random() < self.SNAP_CHANCE
            self.begin_windup(self.SNAP_WINDUP if self.snap else self.WINDUP_TIME)

    def bow_pos(self):
        """Where the bow is on screen (his bow arm points to the right of the sprite, or left if flipped)."""
        return self.x + (-30 if self.flip else 30), self.y - 18

    def _aim_at(self, px, py):
        bx, by = self.bow_pos()
        return math.atan2(py - by, px - bx)

    def _shoot(self):
        ox, oy = self.bow_pos()
        speed = self.SNAP_SPEED if self.snap else self.ARROW_SPEED
        damage = max(1, int(round(self.damage * self.SNAP_DAMAGE))) if self.snap else self.damage
        self.projectiles.append(Arrow(ox, oy, self.aim, speed, damage, self.variant))
        self.x -= math.cos(self.aim) * 4                          # a tiny recoil
        self.y -= math.sin(self.aim) * 4

    def draw_effects(self, surface):
        if self.state == "windup":
            bx, by = self.bow_pos()
            pygame.draw.circle(surface, glow_color(self.variant, "eye", 5),
                               (int(bx + math.cos(self.aim) * 14), int(by + math.sin(self.aim) * 14)),
                               2 + int(self.windup_progress * 4))
