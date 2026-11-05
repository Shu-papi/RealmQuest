"""
lich_king/boss.py - The Lich King (real-time boss).

FIGHT OVERVIEW  -  "OVERWHELMING": the last boss. A huge health pool, skills chained back to back,
an undying skeleton army and almost no breathing room... but never an unreadable attack.
    Intro         He rises from the floor (can't be hurt).
    Phase 1       Attacks come in PAIRS. Shadow volley (5 bolts), Life drain (heals him if it hits you!)
                  and Soul Rain (a scatter of small circles with gaps between them).
    Transition    At 50% HP he roars and can't be hurt for a moment, then immediately calls his army.
    Phase 2       Attacks come in chains of THREE and he adds:
                    Bone Nova      - a ring of bone shards with a SAFE GAP (green).
                    Grasping Hands - hands burst out of the floor (one under you!) and ROOT you.
                    Soul Barrage   - a sweeping stream of bolts through a wedge. Stay outside the wedge.
                    Skeleton army  - up to 8 "slots" of UNDYING skeletons (3x health, a brute takes two slots).
                    Teleporting around the arena.
    Transition    At 25% HP he is ENRAGED (can't be hurt for a moment) and calls his army again.
    Phase 3       LAST STAND: chains of FOUR, afterimages, double nova, eight hands, a 20-bolt barrage,
                  ten-circle Soul Rain. Drain heals him less.
                  SOUL WARD: while ANY of his summons is alive he is INVULNERABLE (a violet barrier, tethers to
                  every minion). Kill the whole wave to shatter the ward: he is STUNNED (his attack is
                  interrupted, he can't act) and takes +50% damage for a few seconds.
                  Acolytes can only raise a couple of dead per wave, so the ward can never be kept up forever,
                  and if you leave him alone he calls a fresh wave after a while.
    Death         He fades away.

THE WAY TO WIN: in phase 3 first break the SOUL WARD (kill every summon). After every chain he is EXHAUSTED (his soulfire is spent). For a few seconds he stands
open and takes +50% damage, with a glowing ring around him. That is the player's window. Everything
else is dodging: every attack still has a wind-up (telegraph), volley and barrage freeze their aim for the
last 0.3 s (AIM_LOCK) so a sidestep works, every nova has a gap, every rain has holes, every barrage has a
safe side, and dashing makes you immune.
Change the numbers in PHASE_STATS (and BOSS_MAX_HP) to tune the difficulty.
"""
import math
import pygame
try:
    import audio                                             # src/ is on sys.path (silent until the game calls audio.init())
    import balance                                           # (reads config/balance.toml)
except ImportError:                                          # run as src.bosses
    from src import audio, balance
from ..base_boss import Boss
from .bone_shard import BoneShard
from .drain_circle import DrainCircle, SoulRain
from .effects import (BONE, BONE_LIGHT, HEAL, SAFE, SAFE_DIM, FxLayer, GroundCracks, ShockBurst, chevron, clip_to,
                      ease_out,
                      hexagram, lerp_color, rune_ring, shock_ring, soul_ribbon, soul_skull, spike, theme,
                      with_alpha)
from .grasping_hand import GraspingHand
from .soul_bolt import SoulBolt
from .minions import (MINION_TIER, collect_requests, minion_load, pick_summons,
                      separate, spawn_monster)
from .art import LichKingArt

SHIELD_BREAK_WINDOW = 2.0         # phase 3: seconds he is STUNNED (takes +50% damage) after his last summon dies
REARM_AFTER = 7.0                 # phase 3: seconds with no army before he calls a fresh wave (the ward comes back)
WAVE_RAISE_BUDGET = 2             # phase 3: dead an acolyte may raise per wave (so the ward can't be kept up forever)
SHIELD = (176, 150, 255)          # the Soul Ward colour: a cold violet nothing else in the fight uses
SHIELD_HOT = (236, 226, 255)

# ALL OF THE NUMBERS BELOW ARE DEFAULTS. config/balance.toml overrides them (see src/balance.py), so tune
# the boss THERE, not here. (Add a new setting? Add its name to TUNABLE below and to tools/make_balance_config.py.)
BOSS_NAME = "Lich King"
BOSS_RADIUS = 44                  # his hit circle
BOSS_INTRO = "Cold air fills the crypt. The Lich King rises from his throne."
BOSS_DEATH_LINE = "The Lich King shatters into dust. 'Death is only the beginning...'"
BOSS_LOOT = ["Crown of Bones", "Staff of Shadows", "150 Gold"]
INTRO_TIME = 2.0                  # seconds: he rises from the floor (can't be hurt)
TRANSITION_TIME = 1.8             # seconds: the roar between phases (can't be hurt)
TELEPORT_TIME = 0.35              # seconds to fade out (and again to fade in)
DYING_TIME = 2.0
VOLLEY_SPREAD_DEG = 16.0          # angle between the bolts of a Shadow Volley
BOSS_MAX_HP = 3000                # was 300. With a 20-damage sword that is 150 hits (about 100 in practice)
EXHAUST_BONUS = 1.5               # damage multiplier while he is exhausted (the player's window)

# Every phase gets faster, chains more attacks together, and calls a different sized army.
#   combo        extra attacks chained after the first (chain length = combo + 1)
#   exhaust      seconds he stands open and takes EXHAUST_BONUS damage after a chain
#   minion_cap   army budget for this phase (0 = no summoning)
PHASE_STATS = {
    1: {"speed": 80.0, "idle": 0.8, "recover": 0.45, "teleport": 0.0, "combo": 1, "exhaust": 2.0,
        "minion_cap": 0, "summon_picks": 0,
        "volley_windup": 0.8, "bolts": 5, "bolt_speed": 300.0,
        "drain_windup": 1.0, "drain_circles": 1, "drain_heal": 45,
        "rain_windup": 1.0, "rain_circles": 4, "rain_radius": 58,
        "summon_windup": 1.2,
        "nova_windup": 1.1, "nova_rings": 1, "nova_shards": 16, "nova_speed": 220.0,
        "grasp_windup": 1.1, "grasp_hands": 3, "grasp_root": 0.8,
        "barrage_windup": 1.0, "barrage_bolts": 12, "barrage_speed": 320.0, "barrage_sweep": 60,
        "barrage_interval": 0.1},
    2: {"speed": 120.0, "idle": 0.45, "recover": 0.3, "teleport": 0.5, "combo": 2, "exhaust": 2.4,
        "minion_cap": 8, "summon_picks": 3,          # his biggest army: a brute counts as 2 (see minions.py)
        "volley_windup": 0.55, "bolts": 7, "bolt_speed": 350.0,
        "drain_windup": 0.85, "drain_circles": 2, "drain_heal": 50,
        "rain_windup": 0.8, "rain_circles": 7, "rain_radius": 58,
        "summon_windup": 1.1,
        "nova_windup": 0.95, "nova_rings": 1, "nova_shards": 20, "nova_speed": 235.0,
        "grasp_windup": 0.95, "grasp_hands": 5, "grasp_root": 1.0,
        "barrage_windup": 0.8, "barrage_bolts": 16, "barrage_speed": 340.0, "barrage_sweep": 70,
        "barrage_interval": 0.09},
    # Phase 3 "Last Stand": four attacks in a row, barely a pause between them, then a short window
    3: {"speed": 165.0, "idle": 0.4, "recover": 0.2, "teleport": 0.6, "combo": 3, "exhaust": 2.6,
        "minion_cap": 6, "summon_picks": 4,
        "volley_windup": 0.5, "bolts": 9, "bolt_speed": 390.0,
        "drain_windup": 0.8, "drain_circles": 3, "drain_heal": 30,
        "rain_windup": 0.65, "rain_circles": 10, "rain_radius": 58,
        "summon_windup": 0.9,
        "nova_windup": 0.9, "nova_rings": 2, "nova_shards": 22, "nova_speed": 265.0,
        "grasp_windup": 0.9, "grasp_hands": 8, "grasp_root": 1.3,
        "barrage_windup": 0.6, "barrage_bolts": 20, "barrage_speed": 370.0, "barrage_sweep": 90,
        "barrage_interval": 0.07},
}

PHASE_2_AT = 0.5                  # fraction of max HP where each phase begins
PHASE_3_AT = 0.25

VOLLEY_DAMAGE = 12
DRAIN_DAMAGE = 18
DRAIN_RADIUS = 85
NOVA_DAMAGE = 10
NOVA_GAP_SHARDS = 3               # how many shards wide the safe gap is
NOVA_SECOND_RING = 0.55           # seconds between the two rings of the phase 3 nova
GRASP_DAMAGE = 12
GRASP_RADIUS = 42
BARRAGE_DAMAGE = 9                # many small bolts, so each one hurts less
RAIN_DAMAGE = 14
RAIN_STAGGER = 0.1                # seconds between one rain circle bursting and the next
GRASP_STAGGER = 0.12              # seconds between one hand bursting and the next
AIM_LOCK = 0.3                    # volley and barrage stop tracking you this long before firing: sidestep or dash!
COMBO_PAUSE = 0.15                # pause between the attacks of a chain

# which art pose goes with which attack wind-up (see assets/bosses/lich_king/README.md)
ATTACK_POSE = {"volley": "volley", "drain": "drain", "summon": "summon",
               "nova": "nova", "grasp": "grasp", "barrage": "volley", "rain": "drain"}

ATTACK_GLOW = {
    "volley": (239, 159, 39),
    "drain": (151, 196, 89),
    "summon": (212, 83, 126),
    "nova": (110, 200, 255),
    "grasp": (176, 110, 235),
    "barrage": (255, 110, 90),
    "rain": (90, 220, 190),
}
EXHAUST_GLOW = (255, 214, 120)    # the "hit me now" colour: a warm gold nothing else in the fight uses

# every setting config/balance.toml may change (the name in the file is this, in lower case)
TUNABLE = (
    "BOSS_NAME", "BOSS_RADIUS", "BOSS_INTRO", "BOSS_DEATH_LINE", "BOSS_LOOT", "BOSS_MAX_HP",
    "INTRO_TIME", "TRANSITION_TIME", "TELEPORT_TIME", "DYING_TIME",
    "PHASE_2_AT", "PHASE_3_AT", "EXHAUST_BONUS",
    "SHIELD_BREAK_WINDOW", "REARM_AFTER", "WAVE_RAISE_BUDGET",
    "VOLLEY_DAMAGE", "DRAIN_DAMAGE", "NOVA_DAMAGE", "GRASP_DAMAGE", "BARRAGE_DAMAGE", "RAIN_DAMAGE",
    "DRAIN_RADIUS", "GRASP_RADIUS", "VOLLEY_SPREAD_DEG", "NOVA_GAP_SHARDS", "NOVA_SECOND_RING",
    "RAIN_STAGGER", "GRASP_STAGGER", "AIM_LOCK", "COMBO_PAUSE",
    "ATTACK_GLOW", "EXHAUST_GLOW", "SHIELD", "SHIELD_HOT",
)
balance.apply_boss(globals(), TUNABLE, PHASE_STATS)
MAX_MINIONS = PHASE_STATS[2]["minion_cap"]      # (kept for old code that imports it)


class LichKing(Boss):
    PHASE_3_HP = PHASE_3_AT           # the arena's P key uses this to jump to phase 3
    INTRO_TIME = INTRO_TIME           # (these four come from the constants above, so the config can change them)
    TRANSITION_TIME = TRANSITION_TIME
    TELEPORT_TIME = TELEPORT_TIME
    DYING_TIME = DYING_TIME

    def __init__(self, x=480, y=268, seed=None):
        super().__init__(
            name=BOSS_NAME,
            max_hp=BOSS_MAX_HP,
            x=x,
            y=y,
            radius=BOSS_RADIUS,
            intro=BOSS_INTRO,
            death_line=BOSS_DEATH_LINE,
            loot=list(BOSS_LOOT),
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
        self.scheduled = []                 # [seconds left, what, ...]: e.g. the second ring of a nova
        self.bounds = (40, 110, 920, 600)   # the arena (remembered so floor effects can be clipped to it)
        self.bursts = []                    # shockwaves / ground cracks that play out after an attack
        self.summon_plan = []               # [(monster name, x, y), ...] the sigils shown while summoning
        self.nova_gap = 0.0                 # angle of the safe gap of the current nova
        self.nova_origin = (x, y)
        self.combo_left = 0
        self.combo_pending = False
        self.rage = 0.0                     # 0 normally, 1 in phase 3 (drives the enraged look)
        self.trail = []                     # recent positions, for the afterimages
        self.remains = []                   # minions that just died: their bones are still flying
        self.barrage_dir = 1                # which way the next barrage sweeps
        self.barrage = None                 # the Soul Barrage that is firing right now (see _start_barrage)
        self.force_next = None              # an attack he MUST use next (his army, right after a phase change)
        self.was_shielded = False           # phase 3: was the Soul Ward up last frame? (to notice it breaking)
        self.break_time = 0.0               # phase 3: seconds left of the "ward shattered" damage window
        self.ward_flash = 0.0               # a hit bounced off the ward (visual feedback)
        self.free_time = 0.0                # phase 3: seconds without any army (he calls a new wave at REARM_AFTER)
        self.wave_raises = 0                # phase 3: dead raised by acolytes in the current wave
        self.intro_heard = False            # the rising sound + phase 1 music start on the first update
        # Sprites are loaded from assets/bosses/lich_king/ the first time he is drawn
        self.art = LichKingArt()

    @property
    def stats(self):
        return PHASE_STATS[self.phase]

    # ------------------------------------------------------------------
    # AI: one small function per state
    # ------------------------------------------------------------------

    def update_ai(self, dt, player, bounds):
        self.bounds = bounds
        if not self.intro_heard:
            self.intro_heard = True
            audio.play("lich_intro", self.x)
            audio.music("lich_p1", fade=0.3)       # the music hits the moment the fight starts
        audio.loop("ward_hum", self.shielded, self.x)      # the Soul Ward hums for as long as it is up
        self.heal_flash = max(0.0, self.heal_flash - dt)
        self.ward_flash = max(0.0, self.ward_flash - dt)
        self.break_time = max(0.0, self.break_time - dt)
        if self.phase == 3 and self.state not in ("transition", "intro", "dying", "dead") and not self.minions:
            self.free_time += dt
        else:
            self.free_time = 0.0
        for line in self.drain_lines:
            line[2] -= dt
        self.drain_lines = [l for l in self.drain_lines if l[2] > 0]

        if self.phase == 3:
            self.rage = min(1.0, self.state_time / self.TRANSITION_TIME) if self.state == "transition" else 1.0
        else:
            self.rage = 0.0
        self.trail.append((self.clock, self.x, self.y))
        self.trail = [t for t in self.trail if self.clock - t[0] < 0.5]

        for burst in self.bursts:
            burst.update(dt)
        self.bursts = [b for b in self.bursts if b.alive]
        if self.barrage:
            self.barrage["t"] += dt
            if self.barrage["t"] >= self.barrage["dur"] + 0.3:
                self.barrage = None
        self._run_scheduled(dt)
        getattr(self, "_do_" + self.state)(dt, player, bounds)

    def set_state(self, state):
        super().set_state(state)
        self._state_sound(state)

    def _state_sound(self, state):
        """The sounds that go with entering a state (attacks have their own, see _begin_attack)."""
        if state == "exhausted":
            audio.play("exhaust_open", self.x)                  # the gong: "hit him NOW"
        elif state == "teleport_out":
            audio.play("teleport_out", self.x)
        elif state == "teleport_in":
            audio.play("teleport_in", self.x)
        elif state == "transition":
            audio.play("roar_phase3" if self.phase >= 3 else "roar_phase2", self.x)
        elif state == "dying":
            audio.play("lich_death", self.x)
        elif state == "dead":
            audio.play("victory_sting")

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
        if not self.scheduled:                  # stand still while a nova's second ring is on its way
            step = self.stats["speed"] * dt
            dx = player.rect.centerx - self.x
            self.x += max(-step, min(step, dx))
            self.x = max(left + self.radius, min(right - self.radius, self.x))

        self.cooldown -= dt
        if self.cooldown <= 0:
            if not self.combo_pending:                      # a fresh attack: how many follow it?
                self.combo_left = self.stats["combo"]
            self.combo_pending = False
            self._begin_attack(self._choose_attack(), player, bounds)

    def _can_summon(self):
        cap = self.stats["minion_cap"]
        if self.phase >= 3:                                 # one wave at a time: the ward is on or off
            return cap > 0 and minion_load(self.minions) == 0
        return cap > 0 and minion_load(self.minions) < cap

    def _choose_attack(self):
        if self.force_next:                                 # right after a phase change: call the army first
            wanted, self.force_next = self.force_next, None
            if wanted != "summon" or self._can_summon():
                return wanted
        if self.phase == 3 and self.free_time >= REARM_AFTER and self._can_summon():
            return "summon"                                 # you left him alone too long: the ward returns
        options = ["volley", "drain", "rain"]
        if self.phase >= 2:
            options += ["nova", "grasp", "barrage"]
            if self._can_summon():
                options.append("summon")
        fresh = [o for o in options if o != self.last_attack]
        return self.rng.choice(fresh or options)

    def _begin_attack(self, name, player, bounds):
        self.attack_name = name
        self.last_attack = name
        self.windup_time = self.stats[name + "_windup"]
        self.aim = (player.rect.centerx, player.rect.centery)
        self.set_state("windup")
        audio.play(name + "_windup", self.x, max_seconds=self.windup_time)     # ends exactly when the attack fires
        if name == "drain":
            self._place_drain_circles(player, bounds)
        elif name == "nova":
            self.nova_gap = self.rng.uniform(0, math.tau)
            self.nova_origin = (self.x, self.y)
        elif name == "grasp":
            self._place_hands(player, bounds)
        elif name == "summon":
            self._plan_summons(player, bounds)
        elif name == "rain":
            self._place_rain(player, bounds)
        elif name == "barrage":
            self.barrage_dir = self.rng.choice((-1, 1))
        if self.phase == 3:
            self.shake = max(self.shake, 0.25)              # the enraged Lich King stomps the floor
            audio.play("phase3_stomp", self.x)

    def _do_windup(self, dt, player, bounds):
        locked = (self.attack_name in ("volley", "barrage")
                  and self.state_time >= self.windup_time - AIM_LOCK)
        if not locked:                                      # (the telegraph freezes too: that is your cue to move)
            self.aim = (player.rect.centerx, player.rect.centery)
        if self.state_time >= self.windup_time:
            if self.attack_name == "volley":
                self._fire_volley(player)
            elif self.attack_name == "summon":
                self._summon(player, bounds)
            elif self.attack_name == "barrage":
                self._start_barrage(player)
            elif self.attack_name == "nova":
                self._fire_nova_ring(0, self.nova_origin)
                if self.stats["nova_rings"] > 1:
                    self.scheduled.append([NOVA_SECOND_RING, "nova_ring", 1, self.nova_origin])
            # "drain", "rain" and "grasp" need nothing here: their circles / hands burst on their own timer
            self.set_state("recover")

    def _do_recover(self, dt, player, bounds):
        if self.state_time >= self.stats["recover"]:
            if self.combo_left > 0:                         # phase 3: straight into the second attack
                self.combo_left -= 1
                self.combo_pending = True
                self._go_idle(COMBO_PAUSE)
            elif self.stats["exhaust"] > 0 and not self.shielded:   # the chain is over: he is spent and open
                self.set_state("exhausted")
            elif self._wants_teleport():
                self.set_state("teleport_out")
            else:
                self._go_idle(self.stats["idle"])

    def _wants_teleport(self):
        return (self.phase >= 2 and not self.scheduled
                and self.rng.random() < self.stats["teleport"])

    def _do_exhausted(self, dt, player, bounds):
        """THE WINDOW. He barely moves and takes EXHAUST_BONUS damage until it ends."""
        left, top, right, bottom = bounds
        if not self.scheduled:
            step = self.stats["speed"] * 0.3 * dt
            dx = player.rect.centerx - self.x
            self.x += max(-step, min(step, dx))
            self.x = max(left + self.radius, min(right - self.radius, self.x))
        if self.state_time >= self.stats["exhaust"]:
            if self._wants_teleport():
                self.set_state("teleport_out")
            else:
                self._go_idle(0.5)

    @property
    def shielded(self):
        """Phase 3 SOUL WARD: he can't be hurt while any summon is alive."""
        return (self.phase >= 3 and self.state not in ("dying", "dead")
                and any(m.is_alive() for m in self.minions))

    @property
    def invulnerable(self):
        return super().invulnerable or self.shielded

    def take_damage(self, amount):
        if self.shielded and self.is_alive() and self.state not in self.invulnerable_states:
            self.ward_flash = 0.25                          # the hit rings off the ward
            audio.play("ward_deflect", self.x)
            return 0
        open_hit = self.state == "exhausted" or self.break_time > 0
        if open_hit:
            amount = int(round(amount * EXHAUST_BONUS))
        dealt = super().take_damage(amount)
        if dealt:                                           # a bright ring on top while he is open: the bonus is audible
            audio.play("boss_hit_open" if open_hit else "boss_hit", self.x)
        return dealt

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

    def _do_stunned(self, dt, player, bounds):
        """The Soul Ward shattered: he reels, helpless, until the stun runs out."""
        if self.state_time >= SHIELD_BREAK_WINDOW:
            self._go_idle(0.6)

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

    def _volley_angles(self, target):
        """The direction of every bolt in the fan (also used to draw the telegraph)."""
        count = self.stats["bolts"]
        spread = math.radians(VOLLEY_SPREAD_DEG)
        base = math.atan2(target[1] - self.y, target[0] - self.x)
        return [base + (i - (count - 1) / 2) * spread for i in range(count)]

    def _fire_volley(self, player):
        count = self.stats["bolts"]
        spread = math.radians(VOLLEY_SPREAD_DEG)
        base = math.atan2(self.aim[1] - self.y, self.aim[0] - self.x)
        audio.play("volley_fire", self.x)
        for i in range(count):
            angle = base + (i - (count - 1) / 2) * spread
            self.projectiles.append(
                SoulBolt(self.x, self.y - 6, angle, self.stats["bolt_speed"], VOLLEY_DAMAGE, phase=self.phase))

    def _run_scheduled(self, dt):
        """Things that happen a moment AFTER an attack started (like the second ring of a nova)."""
        due = []
        for item in self.scheduled:
            item[0] -= dt
            if item[0] <= 0:
                due.append(item)
        for item in due:
            self.scheduled.remove(item)
            if item[1] == "nova_ring":
                self._fire_nova_ring(item[2], item[3])
            elif item[1] == "barrage_bolt":
                self._fire_barrage_bolt(item[2])

    def _nova_gap_centre(self, ring):
        """The safe gap of each ring: the second ring's gap is on the opposite side."""
        return self.nova_gap + ring * math.pi

    def _fire_nova_ring(self, ring, origin):
        """A ring of bone shards with a safe gap. Used by Bone Nova."""
        count = self.stats["nova_shards"]
        step = math.tau / count
        gap_half = step * NOVA_GAP_SHARDS / 2.0
        centre = self._nova_gap_centre(ring)
        ox, oy = origin
        for i in range(count):
            angle = i * step + (step / 2 if ring % 2 else 0.0)
            diff = abs((angle - centre + math.pi) % math.tau - math.pi)
            if diff < gap_half:
                continue
            self.projectiles.append(BoneShard(ox, oy, angle, self.stats["nova_speed"], NOVA_DAMAGE))
        self.shake = max(self.shake, 0.35)
        audio.play("nova_blast", ox)
        self.bursts.append(ShockBurst(ox, oy, self.phase, life=0.5, max_radius=300 + 40 * ring))
        self.bursts.append(GroundCracks(ox, oy, self.phase, life=1.0, count=10, length=240,
                                        seed=ring * 7.3 + ox * 0.01))

    def _barrage_angle(self, index):
        """Where bolt number `index` of the current barrage flies: a sweep from one edge of the wedge to the other."""
        b = self.barrage
        n = max(1, b["count"] - 1)
        return b["centre"] + b["dir"] * (-b["half"] + 2 * b["half"] * index / n)

    def _start_barrage(self, player):
        """Soul Barrage: a stream of bolts sweeping across a wedge aimed at the player. Outside the wedge is safe."""
        stats = self.stats
        centre = math.atan2(self.aim[1] - self.y, self.aim[0] - self.x)
        count = stats["barrage_bolts"]
        self.barrage = {"origin": (self.x, self.y - 6), "centre": centre, "dir": self.barrage_dir,
                        "half": math.radians(stats["barrage_sweep"]) / 2, "count": count, "t": 0.0,
                        "dur": count * stats["barrage_interval"]}
        for i in range(count):
            self.scheduled.append([i * stats["barrage_interval"], "barrage_bolt", i])
        audio.play("barrage_blast", self.x)                  # the barrage opens up with one big blast
        self.shake = max(self.shake, 0.2)

    def _fire_barrage_bolt(self, index):
        if not self.barrage:
            return
        ox, oy = self.barrage["origin"]
        audio.play("barrage_bolt", ox)
        self.projectiles.append(SoulBolt(ox, oy, self._barrage_angle(index), self.stats["barrage_speed"],
                                         BARRAGE_DAMAGE, phase=self.phase))

    def _place_rain(self, player, bounds):
        """
        Soul Rain: small circles, one under the player and the rest scattered around them, bursting one after
        another. They are kept apart so there are always gaps between them to stand in (or dash through).
        """
        left, top, right, bottom = bounds
        px, py = player.rect.centerx, player.rect.centery
        radius = self.stats["rain_radius"]
        spots = [(px, py)]
        for _ in range(self.stats["rain_circles"] - 1):
            best = None
            for _attempt in range(25):
                angle = self.rng.uniform(0, math.tau)
                dist = self.rng.uniform(60, 300)
                sx = max(left + 30, min(right - 30, px + math.cos(angle) * dist))
                sy = max(top + 30, min(bottom - 30, py + math.sin(angle) * dist))
                best = (sx, sy)
                if all(math.hypot(sx - ox, sy - oy) >= radius * 1.7 for ox, oy in spots):
                    break
            spots.append(best)
        order = list(range(len(spots)))
        self.rng.shuffle(order)
        for rank, i in enumerate(order):
            sx, sy = spots[i]
            self.hazards.append(SoulRain(sx, sy, radius, self.windup_time + rank * RAIN_STAGGER, RAIN_DAMAGE,
                                         phase=self.phase))

    def _place_hands(self, player, bounds):
        """Grasping Hands: one crack under the player, the rest scattered around them."""
        left, top, right, bottom = bounds
        px, py = player.rect.centerx, player.rect.centery
        spots = [(px, py)]
        for _ in range(self.stats["grasp_hands"] - 1):
            best = None
            for _attempt in range(14):
                angle = self.rng.uniform(0, math.tau)
                dist = self.rng.uniform(75, 200)
                sx = max(left + 30, min(right - 30, px + math.cos(angle) * dist))
                sy = max(top + 30, min(bottom - 30, py + math.sin(angle) * dist))
                best = (sx, sy)
                if all(math.hypot(sx - ox, sy - oy) >= GRASP_RADIUS * 1.6 for ox, oy in spots):
                    break
            spots.append(best)
        for i, (sx, sy) in enumerate(spots):
            self.hazards.append(GraspingHand(
                sx, sy, GRASP_RADIUS, self.windup_time + i * GRASP_STAGGER, GRASP_DAMAGE,
                self.stats["grasp_root"], seed=self.rng.uniform(0, math.tau), phase=self.phase))

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

    def _plan_summons(self, player, bounds):
        """Choose WHAT he will call and WHERE, at the start of the wind-up, so the sigils can be shown."""
        left, top, right, bottom = bounds
        px, py = player.rect.centerx, player.rect.centery
        self.summon_plan = []
        for name in pick_summons(self.rng, self.minions, self.stats["minion_cap"], self.stats["summon_picks"]):
            x = y = 0
            for _attempt in range(10):
                x = self.rng.uniform(left + 40, right - 40)
                y = self.rng.uniform(top + 150, bottom - 40)
                if math.hypot(x - px, y - py) > 180:
                    break
            self.summon_plan.append((name, x, y))

    def _summon(self, player, bounds):
        if not self.summon_plan:
            self._plan_summons(player, bounds)
        audio.play("summon_rise", self.x)
        for name, x, y in self.summon_plan:
            # his army burns with hellfire in phase 2 and 3
            self.minions.append(spawn_monster(name, x, y, variant="cursed", tier=MINION_TIER,
                                              seed=self.rng.random()))
        self.summon_plan = []
        self.wave_raises = 0
        self.free_time = 0.0

    def _pick_new_position(self, player, bounds):
        left, top, right, bottom = bounds
        px = player.rect.centerx
        for _attempt in range(10):
            x = self.rng.uniform(left + 80, right - 80)
            if abs(x - px) > 200:
                break
        self.x = x
        self.y = self.home_y + self.rng.uniform(-40, 40)

    # ------------------------------------------------------------------
    # Minion bookkeeping (the monsters themselves live in src/monsters/)
    # ------------------------------------------------------------------

    def _update_attacks(self, dt, player, bounds):
        # minions that died since last frame keep playing their shatter animation
        died = [m for m in self.minions if not m.is_alive()]
        self.remains.extend(died)
        self.minions = [m for m in self.minions if m.is_alive()]
        for m in self.remains:
            m.update(dt, player, bounds)
        self.remains = [m for m in self.remains if not m.finished]

        for m in self.minions:
            m.allies = self.minions                    # so acolytes can heal their friends
        super()._update_attacks(dt, player, bounds)
        separate(self.minions)
        extra = self.stats["minion_cap"] + 3                   # acolytes may raise a few extra
        if minion_load(self.minions) < extra:
            raised = collect_requests(self.minions, limit=extra)
            if self.phase >= 3:                                # the ward must be breakable: limited raises per wave
                raised = raised[:max(0, WAVE_RAISE_BUDGET - self.wave_raises)]
                self.wave_raises += len(raised)
            self.minions.extend(raised)
        for m in self.minions:
            self.shake = max(self.shake, m.shake)
        self._watch_ward()

    def _stun(self):
        """Interrupt whatever he was doing (unfired attacks are cancelled) and leave him reeling."""
        self.break_time = SHIELD_BREAK_WINDOW
        self.scheduled = []
        self.barrage = None
        self.summon_plan = []
        self.hazards = []
        self.combo_left = 0
        self.combo_pending = False
        self.fade = 1.0
        self.shake = max(self.shake, 0.6)
        self.set_state("stunned")

    def _watch_ward(self):
        """Phase 3: the moment his last summon falls, the Soul Ward shatters and he is open for a while."""
        shielded = self.shielded
        if shielded and not self.was_shielded and self.is_alive():
            audio.play("ward_up", self.x)                   # the barrier snaps shut round him
        if self.was_shielded and not shielded and self.is_alive() and self.phase >= 3 \
                and self.state not in ("transition", "dying", "dead"):
            self._stun()
            audio.play("ward_break", self.x)
            self.bursts.append(ShockBurst(self.x, self.y, 3, life=0.6, max_radius=260))
        self.was_shielded = shielded

    def clear_attacks(self):
        """Phase change or death: every minion shatters instead of just vanishing."""
        self.scheduled = []
        self.barrage = None
        self.summon_plan = []
        self.combo_left = 0
        self.combo_pending = False
        self.break_time = 0.0
        self.was_shielded = False
        self.free_time = 0.0
        for m in self.minions:
            m.kill()
        self.remains.extend(self.minions)
        super().clear_attacks()

    def draw(self, surface):
        for m in self.remains:
            m.draw(surface)
        self._draw_ground_effects(surface)
        super().draw(surface)

    def on_hazard_hit(self, hazard):
        """A drain circle hurt the player, so the Lich King heals. A hand that grabs just shakes the floor."""
        if isinstance(hazard, DrainCircle) and getattr(hazard, "heals", True):
            self.heal(self.stats["drain_heal"])
            audio.play("drain_heal", self.x)
            self.heal_flash = 0.4
            self.drain_lines.append([hazard.x, hazard.y, 0.4])
        else:
            self.shake = max(self.shake, 0.3)

    # ------------------------------------------------------------------
    # Phase changes and death
    # ------------------------------------------------------------------

    def check_phase(self):
        if self.phase < 3 and self.hp <= self.max_hp * PHASE_3_AT:
            self._enter_phase(3)
        elif self.phase == 1 and self.hp <= self.max_hp * PHASE_2_AT:
            self._enter_phase(2)

    def _enter_phase(self, phase):
        self.phase = phase
        self.clear_attacks()
        self.fade = 1.0
        self.shake = 1.0
        self.force_next = "summon"                           # he calls his army the moment he can act again
        audio.music(f"lich_p{phase}", fade=1.2)              # the music gets angrier with him
        self.set_state("transition")

    def on_death(self):
        self.clear_attacks()
        self.fade = 1.0
        self.shake = 1.0
        audio.stop_music(fade=2.5)
        audio.loop("ward_hum", False)
        self.set_state("dying")

    # ------------------------------------------------------------------
    # Drawing  (the pixel art itself lives in art.py)
    # ------------------------------------------------------------------

    def _look(self):
        """Work out how the art should look this frame."""
        phase = 2 if self.phase >= 2 else 1               # phase 3 uses the phase 2 art, enraged
        glow, level, raise_staff = None, 0, False
        pose, pose_progress = None, 0.0

        if self.state == "windup":
            glow = ATTACK_GLOW.get(self.attack_name)
            progress = min(1.0, self.state_time / self.windup_time)
            level = min(3, int(progress * 4))
            raise_staff = self.attack_name == "summon"
            pose, pose_progress = ATTACK_POSE.get(self.attack_name), progress
        elif self.state == "recover":
            pose = "recover"
            pose_progress = min(1.0, self.state_time / max(0.01, self.stats["recover"]))
        elif self.state == "exhausted":
            pose, pose_progress = "recover", 1.0            # slumped: the player's cue to attack
        elif self.state == "transition":
            # Power-up: roaring, eyes blazing, staff raised. Phase 1 -> 2 also flickers between the forms.
            t = self.state_time / self.TRANSITION_TIME
            if self.phase == 2:
                phase = 2 if (t > 0.6 or int(self.state_time * 12) % 2 == 0) else 1
            level, raise_staff = 3, True
            pose, pose_progress = "roar", (self.state_time * 2.5) % 1.0
        elif self.state == "stunned":
            pose = "hurt"                                  # reeling
        elif self.state == "dying":
            pose = "hurt"
        elif self.hit_flash > 0 and self.state in ("idle", "intro"):
            pose = "hurt"                                  # flinch when hit (never hides a wind-up)

        return dict(phase=phase, glow=glow, glow_level=level, raise_staff=raise_staff,
                    flash=self.hit_flash > 0, fade=self.fade, pose=pose, progress=pose_progress,
                    rage=self.rage)

    def draw_boss(self, surface):
        if self.state == "dead":
            return
        look = self._look()
        if self.rage > 0.3 and self.state not in ("dying", "intro"):
            self._draw_afterimages(surface, look)
        self.art.draw(surface, int(self.x), int(self.y), clock=self.clock, **look)

    def _draw_afterimages(self, surface, look):
        """Enraged: ghostly copies trail behind him wherever he has just been."""
        for age, alpha in ((0.24, 0.16), (0.12, 0.3)):
            wanted = self.clock - age
            old = min(self.trail, key=lambda t: abs(t[0] - wanted), default=None)
            if old is None or math.hypot(old[1] - self.x, old[2] - self.y) < 8:
                continue
            ghost = dict(look, flash=False, glow=None, glow_level=0)
            self.art.draw(surface, int(old[1]), int(old[2]), clock=self.clock, alpha=alpha * self.rage,
                          ghost=True, **ghost)

    # ------------------------------------------------------------------
    # Spell visuals. Pixel-art on the same 3px grid as his sprite (see lich_king/effects.py).
    # Telegraphs that lie on the floor are drawn UNDER everyone; the rest on top.
    # ------------------------------------------------------------------

    def _draw_ground_effects(self, surface):
        with clip_to(surface, self.bounds):
            for burst in self.bursts:
                if isinstance(burst, GroundCracks):
                    burst.draw(surface)
            if self.state == "windup":
                if self.attack_name == "volley":
                    self._draw_volley_telegraph(surface)
                elif self.attack_name == "nova":
                    self._draw_nova_ground(surface)
                elif self.attack_name == "summon":
                    self._draw_summon_sigils(surface)
            if (self.state == "windup" and self.attack_name == "barrage") or self.barrage:
                self._draw_barrage_telegraph(surface)

    def _screen_layer(self, surface):
        return FxLayer(0, 0, surface.get_width(), surface.get_height())

    def _draw_volley_telegraph(self, surface):
        """Every bolt's path as a glowing lane with soul-light racing along it and runes on the floor."""
        colors = theme(self.phase)
        progress = min(1.0, self.state_time / self.windup_time)
        flash = max(0.0, (progress - 0.75) / 0.25)
        ox, oy = self.x, self.y - 6
        fx = self._screen_layer(surface)
        length = 760.0
        for angle in self._volley_angles(self.aim):
            ca, sa = math.cos(angle), math.sin(angle)
            px, py = -sa, ca
            width = 7 + 5 * progress
            for k, (d0, d1, alpha) in enumerate(((30, 230, 120), (230, 460, 80), (460, length, 45))):
                w0, w1 = width * (1 - 0.1 * k), width * (1 - 0.1 * (k + 1))
                fx.polygon([(ox + ca * d0 + px * w0, oy + sa * d0 + py * w0),
                            (ox + ca * d1 + px * w1, oy + sa * d1 + py * w1),
                            (ox + ca * d1 - px * w1, oy + sa * d1 - py * w1),
                            (ox + ca * d0 - px * w0, oy + sa * d0 - py * w0)],
                           with_alpha(colors["glow"], alpha + 70 * flash), soft=True)
            fx.line((ox + ca * 36, oy + sa * 36), (ox + ca * 330, oy + sa * 330),
                    with_alpha(lerp_color(colors["main"], colors["hot"], flash), 230))
            for i in range(4):                                       # soul-light racing outwards along the lane
                d = ((self.clock * (1.2 + progress * 1.6) + i / 4.0) % 1.0) * 520 + 40
                fx.dot(ox + ca * d, oy + sa * d, colors["hot"], size=2)
            for d in (120, 240, 360):                                # runes carved along the lane
                fx.glyph(ox + ca * d, oy + sa * d, int(d / 40), with_alpha(colors["main"], 220))
        fx.draw(surface)

    def _draw_barrage_telegraph(self, surface):
        """
        The wedge the bolts will sweep through: glowing edges, chevrons showing which way the sweep runs, and (while
        it is firing) a bright marker at the bolt being fired right now. EVERYTHING OUTSIDE THE WEDGE IS SAFE.
        """
        colors = theme(self.phase)
        stats = self.stats
        if self.barrage:
            (ox, oy), centre = self.barrage["origin"], self.barrage["centre"]
            half, direction = self.barrage["half"], self.barrage["dir"]
            progress = min(1.0, self.barrage["t"] / max(0.01, self.barrage["dur"]))
            flash, live = 0.0, True
        else:
            ox, oy = self.x, self.y - 6
            centre = math.atan2(self.aim[1] - oy, self.aim[0] - ox)
            half, direction = math.radians(stats["barrage_sweep"]) / 2, self.barrage_dir
            progress = min(1.0, self.state_time / self.windup_time)
            flash, live = max(0.0, (progress - 0.75) / 0.25), False
        fx = self._screen_layer(surface)
        reach = 780.0
        arc = [centre - half + 2 * half * i / 10.0 for i in range(11)]
        wedge = [(ox, oy)] + [(ox + math.cos(a) * reach, oy + math.sin(a) * reach) for a in arc]
        fx.polygon(wedge, with_alpha(ATTACK_GLOW["barrage"], (38 if live else 30 + 40 * progress) + 60 * flash),
                   soft=True)
        for edge in (arc[0], arc[-1]):
            fx.line((ox + math.cos(edge) * 50, oy + math.sin(edge) * 50),
                    (ox + math.cos(edge) * reach, oy + math.sin(edge) * reach),
                    with_alpha(lerp_color(ATTACK_GLOW["barrage"], colors["hot"], flash), 230))
        for k in range(5):                                           # chevrons riding along the sweep direction
            u = (self.clock * 0.9 + k / 5.0) % 1.0
            a = centre + direction * (-half + 2 * half * u)
            for d in (170, 330, 490):
                chevron(fx, ox + math.cos(a) * d, oy + math.sin(a) * d, a + direction * math.pi / 2, 8,
                        with_alpha(colors["hot"], 235))
        if live:                                                     # the bolt being fired right now
            a = centre + direction * (-half + 2 * half * progress)
            fx.line((ox + math.cos(a) * 40, oy + math.sin(a) * 40),
                    (ox + math.cos(a) * reach, oy + math.sin(a) * reach), with_alpha(colors["hot"], 200))
        fx.draw(surface)

    def _draw_exhausted(self, surface, cx, cy):
        """He is spent: a golden ring pulses round him, arrows point in at him, and a timer of dots runs down."""
        total = max(0.01, self.stats["exhaust"])
        left = max(0.0, 1.0 - self.state_time / total)
        pulse = 0.5 + 0.5 * math.sin(self.clock * 10.0)
        radius = self.radius + 26 + 6 * pulse
        fx = self._screen_layer(surface)
        fx.circle((cx, cy), radius + 8, with_alpha(EXHAUST_GLOW, 55 + 55 * pulse), soft=True)
        shock_ring(fx, cx, cy, radius, with_alpha(EXHAUST_GLOW, 255), with_alpha(BONE_LIGHT, 255), thickness=2)
        for i in range(8):
            a = i * math.tau / 8 + self.clock * 0.6
            chevron(fx, cx + math.cos(a) * (radius + 20 - 5 * pulse), cy + math.sin(a) * (radius + 20 - 5 * pulse),
                    a + math.pi, 9, with_alpha(EXHAUST_GLOW, 255))
        for i in range(int(48 * left)):
            a = -math.pi / 2 + i * math.tau / 48
            fx.dot(cx + math.cos(a) * (radius + 42), cy + math.sin(a) * (radius + 42), EXHAUST_GLOW, size=2)
        fx.draw(surface)

    def _draw_ward(self, surface, cx, cy):
        """SOUL WARD: a violet barrier round him, with a soul-light tether to every summon that keeps it alive."""
        pulse = 0.5 + 0.5 * math.sin(self.clock * 4.0)
        hit = min(1.0, self.ward_flash / 0.25)
        radius = self.radius + 34 + 3 * pulse + 6 * hit
        fx = self._screen_layer(surface)
        for i, m in enumerate(m for m in self.minions if m.is_alive()):
            soul_ribbon(fx, (m.x, m.y - 10), (cx, cy - 20), self.clock, SHIELD, seed=i * 2.3, dots=14, amplitude=10.0)
            fx.circle((m.x, m.y - 4), m.radius + 8 + 2 * pulse, with_alpha(SHIELD, 150), width=1)   # marks what to kill
        fx.circle((cx, cy), radius, with_alpha(SHIELD, 40 + 40 * pulse + 110 * hit), soft=True)
        shock_ring(fx, cx, cy, radius, with_alpha(lerp_color(SHIELD, SHIELD_HOT, hit), 255),
                   with_alpha(SHIELD_HOT, 230), thickness=2)
        rune_ring(fx, cx, cy, radius - 10, with_alpha(SHIELD_HOT, 235), self.clock * 0.8, count=12, speed=0.6)
        hexagram(fx, cx, cy - 6, radius * 0.55, with_alpha(SHIELD, 200), self.clock * 0.7)
        fx.draw(surface)

    def _draw_ward_broken(self, surface, cx, cy):
        """The ward has shattered: shards of violet light fly off him while the bonus damage window lasts."""
        left = self.break_time / SHIELD_BREAK_WINDOW
        fx = self._screen_layer(surface)
        radius = self.radius + 30 + 40 * (1 - left)
        for i in range(10):
            a = i * math.tau / 10 + 0.3
            spike(fx, cx + math.cos(a) * radius, cy + math.sin(a) * radius, a, 12 * left + 3, 4,
                  with_alpha(lerp_color(SHIELD, SHIELD_HOT, left), 255 * left))
        shock_ring(fx, cx, cy, self.radius + 18 + 4 * math.sin(self.clock * 12), with_alpha(EXHAUST_GLOW, 255),
                   with_alpha(BONE_LIGHT, 255), thickness=2)
        fx.draw(surface)

    def _draw_stun_stars(self, surface, cx, cy):
        """Little soul-skulls circle his head while he is stunned."""
        fx = self._screen_layer(surface)
        for i in range(4):
            a = self.clock * 5.0 + i * math.tau / 4
            soul_skull(fx, cx + math.cos(a) * 36, cy - self.radius - 34 + math.sin(a) * 9,
                       with_alpha(lerp_color(SHIELD_HOT, EXHAUST_GLOW, 0.5 + 0.5 * math.sin(a)), 255))
        fx.draw(surface)

    def _nova_progress(self):
        progress = min(1.0, self.state_time / self.windup_time)
        return progress, max(0.0, (progress - 0.78) / 0.22)

    def _draw_nova_ground(self, surface):
        """
        On the FLOOR: a faint dithered haze marks everything as danger, EXCEPT the safe gap which glows green
        with arrows flowing outwards. (Phase 3 shows the second ring's gap dimmer, on the opposite side.)
        """
        ox, oy = self.nova_origin
        gap_half = math.tau / self.stats["nova_shards"] * NOVA_GAP_SHARDS / 2.0
        progress, flash = self._nova_progress()
        fx = self._screen_layer(surface)
        reach = 780.0
        fx.circle((ox, oy), reach, with_alpha((200, 60, 70), 38 + 60 * flash), soft=True)
        for ring in range(self.stats["nova_rings"]):
            centre = self._nova_gap_centre(ring)
            green = SAFE if ring == 0 else SAFE_DIM
            arc = [centre - gap_half + gap_half * 2 * i / 8.0 for i in range(9)]
            wedge = [(ox, oy)] + [(ox + math.cos(a) * reach, oy + math.sin(a) * reach) for a in arc]
            fx.polygon(wedge, with_alpha(green, (95 if ring == 0 else 60) + 70 * flash), soft=True)
            for edge in (arc[0], arc[-1]):
                fx.line((ox + math.cos(edge) * 130, oy + math.sin(edge) * 130),
                        (ox + math.cos(edge) * reach, oy + math.sin(edge) * reach), with_alpha(green, 215))
            for k in range(7):                                       # arrows streaming outwards through the gap
                d = ((self.clock * 150 + k * 78) % 520) + 140
                chevron(fx, ox + math.cos(centre) * d, oy + math.sin(centre) * d, centre, 9, green)
        fx.draw(surface)

    def _draw_nova_overlay(self, surface):
        """Above him: a ring of runes, a pale spike for every shard that is about to fly, and a filling charge arc."""
        colors = theme(self.phase)
        ox, oy = self.nova_origin
        count = self.stats["nova_shards"]
        step = math.tau / count
        gap_half = step * NOVA_GAP_SHARDS / 2.0
        progress, flash = self._nova_progress()
        fx = self._screen_layer(surface)
        for ring in range(self.stats["nova_rings"]):
            centre = self._nova_gap_centre(ring)
            ring_radius = 128 + 18 * ease_out(progress) + 34 * ring
            for i in range(count):
                angle = i * step + (step / 2 if ring % 2 else 0.0)
                if abs((angle - centre + math.pi) % math.tau - math.pi) < gap_half:
                    continue
                tone = lerp_color(BONE if ring == 0 else (130, 124, 150), colors["hot"], flash)
                spike(fx, ox + math.cos(angle) * ring_radius, oy + math.sin(angle) * ring_radius, angle,
                      14 + 8 * flash, 4, tone)
        rune_ring(fx, ox, oy, 104, with_alpha(BONE, 235), self.clock * 1.4, count=10, speed=0.9)
        for i in range(int(56 * progress)):
            a = -math.pi / 2 + i * math.tau / 56
            fx.dot(ox + math.cos(a) * 176, oy + math.sin(a) * 176,
                   lerp_color(colors["main"], colors["hot"], flash), size=2)
        fx.draw(surface)

    def _draw_nova_telegraph(self, surface):
        """The whole nova telegraph (floor and overlay together)."""
        self._draw_nova_ground(surface)
        self._draw_nova_overlay(surface)

    def _draw_summon_sigils(self, surface):
        """Necromantic sigils open where his army will rise, with soul-light flowing to each from him."""
        colors = theme(self.phase)
        progress = min(1.0, self.state_time / self.windup_time)
        fx = self._screen_layer(surface)
        for i, (name, x, y) in enumerate(self.summon_plan):
            r = (26 + 14 * ease_out(progress)) * (1.5 if name == "skeleton_brute" else 1.0)
            soul_ribbon(fx, (self.x, self.y - 20), (x, y), self.clock, colors["main"], seed=i * 1.7)
            fx.circle((x, y), r, with_alpha(colors["dark"], 150), soft=True)
            fx.circle((x, y), r * 0.6 * progress + 3, with_alpha(colors["glow"], 130), soft=True)
            rune_ring(fx, x, y, r, colors["main"], self.clock + i, count=8, speed=0.7)
            hexagram(fx, x, y, r * 0.55, with_alpha(colors["glow"], 240), -self.clock * 0.9)
        fx.draw(surface)

    def draw_effects(self, surface):
        cx, cy = int(self.x), int(self.y)
        fx = None
        if self.state == "windup" and self.attack_name == "nova":
            self._draw_nova_overlay(surface)
        for burst in self.bursts:
            if isinstance(burst, ShockBurst):
                burst.draw(surface)
        if self.drain_lines or self.heal_flash > 0:
            fx = self._screen_layer(surface)
            for x, y, life in self.drain_lines:                       # stolen life flows to him as soul-light
                soul_ribbon(fx, (x, y), (cx, cy - 20), self.clock, HEAL, seed=x * 0.01, dots=18)
            if self.heal_flash > 0:
                shock_ring(fx, cx, cy, 64 + 30 * (1 - self.heal_flash / 0.4), with_alpha(HEAL, 255),
                           with_alpha(SAFE_DIM, 255), thickness=1)
            fx.draw(surface)
        if self.shielded:
            self._draw_ward(surface, cx, cy)
        elif self.break_time > 0 and self.state not in ("dying", "dead"):
            self._draw_ward_broken(surface, cx, cy)
            if self.state == "stunned":
                self._draw_stun_stars(surface, cx, cy)
        if self.state == "exhausted":
            self._draw_exhausted(surface, cx, cy)
        if self.state == "transition":
            self._draw_transformation_rings(surface, cx, cy)
        elif self.state == "dying":
            self._draw_death_burst(surface, cx, cy)

    def _draw_transformation_rings(self, surface, cx, cy):
        """Rune-studded shockwaves roll out of him as he changes form."""
        t = self.state_time / self.TRANSITION_TIME
        colors = theme(3 if self.phase == 3 else 2)
        fx = self._screen_layer(surface)
        for k in range(4):
            u = t * 1.7 - k * 0.28
            if 0.0 < u < 1.0:
                radius = 50 + ease_out(u) * 520
                main = colors["hot"] if u < 0.35 else colors["main"]
                fade = 1.0 - 0.7 * u
                shock_ring(fx, cx, cy, radius, with_alpha(main, 255 * fade), with_alpha(colors["glow"], 255 * fade),
                           thickness=2, runes=True, clock=self.clock)
                fx.circle((cx, cy), radius * 0.97, with_alpha(colors["glow"], 32 * fade), soft=True)
        fx.draw(surface)

    def _draw_death_burst(self, surface, cx, cy):
        """A last shockwave, then his souls rise away as little ghost skulls while he dissolves."""
        u = self.state_time / self.DYING_TIME
        colors = theme(2)
        fx = self._screen_layer(surface)
        if u < 0.35:
            radius = 40 + ease_out(u / 0.35) * 420
            shock_ring(fx, cx, cy, radius, with_alpha(BONE_LIGHT, 255), with_alpha(colors["glow"], 255),
                       thickness=2, runes=True, clock=self.clock)
        for i in range(22):
            t = u * 1.25 - i * 0.025
            if not 0.0 < t < 1.0:
                continue
            x = cx + math.sin(i * 2.1 + t * 3.0) * (28 + 70 * t)
            y = cy + 10 - t * 300
            tone = lerp_color(BONE_LIGHT, colors["glow"], t)
            soul_skull(fx, x, y, with_alpha(tone, 255 * (1 - 0.6 * t)))
        fx.draw(surface)

    # ------------------------------------------------------------------
    # Health bar: a second tick at 20% (where he is enraged) and a hot colour in phase 3
    # ------------------------------------------------------------------

    def draw_health_bar(self, surface, font):
        super().draw_health_bar(surface, font)
        w, h = 520, 18
        x = (surface.get_width() - w) // 2
        y = 36
        if self.phase == 3:
            fill = int(w * self.hp_percent())
            if fill > 0:
                pygame.draw.rect(surface, (255, 150, 60), (x, y, fill, h))
                pygame.draw.rect(surface, (255, 220, 150), (x, y, fill, 4))
        pygame.draw.line(surface, (238, 237, 254), (x + w // 2, y - 3), (x + w // 2, y + h + 3), 2)
        tick = x + int(w * PHASE_3_AT)
        pygame.draw.line(surface, (255, 190, 120), (tick, y - 3), (tick, y + h + 3), 2)
        if self.shielded:                                            # phase 3: tell the player what to do
            alive = sum(1 for m in self.minions if m.is_alive())
            label = font.render(f"SOUL WARD  -  INVULNERABLE!  Destroy the summons ({alive} left)", True, SHIELD_HOT)
            surface.blit(label, ((surface.get_width() - label.get_width()) // 2, y + h + 8))
            pygame.draw.rect(surface, SHIELD, (x, y, int(w * self.hp_percent()), 4))
        elif self.break_time > 0 and self.state != "exhausted":
            label = font.render("WARD SHATTERED  -  BOSS STUNNED!  STRIKE NOW!  (+50% damage)", True, EXHAUST_GLOW)
            surface.blit(label, ((surface.get_width() - label.get_width()) // 2, y + h + 8))
        elif self.state == "exhausted":                              # tell the player this is their window
            if self.phase < 3:                                       # (phase 3 already repaints the fill)
                pygame.draw.rect(surface, EXHAUST_GLOW, (x, y, int(w * self.hp_percent()), 4))
            label = font.render("SOULFIRE SPENT  -  STRIKE NOW!  (+50% damage)", True, EXHAUST_GLOW)
            surface.blit(label, ((surface.get_width() - label.get_width()) // 2, y + h + 8))
