"""
minotaur/boss.py - The Minotaur (real-time boss).

FIGHT OVERVIEW
    Intro         He storms in from the top of the arena (can't be hurt).
    Phase 1       Stomps after the player (or circles them, or taunts) and picks his next
                  skill at random, never the same one three times in a row:
                    Charge - he lowers his horns and a red lane appears showing
                             where he will run. He locks on, then sprints along
                             the lane. After hitting the far wall he is STUNNED
                             (takes extra damage: this is your chance to attack).
                    Slam   - he raises his fists and an orange circle appears on the
                             ground. Leave the circle before it bursts!
                    Roar   - he flings his arms wide and casts a RING OF FIREBALLS.
                             Slip through the gaps between them.
                    Rocks  - he calls boulders down: dark circles mark where they land.
                             The first one always lands on YOU, so keep moving.
                    Leap   - he crouches, then jumps (can't be hurt in the air). A circle
                             shows where he will land: it is wherever you were standing.
    Transition    At 50% HP he roars and can't be hurt for a moment.
    Phase 2       Enraged: faster, shorter wind-ups, he charges TWICE in a row,
                  and every slam also throws rocks out in all directions.
    Death         He kneels, topples over and fades away.

EVERY attack has a wind-up (telegraph) so the player can react.
Change the numbers in PHASE_STATS to tune the difficulty.

SPRITES: assets/bosses/minotaur/ (see the README.md there). If the PNGs are missing
or broken he is drawn with simple shapes instead, so the game never crashes.

SOUND: every wind-up, hit, footstep and roar has a sound (assets/bosses/minotaur/sfx/, played by sfx.py).
Sounds are only ever PLAYED from here, they never change the fight, and with no audio they do nothing.
Silence him with  boss.sfx = None.
"""
import math
import random
import pygame

from ..base_boss import Boss
from ..attacks import Projectile, player_pos, player_radius
from ..pixel_art import draw_dotted_line, draw_pixel_ring
from .art import MinotaurArt
from .sfx import get_soundboard
from .shockwave import RockFall, Shockwave
from .view import TopDownView

PHASE_STATS = {
    1: {"speed": 80, "idle": 1.2, "recover": 0.5,
        "charges": 1, "charge_windup": 1.0, "charge_speed": 620, "charge_damage": 20,
        "stun": 1.3,
        "slam_windup": 1.1, "slam_radius": 125, "slam_damage": 16, "rocks": 0,
        "cast_windup": 0.9, "volley": 10, "volley_speed": 230, "volley_damage": 10,
        "rain_windup": 1.1, "rain_count": 5, "rain_radius": 58, "rain_damage": 14,
        "leap_windup": 0.55, "leap_time": 0.8, "leap_radius": 100, "leap_damage": 18},
    2: {"speed": 120, "idle": 0.7, "recover": 0.35,
        "charges": 2, "charge_windup": 0.75, "charge_speed": 720, "charge_damage": 24,
        "stun": 1.0,
        "slam_windup": 0.9, "slam_radius": 150, "slam_damage": 20, "rocks": 8,
        "cast_windup": 0.7, "volley": 14, "volley_speed": 280, "volley_damage": 12,
        "rain_windup": 0.9, "rain_count": 8, "rain_radius": 62, "rain_damage": 16,
        "leap_windup": 0.4, "leap_time": 0.65, "leap_radius": 120, "leap_damage": 22},
}

CHARGE_AIM_LOCK = 0.6        # he stops tracking the player after this share of the wind-up
CHARGE_REPEAT_WINDUP = 0.5   # shorter wind-up for the 2nd charge in phase 2 (seconds)
CHARGE_HIT_SHARE = 0.85      # how much of his hitbox radius hurts the player while charging
ROCK_SPEED = 250
ROCK_DAMAGE = 10
STUN_DAMAGE_MULT = 1.5       # damage multiplier while he is stunned
SLAM_OFFSET_Y = 40           # the slam circle is centred this far below his position (his fists)
FOOT_Y = 88                  # his feet are this far below his position (for dust and footsteps)
WALK_CYCLE_PX = 76           # screen pixels he travels in one full walk cycle (two steps): matches how far a foot swings
CHEST_Y = -10                # fireballs leave from here (relative to his position)
FIREBALL_COLOR = (255, 150, 60)
DEFAULT_BOUNDS = (40, 110, 920, 600)
SKILLS = ("charge", "slam", "cast", "rain", "leap")
WARN_STATES = ("charge_windup", "slam_windup", "cast_windup", "rain_windup", "leap_windup")

# The sound that starts the moment he ENTERS each state (the wind-ups, the stun, the phase-change roar...).
# Hits that land (slam burst, boulders) and footsteps are played where they happen, see _hear_hazards and _update_looks.
STATE_SOUNDS = {
    "charge_windup": "charge_windup", "charge": "charge", "stunned": "stun",
    "slam_windup": "slam_windup", "cast_windup": "cast_windup", "rain_windup": "rain_windup",
    "leap_windup": "leap_windup", "leap": "leap",
    "transition": "roar_big", "dying": "death",
}

DUST = (150, 134, 120)
STEAM = (226, 220, 232)
SPARK = (255, 176, 80)


def _distance_to_wall(x, y, angle, bounds, margin):
    """How far a point can travel along `angle` before it gets within `margin` of the arena wall."""
    left, top, right, bottom = bounds
    dx, dy = math.cos(angle), math.sin(angle)
    limits = []
    if dx > 1e-6:
        limits.append((right - margin - x) / dx)
    elif dx < -1e-6:
        limits.append((left + margin - x) / dx)
    if dy > 1e-6:
        limits.append((bottom - margin - y) / dy)
    elif dy < -1e-6:
        limits.append((top + margin - y) / dy)
    return max(0.0, min(limits)) if limits else 0.0


class Minotaur(Boss):
    INTRO_TIME = 1.8
    TRANSITION_TIME = 1.6
    DYING_TIME = 2.0

    def __init__(self, x=480, y=230, seed=None):
        super().__init__(
            name="Minotaur",
            max_hp=300,
            x=x,
            y=y,
            radius=46,
            intro="The ground trembles. The Minotaur of the Labyrinth lowers its horns.",
            death_line="The Minotaur crashes to the ground. The labyrinth falls silent.",
            loot=["Horn of the Labyrinth", "Bronze Bracers", "120 Gold"],
            seed=seed,
        )
        self.invulnerable_states = {"intro", "transition", "dying", "dead", "leap"}   # "leap" = in the air
        self.home_y = float(y)
        self.y = self.home_y - 110            # starts above and storms in during the intro
        self.state = "intro"
        self.last_attack = None
        self.repeat_count = 0
        self.cooldown = 0.0
        self.bounds = DEFAULT_BOUNDS
        self.target = (x, y + 200)            # where the player was last seen
        # charge bookkeeping
        self.aim_angle = math.pi / 2
        self.charges_left = 0
        self.charge_total = 0.0
        self.charge_remaining = 0.0
        self.charge_hit = False
        # new skills
        self.skill_scale = 1.0                # +-10% random wind-up length for the new skills
        self.recover_kind = "slam"            # what he is recovering from (changes the pose)
        self.leap_from = (x, y)
        self.leap_to = (x, y)
        # looks and moods: all of this is cosmetic or random, none of it changes damage
        self.facing = -1                      # -1 = looking left (like the PNG), 1 = looking right
        self.moving = False
        self.idle_mode = "chase"              # chase / strafe / taunt, re-rolled every time he goes idle
        self.strafe_dir = 1
        self.taunt = "stomp"                  # stomp / snort / roar
        self.sfx = get_soundboard()           # sound effects (None = silent); shared, so files load once
        self._heard = set()                   # ground hazards whose burst has already made a sound
        self._intro_roared = False
        self.fx = []                          # little dust / steam / spark squares
        self.trail = []                       # after-images while charging and leaping
        self._fx_rng = random.Random(seed)    # separate from self.rng so looks never change the fight
        self._fx_timer = 0.0
        self._trail_timer = 0.0
        self._landed = False
        # smooth animation: every look value chases its target through a spring (see _step_anim)
        self.anim = None
        self.walk = 0.0                       # 0 = standing, 1 = walking (fades in and out)
        self.walk_phase = 0.0
        self.tremble = 0.0                    # how hard he is shaking with effort
        self.pose_cur = None                  # pose being faded out
        self.pose_new = None                  # pose being faded in
        self.pose_mix = 1.0
        self.view = TopDownView()             # how he is drawn: the arena swaps in an IsoView for isometric play
        self.depth_dir = 1                    # +1 = facing the camera (front view), -1 = facing away (back view)
        self.back_cur = False
        self.back_new = False
        self._speed_now = 0.0                 # how fast he is really moving (px/s): the walk cycle follows it
        self._face_shown = -1                 # which way he is drawn (changes half way through a turn)
        self._face_goal = -1
        self._turn = 1.0
        # Sprites are loaded from assets/bosses/minotaur/ the first time he is drawn
        self.art = MinotaurArt()

    @property
    def stats(self):
        return PHASE_STATS[self.phase]

    # ------------------------------------------------------------------
    # Sound (never changes the fight; does nothing without audio)
    # ------------------------------------------------------------------

    def _play(self, name, volume=1.0, screen_x=None):
        """Plays a sound, panned to `screen_x` (default: where he is standing)."""
        board = getattr(self, "sfx", None)
        if board is None:
            return
        if screen_x is None:
            screen_x = self.view.project(self.x, self.y)[0]
        board.play(name, volume, screen_x)

    def set_state(self, state, *args, **kwargs):
        """Changing state is when most sounds start: a wind-up begins, he is stunned, he dies."""
        changed = state != getattr(self, "state", None)
        result = super().set_state(state, *args, **kwargs)
        if changed and hasattr(self, "view") and state in STATE_SOUNDS:
            self._play(STATE_SOUNDS[state])
        return result

    def _hear_hazards(self):
        """
        Slam circles and boulders burst inside their own update(), so notice the frame one does and give it a
        sound. A circle is a slam or a leap landing (louder when bigger); a RockFall is a boulder.
        """
        live = set()
        for hazard in self.hazards:
            key = id(hazard)
            live.add(key)
            if getattr(hazard, "state", None) == "burst" and key not in self._heard:
                self._heard.add(key)
                x = self.view.project(hazard.x, hazard.y)[0]
                if isinstance(hazard, RockFall):
                    self._play("rock", 1.0, x)
                else:
                    self._play("slam", 0.7 + 0.3 * min(1.0, hazard.radius / 150.0), x)
        self._heard &= live                       # forget hazards that are gone

    # ------------------------------------------------------------------
    # Things that happen TO the boss
    # ------------------------------------------------------------------

    def take_damage(self, amount):
        """He takes extra damage while stunned (after a charge into the wall)."""
        if self.state == "stunned":
            amount = int(amount * STUN_DAMAGE_MULT)
        return super().take_damage(amount)

    def check_phase(self):
        if self.phase == 1 and self.hp_percent() <= 0.5 and self.state not in ("dying", "dead"):
            self.phase = 2
            self.clear_attacks()
            self.charges_left = 0
            self.shake = 1.0
            self.set_state("transition")

    def on_death(self):
        self.clear_attacks()
        self.set_state("dying")

    # ------------------------------------------------------------------
    # AI: one small function per state
    # ------------------------------------------------------------------

    def update_ai(self, dt, player, bounds):
        self.bounds = bounds
        self.target = player_pos(player)
        self.moving = False
        self._hear_hazards()
        self._update_facing()
        x0, y0 = self.x, self.y
        getattr(self, "_do_" + self.state)(dt, player, bounds)
        if dt > 0:
            # How far he REALLY moved on screen drives the legs, so a planted foot stays planted (no
            # skating) in both views. Airborne, the legs do not walk; at a full charge the cycle is
            # capped so the legs never flicker faster than the eye can follow.
            sdx, sdy = self.view.screen_move(self.x - x0, self.y - y0)
            moved = 0.0 if self.state == "leap" else math.hypot(sdx, sdy)
            self._speed_now += (moved / dt - self._speed_now) * min(1.0, dt * 12.0)
            self.walk_phase += min(moved / WALK_CYCLE_PX * math.tau, dt * 2.6 * math.tau)
        self._update_looks(dt)

    def _go_idle(self, cooldown):
        """Back to stomping around. Each time he rolls a new mood so he never feels scripted."""
        self.set_state("idle")
        self.cooldown = cooldown * (0.8 + 0.4 * self.rng.random())
        roll = self.rng.random()
        self.idle_mode = "chase" if roll < 0.5 else ("strafe" if roll < 0.8 else "taunt")
        self.strafe_dir = 1 if self.rng.random() < 0.5 else -1
        self.taunt = ("stomp", "snort", "roar")[min(2, int(self.rng.random() * 3))]
        self._fx_timer = 0.0
        if self.idle_mode == "taunt" and self.taunt in ("snort", "roar"):
            self._play(self.taunt)                # (a stomp taunt makes its noise with every stomp)

    def _clamp_inside(self, bounds):
        left, top, right, bottom = bounds
        self.x = max(left + self.radius, min(right - self.radius, self.x))
        self.y = max(top + self.radius, min(bottom - self.radius, self.y))

    def _do_intro(self, dt, player, bounds):
        if not self._intro_roared:
            self._intro_roared = True
            self._play("roar_big")            # he roars as he storms in
        t = min(1.0, self.state_time / self.INTRO_TIME)
        self.y = self.home_y - 110 * (1 - t)
        self.moving = True
        if t >= 1.0:
            self.y = self.home_y
            self.shake = 0.6                  # stomps as he arrives
            self._play("thud", 0.8)
            self._dust_ring(*self._ground(), self._screen_radius(90), 12)
            self._go_idle(1.0)

    def _do_idle(self, dt, player, bounds):
        px, py = self.target
        dx, dy = px - self.x, py - self.y
        dist = max(1.0, math.hypot(dx, dy))
        speed = self.stats["speed"]
        if self.idle_mode == "chase":
            if dist > self.radius + 30:       # stomp towards the player, but don't walk into them
                step = min(speed * dt, dist)
                self.x += dx / dist * step
                self.y += dy / dist * step
                self.moving = True
        elif self.idle_mode == "strafe":      # circle the player, drifting in or out to ~170 px
            tx, ty = -dy / dist * self.strafe_dir, dx / dist * self.strafe_dir
            inward = 0.5 if dist > 230 else (-0.4 if dist < 130 else 0.0)
            vx, vy = tx + dx / dist * inward, ty + dy / dist * inward
            length = math.hypot(vx, vy) or 1.0
            self.x += vx / length * speed * 1.15 * dt
            self.y += vy / length * speed * 1.15 * dt
            self.moving = True
        self._clamp_inside(bounds)

        self.cooldown -= dt
        if self.cooldown <= 0:
            self._start_attack(self._pick_attack(dist))

    def _pick_attack(self, dist):
        """
        Picks his next skill at random, but sensibly: slams when you are close, charges and leaps
        when you are far. The skill he just used is less likely, and never 3 times in a row.
        """
        near = dist <= self.stats["slam_radius"] + 40
        if near:
            weights = {"slam": 3.0, "leap": 1.0, "cast": 1.3, "rain": 1.0, "charge": 1.0}
        else:
            weights = {"charge": 3.0, "leap": 2.0, "cast": 1.8, "rain": 1.4, "slam": 0.5}
        if self.phase == 2:                   # the enraged Minotaur mixes it up more
            weights["rain"] *= 1.3
            weights["leap"] *= 1.3
        if self.last_attack in weights:
            weights[self.last_attack] *= 0.4
            if self.repeat_count >= 2:
                del weights[self.last_attack]
        pick = self.rng.random() * sum(weights.values())
        for name, weight in weights.items():
            pick -= weight
            if pick <= 0:
                return name
        return name

    def _start_attack(self, name):
        self.repeat_count = self.repeat_count + 1 if name == self.last_attack else 1
        self.last_attack = name
        self.skill_scale = 0.92 + 0.18 * self.rng.random()
        if name == "charge":
            self.charges_left = self.stats["charges"]
            self._start_charge_windup()
        elif name == "cast":
            self.set_state("cast_windup")
        elif name == "rain":
            self._start_rain()
        elif name == "leap":
            self.set_state("leap_windup")
        else:
            self._start_slam()

    # ---------- charge ----------

    def _start_charge_windup(self):
        self.set_state("charge_windup")
        self.charge_hit = False

    def _do_charge_windup(self, dt, player, bounds):
        first = self.charges_left == self.stats["charges"]
        windup = self.stats["charge_windup"] if first else CHARGE_REPEAT_WINDUP
        if self.state_time < windup * CHARGE_AIM_LOCK:        # tracks the player, then locks on
            px, py = player_pos(player)
            self.aim_angle = math.atan2(py - self.y, px - self.x)
        self.charge_total = _distance_to_wall(self.x, self.y, self.aim_angle,
                                              bounds, self.radius)
        if self.state_time >= windup:
            self.charge_remaining = self.charge_total
            self.charge_hit = False
            self.set_state("charge")

    def _do_charge(self, dt, player, bounds):
        step = min(self.stats["charge_speed"] * dt, self.charge_remaining)
        self.x += math.cos(self.aim_angle) * step
        self.y += math.sin(self.aim_angle) * step
        self.charge_remaining -= step
        self.moving = True

        if not self.charge_hit:
            px, py = player_pos(player)
            reach = self.radius * CHARGE_HIT_SHARE + player_radius(player)
            if math.hypot(px - self.x, py - self.y) <= reach:
                player.take_damage(self.stats["charge_damage"])
                self.charge_hit = True                         # hits once per charge

        if self.charge_remaining <= 0:
            self.shake = 1.0                                   # crashes into the wall
            self._play("crash")
            gx, gy = self._ground()
            ox, oy = self.view.screen_dir(math.cos(self.aim_angle) * 40, math.sin(self.aim_angle) * 40)
            self._dust_ring(gx + ox, gy + oy, self._screen_radius(80), 14)
            self.charges_left -= 1
            if self.charges_left > 0:
                self._start_charge_windup()                    # phase 2: charge again
            else:
                self.set_state("stunned")

    def _do_stunned(self, dt, player, bounds):
        if self.state_time >= self.stats["stun"]:
            self._go_idle(self.stats["idle"])

    # ---------- slam ----------

    def _start_slam(self):
        self.set_state("slam_windup")
        self.hazards.append(Shockwave(self.x, self.y + SLAM_OFFSET_Y,
                                      self.stats["slam_radius"],
                                      self.stats["slam_windup"],
                                      self.stats["slam_damage"]))

    def _do_slam_windup(self, dt, player, bounds):
        if self.state_time >= self.stats["slam_windup"]:
            self.shake = 1.0
            cx, cy = self.view.project(self.x, self.y + SLAM_OFFSET_Y)
            self._dust_ring(cx, cy + (0 if self.view.iso else 20), self._screen_radius(self.stats["slam_radius"] * 0.8), 18)
            rocks = self.stats["rocks"]
            if rocks:
                offset = self.rng.uniform(0, math.tau / rocks)
                for i in range(rocks):
                    angle = offset + math.tau * i / rocks
                    self.projectiles.append(Projectile(
                        self.x, self.y + SLAM_OFFSET_Y, angle, ROCK_SPEED, ROCK_DAMAGE,
                        radius=7, color=(176, 142, 102)))
            self.recover_kind = "slam"
            self.set_state("recover")

    def _do_recover(self, dt, player, bounds):
        if self.state_time >= self.stats["recover"]:
            self._go_idle(self.stats["idle"])

    # ---------- roar: a ring of fireballs ----------

    def _do_cast_windup(self, dt, player, bounds):
        if self.state_time >= self.stats["cast_windup"] * self.skill_scale:
            self._fire_volley()
            self.recover_kind = "cast"
            self.set_state("recover")

    def _fire_volley(self):
        """A ring of fireballs. The gaps between them are wide enough to walk through."""
        count = self.stats["volley"]
        ox, oy = self.x, self.y + CHEST_Y
        rings = [(self.rng.uniform(0, math.tau / count), 1.0)]
        if self.phase == 2:                                    # a slower second ring fills in behind
            rings.append((rings[0][0] + math.pi / count, 0.7))
        for offset, speed_scale in rings:
            for i in range(count):
                angle = offset + math.tau * i / count
                self.projectiles.append(Projectile(
                    ox, oy, angle, self.stats["volley_speed"] * speed_scale,
                    self.stats["volley_damage"], radius=8, color=FIREBALL_COLOR))
        self.shake = max(self.shake, 0.5)
        self._play("fireball")
        rx, ry = self._ref()
        self._burst(rx, ry + CHEST_Y, 16, SPARK, speed=200, life=0.5, size=8)

    # ---------- rocks: boulders called down from the ceiling ----------

    def _start_rain(self):
        self.set_state("rain_windup")
        stats = self.stats
        windup = stats["rain_windup"] * self.skill_scale
        left, top, right, bottom = self.bounds
        radius = stats["rain_radius"]
        spots = [self.target]                                  # the first boulder always targets YOU
        for _ in range(stats["rain_count"] - 1):
            for _attempt in range(25):                         # random spots that don't pile up
                if self.rng.random() < 0.5:                    # half land around the player...
                    angle = self.rng.uniform(0, math.tau)
                    reach = self.rng.uniform(90, 260)
                    spot = (self.target[0] + math.cos(angle) * reach, self.target[1] + math.sin(angle) * reach)
                else:                                          # ...half anywhere in the arena
                    spot = (self.rng.uniform(left + radius, right - radius), self.rng.uniform(top + radius, bottom - radius))
                spot = (min(max(spot[0], left + radius), right - radius), min(max(spot[1], top + radius), bottom - radius))
                if all(math.hypot(spot[0] - o[0], spot[1] - o[1]) > radius * 1.3 for o in spots):
                    break
            spots.append(spot)
        for i, (sx, sy) in enumerate(spots):
            self.hazards.append(RockFall(sx, sy, radius, windup + i * 0.14, stats["rain_damage"]))

    def _do_rain_windup(self, dt, player, bounds):
        if self.state_time >= self.stats["rain_windup"] * self.skill_scale:
            self.shake = max(self.shake, 0.4)
            self.recover_kind = "rain"
            self.set_state("recover")

    # ---------- leap: jumps and lands on where the player stood ----------

    def _do_leap_windup(self, dt, player, bounds):
        if self.state_time >= self.stats["leap_windup"] * self.skill_scale:
            left, top, right, bottom = bounds
            tx = min(max(self.target[0], left + self.radius), right - self.radius)
            ty = min(max(self.target[1], top + self.radius), bottom - self.radius)
            self.leap_from, self.leap_to = (self.x, self.y), (tx, ty)
            self.hazards.append(Shockwave(tx, ty + SLAM_OFFSET_Y, self.stats["leap_radius"],
                                          self.stats["leap_time"], self.stats["leap_damage"]))
            self._burst(*self._ground(), 12, DUST, speed=140, life=0.5, size=8)
            self._landed = False
            self.set_state("leap")

    def _do_leap(self, dt, player, bounds):
        t = min(1.0, self.state_time / self.stats["leap_time"])
        self.x = self.leap_from[0] + (self.leap_to[0] - self.leap_from[0]) * t
        self.y = self.leap_from[1] + (self.leap_to[1] - self.leap_from[1]) * t
        self.moving = True
        if t >= 1.0:
            self.x, self.y = self.leap_to
            self._clamp_inside(bounds)
            self.shake = 1.0                                   # the whole arena shakes when he lands
            cx, cy = self.view.project(self.x, self.y + SLAM_OFFSET_Y)
            self._dust_ring(cx, cy + (0 if self.view.iso else 20), self._screen_radius(self.stats["leap_radius"] * 0.8), 18)
            self.recover_kind = "leap"
            self.set_state("recover")

    # ---------- the rest ----------

    def _do_transition(self, dt, player, bounds):
        if self.state_time >= self.TRANSITION_TIME:
            self._go_idle(0.6)

    def _do_dying(self, dt, player, bounds):
        if not self._landed and self.state_time >= self.DYING_TIME * 0.62:
            self._landed = True                                # he hits the floor
            self.shake = 0.8
            self._play("thud")
            self._dust_ring(*self._ground(), self._screen_radius(110), 16)
        if self.state_time >= self.DYING_TIME:
            self.set_state("dead")

    def _do_dead(self, dt, player, bounds):
        pass

    # ------------------------------------------------------------------
    # Looks: facing, dust, steam, after-images. Cosmetic only.
    # ------------------------------------------------------------------

    def _update_facing(self):
        """Which way he looks: left or right on screen, and (four-way views) towards or away from the camera."""
        if self.state in ("dying", "dead", "stunned"):
            return
        if self.state in ("charge_windup", "charge"):
            dx, dy = math.cos(self.aim_angle) * 100, math.sin(self.aim_angle) * 100
        elif self.state == "leap":
            dx, dy = self.leap_to[0] - self.leap_from[0], self.leap_to[1] - self.leap_from[1]
        else:
            dx, dy = self.target[0] - self.x, self.target[1] - self.y
        sx, sy = self.view.screen_dir(dx, dy)
        if abs(sx) > 22:
            self.facing = 1 if sx > 0 else -1
        if self.view.four_way and abs(sy) > 14:                 # isometric-style: he faces away when you are up the screen
            self.depth_dir = 1 if sy > 0 else -1

    def _burst(self, x, y, count, colour, speed=100, life=0.5, size=8, up=40):
        """
        Little squares thrown out from (x, y). Seen from above (the normal arena) they spread evenly in
        every direction and just slow down. Only the optional isometric room lets them rise and fall.
        """
        for _ in range(count):
            angle = self._fx_rng.uniform(0, math.tau)
            fast = speed * self._fx_rng.uniform(0.35, 1.0)
            if self.view.iso:
                vy = math.sin(angle) * fast * 0.5 - up
            else:
                vy = math.sin(angle) * fast                   # top-down: a full circle, no "up"
            self.fx.append([x, y, math.cos(angle) * fast, vy,
                            0.0, life * self._fx_rng.uniform(0.7, 1.2), colour, size])

    def _dust_ring(self, x, y, radius, count):
        """
        Dust thrown outwards in a ring, like a stomp or a landing. Seen from above it is a true
        circle; the isometric room squashes it to a 2:1 oval.
        """
        squash = 0.5 if self.view.iso else 1.0
        for i in range(count):
            angle = math.tau * i / count + self._fx_rng.uniform(-0.1, 0.1)
            self.fx.append([x + math.cos(angle) * radius * 0.5, y + math.sin(angle) * radius * 0.5 * squash,
                            math.cos(angle) * 170, math.sin(angle) * 170 * squash - (20 if self.view.iso else 0),
                            0.0, self._fx_rng.uniform(0.4, 0.7), DUST, 12])

    def _ref(self):
        """
        The screen point standing in for his "body centre": his feet are FOOT_Y below it.
        In the top-down view that is simply (x, y); in isometric it is placed so he stands on his spot.
        """
        return self.view.sprite_origin(self.x, self.y, FOOT_Y)

    def _ground(self):
        """The screen point under his feet."""
        rx, ry = self._ref()
        return rx, ry + FOOT_Y

    def _screen_radius(self, radius):
        """A floor radius as the sideways radius of its circle on screen (isometric floors are squashed)."""
        return radius * (getattr(self.view, "k", 1.0) * math.sqrt(2.0) if self.view.iso else 1.0)

    def _foot(self, side):
        gx, gy = self._ground()
        return gx + side * 34, gy

    def _update_looks(self, dt):
        self._step_anim(dt)
        for p in self.fx:
            p[4] += dt
            p[0] += p[2] * dt
            p[1] += p[3] * dt
            drag = max(0.0, 1.0 - 2.5 * dt)
            if self.view.iso:
                p[3] += 90 * dt                                # the isometric room: bits fall back down
            else:
                p[3] *= drag                                   # seen from above there is no up or down: they just slow
            p[2] *= drag
        self.fx = [p for p in self.fx if p[4] < p[5]]
        if len(self.fx) > 160:
            del self.fx[:len(self.fx) - 160]

        self._fx_timer -= dt
        if self.state == "idle" and self.moving and self._fx_timer <= 0:
            self._fx_timer = 0.24                              # a puff of dust with each heavy step
            x, y = self._foot(1 if int(self.clock * 7.5 / math.pi) % 2 else -1)
            self._burst(x, y, 2, DUST, speed=50, life=0.35, size=8, up=10)
            self._play("step", 1.0, x)
        elif self.state == "idle" and self.idle_mode == "taunt" and self._fx_timer <= 0:
            if self.taunt == "stomp":
                self._fx_timer = 0.45
                self.shake = max(self.shake, 0.22)
                self._play("stomp")
                self._burst(*self._foot(-1), 3, DUST, speed=90, life=0.4, size=8, up=10)
                self._burst(*self._foot(1), 3, DUST, speed=90, life=0.4, size=8, up=10)
            else:
                self._fx_timer = 0.18                          # steam snorting from his nostrils
                rx, ry = self._ref()
                self._burst(rx + self.facing * 30, ry + 14, 2, STEAM, speed=60, life=0.5, size=8, up=30)
        elif self.state == "charge_windup" and self._fx_timer <= 0:
            self._fx_timer = 0.11                              # pawing the ground
            self._burst(*self._foot(self.facing * -1 if int(self.clock * 12) % 2 else self.facing), 3,
                        DUST, speed=110, life=0.45, size=8, up=20)
            rx, ry = self._ref()
            self._burst(rx + self.facing * 30, ry + 14, 1, STEAM, speed=40, life=0.4, size=8, up=30)
        elif self.state == "charge" and self._fx_timer <= 0:
            self._fx_timer = 0.03                              # dust trail
            gx, gy = self._ground()
            ox, oy = self.view.screen_dir(math.cos(self.aim_angle) * 30, math.sin(self.aim_angle) * 30)
            self._burst(gx - ox, gy - oy, 2, DUST, speed=70, life=0.4, size=12, up=5)
        elif self.state == "cast_windup" and self._fx_timer <= 0:
            self._fx_timer = 0.05                              # embers gather around him
            angle = self._fx_rng.uniform(0, math.tau)
            rx, ry = self._ref()
            self.fx.append([rx + math.cos(angle) * 130, ry + CHEST_Y + math.sin(angle) * 130,
                            -math.cos(angle) * 220, -math.sin(angle) * 220, 0.0, 0.5, SPARK, 8])   # a true circle
        elif self.state == "stunned" and self._fx_timer <= 0:
            self._fx_timer = 0.3
            rx, ry = self._ref()
            self._burst(rx, ry - 70, 1, STEAM, speed=30, life=0.6, size=8, up=20)

        # after-images while he is a blur
        self._trail_timer -= dt
        if self.state in ("charge", "leap"):
            if self._trail_timer <= 0:
                self._trail_timer = 0.035
                snap = self._current_pose()
                snap.update(x=self.x, y=self.y, age=0.0)
                self.trail.append(snap)
        for ghost in self.trail:
            ghost["age"] += dt
        self.trail = [g for g in self.trail if g["age"] < 0.22][-6:]

    # ------------------------------------------------------------------
    # Animation: what pose, lean and squash he has right now
    # ------------------------------------------------------------------

    @staticmethod
    def _ease(t):
        t = max(0.0, min(1.0, t))
        return t * t * (3 - 2 * t)

    def _walk_pose(self):
        """The leg frame for the current moment of the walk cycle ("walk3"), or None if there are no walk files."""
        count = self.art.walk_frame_count()
        if not count:
            return None
        frame = int(round((self.walk_phase % math.tau) / math.tau * count)) % count
        return "walk%d" % frame

    def _lean_side(self):
        """+1 when he leans to the right, -1 to the left (the way he is looking)."""
        return 1 if self.facing > 0 else -1

    def _animation(self):
        """
        The pose he is AIMING for right now: lean, squash, lift, pose, plus how snappy to get there.
        The picture on screen follows these targets through springs (_step_anim), so changes between
        states are smooth, landings rebound and nothing ever pops.
        """
        state, t, c, face = self.state, self.state_time, self.clock, self._lean_side()
        a = {"pose": None, "back": self.depth_dir < 0, "angle": 0.0, "sx": 1.0, "sy": 1.0, "lift": 0.0,
             "shift": (0.0, 0.0), "hem": 0, "shadow": 1.0, "bob": 1.0, "speed": 1.0,
             "tremble": 0.0, "omega": 15.0, "zeta": 0.85}
        step = abs(math.sin(self.walk_phase))                  # 0 when a foot lands, 1 when the legs pass

        if state == "intro":                                   # running in from the gate
            a.update(pose=self._walk_pose(), angle=face * 7, lift=step * 2.2, sy=1 + 0.03 * math.sin(c * 13),
                     bob=0.0, omega=24.0)

        elif state == "idle":
            amp, phase = self.walk, self.walk_phase            # walking fades in and out smoothly
            a.update(pose=self._walk_pose() if amp > 0.3 else None,
                     lift=step * 1.4 * amp,                    # a lumbering walk: bob, sway, squash on each step
                     angle=math.sin(phase) * 3.2 * amp + math.sin(c * 1.3) * 1.2 * (1 - amp),
                     sy=1 - 0.035 * (1 - step) * amp + 0.018 * math.sin(c * 2.4) * (1 - amp),
                     sx=1 + 0.02 * (1 - step) * amp, bob=1.0 - amp, omega=18.0)
            if self.idle_mode == "taunt" and amp < 0.3:
                self._taunt_pose(a, t, c, face)

        elif state == "charge_windup":                         # paws the ground, head down, trembling
            first = self.charges_left == self.stats["charges"]
            windup = self.stats["charge_windup"] if first else CHARGE_REPEAT_WINDUP
            p = self._ease(t / windup)
            side = 1 if math.cos(self.aim_angle) > 0 else -1
            a.update(angle=side * (2 + 11 * p), sy=1 - 0.10 * p, sx=1 + 0.06 * p,
                     lift=max(0.0, math.sin(c * 12)) * 1.6 * p, bob=0.0, tremble=0.7 * p,
                     omega=12.0, zeta=1.0)

        elif state == "charge":                                # a leaning, stretched, bouncing blur
            cx, cy = abs(math.cos(self.aim_angle)), abs(math.sin(self.aim_angle))
            side = 1 if math.cos(self.aim_angle) > 0 else -1
            a.update(pose=self._walk_pose(), angle=side * 15 * cx, sx=1 + 0.12 * cx, sy=1 - 0.06 * cx + 0.08 * cy,
                     lift=step * 2.0, bob=0.0, omega=30.0, zeta=0.8)

        elif state == "stunned":                               # dizzy: wobbling and slumped
            a.update(angle=math.sin(t * 4.5) * 7, sy=0.92, sx=1.04, shift=(0.0, 1.0), bob=0.0,
                     omega=9.0, zeta=0.5)

        elif state == "slam_windup":                           # fists overhead, leaning back, rising
            p = self._ease(t / self.stats["slam_windup"])
            a.update(pose="raise", lift=3 + 5 * p, angle=-face * 6 * p, sy=1 + 0.05 * p, bob=0.0,
                     tremble=0.8 * self._ease((p - 0.6) / 0.4), omega=12.0, zeta=1.0)

        elif state == "cast_windup":                           # arms flung wide, glowing
            p = self._ease(t / (self.stats["cast_windup"] * self.skill_scale))
            pulse = 1 + 0.03 * math.sin(c * 16) * p
            a.update(pose="cast", lift=1.5 * p + math.sin(c * 7) * 0.6, angle=-face * 5 * p,
                     sx=pulse, sy=pulse, bob=0.0, tremble=0.5 * p, omega=13.0, zeta=1.0)

        elif state == "rain_windup":                           # fists to the sky, calling the boulders
            p = self._ease(t / (self.stats["rain_windup"] * self.skill_scale))
            a.update(pose="raise", lift=2 + 3 * p, angle=math.sin(c * 5) * 2, bob=0.0,
                     sy=1 + 0.03 * p, tremble=0.6 * p, omega=12.0, zeta=1.0)

        elif state == "leap_windup":                           # crouching down to spring
            p = self._ease(t / (self.stats["leap_windup"] * self.skill_scale))
            a.update(sy=1 - 0.22 * p, sx=1 + 0.14 * p, angle=-face * 5 * p, shift=(0.0, 1.5 * p),
                     bob=0.0, omega=14.0, zeta=1.0)

        elif state == "leap":                                  # airborne: tucked, stretched, small shadow
            u = min(1.0, t / self.stats["leap_time"])
            arc = math.sin(math.pi * u)
            a.update(lift=20 * arc, sy=1 + 0.10 * arc, sx=1 - 0.04 * arc, angle=face * (-8 + 18 * u),
                     pose="raise" if 0.15 < u < 0.85 else None, shadow=1 - 0.45 * arc, bob=0.0,
                     omega=24.0, zeta=0.85)

        elif state == "recover":                               # the landing squash springs back
            total = max(0.01, self.stats["recover"])
            s = max(0.0, 1 - t / total)
            if self.recover_kind in ("slam", "leap"):
                a.update(sx=1 + 0.14 * s, sy=1 - 0.16 * s, bob=0.0, omega=26.0, zeta=0.5)
            elif self.recover_kind == "cast":
                a.update(pose="cast" if s > 0.45 else None, angle=-face * 3 * s, lift=1.0 * s, omega=14.0, zeta=0.9)
            else:
                a.update(pose="raise" if s > 0.6 else None, lift=2 * s, omega=14.0, zeta=0.9)

        elif state == "transition":                            # the enraged roar
            a.update(pose="cast", angle=-face * 8, lift=2, sx=1 + 0.035 * math.sin(t * 24),
                     tremble=0.6, bob=0.0, omega=24.0, zeta=0.8)

        elif state in ("dying", "dead"):                       # kneels, then topples over
            p = min(1.0, t / self.DYING_TIME)
            kneel = self._ease(p / 0.3)
            fall = self._ease((p - 0.3) / 0.35)
            a.update(sy=1 - 0.2 * kneel, sx=1 + 0.06 * kneel, shift=(0.0, 1.0 * kneel),
                     angle=face * 86 * fall, bob=0.0, omega=12.0, zeta=0.9)

        a["speed"] = 3.0 if state == "charge" else 1.0
        return a

    def _taunt_pose(self, a, t, c, face):
        """The three idle taunts: a stomp hop, a head-tossing snort and a roar."""
        if self.taunt == "stomp":
            cycle = (t % 0.45) / 0.45
            hop = math.sin(math.pi * cycle)
            land = max(0.0, 1 - cycle * 5)
            a.update(lift=hop * 3.0, sy=1 + 0.05 * hop - 0.10 * land, sx=1 - 0.02 * hop + 0.08 * land,
                     bob=0.0, omega=26.0, zeta=0.6)
        elif self.taunt == "snort":
            toss = math.sin(min(t, 0.9) * 7) * max(0.0, 1 - t / 0.9)
            a.update(angle=-face * 8 * toss, sy=1 + 0.03 * toss, bob=0.0, omega=20.0)
        else:
            a.update(pose="cast" if (t % 1.2) < 0.7 else None, angle=-face * 5, lift=1.0,
                     tremble=0.5, bob=0.0)

    # ------------------------------------------------------------------
    # Smoothing: springs, pose cross-fades and turning around
    # ------------------------------------------------------------------

    SPRING_KEYS = ("angle", "sx", "sy", "lift", "shx", "shy", "shadow", "bob")

    def _step_anim(self, dt):
        """Moves every animation value towards its target like a damped spring (stable at any frame rate)."""
        moving_now = self.state == "idle" and self.moving and self._speed_now > 12.0
        self.walk += ((1.0 if moving_now else 0.0) - self.walk) * min(1.0, dt * 6.0)

        target = self._animation()
        goals = {"angle": target["angle"], "sx": target["sx"], "sy": target["sy"], "lift": target["lift"],
                 "shx": target["shift"][0], "shy": target["shift"][1], "shadow": target["shadow"],
                 "bob": target["bob"]}
        if self.anim is None:
            self.anim = {key: [goals[key], 0.0] for key in self.SPRING_KEYS}
            self.pose_cur = self.pose_new = target["pose"]
            self.back_cur = self.back_new = target["back"]
            self.pose_mix = 1.0
            self._face_shown = self._face_goal = self.facing
        else:
            omega, zeta = target["omega"], target["zeta"]
            steps = max(1, int(math.ceil(dt * 240)))
            h = dt / steps
            for key in self.SPRING_KEYS:
                value, velocity = self.anim[key]
                goal = goals[key]
                for _ in range(steps):
                    velocity += (omega * omega * (goal - value) - 2 * zeta * omega * velocity) * h
                    value += velocity * h
                self.anim[key] = [value, velocity]
        self.tremble += (target["tremble"] - self.tremble) * min(1.0, dt * 14.0)

        # poses (and front/back views) fade into each other instead of switching
        goal = (target["pose"], target["back"])
        if goal != (self.pose_new, self.back_new):
            both_walking = (isinstance(goal[0], str) and goal[0].startswith("walk")
                            and isinstance(self.pose_new, str) and self.pose_new.startswith("walk")
                            and goal[1] == self.back_new)
            if both_walking:                                   # the next leg frame simply replaces this one
                self.pose_cur = self.pose_new = goal[0]
                self.pose_mix = 1.0
            else:
                if self.pose_mix > 0.5:
                    self.pose_cur, self.back_cur = self.pose_new, self.back_new
                self.pose_new, self.back_new = goal
                self.pose_mix = 0.0
        if self.pose_mix < 1.0:
            self.pose_mix = min(1.0, self.pose_mix + dt / 0.14)
            if self.pose_mix >= 1.0:
                self.pose_cur, self.back_cur = self.pose_new, self.back_new

        # turning around: squeeze thin, flip while thin, expand again
        if self.facing != self._face_goal:
            self._face_goal = self.facing
            self._turn = 0.0
        if self._turn < 1.0:
            self._turn = min(1.0, self._turn + dt / 0.22)
            if self._turn >= 0.5:
                self._face_shown = self._face_goal
        else:
            self._face_shown = self._face_goal

    def _current_pose(self):
        """What is drawn this instant (smoothed): art settings ready to hand to MinotaurArt.draw."""
        if self.anim is None:
            self._step_anim(0.0)
        a = self.anim
        c = self.clock
        shake_x = (math.sin(c * 62) + 0.4 * math.sin(c * 97)) * self.tremble
        shake_y = math.cos(c * 71) * 0.4 * self.tremble
        turn = 1.0 if self._turn >= 1.0 else max(0.3, abs(1.0 - 2.0 * self._turn))
        mix = self._ease(self.pose_mix)
        fading = (self.pose_new, self.back_new) != (self.pose_cur, self.back_cur)
        return {"pose": self.pose_cur, "back": self.back_cur,
                "fade_to": (self.pose_new, self.back_new) if fading else None,
                "fade_mix": mix, "flip": self._face_shown > 0, "angle": a["angle"][0],
                "sx": a["sx"][0] * turn, "sy": a["sy"][0], "lift": a["lift"][0],
                "shift": (a["shx"][0] + shake_x, a["shy"][0] + shake_y), "shadow": a["shadow"][0],
                "bob": max(0.0, min(1.0, a["bob"][0])), "hem": 0}

    # ------------------------------------------------------------------
    # Drawing
    # ------------------------------------------------------------------

    def draw_boss(self, surface):
        """Top-down drawing: the red charge lane on the floor, then him."""
        if self.state == "dead":
            return
        if self.state == "charge_windup":
            self._draw_charge_lane(surface)                    # under the sprite
        self.draw_body(surface)

    def draw_body(self, surface, view=None):
        """Draws him (and his after-images) standing on his spot. `view` = where to project (default: self.view)."""
        if self.state == "dead":
            return
        view = view or self.view
        tint, tint_amount = None, 0.0
        if self.hit_flash > 0:
            tint, tint_amount = "flash", min(1.0, self.hit_flash / 0.10)          # fades out smoothly
        elif self.state in WARN_STATES:                        # a red glow that pulses: "attack coming!"
            ramp = min(1.0, self.state_time / 0.5)
            pulse = 0.5 + 0.5 * math.sin(math.tau * 3.2 * self.state_time - math.pi / 2)
            tint, tint_amount = "warn", ramp * (0.2 + 0.8 * pulse)

        alpha = 255
        if self.state == "dying":
            fade = (self.state_time / self.DYING_TIME - 0.55) / 0.45
            alpha = int(255 * min(1.0, max(0.0, 1.0 - fade)))

        cur = self._current_pose()
        drawn = True
        for ghost in self.trail:                               # after-images (charge and leap)
            fade = 1.0 - ghost["age"] / 0.22
            gx, gy = view.sprite_origin(ghost["x"], ghost["y"], FOOT_Y)
            drawn = self.art.draw(surface, gx, gy, clock=self.clock, phase=self.phase,
                                  lift=ghost["lift"], alpha=int(90 * fade), pose=ghost["pose"], back=ghost["back"],
                                  fade_to=ghost["fade_to"], fade_mix=ghost["fade_mix"], flip=ghost["flip"],
                                  angle=ghost["angle"], sx=ghost["sx"], sy=ghost["sy"], shift=ghost["shift"],
                                  hem=0, shadow=False, bob=0.0) and drawn
        ox, oy = view.sprite_origin(self.x, self.y, FOOT_Y)
        if view.four_way and alpha > 100:                      # the isometric-style boss stands on an oval shadow
            width = int(2 * self._screen_radius(self.radius * 1.7) * max(0.2, cur["shadow"]))
            oval = pygame.Surface((width, width // 2), pygame.SRCALPHA)
            pygame.draw.ellipse(oval, (8, 6, 12, 150), oval.get_rect())
            surface.blit(oval, (int(ox) - width // 2, int(oy) + FOOT_Y - width // 4))
        drawn = self.art.draw(surface, ox, oy, clock=self.clock, phase=self.phase,
                              tint=tint, tint_amount=tint_amount, lift=cur["lift"], alpha=alpha,
                              pose=cur["pose"], back=cur["back"], fade_to=cur["fade_to"], fade_mix=cur["fade_mix"],
                              flip=cur["flip"], angle=cur["angle"], sx=cur["sx"], sy=cur["sy"],
                              shift=cur["shift"], hem=0, shadow=not view.four_way, shadow_scale=cur["shadow"],
                              bob=cur["bob"]) and drawn
        if not drawn:
            self._draw_shapes(surface, ox, oy, tint if tint_amount > 0.5 else None, alpha)

    def _draw_shapes(self, surface, ox, oy, tint, alpha):
        """Simple stand-in used only when the PNG sprites are missing or broken."""
        if tint == "flash":
            body = (255, 255, 255)
        elif tint == "warn":
            body = (226, 75, 74)
        else:
            body = (120, 70, 46) if self.phase == 1 else (130, 44, 40)
        layer = pygame.Surface((220, 200), pygame.SRCALPHA)
        cx, cy = 110, 100
        horn = (232, 220, 180, alpha)
        pygame.draw.polygon(layer, horn, [(cx - 30, cy - 30), (cx - 80, cy - 70), (cx - 50, cy - 20)])
        pygame.draw.polygon(layer, horn, [(cx + 30, cy - 30), (cx + 80, cy - 70), (cx + 50, cy - 20)])
        pygame.draw.circle(layer, body + (alpha,), (cx, cy), self.radius)
        pygame.draw.rect(layer, (206, 148, 116, alpha), (cx - 14, cy + 4, 28, 26))
        eye = (255, 214, 90, alpha) if self.phase == 1 else (255, 70, 40, alpha)
        pygame.draw.rect(layer, eye, (cx - 22, cy - 12, 8, 8))
        pygame.draw.rect(layer, eye, (cx + 14, cy - 12, 8, 8))
        surface.blit(layer, (int(ox) - cx, int(oy) - cy))

    def draw_particles(self, surface):
        """Dust, steam, sparks and the stun stars: little things drawn in screen space."""
        for x, y, vx, vy, age, life, colour, size in self.fx:
            shrink = 1.0 - age / life
            px = max(2, int(size * shrink) // 2 * 2)
            pygame.draw.rect(surface, colour, (int(x) - px // 2, int(y) - px // 2, px, px))
        if self.state == "stunned":
            self._draw_stars(surface)

    def draw_effects(self, surface):
        """Top-down drawing of every effect (particles + the rings around him)."""
        self.draw_particles(surface)
        self._draw_rings(surface, (self.x, self.y), (self.x, self.y + CHEST_Y), (self.x, self.y + FOOT_Y - 8))

    def draw_ground(self, surface):
        """The effects that lie flat on the floor, in WORLD coordinates (the isometric view flattens them onto the floor)."""
        if self.state == "charge_windup":
            self._draw_charge_lane(surface)
        self._draw_rings(surface, (self.x, self.y), (self.x, self.y), (self.x, self.y))

    def _draw_rings(self, surface, center, chest, foot):
        if self.state == "transition":
            progress = min(1.0, self.state_time / self.TRANSITION_TIME)
            draw_pixel_ring(surface, center, 40 + progress * 320, (226, 75, 74), dot=4, count=40)
        elif self.state == "cast_windup":                           # rings of fire gather inwards
            windup = self.stats["cast_windup"] * self.skill_scale
            progress = min(1.0, self.state_time / windup)
            for k in range(3):
                phase = (progress * 1.6 + k / 3.0) % 1.0
                draw_pixel_ring(surface, chest, 190 * (1 - phase) + 30,
                                FIREBALL_COLOR if k % 2 == 0 else (255, 214, 120), dot=4, count=28)
        elif self.state == "rain_windup":                           # the ground trembles under him
            pulse = 60 + 14 * math.sin(self.clock * 14)
            draw_pixel_ring(surface, foot, pulse, (176, 142, 102), dot=4, count=24)
        elif self.state == "leap_windup":
            progress = min(1.0, self.state_time / (self.stats["leap_windup"] * self.skill_scale))
            draw_pixel_ring(surface, foot, 90 - 40 * progress, (239, 140, 60), dot=4, count=20)

    def _draw_charge_lane(self, surface):
        """A dotted red lane showing exactly where he is about to run."""
        ex = self.x + math.cos(self.aim_angle) * self.charge_total
        ey = self.y + math.sin(self.aim_angle) * self.charge_total
        side = self.radius * CHARGE_HIT_SHARE
        nx, ny = -math.sin(self.aim_angle) * side, math.cos(self.aim_angle) * side
        red = (226, 75, 74)
        draw_dotted_line(surface, (self.x, self.y), (ex, ey), red, gap=8)
        draw_dotted_line(surface, (self.x + nx, self.y + ny), (ex + nx, ey + ny), (140, 44, 48), gap=8)
        draw_dotted_line(surface, (self.x - nx, self.y - ny), (ex - nx, ey - ny), (140, 44, 48), gap=8)
        draw_pixel_ring(surface, (ex, ey), 16, red, dot=4, count=12)

    def star_positions(self):
        """Where the three stun stars are: they circle his head in a true circle (seen from above)."""
        rx, ry = self._ref()
        return [(rx + math.cos(self.clock * 5 + i * math.tau / 3) * 46,
                 ry - 100 + math.sin(self.clock * 5 + i * math.tau / 3) * 46) for i in range(3)]

    def _draw_stars(self, surface):
        """Little stars circling his head while he is stunned."""
        for x, y in self.star_positions():
            pygame.draw.rect(surface, (250, 199, 117), (int(x) // 4 * 4, int(y) // 4 * 4, 8, 8))
