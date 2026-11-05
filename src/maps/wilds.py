"""
wilds.py - the dangerous country outside Oakwood: roaming packs, monster lairs and world events.

    Wilds(world, save, pc, sfx, on_xp)
        update(dt, active)          call every playing frame in the village
        player_swing(...)           sword hits (PlayerCombat.try_attack calls this)
        hostile_near(x, y, r)       anything dangerous close by (stops out-of-combat healing)
        draw_world / lights / draw_hud / draw_minimap

Packs roam around a home point and chase Himmel when he comes close. They grow
stronger the further they are from the village: slimes and goblin scouts near the
caves, bandits and wild boars across the river and at the forest's edge, shadow stalkers
and wraiths deep in the Deep Forest. A wiped-out pack returns after a while.

Slimes (red / blue / green) and wild boars wear the sprites from assets/monsters/mobs/
(see src/monsters/game_sprites.py); the others are still drawn as plain shapes.

Lairs keep sending out monsters while Himmel is near. Destroy one for XP and gold;
it is rebuilt a few minutes later.

World events now and then: a champion roams somewhere for a while, or a merchant
caravan on the Kingsroad is attacked and needs saving.

Monsters reuse combat.Enemy for hp, damage and drawing.
"""
from __future__ import annotations

import math
import random

import pygame

try:
    from .combat import Enemy, SWORD_REACH
    from .night_raid import _Ground, OVERWORLD_XP
except ImportError:
    from combat import Enemy, SWORD_REACH
    from night_raid import _Ground, OVERWORLD_XP

# name, hp, speed, damage, colour, radius, tier
MOBS = {
    "slime":   ("Slime", 6, 80, 2, (110, 190, 110), 13, 1),
    "goblin":  ("Goblin Scout", 8, 78, 2, (112, 150, 70), 13, 1),
    "bandit":  ("Bandit", 12, 82, 3, (156, 104, 82), 14, 2),
    "boar":    ("Wild Boar", 14, 88, 3, (124, 86, 56), 18, 2),
    "stalker": ("Shadow Stalker", 16, 92, 4, (96, 64, 140), 14, 3),
    "wraith":  ("Forest Wraith", 18, 70, 5, (150, 196, 206), 15, 3),
}
# kind, home, count, roam radius
PACKS = [
    ("slime", (720, 2240), 3, 150), ("slime", (1640, 2240), 3, 160), ("goblin", (250, 1820), 3, 120),
    ("goblin", (1400, 2230), 3, 130),
    ("bandit", (1650, 3010), 3, 150), ("bandit", (2950, 2640), 4, 160), ("bandit", (3450, 2960), 4, 160),
    ("boar", (3820, 2760), 3, 170), ("boar", (3150, 1320), 3, 150), ("boar", (3300, 1950), 3, 150),
    ("boar", (3560, 1640), 4, 150),
    ("stalker", (3700, 1120), 4, 140), ("stalker", (4020, 1420), 4, 140), ("stalker", (3900, 560), 4, 150),
    ("stalker", (3480, 480), 3, 150), ("wraith", (4160, 900), 3, 140), ("wraith", (4120, 2000), 3, 140),
]
# kind, position, name
LAIRS = [
    ("slime", (700, 2640), "Slime Den"), ("goblin", (1650, 2100), "Goblin Camp"),
    ("bandit", (3150, 2860), "Bandit Camp"), ("boar", (3380, 1250), "Boar Warren"),
    ("stalker", (3960, 1150), "Stalker Nest"), ("wraith", (4170, 1690), "Wraith Barrow"),
]
LAIR_RESPAWN = 240.0
PACK_RESPAWN = 90.0
# where world events can happen, by tier
EVENT_SPOTS = {1: [(900, 2060), (1800, 2250), (420, 1700)],
               2: [(2500, 2620), (3300, 2700), (3150, 1500), (1500, 2900)],
               3: [(3800, 900), (4000, 1500), (3600, 400)]}
CHAMPIONS = {1: ("Gloomgut the Great Slime", "slime"), 2: ("Black Tusk", "boar"), 3: ("The Hollow Widow", "stalker")}
# monsters that wear a sprite: kind -> skin keys (one is picked per monster)
SKINS = {"slime": ("slime_red", "slime_blue", "slime_green"), "boar": ("wild_boar",)}
CARAVAN_SPOT = (2075, 2180)


def reserve(big_circles):
    """Clearings for packs and lairs, so the trees leave them room."""
    for _k, (x, y), _n, r in PACKS:
        big_circles.append((x, y, 70))
    for _k, (x, y), _n in LAIRS:
        big_circles.append((x, y, 120))


class Mob(Enemy):
    def __init__(self, kind, x, y, home, roam, rng, scale=1.0):
        name, hp, speed, dmg, col, rad, tier = MOBS[kind]
        super().__init__(x, y, name, int(hp * scale), speed, dmg, col, rad)
        self.kind, self.tier = kind, tier
        self.home, self.roam = home, roam
        self.rng = rng
        self.target = None
        self.wait = rng.uniform(0.5, 3.0)
        self.aggro = False
        self.leash = 520
        if kind in SKINS:
            self.skin = rng.choice(SKINS[kind])

    def step(self, dt, player, ground, pc, wilds):
        if self.dead:
            return
        self.attack_cd = max(0.0, self.attack_cd - dt)
        self.hit_flash = max(0.0, self.hit_flash - dt)
        if self.cc_tick(dt):
            return
        self.face_x = 0
        dp = math.hypot(player.x - self.x, player.y - self.y)
        dh = math.hypot(self.x - self.home[0], self.y - self.home[1])
        if self.aggro and (dh > self.leash or pc.dead):
            self.aggro = False                               # give up and go home
            self.target = self.home
        elif not self.aggro and dp < (200 if self.tier == 1 else 240) and dh < self.leash - 60 and not pc.dead:
            self.aggro = True
        if self.aggro:
            self.face_x = 1 if player.x > self.x else -1
            if dp > self.radius + 22:
                self._move(player.x - self.x, player.y - self.y, dt, ground, 1.0)
            elif self.attack_cd <= 0 and pc.hurt(self.damage, player, ground, self.x, self.y):
                self.attack_cd = 0.9
                wilds.sfx.play("hurt")
            return
        if not self.aggro and self.hp < self.max_hp and dh < 40:
            self.hp = min(self.max_hp, self.hp + 4 * dt)       # licks its wounds at home
        if self.target is None:
            self.wait -= dt
            if self.wait <= 0:
                a, r = self.rng.random() * math.tau, self.rng.random() * self.roam
                self.target = (self.home[0] + math.cos(a) * r, self.home[1] + math.sin(a) * r * 0.7)
        else:
            tx, ty = self.target
            if math.hypot(tx - self.x, ty - self.y) < 8:
                self.target, self.wait = None, self.rng.uniform(1.5, 4.0)
            elif not self._move(tx - self.x, ty - self.y, dt, ground, 0.45):
                self.target, self.wait = None, self.rng.uniform(0.5, 2.0)

    def _move(self, dx, dy, dt, ground, k):
        d = math.hypot(dx, dy) or 1.0
        v = self.speed * self.speed_k * k * dt
        sx, sy = dx / d * v, dy / d * v
        moved = False
        if ground.can_stand(self.x + sx, self.y):
            self.x += sx
            moved = True
        if ground.can_stand(self.x, self.y + sy):
            self.y += sy
            moved = True
        return moved

    def draw(self, surf, cx, cy):
        super().draw(surf, cx, cy)
        if not self.dead and not self.skin:
            x, y = int(self.x - cx), int(self.y - cy - 14)
            eye = (255, 230, 120) if self.tier < 3 else (190, 240, 255)
            for ex in (-5, 5):
                surf.fill(eye, (x + ex - 1, y - 3, 3, 2))


class Pack:
    def __init__(self, kind, home, count, roam, rng):
        self.kind, self.home, self.count, self.roam = kind, home, count, roam
        self.rng = rng
        self.mobs: list[Mob] = []
        self.timer = 0.0
        self.spawn()

    def spawn(self):
        hx, hy = self.home
        self.mobs = [Mob(self.kind, hx + self.rng.uniform(-50, 50), hy + self.rng.uniform(-30, 30), self.home,
                         self.roam, self.rng) for _ in range(self.count)]
        self.timer = 0.0


class Lair:
    def __init__(self, kind, pos, name):
        self.kind, (self.x, self.y), self.name = kind, pos, name
        self.tier = MOBS[kind][6]
        self.max_hp = 30 * self.tier + 10
        self.hp = self.max_hp
        self.radius = 34
        self.alive = True
        self.timer = 0.0
        self.spawn_cd = 3.0
        self.spawned: list[Mob] = []
        self.flash = 0.0
        self.img = self._make(kind)

    @property
    def dead(self):
        return not self.alive

    @staticmethod
    def _make(kind):
        s = pygame.Surface((96, 84), pygame.SRCALPHA)
        hide = {"slime": (96, 150, 96), "goblin": (100, 120, 60), "bandit": (140, 90, 70), "boar": (110, 80, 54),
                "stalker": (60, 44, 80), "wraith": (90, 110, 120)}[kind]
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
        self.packs = [Pack(k, h, n, r, self.rng) for k, h, n, r in PACKS]
        self.lairs = [Lair(k, p, n) for k, p, n in LAIRS]
        self.floaters: list = []          # [x, y, text, life, colour]
        self.event = None                 # dict while a world event is running
        self.event_cd = 75.0
        self.result = None
        world.wilds = self

    # ---- queries ---------------------------------------------------------------
    def enemies(self):
        for p in self.packs:
            yield from (m for m in p.mobs if not m.dead)
        for lr in self.lairs:
            yield from (m for m in lr.spawned if not m.dead)
        ev = self.event
        if ev:
            yield from (m for m in ev["mobs"] if not m.dead)

    def hostile_near(self, x, y, r):
        return any(math.hypot(m.x - x, m.y - y) < r and getattr(m, "aggro", True) for m in self.enemies())

    def _kill(self, m, mult=1):
        xp = max(1, int(m.max_hp * getattr(m, "tier", 1) * mult * OVERWORLD_XP))
        self.on_xp(xp, m.x, m.y)

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
            for m in pack.mobs:
                if near or m.aggro:
                    m.step(dt, player, ground, pc, self)
            for m in pack.mobs:
                if m.dead and not getattr(m, "counted", False):
                    m.counted = True
                    self._kill(m)
            pack.mobs = [m for m in pack.mobs if not m.dead]
            if not pack.mobs:
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
                continue
            d = math.hypot(lr.x - px, lr.y - py)
            if d < 420:
                lr.spawn_cd -= dt
                alive = [m for m in lr.spawned if not m.dead]
                if lr.spawn_cd <= 0 and len(alive) < 4:
                    lr.spawn_cd = 7.0
                    m = Mob(lr.kind, lr.x + self.rng.uniform(-30, 30), lr.y + 40, (lr.x, lr.y + 40), 120, self.rng)
                    m.aggro = True
                    lr.spawned.append(m)
            for m in lr.spawned:
                m.step(dt, player, ground, pc, self)
                if m.dead and not getattr(m, "counted", False):
                    m.counted = True
                    self._kill(m)
            lr.spawned = [m for m in lr.spawned if not m.dead]
            if lr.hp <= 0 and lr.alive:
                lr.alive = False
                lr.timer = 0.0
                gold = 25 * lr.tier
                self.save.gold += gold
                self.on_xp(int(50 * lr.tier * OVERWORLD_XP), lr.x, lr.y - 30)
                self.floaters.append([lr.x, lr.y - 80, "+%d gold" % gold, 1.6, (255, 226, 130)])
                self.world.toast("%s destroyed!  +%d gold" % (lr.name, gold), (255, 214, 120))
                self.sfx.play("clear")
        self._update_event(dt, player, pc, ground)

    # ---- world events ---------------------------------------------------------------------
    def _tier_for_player(self):
        lv = self.save.level
        return 1 if lv < 5 else (2 if lv < 9 else 3)

    def _start_event(self):
        tier = self._tier_for_player()
        if self.rng.random() < 0.55:
            x, y = self.rng.choice(EVENT_SPOTS[tier])
            name, kind = CHAMPIONS[tier]
            m = Mob(kind, x, y, (x, y), 140, self.rng, scale=1.0)
            m.name, m.max_hp, m.hp = name, 30 * tier + 26, 30 * tier + 26
            m.radius, m.damage, m.speed = 20, 3 + tier, 84
            m.skin_scale = 1.4                       # champions are bigger
            m.color = tuple(min(255, int(c * 1.25)) for c in m.color)
            self.event = dict(kind="champion", x=x, y=y, mobs=[m], champion=m, time=150.0, tier=tier,
                              title="A champion prowls: %s" % name)
            self.world.toast("Merlin: I sense a champion out there... %s!" % name, (255, 200, 140))
        else:
            x, y = CARAVAN_SPOT
            kind = "slime" if tier == 1 else ("bandit" if tier == 2 else "stalker")
            mobs = []
            for i in range(4):
                a = i * math.tau / 4
                m = Mob(kind, x + math.cos(a) * 120, y + math.sin(a) * 70, (x, y), 60, self.rng)
                m.aggro = False
                mobs.append(m)
            self.event = dict(kind="caravan", x=x, y=y, mobs=mobs, cart_hp=60, time=150.0, tier=tier,
                              title="A merchant caravan is under attack on the Kingsroad!")
            self.world.toast("Merlin: A caravan on the Kingsroad, under attack! Hurry!", (255, 200, 140))
        self.sfx.play("roar")

    def _end_event(self, won, text):
        ev, self.event = self.event, None
        self.event_cd = self.rng.uniform(110, 170)
        col = (150, 230, 150) if won else (255, 170, 150)
        self.result = (text, col, 4.0)
        if won:
            tier = ev["tier"]
            gold = (40 if ev["kind"] == "champion" else 50) * tier
            self.save.gold += gold
            self.on_xp(int((60 if ev["kind"] == "champion" else 30) * tier * OVERWORLD_XP), ev["x"], ev["y"] - 40)
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
        ev["time"] -= dt
        for m in ev["mobs"]:
            if ev["kind"] == "caravan" and not m.aggro and not m.dead:
                # raiders claw at the cart unless Himmel gets in the way
                if math.hypot(player.x - m.x, player.y - m.y) < 200:
                    m.aggro = True
                else:
                    d = math.hypot(ev["x"] - m.x, ev["y"] - m.y)
                    if d > 46:
                        m._move(ev["x"] - m.x, ev["y"] - m.y, dt, ground, 0.8)
                    else:
                        m.attack_cd = max(0.0, m.attack_cd - dt)
                        if m.attack_cd <= 0:
                            m.attack_cd = 1.2
                            ev["cart_hp"] -= m.damage
                    continue
            m.step(dt, player, ground, pc, self)
        for m in ev["mobs"]:
            if m.dead and not getattr(m, "counted", False):
                m.counted = True
                self._kill(m, 2 if m is ev.get("champion") else 1)
        ev["mobs"] = [m for m in ev["mobs"] if not m.dead]
        if ev["kind"] == "caravan" and ev["cart_hp"] <= 0:
            self._end_event(False, "The caravan was lost...")
        elif not ev["mobs"]:
            self._end_event(True, "Champion slain!" if ev["kind"] == "champion" else "Caravan saved!  The merchant thanks you.")
        elif ev["time"] <= 0:
            self._end_event(False, "The champion slipped away." if ev["kind"] == "champion" else "The caravan was lost...")

    def player_swing(self, player, dx, dy, dmg):
        hit = False
        for m in list(self.enemies()) + [lr for lr in self.lairs if lr.alive]:
            vx, vy = m.x - player.x, m.y - player.y
            d = math.hypot(vx, vy) or 1.0
            if d <= SWORD_REACH + m.radius and (vx * dx + vy * dy) / d >= 0.15:
                m.take_damage(dmg)
                if isinstance(m, Mob):
                    m.aggro = True
                hit = True
        if hit:
            self.sfx.play("hit")
        return hit

    def calm(self):
        """After Himmel falls: everything goes home."""
        for m in self.enemies():
            if isinstance(m, Mob):
                m.aggro = False
                m.target = m.home

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
        mobs = [m for m in self.enemies() if view.collidepoint(m.x, m.y)]
        for m in sorted(mobs, key=lambda m: m.y):
            m.draw(scr, cx, cy)
            if ev and m is ev.get("champion"):
                img = pygame.font.Font(None, 22).render(m.name, True, (255, 210, 140))
                scr.blit(img, (int(m.x - cx) - img.get_width() // 2, int(m.y - cy) - 60))
        if self.floaters:
            font = pygame.font.Font(None, 26)
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
