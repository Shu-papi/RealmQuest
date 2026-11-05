"""
base_monster.py - The blueprint every RealmQuest monster is built from (real-time / Pygame).

Monsters are the small fry: the skeletons that guard a crypt, a pack that ambushes you in an
event, the minions a boss calls in. Anything in the game can spawn them (see monsters/__init__.py).

WHAT THE GAME NEEDS TO DO
    monster.update(dt, player, bounds)   every frame. bounds = (left, top, right, bottom)
    monster.draw(surface)                draws the monster, its shadow, its attacks and effects
    monster.take_damage(n, source=None)  returns the damage dealt (0 if it can't be hurt right now).
                                         `source` = (x, y) of the attacker adds knockback (optional)

    monster.is_alive()       False as soon as HP hits 0 (the shatter animation then plays)
    monster.finished         True once the death animation is over: now you can remove it
    monster.drop_loot()      list of item names (after death)
    monster.xp               experience for the player

    Bosses use the same shape (.x .y .radius .take_damage .is_alive .update .draw), so a boss can
    put monsters in `boss.minions` and everything just works. MonsterGroup (group.py) manages
    a bunch of monsters for maps and events.

WHAT A MONSTER NEEDS FROM THE PLAYER
    player.rect              a pygame.Rect
    player.take_damage(n)

TO MAKE A NEW MONSTER
    Inherit from Monster, set the class numbers, and write think(). See skeleton/warrior.py
    (the simplest) and HOW_TO_ADD_A_MONSTER.md.
"""
import math
import random

import pygame

try:
    import audio                                             # src/ is on sys.path (silent until the game calls audio.init())
except ImportError:                                          # run as src.monsters
    from src import audio
from .attacks import player_radius
from .fx import Particles, pixel_ring
from .sprites import VARIANTS, glow_color, get_sheet



class Monster:
    # ---------- numbers every monster sets ----------
    NAME = "monster"              # registry name AND the folder name in assets/monsters/
    DISPLAY_NAME = "Monster"
    MAX_HP = 20
    RADIUS = 14                   # hit circle used for the player's attacks and for touching
    SPEED = 90.0
    DAMAGE = 8
    FOOT = 20                     # pixels from (x, y) straight down to the floor under its feet
    XP = 5
    GOLD = (0, 0)                 # (min, max) coins dropped
    LOOT = ()                     # (("Item name", chance 0..1), ...)

    # ---------- timing ----------
    SPAWN_TIME = 0.8
    DYING_TIME = 1.25
    STAGGER_TIME = 0.28
    STAGGER_COOLDOWN = 1.4        # can't be stun-locked: it shrugs hits off for a moment after
    STRIKE_TIME = 0.25            # how long the "strike" state lasts (its animation is spread over it)
    RECOVER_TIME = 0.5            # ...and "recover" (so the animations line up with the AI)
    STEP_LENGTH = 6.0             # pixels walked per walk-animation frame (smaller = quicker legs)
    IDLE_FPS = 5.0

    # ---------- toughness ----------
    POISE = False                 # True = hits never interrupt it
    KNOCKBACK = 190.0             # push speed from one hit
    KNOCKBACK_RESIST = 0.0        # 0 = normal, 1 = immovable

    # ---------- sounds (names of files in assets/audio/sfx/; None = silent) ----------
    SFX_SPAWN = "monster_spawn"   # clawing out of the ground
    SFX_HURT = "bone_hit"         # a hit that does not kill it
    SFX_DIE = "bone_shatter"      # falling apart
    SFX_WINDUP = None             # the warning before an attack (played by begin_windup)
    SFX_STRIKE = None             # the attack itself (played when the state changes to "strike")

    START_STATE = "chase"
    INVULNERABLE_STATES = ("spawn", "dying", "dead")

    def __init__(self, x, y, variant="bone", seed=None, spawn=True,
                 hp_scale=1.0, damage_scale=1.0, loot=None, speed_scale=1.0):
        if variant not in VARIANTS:
            raise ValueError(f"Unknown variant '{variant}'. Choose from: {list(VARIANTS)}")
        self.x = float(x)
        self.y = float(y)
        self.radius = self.RADIUS
        self.max_hp = max(1, int(round(self.MAX_HP * hp_scale)))
        self.hp = self.max_hp
        self.speed = self.SPEED * speed_scale
        self.damage = max(1, int(round(self.DAMAGE * damage_scale)))
        self.xp = self.XP
        self.variant = variant
        self.rng = random.Random(seed)
        self.loot_table = self.LOOT if loot is None else loot

        self.state = "spawn" if spawn else self.START_STATE
        self.state_time = 0.0
        self.spawn_timer = self.SPAWN_TIME if spawn else 0.0
        self.clock = 0.0
        self.hit_flash = 0.0
        self.bar_time = 0.0
        self.shake = 0.0              # screen-shake the game may read (the brute's slam sets it)
        self.flip = False             # True = facing left
        self.moving = False
        self.walk_t = 0.0
        self.kx = self.ky = 0.0       # knockback velocity
        self.stagger_cd = 0.0
        self.windup_time = 0.0
        self.cooldown = 0.6
        self.bounds = (0, 0, 960, 640)

        self.projectiles = []
        self.allies = []              # other monsters it may help (set by MonsterGroup / the boss)
        self.spawn_requests = []      # monsters it wants added to the fight (acolyte raising the dead)
        self.fx = Particles()
        self.rings = []               # expanding shockwaves: [x, y, radius, max_radius, life, max_life]
        self.chunks = []
        self._loot = []
        self.sheet = get_sheet(self.NAME, variant)
        if spawn:
            self._spawn_burst()

    # ------------------------------------------------------------------
    # Questions the game can ask
    # ------------------------------------------------------------------

    def __repr__(self):
        return f"<{self.NAME} {self.hp}/{self.max_hp} {self.state} at {int(self.x)},{int(self.y)}>"

    def is_alive(self):
        return self.hp > 0

    @property
    def finished(self):
        return self.state == "dead"

    @property
    def spawning(self):
        return self.state == "spawn"

    @property
    def invulnerable(self):
        return self.state in self.INVULNERABLE_STATES

    @property
    def foot_y(self):
        return self.y + self.FOOT

    def hp_percent(self):
        return self.hp / self.max_hp

    def drop_loot(self):
        """Item names this monster dropped (empty until it has died)."""
        return list(self._loot)

    def take_spawn_requests(self):
        requests, self.spawn_requests = self.spawn_requests, []
        return requests

    def hittables(self):
        return [self] if self.is_alive() else []

    # ------------------------------------------------------------------
    # Things that happen TO the monster
    # ------------------------------------------------------------------

    def take_damage(self, amount, source=None):
        """Returns the damage dealt (0 if it can't be hurt right now)."""
        if self.invulnerable or not self.is_alive():
            return 0
        self.hp = max(0, self.hp - amount)
        self.hit_flash = 0.12
        self.bar_time = 2.5
        self.fx.burst(self.x, self.y, glow_color(self.variant, "eye", 2) if self.rng.random() < 0.25
                      else (222, 216, 196), count=5, speed=150, life=0.35)
        if self.hp > 0 and self.SFX_HURT:
            audio.play(self.SFX_HURT, self.x)
        if self.hp <= 0:
            self._die()
            return amount
        self.on_hurt(amount)
        if source is not None:
            self._knock_back(source)
        if not self.POISE and self.stagger_cd <= 0 and self.state in ("chase", "windup", "recover"):
            self.stagger_cd = self.STAGGER_COOLDOWN
            self.set_state("stagger")
        return amount

    def heal(self, amount):
        if self.is_alive() and self.hp < self.max_hp:
            self.hp = min(self.max_hp, self.hp + amount)
            self.bar_time = 2.5
            self.fx.burst(self.x, self.y - 6, (151, 196, 89), count=6, speed=70, life=0.6,
                          gravity=-120, up=0)

    def kill(self):
        """Destroy it right now (the shatter animation still plays). Used when a boss changes phase."""
        if self.is_alive():
            self.projectiles = []
            self.hp = 0
            self._die()

    def on_hurt(self, amount):
        """Called after a hit that did not kill. Optional."""

    def on_death(self):
        """Called once when HP reaches 0. Optional."""

    def _knock_back(self, source):
        dx, dy = self.x - source[0], self.y - source[1]
        d = math.hypot(dx, dy) or 1.0
        push = self.KNOCKBACK * (1.0 - self.KNOCKBACK_RESIST)
        self.kx += dx / d * push
        self.ky += dy / d * push

    def _die(self):
        if self.SFX_DIE:
            audio.play(self.SFX_DIE, self.x)
        self.set_state("dying")
        self.windup_time = 0.0
        self._loot = self._roll_loot()
        self._start_death_fx()
        self.on_death()

    def _roll_loot(self):
        items = [name for name, chance in self.loot_table if self.rng.random() < chance]
        low, high = self.GOLD
        if high > 0:
            items.append(f"{self.rng.randint(low, high)} Gold")
        return items

    # ------------------------------------------------------------------
    # Per-frame update
    # ------------------------------------------------------------------

    def set_state(self, state):
        self.state = state
        self.state_time = 0.0
        if state == "strike" and self.SFX_STRIKE:
            audio.play(self.SFX_STRIKE, self.x)

    def update(self, dt, player, bounds):
        self.bounds = bounds
        self.clock += dt
        self.state_time += dt
        self.moving = False
        self.hit_flash = max(0.0, self.hit_flash - dt)
        self.bar_time = max(0.0, self.bar_time - dt)
        self.stagger_cd = max(0.0, self.stagger_cd - dt)
        self.shake = max(0.0, self.shake - dt * 1.5)
        self.fx.update(dt)
        self._update_rings(dt)
        self._update_projectiles(dt, player, bounds)

        if self.state == "dead":
            return
        if self.state == "dying":
            self._update_dying(dt)
            return

        self._apply_knockback(dt)
        if self.state == "spawn":
            self.spawn_timer -= dt
            if self.spawn_timer > 0:
                if self.rng.random() < dt * 14:
                    self.fx.add(self.x + self.rng.uniform(-14, 14), self.foot_y,
                                self.rng.uniform(-25, 25), -self.rng.uniform(30, 90), 0.5,
                                (83, 74, 100), 3, gravity=200)
                return
            self.set_state(self.START_STATE)
            return
        if self.state == "stagger":
            if self.state_time >= self.STAGGER_TIME:
                self.cooldown = max(self.cooldown, 0.35)
                self.set_state(self.START_STATE)
            self._clamp(bounds)
            return

        self.cooldown = max(0.0, self.cooldown - dt)
        self.think(dt, player, bounds)
        self._clamp(bounds)

    def think(self, dt, player, bounds):
        raise NotImplementedError("Each monster must write its own think()")

    def _update_projectiles(self, dt, player, bounds):
        for p in self.projectiles:
            p.update(dt, player, bounds)
        self.projectiles = [p for p in self.projectiles if p.alive]

    def _update_rings(self, dt):
        for ring in self.rings:
            ring[4] -= dt
            ring[2] = ring[3] * (1.0 - ring[4] / ring[5])
        self.rings = [r for r in self.rings if r[4] > 0]

    def _apply_knockback(self, dt):
        if abs(self.kx) + abs(self.ky) < 4:
            self.kx = self.ky = 0.0
            return
        self.x += self.kx * dt
        self.y += self.ky * dt
        damp = math.exp(-9.0 * dt)
        self.kx *= damp
        self.ky *= damp

    def _clamp(self, bounds):
        left, top, right, bottom = bounds
        self.x = max(left + self.radius, min(right - self.radius, self.x))
        self.y = max(top + self.radius, min(bottom - self.radius, self.y))

    # ---------- helpers for think() ----------

    def vector_to(self, x, y):
        """(dx, dy, distance) from this monster to a point."""
        dx, dy = x - self.x, y - self.y
        return dx, dy, math.hypot(dx, dy)

    def touch_distance(self, player):
        return self.radius + player_radius(player)

    def face(self, x):
        if abs(x - self.x) > 6:
            self.flip = x < self.x

    def move(self, dx, dy, speed, dt):
        """Walk along (dx, dy) at `speed` pixels per second (also drives the walk animation)."""
        d = math.hypot(dx, dy)
        if d < 1e-6:
            return
        step = speed * dt
        self.x += dx / d * step
        self.y += dy / d * step
        self.walk_t += step
        self.moving = True

    def begin_windup(self, seconds):
        self.windup_time = seconds
        self.set_state("windup")
        if self.SFX_WINDUP:
            audio.play(self.SFX_WINDUP, self.x, max_seconds=seconds)

    @property
    def windup_progress(self):
        if self.state != "windup" or self.windup_time <= 0:
            return 0.0
        return min(1.0, self.state_time / self.windup_time)

    def _spawn_burst(self):
        """Dirt and bone chips thrown up where the monster claws its way out of the floor."""
        if self.SFX_SPAWN:
            audio.play(self.SFX_SPAWN, self.x)
        self.fx.burst(self.x, self.foot_y, (83, 74, 100), count=10, speed=110, life=0.6,
                      gravity=420, up=90)
        self.fx.burst(self.x, self.foot_y, (168, 160, 158), count=5, speed=90, life=0.5,
                      gravity=420, up=110)

    # ------------------------------------------------------------------
    # Death: the sprite shatters into bone chunks and a soul wisp drifts up
    # ------------------------------------------------------------------

    def _start_death_fx(self):
        sheet = self.sheet
        ember = VARIANTS[self.variant]["embers"]
        for i in range(3):
            self.fx.add(self.x + self.rng.uniform(-6, 6), self.y - 10 - i * 6,
                        self.rng.uniform(-12, 12), -self.rng.uniform(40, 80), 1.0 + 0.2 * i,
                        ember[i % len(ember)], 4, gravity=-30, drag=0.6)
        self.fx.burst(self.x, self.foot_y - 4, (83, 74, 100), count=8, speed=90, life=0.5,
                      gravity=-20, up=20)
        if sheet is None:
            return
        try:
            image = sheet.image(self._current_index(), self.flip, 3, False)
            left, top = sheet.top_left(self.x, self.foot_y, self.flip)
            width, height = image.get_size()
            cell = sheet.scale * 3
            floor = self.foot_y
            cx, cy = left + width / 2.0, top + height / 2.0
            for cy0 in range(0, height, cell):
                for cx0 in range(0, width, cell):
                    piece = image.subsurface(
                        pygame.Rect(cx0, cy0, min(cell, width - cx0), min(cell, height - cy0))).copy()
                    if pygame.mask.from_surface(piece).count() == 0:
                        continue
                    px, py = left + cx0, top + cy0
                    self.chunks.append([piece, float(px), float(py),
                                        (px - cx) * 3.2 + self.rng.uniform(-45, 45),
                                        -self.rng.uniform(90, 340) + (py - cy) * 0.9,
                                        floor + self.rng.uniform(-8, 8)])
        except Exception:                                              # noqa: BLE001
            self.chunks = []

    def _update_dying(self, dt):
        for chunk in self.chunks:
            piece, px, py, vx, vy, floor = chunk
            vy += 1150 * dt
            px += vx * dt
            py += vy * dt
            if py >= floor:
                py = floor
                vy = -vy * 0.3 if abs(vy) > 150 else 0.0
                vx *= 0.55
            chunk[1], chunk[2], chunk[3], chunk[4] = px, py, vx, vy
        if self.state_time >= self.DYING_TIME:
            self.set_state("dead")

    # ------------------------------------------------------------------
    # Drawing
    # ------------------------------------------------------------------

    def _current_index(self):
        animation, step = self.pose()
        return self.sheet.frame_index(animation, step)

    def pose(self):
        """(animation name, frame step) for this moment. The art decides how many frames each has."""
        state, sheet = self.state, self.sheet
        if state in ("stagger", "dying"):
            return "hurt", 0
        if sheet is None:
            return "walk", 0
        if state == "windup":
            return "windup", self._progress_step("windup", self.windup_progress)
        if state == "strike":
            return "strike", self._progress_step("strike", self.state_time / self.STRIKE_TIME)
        if state == "recover":
            return "recover", self._progress_step("recover", self.state_time / self.RECOVER_TIME)
        if self.moving:
            return "walk", int(self.walk_t / self.STEP_LENGTH) % sheet.count("walk")
        return "idle", int(self.clock * self.IDLE_FPS) % sheet.count("idle")

    def _progress_step(self, animation, progress):
        n = self.sheet.count(animation)
        return max(0, min(n - 1, int(progress * n)))

    def glow_level(self):
        if self.state == "windup":
            return 3 + int(self.windup_progress * 2.99)
        if self.state in ("strike",):
            return 5
        if self.state in ("stagger", "spawn"):
            return 0
        return 2 + (1 if int(self.clock * 3) % 2 == 0 else 0)

    def draw(self, surface):
        if self.state == "dead":
            return
        self.draw_floor(surface)
        if self.state == "dying":
            self._draw_dying(surface)
        else:
            self._draw_body(surface)
        self.fx.draw(surface)
        for ring in self.rings:
            pixel_ring(surface, (ring[0], ring[1]), ring[2], ring[2] * 0.62,
                       glow_color(self.variant, "glow", 4))
        for p in self.projectiles:
            p.draw(surface)
        self.draw_effects(surface)

    def draw_floor(self, surface):
        """Everything that lies on the ground: the shadow, spawn runes. Subclasses add warnings."""
        fx, fy = int(self.x), int(self.foot_y)
        if self.state == "dying":
            return
        grow = 1.0
        if self.state == "spawn":
            grow = 1.0 - max(0.0, self.spawn_timer) / self.SPAWN_TIME
        w = int(self.radius * 2.1 * (0.4 + 0.6 * grow))
        pygame.draw.ellipse(surface, (18, 15, 28), (fx - w // 2, fy - 5, w, 10))
        if self.state == "spawn":
            fade = max(0.0, self.spawn_timer) / self.SPAWN_TIME
            rr = self.radius * (1.2 + 1.4 * (1.0 - fade))
            color = glow_color(self.variant, "glow", 2 if fade > 0.3 else 1)
            pixel_ring(surface, (fx, fy), rr, rr * 0.5, color, phase=self.clock * 1.5)
            pixel_ring(surface, (fx, fy), rr * 0.55, rr * 0.28, color, phase=-self.clock * 2.0,
                       count=10)

    def draw_effects(self, surface):
        """Everything drawn above the body (attack flashes, beams). Optional."""

    def _draw_body(self, surface):
        if self.sheet is None:
            self._draw_placeholder(surface)
            return
        index = self._current_index()
        image = self.sheet.image(index, self.flip, self.glow_level(), self.hit_flash > 0)
        left, top = self.sheet.top_left(self.x, self.foot_y, self.flip)
        if self.state == "spawn":
            # rise out of the floor: reveal the picture from the feet upwards
            progress = 1.0 - max(0.0, self.spawn_timer) / self.SPAWN_TIME
            width, height = image.get_size()
            shown = max(1, int(height * progress))
            surface.blit(image, (left, top + height - shown), (0, height - shown, width, shown))
        else:
            surface.blit(image, (left, top))
            if self.bar_time > 0 and self.is_alive():
                self._draw_hp_bar(surface, left, top + self.sheet.figure_top())

    def _draw_hp_bar(self, surface, left, top):
        w = max(26, int(self.radius * 2))
        x = int(self.x) - w // 2
        y = top - 8
        pygame.draw.rect(surface, (30, 26, 44), (x - 2, y - 2, w + 4, 8))
        pygame.draw.rect(surface, (70, 40, 60), (x, y, w, 4))
        fill = int(w * self.hp_percent())
        if fill > 0:
            pygame.draw.rect(surface, (226, 75, 74), (x, y, fill, 4))

    def _draw_dying(self, surface):
        fade = 1.0
        if self.state_time > self.DYING_TIME * 0.7:
            fade = max(0.0, 1.0 - (self.state_time - self.DYING_TIME * 0.7) / (self.DYING_TIME * 0.3))
        for chunk in self.chunks:
            piece = chunk[0]
            piece.set_alpha(int(255 * fade))
            surface.blit(piece, (int(chunk[1]), int(chunk[2])))

    def _draw_placeholder(self, surface):
        """Shapes used when the PNGs are missing, so the game still works."""
        cx, cy = int(self.x), int(self.y)
        body = (255, 255, 255) if self.hit_flash > 0 else (222, 218, 204)
        pygame.draw.circle(surface, body, (cx, cy), self.radius)
        pygame.draw.circle(surface, (33, 29, 46), (cx, cy), self.radius, 2)
        eye = glow_color(self.variant, "eye", self.glow_level())
        pygame.draw.circle(surface, eye, (cx - 4, cy - 3), 2)
        pygame.draw.circle(surface, eye, (cx + 4, cy - 3), 2)

    def draw_debug(self, surface):
        pygame.draw.circle(surface, (0, 255, 120), (int(self.x), int(self.y)), int(self.radius), 1)
