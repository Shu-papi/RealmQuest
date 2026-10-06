"""
minotaur/boss.py - The Minotaur (real-time boss).

FIGHT OVERVIEW
    Intro         He storms in from the top of the arena (can't be hurt).
    Phase 1       Stomps after the player and alternates two attacks:
                    Charge - he lowers his horns and a red lane appears showing
                             where he will run. He locks on, then sprints along
                             the lane. After hitting the far wall he is STUNNED
                             (takes extra damage: this is your chance to attack).
                    Slam   - he raises his fists and an orange circle appears on the
                             ground. Leave the circle before it bursts!
    Transition    At 50% HP he roars and can't be hurt for a moment.
    Phase 2       Enraged: faster, shorter wind-ups, he charges TWICE in a row,
                  and every slam also throws rocks out in all directions.
    Death         He collapses and fades away.

EVERY attack has a wind-up (telegraph) so the player can react.
Change the numbers in PHASE_STATS to tune the difficulty.

SPRITES: assets/bosses/minotaur/ (see the README.md there). If the PNGs are missing
or broken he is drawn with simple shapes instead, so the game never crashes.
"""
import math
import pygame

from ..base_boss import Boss
from ..attacks import Projectile, player_pos, player_radius
from ..pixel_art import draw_dotted_line, draw_pixel_ring
from .art import MinotaurArt
from .shockwave import Shockwave

PHASE_STATS = {
    1: {"speed": 80, "idle": 1.2, "recover": 0.5,
        "charges": 1, "charge_windup": 1.0, "charge_speed": 620, "charge_damage": 20,
        "stun": 1.3,
        "slam_windup": 1.1, "slam_radius": 125, "slam_damage": 16, "rocks": 0},
    2: {"speed": 120, "idle": 0.7, "recover": 0.35,
        "charges": 2, "charge_windup": 0.75, "charge_speed": 720, "charge_damage": 24,
        "stun": 1.0,
        "slam_windup": 0.9, "slam_radius": 150, "slam_damage": 20, "rocks": 8},
}

CHARGE_AIM_LOCK = 0.6        # he stops tracking the player after this share of the wind-up
CHARGE_REPEAT_WINDUP = 0.5   # shorter wind-up for the 2nd charge in phase 2 (seconds)
CHARGE_HIT_SHARE = 0.85      # how much of his hitbox radius hurts the player while charging
ROCK_SPEED = 250
ROCK_DAMAGE = 10
STUN_DAMAGE_MULT = 1.5       # damage multiplier while he is stunned
SLAM_OFFSET_Y = 40           # the slam circle is centred this far below his position (his fists)


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
        self.invulnerable_states = {"intro", "transition", "dying", "dead"}
        self.home_y = float(y)
        self.y = self.home_y - 110            # starts above and storms in during the intro
        self.state = "intro"
        self.last_attack = None
        self.repeat_count = 0
        self.cooldown = 0.0
        # charge bookkeeping
        self.aim_angle = math.pi / 2
        self.charges_left = 0
        self.charge_total = 0.0
        self.charge_remaining = 0.0
        self.charge_hit = False
        # Sprites are loaded from assets/bosses/minotaur/ the first time he is drawn
        self.art = MinotaurArt()

    @property
    def stats(self):
        return PHASE_STATS[self.phase]

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
        getattr(self, "_do_" + self.state)(dt, player, bounds)

    def _go_idle(self, cooldown):
        self.set_state("idle")
        self.cooldown = cooldown

    def _clamp_inside(self, bounds):
        left, top, right, bottom = bounds
        self.x = max(left + self.radius, min(right - self.radius, self.x))
        self.y = max(top + self.radius, min(bottom - self.radius, self.y))

    def _do_intro(self, dt, player, bounds):
        t = min(1.0, self.state_time / self.INTRO_TIME)
        self.y = self.home_y - 110 * (1 - t)
        if t >= 1.0:
            self.y = self.home_y
            self.shake = 0.6                  # stomps as he arrives
            self._go_idle(1.0)

    def _do_idle(self, dt, player, bounds):
        px, py = player_pos(player)
        dist = math.hypot(px - self.x, py - self.y)
        if dist > self.radius + 30:           # stomp towards the player, but don't walk into them
            step = min(self.stats["speed"] * dt, dist)
            self.x += (px - self.x) / dist * step
            self.y += (py - self.y) / dist * step
        self._clamp_inside(bounds)

        self.cooldown -= dt
        if self.cooldown <= 0:
            self._start_attack(self._pick_attack(dist))

    def _pick_attack(self, dist):
        """Slams when the player is close, charges when they are far. Never the same one 3 times."""
        near = dist <= self.stats["slam_radius"] + 40
        slam_chance = 0.75 if near else 0.25
        choice = "slam" if self.rng.random() < slam_chance else "charge"
        if choice == self.last_attack and self.repeat_count >= 2:
            choice = "charge" if choice == "slam" else "slam"
        return choice

    def _start_attack(self, name):
        self.repeat_count = self.repeat_count + 1 if name == self.last_attack else 1
        self.last_attack = name
        if name == "charge":
            self.charges_left = self.stats["charges"]
            self._start_charge_windup()
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

        if not self.charge_hit:
            px, py = player_pos(player)
            reach = self.radius * CHARGE_HIT_SHARE + player_radius(player)
            if math.hypot(px - self.x, py - self.y) <= reach:
                player.take_damage(self.stats["charge_damage"])
                self.charge_hit = True                         # hits once per charge

        if self.charge_remaining <= 0:
            self.shake = 1.0                                   # crashes into the wall
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
            rocks = self.stats["rocks"]
            if rocks:
                offset = self.rng.uniform(0, math.tau / rocks)
                for i in range(rocks):
                    angle = offset + math.tau * i / rocks
                    self.projectiles.append(Projectile(
                        self.x, self.y + SLAM_OFFSET_Y, angle, ROCK_SPEED, ROCK_DAMAGE,
                        radius=7, color=(176, 142, 102)))
            self.set_state("recover")

    def _do_recover(self, dt, player, bounds):
        if self.state_time >= self.stats["recover"]:
            self._go_idle(self.stats["idle"])

    # ---------- the rest ----------

    def _do_transition(self, dt, player, bounds):
        if self.state_time >= self.TRANSITION_TIME:
            self._go_idle(0.6)

    def _do_dying(self, dt, player, bounds):
        if self.state_time >= self.DYING_TIME:
            self.set_state("dead")

    def _do_dead(self, dt, player, bounds):
        pass

    # ------------------------------------------------------------------
    # Drawing
    # ------------------------------------------------------------------

    def draw_boss(self, surface):
        if self.state == "dead":
            return
        if self.state == "charge_windup":
            self._draw_charge_lane(surface)                    # under the sprite

        tint = None
        if self.hit_flash > 0:
            tint = "flash"
        elif self.state in ("charge_windup", "slam_windup") and int(self.state_time * 10) % 2 == 0:
            tint = "warn"                                      # blinks red: "attack coming!"

        lift = 0
        if self.state == "slam_windup":                       # raises his fists before the slam
            lift = 3 * min(1.0, self.state_time / self.stats["slam_windup"])
        alpha = 255
        if self.state == "dying":
            alpha = int(255 * max(0.0, 1.0 - self.state_time / self.DYING_TIME))

        drawn = self.art.draw(surface, self.x, self.y, clock=self.clock, phase=self.phase,
                              tint=tint, lift=lift, alpha=alpha,
                              anim_speed=3.0 if self.state == "charge" else 1.0)
        if not drawn:
            self._draw_shapes(surface, tint, alpha)

    def _draw_shapes(self, surface, tint, alpha):
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
        surface.blit(layer, (int(self.x) - cx, int(self.y) - cy))

    def draw_effects(self, surface):
        if self.state == "stunned":
            self._draw_stars(surface)
        elif self.state == "transition":
            progress = min(1.0, self.state_time / self.TRANSITION_TIME)
            draw_pixel_ring(surface, (self.x, self.y), 40 + progress * 320,
                            (226, 75, 74), dot=4, count=40)

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

    def _draw_stars(self, surface):
        """Little stars circling his head while he is stunned."""
        for i in range(3):
            angle = self.clock * 5 + i * math.tau / 3
            sx = int(self.x + math.cos(angle) * 44) // 4 * 4
            sy = int(self.y - 120 + math.sin(angle) * 10) // 4 * 4
            pygame.draw.rect(surface, (250, 199, 117), (sx, sy, 8, 8))
