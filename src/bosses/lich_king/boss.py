"""
lich_king/boss.py - The Lich King (real-time boss).

FIGHT OVERVIEW
    Intro         He rises from the floor (can't be hurt).
    Phase 1       Drifts above the player and alternates two attacks:
                    Shadow volley  - eyes glow amber and an aim line appears,
                                     then a fan of bolts is fired.
                    Life drain     - purple circles appear on the ground. Leave
                                     them before they burst! If they hit you,
                                     he heals.
    Transition    At 50% HP he roars and can't be hurt for a moment.
    Phase 2       Faster, more bolts, two drain circles at once, and he:
                    Summons skeletons (up to 4 alive at once).
                    Teleports around the arena after some attacks.
    Death         He fades away.

EVERY attack has a wind-up (telegraph) so the player can react.
Change the numbers in PHASE_STATS to tune the difficulty.
"""
import math
import pygame
from ..base_boss import Boss
from ..attacks import Projectile
from ..pixel_art import draw_dotted_line, draw_pixel_ring
from .drain_circle import DrainCircle
from .minions import Skeleton
from .art import LichKingArt

MAX_MINIONS = 4

PHASE_STATS = {
    1: {"speed": 70, "idle": 1.3, "recover": 0.6,
        "volley_windup": 0.8, "bolts": 3, "bolt_speed": 300,
        "drain_windup": 1.1, "drain_circles": 1,
        "summon_windup": 1.2},
    2: {"speed": 110, "idle": 0.7, "recover": 0.4,
        "volley_windup": 0.6, "bolts": 5, "bolt_speed": 340,
        "drain_windup": 0.9, "drain_circles": 2,
        "summon_windup": 1.2},
}

VOLLEY_DAMAGE = 12
DRAIN_DAMAGE = 18
DRAIN_HEAL = 15
DRAIN_RADIUS = 85

ATTACK_GLOW = {
    "volley": (239, 159, 39),
    "drain": (151, 196, 89),
    "summon": (212, 83, 126),
}


class LichKing(Boss):
    INTRO_TIME = 2.0
    TRANSITION_TIME = 1.8
    TELEPORT_TIME = 0.35
    DYING_TIME = 2.0

    def __init__(self, x=480, y=230, seed=None):
        super().__init__(
            name="Lich King",
            max_hp=300,
            x=x,
            y=y,
            radius=44,
            intro="Cold air fills the crypt. The Lich King rises from his throne.",
            death_line="The Lich King shatters into dust. 'Death is only the beginning...'",
            loot=["Crown of Bones", "Staff of Shadows", "150 Gold"],
            seed=seed,
        )
        self.invulnerable_states = {"intro", "transition", "teleport_out",
                                    "teleport_in", "dying", "dead"}
        self.home_y = float(y)
        self.y = self.home_y + 140          # starts below and rises in the intro
        self.state = "intro"
        self.attack_name = None
        self.last_attack = None
        self.windup_time = 0.0
        self.cooldown = 0.0
        self.aim = (x, y)
        self.fade = 1.0
        self.heal_flash = 0.0
        self.drain_lines = []
        # Sprites are loaded from assets/bosses/lich_king/ the first time he is drawn
        self.art = LichKingArt()

    @property
    def stats(self):
        return PHASE_STATS[self.phase]

    # ------------------------------------------------------------------
    # AI: one small function per state
    # ------------------------------------------------------------------

    def update_ai(self, dt, player, bounds):
        self.heal_flash = max(0.0, self.heal_flash - dt)
        for line in self.drain_lines:
            line[2] -= dt
        self.drain_lines = [l for l in self.drain_lines if l[2] > 0]

        getattr(self, "_do_" + self.state)(dt, player, bounds)

    def _go_idle(self, cooldown):
        self.set_state("idle")
        self.cooldown = cooldown

    def _do_intro(self, dt, player, bounds):
        t = min(1.0, self.state_time / self.INTRO_TIME)
        self.y = self.home_y + 140 * (1 - t)
        if t >= 1.0:
            self.y = self.home_y
            self._go_idle(1.0)

    def _do_idle(self, dt, player, bounds):
        left, top, right, bottom = bounds
        step = self.stats["speed"] * dt
        dx = player.rect.centerx - self.x
        self.x += max(-step, min(step, dx))
        self.x = max(left + self.radius, min(right - self.radius, self.x))

        self.cooldown -= dt
        if self.cooldown <= 0:
            self._begin_attack(self._choose_attack(), player, bounds)

    def _choose_attack(self):
        options = ["volley", "drain"]
        if self.phase == 2 and len(self.minions) < MAX_MINIONS:
            options.append("summon")
        fresh = [o for o in options if o != self.last_attack]
        return self.rng.choice(fresh or options)

    def _begin_attack(self, name, player, bounds):
        self.attack_name = name
        self.last_attack = name
        self.windup_time = self.stats[name + "_windup"]
        self.aim = (player.rect.centerx, player.rect.centery)
        self.set_state("windup")
        if name == "drain":
            self._place_drain_circles(player, bounds)

    def _do_windup(self, dt, player, bounds):
        self.aim = (player.rect.centerx, player.rect.centery)
        if self.state_time >= self.windup_time:
            if self.attack_name == "volley":
                self._fire_volley(player)
            elif self.attack_name == "summon":
                self._summon(player, bounds)
            # "drain" needs nothing here: its circles burst on their own timer
            self.set_state("recover")

    def _do_recover(self, dt, player, bounds):
        if self.state_time >= self.stats["recover"]:
            if self.phase == 2 and self.rng.random() < 0.5:
                self.set_state("teleport_out")
            else:
                self._go_idle(self.stats["idle"])

    def _do_teleport_out(self, dt, player, bounds):
        self.fade = max(0.0, 1.0 - self.state_time / self.TELEPORT_TIME)
        if self.state_time >= self.TELEPORT_TIME:
            self._pick_new_position(player, bounds)
            self.set_state("teleport_in")

    def _do_teleport_in(self, dt, player, bounds):
        self.fade = min(1.0, self.state_time / self.TELEPORT_TIME)
        if self.state_time >= self.TELEPORT_TIME:
            self.fade = 1.0
            self._go_idle(0.4)

    def _do_transition(self, dt, player, bounds):
        if self.state_time >= self.TRANSITION_TIME:
            self._go_idle(0.8)

    def _do_dying(self, dt, player, bounds):
        self.fade = max(0.0, 1.0 - self.state_time / self.DYING_TIME)
        if self.state_time >= self.DYING_TIME:
            self.set_state("dead")

    def _do_dead(self, dt, player, bounds):
        pass

    # ------------------------------------------------------------------
    # Attacks
    # ------------------------------------------------------------------

    def _fire_volley(self, player):
        count = self.stats["bolts"]
        spread = math.radians(16)
        base = math.atan2(player.rect.centery - self.y, player.rect.centerx - self.x)
        for i in range(count):
            angle = base + (i - (count - 1) / 2) * spread
            self.projectiles.append(
                Projectile(self.x, self.y - 6, angle,
                           self.stats["bolt_speed"], VOLLEY_DAMAGE))

    def _place_drain_circles(self, player, bounds):
        left, top, right, bottom = bounds
        px, py = player.rect.centerx, player.rect.centery
        spots = [(px, py)]
        for _ in range(self.stats["drain_circles"] - 1):
            angle = self.rng.uniform(0, math.tau)
            dist = self.rng.uniform(130, 190)
            spots.append((px + math.cos(angle) * dist, py + math.sin(angle) * dist))
        for sx, sy in spots:
            sx = max(left + 20, min(right - 20, sx))
            sy = max(top + 20, min(bottom - 20, sy))
            self.hazards.append(
                DrainCircle(sx, sy, DRAIN_RADIUS, self.windup_time, DRAIN_DAMAGE))

    def _summon(self, player, bounds):
        left, top, right, bottom = bounds
        px, py = player.rect.centerx, player.rect.centery
        free_slots = MAX_MINIONS - len(self.minions)
        for _ in range(min(2, free_slots)):
            x = y = 0
            for _attempt in range(10):
                x = self.rng.uniform(left + 30, right - 30)
                y = self.rng.uniform(top + 150, bottom - 30)
                if math.hypot(x - px, y - py) > 160:
                    break
            self.minions.append(Skeleton(x, y))

    def _pick_new_position(self, player, bounds):
        left, top, right, bottom = bounds
        px = player.rect.centerx
        for _attempt in range(10):
            x = self.rng.uniform(left + 80, right - 80)
            if abs(x - px) > 200:
                break
        self.x = x
        self.y = self.home_y + self.rng.uniform(-40, 40)

    def on_hazard_hit(self, hazard):
        """The drain circle hurt the player, so the Lich King heals."""
        self.heal(DRAIN_HEAL)
        self.heal_flash = 0.4
        self.drain_lines.append([hazard.x, hazard.y, 0.4])

    # ------------------------------------------------------------------
    # Phase changes and death
    # ------------------------------------------------------------------

    def check_phase(self):
        if self.phase == 1 and self.hp <= self.max_hp * 0.5:
            self.phase = 2
            self.clear_attacks()
            self.fade = 1.0
            self.shake = 1.0
            self.set_state("transition")

    def on_death(self):
        self.clear_attacks()
        self.fade = 1.0
        self.shake = 1.0
        self.set_state("dying")

    # ------------------------------------------------------------------
    # Drawing  (the pixel art itself lives in art.py)
    # ------------------------------------------------------------------

    def _look(self):
        """Work out how the art should look this frame."""
        phase = self.phase
        glow, level, raise_staff = None, 0, False

        if self.state == "windup":
            glow = ATTACK_GLOW.get(self.attack_name)
            progress = min(1.0, self.state_time / self.windup_time)
            level = min(3, int(progress * 4))
            raise_staff = self.attack_name == "summon"
        elif self.state == "transition":
            # Power-up: flicker between the two forms, eyes blazing, staff raised
            t = self.state_time / self.TRANSITION_TIME
            phase = 2 if (t > 0.6 or int(self.state_time * 12) % 2 == 0) else 1
            level, raise_staff = 3, True

        return dict(phase=phase, glow=glow, glow_level=level, raise_staff=raise_staff,
                    flash=self.hit_flash > 0, fade=self.fade)

    def draw_boss(self, surface):
        if self.state == "dead":
            return
        self.art.draw(surface, int(self.x), int(self.y), clock=self.clock, **self._look())

    def draw_effects(self, surface):
        cx, cy = int(self.x), int(self.y)
        if self.state == "windup" and self.attack_name == "volley":
            draw_dotted_line(surface, (cx, cy), (int(self.aim[0]), int(self.aim[1])),
                             (175, 169, 236))
        for x, y, _t in self.drain_lines:
            draw_dotted_line(surface, (int(x), int(y)), (cx, cy), (151, 196, 89), dot=8, gap=14)
        if self.heal_flash > 0:
            draw_pixel_ring(surface, (cx, cy), self.radius + 12, (151, 196, 89))
