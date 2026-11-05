"""
brute.py - Bone Brute: slow, tough, and hits like a falling house.

BEHAVIOUR
    chase    Stomps toward you. Hits never interrupt it (it has "poise") and it barely moves
             when you hit it, so you need to dodge, not trade blows.
    windup   Raises its maul overhead. A red circle on the floor fills up where the hammer
             will land. Get out of it!
    strike   SLAM: shockwave + screen shake. Hurts you only if you are still inside the circle.
    recover  Hammer stuck in the ground for a full second. This is your moment to hit back.
"""
import math

try:
    import audio                                             # src/ is on sys.path
except ImportError:                                          # run as src.monsters
    from src import audio
from ..attacks import player_pos
from ..base_monster import Monster
from ..fx import ground_circle


class SkeletonBrute(Monster):
    NAME = "skeleton_brute"
    SFX_HURT = "brute_hit"              # heavier hits and a bigger crash when it falls apart
    SFX_DIE = "brute_shatter"
    SFX_WINDUP = "brute_windup"
    DISPLAY_NAME = "Bone Brute"
    MAX_HP = 90
    RADIUS = 28
    SPEED = 58.0
    DAMAGE = 20
    FOOT = 40
    XP = 30
    GOLD = (10, 25)
    LOOT = (("Bone Dust", 1.0), ("Iron Maul Head", 0.25), ("Ram Horn", 0.2))

    SPAWN_TIME = 1.3
    POISE = True
    KNOCKBACK_RESIST = 0.85
    STEP_LENGTH = 5.0               # heavy, slow footsteps

    WINDUP_TIME = 0.7
    STRIKE_TIME = 0.3
    RECOVER_TIME = 1.0
    SLAM_RADIUS = 76
    SLAM_REACH = 62                 # the slam lands this far in front of the brute
    ATTACK_RANGE = 70
    ATTACK_COOLDOWN = 0.6
    SWIPE_RANGE = 16                # BASIC ATTACK: if you are this close to touching it, it may backhand you
    SWIPE_WINDUP = 0.28
    SWIPE_REACH = 36
    SWIPE_DAMAGE = 0.5              # fraction of the slam damage
    SWIPE_COOLDOWN = 1.1
    SWIPE_CHANCE = 0.6
    AIM_LOCK = 0.3

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.slam_angle = math.pi / 2
        self.hit_done = False
        self.kind = "slam"              # "slam" (the telegraphed hammer) or "swipe" (the quick basic backhand)
        self.swipe_cd = 0.0

    @property
    def slam_center(self):
        return (self.x + math.cos(self.slam_angle) * self.SLAM_REACH,
                self.y + math.sin(self.slam_angle) * self.SLAM_REACH)

    def think(self, dt, player, bounds):
        px, py = player_pos(player)
        dx, dy, dist = self.vector_to(px, py)
        self.face(px)
        self.swipe_cd = max(0.0, self.swipe_cd - dt)

        if self.state == "chase":
            touch = self.touch_distance(player)
            if dist > touch - 4 and dist > 0:
                self.move(dx, dy, self.speed, dt)
            if self.swipe_cd <= 0 and dist <= touch + self.SWIPE_RANGE and self.rng.random() < self.SWIPE_CHANCE:
                self.kind = "swipe"
                self.slam_angle = math.atan2(dy, dx)
                self.STRIKE_TIME, self.RECOVER_TIME = 0.2, 0.4
                self.swipe_cd = self.SWIPE_COOLDOWN
                self.begin_windup(self.SWIPE_WINDUP)
            elif self.cooldown <= 0 and dist <= touch + self.ATTACK_RANGE + self.SLAM_RADIUS * 0.4:
                self.kind = "slam"
                self.STRIKE_TIME, self.RECOVER_TIME = type(self).STRIKE_TIME, type(self).RECOVER_TIME
                self.slam_angle = math.atan2(dy, dx)
                self.begin_windup(self.WINDUP_TIME)
        elif self.state == "windup":
            if self.state_time < self.windup_time - (self.AIM_LOCK if self.kind == "slam" else 0.08):
                self.slam_angle = math.atan2(dy, dx)
            if self.state_time >= self.windup_time:
                self._slam(player) if self.kind == "slam" else self._swipe(player)
                self.set_state("strike")
        elif self.state == "strike":
            if self.state_time >= self.STRIKE_TIME:
                self.set_state("recover")
        elif self.state == "recover":
            if self.state_time >= self.RECOVER_TIME:
                self.cooldown = self.ATTACK_COOLDOWN
                self.set_state("chase")

    def _swipe(self, player):
        """The quick backhand: a short arc in front of it, only hurts if you are still hugging it."""
        cx = self.x + math.cos(self.slam_angle) * self.SWIPE_REACH
        cy = self.y + math.sin(self.slam_angle) * self.SWIPE_REACH
        self.shake = max(self.shake, 0.15)
        audio.play("brute_swipe", self.x)
        self.fx.burst(cx, cy, (222, 216, 196), count=6, speed=150, life=0.25)
        px, py = player_pos(player)
        if math.hypot(px - cx, py - cy) <= self.SWIPE_REACH * 0.8 + 14:
            player.take_damage(max(1, int(round(self.damage * self.SWIPE_DAMAGE))))

    def _slam(self, player):
        cx, cy = self.slam_center
        self.shake = max(self.shake, 0.5)
        audio.play("brute_slam", cx)
        self.rings.append([cx, cy, 0.0, self.SLAM_RADIUS * 1.25, 0.4, 0.4])
        self.fx.burst(cx, cy, (168, 160, 158), count=14, speed=230, life=0.5, gravity=700, up=120)
        self.fx.burst(cx, cy, (83, 74, 100), count=10, speed=140, life=0.6, gravity=200, up=20)
        px, py = player_pos(player)
        if math.hypot(px - cx, py - cy) <= self.SLAM_RADIUS:
            player.take_damage(self.damage)

    def draw_floor(self, surface):
        super().draw_floor(surface)
        if self.state == "windup" and self.kind == "slam":
            cx, cy = self.slam_center
            ground_circle(surface, cx, cy, self.SLAM_RADIUS, self.windup_progress)
