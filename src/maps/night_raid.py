"""
night_raid.py - Oakwood at night: atmosphere and the playable night raids.

    Night(world, save, pc, sfx, on_event)
        update(dt, can_start)      call every playing frame in the village
        player_swing(...)          called by PlayerCombat.try_attack during a raid
        lights(t)                  extra light sources (ward, monster eyes)
        draw_world(scr, cx, cy, t) monsters + sword slash (before night lighting)
        draw_glow(scr, cx, cy, t)  ward dome and watching eyes (after lighting)
        draw_hud(scr)              raid banner, ward bar, monsters left

Every night the anchors' creatures come for Oakwood. Merlin's ward covers the
plaza; monsters walk down the road from the dungeon you are working on and
claw at the ward. Himmel meets them with the sword. Raids from a dungeon stop
once its anchor is shattered, so when all three are gone the nights are quiet.

Monsters reuse combat.Enemy (hp, damage, drawing); only how they move differs.
"""
from __future__ import annotations

import math
import random

import pygame

try:
    from .combat import Enemy, SWORD_REACH
except ImportError:
    from combat import Enemy, SWORD_REACH

WARD_CENTER = (1400, 1640)
WARD_R = 150
WARD_MAX = 100
HOME_RANGE = 1100              # a raid only plays out if Himmel is this close to the plaza at nightfall
OVERWORLD_XP = 0.5             # overworld XP is kept small: caves and dungeons are where you level

# road waypoints from each dungeon's portal down to the plaza
PATHS = {
    "goblin":    [(790, 1085), (800, 1110), (900, 1140), (1060, 1190), (1250, 1260), (1408, 1380), (1400, 1560)],
    "berserker": [(2060, 985), (2045, 1010), (1850, 1020), (1600, 1075), (1385, 1150), (1408, 1380), (1400, 1560)],
    "lich":      [(1400, 400), (1400, 430), (1398, 600), (1415, 860), (1385, 1150), (1408, 1380), (1400, 1560)],
}
ROAD_NAME = {"goblin": "west road", "berserker": "east road", "lich": "north road"}
# name, hp, speed, damage, colour, radius
MONSTERS = {
    "goblin":    ("Goblin Raider", 6, 72, 2, (112, 150, 70), 13),
    "berserker": ("Berserker", 9, 80, 3, (174, 76, 52), 15),
    "lich":      ("Deadling", 11, 62, 3, (112, 86, 164), 14),
}
ORDER = ("goblin", "berserker", "lich")


class _Ground:
    """Lets combat code (Enemy, PlayerCombat.hurt) ask 'can I stand here?' in the overworld."""

    def __init__(self, world):
        self.world = world

    def can_stand(self, x, y):
        r = pygame.Rect(int(x) - 7, int(y) - 4, 14, 8)
        W, H = self.world.ground.get_size()
        return 30 < x < W - 30 and 50 < y < H - 10 and r.collidelist(self.world.colliders) == -1


class RaidMonster(Enemy):
    def __init__(self, sid, path, rng):
        name, hp, speed, dmg, col, rad = MONSTERS[sid]
        x, y = path[0]
        super().__init__(x + rng.uniform(-30, 30), y + rng.uniform(-20, 20), name, hp, speed * rng.uniform(0.9, 1.1),
                         dmg, col, rad)
        self.path = path
        self.idx = 1
        self.claw = rng.uniform(0.2, 1.0)
        self.off = (rng.uniform(-28, 28), rng.uniform(-14, 14))

    def step(self, dt, player, ground, pc, night):
        if self.dead:
            return
        self.attack_cd = max(0.0, self.attack_cd - dt)
        self.hit_flash = max(0.0, self.hit_flash - dt)
        dp = math.hypot(player.x - self.x, player.y - self.y)
        if dp < 220 and not pc.dead:                     # chase Himmel
            if dp > self.radius + 22:
                self._move(player.x - self.x, player.y - self.y, dt, ground)
            elif self.attack_cd <= 0 and pc.hurt(self.damage, player, ground, self.x, self.y):
                self.attack_cd = 0.9
                night.sfx.play("hurt")
            return
        wx, wy = WARD_CENTER
        if math.hypot(self.x - wx, self.y - wy) < WARD_R - 20:    # at the ward: claw at it
            self.claw -= dt
            if self.claw <= 0:
                self.claw = 1.2
                night.hit_ward(self.damage * 2, self.x, self.y)
            return
        tx, ty = self.path[min(self.idx, len(self.path) - 1)]
        tx, ty = tx + self.off[0], ty + self.off[1]
        if math.hypot(tx - self.x, ty - self.y) < 14 and self.idx < len(self.path) - 1:
            self.idx += 1
        self._move(tx - self.x, ty - self.y, dt, None if self.idx < len(self.path) else ground)

    def _move(self, dx, dy, dt, ground):
        d = math.hypot(dx, dy) or 1.0
        sx, sy = dx / d * self.speed * dt, dy / d * self.speed * dt
        if ground is None:                 # on the road: just walk
            self.x += sx
            self.y += sy
            return
        if ground.can_stand(self.x + sx, self.y):
            self.x += sx
        if ground.can_stand(self.x, self.y + sy):
            self.y += sy

    def draw(self, surf, cx, cy):
        super().draw(surf, cx, cy)
        if not self.dead:      # glowing eyes, so they read at night
            x, y = int(self.x - cx), int(self.y - cy - 14)
            for ex in (-5, 5):
                surf.fill((255, 70, 50), (x + ex - 1, y - 3, 3, 2))


def _eye_spots(world, rng):
    """Places at the dark edges of the woods where eyes watch the village at night."""
    out = []
    for _ in range(400):
        if len(out) >= 70:
            break
        W, H = world.ground.get_size()
        x, y = rng.uniform(120, W - 120), rng.uniform(140, H - 60)
        if math.hypot(x - WARD_CENTER[0], y - WARD_CENTER[1]) < 620:
            continue
        cell = (int(x) // 32, int(y) // 32)
        if cell in world.road_cells:
            continue
        out.append((x, y, rng.random() * 10, rng.uniform(2.5, 6.0)))
    return out


def make_barricade():
    """Sharpened stakes lashed together."""
    s = pygame.Surface((70, 46), pygame.SRCALPHA)
    pygame.draw.ellipse(s, (0, 0, 0, 70), (2, 36, 66, 10))
    for i, x in enumerate(range(4, 66, 9)):
        h = 30 + (i % 2) * 6
        pygame.draw.polygon(s, (110, 76, 44), [(x, 42), (x + 7, 42), (x + 7, 42 - h + 6), (x + 3, 42 - h), (x, 42 - h + 6)])
        pygame.draw.line(s, (150, 110, 66), (x + 1, 41), (x + 1, 42 - h + 7), 1)
        pygame.draw.polygon(s, (40, 28, 20), [(x, 42), (x + 7, 42), (x + 7, 42 - h + 6), (x + 3, 42 - h), (x, 42 - h + 6)], 1)
    for y in (22, 32):
        pygame.draw.line(s, (90, 64, 40), (2, y), (68, y + 2), 3)
    return s


class Night:
    def __init__(self, world, save, pc, sfx, on_event=None):
        self.world, self.save, self.pc, self.sfx = world, save, pc, sfx
        self.on_event = on_event or (lambda *a: None)
        self.on_xp = lambda *a: None             # set by the Game: on_xp(amount, x, y)
        self.ground = _Ground(world)
        self.rng = random.Random()
        self.eyes = _eye_spots(world, random.Random(7))
        self.active = False
        self.source = None
        self.monsters: list[RaidMonster] = []
        self.to_spawn: list[float] = []      # spawn timers for the current wave
        self.waves_left = 0
        self.ward = WARD_MAX
        self.ward_flash = 0.0
        self.banner_t = 0.0
        self.flash = 0.0                     # Merlin's blast when a raid is lost
        self.prev_phase = world.daynight.phase
        self.roar_cd = 30.0
        self.result = None                   # (text, colour, time left) shown after a raid
        world.night = self
        self._add_defences()

    # ---- set dressing ------------------------------------------------------------
    def _add_defences(self):
        """Barricades and torches where the roads come down into the plaza."""
        try:
            from .surface_world import Prop, Torch
        except ImportError:
            from surface_world import Prop, Torch
        img = make_barricade()
        w = self.world
        for x, y in ((1316, 1012), (1484, 1012)):
            w.props.append(Prop(img, x, y, foot=4))
            w.props[-1]._kind = "barricade"
            w.props.append(Torch(x + (-46 if x < 1400 else 46), y + 2))

    # ---- queries -------------------------------------------------------------------
    def current_source(self):
        cleared = self.save.cleared
        return next((sid for sid in ORDER if sid not in cleared), None)

    @property
    def night_level(self):
        return self.world.daynight.night()

    # ---- raid flow -----------------------------------------------------------------
    def start_raid(self):
        sid = self.current_source()
        if sid is None:
            return False
        self.active, self.source = True, sid
        stage = self.save.stage
        self.waves_left = 2 + (1 if stage >= 1 else 0)
        self.ward = WARD_MAX
        self.monsters.clear()
        self._next_wave()
        self.banner_t = 4.0
        self.sfx.play("roar")
        self.world.toast("The horn! Monsters on the %s! Defend Oakwood!" % ROAD_NAME[sid], (255, 150, 120))
        self.on_event("raid_start")
        return True

    def _next_wave(self):
        self.waves_left -= 1
        n = 3 + self.save.stage + self.rng.randint(0, 1)
        self.to_spawn = [i * 0.8 for i in range(n)]

    def hit_ward(self, dmg, x, y):
        self.ward = max(0, self.ward - dmg)
        self.ward_flash = 0.25
        self.sfx.play("hit")
        if self.ward <= 0 and self.active:
            self.end_raid(False)

    def abort(self):
        """Leaving the village mid-raid (should not happen in play: portals are closed)."""
        self.active = False
        self.monsters.clear()
        self.to_spawn = []

    def end_raid(self, won):
        self.active = False
        self.monsters.clear()
        self.to_spawn = []
        if won:
            gold = 20 + 10 * self.save.stage
            self.save.gold += gold
            self.save.raids += 1
            self.on_xp(int(30 * (self.save.stage + 1) * OVERWORLD_XP), WARD_CENTER[0], WARD_CENTER[1] - 60)
            self.result = ("Oakwood holds!  +%d gold" % gold, (150, 230, 150), 4.0)
            self.sfx.play("victory")
            self.on_event("raid_won")
        else:
            lost = min(15, self.save.gold)
            self.save.gold -= lost
            self.flash = 0.6
            self.result = ("Merlin drives them off...  -%d gold" % lost if lost else "Merlin drives them off...",
                           (255, 170, 150), 4.0)
            self.sfx.play("roar")
            p = self.world.player
            p.x, p.y = WARD_CENTER[0] - 40, WARD_CENTER[1] + 60
            self.pc.reset()
            self.on_event("raid_lost")

    # ---- per frame ------------------------------------------------------------------
    def update(self, dt, can_start):
        dn = self.world.daynight
        phase = dn.phase
        crossed = self.prev_phase < 0.70 <= phase
        self.prev_phase = phase
        self.ward_flash = max(0.0, self.ward_flash - dt)
        self.flash = max(0.0, self.flash - dt)
        self.banner_t = max(0.0, self.banner_t - dt)
        if self.result:
            text, col, left = self.result
            self.result = (text, col, left - dt) if left - dt > 0 else None
        if not self.active:
            if crossed and can_start and self.current_source():
                p = self.world.player
                if math.hypot(p.x - WARD_CENTER[0], p.y - WARD_CENTER[1]) < HOME_RANGE:
                    self.start_raid()
                else:
                    self.world.toast("Distant horns... Captain Hale's watch holds Oakwood tonight.", (200, 200, 230))
            elif self.night_level > 0.6 and self.current_source():
                self.roar_cd -= dt
                if self.roar_cd <= 0:                     # something howls in the woods
                    self.roar_cd = self.rng.uniform(35, 70)
                    self.sfx.play("roar")
            return
        pc, player = self.pc, self.world.player
        path = PATHS[self.source]
        for i in range(len(self.to_spawn)):
            self.to_spawn[i] -= dt
        while self.to_spawn and self.to_spawn[0] <= 0:
            self.to_spawn.pop(0)
            self.monsters.append(RaidMonster(self.source, path, self.rng))
        for m in self.monsters:
            m.step(dt, player, self.ground, pc, self)
        if not self.active:          # the ward broke this frame
            return
        tier = ORDER.index(self.source) + 1
        for m in self.monsters:
            if m.dead:
                self.on_xp(max(1, int(m.max_hp * tier * OVERWORLD_XP)), m.x, m.y)
        self.monsters = [m for m in self.monsters if not m.dead]
        if pc.dead:
            self.end_raid(False)
            return
        if not self.monsters and not self.to_spawn:
            if self.waves_left > 0:
                self._next_wave()
                self.world.toast("Another wave!", (255, 190, 150))
            else:
                self.end_raid(True)
                return
        if 0.08 < phase < 0.6:       # daylight: the rest flee back down the road
            self.end_raid(True)

    def player_swing(self, player, dx, dy, dmg):
        hit = False
        for m in self.monsters:
            if m.dead:
                continue
            vx, vy = m.x - player.x, m.y - player.y
            d = math.hypot(vx, vy) or 1.0
            if d <= SWORD_REACH + m.radius and (vx * dx + vy * dy) / d >= 0.15:
                m.take_damage(dmg)
                hit = True
        if hit:
            self.sfx.play("hit")

    # ---- drawing ----------------------------------------------------------------------
    def lights(self, t):
        out = []
        n = self.night_level
        if n > 0.2 and self.current_source():
            r = int(round((170 + 30 * math.sin(t * 2)) / 10) * 10)
            out.append((WARD_CENTER[0], WARD_CENTER[1] - 20, r, (60, 90, 150)))
        for m in self.monsters:
            out.append((int(m.x), int(m.y) - 14, 50, (140, 40, 30)))
        return out

    def draw_world(self, scr, cx, cy, t):
        for m in sorted(self.monsters, key=lambda m: m.y):
            m.draw(scr, cx, cy)
        self.pc.draw_slash(scr, self.world.player, cx, cy)

    def draw_glow(self, scr, cx, cy, t):
        n = self.night_level
        if n < 0.15 and not self.active:
            return
        # Merlin's ward: a ring of runes over the plaza (only while the anchors still stand)
        if self.current_source() or self.active:
            k = min(1.0, n * 1.2) * (0.6 + 0.4 * self.ward / WARD_MAX)
            if self.ward_flash > 0:
                k = 1.0
            col = (int(110 * k), int(160 * k), int(255 * k))
            x, y = WARD_CENTER[0] - cx, WARD_CENTER[1] - cy
            rect = pygame.Rect(x - WARD_R, y - WARD_R * 0.55, WARD_R * 2, WARD_R * 1.1)
            pygame.draw.ellipse(scr, col, rect, 2)
            for i in range(12):
                a = t * 0.4 + i * math.tau / 12
                rx, ry = x + math.cos(a) * WARD_R, y + math.sin(a) * WARD_R * 0.55
                scr.fill(col, (int(rx) - 2, int(ry) - 2, 4, 4))
                scr.fill(col, (int(rx) - 1, int(ry) - 14 - int(6 * math.sin(t * 3 + i)), 2, 2))
        # eyes in the dark woods
        if n > 0.55 and self.current_source():
            for ex, ey, ph, period in self.eyes:
                sx, sy = int(ex - cx), int(ey - cy)
                if not (-10 < sx < scr.get_width() + 10 and -10 < sy < scr.get_height() + 10):
                    continue
                c = (t + ph) % period
                if c < 0.15 or c > period - 0.6:       # blink, then look away for a moment
                    continue
                scr.fill((255, 60, 40), (sx - 4, sy, 3, 2))
                scr.fill((255, 60, 40), (sx + 2, sy, 3, 2))
        if self.flash > 0:
            v = pygame.Surface(scr.get_size())
            v.fill((200, 220, 255))
            v.set_alpha(int(255 * min(1.0, self.flash / 0.4)))
            scr.blit(v, (0, 0))

    def draw_hud(self, scr, font, big_font):
        W, H = scr.get_size()
        y0 = H - 168
        if self.active:
            alive = len(self.monsters) + len(self.to_spawn)
            title = "NIGHT RAID - %s" % ROAD_NAME[self.source].upper()
            img = big_font.render(title, True, (255, 170, 140))
            box = pygame.Rect(W // 2 - 280, y0, 560, 96)
            panel = pygame.Surface(box.size, pygame.SRCALPHA)
            pygame.draw.rect(panel, (20, 10, 14, 210), panel.get_rect(), border_radius=10)
            pygame.draw.rect(panel, (200, 90, 80, 255), panel.get_rect(), 2, border_radius=10)
            scr.blit(panel, box)
            scr.blit(img, (W // 2 - img.get_width() // 2, y0 + 6))
            bw = 320
            bx = W // 2 - bw // 2
            pygame.draw.rect(scr, (0, 0, 0), (bx - 2, y0 + 44, bw + 4, 16))
            pygame.draw.rect(scr, (30, 40, 70), (bx, y0 + 46, bw, 12))
            col = (255, 255, 255) if self.ward_flash > 0 else (110, 160, 255)
            pygame.draw.rect(scr, col, (bx, y0 + 46, int(bw * self.ward / WARD_MAX), 12))
            lab = font.render("Merlin's ward      monsters left: %d      waves left: %d      Space: strike" %
                              (alive, self.waves_left), True, (220, 226, 240))
            scr.blit(lab, (W // 2 - lab.get_width() // 2, y0 + 66))
        if self.result:
            text, col, left = self.result
            img = big_font.render(text, True, col)
            sh = big_font.render(text, True, (0, 0, 0))
            a = int(255 * min(1.0, left / 0.6))
            img.set_alpha(a)
            sh.set_alpha(a)
            scr.blit(sh, (W // 2 - img.get_width() // 2 + 2, y0 + 42))
            scr.blit(img, (W // 2 - img.get_width() // 2, y0 + 40))
