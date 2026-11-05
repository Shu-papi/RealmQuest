"""
in_game.py - The Lich King's skeletons as ordinary game enemies (dungeon rooms, night raids).

The skeletons were written for an arena: a 960x640 window, a 100-HP hero, a 20-damage sword,
`update(dt, player, bounds)` with `player.rect` / `player.take_damage`, and `draw(surface)` at their own
x, y with no camera. The game has a scrolling camera, a 40-HP hero, a 2-damage sword and `PlayerCombat.hurt`.
This module sits between the two, so neither side changes:

    host = SkeletonHost(room_x, room_y, room_w, room_h, "dungeon", ground=dungeon)    # world pixels
    enemy = host.add("skeleton_archer", world_x, world_y)       # -> SkeletonEnemy, a combat.Enemy look-alike
    warden = make_warden(host, x, y, "Bone Warden", "cursed")   # a big, recoloured mini-boss

    every frame:  enemy.update(dt, player, dungeon, pc)   (each one)   then   host.step(dt)
                  enemy.take_damage(n); enemy.dead; enemy.hp; enemy.max_hp   (game units)
                  host.draw(surface, cam_x, cam_y)        (draws them all, and the ones still falling apart)
                  host.new_members()                      skeletons an acolyte raised (no XP for those)

RULES holds the numbers that convert between the two worlds (tune them there):
    tier       which monsters.TIERS row they use (health / damage / speed)
    hp_power   a hit of 2 does 2 x hp_power to the skeleton; the HP the game sees is divided by it
    damage_k   every skeleton hit on the hero is multiplied by it (then PlayerCombat applies defence)
"""
import math
import random

import pygame

from . import TIERS, collect_requests, separate, spawn_monster

RULES = {
    "dungeon": {"tier": "veteran", "hp_power": 4.0, "damage_k": 0.3},
    "raid": {"tier": "normal", "hp_power": 4.0, "damage_k": 0.3},
}

# The room roster: weights, and the most of a kind one room may hold (like the Goblin Shaman cap)
ROSTER_WEIGHTS = {"skeleton_warrior": 3.0, "skeleton_archer": 2.0, "skeleton_acolyte": 1.0, "skeleton_brute": 1.0}
ROSTER_CAPS = {"skeleton_acolyte": 1, "skeleton_brute": 1}
DISPLAY = {"skeleton_warrior": "Skeleton Warrior", "skeleton_archer": "Skeleton Archer",
           "skeleton_acolyte": "Skeleton Acolyte", "skeleton_brute": "Bone Brute"}

WARDEN_SIZE = 1.7            # the mini-boss: a skeleton warrior this much bigger...
WARDEN_TIER = "elite"        # ...with elite stats...
WARDEN_HP = 3.0              # ...and this much more health on top
# Health trims so the room's pecking order is right (warrior 8 < brute 16 < guard brute 25 < Warden 37 in the dungeon):
# the brute's arena health (90) is four warriors' worth, too much for a room regular
HP_TRIM = {"skeleton_brute": 0.45}
HERO_RADIUS = 12
HERO_LIFT = 10               # skeletons aim at the hero's body, not at the feet
RAISED_LIMIT = 10            # most skeletons one host holds (acolytes stop raising)


def skeleton_roster(rng, count):
    """`count` monster names for one room: weighted, at most ROSTER_CAPS of a kind, then shuffled."""
    names = list(ROSTER_WEIGHTS)
    out = []
    for _ in range(count):
        options = [n for n in names if out.count(n) < ROSTER_CAPS.get(n, count)]
        out.append(rng.choices(options, weights=[ROSTER_WEIGHTS[n] for n in options])[0])
    rng.shuffle(out)
    return out


class Painter:
    """Draw arena-style things (they draw at their own x, y) onto a scrolling screen.

    The part of the screen over the host's box is copied onto a box-sized surface, the things draw on it in
    box coordinates, and it is pasted back. Glows and additive effects blend with the real floor that way."""

    def __init__(self, ox, oy, w, h):
        self.ox, self.oy, self.w, self.h = ox, oy, int(w), int(h)
        self.layer = None

    def paint(self, surf, cam_x, cam_y, draw_fn):
        ox, oy = int(self.ox) - int(cam_x), int(self.oy) - int(cam_y)    # the box's corner on the screen
        sw, sh = surf.get_size()
        x0, y0 = max(0, -ox), max(0, -oy)
        x1, y1 = min(self.w, sw - ox), min(self.h, sh - oy)
        if x1 <= x0 or y1 <= y0:
            return
        if self.layer is None:
            self.layer = pygame.Surface((self.w, self.h))
        area = pygame.Rect(x0, y0, x1 - x0, y1 - y0)
        self.layer.blit(surf, (x0, y0), pygame.Rect(x0 + ox, y0 + oy, area.w, area.h))
        draw_fn(self.layer)
        surf.blit(self.layer, (x0 + ox, y0 + oy), area)


class HeroTarget:
    """What a skeleton reads from 'the player': rect, x, y, radius, take_damage (in host coordinates).
    take_damage calls `hurt(amount)`, so the same target can stand for the hero or for the village ward."""

    radius = HERO_RADIUS

    def __init__(self, host, hurt=None):
        self.host = host
        self.hurt = hurt
        self.rect = pygame.Rect(0, 0, HERO_RADIUS * 2, HERO_RADIUS * 2)
        self.x = self.y = 0.0

    def aim(self, world_x, world_y):
        self.x, self.y = world_x - self.host.ox, world_y - self.host.oy
        self.rect.center = (round(self.x), round(self.y))

    def take_damage(self, amount):
        return self.hurt(amount) if self.hurt else 0


class SkeletonEnemy:
    """One skeleton, seen by the game as a combat.Enemy (x, y = its feet, in world pixels)."""

    skin = None
    summoned = False

    def __init__(self, host, monster, kind="normal", name=None, cc_immune=False, no_reward=False):
        self.host = host
        self.monster = monster
        self.kind = kind
        self.name = name or DISPLAY.get(monster.NAME, "Skeleton")
        self.cc_immune = cc_immune
        self.no_reward = no_reward
        self.damage = 0
        self.stun_t = self.slow_t = self.hit_flash = 0.0
        self.target = None                    # a raider has its own target (the road / the ward)

    @property
    def x(self):
        return self.host.ox + self.monster.x

    @property
    def y(self):
        return self.host.oy + self.monster.foot_y

    @property
    def radius(self):
        return self.monster.radius

    @property
    def hp(self):
        return self.monster.hp / self.host.hp_power

    @property
    def max_hp(self):
        return self.monster.max_hp / self.host.hp_power

    @property
    def dead(self):
        return not self.monster.is_alive()

    def take_damage(self, amount):
        hero = self.host.hero                 # the hit pushes it away from the hero (knockback wants a point)
        if not self.dead and self.monster.take_damage(amount * self.host.hp_power, source=(hero.x, hero.y)):
            self.hit_flash = 0.12

    def pop_sounds(self):
        return []                             # skeletons play their own sounds (audio package)

    def update(self, dt, player, dungeon, pc):
        self.host.hero_from(player, pc, dungeon)
        self.run(dt, self.host.hero)

    def run(self, dt, target):
        """One frame of the skeleton's own AI against `target` (stun / slow from the hero's skills apply)."""
        self.hit_flash = max(0.0, self.hit_flash - dt)
        if self.dead:
            return
        if self.stun_t > 0:
            self.stun_t = max(0.0, self.stun_t - dt)
            return
        if self.slow_t > 0:
            self.slow_t = max(0.0, self.slow_t - dt)
            dt *= 0.5
        m = self.monster
        before = (m.x, m.y)
        self.host.attacker = self
        m.update(dt, target, self.host.bounds)
        self.host.keep_out_of_walls(m, before)

    def draw(self, surf, cx, cy):
        pass                                  # the host draws every skeleton in one go


class SkeletonHost:
    """A box of the world (a dungeon room, the north road) where skeletons fight."""

    def __init__(self, ox, oy, w, h, rules="dungeon", ground=None, edge=12, seed=None):
        cfg = RULES[rules]
        self.rules = rules
        self.ox, self.oy, self.w, self.h = float(ox), float(oy), int(w), int(h)
        self.tier = known_tier(cfg["tier"])
        self.hp_power = float(cfg["hp_power"])
        self.damage_k = float(cfg["damage_k"])
        self.bounds = (edge, edge, self.w - edge, self.h - edge)
        self.ground = ground
        self.rng = random.Random(seed)
        self.members = []                     # SkeletonEnemy, alive
        self.remains = []                     # Monsters still falling apart
        self.fresh = []                       # raised this frame, not yet handed to the game
        self.attacker = None                  # the skeleton being updated (where a hit on the hero comes from)
        self.hero = HeroTarget(self, self._hurt_hero)
        self.raise_as = (SkeletonEnemy, {})    # what the raised dead become (a raid makes them raiders)
        self._player = self._pc = self._ground = None
        self.painter = Painter(self.ox, self.oy, self.w, self.h)

    # ---- making skeletons ------------------------------------------------------------------
    def add(self, name, world_x, world_y, kind="normal", variant="bone", size=1.0, tier=None, hp_scale=1.0,
            display=None, cc_immune=False, poise=None, spawn=True, proxy=SkeletonEnemy, **extra):
        m = spawn_monster(name, world_x - self.ox, world_y - self.oy - _foot(name, size),
                          tier=known_tier(tier or self.tier), variant=variant, size=size, spawn=spawn,
                          seed=self.rng.random())
        hp_scale *= HP_TRIM.get(name, 1.0)
        m.extra_hp = hp_scale                 # (refresh_config keeps the trim / warden multiplier)
        if hp_scale != 1.0:
            m.max_hp = m.hp = max(1, int(round(m.max_hp * hp_scale)))
        if poise is not None:
            m.POISE = poise
        enemy = proxy(self, m, kind=kind, name=display, cc_immune=cc_immune, **extra)
        self.members.append(enemy)
        return enemy

    def new_members(self):
        out, self.fresh = self.fresh, []
        return out

    # ---- the hero ---------------------------------------------------------------------------
    def hero_from(self, player, pc, ground):
        self._player, self._pc, self._ground = player, pc, ground
        self.hero.aim(player.x, player.y - HERO_LIFT)

    def _hurt_hero(self, amount):
        pc, a = self._pc, self.attacker
        if pc is None:
            return 0
        damage = max(1, round(amount * self.damage_k))
        fx, fy = (a.x, a.y) if a is not None else (self._player.x, self._player.y)
        return damage if pc.hurt(damage, self._player, self._ground, fx, fy) else 0

    def keep_out_of_walls(self, m, before):
        """Undo a step (or a knockback) that would put a skeleton's feet in a wall or a tree."""
        g = self.ground
        if g is None or (m.x, m.y) == before:
            return
        ox, oy, lift = self.ox, self.oy, m.foot_y - m.y
        if g.can_stand(ox + m.x, oy + m.y + lift):
            return
        bx, by = before
        if g.can_stand(ox + m.x, oy + by + lift):          # slide along the wall
            m.y = by
        elif g.can_stand(ox + bx, oy + m.y + lift):
            m.x = bx
        elif g.can_stand(ox + bx, oy + by + lift):
            m.x, m.y = bx, by
        else:                                              # it was already stuck in a wall: get it out
            self.unstick(m)

    def unstick(self, m):
        """Move a skeleton whose feet are inside a wall to the nearest free spot."""
        g = self.ground
        if g is None:
            return
        lift = m.foot_y - m.y
        for rad in range(1, 13):
            r = rad * 8
            for k in range(12):
                a = k * math.pi / 6
                nx, ny = m.x + math.cos(a) * r, m.y + math.sin(a) * r
                if g.can_stand(self.ox + nx, self.oy + ny + lift):
                    m.x, m.y = nx, ny
                    return

    def refresh_config(self):
        """The config files changed: the host's rules and every living skeleton read their numbers again."""
        cfg = RULES.get(self.rules, {})
        self.tier = known_tier(cfg.get("tier", self.tier))
        self.hp_power = float(cfg.get("hp_power", self.hp_power))
        self.damage_k = float(cfg.get("damage_k", self.damage_k))
        for e in self.members:
            fn = getattr(e.monster, "refresh_config", None)
            if fn is not None and not e.dead:
                fn()

    # ---- every frame --------------------------------------------------------------------------
    def step(self, dt):
        """Group behaviour (spacing, acolytes raising the dead) and the death animations."""
        alive = [e.monster for e in self.members if not e.dead]
        for m in alive:
            m.allies = alive
        before = [(m.x, m.y) for m in alive]
        separate(alive)
        for m, b in zip(alive, before):      # the spacing push must not shove one into a wall
            self.keep_out_of_walls(m, b)
        for baby in collect_requests(alive, limit=RAISED_LIMIT):
            cls, extra = self.raise_as
            raised = cls(self, baby, no_reward=True, **extra)       # raised dead: no XP, or it could be farmed
            self.members.append(raised)
            self.fresh.append(raised)
        for e in [e for e in self.members if e.dead]:
            self.members.remove(e)
            self.remains.append(e.monster)
        for m in self.remains:
            m.update(dt, self.hero, self.bounds)                    # (its arrows still fly while it falls apart)
        self.remains = [m for m in self.remains if not m.finished]

    @property
    def done(self):
        return not self.members and not self.remains

    def clear(self):
        self.members, self.remains, self.fresh = [], [], []

    # ---- drawing ---------------------------------------------------------------------------------
    def draw(self, surf, cam_x, cam_y):
        if self.done:
            return
        everyone = sorted(self.remains + [e.monster for e in self.members], key=lambda m: m.foot_y)
        self.painter.paint(surf, cam_x, cam_y, lambda layer: [m.draw(layer) for m in everyone])

    def shake(self):
        return max([e.monster.shake for e in self.members] + [0.0])


def known_tier(tier):
    """A tier name from the config, or "normal" (with a warning) if there is no such tier: a typo in
    skeleton_army.toml / skeleton_warden.toml must never crash the game."""
    if tier in TIERS:
        return tier
    try:
        _balance.warn(f"unknown tier '{tier}' - using 'normal'. Known tiers: {', '.join(TIERS)}.")
    except NameError:                                     # (before the config part below is loaded)
        pass
    return "normal"


def _foot(name, size):
    """Pixels from a monster's body (x, y) down to its feet (so `add` can take the feet position)."""
    from . import MONSTERS                    # noqa: PLC0415
    return MONSTERS[name].FOOT * size


def make_warden(host, world_x, world_y, name, variant="cursed", proxy=SkeletonEnemy, **extra):
    """The skeleton mini-boss: a skeleton warrior, WARDEN_SIZE bigger, recoloured, elite, no stagger."""
    return host.add("skeleton_warrior", world_x, world_y, kind="elite", variant=variant, size=WARDEN_SIZE,
                    tier=WARDEN_TIER, hp_scale=WARDEN_HP, display=name, cc_immune=True, poise=True,
                    proxy=proxy, **extra)


def distance(ax, ay, bx, by):
    return math.hypot(ax - bx, ay - by)


# ======================================================================================================
# CONFIG FILES: config/monsters/skeleton_warden.toml and config/monsters/skeleton_army.toml (src/balance.py).
# Each skeleton's own stats are in config/monsters/skeleton_<kind>.toml.
# ======================================================================================================
try:
    import balance as _balance                              # src/ is on the path
except ImportError:                                         # run as src.monsters
    from src import balance as _balance


def _rule(place, key):
    return _balance.Prop(lambda: RULES[place][key], lambda v: RULES[place].__setitem__(key, v))


def _weight(name):
    return _balance.Prop(lambda: ROSTER_WEIGHTS[name], lambda v: ROSTER_WEIGHTS.__setitem__(name, v))


def _cap(name):
    return _balance.Prop(lambda: ROSTER_CAPS[name], lambda v: ROSTER_CAPS.__setitem__(name, v))


_balance.declare(
    "monsters", "skeleton_warden", "SKELETON WARDEN",
    "MINI-BOSS of the Lich King Dungeon, Ashen Pit and Bone Hollow (Bone / Cinder / Hollow Warden), and the "
    "Barrow Warden of the north-road raid: a skeleton warrior, bigger and recoloured.",
    globals(), {"size": "WARDEN_SIZE", "tier": "WARDEN_TIER", "hp_multiplier": "WARDEN_HP"},
    docs={"size": "How much bigger than a skeleton warrior it is (its art grows in whole pixels).",
          "tier": "Which tier of config/tiers.toml it uses (health / damage / speed).",
          "hp_multiplier": "Extra health on top of the tier."})
_balance.declare(
    "monsters", "skeleton_army", "THE SKELETON ARMY (outside the boss room)",
    "How the Lich King's skeletons fill the Lich King Dungeon rooms and the north-road raid. "
    "Each skeleton's own stats: skeleton_<kind>.toml.",
    globals(),
    {"room_tier": _rule("dungeon", "tier"), "room_hp_power": _rule("dungeon", "hp_power"),
     "room_damage_k": _rule("dungeon", "damage_k"),
     "raid_tier": _rule("raid", "tier"), "raid_hp_power": _rule("raid", "hp_power"),
     "raid_damage_k": _rule("raid", "damage_k"),
     "warrior_weight": _weight("skeleton_warrior"), "archer_weight": _weight("skeleton_archer"),
     "acolyte_weight": _weight("skeleton_acolyte"), "brute_weight": _weight("skeleton_brute"),
     "max_acolytes": _cap("skeleton_acolyte"), "max_brutes": _cap("skeleton_brute"),
     "brute_hp_trim": _balance.Prop(lambda: HP_TRIM["skeleton_brute"], lambda v: HP_TRIM.__setitem__("skeleton_brute", v))},
    docs={"room_tier": "Tier (config/tiers.toml) of the skeletons in dungeon rooms.",
          "room_hp_power": "A sword hit of 2 does 2 x this to a skeleton in a room (bigger = they die faster).",
          "room_damage_k": "Every skeleton hit on the hero in a room is multiplied by this.",
          "raid_tier": "Tier of the skeletons in the north-road night raid.",
          "raid_hp_power": "Same as room_hp_power, for the raid.",
          "raid_damage_k": "Same as room_damage_k, for the raid.",
          "warrior_weight": "How often a room rolls a skeleton warrior (higher = more often).",
          "archer_weight": "...a skeleton archer.", "acolyte_weight": "...a skeleton acolyte.",
          "brute_weight": "...a bone brute.",
          "max_acolytes": "Most acolytes in one room.", "max_brutes": "Most bone brutes in one room.",
          "brute_hp_trim": "A bone brute's health x this (its arena health is four warriors' worth)."})
