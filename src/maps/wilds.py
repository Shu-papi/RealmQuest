"""
wilds.py - the dangerous country outside Oakwood: roaming packs, monster lairs and world events.

    Wilds(world, save, pc, sfx, on_xp)
        update(dt, active)          call every playing frame in the village
        player_swing(...)           sword hits (PlayerCombat.try_attack calls this)
        hostile_near(x, y, r)       anything dangerous close by (stops out-of-combat healing)
        draw_world / lights / draw_hud / draw_minimap

The wilds are tiered like the dungeons, and the monsters ARE the dungeons' monsters (same classes, same
sprites, same config files in config/monsters/):

    tier 1  near Oakwood and the caves       the Goblin Dungeon's mobs: slimes, goblin minions, goblin
                                             shamans (fireballs + barriers), wild boars
    tier 2  across the river, forest's edge  the Berserker Dungeon's: orc warriors, orc shamans (meteors),
                                             treants (roots that hold the hero)
    tier 3  deep in the Deep Forest          the Lich's skeletons (warriors, archers, acolytes, brutes)

Packs roam around a home point and chase the hero when he comes close; once they turn on him they fight
with their dungeon AI (WildMixin hands over to the dungeon class's update()). A wiped-out pack returns
after a while. Skeleton packs run in a SkeletonHost box around their home, like the night raid's.

Lairs keep sending out monsters while the hero is near. Destroy one for XP and gold; it is rebuilt a few
minutes later. World events now and then: a champion roams somewhere for a while, or a merchant caravan
on the Kingsroad is attacked and needs saving.
"""
from __future__ import annotations

import math
import random

import pygame

try:
    from . import combat as _combat
    from .combat import (Enemy, RangedEnemy, OrcEnemy, OrcShaman, TreantEnemy, sword_hits, _try_step, kill_xp,
                         SLIME_SKINS)
    from .night_raid import _Ground, OVERWORLD_XP
except ImportError:
    import combat as _combat
    from combat import (Enemy, RangedEnemy, OrcEnemy, OrcShaman, TreantEnemy, sword_hits, _try_step, kill_xp,
                        SLIME_SKINS)
    from night_raid import _Ground, OVERWORLD_XP

# ---- who lives out here --------------------------------------------------------------------------------
# kind -> (row table name in combat.py, row key, class key, skin, size, tier)
#   the numbers come from that row, so config/monsters/<file>.toml tunes the dungeon AND the wilds
KINDS = {
    "slime":           ("GOBLIN_MOBS", "slime", "enemy", None, 1.0, 1),
    "goblin_minion":   ("GOBLIN_MOBS", "minion", "enemy", "goblin_minion", 1.0, 1),
    "goblin_shaman":   ("GOBLIN_MOBS", "shaman", "shaman", "goblin_shaman", 1.0, 1),
    "wild_boar":       ("GOBLIN_MOBS", "boar", "enemy", "wild_boar", 1.0, 1),
    "goblin_war_boar": (None, "GOBLIN_WAR_BOAR", "enemy", "giant_boar", 1.0, 1),
    "orc_warrior":     ("BERSERKER_MOBS", "orc", "orc", "orc_warrior", 1.0, 2),
    "orc_shaman":      ("BERSERKER_MOBS", "shaman", "orc_shaman", "orc_shaman", 1.0, 2),
    "treant":          ("BERSERKER_MOBS", "treant", "treant", "treant", 1.0, 2),
    "elder_treant":    (None, "ELDER_TREANT", "treant", "treant", "ELDER_SCALE", 2),
    "orc_warlord":     (None, "ORC_WARLORD", "orc", "orc_warlord", "WARLORD_SCALE", 2),
}
# roster -> {kind: weight} (at most one shaman per pack); "skeletons" = the Lich's (monsters.in_game roster)
ROSTERS = {
    "slimes":    {"slime": 1},
    "goblins":   {"goblin_minion": 3, "goblin_shaman": 1, "wild_boar": 1},
    "orcs":      {"orc_warrior": 3, "orc_shaman": 1},
    "treants":   {"treant": 2, "orc_warrior": 1},
    "skeletons": None,
}
ROSTER_TIER = {"slimes": 1, "goblins": 1, "orcs": 2, "treants": 2, "skeletons": 3}
SHAMANS = ("goblin_shaman", "orc_shaman")

# roster, home, count, roam radius
PACKS = [
    ("slimes", (720, 2240), 3, 150), ("slimes", (1640, 2240), 3, 160), ("goblins", (250, 1820), 3, 120),
    ("goblins", (1400, 2230), 3, 130),
    ("orcs", (1650, 3010), 3, 150), ("orcs", (2950, 2640), 4, 160), ("orcs", (3450, 2960), 4, 160),
    ("treants", (3820, 2760), 3, 170), ("treants", (3150, 1320), 3, 150), ("treants", (3300, 1950), 3, 150),
    ("treants", (3560, 1640), 4, 150),
    ("skeletons", (3700, 1120), 4, 140), ("skeletons", (4020, 1420), 4, 140), ("skeletons", (3900, 560), 4, 150),
    ("skeletons", (3480, 480), 3, 150), ("skeletons", (4160, 900), 3, 140), ("skeletons", (4120, 2000), 3, 140),
]
# roster, position, name
LAIRS = [
    ("slimes", (700, 2640), "Slime Den"), ("goblins", (1650, 2100), "Goblin Camp"),
    ("orcs", (3150, 2860), "Orc Warcamp"), ("treants", (3380, 1250), "Treant Grove"),
    ("skeletons", (3960, 1150), "Bone Pit"), ("skeletons", (4170, 1690), "Barrow of the Lich"),
]
LAIR_RESPAWN = 240.0
PACK_RESPAWN = 90.0
LAIR_HP = (300, 200)          # a lair's health = LAIR_HP[0] x tier + LAIR_HP[1]
LEASH = 520                   # px from home before a pack gives up the chase
SKELETON_LEASH = 420          # (skeletons fight inside a box this far round their home)
AGGRO = {1: 200, 2: 240, 3: 240}
# where world events can happen, by tier
EVENT_SPOTS = {1: [(900, 2060), (1800, 2250), (420, 1700)],
               2: [(2500, 2620), (3300, 2700), (3150, 1500), (1500, 2900)],
               3: [(3800, 900), (4000, 1500), (3600, 400)]}
CHAMPIONS = {1: "Gloomgut the Great Slime", 2: "Black Tusk the Warlord", 3: "The Hollow Widow"}
CARAVAN_SPOT = (2075, 2180)
CARAVAN_ROSTER = {1: "goblins", 2: "orcs", 3: "skeletons"}


_FONTS: dict = {}


def _font(size):
    """pygame fonts, made once (not every frame)."""
    f = _FONTS.get(size)
    if f is None:
        f = _FONTS[size] = pygame.font.Font(None, size)
    return f


def reserve(big_circles):
    """Clearings for packs and lairs, so the trees leave them room."""
    for _k, (x, y), _n, r in PACKS:
        big_circles.append((x, y, 70))
    for _k, (x, y), _n in LAIRS:
        big_circles.append((x, y, 120))


# ---- the dungeon's monsters, roaming --------------------------------------------------------------------
class WildMixin:
    """Roams round its home until the hero comes close, then fights with its dungeon class's own
    update() (fireballs, meteors, roots, axe swings ...); gives up past its leash and walks home."""

    def setup_wild(self, kind, home, roam, rng, tier):
        self.kind_name, self.kind, self.tier = kind, "normal", tier
        self.home, self.roam = home, roam
        self.rng = rng
        self.target = None
        self.wait = rng.uniform(0.5, 3.0)
        self.aggro = False
        self.leash = LEASH

    def step(self, dt, player, ground, pc, wilds):
        if self.dead:
            return
        dp = math.hypot(player.x - self.x, player.y - self.y)
        dh = math.hypot(self.x - self.home[0], self.y - self.home[1])
        if self.aggro and (dh > self.leash or pc.dead):
            self.aggro = False                               # give up and go home
            self.target = self.home
        elif not self.aggro and dp < AGGRO[self.tier] and dh < self.leash - 60 and not pc.dead:
            self.aggro = True
        if self.aggro:
            self.update(dt, player, ground, pc)              # its dungeon AI
            return
        self.attack_cd = max(0.0, self.attack_cd - dt)
        self.hit_flash = max(0.0, self.hit_flash - dt)
        if self.cc_tick(dt):
            return
        self.face_x = 0
        if self.hp < self.max_hp and dh < 40:
            self.hp = min(self.max_hp, self.hp + self.max_hp * 0.05 * dt)     # licks its wounds at home
        if self.target is None:
            self.wait -= dt
            if self.wait <= 0:
                a, r = self.rng.random() * math.tau, self.rng.random() * self.roam
                self.target = (self.home[0] + math.cos(a) * r, self.home[1] + math.sin(a) * r * 0.7)
        else:
            tx, ty = self.target
            if math.hypot(tx - self.x, ty - self.y) < 8:
                self.target, self.wait = None, self.rng.uniform(1.5, 4.0)
            elif not self.walk_to(tx, ty, dt, ground, 0.45):
                self.target, self.wait = None, self.rng.uniform(0.5, 2.0)

    def walk_to(self, tx, ty, dt, ground, k=1.0):
        dx, dy = tx - self.x, ty - self.y
        d = math.hypot(dx, dy) or 1.0
        if abs(dx) > 2:
            self.face_x = 1 if dx > 0 else -1
        # straight on, else slide along the obstacle, else turn 45 / 90 degrees past it
        return _try_step(self, dx / d, dy / d, self.speed * self.speed_k * k * dt, ground) is not None

    def hit_cart(self):
        return self.damage


class WildEnemy(WildMixin, Enemy):
    pass


class WildShaman(WildMixin, RangedEnemy):
    pass


class WildOrc(WildMixin, OrcEnemy):
    pass


class WildOrcShaman(WildMixin, OrcShaman):
    pass


class WildTreant(WildMixin, TreantEnemy):
    pass


CLASSES = {"enemy": WildEnemy, "shaman": WildShaman, "orc": WildOrc, "orc_shaman": WildOrcShaman,
           "treant": WildTreant}
Mob = WildMixin                 # (old name: anything that roams the wilds)


def _row(kind):
    table, key, *_ = KINDS[kind]
    src = vars(_combat) if table is None else getattr(_combat, table)
    return src, key


def make_wild(kind, x, y, home, roam, rng, wilds, allies=None):
    """A roaming copy of a dungeon monster (numbers from its config row, its real sprite and AI)."""
    table, key, cls_key, skin, size, tier = KINDS[kind]
    src, key = _row(kind)
    name, hp, speed, dmg, color, radius = src[key][:6]
    extra = {}
    if cls_key == "shaman":
        extra = dict(bolts=wilds.bolts, allies=allies or (lambda: []))
    elif cls_key in ("orc_shaman", "treant"):
        extra = dict(hazards=wilds.hazards)
    elif cls_key == "orc" and kind == "orc_warlord":
        extra = dict(reach="WARLORD_REACH", swing_sound="king_swing")
    m = CLASSES[cls_key](x, y, name, hp, speed, dmg, color, radius, **extra)
    m.setup_wild(kind, home, roam, rng, tier)
    m.cfg = (src, key)                               # refresh_config(): the config file changed
    m.skin = skin or rng.choice(SLIME_SKINS)
    if isinstance(size, str):
        size = getattr(_combat, size, 1.0)
    m.skin_scale = size
    if table is None:                                # elites and mini-bosses: like in the dungeon
        m.kind = "elite"
        m.kind_name = kind
        m.cc_immune = kind == "orc_warlord"
    return m


def _wild_skeleton_class():
    """WildSkeleton, built on monsters.in_game.SkeletonEnemy (imported late: combat.py puts src/ on the path)."""
    global WildSkeleton
    if WildSkeleton is not None:
        return WildSkeleton
    from monsters.in_game import SkeletonEnemy

    class _WildSkeleton(SkeletonEnemy):
        """A skeleton of the Deep Forest: wanders round its home, then fights the hero with its own AI."""

        def __init__(self, host, monster, home=None, roam=140, rng=None, **kw):
            super().__init__(host, monster, **kw)
            self.home = home or (host.ox + host.w / 2, host.oy + host.h / 2)
            self.roam = roam
            self.rng = rng or host.rng
            self.tier = 3
            self.aggro = False
            self.wander = None
            self.wait = self.rng.uniform(0.5, 3.0)
            self.leash = SKELETON_LEASH

        def step(self, dt, player, ground, pc, wilds):
            if self.dead:
                return
            host = self.host
            host.hero_from(player, pc, ground)               # (also where a hit knocks it back from)
            dp = math.hypot(player.x - self.x, player.y - self.y)
            dh = math.hypot(self.x - self.home[0], self.y - self.home[1])
            if self.aggro and (dh > self.leash or pc.dead):
                self.aggro = False
                calm_down(self.monster)
            elif not self.aggro and dp < AGGRO[3] and dh < self.leash - 60 and not pc.dead:
                self.aggro = True
            if self.aggro:
                self.run(dt, host.hero)
                return
            if self.wander is None:
                self.wait -= dt
                if self.wait <= 0:
                    a, r = self.rng.random() * math.tau, self.rng.random() * self.roam
                    self.wander = (self.home[0] + math.cos(a) * r, self.home[1] + math.sin(a) * r * 0.7)
                tx, ty = self.x, self.y
            else:
                tx, ty = self.wander
                if math.hypot(tx - self.x, ty - self.y) < 10:
                    self.wander, self.wait = None, self.rng.uniform(1.5, 4.0)
            self._stroll(dt, tx, ty, 0.45)

        def walk_to(self, tx, ty, dt, ground, k=1.0):
            self._stroll(dt, tx, ty, k)
            return True

        def _stroll(self, dt, tx, ty, k):
            m = self.monster
            dx, dy = tx - self.x, ty - self.y

            def stroll(dt_, _player, _bounds):
                if math.hypot(dx, dy) > 4:
                    m.face(m.x + dx)
                    m.move(dx, dy, m.speed * k, dt_)

            m.think = stroll                                 # (instance attribute: shadows its fighting AI)
            try:
                self.run(dt, self.host.hero)
            finally:
                del m.think

        def hit_cart(self):
            return max(1, round(self.monster.damage * self.host.damage_k))

    _WildSkeleton.__name__ = _WildSkeleton.__qualname__ = "WildSkeleton"
    WildSkeleton = _WildSkeleton
    return WildSkeleton


WildSkeleton = None


def calm_down(m):
    """A skeleton that stops fighting drops whatever attack it was winding up (or it would freeze in
    the pose and strike the moment it fights again)."""
    if m.state not in ("spawn", "dying", "dead", "stagger") and m.state != m.START_STATE:
        m.set_state(m.START_STATE)
    m.cooldown = max(getattr(m, "cooldown", 0.0), 0.4)


def is_wild(m):
    return isinstance(m, WildMixin) or (WildSkeleton is not None and isinstance(m, WildSkeleton))


class Group:
    """Monsters of one roster around one home: a pack, a lair's brood or an event's raiders.
    Skeletons fight inside their own SkeletonHost box."""

    def __init__(self, roster, home, roam, rng, wilds):
        self.roster, self.home, self.roam, self.rng, self.wilds = roster, home, roam, rng, wilds
        self.tier = ROSTER_TIER[roster]
        self.mobs: list = []
        self.host = None
        if roster == "skeletons":
            from monsters.in_game import SkeletonHost
            r = SKELETON_LEASH + 60
            self.host = SkeletonHost(home[0] - r, home[1] - r, 2 * r, 2 * r, "dungeon", ground=wilds.ground,
                                     seed=rng.random())
            self.host.raise_as = (_wild_skeleton_class(), {"home": home, "roam": roam, "rng": rng})

    def kinds(self, n):
        weights = ROSTERS[self.roster]
        out = []
        for _ in range(n):
            pool = {k: w for k, w in weights.items()
                    if not (k in SHAMANS and any(o in SHAMANS for o in out + [getattr(m, "kind_name", "")
                                                                               for m in self.mobs]))}
            out.append(self.rng.choices(list(pool), list(pool.values()))[0])
        return out

    def add(self, x, y, kind=None):
        if self.host is not None:
            from monsters.in_game import skeleton_roster
            name = kind or skeleton_roster(self.rng, 1)[0]
            m = self.host.add(name, x, y, proxy=_wild_skeleton_class(), home=self.home, roam=self.roam, rng=self.rng)
        else:
            kind = kind or self.kinds(1)[0]
            m = make_wild(kind, x, y, self.home, self.roam, self.rng, self.wilds, allies=lambda: self.mobs)
        self.mobs.append(m)
        return m

    def step(self, dt, player, ground, pc, near=True):
        for m in self.mobs:
            if near or m.aggro:
                m.step(dt, player, ground, pc, self.wilds)
                self.wilds._hear(m)
        if self.host is not None:
            self.host.step(dt)
            self.mobs.extend(self.host.new_members())

    def reap(self, mult=1, special=None):
        """Pay XP for the dead and forget them."""
        for m in self.mobs:
            if m.dead and not getattr(m, "counted", False):
                m.counted = True
                if not getattr(m, "no_reward", False):
                    self.wilds._kill(m, 2 if m is special else mult)
        self.mobs = [m for m in self.mobs if not m.dead]

    def alive(self):
        return [m for m in self.mobs if not m.dead]

    def clear(self):
        self.mobs = []
        if self.host is not None:
            self.host.clear()


class Pack(Group):
    def __init__(self, roster, home, count, roam, rng, wilds):
        super().__init__(roster, home, roam, rng, wilds)
        self.count = count
        self.timer = 0.0
        self.spawn()

    def spawn(self):
        hx, hy = self.home
        self.clear()
        for _ in range(self.count):
            self.add(hx + self.rng.uniform(-50, 50), hy + self.rng.uniform(-30, 30))
        self.timer = 0.0


class Lair:
    def __init__(self, roster, pos, name, rng, wilds):
        self.roster, (self.x, self.y), self.name = roster, pos, name
        self.tier = ROSTER_TIER[roster]
        self.max_hp = LAIR_HP[0] * self.tier + LAIR_HP[1]
        self.hp = self.max_hp
        self.radius = 34
        self.alive = True
        self.timer = 0.0
        self.spawn_cd = 3.0
        self.brood = Group(roster, (self.x, self.y + 40), 120, rng, wilds)
        self.flash = 0.0
        self.img = self._make(roster)

    @property
    def spawned(self):
        return self.brood.mobs

    @property
    def dead(self):
        return not self.alive

    @staticmethod
    def _make(roster):
        s = pygame.Surface((96, 84), pygame.SRCALPHA)
        hide = {"slimes": (96, 150, 96), "goblins": (100, 120, 60), "orcs": (140, 70, 52), "treants": (92, 74, 48),
                "skeletons": (70, 60, 86)}[roster]
        pygame.draw.ellipse(s, (0, 0, 0, 90), (6, 66, 84, 16))
        pygame.draw.polygon(s, (60, 40, 26), [(10, 74), (48, 8), (86, 74)])            # poles
        pygame.draw.polygon(s, hide, [(14, 72), (48, 14), (82, 72)])                    # hide tent
        pygame.draw.polygon(s, tuple(int(c * 0.7) for c in hide), [(48, 14), (82, 72), (60, 72)])
        pygame.draw.polygon(s, (16, 10, 12), [(38, 72), (48, 46), (58, 72)])            # doorway
        for x in (44, 48, 52):
            pygame.draw.line(s, (90, 64, 40), (48, 14), (x, 2), 2)
        for x, y in ((18, 72), (78, 70)):                                               # skulls
            pygame.draw.circle(s, (230, 224, 206), (x, y - 4), 5)
            s.fill((20, 14, 16), (x - 3, y - 5, 2, 2))
            s.fill((20, 14, 16), (x + 1, y - 5, 2, 2))
        return s

    def take_damage(self, n):
        if self.alive:
            self.hp = max(0, self.hp - n)
            self.flash = 0.12


class Wilds:
    def __init__(self, world, save, pc, sfx, on_xp=None):
        self.world, self.save, self.pc, self.sfx = world, save, pc, sfx
        self.on_xp = on_xp or (lambda *a: None)
        self.ground = _Ground(world)
        self.rng = random.Random()
        self.bolts: list = []             # goblin shamans' fireballs (combat.EnemyBolt)
        self.hazards: list = []           # orc shamans' meteors, treants' roots (combat.MeteorStrike / RootSnare)
        self.packs = [Pack(k, h, n, r, self.rng, self) for k, h, n, r in PACKS]
        self.lairs = [Lair(k, p, n, self.rng, self) for k, p, n in LAIRS]
        self.floaters: list = []          # [x, y, text, life, colour]
        self.event = None                 # dict while a world event is running
        self.event_cd = 75.0
        self.result = None
        world.wilds = self

    # ---- queries ---------------------------------------------------------------
    def groups(self):
        yield from self.packs
        for lr in self.lairs:
            yield lr.brood
        if self.event:
            yield self.event["group"]

    def enemies(self):
        for g in self.groups():
            yield from (m for m in g.mobs if not m.dead)

    def hostile_near(self, x, y, r):
        return any(math.hypot(m.x - x, m.y - y) < r and getattr(m, "aggro", True) for m in self.enemies())

    def _kill(self, m, mult=1):
        xp = max(1, int(kill_xp(m.max_hp) * getattr(m, "tier", 1) * mult * OVERWORLD_XP))
        self.on_xp(xp, m.x, m.y)

    def refresh_config(self):
        """The config files changed: every wild monster reads its numbers again."""
        for g in self.groups():
            for m in g.mobs:
                fn = getattr(m, "refresh_config", None)
                if fn is not None:
                    fn()
            if g.host is not None:
                g.host.refresh_config()
        for lr in self.lairs:
            lr.max_hp = LAIR_HP[0] * lr.tier + LAIR_HP[1]
            lr.hp = min(lr.hp, lr.max_hp)

    # ---- update -------------------------------------------------------------------
    def update(self, dt, active):
        for f in self.floaters:
            f[1] -= 30 * dt
            f[3] -= dt
        self.floaters = [f for f in self.floaters if f[3] > 0]
        if self.result:
            t, c, left = self.result
            self.result = (t, c, left - dt) if left > dt else None
        if not active:
            return
        player, pc, ground = self.world.player, self.pc, self.ground
        px, py = player.x, player.y
        # packs
        for pack in self.packs:
            near = abs(pack.home[0] - px) < 1500 and abs(pack.home[1] - py) < 1100
            pack.step(dt, player, ground, pc, near)
            pack.reap()
            if not pack.alive() and (pack.host is None or pack.host.done):
                pack.timer += dt
                if pack.timer > PACK_RESPAWN and math.hypot(pack.home[0] - px, pack.home[1] - py) > 700:
                    pack.spawn()
        # lairs
        for lr in self.lairs:
            lr.flash = max(0.0, lr.flash - dt)
            if not lr.alive:
                lr.timer += dt
                if lr.timer > LAIR_RESPAWN and math.hypot(lr.x - px, lr.y - py) > 800:
                    lr.alive, lr.hp, lr.timer = True, lr.max_hp, 0.0
            elif math.hypot(lr.x - px, lr.y - py) < 420:
                lr.spawn_cd -= dt
                if lr.spawn_cd <= 0 and len(lr.brood.alive()) < 4:
                    lr.spawn_cd = 7.0
                    m = lr.brood.add(lr.x + self.rng.uniform(-30, 30), lr.y + 40)
                    m.aggro = True
            lr.brood.step(dt, player, ground, pc)
            lr.brood.reap()
            if lr.hp <= 0 and lr.alive:
                lr.alive = False
                lr.timer = 0.0
                gold = 25 * lr.tier
                self.save.gold += gold
                self.on_xp(int(50 * lr.tier * OVERWORLD_XP), lr.x, lr.y - 30, "reward")
                self.floaters.append([lr.x, lr.y - 80, "+%d gold" % gold, 1.6, (255, 226, 130)])
                self.world.toast("%s destroyed!  +%d gold" % (lr.name, gold), (255, 214, 120))
                self.sfx.play("clear")
        self._update_event(dt, player, pc, ground)
        self._update_spells(dt, player, pc, ground)

    def _update_spells(self, dt, player, pc, ground):
        """The shamans' fireballs and the meteors / roots on the ground (like Encounters.update)."""
        for bolt in self.bolts:
            bolt.update(dt, player, ground, pc)
        self.bolts[:] = [b for b in self.bolts if not b.dead]          # (in place: shamans hold this list)
        for spell in self.hazards:
            spell.update(dt, player, ground, pc)
            for name in spell.pop_sounds():
                self.sfx.play(name)
        self.hazards[:] = [s for s in self.hazards if not s.dead]

    def _hear(self, m):
        for name in m.pop_sounds():
            self.sfx.play(name)

    # ---- world events ---------------------------------------------------------------------
    def _tier_for_player(self):
        lv = self.save.level
        return 1 if lv < 5 else (2 if lv < 9 else 3)

    def _start_event(self):
        tier = self._tier_for_player()
        if self.rng.random() < 0.55:
            x, y = self.rng.choice(EVENT_SPOTS[tier])
            name = CHAMPIONS[tier]
            group = Group(("slimes", "orcs", "skeletons")[tier - 1], (x, y), 140, self.rng, self)
            if tier == 1:                                  # a great slime: three slimes' health, bigger
                m = group.add(x, y, "slime")
                m.cfg_hp_k = 3.0
                m.max_hp = m.hp = m.max_hp * 3
                m.skin_scale = 1.6
                m.cfg_radius_k = 20 / max(1, m.radius)        # (refresh_config keeps the big hit circle)
                m.radius = 20
            elif tier == 2:                                # an Orc Warlord
                m = group.add(x, y, "orc_warlord")
            else:                                          # a skeleton warden
                from monsters.in_game import make_warden
                m = make_warden(group.host, x, y, name, "cursed", proxy=_wild_skeleton_class(),
                                home=(x, y), roam=140, rng=self.rng)
                group.mobs.append(m)
            m.name = name
            self.event = dict(kind="champion", x=x, y=y, group=group, champion=m, time=150.0, tier=tier,
                              title="A champion prowls: %s" % name)
            self.world.toast("Merlin: I sense a champion out there... %s!" % name, (255, 200, 140))
        else:
            x, y = CARAVAN_SPOT
            group = Group(CARAVAN_ROSTER[tier], (x, y), 60, self.rng, self)
            for i in range(4):
                a = i * math.tau / 4
                m = group.add(x + math.cos(a) * 120, y + math.sin(a) * 70)
                m.aggro = False
                m.leash = 400
            self.event = dict(kind="caravan", x=x, y=y, group=group, cart_hp=60, time=150.0, tier=tier,
                              title="A merchant caravan is under attack on the Kingsroad!")
            self.world.toast("Merlin: A caravan on the Kingsroad, under attack! Hurry!", (255, 200, 140))
        self.sfx.play("roar")

    def _end_event(self, won, text):
        ev, self.event = self.event, None
        ev["group"].clear()
        self.event_cd = self.rng.uniform(110, 170)
        col = (150, 230, 150) if won else (255, 170, 150)
        self.result = (text, col, 4.0)
        if won:
            tier = ev["tier"]
            gold = (40 if ev["kind"] == "champion" else 50) * tier
            self.save.gold += gold
            self.on_xp(int((60 if ev["kind"] == "champion" else 30) * tier * OVERWORLD_XP), ev["x"], ev["y"] - 40,
                       "reward")
            if ev["kind"] == "caravan":
                self.pc.add_potion()
                self.save.pull_from(self.pc)
            self.sfx.play("victory")

    def _update_event(self, dt, player, pc, ground):
        night = getattr(self.world, "night", None)
        if self.event is None:
            if night is None or not night.active:
                self.event_cd -= dt
                if self.event_cd <= 0:
                    self._start_event()
            return
        ev = self.event
        group = ev["group"]
        ev["time"] -= dt
        caravan = ev["kind"] == "caravan"
        for m in group.mobs:
            if caravan and not m.aggro and not m.dead:
                # raiders claw at the cart unless the hero gets in the way
                if math.hypot(player.x - m.x, player.y - m.y) < 200:
                    m.aggro = True
                else:
                    d = math.hypot(ev["x"] - m.x, ev["y"] - m.y)
                    if d > 46:
                        m.walk_to(ev["x"], ev["y"], dt, ground, 0.8)
                    else:
                        m.claw_t = getattr(m, "claw_t", 0.0) - dt
                        if m.claw_t <= 0:
                            m.claw_t = 1.2
                            ev["cart_hp"] -= m.hit_cart()
                    continue
            m.step(dt, player, ground, pc, self)
            self._hear(m)
        if group.host is not None:
            group.host.step(dt)
            group.mobs.extend(group.host.new_members())
        group.reap(special=ev.get("champion"))
        if caravan and ev["cart_hp"] <= 0:
            self._end_event(False, "The caravan was lost...")
        elif not group.mobs:
            self._end_event(True, "Champion slain!" if not caravan else "Caravan saved!  The merchant thanks you.")
        elif ev["time"] <= 0:
            self._end_event(False, "The champion slipped away." if not caravan else "The caravan was lost...")

    def player_swing(self, player, dx, dy, dmg):
        hit = False
        for m in list(self.enemies()) + [lr for lr in self.lairs if lr.alive]:
            if sword_hits(player.x, player.y, dx, dy, m.x, m.y, m.radius):
                host = getattr(m, "host", None)
                if host is not None:
                    host.hero_from(player, self.pc, self.ground)   # (knocked back away from the hero)
                m.take_damage(dmg)
                if is_wild(m):
                    m.aggro = True
                hit = True
        return hit                                # (the Game plays the hit sound once per swing)

    def calm(self):
        """After the hero falls: everything goes home, and the spells in the air fizzle."""
        for m in self.enemies():
            if is_wild(m):
                m.aggro = False
                if hasattr(m, "monster"):
                    calm_down(m.monster)
                if hasattr(m, "home") and isinstance(m, WildMixin):
                    m.target = m.home
        self.bolts.clear()
        self.hazards.clear()

    # ---- drawing ------------------------------------------------------------------------
    def lights(self, t):
        out = []
        for lr in self.lairs:
            if lr.alive:
                out.append((lr.x, lr.y - 20, 110, (150, 60, 40)))
        if self.event:
            out.append((int(self.event["x"]), int(self.event["y"]) - 20, 120, (190, 150, 60)))
        return out

    def draw_world(self, scr, cx, cy, t):
        W, H = scr.get_size()
        view = pygame.Rect(cx - 80, cy - 80, W + 160, H + 160)
        for lr in self.lairs:
            if not view.collidepoint(lr.x, lr.y):
                continue
            X, Y = int(lr.x - cx), int(lr.y - cy)
            if lr.alive:
                img = lr.img
                if lr.flash > 0:
                    img = img.copy()
                    img.fill((90, 60, 60), special_flags=pygame.BLEND_RGB_ADD)
                scr.blit(img, (X - 48, Y - 74))
                if lr.hp < lr.max_hp:
                    pygame.draw.rect(scr, (0, 0, 0), (X - 31, Y - 86, 62, 7))
                    pygame.draw.rect(scr, (220, 90, 60), (X - 30, Y - 85, int(60 * lr.hp / lr.max_hp), 5))
            else:                                  # smouldering ruin
                pygame.draw.ellipse(scr, (40, 34, 30), (X - 34, Y - 10, 68, 22))
                for i in range(3):
                    k = (t * 0.6 + i / 3) % 1.0
                    pygame.draw.circle(scr, (90, 90, 90), (X - 10 + i * 10, int(Y - 10 - k * 40)), 3 + int(k * 4))
        ev = self.event
        if ev and ev["kind"] == "caravan" and view.collidepoint(ev["x"], ev["y"]):
            X, Y = int(ev["x"] - cx), int(ev["y"] - cy)
            pygame.draw.ellipse(scr, (0, 0, 0), (X - 34, Y - 6, 68, 14))
            pygame.draw.rect(scr, (120, 84, 48), (X - 30, Y - 34, 60, 26))
            pygame.draw.rect(scr, (220, 210, 186), (X - 26, Y - 52, 52, 22), border_top_left_radius=12,
                             border_top_right_radius=12)
            for wx in (-20, 20):
                pygame.draw.circle(scr, (60, 40, 24), (X + wx, Y - 6), 9)
                pygame.draw.circle(scr, (150, 110, 70), (X + wx, Y - 6), 6)
            pygame.draw.rect(scr, (0, 0, 0), (X - 31, Y - 64, 62, 7))
            pygame.draw.rect(scr, (230, 200, 90), (X - 30, Y - 63, int(60 * max(0, ev["cart_hp"]) / 60), 5))
        for spell in self.hazards:                 # meteor and root warnings on the ground
            spell.draw(scr, cx, cy, t)
        for g in self.groups():                    # skeletons (and the ones still falling apart)
            if g.host is not None and view.colliderect(pygame.Rect(g.host.ox, g.host.oy, g.host.w, g.host.h)):
                g.host.draw(scr, cx, cy)
        mobs = [m for m in self.enemies() if view.collidepoint(m.x, m.y)]
        for m in sorted(mobs, key=lambda m: m.y):
            m.draw(scr, cx, cy)
            if ev and m is ev.get("champion"):
                img = _font(22).render(m.name, True, (255, 210, 140))
                scr.blit(img, (int(m.x - cx) - img.get_width() // 2, int(m.y - cy) - 70))
        for bolt in self.bolts:
            bolt.draw(scr, cx, cy, t)
        if self.floaters:
            font = _font(26)
            for x, y, text, life, col in self.floaters:
                img = font.render(text, True, col)
                img.set_alpha(int(255 * min(1.0, life / 0.4)))
                scr.blit(img, (int(x - cx) - img.get_width() // 2, int(y - cy)))

    def draw_hud(self, scr, font, big_font):
        W, H = scr.get_size()
        y0 = H - 118
        ev = self.event
        if ev:
            mins, secs = divmod(max(0, int(ev["time"])), 60)
            txt = "EVENT:  %s   %d:%02d" % (ev["title"], mins, secs)
            img = font.render(txt, True, (255, 220, 160))
            w = img.get_width() + 30
            panel = pygame.Surface((w, 30), pygame.SRCALPHA)
            pygame.draw.rect(panel, (24, 16, 8, 210), panel.get_rect(), border_radius=8)
            pygame.draw.rect(panel, (220, 170, 90, 255), panel.get_rect(), 2, border_radius=8)
            scr.blit(panel, (W // 2 - w // 2, y0))
            scr.blit(img, (W // 2 - img.get_width() // 2, y0 + 6))
        if self.result:
            text, col, left = self.result
            img = big_font.render(text, True, col)
            img.set_alpha(int(255 * min(1.0, left / 0.6)))
            scr.blit(img, (W // 2 - img.get_width() // 2, y0 - 40))

    def draw_minimap(self, scr, ox, oy, k, t):
        for lr in self.lairs:
            if lr.alive:
                p = (int(ox + lr.x * k), int(oy + lr.y * k))
                pygame.draw.rect(scr, (10, 10, 14), (p[0] - 3, p[1] - 3, 7, 7))
                pygame.draw.rect(scr, (220, 80, 60), (p[0] - 2, p[1] - 2, 5, 5))
        if self.event:
            p = (int(ox + self.event["x"] * k), int(oy + self.event["y"] * k))
            r = 5 + int(t * 4) % 2
            pts = [(p[0], p[1] - r), (p[0] + r, p[1]), (p[0], p[1] + r), (p[0] - r, p[1])]
            pygame.draw.polygon(scr, (10, 10, 14), [(x, y + 1) for x, y in pts])
            pygame.draw.polygon(scr, (255, 190, 90), pts)
