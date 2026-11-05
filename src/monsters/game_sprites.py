"""
game_sprites.py - Puts the monster sprite sheets on the game's enemies.

    from monsters import game_sprites
    enemy.skin = "slime_green"                      # any key of SKINS
    game_sprites.draw_enemy(enemy, surface, cam_x, cam_y)

An enemy only needs x, y (the point under its feet), radius, and optionally
attack_cd (an attack starts when it jumps up), face_x (+1 right / -1 left),
hit_flash (> 0 = flash white) and skin_scale.
The animation state is kept on the enemy itself (enemy._anim), so one skin is shared
by every enemy that wears it.

Skins:
    overworld:      slime_red, slime_blue, slime_green, wild_boar
                    (assets/monsters/mobs/ - idle / walk / attack sheets)
    goblin dungeon: goblin_shaman (assets/monsters/mobs/),
                    goblin_general, giant_boar (assets/monsters/goblin_army/)
"""
from __future__ import annotations

import math
import os

import pygame

try:
    from . import mobs as mobs_mod
    from . import monsters_config as army_cfg
except ImportError:
    import mobs as mobs_mod
    import monsters_config as army_cfg

MOB_PIXEL = 2                 # on-screen size of one art pixel for the mobs sheets
ARMY_SCALE = {"goblin_general": 2.0, "giant_boar": 1.5}
ARMY_NAMES = {"goblin_general": "goblin_general", "giant_boar": "giant_boar"}
MOB_SKINS = ("slime_red", "slime_blue", "slime_green", "wild_boar", "goblin_shaman")
SKINS = MOB_SKINS + tuple(ARMY_SCALE)
ATTACK_CLIP = {"goblin_shaman": "fireball"}     # which attack sheet a skin plays

_library = None
_army = {}
_flash_cache = {}


class _Anim:
    """One animation: frames facing right + left, where the feet are, and frame times."""

    def __init__(self, frames, anchor, baseline, durations, loop, root=0.0):
        self.frames = {1: frames, -1: [pygame.transform.flip(f, True, False) for f in frames]}
        self.anchor = anchor                 # {1: x, -1: x} of the body centre inside a frame
        self.baseline = baseline             # y of the feet inside a frame
        self.durations = durations           # seconds per frame
        self.loop = loop
        self.root = root                     # px the sprite travels inside the sheet (attacks)

    @property
    def length(self):
        return sum(self.durations)

    def index_at(self, t):
        total = self.length
        if self.loop:
            t = t % total
        elif t >= total:
            return len(self.durations) - 1
        for i, d in enumerate(self.durations):
            if t < d:
                return i
            t -= d
        return len(self.durations) - 1


def _mob_skin(key):
    global _library
    if _library is None:
        _library = mobs_mod.SpriteLibrary(mobs_mod.DEFAULT_ASSETS, pixel=MOB_PIXEL)
    clips = _library[key]
    out = {}
    for state, name in (("idle", "idle"), ("walk", "walk"), ("attack", ATTACK_CLIP.get(key, "attack"))):
        c = clips[name]
        out[state] = _Anim(c.frames[1], c.anchor, c.baseline, [ms / 1000.0 for ms in c.durations],
                           state != "attack", c.root_motion)
    return out


def _army_skin(key):
    info = army_cfg.MONSTERS[ARMY_NAMES[key]]
    sheet = pygame.image.load(os.path.join(army_cfg.ASSET_DIR, info["sheet"])).convert_alpha()
    fw, fh = info["frame"]
    k = ARMY_SCALE[key]
    size = (int(round(fw * k)), int(round(fh * k)))
    out = {}
    baseline = None
    for state, row_name in (("idle", "idle"), ("walk", "move"), ("attack", "attack")):
        r = army_cfg.ROWS[row_name]
        frames = [pygame.transform.scale(sheet.subsurface(pygame.Rect(c * fw, r * fh, fw, fh)), size)
                  for c in range(army_cfg.FRAMES_PER_ROW)]
        if baseline is None:      # feet = lowest solid pixel of the idle pose
            baseline = max(f.get_bounding_rect().bottom for f in frames)
        dur = 1.0 / army_cfg.FPS[row_name]
        out[state] = _Anim(frames, {1: size[0] / 2, -1: size[0] / 2}, baseline,
                           [dur] * len(frames), state != "attack")
    return out


def skin(key):
    """The animations of a skin, loaded on first use (needs a display)."""
    s = _army.get(key)
    if s is None:
        s = _army[key] = _mob_skin(key) if key in MOB_SKINS else _army_skin(key)
    return s


def portrait(key, height=120):
    """An idle frame cropped to the body and scaled to `height` (for dialogs)."""
    img = skin(key)["idle"].frames[1][0]
    body = img.subsurface(img.get_bounding_rect()).copy()
    k = height / max(1, body.get_height())
    return pygame.transform.scale(body, (max(1, int(body.get_width() * k)), height))


def _flash(img):
    f = _flash_cache.get(id(img))
    if f is None or f[0] is not img:
        sil = pygame.mask.from_surface(img).to_surface(setcolor=(255, 246, 226, 255), unsetcolor=(0, 0, 0, 0))
        f = _flash_cache[id(img)] = (img, sil)
    return f[1]


def _state(enemy, dt_hint=1 / 60):
    st = getattr(enemy, "_anim", None)
    if st is None:
        st = enemy._anim = {"t": 0.0, "atk": None, "last": (enemy.x, enemy.y), "cd": 0.0,
                            "face": 1, "moving": 0.0, "clock": pygame.time.get_ticks()}
    return st


def draw_enemy(enemy, surf, cx, cy, shadow=True):
    """Draw `enemy` with its skin. Returns the screen rect of the sprite."""
    anims = skin(enemy.skin)
    st = _state(enemy)
    now = pygame.time.get_ticks()
    dt = min(0.1, max(0.0, (now - st["clock"]) / 1000.0))
    st["clock"] = now
    st["t"] += dt

    lx, ly = st["last"]
    mvx = enemy.x - lx
    moved = math.hypot(mvx, enemy.y - ly)
    st["last"] = (enemy.x, enemy.y)
    st["moving"] = 0.15 if moved > 0.2 else max(0.0, st["moving"] - dt)
    face = getattr(enemy, "face_x", None)
    if face:
        st["face"] = 1 if face > 0 else -1
    elif abs(mvx) > 0.2:
        st["face"] = 1 if mvx > 0 else -1

    cd = getattr(enemy, "attack_cd", 0.0)
    if cd > st["cd"] + 0.05:                      # an attack just started
        st["atk"] = 0.0
    st["cd"] = cd
    if st["atk"] is not None:
        st["atk"] += dt
        if st["atk"] >= anims["attack"].length:
            st["atk"] = None

    if st["atk"] is not None:
        anim, at = anims["attack"], st["atk"]
    elif st["moving"] > 0 and not getattr(enemy, "stun_t", 0):
        anim, at = anims["walk"], st["t"]
    else:
        anim, at = anims["idle"], st["t"]
    f = st["face"]
    i = anim.index_at(at)
    img = anim.frames[f][i]
    scale = getattr(enemy, "skin_scale", 1.0)
    ax, base = anim.anchor[f], anim.baseline
    if anim.root and len(anim.durations) > 1:      # keep the body in place while the sheet lunges
        ax += f * anim.root * i / (len(anim.durations) - 1)
    if getattr(enemy, "hit_flash", 0) > 0:
        img = _flash(img)                          # cached per sheet frame
    if scale != 1.0:
        img = pygame.transform.scale(img, (int(img.get_width() * scale), int(img.get_height() * scale)))
        ax, base = ax * scale, base * scale
    X, Y = int(enemy.x - cx), int(enemy.y - cy)
    if shadow:
        w = max(18, int(enemy.radius * 2.4))
        sh = pygame.Surface((w, max(6, w // 4)), pygame.SRCALPHA)
        pygame.draw.ellipse(sh, (0, 0, 0, 80), sh.get_rect())
        surf.blit(sh, (X - w // 2, Y - sh.get_height() // 2))
    pos = (int(X - ax), int(Y - base))
    surf.blit(img, pos)
    if getattr(enemy, "slow_t", 0) > 0:              # frosty tint while slowed
        ice = pygame.mask.from_surface(img).to_surface(setcolor=(120, 200, 255, 90), unsetcolor=(0, 0, 0, 0))
        surf.blit(ice, pos)
    return pygame.Rect(pos, img.get_size())
