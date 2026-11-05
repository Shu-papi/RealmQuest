#!/usr/bin/env python3
"""
mobs.py - RealmQuest pixel-art mobs: sprite loading, animation, simple AI and a test run.

Run from the repo root:
    python -m pip install pygame-ce
    python src/monsters/mobs.py            # watch the mobs (auto-wandering, or drive one by hand)
    python src/monsters/mobs.py --test     # headless self-test, screenshots go to test_output/mobs/

Mobs:   Red / Blue / Green Slime, Wild Boar, Goblin Shaman
States: idle, walk, attack  (Goblin Shaman has two attacks: "barrier" and "fireball")

Sprite-sheet format (every PNG in assets/monsters/mobs/):
    1024 x 1024, transparent, ONE row of 4 frames, each frame 256 x 256,
    the row sits at y = 384.

Using the classes in your own game:
    from monsters.mobs import SpriteLibrary, Mob     # with src/ on the import path
    lib   = SpriteLibrary(pixel=6)                   # after pygame.display.set_mode()
    mob   = Mob("wild_boar", lib, x=400)
    mob.move(+1)                                     # walk right   (0 = idle)
    mob.attack(0)                                    # play attack  (shaman: 0 barrier, 1 fireball)
    events = mob.update(dt, bounds=(100, 1100))      # [("hit", "attack"), ("end", "attack")]
    mob.draw(screen, feet_y=650)

`pixel` = on-screen size of ONE art pixel (3, 6, 9, 12 are all exact). Every mob and every
animation is rescaled to that same pixel size, so a slime is always smaller than the shaman
even though the sheets were exported at different zoom levels.
"""
from __future__ import annotations

import argparse
import math
import os
import random
import sys
from dataclasses import dataclass

import pygame

# --------------------------------------------------------------------------- sheet layout
SHEET_SIZE = 1024
CELL = 256            # one frame is 256 x 256
ROW_Y = 384           # the single row of frames starts at y = 384
FRAMES = 4

HERE = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(os.path.dirname(HERE))
DEFAULT_ASSETS = os.path.join(REPO_ROOT, "assets", "monsters", "mobs")
DEFAULT_TEST_OUT = os.path.join(REPO_ROOT, "test_output", "mobs")

WIN_W, WIN_H = 1280, 720
FEET_Y = 650          # where mobs stand on screen

MOB_KEYS = ["slime_red", "slime_blue", "slime_green", "wild_boar", "goblin_shaman"]


# --------------------------------------------------------------------------- mob data
@dataclass(frozen=True)
class MobMeta:
    label: str
    speed: float                 # walk speed in px/s at pixel=6
    shadow: int                  # shadow width in px at pixel=6
    height: int                  # body height in px at pixel=6 (labels / markers)
    attacks: tuple               # attack clip names, primary first
    popups: tuple                # floating text shown on the "hit" frame


META = {
    "slime_red":     MobMeta("Red Slime",     70, 100, 90,  ("attack",), ("SLAM!",)),
    "slime_blue":    MobMeta("Blue Slime",    70, 100, 90,  ("attack",), ("SLAM!",)),
    "slime_green":   MobMeta("Green Slime",   70, 100, 90,  ("attack",), ("SLAM!",)),
    "wild_boar":     MobMeta("Wild Boar",    150, 190, 150, ("attack",), ("CHARGE!",)),
    "goblin_shaman": MobMeta("Goblin Shaman", 85, 110, 215, ("barrier", "fireball"), ("BARRIER!", "FIREBALL!")),
}


def clip_specs(key):
    """Everything the player needs to know about each sheet of a mob.

    px       : zoom the sheet was exported at (screen px per art pixel)
    baseline : y inside the 256px cell where the feet touch the floor
    anchor   : x inside the cell of the body centre (so the mob stays planted when sheets change)
    hit_frame: frame index where the attack 'lands' (use it for damage / spawning projectiles)
    root     : px the mob has travelled (inside the sheet) by the end of the attack
    """
    sh = key == "goblin_shaman"
    slime = key.startswith("slime")
    specs = {
        "idle": dict(file=f"idle/idle_{key}.png", loop=True, baseline=248, px=12 if slime else 6,
                     anchor=110 if sh else 128, ms=[220, 220, 220, 220]),
        "walk": dict(file=f"walk/walk_{key}.png", loop=True, baseline=242 if sh else 248, px=12 if slime else 6,
                     anchor=110 if sh else 128,
                     ms=[110, 110, 110, 110] if key == "wild_boar" else
                        [150, 110, 110, 110] if key.startswith("slime") else [140, 140, 140, 140]),
    }
    if key.startswith("slime"):
        specs["attack"] = dict(file=f"attack/attack_{key}.png", loop=False, baseline=240, anchor=76, px=8,
                               ms=[180, 120, 110, 220], hit_frame=2, root=104)
    elif key == "wild_boar":
        specs["attack"] = dict(file="attack/attack_wild_boar.png", loop=False, baseline=240, anchor=88, px=4,
                               ms=[240, 100, 100, 240], hit_frame=3, root=76)
    else:
        specs["barrier"] = dict(file="attack/attack_goblin_shaman_barrier.png", loop=False, baseline=236,
                                anchor=116, px=4, ms=[180, 150, 150, 380], hit_frame=2, root=0)
        # the cast sheet = the fireball sheet without the painted fireball (tools/make_shaman_cast.py);
        # the game's real projectile leaves the staff orb on hit_frame
        specs["fireball"] = dict(file="attack/attack_goblin_shaman_cast.png", loop=False, baseline=236,
                                 anchor=52, px=4, ms=[200, 160, 130, 320], hit_frame=2, root=0)
    return specs


# --------------------------------------------------------------------------- sprite loading
class Clip:
    """One animation (4 frames) ready to draw, facing right and mirrored for facing left."""

    def __init__(self, name, frames, spec, k):
        self.name = name
        self.frames = {1: frames, -1: [pygame.transform.flip(f, True, False) for f in frames]}
        self.count = len(frames)
        self.size = frames[0].get_width()
        self.durations = list(spec["ms"])
        self.loop = spec["loop"]
        self.baseline = spec["baseline"] * k
        self.anchor = {1: spec["anchor"] * k, -1: self.size - spec["anchor"] * k}
        self.hit_frame = spec.get("hit_frame")
        self.root_motion = spec.get("root", 0) * k


def load_row(path, k):
    """Slice the single row of 4 frames out of a 1024x1024 sheet (nearest-neighbour scaling)."""
    if not os.path.isfile(path):
        raise FileNotFoundError(f"missing sprite sheet: {path}")
    sheet = pygame.image.load(path).convert_alpha()
    if sheet.get_size() != (SHEET_SIZE, SHEET_SIZE):
        raise ValueError(f"{path}: expected {SHEET_SIZE}x{SHEET_SIZE}, got {sheet.get_size()}")
    size = max(1, int(round(CELL * k)))
    frames = []
    for i in range(FRAMES):
        cell = sheet.subsurface(pygame.Rect(i * CELL, ROW_Y, CELL, CELL)).copy()
        if size != CELL:
            cell = pygame.transform.scale(cell, (size, size))
        frames.append(cell)
    return frames


class SpriteLibrary:
    def __init__(self, assets_dir=DEFAULT_ASSETS, pixel=6):
        self.assets_dir = assets_dir
        self.pixel = pixel
        self.scale = pixel / 6.0          # UI scale used for speeds / shadows
        self.clips = {}
        for key in MOB_KEYS:
            self.clips[key] = {}
            for name, spec in clip_specs(key).items():
                k = pixel / spec["px"]    # same on-screen pixel size for every sheet
                frames = load_row(os.path.join(assets_dir, spec["file"]), k)
                self.clips[key][name] = Clip(name, frames, spec, k)

    def __getitem__(self, key):
        return self.clips[key]


# --------------------------------------------------------------------------- the mob
class Mob:
    def __init__(self, key, lib, x=400.0):
        self.key = key
        self.meta = META[key]
        self.clips = lib[key]
        self.scale = lib.scale
        self.x = float(x)
        self.facing = 1
        self.state = "idle"          # idle | walk | attack
        self.anim = "idle"
        self.clip = self.clips["idle"]
        self.index = 0
        self.t = 0.0
        self.finished = False
        self.attack_slot = 0
        self.bounce = False          # turn around at the edges (used by the AI)

    # -- control ------------------------------------------------------------------------
    @property
    def attacking(self):
        return self.state == "attack"

    def _play(self, name):
        if name == self.anim:
            return
        self.anim, self.clip = name, self.clips[name]
        self.index, self.t, self.finished = 0, 0.0, False

    def move(self, direction):
        """-1 walk left, +1 walk right, 0 stand still. Ignored while attacking."""
        if self.attacking:
            return
        if direction == 0:
            self.state = "idle"
            self._play("idle")
        else:
            self.facing = 1 if direction > 0 else -1
            self.state = "walk"
            self._play("walk")

    def attack(self, slot=0, face=None):
        """Start attack `slot` (index into META.attacks). Returns False if already attacking."""
        if self.attacking:
            return False
        names = self.meta.attacks
        self.attack_slot = slot % len(names)
        if face:
            self.facing = 1 if face > 0 else -1
        self.state = "attack"
        self.anim = ""               # force restart even if the same clip is replayed
        self._play(names[self.attack_slot])
        return True

    @property
    def attack_name(self):
        return self.meta.attacks[self.attack_slot]

    # -- simulation ---------------------------------------------------------------------
    def update(self, dt, bounds):
        events = []
        clip = self.clip
        self.t += dt * 1000.0
        while not self.finished and self.t >= clip.durations[self.index]:
            self.t -= clip.durations[self.index]
            self.index += 1
            if self.index >= clip.count:
                if clip.loop:
                    self.index = 0
                else:
                    self.index, self.t, self.finished = clip.count - 1, 0.0, True
                    break
            if clip.hit_frame is not None and self.index == clip.hit_frame:
                events.append(("hit", self.anim))

        if self.attacking and self.finished:
            events.append(("end", self.anim))
            self.x += self.facing * clip.root_motion       # keep the distance the sprite jumped / dashed
            self.state = "idle"
            self.anim = ""
            self._play("idle")

        if self.state == "walk":
            self.x += self.facing * self.meta.speed * self.scale * dt

        lo, hi = bounds
        if self.x <= lo or self.x >= hi:
            self.x = min(max(self.x, lo), hi)
            if self.bounce and self.state == "walk":
                self.facing = 1 if self.x <= lo else -1
        return events

    # -- drawing ------------------------------------------------------------------------
    def draw(self, surf, feet_y, debug=False):
        clip = self.clip
        img = clip.frames[self.facing][self.index]
        px = int(round(self.x - clip.anchor[self.facing]))
        py = int(round(feet_y - clip.baseline))
        surf.blit(img, (px, py))
        if debug:
            pygame.draw.rect(surf, (255, 255, 0), pygame.Rect(px, py, clip.size, clip.size), 1)
            pygame.draw.line(surf, (255, 60, 60), (px, feet_y), (px + clip.size, feet_y), 1)
            pygame.draw.line(surf, (60, 255, 60), (int(self.x), feet_y - 40), (int(self.x), feet_y + 6), 2)


# --------------------------------------------------------------------------- simple AI
class Wanderer:
    """Randomly idles and walks; attacks the nearest other mob at least every few seconds.

    Attacks cycle through the mob's attack list, so the Goblin Shaman alternates
    barrier -> fireball -> barrier ...
    """

    MAX_PEACE = 4.0     # seconds without an attack before the next decision is forced to be one

    def __init__(self, rng):
        self.rng = rng
        self.timer = rng.uniform(0.2, 1.5)
        self.since_attack = rng.uniform(0.0, 2.5)
        self.slot = 0

    def update(self, mob, others, dt):
        if mob.attacking:
            self.since_attack = 0.0
            return
        mob.bounce = True
        self.since_attack += dt
        self.timer -= dt
        if self.timer > 0:
            return
        r = self.rng.random()
        if self.since_attack > self.MAX_PEACE:
            r = 1.0
        if r < 0.25:
            mob.move(0)
            self.timer = self.rng.uniform(0.6, 1.6)
        elif r < 0.65:
            mob.move(self.rng.choice((-1, 1)))
            self.timer = self.rng.uniform(1.0, 2.5)
        else:
            target = min(others, key=lambda o: abs(o.x - mob.x)) if others else None
            face = (1 if target.x >= mob.x else -1) if target else mob.facing
            mob.move(0)
            mob.attack(self.slot, face=face)
            self.slot += 1
            self.timer = self.rng.uniform(0.8, 1.8)


# --------------------------------------------------------------------------- scene helpers
def make_background(w=WIN_W, h=WIN_H):
    """Chunky pixel-art fantasy dusk, drawn at 1/4 size then scaled up."""
    sw, sh = w // 4, h // 4
    bg = pygame.Surface((sw, sh))
    horizon = 150
    top, bottom = (58, 42, 102), (246, 168, 120)
    for y in range(horizon):
        t = y / horizon
        bg.fill(tuple(int(top[i] + (bottom[i] - top[i]) * t) for i in range(3)), pygame.Rect(0, y, sw, 1))
    rng = random.Random(7)
    for _ in range(40):
        bg.fill((255, 245, 220), pygame.Rect(rng.randrange(sw), rng.randrange(60), 1, 1))
    pygame.draw.ellipse(bg, (255, 236, 190), pygame.Rect(238, 24, 26, 26))
    for col, base, amp, freq, phase in (((92, 66, 128), 118, 14, 0.035, 0.0), ((58, 90, 96), 134, 10, 0.06, 1.3)):
        pts = [(0, horizon)] + [(x, int(base + amp * math.sin(x * freq + phase))) for x in range(0, sw + 4, 4)] + [(sw, horizon)]
        pygame.draw.polygon(bg, col, pts)
    bg.fill((70, 128, 74), pygame.Rect(0, horizon, sw, sh - horizon))
    bg.fill((110, 176, 90), pygame.Rect(0, horizon, sw, 2))
    bg.fill((86, 150, 78), pygame.Rect(0, horizon + 2, sw, 2))
    bg.fill((96, 66, 52), pygame.Rect(0, sh - 10, sw, 10))
    for x in range(0, sw, 6):
        bg.fill((52, 104, 62), pygame.Rect(x + (x // 6) % 3, horizon + 8 + (x * 7) % 14, 2, 1))
    return pygame.transform.scale(bg, (w, h))


def draw_shadow(surf, mob, feet_y):
    w = int(mob.meta.shadow * mob.scale)
    h = max(6, w // 6)
    shadow = pygame.Surface((w, h), pygame.SRCALPHA)
    pygame.draw.ellipse(shadow, (0, 0, 0, 80), pygame.Rect(0, 0, w, h))
    surf.blit(shadow, (int(mob.x - w / 2), feet_y - h // 2))


class FloatText:
    def __init__(self, text, x, y, color=(255, 236, 150), ttl=0.8):
        self.text, self.x, self.y, self.color, self.ttl, self.life = text, x, y, color, ttl, ttl

    def update(self, dt):
        self.life -= dt
        self.y -= 28 * dt
        return self.life > 0


def draw_text(surf, font, text, pos, color=(255, 255, 255), shadow=True, center=False):
    img = font.render(text, True, color)
    x, y = int(pos[0]), int(pos[1])
    if center:
        x -= img.get_width() // 2
    if shadow:
        surf.blit(font.render(text, True, (20, 12, 30)), (x + 2, y + 2))
    surf.blit(img, (x, y))


def create_mobs(lib, rng):
    xs = [170, 360, 550, 790, 1100]
    mobs = [Mob(k, lib, x) for k, x in zip(MOB_KEYS, xs)]
    brains = [Wanderer(random.Random(rng.random())) for _ in mobs]
    return mobs, brains


# --------------------------------------------------------------------------- interactive viewer
def run_viewer(args):
    pygame.init()
    screen = pygame.display.set_mode((WIN_W, WIN_H))
    pygame.display.set_caption("RealmQuest - Mobs")
    clock = pygame.time.Clock()
    lib = SpriteLibrary(args.assets, args.pixel)
    rng = random.Random(args.seed)
    mobs, brains = create_mobs(lib, rng)
    bg = make_background()
    font = pygame.font.Font(None, 26)
    small = pygame.font.Font(None, 20)
    big = pygame.font.Font(None, 40)

    selected, auto, debug = 3, True, False
    floats = []
    bounds = (110, WIN_W - 110)
    running = True
    while running:
        dt = min(clock.tick(60) / 1000.0, 0.05)
        for ev in pygame.event.get():
            if ev.type == pygame.QUIT:
                running = False
            elif ev.type == pygame.KEYDOWN:
                k = ev.key
                if k == pygame.K_ESCAPE:
                    running = False
                elif k == pygame.K_m:
                    auto = not auto
                    for m in mobs:
                        m.move(0)
                elif k == pygame.K_F1:
                    debug = not debug
                elif k == pygame.K_TAB:
                    selected = (selected + 1) % len(mobs)
                elif pygame.K_1 <= k <= pygame.K_5:
                    selected = k - pygame.K_1
                elif k == pygame.K_SPACE:
                    mobs[selected].attack(0)
                elif k == pygame.K_f:
                    mobs[selected].attack(1)

        keys = pygame.key.get_pressed()
        if auto:
            for m, b in zip(mobs, brains):
                b.update(m, [o for o in mobs if o is not m], dt)
        else:
            sel = mobs[selected]
            d = (keys[pygame.K_RIGHT] or keys[pygame.K_d]) - (keys[pygame.K_LEFT] or keys[pygame.K_a])
            sel.bounce = False
            sel.move(int(d))

        for m in mobs:
            for kind, name in m.update(dt, bounds):
                if kind == "hit":
                    slot = m.meta.attacks.index(name)
                    floats.append(FloatText(m.meta.popups[slot], m.x, FEET_Y - (m.meta.height + 55) * m.scale))
        floats = [f for f in floats if f.update(dt)]

        screen.blit(bg, (0, 0))
        for m in mobs:
            draw_shadow(screen, m, FEET_Y)
        for m in mobs:
            m.draw(screen, FEET_Y, debug)
        for i, m in enumerate(mobs):
            tag = f"{m.meta.label}: {m.anim}"
            draw_text(screen, small, tag, (m.x, FEET_Y + 24), (255, 255, 255) if i == selected else (200, 200, 215), center=True)
        sel = mobs[selected]
        head = sel.meta.height * sel.scale
        tip_top, tip_bot, sx = int(FEET_Y - head - 40), int(FEET_Y - head - 22), int(sel.x)
        pygame.draw.polygon(screen, (255, 220, 80), [(sx - 9, tip_top), (sx + 9, tip_top), (sx, tip_bot)])
        for f in floats:
            draw_text(screen, big, f.text, (f.x, f.y), f.color, center=True)

        draw_text(screen, font, "REALMQUEST MOBS", (20, 14))
        draw_text(screen, small, f"mode: {'AUTO (all mobs act on their own)' if auto else 'MANUAL (controlling ' + sel.meta.label + ')'}", (20, 42), (255, 220, 120))
        draw_text(screen, small, "1-5 / TAB select   A D / arrows walk   SPACE attack   F 2nd attack (Shaman: fireball)   M auto/manual   F1 debug   ESC quit", (20, WIN_H - 28), (230, 230, 245))
        pygame.display.flip()
    pygame.quit()
    return 0


# --------------------------------------------------------------------------- test run
def contact_sheet(lib, font):
    """Every animation of every mob, frame by frame, on one image."""
    cell = 128
    rows = [(k, n) for k in MOB_KEYS for n in lib[k]]
    sheet = pygame.Surface((200 + FRAMES * cell, len(rows) * cell))
    sheet.fill((52, 56, 76))
    for r, (k, n) in enumerate(rows):
        clip = lib[k][n]
        draw_text(sheet, font, f"{META[k].label}", (8, r * cell + 42), shadow=False)
        draw_text(sheet, font, f"{n}", (8, r * cell + 64), (255, 220, 120), shadow=False)
        for i in range(FRAMES):
            f = pygame.transform.scale(clip.frames[1][i], (cell, cell))
            sheet.blit(f, (200 + i * cell, r * cell))
            pygame.draw.rect(sheet, (80, 86, 110), pygame.Rect(200 + i * cell, r * cell, cell, cell), 1)
    return sheet


def run_tests(args):
    os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
    os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
    pygame.init()
    screen = pygame.display.set_mode((WIN_W, WIN_H))
    os.makedirs(args.out, exist_ok=True)
    results = []

    def check(name, ok, detail=""):
        results.append(ok)
        print(f"  [{'PASS' if ok else 'FAIL'}] {name}" + (f"  ({detail})" if detail else ""))

    print("pygame", pygame.version.ver, "| assets:", args.assets)

    # 1. load every sheet --------------------------------------------------------------
    print("1) loading sprite sheets")
    try:
        lib = SpriteLibrary(args.assets, args.pixel)
        check("all sheets load", True, f"{sum(len(v) for v in lib.clips.values())} animations")
    except Exception as exc:                       # noqa: BLE001
        check("all sheets load", False, repr(exc))
        return 1
    for key in MOB_KEYS:
        for name, clip in lib[key].items():
            nonempty = all(pygame.mask.from_surface(f).count() > 0 for f in clip.frames[1])
            check(f"{key}/{name}: {clip.count} non-empty frames", clip.count == FRAMES and nonempty)

    # 2. looping clips visit every frame -------------------------------------------------
    print("2) idle / walk loops")
    bounds = (0, 100000)
    for key in MOB_KEYS:
        for state in ("idle", "walk"):
            m = Mob(key, lib, x=500)
            m.move(0 if state == "idle" else 1)
            seen = set()
            for _ in range(180):
                m.update(1 / 60, bounds)
                seen.add(m.index)
            check(f"{key} {state} cycles all frames", seen == set(range(FRAMES)))

    # 3. attacks: hit event once, ends, returns to idle, root motion applied -----------------
    print("3) attacks")
    for key in MOB_KEYS:
        meta = META[key]
        for slot, name in enumerate(meta.attacks):
            m = Mob(key, lib, x=500)
            m.facing = 1
            ok_start = m.attack(slot, face=1)
            blocked = not m.attack(slot)            # a second call while attacking must be ignored
            ev = []
            for _ in range(600):
                ev += m.update(1 / 60, bounds)
                if not m.attacking:
                    break
            hits = [e for e in ev if e == ("hit", name)]
            ended = [e for e in ev if e == ("end", name)]
            moved = m.x - 500
            expect = lib[key][name].root_motion
            check(f"{key}/{name}: starts, locks, 1 hit, ends -> idle",
                  ok_start and blocked and len(hits) == 1 and len(ended) == 1 and m.state == "idle" and m.anim == "idle")
            check(f"{key}/{name}: root motion {moved:.0f}px (expected {expect:.0f}px)", abs(moved - expect) < 1.0)

    # 4. flipping and bounds --------------------------------------------------------------
    print("4) facing + bounds")
    m = Mob("wild_boar", lib, x=300)
    m.move(-1)
    for _ in range(600):
        m.update(1 / 60, (200, 400))
    check("walking left clamps at left bound", abs(m.x - 200) < 1e-6 and m.facing == -1)
    m.bounce = True
    m.update(1 / 60, (200, 400))
    check("bounce turns the mob around", m.facing == 1)
    left, right = lib["goblin_shaman"]["fireball"].anchor[-1], lib["goblin_shaman"]["fireball"].anchor[1]
    check("mirrored anchor is correct", abs((left + right) - lib["goblin_shaman"]["fireball"].size) < 1e-6)

    # 5. full scene simulation with rendering ------------------------------------------------
    print("5) 20 s simulated scene (AI + rendering)")
    rng = random.Random(args.seed)
    mobs, brains = create_mobs(lib, rng)
    bg = make_background()
    font = pygame.font.Font(None, 22)
    counts = {m.key: 0 for m in mobs}
    ends = {m.key: 0 for m in mobs}
    shaman_seen = set()
    for frame in range(60 * 20):
        for m, b in zip(mobs, brains):
            b.update(m, [o for o in mobs if o is not m], 1 / 60)
            for kind, aname in m.update(1 / 60, (110, WIN_W - 110)):
                if kind == "hit":
                    counts[m.key] += 1
                    if m.key == "goblin_shaman":
                        shaman_seen.add(aname)
                elif kind == "end":
                    ends[m.key] += 1
        if frame % 3 == 0:
            screen.blit(bg, (0, 0))
            for m in mobs:
                draw_shadow(screen, m, FEET_Y)
                m.draw(screen, FEET_Y)
    pygame.image.save(screen, os.path.join(args.out, "test_scene.png"))
    for _ in range(300):                             # let any attack that is still playing finish
        if not any(m.attacking for m in mobs):
            break
        for m in mobs:
            for kind, _name in m.update(1 / 60, (110, WIN_W - 110)):
                if kind == "hit":
                    counts[m.key] += 1
                elif kind == "end":
                    ends[m.key] += 1
    check("every mob attacked at least once", all(c >= 1 for c in counts.values()), str(counts))
    check("every attack finished", counts == ends)
    check("shaman used both attacks", shaman_seen == {"barrier", "fireball"}, str(sorted(shaman_seen)))
    check("mobs stayed inside the stage", all(110 <= m.x <= WIN_W - 110 for m in mobs))

    # 6. screenshots ----------------------------------------------------------------------------
    print("6) screenshots")
    lineup = [Mob(k, lib, x) for k, x in zip(MOB_KEYS, [170, 360, 550, 790, 1100])]
    for m in lineup:
        m.attack(1 if m.key == "goblin_shaman" else 0, face=1)
        for _ in range(80):                          # advance to the hit frame
            m.update(1 / 60, (0, 5000))
            if m.index >= 2:
                break
    screen.blit(bg, (0, 0))
    for m in lineup:
        draw_shadow(screen, m, FEET_Y)
        m.draw(screen, FEET_Y, debug=False)
    pygame.image.save(screen, os.path.join(args.out, "test_attacks.png"))
    pygame.image.save(contact_sheet(lib, font), os.path.join(args.out, "test_contact_sheet.png"))
    check("screenshots written", all(os.path.isfile(os.path.join(args.out, n))
                                     for n in ("test_scene.png", "test_attacks.png", "test_contact_sheet.png")),
          args.out)

    passed, total = sum(results), len(results)
    print(f"\n{'ALL TESTS PASSED' if passed == total else 'SOME TESTS FAILED'}: {passed}/{total}")
    pygame.quit()
    return 0 if passed == total else 1


# --------------------------------------------------------------------------- entry point
def main(argv=None):
    ap = argparse.ArgumentParser(description="RealmQuest mobs: sprite viewer / self-test")
    ap.add_argument("--assets", default=DEFAULT_ASSETS, help="folder with idle/ walk/ attack/ sheets")
    ap.add_argument("--pixel", type=int, default=6, help="on-screen size of one art pixel (3, 6, 9, 12 are exact)")
    ap.add_argument("--seed", type=int, default=3, help="random seed for the viewer / test AI")
    ap.add_argument("--test", action="store_true", help="headless self-test + screenshots")
    ap.add_argument("--out", default=DEFAULT_TEST_OUT, help="screenshot folder for --test")
    args = ap.parse_args(argv)
    if args.pixel % 3:
        print("note: --pixel works best as a multiple of 3 (3, 6, 9, 12); other values may show uneven pixels")
    return run_tests(args) if args.test else run_viewer(args)


if __name__ == "__main__":
    sys.exit(main())
