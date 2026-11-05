"""
combat.py - the hero's combat (class, bars, dash, basic attack) and the dungeon monsters.

The Goblin Dungeon family uses real sprites (Goblin Minion, Goblin Shaman, slimes, Wild Boar,
Goblin War Boar, General Grub, and Valdur the Goblin King from src/bosses/goblin_king); the other dungeons still use
plain shapes until their art arrives. Teammates plug in monsters/bosses through `Encounters`.

The map file imports from here:
    Encounters, PlayerCombat, DASH_SPEED, sprite

HOOKS THE MAP CALLS ON `Encounters` (keep these names):
    locked (property)        -> True while the player is confined to a room
    exit_open()              -> True when the exit portal can be used
    update(dt, player, pc)   -> per-frame logic
    draw(surf, cx, cy, t, player, pc)
    draw_hud(surf, cx, cy, pc, t)
    use_potion(player, pc)
    retry_room()             -> returns the room index that was reset (or None)
    player_swing(player, dx, dy, dmg)   -> called when the player swings the sword
    sound_queue (list)       -> sound names the Game should play
    dialog_request / outro_request      -> set to a boss kind to open a dialog
    state (list per room), boss_room, boss_floor, boss_kind   -> used by the minimap

USEFUL MAP DATA FOR TEAMMATES:
    dungeon.rooms          list of pygame.Rect (in TILES)
    dungeon.can_stand(x,y) pixel-position walkability check
    dungeon.lock_rect      set to a pixel pygame.Rect to confine the player (None to free)
    dungeon.floor_name     e.g. "1-1", "1-3" (boss floors end in "-3")
    dungeon.room_roles     per room: "start", "combat", "guard", "seal", "vault", "miniboss",
                           "shrine", "trap", "stairs", "antechamber", "boss" (see dungeon_gen.py)
    free(d, x, y, hw, hh)  helper below to test if a monster hitbox fits
"""
from __future__ import annotations

import math
import os
import random
import sys

import pygame

# src/ on the import path, so the map can use the skills, monsters and bosses packages
_SRC = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

from skills import classes as hero_classes          # noqa: E402
from skills.skills import Pools, SkillCaster, spawn_basic   # noqa: E402

TILE = 24
MAP_W, MAP_H = 288, 162
FLOOR, LIQUID, PATH = 1, 2, 5
WALK = (FLOOR, PATH)
OPEN = (FLOOR, LIQUID, PATH)

# ---- player tuning --------------------------------------------------------
PLAYER_MAX_HP = 40
SWORD_DMG = 2
SWORD_REACH = 90
SWORD_ARC = 0.34            # cos of half the swing cone: 0.34 = about 140 degrees in front of the hero
CONTACT_REACH = 14          # px past its own radius a monster's bite / punch reaches (about the hero's half-width)
SWORD_COOLDOWN = 0.55
SWING_TIME = 0.16
HEAL_ON_CLEAR = 8
POTION_HEAL = 12
POTION_MAX = 6
POTION_START = 2
POTION_DROP_CHANCE = 0.3

# dash (Shift)
DASH_TIME = 0.18
DASH_SPEED = 520.0
DASH_COOLDOWN = 0.9
DASH_IFRAMES = 0.3
DASH_EFFECT = True          # afterimages + speed lines while dashing (src/maps/dash_fx.py)
XP_PER_HEALTH = 0.04        # kill XP = a monster's max health x this (x its tier, x2 elite, x3 boss)
BONUS_SCALE = 5             # every flat attack bonus (sword upgrades, levels, gear, Power, class) x this
POTION_HEAL_PERCENT = 20    # a potion also heals this % of max health
HEAL_ON_CLEAR_PERCENT = 10  # clearing a room also heals this % of max health


def kill_xp(max_hp):
    """XP for killing a monster with this much max health (before the tier / elite multipliers)."""
    return max_hp * XP_PER_HEALTH


# ---- small helpers --------------------------------------------------------
def blank(w, h):
    return pygame.Surface((w, h), pygame.SRCALPHA)


def free(d, x, y, hw, hh):
    """True if a monster hitbox (half width hw, half height hh) fits at pixel (x, y)."""
    for ox, oy in ((-hw, -hh), (hw, -hh), (-hw, 2), (hw, 2)):
        tx, ty = int((x + ox) // TILE), int((y + oy) // TILE)
        if not (0 <= tx < MAP_W and 0 <= ty < MAP_H):
            return False
        i = ty * MAP_W + tx
        if d.tiles[i] not in WALK or d.solid[i]:
            return False
    return True


# ---- monster movement: slide along walls, then find a way round -------------------------------
STUCK_TIME = 0.35           # s of no progress before a monster starts following a path
PATH_TIME = 1.0             # s it keeps following the path once it does
FLOW_WINDOW = 32            # tiles around the target the path search covers (outside a locked room)
FLOW_REFRESH = 1.5          # s a path field is kept for one target tile
_TURNS = (0.0, math.radians(45), -math.radians(45), math.radians(90), -math.radians(90))
_NEIGHBOURS = ((1, 0), (-1, 0), (0, 1), (0, -1), (1, 1), (1, -1), (-1, 1), (-1, -1))


def _walkable(d, i):
    return d.tiles[i] in WALK and not d.solid[i]


def flow_field(d, tx, ty):
    """{tile index: steps to the target tile (tx, ty)} over the floor around the target.
    Cached on the dungeon per target tile and room lock; None if the map has no tile grid."""
    if not hasattr(d, "tiles") or not hasattr(d, "solid"):
        return None
    lr = getattr(d, "lock_rect", None)
    if lr is not None:
        x0, y0 = lr.left // TILE, lr.top // TILE
        x1, y1 = (lr.right - 1) // TILE, (lr.bottom - 1) // TILE
    else:
        x0, y0 = tx - FLOW_WINDOW, ty - FLOW_WINDOW
        x1, y1 = tx + FLOW_WINDOW, ty + FLOW_WINDOW
    x0, y0 = max(0, x0), max(0, y0)
    x1, y1 = min(MAP_W - 1, x1), min(MAP_H - 1, y1)
    key = (tx, ty, x0, y0, x1, y1)
    now = pygame.time.get_ticks() / 1000.0 if pygame.get_init() else 0.0
    cached = getattr(d, "_flow_cache", None)
    if cached is not None and cached[0] == key and now - cached[1] < FLOW_REFRESH:
        return cached[2]
    dist = {}
    if x0 <= tx <= x1 and y0 <= ty <= y1:
        start = ty * MAP_W + tx
        dist[start] = 0
        frontier = [start]
        while frontier:
            nxt = []
            for i in frontier:
                cx, cy = i % MAP_W, i // MAP_W
                for ox, oy in _NEIGHBOURS[:4]:
                    nx, ny = cx + ox, cy + oy
                    if x0 <= nx <= x1 and y0 <= ny <= y1:
                        j = ny * MAP_W + nx
                        if j not in dist and _walkable(d, j):
                            dist[j] = dist[i] + 1
                            nxt.append(j)
            frontier = nxt
    try:
        d._flow_cache = (key, now, dist)
    except AttributeError:
        pass
    return dist


def path_step(d, x, y, tx, ty):
    """The centre of the next tile on the way from pixel (x, y) to pixel (tx, ty), or None."""
    field = flow_field(d, int(tx // TILE), int(ty // TILE))
    if not field:
        return None
    cx, cy = int(x // TILE), int(y // TILE)
    best, best_d = None, field.get(cy * MAP_W + cx, 1 << 30)
    for ox, oy in _NEIGHBOURS:
        nx, ny = cx + ox, cy + oy
        if not (0 <= nx < MAP_W and 0 <= ny < MAP_H):
            continue
        if ox and oy:            # no cutting a corner past a wall
            if (cy * MAP_W + nx) not in field or (ny * MAP_W + cx) not in field:
                continue
        dd = field.get(ny * MAP_W + nx)
        if dd is not None and dd < best_d:
            best, best_d = (nx, ny), dd
    if best is None:
        return None
    return best[0] * TILE + TILE / 2, best[1] * TILE + TILE / 2


def _try_step(e, ux, uy, step, dungeon):
    """Try the step (ux, uy) * step, then slides along each axis, then turned 45 / 90 degrees.
    Moves the monster and returns the (dx, dy) it moved, or None if every way is blocked."""
    for turn in _TURNS:
        if turn:
            c, s = math.cos(turn), math.sin(turn)
            vx, vy = ux * c - uy * s, ux * s + uy * c
        else:
            vx, vy = ux, uy
        nx, ny = e.x + vx * step, e.y + vy * step
        if dungeon.can_stand(nx, ny):
            e.x, e.y = nx, ny
            return vx * step, vy * step
        if not turn:                                   # slide along the wall
            for sx, sy in ((math.copysign(1.0, ux), 0.0), (0.0, math.copysign(1.0, uy))):
                k = abs(ux) if sx else abs(uy)
                if k < 0.15:
                    continue
                nx, ny = e.x + sx * step * k, e.y + sy * step * k
                if dungeon.can_stand(nx, ny):
                    e.x, e.y = nx, ny
                    return sx * step * k, sy * step * k
    return None


def move_enemy(e, tx, ty, dt, dungeon, away=False, speed=None):
    """Walk monster `e` toward pixel (tx, ty) (or away from it) without getting stuck:
    it slides along walls and props, turns past corners, and when it still makes no
    progress for STUCK_TIME it follows a path round the obstacle for PATH_TIME.
    Returns True if it moved."""
    sp = (e.speed if speed is None else speed) * getattr(e, "speed_k", 1.0)
    step = sp * dt
    if step <= 0:
        return False
    dx, dy = tx - e.x, ty - e.y
    dist = math.hypot(dx, dy) or 1.0
    ux, uy = dx / dist, dy / dist
    if away:
        ux, uy = -ux, -uy
    path_t = getattr(e, "path_t", 0.0)
    if path_t > 0 and not away:
        e.path_t = path_t - dt
        nxt = path_step(dungeon, e.x, e.y, tx, ty)
        if nxt is not None:
            px, py = nxt[0] - e.x, nxt[1] - e.y
            pl = math.hypot(px, py)
            if pl > 1e-3:
                ux, uy = px / pl, py / pl
    moved = _try_step(e, ux, uy, step, dungeon)
    # progress = how much closer (or further, when backing off) it got
    if moved is None:
        gain = 0.0
    else:
        gain = (moved[0] * dx + moved[1] * dy) / dist * (-1 if away else 1)
    if gain < step * 0.3:
        e.stuck_t = getattr(e, "stuck_t", 0.0) + dt
        if e.stuck_t >= STUCK_TIME and not away:
            e.stuck_t = 0.0
            e.path_t = PATH_TIME
    else:
        e.stuck_t = 0.0
    return moved is not None


def sword_hits(px, py, dx, dy, ex, ey, radius):
    """True if a sword swing from the hero at (px, py) aimed along the unit vector (dx, dy) hits a
    monster at (ex, ey) with hit circle `radius`: it must be within SWORD_REACH + radius and inside
    the SWORD_ARC cone in front of the hero. A monster touching the hero is always hit."""
    vx, vy = ex - px, ey - py
    d = math.hypot(vx, vy)
    if d <= radius + 12:                  # right on top of the hero
        return True
    if d > SWORD_REACH + radius:
        return False
    # the cone is widened by the monster's size: its edge only has to be inside
    edge = math.asin(min(1.0, radius / d))
    return (vx * dx + vy * dy) / d >= math.cos(math.acos(SWORD_ARC) + edge)


def unstick(e, dungeon, radius=4):
    """A monster standing inside a wall (pushed there): move it to the nearest free spot."""
    if dungeon.can_stand(e.x, e.y):
        return False
    for rad in range(1, radius * 3 + 1):
        r = rad * TILE / 3
        for k in range(12):
            a = k * math.pi / 6
            nx, ny = e.x + math.cos(a) * r, e.y + math.sin(a) * r
            if dungeon.can_stand(nx, ny):
                e.x, e.y = nx, ny
                return True
    return False


def put(surf, font, s, col, x, y, alpha=255, center=False):
    a = font.render(s, True, col)
    b = font.render(s, True, (0, 0, 0))
    if alpha < 255:
        a.set_alpha(alpha)
        b.set_alpha(alpha)
    if center:
        x -= a.get_width() // 2
    surf.blit(b, (x + 1, y + 1))
    surf.blit(a, (x, y))


def bar(surf, x, y, w, h, frac, col, back=(54, 18, 24)):
    pygame.draw.rect(surf, (0, 0, 0), (x - 1, y - 1, w + 2, h + 2))
    pygame.draw.rect(surf, back, (x, y, w, h))
    pygame.draw.rect(surf, col, (x, y, int(w * max(0.0, min(1.0, frac))), h))


# ---- placeholder sprite ---------------------------------------------------
_BOSS_PORTRAITS = {}


def sprite(kind, flip=False):
    """Dialog portrait for a boss / monster `kind`.
    The three bosses use their real art; anything else gets a plain block."""
    if kind == "goblin_king":
        img = _BOSS_PORTRAITS.get(kind)
        if img is None:
            try:
                from bosses.goblin_king.goblin_king import load_image
                from bosses.goblin_king import boss_config as gk_cfg
                sheet = load_image(gk_cfg.SHEET)
                col = gk_cfg.ANIMS["idle"]["frames"][0]
                frame = sheet.subsurface(pygame.Rect(col * gk_cfg.FRAME_W, 0, gk_cfg.FRAME_W, gk_cfg.FRAME_H))
                body = frame.subsurface(frame.get_bounding_rect()).copy()
                img = pygame.transform.scale(body, (body.get_width() * 3, body.get_height() * 3))
            except Exception:
                img = None
            _BOSS_PORTRAITS[kind] = img
        if img is not None:
            return pygame.transform.flip(img, True, False) if flip else img
    if kind in ("minotaur", "lich"):                    # drawn from the real boss art (src/bosses/in_game.py)
        from bosses.in_game import portrait
        img = portrait({"minotaur": "minotaur", "lich": "lich_king"}[kind])
        if img is not None:
            return pygame.transform.flip(img, True, False) if flip else img
    s = pygame.Surface((32, 32), pygame.SRCALPHA)
    s.fill((200, 0, 200, 255))
    return s


# ---- player combat (kept: the map's Player uses dash, hp, sword) ----------
class PlayerCombat:
    def __init__(self, character_class="warrior"):
        self.max_hp = PLAYER_MAX_HP
        self.potions = POTION_START
        self.dmg_bonus = 0          # permanent sword upgrade (boss rewards)
        self.apply_class(character_class)
        self.reset()

    def apply_class(self, character_class):
        """Warrior / Mage / Archer: basic-attack feel, resource bars and skills."""
        st = hero_classes.stats(character_class)
        self.character_class = character_class if character_class in hero_classes.CLASS_STATS else "warrior"
        self.class_name = st["name"]
        self.class_dmg = st["dmg_bonus"]
        self.base_swing_cd = st["swing_cd"]
        self.swing_cd = st["swing_cd"]
        self.base_speed = st["speed"]
        self.resource = st["skill_resource"]
        self.defense = 0
        self.crit = 0
        self.aspd = 0
        self.basic = st.get("attack", {"kind": "melee"})   # sword / arcane bolt / arrow
        self.speed_k = st["speed"]
        self.energy_on_hit = st["energy_on_hit"]
        self.pools = Pools(st["bars"])
        self.caster = SkillCaster(self.character_class)

    @property
    def sword_dmg(self):
        if getattr(self, "one_hit", False):          # tester mode: everything dies in one hit
            return 9999
        return max(1, int(round(SWORD_DMG + BONUS_SCALE * (self.dmg_bonus + self.class_dmg))))

    @property
    def attack_power(self):
        """Exact attack value (gear and Power add fractions) for the stats screen."""
        return SWORD_DMG + BONUS_SCALE * (self.dmg_bonus + self.class_dmg)

    def apply_stats(self, bonus):
        """Gear + stat points (see SaveState.bonus_stats). Max HP / damage are set by the save."""
        self.defense = bonus.get("def", 0)
        self.crit = min(75, bonus.get("crit", 0))
        self.aspd = bonus.get("aspd", 0)
        self.swing_cd = self.base_swing_cd / (1 + self.aspd / 100.0)
        self.speed_k = self.base_speed * (1 + bonus.get("spd", 0) / 100.0)
        self.pools.set_bonus(self.resource, bonus.get("res", 0), bonus.get("regen", 0))

    def damage_taken(self, dmg):
        """Defense softens every hit: x 20 / (20 + defense). Fractions round by chance."""
        eff = dmg * 20.0 / (20.0 + max(0, self.defense))
        whole = int(eff)
        return whole + (1 if random.random() < eff - whole else 0)

    def roll_damage(self):
        """Basic-attack damage, doubled on a crit."""
        dmg = self.sword_dmg
        self.last_crit = bool(self.crit) and random.random() * 100 < self.crit
        return dmg * 2 if self.last_crit else dmg

    def reset(self):
        self.hp = self.max_hp
        self.iframes = 0.0
        self.cd = 0.0
        self.swing = 0.0
        self.swing_dir = (0.0, 1.0)
        self.dead = False
        self.dash_cd = 0.0
        self.dash_inv = 0.0
        self.barrier = None         # Arcane Barrier / Blade Ward: soaks up damage while it lasts
        self.hits = []              # (damage taken, damage a barrier soaked) since the Game last looked
        self.last_crit = False
        self.pools.refill()

    def heal(self, n):
        self.hp = min(self.max_hp, self.hp + n)

    def add_potion(self):
        if self.potions >= POTION_MAX:
            return False
        self.potions += 1
        return True

    def drink(self):
        if self.dead or self.potions <= 0 or self.hp >= self.max_hp:
            return False
        self.potions -= 1
        self.heal(POTION_HEAL + round(self.max_hp * POTION_HEAL_PERCENT / 100))
        return True

    def update(self, dt):
        self.iframes = max(0.0, self.iframes - dt)
        self.cd = max(0.0, self.cd - dt)
        self.swing = max(0.0, self.swing - dt)
        self.dash_cd = max(0.0, self.dash_cd - dt)
        self.dash_inv = max(0.0, self.dash_inv - dt)
        if not self.dead:
            self.pools.update(dt)
        self.caster.update(dt)

    def try_dash(self, player, dx, dy):
        if self.dead or self.dash_cd > 0 or player.dash_t > 0:
            return False
        if not self.pools.spend("stamina", hero_classes.DASH_STAMINA):
            return False
        l = math.hypot(dx, dy)
        if l < 1e-6:
            dx, dy = player.face
            l = math.hypot(dx, dy)
        if l < 1e-6:
            dx, dy, l = 0.0, 1.0, 1.0
        player.dash_dir = (dx / l, dy / l)
        player.dash_t = DASH_TIME
        self.dash_cd = DASH_COOLDOWN
        self.dash_inv = DASH_IFRAMES
        return True

    def blinking(self):
        return self.iframes > 0 and int(self.iframes * 20) % 2 == 0

    def hurt(self, dmg, player, dungeon, fx, fy):
        """Call this from your monster/projectile code when the player is hit.
        (fx, fy) is where the hit came from (used for knockback)."""
        if self.iframes > 0 or self.dash_inv > 0 or self.dead or getattr(self, "god", False):   # god: tester mode
            return False
        dmg = self.damage_taken(dmg)
        b = self.barrier
        if b is not None and not b.done and b.absorb > 0:
            soak = min(b.absorb, dmg)
            b.absorb -= soak
            b.flash = 0.25
            dmg -= soak
            if dmg <= 0:
                self.iframes = 0.35
                self.hits.append((0, soak))
                return True
        else:
            soak = 0
        self.hits.append((dmg, soak))
        self.hp -= dmg
        self.iframes = 0.9
        dx, dy = player.x - fx, player.y - fy
        l = math.hypot(dx, dy) or 1.0
        for _ in range(3):
            nx, ny = player.x + dx / l * 5, player.y + dy / l * 5
            if dungeon.can_stand(nx, ny):
                player.x, player.y = nx, ny
            else:
                break
        if self.hp <= 0:
            self.hp = 0
            self.dead = True
        return True

    @property
    def ranged(self):
        return self.basic["kind"] != "melee"

    def can_attack(self):
        """Off cooldown, alive and (Mage) enough mana for a bolt."""
        if self.cd > 0 or self.dead:
            return False
        b = self.basic
        return not b.get("cost") or self.pools.can_spend(b["resource"], b["cost"])

    def try_attack(self, player, enc, aim=None, fx=None, release=0.0):
        """The basic attack. Warrior: a sword hit in front (the Knight's spritesheet shows it).
        Mage / Archer: an arcane bolt / arrow into `fx` (SkillFX) toward `aim`, leaving after
        `release` seconds so it matches the sprite. Returns True if an attack happened."""
        if not self.can_attack() or (self.ranged and fx is None):
            return False
        dx, dy = aim if aim else player.face
        l = math.hypot(dx, dy)
        if l < 1e-6:
            dx, dy, l = 0.0, 1.0, 1.0
        dx, dy = dx / l, dy / l
        self.cd = self.swing_cd
        self.swing = SWING_TIME
        self.swing_dir = (dx, dy)
        if abs(dx) > abs(dy):
            player.dir = "right" if dx > 0 else "left"
        else:
            player.dir = "down" if dy > 0 else "up"
        b = self.basic
        dmg = self.roll_damage()
        if not self.ranged:
            enc.player_swing(player, dx, dy, dmg)
            return True
        if b.get("cost"):
            self.pools.spend(b["resource"], b["cost"])
        spawn_basic(fx, b["kind"], player.x, player.y, (dx, dy), dmg, b, delay=release)
        return True


_SLIME_NOISES = {"attack": "slime_attack", "walk": "slime_walk"}
# skin -> {"attack" / "walk": sound name}  (assets/sfx/, see maps.sfx.FILE_SOUNDS)
SKIN_SOUNDS = {
    "wild_boar": {"attack": "boar_attack"},
    "giant_boar": {"attack": "boar_attack"},
    "slime_red": _SLIME_NOISES,
    "slime_blue": _SLIME_NOISES,
    "slime_green": _SLIME_NOISES,
    "treant": {"attack": "shield_bash"},
}
WALK_SOUND_GAP = 0.45       # s between two footstep sounds of one monster
GOBLIN_SKINS = {"goblin_minion", "goblin_shaman", "goblin_general"}


class Enemy:
    def __init__(self, x, y, name, hp, speed, damage, color, radius=14):
        self.x = float(x)
        self.y = float(y)
        self.name = name
        self.max_hp = hp
        self.hp = hp
        self.speed = speed
        self.damage = damage
        self.color = color
        self.radius = radius
        self.attack_cd = 0.0
        self.hit_flash = 0.0
        self.stun_t = 0.0           # skills: can't move or attack
        self.slow_t = 0.0           # skills: moves at SLOW_K speed
        self.face_x = 0             # +1 / -1: which way the sprite looks (0 = from movement)
        self.skin = None            # monsters.game_sprites skin key, None = plain circle
        self.skin_scale = 1.0
        self.shield = 0.0           # Goblin Shaman barrier: soaks this much damage...
        self.shield_t = 0.0         # ...for this many seconds
        self.shield_flash = 0.0
        self.sounds = []            # sound names for whoever runs this monster to play
        self.walk_t = 0.0

    @property
    def dead(self):
        return self.hp <= 0

    def noise(self, what):
        """Queue this skin's "attack" / "walk" sound, if it has one."""
        name = SKIN_SOUNDS.get(self.skin, {}).get(what)
        if name:
            self.sounds.append(name)

    def pop_sounds(self):
        out, self.sounds = self.sounds, []
        return out

    def walked(self, dt):
        """Call after a step: footstep sounds every WALK_SOUND_GAP while it keeps moving."""
        self.walk_t -= dt
        if self.walk_t <= 0:
            self.walk_t = WALK_SOUND_GAP
            self.noise("walk")

    @property
    def speed_k(self):
        return SLOW_K if self.slow_t > 0 else 1.0

    def give_shield(self, amount, seconds):
        """A barrier that soaks `amount` damage for `seconds` (a fresh cast refreshes it)."""
        self.shield = max(self.shield, float(amount))
        self.shield_t = max(self.shield_t, float(seconds))

    def cc_tick(self, dt):
        """Count down stun / slow (and the barrier). True while stunned (skip moving and attacking)."""
        self.slow_t = max(0.0, self.slow_t - dt)
        self.shield_flash = max(0.0, self.shield_flash - dt)
        if self.shield_t > 0:
            self.shield_t = max(0.0, self.shield_t - dt)
            if self.shield_t == 0:
                self.shield = 0.0
        if self.stun_t > 0:
            self.stun_t = max(0.0, self.stun_t - dt)
            return True
        return False

    def update(self, dt, player, dungeon, pc):
        if self.dead:
            return
        self.attack_cd = max(0.0, self.attack_cd - dt)
        self.hit_flash = max(0.0, self.hit_flash - dt)
        if self.cc_tick(dt):
            return
        dx, dy = player.x - self.x, player.y - self.y
        self.face_x = 1 if dx > 0 else -1
        distance = math.hypot(dx, dy) or 1.0
        if distance > self.radius + CONTACT_REACH:
            if move_enemy(self, player.x, player.y, dt, dungeon):
                self.walked(dt)
        elif self.attack_cd <= 0:
            if pc.hurt(self.damage, player, dungeon, self.x, self.y):
                self.attack_cd = 0.9
                self.noise("attack")

    def refresh_config(self):
        """The config files changed while this monster is alive: read its row again (health keeps
        the same share left, plus speed, damage and hit radius). cfg = (table, key) set at spawn."""
        src = getattr(self, "cfg", None)
        if not src or self.dead:
            return
        table, key = src
        try:
            _name, hp, speed, damage, _color, radius = table[key][:6]
        except (KeyError, TypeError, ValueError):
            return
        hp = hp * getattr(self, "cfg_hp_k", 1.0)              # (e.g. a wilds mob's pack scale)
        hp = int(hp) if isinstance(self.max_hp, int) else hp
        share = self.hp / self.max_hp if self.max_hp else 1.0
        self.max_hp = hp
        self.hp = max(1, round(hp * share)) if hp >= 1 else hp * share
        self.speed = speed * getattr(self, "cfg_speed_k", 1.0)
        self.damage, self.radius = damage, radius * getattr(self, "cfg_radius_k", 1.0)

    def take_damage(self, amount):
        if self.dead:
            return
        if self.shield > 0:                         # the barrier eats the hit first
            soak = min(self.shield, amount)
            self.shield -= soak
            amount -= soak
            self.shield_flash = 0.2
            if self.shield <= 0:
                self.shield, self.shield_t = 0.0, 0.0
            if amount <= 0:
                return
        self.hp = max(0, self.hp - amount)
        self.hit_flash = 0.12

    def draw_shield(self, surf, x, feet_y, body_h):
        """A see-through bubble around the monster while a barrier holds."""
        if self.shield <= 0 or (self.shield_t < 1.0 and int(self.shield_t * 10) % 2 == 0):
            return                                   # blinks out during its last second
        w = int(max(self.radius * 2.6, body_h * 0.8)) + 8
        h = int(body_h * 1.1) + 8
        pulse = 0.5 + 0.5 * math.sin(pygame.time.get_ticks() / 180.0)
        hot = self.shield_flash > 0
        b = pygame.Surface((w, h), pygame.SRCALPHA)
        pygame.draw.ellipse(b, (110, 210, 255, 70 if hot else 34), b.get_rect())
        pygame.draw.ellipse(b, (190, 245, 255, 230) if hot else (120, 220, 255, int(130 + 70 * pulse)),
                            b.get_rect(), 2)
        surf.blit(b, (x - w // 2, feet_y - h + 4))

    def draw(self, surf, cx, cy):
        if self.dead:
            return
        if self.skin:
            from monsters import game_sprites
            rect = game_sprites.draw_enemy(self, surf, cx, cy)
            self.draw_shield(surf, int(self.x - cx), int(self.y - cy), game_sprites.body_height(self))
            if self.hp < self.max_hp:
                w = max(28, self.radius * 2)
                bar(surf, int(self.x - cx) - w // 2, rect.top + 4, w, 4,
                    self.hp / self.max_hp, (210, 54, 60), (45, 18, 24))
            if self.stun_t > 0:                           # little stars over its head
                for i in range(3):
                    a = pygame.time.get_ticks() / 160 + i * 2.1
                    pygame.draw.circle(surf, (255, 230, 120), (int(self.x - cx + math.cos(a) * 12),
                                                               rect.top + 2 + int(math.sin(a) * 4)), 2)
            return
        x, y = int(self.x - cx), int(self.y - cy - 14)
        color = (255, 245, 220) if self.hit_flash else self.color
        self.draw_shield(surf, x, int(self.y - cy), self.radius * 2 + 14)
        pygame.draw.ellipse(surf, (18, 12, 18), (x - self.radius, y + self.radius - 3,
                                                  self.radius * 2, 10))
        pygame.draw.circle(surf, color, (x, y), self.radius)
        pygame.draw.circle(surf, (20, 16, 24), (x - 5, y - 2), 2)
        pygame.draw.circle(surf, (20, 16, 24), (x + 5, y - 2), 2)
        bar(surf, x - self.radius, y - self.radius - 8, self.radius * 2, 4,
            self.hp / self.max_hp, (210, 54, 60), (45, 18, 24))


SLOW_K = 0.45                       # speed while slowed by Frost Nova


def projectile_open(dungeon, x, y):
    """Can a fireball / arrow be here? Walls and the locked room's edge stop it; puddles,
    statues and crates don't (unlike walking, see Dungeon.can_stand)."""
    lr = getattr(dungeon, "lock_rect", None)
    if lr is not None and not lr.collidepoint(x, y):
        return False
    if not hasattr(dungeon, "tiles"):                # the overworld (night_raid._Ground): trees and walls
        return dungeon.can_stand(x, y)
    tx, ty = int(x // TILE), int(y // TILE)
    if not (0 <= tx < MAP_W and 0 <= ty < MAP_H):
        return False
    return dungeon.tiles[ty * MAP_W + tx] in OPEN


_BOLT_ART = {}


def _bolt_art():
    """The shaman's fireball (assets/monsters/mobs/attack/goblin_shaman_fireball_bolt.png, made by
    tools/make_shaman_cast.py), scaled like the mobs and padded so the ball sits in the centre
    (then rotating it keeps the ball where the bolt is). None if it can't load."""
    if "img" not in _BOLT_ART:
        img = None
        try:
            from monsters import mobs
            raw = pygame.image.load(os.path.join(mobs.DEFAULT_ASSETS, "attack",
                                                 "goblin_shaman_fireball_bolt.png")).convert_alpha()
            k = 0.5                                       # art px=4, game MOB_PIXEL=2
            raw = pygame.transform.scale(raw, (int(raw.get_width() * k), int(raw.get_height() * k)))
            hot = []
            for px in range(raw.get_width()):
                for py in range(raw.get_height()):
                    c = raw.get_at((px, py))
                    if c.a > 200 and c.r > 240 and c.g > 200:
                        hot.append((px, py))
            bx = sum(p[0] for p in hot) / len(hot) if hot else raw.get_width() - 8
            by = sum(p[1] for p in hot) / len(hot) if hot else raw.get_height() / 2
            half = int(max(bx, raw.get_width() - bx, by, raw.get_height() - by)) + 2
            img = pygame.Surface((half * 2, half * 2), pygame.SRCALPHA)
            img.blit(raw, (int(half - bx), int(half - by)))
        except Exception:
            img = None
        _BOLT_ART["img"] = img
    return _BOLT_ART["img"]


class EnemyBolt:
    """A Goblin Shaman's fireball: flies straight, hurts the hero, stops at walls.
    (x, y) is the floor point under it; it is drawn `lift` px up, starting at the staff orb
    and settling to body height."""

    BODY_LIFT = 14.0

    def __init__(self, x, y, dx, dy, damage, speed=190.0, lift=BODY_LIFT):
        self.x, self.y = x, y
        d = math.hypot(dx, dy) or 1.0
        self.vx, self.vy = dx / d * speed, dy / d * speed
        self.damage = damage
        self.life = 2.4
        self.dead = False
        self.lift = float(lift)
        self._img = None

    def update(self, dt, player, dungeon, pc):
        self.x += self.vx * dt
        self.y += self.vy * dt
        self.life -= dt
        self.lift += (self.BODY_LIFT - self.lift) * min(1.0, dt * 9.0)
        if self.life <= 0 or not projectile_open(dungeon, self.x, self.y):
            self.dead = True
        elif math.hypot(player.x - self.x, player.y - self.y) < 16:
            pc.hurt(self.damage, player, dungeon, self.x, self.y)
            self.dead = True

    def draw(self, surf, cx, cy, t):
        x, y = int(self.x - cx), int(self.y - cy - self.lift)
        if self._img is None:
            art = _bolt_art()
            if art is not None:
                angle = -math.degrees(math.atan2(self.vy, self.vx))
                self._img = pygame.transform.rotate(art, angle)
        if self._img is not None:
            surf.blit(self._img, self._img.get_rect(center=(x, y)))
            return
        pygame.draw.circle(surf, (120, 40, 20), (x, y), 8)
        pygame.draw.circle(surf, (255, 140, 50), (x, y), 6)
        pygame.draw.circle(surf, (255, 240, 180), (x - 1, y - 1), 3)


def _cast_times(clip):
    """(release, length) in seconds of a Goblin Shaman cast sheet, from monsters/mobs.py:
    release = when its hit frame starts (the fireball leaves the orb / the barrier pops)."""
    try:
        from monsters import mobs
        spec = mobs.clip_specs("goblin_shaman")[clip]
        ms = spec["ms"]
        return sum(ms[:spec["hit_frame"]]) / 1000.0, sum(ms) / 1000.0
    except Exception:
        return 0.36, 0.8


# Goblin Shaman barrier: shields itself and the monsters around it
BARRIER_SHIELD = 6          # damage it soaks per monster
BARRIER_TIME = 6.0          # seconds it lasts
BARRIER_RANGE = 170         # px around the shaman
BARRIER_COOLDOWN = 9.0
STAFF_ORB = (24, 64)        # the staff's orb: px in front of / above the shaman's feet


class RangedEnemy(Enemy):
    """The Goblin Shaman: keeps its distance and throws fireballs, and now and then raises a
    barrier on itself and its fellow monsters. Casts follow the sprite: the fireball leaves the
    staff orb on the cast sheet's hit frame. `allies` = a function giving the room's monsters."""

    FIREBALL = _cast_times("fireball")
    BARRIER = _cast_times("barrier")

    def __init__(self, *args, bolts=None, allies=None, **kw):
        super().__init__(*args, **kw)
        self.bolts = bolts if bolts is not None else []
        self.allies = allies
        self.attack_cd = random.uniform(0.6, 1.6)
        self.barrier_cd = random.uniform(1.5, 3.5)
        self.attack_clip = "attack"        # which sheet game_sprites plays: "attack" or "barrier"
        self.cast = None                   # {"clip", "t", "release", "length", "done"} while casting

    def barrier_targets(self):
        """Itself and the monsters near it that a barrier can hold (bosses can't take one)."""
        group = list(self.allies()) if self.allies else [self]
        if self not in group:
            group.append(self)
        return [e for e in group if not e.dead and hasattr(e, "give_shield")
                and getattr(e, "kind", "") != "boss"
                and math.hypot(e.x - self.x, e.y - self.y) <= BARRIER_RANGE]

    def _start_cast(self, clip):
        release, length = self.BARRIER if clip == "barrier" else self.FIREBALL
        self.attack_clip = "barrier" if clip == "barrier" else "attack"
        self.cast = {"clip": clip, "t": 0.0, "release": release, "length": length, "done": False}
        self.attack_cd = 1.4 if clip == "barrier" else 2.2      # the jump starts the sprite's cast
        if clip == "barrier":
            self.barrier_cd = BARRIER_COOLDOWN

    def _cast_step(self, dt, player, dungeon, pc):
        c = self.cast
        c["t"] += dt
        if not c["done"] and c["t"] >= c["release"]:
            c["done"] = True
            if c["clip"] == "barrier":
                self.sounds.append("shaman_barrier")
                for e in self.barrier_targets():
                    e.give_shield(BARRIER_SHIELD, BARRIER_TIME)
            elif not pc.dead:
                self.sounds.append("shaman_fireball")
                ox, oz = STAFF_ORB
                bx = self.x + self.face_x * ox
                self.bolts.append(EnemyBolt(bx, self.y, player.x - bx, player.y - self.y, self.damage,
                                            lift=oz))
        if c["t"] >= c["length"]:
            self.cast = None

    def update(self, dt, player, dungeon, pc):
        if self.dead:
            return
        self.attack_cd = max(0.0, self.attack_cd - dt)
        self.barrier_cd = max(0.0, self.barrier_cd - dt)
        self.hit_flash = max(0.0, self.hit_flash - dt)
        if self.cc_tick(dt):
            self.cast = None                       # a stun breaks the spell
            return
        if self.cast is not None:                  # stands still and faces the way it cast
            self._cast_step(dt, player, dungeon, pc)
            return
        dx, dy = player.x - self.x, player.y - self.y
        self.face_x = 1 if dx > 0 else -1
        d = math.hypot(dx, dy) or 1.0
        if d > 230:                         # close in
            move_enemy(self, player.x, player.y, dt, dungeon)
        elif d < 120:                       # back off
            move_enemy(self, player.x, player.y, dt, dungeon, away=True)
        if d < 330 and self.attack_cd <= 0 and not pc.dead:
            if self.barrier_cd <= 0 and any(e.shield <= 0 for e in self.barrier_targets()):
                self._start_cast("barrier")
            else:
                self._start_cast("fireball")


# ---- the Berserker Dungeon: orcs, orc shamans and treants -------------------------------------
# Art: assets/monsters/berserker/ (tools/make_berserker_sprites.py). Attacks follow the sprite: each one
# lands on its clip's hit frame (read from the skin's config.json).
ORC_REACH = 30              # px past its own radius that the axe reaches
ORC_ARC = 55                # degrees either side of where it aimed: step behind it and the slash misses
ORC_COOLDOWN = 0.9          # s after a slash
METEOR_CD = 3.0             # s between an Orc Shaman's meteors
METEOR_FALL = 0.9           # s from the warning circle to the impact (time to step out)
METEOR_R = 46               # px: the impact circle
METEOR_DMG = 4
METEOR_RANGE = 340          # px: it casts when the hero is this close
ROOT_CD = 4.5               # s between a Treant's root attacks
ROOT_RANGE = 220            # px
ROOT_DELAY = 0.8            # s from the green warning circle to the roots bursting out
ROOT_R = 40                 # px
ROOT_DMG = 2
ROOT_TIME = 1.2             # s the hero is held (can't walk or dash)


def _clip_times(skin, clip, fallback):
    """(seconds to the hit frame, clip length) of a Berserker skin's animation."""
    try:
        from monsters import game_sprites
        return game_sprites.clip_times(skin, clip)
    except Exception:
        return fallback


def _walk_toward(e, dx, dy, dist, dt, dungeon, away=False):
    """Step toward (or away from) the point (e.x + dx, e.y + dy); see move_enemy."""
    if move_enemy(e, e.x + dx, e.y + dy, dt, dungeon, away=away):
        e.walked(dt)


class OrcEnemy(Enemy):
    """The Orc Warrior (and the Orc Warlord): walks up, raises its axe, and slashes in front of it.
    The aim is fixed when the swing starts, so a quick sidestep or a dash behind it makes it miss."""

    def __init__(self, *args, reach=None, swing_sound="swing", **kw):
        super().__init__(*args, **kw)
        # None = ORC_REACH (read live, so orc_warrior.toml "reach" applies), a setting's name like
        # "WARLORD_REACH" = that setting, a number = fixed
        self._reach = reach
        self.swing_sound = swing_sound
        self.swing = None                 # seconds into a slash (None = not slashing)
        self.swung = False
        self.aim = (-1.0, 0.0)
        self.release, self.length = 0.26, 0.75

    @property
    def reach(self):
        r = self._reach
        if r is None:
            return ORC_REACH
        return globals().get(r, ORC_REACH) if isinstance(r, str) else r

    @reach.setter
    def reach(self, value):
        self._reach = value

    def in_arc(self, player):
        dx, dy = player.x - self.x, player.y - self.y
        d = math.hypot(dx, dy)
        if d > self.radius + self.reach + 10:          # (10: the hero's own size)
            return False
        if d < 1:
            return True
        return (dx * self.aim[0] + dy * self.aim[1]) / d >= math.cos(math.radians(ORC_ARC))

    def update(self, dt, player, dungeon, pc):
        if self.dead:
            return
        self.attack_cd = max(0.0, self.attack_cd - dt)
        self.hit_flash = max(0.0, self.hit_flash - dt)
        if self.cc_tick(dt):
            self.swing = None                          # a stun breaks the swing
            return
        if self.swing is not None:
            self.swing += dt
            if not self.swung and self.swing >= self.release:
                self.swung = True
                if not pc.dead and self.in_arc(player):
                    pc.hurt(self.damage, player, dungeon, self.x, self.y)
            if self.swing >= self.length:
                self.swing = None
            return
        dx, dy = player.x - self.x, player.y - self.y
        dist = math.hypot(dx, dy) or 1.0
        self.face_x = 1 if dx > 0 else -1
        if dist > self.radius + self.reach * 0.6 + 6:
            _walk_toward(self, dx, dy, dist, dt, dungeon)
        elif self.attack_cd <= 0 and not pc.dead:      # wind up the slash
            self.release, self.length = _clip_times(self.skin or "orc_warrior", "attack", (0.26, 0.75))
            self.swing, self.swung = 0.0, False
            self.aim = (dx / dist, dy / dist)
            self.attack_cd = self.length + ORC_COOLDOWN   # (the jump starts the sprite's attack clip)
            self.sounds.append(self.swing_sound)


class OrcShaman(Enemy):
    """Keeps its distance and calls down a meteor every METEOR_CD seconds where the hero stands."""

    def __init__(self, *args, hazards=None, **kw):
        super().__init__(*args, **kw)
        self.hazards = hazards if hazards is not None else []
        self.attack_cd = random.uniform(1.0, 2.0)
        self.attack_clip = "cast"
        self.cast = None                  # [seconds in, release, length, done]

    def update(self, dt, player, dungeon, pc):
        if self.dead:
            return
        self.attack_cd = max(0.0, self.attack_cd - dt)
        self.hit_flash = max(0.0, self.hit_flash - dt)
        if self.cc_tick(dt):
            self.cast = None                           # a stun breaks the spell
            return
        if self.cast is not None:                      # stands still while the orb grows
            c = self.cast
            c[0] += dt
            if not c[3] and c[0] >= c[1]:
                c[3] = True
                if not pc.dead:
                    self.hazards.append(MeteorStrike(player.x, player.y, METEOR_DMG))
                    self.sounds.append("meteor")
            if c[0] >= c[2]:
                self.cast = None
            return
        dx, dy = player.x - self.x, player.y - self.y
        d = math.hypot(dx, dy) or 1.0
        self.face_x = 1 if dx > 0 else -1
        if d > 300:
            _walk_toward(self, dx, dy, d, dt, dungeon)
        elif d < 140:
            _walk_toward(self, dx, dy, d, dt, dungeon, away=True)
        if d < METEOR_RANGE and self.attack_cd <= 0 and not pc.dead:
            release, length = _clip_times("orc_shaman", "cast", (0.5, 0.9))
            self.cast = [0.0, release, length, False]
            self.attack_cd = METEOR_CD                  # (the jump starts the sprite's cast clip)


class TreantEnemy(Enemy):
    """Slow and tough. Hits whatever touches it, and now and then drives its branches into the ground:
    roots burst out under the hero and hold him in place."""

    def __init__(self, *args, hazards=None, **kw):
        super().__init__(*args, **kw)
        self.hazards = hazards if hazards is not None else []
        self.root_cd = random.uniform(1.5, 3.0)
        self.cast = None

    def update(self, dt, player, dungeon, pc):
        if self.dead:
            return
        self.root_cd = max(0.0, self.root_cd - dt)
        if self.cast is not None:
            self.attack_cd = max(0.0, self.attack_cd - dt)
            self.hit_flash = max(0.0, self.hit_flash - dt)
            if self.cc_tick(dt):
                self.cast = None
                return
            c = self.cast
            c[0] += dt
            if not c[3] and c[0] >= c[1]:
                c[3] = True
                if not pc.dead:
                    self.hazards.append(RootSnare(player.x, player.y))
                    self.sounds.append("earthsplitter")
            if c[0] >= c[2]:
                self.cast = None
            return
        d = math.hypot(player.x - self.x, player.y - self.y)
        if (self.root_cd <= 0 and d <= ROOT_RANGE and not pc.dead and self.stun_t <= 0
                and d > self.radius + 22):                 # (right next to it, it just hits)
            release, length = _clip_times("treant", "attack", (0.42, 0.98))
            self.cast = [0.0, release, length, False]
            self.root_cd = ROOT_CD
            self.face_x = 1 if player.x > self.x else -1
            self.attack_cd = max(self.attack_cd, 0.0) + length + 0.3   # (the jump starts the clip)
            return
        super().update(dt, player, dungeon, pc)


class _GroundSpell:
    """Something on the floor that warns first and goes off later (a meteor, a root snare)."""

    def __init__(self, x, y, delay, radius, linger):
        self.x, self.y = x, y
        self.delay, self.radius, self.linger = delay, radius, linger
        self.t = 0.0
        self.fired = False
        self.dead = False
        self.sounds = []

    def pop_sounds(self):
        out, self.sounds = self.sounds, []
        return out

    def update(self, dt, player, dungeon, pc):
        self.t += dt
        if not self.fired and self.t >= self.delay:
            self.fired = True
            if not pc.dead and math.hypot(player.x - self.x, player.y - self.y) <= self.radius:
                self.hit(player, dungeon, pc)
            self.went_off()
        if self.t >= self.delay + self.linger:
            self.dead = True

    def hit(self, player, dungeon, pc):
        pass

    def went_off(self):
        pass

    def ring(self, surf, cx, cy, color, fill_k):
        """The warning on the floor: an outline and a fill that grows until it goes off."""
        r = self.radius
        size = (int(r * 2) + 4, int(r) + 4)
        s = pygame.Surface(size, pygame.SRCALPHA)
        rect = pygame.Rect(2, 2, int(r * 2), int(r))
        inner = rect.inflate(-int(r * 2 * (1 - fill_k)), -int(r * (1 - fill_k)))
        if inner.w > 0 and inner.h > 0:
            pygame.draw.ellipse(s, (*color, 90), inner)
        pygame.draw.ellipse(s, (*color, 220), rect, 2)
        surf.blit(s, (int(self.x - cx - r) - 2, int(self.y - cy - r / 2) - 2))


class MeteorStrike(_GroundSpell):
    """An Orc Shaman's meteor: a red circle on the floor, a burning rock falling into it, then the impact."""

    def __init__(self, x, y, damage):
        super().__init__(x, y, METEOR_FALL, METEOR_R, 0.45)
        self.damage = damage

    def hit(self, player, dungeon, pc):
        pc.hurt(self.damage, player, dungeon, self.x, self.y)

    def went_off(self):
        self.sounds.append("boom")

    def draw(self, surf, cx, cy, t):
        X, Y = int(self.x - cx), int(self.y - cy)
        if not self.fired:
            k = min(1.0, self.t / self.delay)
            self.ring(surf, cx, cy, (235, 80, 40), k)
            fall = (1.0 - k) ** 1.4
            rx, ry = X - 90 * fall, Y - 300 * fall
            for i in range(4, 0, -1):                      # the trail
                tx, ty = rx - 90 * 0.05 * i * 1.6, ry - 300 * 0.05 * i * 1.6
                pygame.draw.circle(surf, (255, 120 + 20 * i, 40), (int(tx), int(ty)), max(1, 7 - i))
            pygame.draw.circle(surf, (110, 40, 20), (int(rx), int(ry)), 9)
            pygame.draw.circle(surf, (255, 130, 50), (int(rx), int(ry)), 7)
            pygame.draw.circle(surf, (255, 236, 170), (int(rx) - 2, int(ry) - 2), 3)
            return
        a = min(1.0, (self.t - self.delay) / self.linger)
        r = self.radius * (0.6 + 0.8 * a)
        s = pygame.Surface((int(r * 2) + 8, int(r) + 8), pygame.SRCALPHA)
        pygame.draw.ellipse(s, (40, 24, 20, int(150 * (1 - a))), s.get_rect().inflate(-4, -4))     # scorch
        pygame.draw.ellipse(s, (255, 170, 70, int(230 * (1 - a))), s.get_rect().inflate(-4, -4), 3)
        surf.blit(s, (X - s.get_width() // 2, Y - s.get_height() // 2))
        for i in range(8):                                  # sparks
            ang = i * math.tau / 8 + 0.3
            d0, d1 = r * 0.4, r * (0.7 + 0.5 * a)
            pygame.draw.line(surf, (255, 210, 120), (X + math.cos(ang) * d0, Y + math.sin(ang) * d0 * 0.5 - 6 * a),
                             (X + math.cos(ang) * d1, Y + math.sin(ang) * d1 * 0.5 - 14 * a), 2)


class RootSnare(_GroundSpell):
    """A Treant's root attack: a green circle with cracks, then roots burst out and hold the hero."""

    def __init__(self, x, y):
        super().__init__(x, y, ROOT_DELAY, ROOT_R, 0.6)

    def hit(self, player, dungeon, pc):
        if pc.hurt(ROOT_DMG, player, dungeon, self.x, self.y) and hasattr(player, "afflict"):
            player.afflict("root", ROOT_TIME)          # (a dashing hero takes no hit, so no roots)

    def draw(self, surf, cx, cy, t):
        X, Y = int(self.x - cx), int(self.y - cy)
        if not self.fired:
            k = min(1.0, self.t / self.delay)
            self.ring(surf, cx, cy, (120, 230, 90), k)
            for i in range(5):                              # cracks spreading over the floor
                ang = i * math.tau / 5 + 0.5
                L = self.radius * 0.9 * k
                pygame.draw.line(surf, (80, 190, 70), (X, Y),
                                 (X + math.cos(ang) * L, Y + math.sin(ang) * L * 0.5), 2)
            return
        a = min(1.0, (self.t - self.delay) / self.linger)
        rise = math.sin(min(1.0, a * 1.6) * math.pi / 2) * (1 - max(0.0, a - 0.6) / 0.4 * 0.6)
        for i in range(7):                                  # roots / tendrils
            ang = i * math.tau / 7 + 0.2
            bx = X + math.cos(ang) * self.radius * 0.7
            by = Y + math.sin(ang) * self.radius * 0.35
            h = 26 * rise
            tip = (bx - math.cos(ang) * 8, by - h)
            pygame.draw.line(surf, (70, 46, 28), (bx, by), tip, 5)
            pygame.draw.line(surf, (128, 92, 56), (bx - 1, by), (tip[0] - 1, tip[1]), 2)
            pygame.draw.circle(surf, (110, 190, 80), (int(tip[0]), int(tip[1])), 2)


# rooms with no monsters (they start "safe" and never lock)
SAFE_ROLES = {"start", "shrine", "trap", "stairs", "antechamber"}

# placeholder mini-bosses: name, hp, speed, damage, color, radius
MINIBOSSES = {
    1: ("General Grub", 22, 76, 4, (92, 124, 52), 22),
    2: ("Bloodhowl Captain", 30, 70, 5, (190, 64, 44), 21),
    3: ("Bone Warden", 36, 60, 6, (176, 168, 204), 21),
}


# Goblin Dungeon regulars: name, hp, speed, damage, color, radius
GOBLIN_MOBS = {
    "minion": ("Goblin Minion", 10, 86, 2, (112, 150, 70), 14),
    "shaman": ("Goblin Shaman", 8, 70, 2, (112, 150, 70), 14),
    "slime":  ("Slime", 6, 76, 2, (110, 190, 110), 13),
    "boar":   ("Wild Boar", 12, 96, 3, (124, 86, 56), 18),
}
# The Lich King's skeletons (src/monsters/in_game.py) hold family 3: the Lich King Dungeon and the undead minis.
# first number of the floor -> (regulars' colours, mini-boss name, mini-boss colours)  (colours: monsters VARIANTS)
SKELETON_PLACES = {
    3: ("bone", "Bone Warden", "cursed"),          # Lich King Dungeon
    15: ("ember", "Cinder Warden", "ember"),       # Ashen Pit
    16: ("plague", "Hollow Warden", "frost"),      # Bone Hollow
}
GOBLIN_EXTRAS = ("minion", "slime", "boar")       # the Goblin King's random "extra" summon
GOBLIN_WAR_BOAR = ("Goblin War Boar", 14, 92, 3, (112, 150, 70), 22)   # the guard room's elite

# Berserker Dungeon (family 2) regulars: name, hp, speed, damage, color, radius
BERSERKER_MOBS = {
    "orc": ("Orc Warrior", 12, 84, 3, (110, 150, 70), 15),
    "shaman": ("Orc Shaman", 9, 66, 2, (130, 60, 50), 14),
    "treant": ("Treant", 18, 48, 3, (110, 80, 50), 18),
}
BERSERKER_ROSTER = {"orc": 3, "shaman": 2, "treant": 2}     # weights (at most MAX_SHAMANS shamans)
ELDER_TREANT = ("Elder Treant", 26, 46, 4, (110, 80, 50), 22)   # the guard room's elite
ORC_WARLORD = ("Orc Warlord", 34, 76, 5, (160, 50, 40), 22)     # the mini-boss: a recoloured, bigger orc
WARLORD_SCALE = 1.35
ELDER_SCALE = 1.3
WARLORD_REACH = ORC_REACH + 18                                # its axe reaches further
# Every monster room: this many regular mobs (plus the guard elite / mini-boss where there is one)
MOBS_PER_ROOM = (4, 6)
# Goblin Dungeon rooms are drawn at random from these (weights); at most MAX_SHAMANS shamans
GOBLIN_ROSTER = {"minion": 3, "slime": 2, "boar": 2, "shaman": 2}
MAX_SHAMANS = 2
SPAWN_INSET = 2             # tiles kept clear along the room walls
SPAWN_GAP = 44              # px between two mobs at least
SPAWN_SAFE = 150            # px kept clear around the hero when the room locks
SLIME_SKINS = ("slime_red", "slime_blue", "slime_green")


class Encounters:
    """Room encounters and locks used by the dungeon map."""

    def __init__(self, dungeon):
        self.d = dungeon
        self.font = pygame.font.Font(None, 22)
        n = len(dungeon.rooms)
        self.boss_room = n - 1
        dungeon_id, floor = (int(value) for value in dungeon.floor_name.split("-"))
        self.boss_floor = floor == 3 and dungeon_id in (1, 2, 3)
        self.boss_kind = {1: "goblin_king", 2: "minotaur", 3: "lich"}.get(dungeon_id)
        self.state = ["pending"] * n  # per room: "pending"/"active"/"cleared"
        self.active = None            # index of the room currently locked, or None
        self.dialog_request = None    # set to a boss kind to play its intro dialog
        self.boss_intro_done = False  # (the intro plays the first time the boss room locks)
        self.outro_request = None     # set to a boss kind to play its outro dialog
        self.sound_queue = []         # sound names for Game to play
        self.enemies = []
        self.rng = random.Random(getattr(dungeon, "rng_key", dungeon.floor_name))
        self.roles = getattr(dungeon, "room_roles", None)
        self.miniboss = None          # the mini-boss Enemy while it is alive (for the HUD bar)
        self.family = getattr(dungeon, "family", dungeon_id)   # which monsters (mini dungeons borrow one)
        self.killed = []              # (x, y, max_hp, kind) of enemies that died; the Game turns them into XP
        self.bolts = []               # Goblin Shaman fireballs in flight
        self.summon_spots = []        # where the Goblin King's minions will appear (phase 2 roar)
        self.hazards = []             # Berserker spells on the floor: meteors, root snares
        self.hosts = []               # skeleton rooms (monsters.in_game.SkeletonHost): they draw their skeletons
        if self.roles:
            for k, role in enumerate(self.roles):
                if role in SAFE_ROLES:
                    self.state[k] = "safe"
        self.exit_ready = self._exit_ready()

    @property
    def locked(self):
        return self.active is not None

    def exit_open(self):
        return self.exit_ready

    def snd(self, name):
        self.sound_queue.append(name)

    def _exit_ready(self):
        if not self.roles:
            return all(state == "cleared" for state in self.state)
        if self.boss_floor or self.roles[-1] == "lair":
            return self.state[len(self.state) - 1] == "cleared"
        return True       # floors 1-2: the locked stairs door (map side) is what holds you back

    def update(self, dt, player, pc):
        for host in self.hosts:                 # skeletons: spacing, raised dead, falling apart (even after a clear)
            host.step(dt)
            if self.active is not None:
                self.enemies.extend(host.new_members())
        self.hosts = [h for h in self.hosts if not h.done]
        if self.active is None:
            room = next((i for i, rect in enumerate(self.d.rooms)
                         if rect.collidepoint(int(player.x // TILE), int(player.y // TILE))), None)
            if room is not None and self.state[room] not in ("cleared", "safe"):
                self._start_room(room, player)
            return

        for enemy in self.enemies:
            enemy.update(dt, player, self.d, pc)
            self.sound_queue.extend(enemy.pop_sounds())
        for bolt in self.bolts:
            bolt.update(dt, player, self.d, pc)
        self.bolts[:] = [b for b in self.bolts if not b.dead]     # in place: shamans hold this list
        for spell in self.hazards:
            spell.update(dt, player, self.d, pc)
            self.sound_queue.extend(spell.pop_sounds())
        self.hazards[:] = [h for h in self.hazards if not h.dead]     # in place: casters hold this list
        self._boss_phase2()
        for boss in [e for e in self.enemies if hasattr(e, "new_minions")]:
            self.enemies.extend(boss.new_minions())           # the Lich King's skeletons can be hit
        if any(getattr(e, "kind", "") == "boss" and e.dead for e in self.enemies):
            # the king has fallen: his minions scatter (gone, no XP)
            self.enemies = [e for e in self.enemies if not getattr(e, "summoned", False)]
            self.summon_spots = []
        for enemy in self.enemies:
            if enemy.dead and not getattr(enemy, "no_reward", False):
                self.killed.append((enemy.x, enemy.y, enemy.max_hp, getattr(enemy, "kind", "normal")))
        self.enemies = [enemy for enemy in self.enemies if not enemy.dead]
        if self.enemies:
            return
        self.bolts.clear()
        self.hazards.clear()

        room = self.active
        self.state[room] = "cleared"
        self.active = None
        self.d.lock_rect = None
        self.snd("room_clear")
        pc.heal(HEAL_ON_CLEAR + round(pc.max_hp * HEAL_ON_CLEAR_PERCENT / 100))
        if room == self.boss_room and self.boss_floor and self.boss_kind:
            self.outro_request = self.boss_kind
        self.miniboss = None
        self.exit_ready = self._exit_ready()

    def _start_room(self, room, player):
        self.active = room
        self.state[room] = "active"
        rect = self.d.rooms[room]
        self.d.lock_rect = pygame.Rect(rect.x * TILE, rect.y * TILE,
                                       rect.w * TILE, rect.h * TILE)
        is_boss = room == self.boss_room and self.boss_floor
        if is_boss:
            if self.boss_kind == "goblin_king":        # the real sprite boss
                from bosses.goblin_king.in_game import GoblinKingEnemy
                self.enemies = [GoblinKingEnemy(rect.centerx * TILE, rect.centery * TILE)]
            else:                                      # the Minotaur and the Lich King (src/bosses/in_game.py)
                from bosses.in_game import BossEnemy
                key = {"minotaur": "minotaur", "lich": "lich_king"}[self.boss_kind]
                self.enemies = [BossEnemy(key, rect.x * TILE, rect.y * TILE, rect.w * TILE, rect.h * TILE)]
            if not self.boss_intro_done:                 # (not again after every retry)
                self.boss_intro_done = True
                self.dialog_request = self.boss_kind
        else:
            names = {
                1: ("Goblin", (112, 150, 70)),
                2: ("Berserker", (174, 76, 52)),
                3: ("Deadling", (112, 86, 164)),
            }
            dungeon_id = self.family
            name, color = names.get(dungeon_id, names[3])
            role = self.roles[room] if self.roles else "combat"
            cx, cy = rect.centerx, rect.centery
            count = self.rng.randint(*MOBS_PER_ROOM)
            spots = self._spawn_spots(rect, count, player)
            goblins = dungeon_id == 1         # the Goblin Dungeon family: real sprites
            if dungeon_id == 3:               # the Lich King's skeletons
                self._skeleton_room(rect, role, count, spots)
                return
            if dungeon_id == 2:               # orcs, orc shamans and treants
                self._berserker_room(rect, role, count, spots)
                return
            if goblins:
                self.enemies = [self._goblin_mob(kind, x, y)
                                for kind, (x, y) in zip(self._goblin_roster(count), spots)]
            else:
                self.enemies = [Enemy(x, y, name, 8, 82, 2, color) for x, y in spots]
            if role == "guard":          # an elite holds the floor key
                if goblins:
                    name, hp, speed, damage, ecolor, radius = GOBLIN_WAR_BOAR
                    elite = Enemy(cx * TILE, (cy - 3) * TILE, name, hp, speed, damage, ecolor, radius)
                    elite.skin = "giant_boar"
                    elite.cfg = (globals(), "GOBLIN_WAR_BOAR")
                else:
                    elite = Enemy(cx * TILE, (cy - 3) * TILE, name + " Elite", 14, 78, 3,
                                  tuple(min(255, c + 50) for c in color), 17)
                elite.kind = "elite"
                self.enemies.append(elite)
            elif role in ("miniboss", "lair"):
                mname, hp, speed, dmg, mcol, rad = MINIBOSSES.get(dungeon_id, MINIBOSSES[3])
                self.miniboss = Enemy(cx * TILE, (cy - 2) * TILE, mname, hp, speed, dmg, mcol, rad)
                self.miniboss.cfg = (MINIBOSSES, dungeon_id if dungeon_id in MINIBOSSES else 3)
                if goblins:
                    self.miniboss.skin = "goblin_general"
                self.miniboss.kind = "elite"
                self.enemies.append(self.miniboss)
                self.snd("roar")

    def _skeleton_room(self, rect, role, count, spots):
        """Family 3: the goblins' rule with skeletons. 4-6 of them, an elite brute on a guard room,
        a big recoloured Warden on a mini-boss / lair room."""
        from monsters.in_game import SkeletonHost, make_warden, skeleton_roster
        num = int(self.d.floor_name.split("-")[0])
        variant, warden, warden_variant = SKELETON_PLACES.get(num, SKELETON_PLACES[3])
        host = SkeletonHost(rect.x * TILE, rect.y * TILE, rect.w * TILE, rect.h * TILE, "dungeon",
                            ground=self.d, seed=self.rng.random())
        self.hosts.append(host)
        self.enemies = [host.add(name, x, y, variant=variant)
                        for name, (x, y) in zip(skeleton_roster(self.rng, count), spots)]
        cx, cy = rect.centerx * TILE, rect.centery * TILE
        if role == "guard":                # an elite holds the floor key
            self.enemies.append(host.add("skeleton_brute", cx, cy - 3 * TILE, kind="elite", tier="elite",
                                         variant=variant, display="Grave Brute"))
        elif role in ("miniboss", "lair"):
            self.miniboss = make_warden(host, cx, cy - 2 * TILE, warden, warden_variant)
            self.enemies.append(self.miniboss)
            self.snd("roar")

    def _berserker_room(self, rect, role, count, spots):
        """Family 2 (the Berserker Dungeon and its minis): the goblins' rule with orcs, orc shamans and
        treants. An Elder Treant guards a guard room; the Orc Warlord (a bigger, recoloured orc) holds a
        mini-boss / lair room."""
        self.enemies = [self._berserker_mob(kind, x, y)
                        for kind, (x, y) in zip(self._goblin_roster(count, BERSERKER_ROSTER), spots)]
        cx, cy = rect.centerx, rect.centery
        if role == "guard":                # an elite holds the floor key
            name, hp, speed, dmg, color, radius = ELDER_TREANT
            elite = TreantEnemy(cx * TILE, (cy - 3) * TILE, name, hp, speed, dmg, color, radius,
                                hazards=self.hazards)
            elite.skin, elite.skin_scale, elite.kind = "treant", ELDER_SCALE, "elite"
            elite.cfg = (globals(), "ELDER_TREANT")
            self.enemies.append(elite)
        elif role in ("miniboss", "lair"):
            name, hp, speed, dmg, color, radius = ORC_WARLORD
            boss = OrcEnemy(cx * TILE, (cy - 2) * TILE, name, hp, speed, dmg, color, radius,
                            reach="WARLORD_REACH", swing_sound="king_swing")
            boss.skin, boss.skin_scale, boss.kind = "orc_warlord", WARLORD_SCALE, "elite"
            boss.cfg = (globals(), "ORC_WARLORD")
            boss.cc_immune = True
            self.miniboss = boss
            self.enemies.append(boss)
            self.snd("roar")

    def _berserker_mob(self, kind, x, y):
        name, hp, speed, dmg, color, radius = BERSERKER_MOBS[kind]
        if kind == "orc":
            e = OrcEnemy(x, y, name, hp, speed, dmg, color, radius)
            e.skin = "orc_warrior"
        elif kind == "shaman":
            e = OrcShaman(x, y, name, hp, speed, dmg, color, radius, hazards=self.hazards)
            e.skin = "orc_shaman"
        else:
            e = TreantEnemy(x, y, name, hp, speed, dmg, color, radius, hazards=self.hazards)
            e.skin = "treant"
        e.cfg = (BERSERKER_MOBS, kind)
        return e

    def _boss_phase2(self):
        """The Goblin King at half HP: roar (pick + show spawn spots), then spawn his minions."""
        for boss in [e for e in self.enemies if hasattr(e, "take_summons") and not e.dead]:
            if boss.summoning and not getattr(boss, "_roared", False):
                boss._roared = True
                self.snd("roar")
                self.summon_spots = self._summon_spots(boss)
            if boss.take_summons():
                self._summon_minions(boss)

    def _summon_spots(self, boss):
        from bosses.goblin_king import boss_config as gk_cfg
        n = len(gk_cfg.PHASE2_SUMMONS)
        ring = gk_cfg.SUMMON_RING
        lr = self.d.lock_rect
        spots = []
        start = self.rng.random() * math.tau
        for i in range(n):
            for r_k, turn in ((1.0, 0.0), (0.7, 0.3), (1.3, -0.3), (0.45, 0.6), (0.0, 0.0)):
                a = start + math.tau * i / n + turn
                x, y = boss.x + math.cos(a) * ring * r_k, boss.y + math.sin(a) * ring * r_k
                if free(self.d, x, y, 10, 10) and (lr is None or lr.collidepoint(x, y)):
                    spots.append((x, y))
                    break
            else:
                spots.append((boss.x, boss.y))
        return spots

    def _summon_minions(self, boss):
        from bosses.goblin_king import boss_config as gk_cfg
        spots = self.summon_spots or self._summon_spots(boss)
        for kind, (x, y) in zip(gk_cfg.PHASE2_SUMMONS, spots):
            if kind == "extra":
                kind = self.rng.choice(GOBLIN_EXTRAS)
            e = self._goblin_mob(kind, x, y)
            e.summoned = True
            e.hit_flash = 0.25                       # pops in with a flash
            self.enemies.append(e)
        self.summon_spots = []
        self.snd("roar")

    def _spawn_spots(self, rect, count, player):
        """`count` random floor points (pixels) in room `rect` (tiles): on open floor, off the
        walls, spread apart and not on top of the hero who just walked in."""
        spots = []
        x0, x1 = rect.left + SPAWN_INSET, rect.right - 1 - SPAWN_INSET
        y0, y1 = rect.top + SPAWN_INSET, rect.bottom - 1 - SPAWN_INSET
        px, py = getattr(player, "x", None), getattr(player, "y", None)
        for strict in (True, False):
            tries = 0
            while len(spots) < count and tries < 300:
                tries += 1
                x = (self.rng.randint(x0, max(x0, x1)) + 0.5) * TILE
                y = (self.rng.randint(y0, max(y0, y1)) + 0.5) * TILE
                if not free(self.d, x, y, 10, 10):
                    continue
                if strict and px is not None and math.hypot(x - px, y - py) < SPAWN_SAFE:
                    continue
                if strict and any(math.hypot(x - sx, y - sy) < SPAWN_GAP for sx, sy in spots):
                    continue
                spots.append((x, y))
        while len(spots) < count:                     # tiny / blocked room: around the centre
            k = len(spots)
            ox, oy = ((-2, -1), (2, 1), (0, 3), (-3, 2), (3, -2), (1, -3))[k % 6]
            spots.append(((rect.centerx + ox) * TILE, (rect.centery + oy) * TILE))
        return spots

    def _goblin_roster(self, count, table=None):
        """Which monsters fill a room: a random mix by weight (GOBLIN_ROSTER, or BERSERKER_ROSTER for the
        orcs), at most MAX_SHAMANS shamans."""
        table = GOBLIN_ROSTER if table is None else table
        kinds, weights = list(table), list(table.values())
        roster = []
        while len(roster) < count:
            kind = self.rng.choices(kinds, weights)[0]
            if kind == "shaman" and roster.count("shaman") >= MAX_SHAMANS:
                continue
            roster.append(kind)
        self.rng.shuffle(roster)
        return roster

    def _goblin_mob(self, kind, x, y):
        name, hp, speed, dmg, color, radius = GOBLIN_MOBS[kind]
        if kind == "shaman":
            e = RangedEnemy(x, y, name, hp, speed, dmg, color, radius, bolts=self.bolts,
                            allies=lambda: self.enemies)
            e.skin = "goblin_shaman"
        else:
            e = Enemy(x, y, name, hp, speed, dmg, color, radius)
            e.skin = {"minion": "goblin_minion", "boar": "wild_boar"}.get(kind) or self.rng.choice(SLIME_SKINS)
        e.cfg = (GOBLIN_MOBS, kind)
        return e

    def player_swing(self, player, dx, dy, dmg=None):
        dmg = SWORD_DMG if dmg is None else dmg
        if self.active is None:
            return
        for enemy in self.enemies:
            if enemy.dead:
                continue
            if sword_hits(player.x, player.y, dx, dy, enemy.x, enemy.y, enemy.radius):
                enemy.take_damage(dmg)

    def refresh_config(self):
        """The config files changed: every monster alive in this room reads its numbers again."""
        for e in list(self.enemies):
            fn = getattr(e, "refresh_config", None)
            if fn is not None:
                fn()
        for host in self.hosts:
            fn = getattr(host, "refresh_config", None)
            if fn is not None:
                fn()

    def use_potion(self, player, pc):
        if pc.dead or pc.potions <= 0 or pc.hp >= pc.max_hp:
            return False
        return pc.drink()

    def retry_room(self):
        # Called after the player dies. Reset the room and return its index.
        room = self.active
        if room is None:
            return None
        for enemy in self.enemies:
            getattr(enemy, "dispose", lambda: None)()          # a boss stops its music
        self.enemies = []
        for host in self.hosts:
            host.clear()
        self.hosts = []
        self.bolts.clear()
        self.hazards.clear()
        self.summon_spots = []
        self.active = None
        self.d.lock_rect = None
        self.state[room] = "pending"
        self.miniboss = None
        self.exit_ready = self._exit_ready()
        return room

    def draw(self, surf, cx, cy, t, player, pc):
        # monsters and their projectiles (the hero's attacks are shown by the hero's sprite)
        for i, (x, y) in enumerate(self.summon_spots):      # where the king's minions will appear
            r = 6 + (t * 30 + i * 7) % 16
            pygame.draw.ellipse(surf, (120, 230, 90), (int(x - cx - r), int(y - cy - r * 0.45),
                                                       int(r * 2), int(r * 0.9)), 2)
        for spell in self.hazards:               # meteors and root snares on the floor
            spell.draw(surf, cx, cy, t)
        for host in self.hosts:                  # skeletons (and the ones still falling apart)
            host.draw(surf, cx, cy)
        for enemy in sorted(self.enemies, key=lambda e: e.y):
            enemy.draw(surf, cx, cy)
        for bolt in self.bolts:
            bolt.draw(surf, cx, cy, t)

    def draw_hud(self, surf, cx, cy, pc, t):
        """Boss / mini-boss bars (the hero's own bars are drawn by the Game's hero HUD)."""
        boss = next((e for e in self.enemies if getattr(e, "kind", "") == "boss" and not e.dead), None)
        if boss is not None:
            w = 520
            x = surf.get_width() // 2 - w // 2
            put(surf, self.font, boss.name, (255, 200, 150), surf.get_width() // 2, surf.get_height() - 64,
                center=True)
            bar(surf, x, surf.get_height() - 42, w, 16, boss.hp / boss.max_hp, (200, 40, 50))
            put(surf, self.font, f"{math.ceil(boss.hp)} / {round(boss.max_hp)}", (255, 235, 235), surf.get_width() // 2,
                surf.get_height() - 42, center=True)
        mb = self.miniboss
        if mb is not None and not mb.dead:          # mini-boss name + health bar, top centre
            w = 360
            x = surf.get_width() // 2 - w // 2
            put(surf, self.font, mb.name, (255, 210, 170), surf.get_width() // 2, 22, center=True)
            bar(surf, x, 42, w, 12, mb.hp / mb.max_hp, (220, 120, 60))


# ======================================================================================================
# CONFIG FILES: config/monsters/<monster>.toml and config/characters/hero.toml set the numbers above.
# (src/balance.py reads them; tools/make_config_files.py writes them from these declarations.)
# ======================================================================================================
import balance as _balance                                  # noqa: E402  (src/ is on the path, see the top)

ROW = ("name", "hp", "speed", "damage", "color", "radius")
ROW_DOCS = {
    "name": "Name shown on its health bar.",
    "hp": "Health (the hero's sword does sword_damage + gear per hit, see hero.toml).",
    "speed": "Walking speed (pixels per second).",
    "damage": "Health the hero loses per hit (before armour).",
    "color": "Placeholder colour (only used if the sprite can't load): [red, green, blue].",
    "radius": "Hit circle (pixels). Bigger = easier to hit.",
}


def _monster(name, title, about, row, fields=None, docs=None):
    _balance.declare("monsters", name, title, about, globals(), fields, row, ROW, dict(ROW_DOCS, **(docs or {})))


_monster("goblin_minion", "GOBLIN MINION", "Goblin Dungeon regular: runs at the hero and stabs.", (GOBLIN_MOBS, "minion"))
_monster("goblin_shaman", "GOBLIN SHAMAN", "Goblin Dungeon regular: throws fireballs and shields its friends.",
         (GOBLIN_MOBS, "shaman"),
         {"barrier_shield": "BARRIER_SHIELD", "barrier_time": "BARRIER_TIME", "barrier_range": "BARRIER_RANGE",
          "barrier_cooldown": "BARRIER_COOLDOWN"},
         {"barrier_shield": "Damage its barrier soaks, per monster.", "barrier_time": "Seconds a barrier lasts.",
          "barrier_range": "Pixels around the shaman that the barrier reaches.",
          "barrier_cooldown": "Seconds between barriers."})
_monster("slime", "SLIME", "Goblin Dungeon regular (red, blue or green): bounces at the hero.", (GOBLIN_MOBS, "slime"))
_monster("wild_boar", "WILD BOAR", "Goblin Dungeon regular: a fast charger.", (GOBLIN_MOBS, "boar"))
_monster("goblin_war_boar", "GOBLIN WAR BOAR", "ELITE: guards the Goblin Dungeon's floor key.",
         (globals(), "GOBLIN_WAR_BOAR"))
_monster("goblin_general", "GENERAL GRUB", "MINI-BOSS of the Goblin Dungeon and the goblin caves.", (MINIBOSSES, 1))
_monster("orc_warrior", "ORC WARRIOR", "Berserker Dungeon regular: winds up its axe and slashes in front of it.",
         (BERSERKER_MOBS, "orc"),
         {"reach": "ORC_REACH", "slash_arc": "ORC_ARC", "cooldown": "ORC_COOLDOWN"},
         {"reach": "Pixels past its own hit circle that the axe reaches.",
          "slash_arc": "Degrees either side of its aim that the slash covers (step behind it to dodge).",
          "cooldown": "Seconds of rest after a slash."})
_monster("orc_shaman", "ORC SHAMAN", "Berserker Dungeon regular: keeps its distance and calls down meteors.",
         (BERSERKER_MOBS, "shaman"),
         {"meteor_cooldown": "METEOR_CD", "meteor_fall_time": "METEOR_FALL", "meteor_radius": "METEOR_R",
          "meteor_damage": "METEOR_DMG", "cast_range": "METEOR_RANGE"},
         {"meteor_cooldown": "Seconds between meteors.",
          "meteor_fall_time": "Seconds from the red warning circle to the impact (time to step out).",
          "meteor_radius": "Size of the impact circle (pixels).", "meteor_damage": "Health lost to a meteor.",
          "cast_range": "It casts when the hero is this close (pixels)."})
_monster("treant", "TREANT", "Berserker Dungeon regular: slow and tough; its roots hold the hero in place.",
         (BERSERKER_MOBS, "treant"),
         {"root_cooldown": "ROOT_CD", "root_range": "ROOT_RANGE", "root_delay": "ROOT_DELAY",
          "root_radius": "ROOT_R", "root_damage": "ROOT_DMG", "root_time": "ROOT_TIME"},
         {"root_cooldown": "Seconds between root attacks.", "root_range": "It roots when the hero is this close.",
          "root_delay": "Seconds from the green warning circle to the roots bursting out.",
          "root_radius": "Size of the root circle (pixels).", "root_damage": "Health lost when the roots grab.",
          "root_time": "Seconds the hero is held (can't walk or dash)."})
_monster("elder_treant", "ELDER TREANT", "ELITE: a bigger treant guarding the Berserker Dungeon's floor key. "
         "Its roots use the treant's numbers.", (globals(), "ELDER_TREANT"),
         {"size": "ELDER_SCALE"}, {"size": "How much bigger it is drawn than a treant."})
_monster("orc_warlord", "ORC WARLORD", "MINI-BOSS of the Berserker Dungeon and its minis: a bigger, recoloured orc.",
         (globals(), "ORC_WARLORD"),
         {"size": "WARLORD_SCALE", "reach": "WARLORD_REACH"},
         {"size": "How much bigger it is drawn than an orc warrior.",
          "reach": "Pixels past its hit circle that its axe reaches (a normal orc: see orc_warrior.toml)."})

_balance.declare(
    "characters", "hero", "THE HERO (every class)",
    "Numbers every class shares. Each class's own numbers are in warrior.toml, mage.toml and archer.toml.",
    globals(),
    {"sword_damage": "SWORD_DMG", "sword_reach": "SWORD_REACH", "heal_on_room_clear": "HEAL_ON_CLEAR",
     "potion_heal": "POTION_HEAL", "potion_max": "POTION_MAX", "potion_start": "POTION_START",
     "dash_time": "DASH_TIME", "dash_speed": "DASH_SPEED", "dash_cooldown": "DASH_COOLDOWN",
     "dash_invulnerable": "DASH_IFRAMES", "dash_effect": "DASH_EFFECT", "xp_per_health": "XP_PER_HEALTH",
     "bonus_scale": "BONUS_SCALE", "potion_heal_percent": "POTION_HEAL_PERCENT",
     "heal_on_clear_percent": "HEAL_ON_CLEAR_PERCENT",
     "dash_stamina": _balance.Prop(lambda: hero_classes.DASH_STAMINA,
                                   lambda v: setattr(hero_classes, "DASH_STAMINA", v))},
    docs={"sword_damage": "Base damage of every basic attack (a class's dmg_bonus and gear add to it).",
          "sword_reach": "How far the melee swing reaches (pixels).",
          "heal_on_room_clear": "Health back when a room is cleared.",
          "potion_heal": "Health a potion gives back (Mending Herbs add to it).",
          "potion_max": "Most potions the hero can carry.", "potion_start": "Potions a new hero starts with.",
          "dash_time": "Seconds a dash lasts.", "dash_speed": "Dash speed (pixels per second).",
          "dash_cooldown": "Seconds between dashes (Windstep Boots shorten it).",
          "dash_invulnerable": "Seconds the hero can't be hurt at the start of a dash.",
          "dash_stamina": "Stamina one dash costs.",
          "dash_effect": "true = afterimages and speed lines while dashing, false = off.",
          "xp_per_health": "Kill XP = the monster's max health x this (x its tier; elites x2, bosses x3).",
          "bonus_scale": "Every flat attack bonus (sword upgrades, levels, gear, Power, class) is multiplied by this.",
          "potion_heal_percent": "A potion also heals this % of max health.",
          "heal_on_clear_percent": "Clearing a room also heals this % of max health."})
