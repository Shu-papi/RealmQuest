"""
warrior.py - Skeleton Warrior: the basic melee skeleton (and the simplest monster to read).

BEHAVIOUR
    chase    Walks at you, circling a little so a crowd doesn't walk in a straight line.
    windup   Lifts its sword. A red lane appears on the floor in the direction it will lunge.
    strike   Lunges forward fast. Hurts you once if it reaches you. Dash sideways to dodge!
    recover  Wide open for a counter-attack.
    BASIC ATTACK  "slash": if you stand right next to it, it chops at you almost instantly (no lane,
             a tiny wind-up, 65% damage, a short hop). Don't hug a warrior!
"""
import math

from ..attacks import player_pos
from ..base_monster import Monster
from ..fx import ground_lane


class SkeletonWarrior(Monster):
    NAME = "skeleton_warrior"
    SFX_WINDUP = "skeleton_windup"      # (these names are files in assets/audio/sfx/)
    SFX_STRIKE = "sword_swish"
    DISPLAY_NAME = "Skeleton Warrior"
    MAX_HP = 20                     # one sword hit (the Lich King's old skeletons died in one hit too)
    RADIUS = 16
    SPEED = 95.0
    DAMAGE = 8
    FOOT = 30
    XP = 6
    GOLD = (1, 5)
    LOOT = (("Bone Dust", 0.55), ("Rusty Sword", 0.06), ("Dented Shield", 0.05))

    WINDUP_TIME = 0.32
    STRIKE_TIME = 0.2
    RECOVER_TIME = 0.5
    STEP_LENGTH = 6.0
    LUNGE_SPEED = 540.0
    ATTACK_RANGE = 58               # starts winding up this far from touching the player
    ATTACK_COOLDOWN = 0.9
    SLASH_RANGE = 22                # the basic slash starts when you are this close to touching it
    SLASH_WINDUP = 0.14
    SLASH_STRIKE = 0.12
    SLASH_RECOVER = 0.3
    SLASH_LUNGE = 260.0
    SLASH_DAMAGE = 0.65             # fraction of its normal damage
    SLASH_COOLDOWN = 0.55
    AIM_LOCK = 0.12                 # stops tracking this long before the lunge (fair to dodge)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.lunge_angle = 0.0
        self.hit_done = False
        self.kind = "lunge"             # "lunge" (the telegraphed charge) or "slash" (the quick basic attack)
        self.slash_cd = 0.0
        self.strafe = self.rng.choice((-1, 1))
        self.strafe_timer = self.rng.uniform(1.5, 3.0)

    def think(self, dt, player, bounds):
        px, py = player_pos(player)
        dx, dy, dist = self.vector_to(px, py)
        self.face(px)
        self.slash_cd = max(0.0, self.slash_cd - dt)

        if self.state == "chase":
            self._do_chase(dt, dx, dy, dist, player)
        elif self.state == "windup":
            if self.state_time < self.windup_time - self.AIM_LOCK:
                self.lunge_angle = math.atan2(dy, dx)
            if self.state_time >= self.windup_time:
                self.hit_done = False
                self.set_state("strike")
        elif self.state == "strike":
            speed = self.LUNGE_SPEED if self.kind == "lunge" else self.SLASH_LUNGE
            self.x += math.cos(self.lunge_angle) * speed * dt
            self.y += math.sin(self.lunge_angle) * speed * dt
            if not self.hit_done and dist <= self.touch_distance(player):
                self.hit_done = True
                player.take_damage(self.damage if self.kind == "lunge"
                                   else max(1, int(round(self.damage * self.SLASH_DAMAGE))))
                self.fx.burst(px, py, (255, 255, 255), count=6, speed=160, life=0.25)
            if self.state_time >= self.STRIKE_TIME:
                if self.kind == "lunge":
                    self.cooldown = max(self.cooldown, self.ATTACK_COOLDOWN)
                else:
                    self.slash_cd = self.SLASH_COOLDOWN
                    self.cooldown = max(self.cooldown, 0.35)       # the big lunge is not far behind
                self.set_state("recover")
        elif self.state == "recover":
            if self.state_time >= self.RECOVER_TIME:
                self.set_state("chase")

    def _do_chase(self, dt, dx, dy, dist, player):
        touch = self.touch_distance(player)
        self.strafe_timer -= dt
        if self.strafe_timer <= 0:
            self.strafe = -self.strafe
            self.strafe_timer = self.rng.uniform(1.5, 3.0)
        if dist > touch - 2 and dist > 0:
            angle = math.atan2(dy, dx)
            if dist < 170:                              # close in: curve around instead of straight on
                angle += self.strafe * 0.45
            self.move(math.cos(angle), math.sin(angle), self.speed, dt)
        if self.slash_cd <= 0 and dist <= touch + self.SLASH_RANGE:             # basic attack: right next to it
            self._start("slash", self.SLASH_WINDUP, self.SLASH_STRIKE, self.SLASH_RECOVER, dx, dy)
        elif self.cooldown <= 0 and dist <= touch + self.ATTACK_RANGE:
            self._start("lunge", self.WINDUP_TIME, type(self).STRIKE_TIME, type(self).RECOVER_TIME, dx, dy)

    def _start(self, kind, windup, strike, recover, dx, dy):
        self.kind = kind
        self.STRIKE_TIME, self.RECOVER_TIME = strike, recover          # (per monster: the animation follows these)
        self.lunge_angle = math.atan2(dy, dx)
        self.begin_windup(windup)

    # ---------- the warning on the floor ----------

    def draw_floor(self, surface):
        super().draw_floor(surface)
        if self.state == "windup" and self.kind == "lunge":
            reach = self.LUNGE_SPEED * self.STRIKE_TIME + self.radius
            ground_lane(surface, self.x, self.y, self.lunge_angle, reach, self.radius * 2.2,
                        self.windup_progress)
