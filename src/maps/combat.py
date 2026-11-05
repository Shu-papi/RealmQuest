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
    The Goblin King uses his real sprite; bosses without art yet get a plain block."""
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
        return max(1, int(round(SWORD_DMG + self.dmg_bonus + self.class_dmg)))

    @property
    def attack_power(self):
        """Exact attack value (gear and Power add fractions) for the stats screen."""
        return SWORD_DMG + self.dmg_bonus + self.class_dmg

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
        self.heal(POTION_HEAL)
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
        if self.iframes > 0 or self.dash_inv > 0 or self.dead:
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
        if distance > self.radius + 22:
            step = self.speed * self.speed_k * dt / distance
            nx, ny = self.x + dx * step, self.y + dy * step
            if dungeon.can_stand(nx, ny):
                self.x, self.y = nx, ny
                self.walked(dt)
        elif self.attack_cd <= 0:
            if pc.hurt(self.damage, player, dungeon, self.x, self.y):
                self.attack_cd = 0.9
                self.noise("attack")

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
        step = self.speed * self.speed_k * dt / d
        if d > 230:                         # close in
            nx, ny = self.x + dx * step, self.y + dy * step
        elif d < 120:                       # back off
            nx, ny = self.x - dx * step, self.y - dy * step
        else:
            nx, ny = self.x, self.y
        if dungeon.can_stand(nx, ny):
            self.x, self.y = nx, ny
        if d < 330 and self.attack_cd <= 0 and not pc.dead:
            if self.barrier_cd <= 0 and any(e.shield <= 0 for e in self.barrier_targets()):
                self._start_cast("barrier")
            else:
                self._start_cast("fireball")


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
GOBLIN_EXTRAS = ("minion", "slime", "boar")       # the Goblin King's random "extra" summon
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
        self._boss_phase2()
        if any(getattr(e, "kind", "") == "boss" and e.dead for e in self.enemies):
            # the king has fallen: his minions scatter (gone, no XP)
            self.enemies = [e for e in self.enemies if not getattr(e, "summoned", False)]
            self.summon_spots = []
        for enemy in self.enemies:
            if enemy.dead:
                self.killed.append((enemy.x, enemy.y, enemy.max_hp, getattr(enemy, "kind", "normal")))
        self.enemies = [enemy for enemy in self.enemies if not enemy.dead]
        if self.enemies:
            return
        self.bolts.clear()

        room = self.active
        self.state[room] = "cleared"
        self.active = None
        self.d.lock_rect = None
        self.snd("room_clear")
        pc.heal(HEAL_ON_CLEAR)
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
            else:
                name, hp, speed, damage, color, radius = {
                    "minotaur": ("Minotaur", 48, 58, 7, (132, 82, 48), 24),
                    "lich": ("Lich King", 60, 48, 8, (132, 92, 190), 24),
                }[self.boss_kind]
                self.enemies = [Enemy(rect.centerx * TILE, rect.centery * TILE,
                                      name, hp, speed, damage, color, radius)]
                self.enemies[0].kind = "boss"
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
            if goblins:
                self.enemies = [self._goblin_mob(kind, x, y)
                                for kind, (x, y) in zip(self._goblin_roster(count), spots)]
            else:
                self.enemies = [Enemy(x, y, name, 8, 82, 2, color) for x, y in spots]
            if role == "guard":          # an elite holds the floor key
                if goblins:
                    elite = Enemy(cx * TILE, (cy - 3) * TILE, "Goblin War Boar", 14, 92, 3, color, 22)
                    elite.skin = "giant_boar"
                else:
                    elite = Enemy(cx * TILE, (cy - 3) * TILE, name + " Elite", 14, 78, 3,
                                  tuple(min(255, c + 50) for c in color), 17)
                elite.kind = "elite"
                self.enemies.append(elite)
            elif role in ("miniboss", "lair"):
                mname, hp, speed, dmg, mcol, rad = MINIBOSSES.get(dungeon_id, MINIBOSSES[3])
                self.miniboss = Enemy(cx * TILE, (cy - 2) * TILE, mname, hp, speed, dmg, mcol, rad)
                if goblins:
                    self.miniboss.skin = "goblin_general"
                self.miniboss.kind = "elite"
                self.enemies.append(self.miniboss)
                self.snd("roar")

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

    def _goblin_roster(self, count):
        """Which Goblin Dungeon monsters fill a room: a random mix of Goblin Minions, slimes,
        wild boars and Goblin Shamans (GOBLIN_ROSTER weights, at most MAX_SHAMANS shamans)."""
        kinds, weights = list(GOBLIN_ROSTER), list(GOBLIN_ROSTER.values())
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
        return e

    def player_swing(self, player, dx, dy, dmg=SWORD_DMG):
        if self.active is None:
            return
        for enemy in self.enemies:
            if enemy.dead:
                continue
            vx, vy = enemy.x - player.x, enemy.y - player.y
            distance = math.hypot(vx, vy) or 1.0
            facing = (vx * dx + vy * dy) / distance
            if distance <= SWORD_REACH + enemy.radius and facing >= 0.15:
                enemy.take_damage(dmg)

    def use_potion(self, player, pc):
        if pc.dead or pc.potions <= 0 or pc.hp >= pc.max_hp:
            return False
        return pc.drink()

    def retry_room(self):
        # Called after the player dies. Reset the room and return its index.
        room = self.active
        if room is None:
            return None
        self.enemies = []
        self.bolts.clear()
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
            put(surf, self.font, f"{int(boss.hp)} / {boss.max_hp}", (255, 235, 235), surf.get_width() // 2,
                surf.get_height() - 42, center=True)
        mb = self.miniboss
        if mb is not None and not mb.dead:          # mini-boss name + health bar, top centre
            w = 360
            x = surf.get_width() // 2 - w // 2
            put(surf, self.font, mb.name, (255, 210, 170), surf.get_width() // 2, 22, center=True)
            bar(surf, x, 42, w, 12, mb.hp / mb.max_hp, (220, 120, 60))