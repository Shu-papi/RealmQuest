"""
combat.py - MAP-ONLY VERSION

All placeholder monsters, bosses, projectiles and their sprites have been removed.
What remains is the contract the map (game file) depends on, so teammates can plug in
their own monsters/bosses by filling in the `Encounters` class.

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
import random

import pygame

TILE = 24
MAP_W, MAP_H = 288, 162
FLOOR, LIQUID, PATH = 1, 2, 5
WALK = (FLOOR, PATH)
OPEN = (FLOOR, LIQUID, PATH)

# ---- player tuning --------------------------------------------------------
PLAYER_MAX_HP = 40
SWORD_DMG = 2
SWORD_REACH = 90
SWORD_COOLDOWN = 0.32
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
def sprite(kind, flip=False):
    """Placeholder so the map file's import (and dialog portraits) still work.
    Teammates: return your own monster/boss sprite for `kind` here."""
    s = pygame.Surface((32, 32), pygame.SRCALPHA)
    s.fill((200, 0, 200, 255))
    return s


# ---- player combat (kept: the map's Player uses dash, hp, sword) ----------
class PlayerCombat:
    def __init__(self):
        self.max_hp = PLAYER_MAX_HP
        self.potions = POTION_START
        self.dmg_bonus = 0          # permanent sword upgrade (boss rewards)
        self.reset()

    @property
    def sword_dmg(self):
        return SWORD_DMG + self.dmg_bonus

    def reset(self):
        self.hp = self.max_hp
        self.iframes = 0.0
        self.cd = 0.0
        self.swing = 0.0
        self.swing_dir = (0.0, 1.0)
        self.dead = False
        self.dash_cd = 0.0
        self.dash_inv = 0.0

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

    def try_dash(self, player, dx, dy):
        if self.dead or self.dash_cd > 0 or player.dash_t > 0:
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

    def try_attack(self, player, enc, aim=None):
        if self.cd > 0 or self.dead:
            return
        dx, dy = aim if aim else player.face
        l = math.hypot(dx, dy)
        if l < 1e-6:
            dx, dy, l = 0.0, 1.0, 1.0
        dx, dy = dx / l, dy / l
        self.cd = SWORD_COOLDOWN
        self.swing = SWING_TIME
        self.swing_dir = (dx, dy)
        if abs(dx) > abs(dy):
            player.dir = "right" if dx > 0 else "left"
        else:
            player.dir = "down" if dy > 0 else "up"
        enc.player_swing(player, dx, dy, self.sword_dmg)

    def draw_slash(self, surf, player, cx, cy):
        if self.swing <= 0:
            return
        k = self.swing / SWING_TIME
        dx, dy = self.swing_dir
        ang = math.atan2(dy, dx)
        spread, r_out, r_in = 1.05, 58, 26
        end = ang - spread + 2 * spread * min(1.0, (1 - k) * 1.6 + 0.2)
        n = 10
        outer, inner = [], []
        for i in range(n + 1):
            a = ang - spread + (end - (ang - spread)) * i / n
            outer.append((70 + math.cos(a) * r_out, 70 + math.sin(a) * r_out))
            inner.append((70 + math.cos(a) * r_in, 70 + math.sin(a) * r_in))
        layer = blank(140, 140)
        pygame.draw.polygon(layer, (230, 240, 255, int(190 * k)), outer + inner[::-1])
        pygame.draw.lines(layer, (255, 255, 255, int(255 * k)), False, outer, 2)
        px = int(player.x - cx) - 70
        py = int(player.y - cy) - 14 - 70
        surf.blit(layer, (px, py))


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

    @property
    def dead(self):
        return self.hp <= 0

    def update(self, dt, player, dungeon, pc):
        if self.dead:
            return
        self.attack_cd = max(0.0, self.attack_cd - dt)
        self.hit_flash = max(0.0, self.hit_flash - dt)
        dx, dy = player.x - self.x, player.y - self.y
        distance = math.hypot(dx, dy) or 1.0
        if distance > self.radius + 22:
            step = self.speed * dt / distance
            nx, ny = self.x + dx * step, self.y + dy * step
            if dungeon.can_stand(nx, ny):
                self.x, self.y = nx, ny
        elif self.attack_cd <= 0:
            if pc.hurt(self.damage, player, dungeon, self.x, self.y):
                self.attack_cd = 0.9

    def take_damage(self, amount):
        if self.dead:
            return
        self.hp = max(0, self.hp - amount)
        self.hit_flash = 0.12

    def draw(self, surf, cx, cy):
        if self.dead:
            return
        x, y = int(self.x - cx), int(self.y - cy - 14)
        color = (255, 245, 220) if self.hit_flash else self.color
        pygame.draw.ellipse(surf, (18, 12, 18), (x - self.radius, y + self.radius - 3,
                                                  self.radius * 2, 10))
        pygame.draw.circle(surf, color, (x, y), self.radius)
        pygame.draw.circle(surf, (20, 16, 24), (x - 5, y - 2), 2)
        pygame.draw.circle(surf, (20, 16, 24), (x + 5, y - 2), 2)
        bar(surf, x - self.radius, y - self.radius - 8, self.radius * 2, 4,
            self.hp / self.max_hp, (210, 54, 60), (45, 18, 24))


# rooms with no monsters (they start "safe" and never lock)
SAFE_ROLES = {"start", "shrine", "trap", "stairs", "antechamber"}

# placeholder mini-bosses: name, hp, speed, damage, color, radius
MINIBOSSES = {
    1: ("Grub the Warchief", 22, 76, 4, (92, 124, 52), 19),
    2: ("Bloodhowl Captain", 30, 70, 5, (190, 64, 44), 21),
    3: ("Bone Warden", 36, 60, 6, (176, 168, 204), 21),
}


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
        for enemy in self.enemies:
            if enemy.dead:
                self.killed.append((enemy.x, enemy.y, enemy.max_hp, getattr(enemy, "kind", "normal")))
        self.enemies = [enemy for enemy in self.enemies if not enemy.dead]
        if self.enemies:
            return

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
            name, hp, speed, damage, color, radius = {
                "goblin_king": ("Valdur, Goblin King", 34, 72, 5, (126, 62, 52), 20),
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
            points = ((-2, -1), (2, 1), (0, 3), (-3, 2), (3, -2))
            cx, cy = rect.centerx, rect.centery
            if not self.roles:
                count = 2 + room % 2
            else:
                count = {"guard": 4, "seal": 3, "miniboss": 2, "vault": self.rng.randint(2, 3)}.get(
                    role, self.rng.randint(2, 4))
            self.enemies = [Enemy((cx + ox) * TILE, (cy + oy) * TILE, name, 8, 82, 2, color)
                            for ox, oy in points[:count]]
            if role == "guard":          # an elite holds the floor key
                self.enemies.append(Enemy(cx * TILE, (cy - 3) * TILE, name + " Elite", 14, 78, 3,
                                          tuple(min(255, c + 50) for c in color), 17))
                self.enemies[-1].kind = "elite"
            elif role in ("miniboss", "lair"):
                mname, hp, speed, dmg, mcol, rad = MINIBOSSES.get(dungeon_id, MINIBOSSES[3])
                self.miniboss = Enemy(cx * TILE, (cy - 2) * TILE, mname, hp, speed, dmg, mcol, rad)
                self.miniboss.kind = "elite"
                self.enemies.append(self.miniboss)
                self.snd("roar")

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
        self.active = None
        self.d.lock_rect = None
        self.state[room] = "pending"
        self.miniboss = None
        self.exit_ready = self._exit_ready()
        return room

    def draw(self, surf, cx, cy, t, player, pc):
        # monsters/projectiles/etc. go here; the sword slash is kept so attacks show
        for enemy in self.enemies:
            enemy.draw(surf, cx, cy)
        pc.draw_slash(surf, player, cx, cy)

    def draw_hud(self, surf, cx, cy, pc, t):
        bar(surf, 16, 82, 290, 16, pc.hp / pc.max_hp, (214, 56, 64))
        put(surf, self.font, f"HP {pc.hp}/{pc.max_hp}", (255, 235, 235), 24, 83)
        put(surf, self.font, f"Potions: {pc.potions}   (H: drink)", (255, 225, 230), 16, 106)
        mb = self.miniboss
        if mb is not None and not mb.dead:          # mini-boss name + health bar, top centre
            w = 360
            x = surf.get_width() // 2 - w // 2
            put(surf, self.font, mb.name, (255, 210, 170), surf.get_width() // 2, 22, center=True)
            bar(surf, x, 42, w, 12, mb.hp / mb.max_hp, (220, 120, 60))