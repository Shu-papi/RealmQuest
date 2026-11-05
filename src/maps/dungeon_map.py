from __future__ import annotations
import math
import random
from dataclasses import dataclass
import pygame

try:
    from .combat import Encounters, PlayerCombat, DASH_SPEED, projectile_open
except ImportError:
    from combat import Encounters, PlayerCombat, DASH_SPEED, projectile_open

try:
    from . import dungeon_gen
except ImportError:
    import dungeon_gen

try:
    from .story import Dialog, INTRO_LINES, BOSS_DIALOGS, OUTRO_DIALOGS, BOSS_SPEAKERS
    from . import story
except ImportError:
    from story import Dialog, INTRO_LINES, BOSS_DIALOGS, OUTRO_DIALOGS, BOSS_SPEAKERS
    import story

try:
    from .save_state import SaveState
    from . import village
    from . import room_features
    from . import quests
    from . import world_lore
    from . import night_raid
    from . import minis
    from . import wilds
    from .save_state import level_progress
except ImportError:
    from save_state import SaveState
    import village
    import room_features
    import quests
    import world_lore
    import night_raid
    import minis
    import wilds
    from save_state import level_progress

try:
    from .shop import ShopMenu
    from .journal import Journal
except ImportError:
    from shop import ShopMenu
    from journal import Journal

try:
    from .sfx import Sfx
except ImportError:
    from sfx import Sfx

try:
    from .combat import sprite as monster_sprite
except ImportError:
    from combat import sprite as monster_sprite

try:
    from . import surface_world as sw_mod
    from . import npc_art
    from .music import Music, pick_place
except ImportError:
    import surface_world as sw_mod
    import npc_art
    from music import Music, pick_place

# combat.py put src/ on the import path: the team's UI and the hero's skills
from skills.skills import SkillFX, SLOTS                       # noqa: E402
from ui import widgets as ui_widgets                           # noqa: E402
from ui import theme as ui_theme                               # noqa: E402
from ui.app_screens import FrontEnd, draw_centered             # noqa: E402
from ui.assets import get_font                                 # noqa: E402
from ui.hero_hud import HeroHUD                                # noqa: E402
from ui.settings_data import Settings                          # noqa: E402
from ui.settings_screen import SettingsScreen, BACK as SETTINGS_BACK, VIDEO_CHANGED  # noqa: E402
from ui.text import draw_text as ui_text                       # noqa: E402

# dungeon number used by the floors ("1-1" -> 1) <-> portal id in the surface world
SURFACE_IDS = {1: "goblin", 2: "berserker", 3: "lich"}
MAIN_IDS = dict(SURFACE_IDS)
for _m in minis.MINIS:                 # mini dungeons: 11-16, one floor each
    SURFACE_IDS[_m["num"]] = _m["id"]
SURFACE_NUMS = {v: k for k, v in SURFACE_IDS.items()}

SCREEN_W, SCREEN_H = 1152, 648
FPS = 60
TILE = 24
MAP_W, MAP_H = 288, 162
CELLS = MAP_W * MAP_H
PLAYER_SPEED = 180.0
LIQUID_FRAMES = 8
MINIMAP_REVEAL_ALL = False  # True = whole floor is lit up on the minimap from the start

VOID, FLOOR, LIQUID, TOP, FACE, PATH, FACE_UP = range(7)
OPEN = (FLOOR, LIQUID, PATH)
WALK = (FLOOR, PATH)
WALLS = (TOP, FACE, FACE_UP)

Color = tuple[int, int, int]


@dataclass(frozen=True)
class Theme:
    key: str
    name: str
    floor: Color
    floor_alt: Color
    path: Color
    path_alt: Color
    wall: Color
    wall_hi: Color
    wall_dark: Color
    top: Color
    liquid: Color
    liquid_hi: Color
    liquid_rim: Color
    accent: Color
    danger: Color
    ambient: Color
    glow: Color
    mote: Color


THEMES = {
    "forest": Theme(
        "forest", "Forest & Ruins",
        (54, 92, 58), (74, 118, 66), (116, 92, 62), (92, 70, 48),
        (96, 102, 88), (136, 144, 122), (34, 40, 36), (22, 30, 26),
        (38, 84, 112), (110, 170, 196), (70, 104, 64),
        (120, 196, 110), (150, 60, 46), (4, 14, 10), (255, 196, 120),
        (206, 255, 126),
    ),
    "stone": Theme(
        "stone", "Ancient Ruins",
        (76, 74, 90), (92, 88, 108), (58, 56, 70), (72, 68, 86),
        (72, 68, 84), (116, 110, 134), (24, 23, 30), (16, 15, 22),
        (22, 36, 58), (74, 104, 140), (46, 44, 56),
        (160, 130, 196), (168, 58, 66), (4, 4, 14), (255, 176, 96),
        (196, 196, 236),
    ),
    "hell": Theme(
        "hell", "The Underworld",
        (72, 34, 30), (92, 42, 32), (52, 28, 26), (68, 36, 30),
        (60, 36, 34), (118, 64, 46), (22, 12, 12), (14, 8, 9),
        (224, 92, 26), (255, 196, 76), (40, 20, 18),
        (236, 110, 40), (250, 70, 30), (24, 4, 3), (255, 112, 44),
        (255, 154, 64),
    ),
}


def dungeon_for(floor_name: str) -> int:
    return int(floor_name.split("-")[0])


def family_for(floor_name: str) -> int:
    """Which monster family (and look) a floor has: 1 goblin / 2 berserker / 3 the dead."""
    d = dungeon_for(floor_name)
    m = minis.MINI_BY_NUM.get(d)
    return m["family"] if m else d


def theme_for(floor_name: str) -> Theme:
    d = family_for(floor_name)
    # 1 = Goblin (forest), 2 = Berserker (ancient ruins), 3 = Lich King (underworld)
    by_dungeon = {1: "forest", 2: "stone", 3: "hell"}
    if d in by_dungeon:
        return THEMES[by_dungeon[d]]
    return THEMES["stone" if d <= 6 else "hell"]    # unused dungeons 4-9


def is_boss_floor(floor_name: str) -> bool:
    return floor_name.endswith("-3")


def is_last_floor(floor_name: str) -> bool:
    """The floor whose exit leads back to Oakwood (boss floors and mini dungeons)."""
    return is_boss_floor(floor_name) or minis.is_mini_floor(floor_name)


def next_floor(floor_name: str) -> str | None:
    d, f = map(int, floor_name.split("-"))
    if f < 3:
        return f"{d}-{f + 1}"
    if d < 9:
        return f"{d + 1}-1"
    return None


def previous_floor(floor_name: str) -> str | None:
    d, f = map(int, floor_name.split("-"))
    if f > 1:
        return f"{d}-{f - 1}"
    if d > 1:
        return f"{d - 1}-3"
    return None


# --------------------------------------------------------------------------
# Small helpers
# --------------------------------------------------------------------------

def shade(c, f):
    return (
        max(0, min(255, int(c[0] * f))),
        max(0, min(255, int(c[1] * f))),
        max(0, min(255, int(c[2] * f))),
    )


def mix(a, b, t):
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))


def hash2(x, y, s=0):
    n = (x * 374761393 + y * 668265263 + s * 2246822519) & 0xFFFFFFFF
    n = ((n ^ (n >> 13)) * 1274126177) & 0xFFFFFFFF
    return n ^ (n >> 16)


def blank(w, h):
    return pygame.Surface((w, h), pygame.SRCALPHA)


def vgrad(s, rect, top, bot):
    """Vertical gradient fill (works for RGB and RGBA tuples)."""
    x, y, w, h = rect
    n = len(top)
    for j in range(h):
        k = j / max(1, h - 1)
        c = tuple(int(top[i] + (bot[i] - top[i]) * k) for i in range(n))
        s.fill(c, (x, y + j, w, 1))


def wrap_ellipse(s, col, cx, cy, rw, rh):
    """Ellipse that wraps around tile edges so tiles stay seamless."""
    for ox in (-TILE, 0, TILE):
        for oy in (-TILE, 0, TILE):
            pygame.draw.ellipse(s, col, (cx - rw + ox, cy - rh + oy, rw * 2, rh * 2))


def soft_shadow(s, cx, cy, rw, rh, alpha=80):
    sh = blank(rw * 2, rh * 2)
    pygame.draw.ellipse(sh, (0, 0, 0, alpha // 2), (0, 0, rw * 2, rh * 2))
    pygame.draw.ellipse(sh, (0, 0, 0, alpha), (rw * 0.25, rh * 0.25, rw * 1.5, rh * 1.5))
    s.blit(sh, (cx - rw, cy - rh))


def noise(s, base, rng, n, lo=0.88, hi=1.12):
    for _ in range(n):
        s.set_at((rng.randrange(TILE), rng.randrange(TILE)),
                 shade(base, rng.uniform(lo, hi)))


def crack(s, rng, color, core):
    x, y = rng.randrange(4, TILE - 4), rng.randrange(4, TILE - 4)
    pts = [(x, y)]
    for _ in range(rng.randrange(3, 5)):
        x = max(1, min(TILE - 2, x + rng.randrange(-6, 7)))
        y = max(1, min(TILE - 2, y + rng.randrange(-6, 7)))
        pts.append((x, y))
    pygame.draw.lines(s, color, False, pts, 2 if core else 1)
    if core:
        pygame.draw.lines(s, core, False, pts, 1)


def draw_panel(surf, rect, border, alpha=205):
    """Gradient glass panel with a double border and corner studs."""
    w, h = rect.w, rect.h
    s = blank(w, h)
    vgrad(s, (0, 0, w, h), (24, 24, 34, alpha), (6, 6, 10, alpha))
    m = blank(w, h)
    pygame.draw.rect(m, (255, 255, 255, 255), m.get_rect(), border_radius=8)
    s.blit(m, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
    pygame.draw.rect(s, border, s.get_rect(), 2, border_radius=8)
    pygame.draw.rect(s, shade(border, 0.4), s.get_rect().inflate(-8, -8), 1, border_radius=5)
    s.fill((255, 255, 255, 26), (8, 3, max(1, w - 16), 1))
    for x, y in ((6, 6), (w - 9, 6), (6, h - 9), (w - 9, h - 9)):
        s.fill(border, (x, y, 3, 3))
        s.fill(shade(border, 1.5), (x, y, 1, 1))
    surf.blit(s, rect.topleft)


# --------------------------------------------------------------------------
# Tiles
# --------------------------------------------------------------------------

def slab_tile(s, base, alt, rng, lip=1.2):
    """Beveled flagstone with mortar gaps."""
    s.fill(shade(base, 0.5))
    body = shade(base, rng.uniform(0.95, 1.08))
    vgrad(s, (1, 1, TILE - 2, TILE - 2), shade(body, 1.07), shade(body, 0.9))
    noise(s, body, rng, 60, 0.9, 1.1)
    pygame.draw.line(s, shade(alt, lip), (1, 1), (TILE - 3, 1))
    pygame.draw.line(s, shade(alt, lip * 0.92), (1, 1), (1, TILE - 3))
    pygame.draw.line(s, shade(base, 0.66), (TILE - 2, 2), (TILE - 2, TILE - 2))
    pygame.draw.line(s, shade(base, 0.66), (2, TILE - 2), (TILE - 2, TILE - 2))
    for _ in range(rng.randrange(1, 4)):
        x, y = rng.randrange(3, TILE - 5), rng.randrange(3, TILE - 5)
        s.fill(shade(body, 0.7), (x, y, 2, 1))
        s.fill(shade(body, 1.2), (x, y + 1, 2, 1))


def make_floor(t: Theme, rng: random.Random, path: bool):
    s = pygame.Surface((TILE, TILE))
    base = t.path if path else t.floor
    alt = t.path_alt if path else t.floor_alt
    s.fill(base)

    if t.key == "forest":
        for _ in range(5):
            wrap_ellipse(s, shade(base, rng.uniform(0.9, 1.12)),
                         rng.randrange(TILE), rng.randrange(TILE),
                         rng.randrange(5, 10), rng.randrange(4, 8))
        noise(s, base, rng, 70)
        if path:
            for _ in range(9):
                x, y = rng.randrange(2, TILE - 5), rng.randrange(2, TILE - 5)
                w, h = rng.randrange(3, 6), rng.randrange(2, 4)
                c = shade(alt, rng.uniform(0.9, 1.4))
                pygame.draw.ellipse(s, shade(c, 0.55), (x, y + 1, w, h))
                pygame.draw.ellipse(s, c, (x, y, w, h))
                s.set_at((x + 1, y), shade(c, 1.3))
            for _ in range(10):
                s.fill(shade(base, rng.uniform(0.6, 0.8)),
                       (rng.randrange(TILE), rng.randrange(TILE), 1, 1))
            for _ in range(3):
                x, y = rng.randrange(2, TILE - 2), rng.randrange(4, TILE)
                pygame.draw.line(s, shade(t.floor_alt, rng.uniform(0.8, 1.2)),
                                 (x, y), (x + rng.choice((-1, 0, 1)), y - rng.randrange(2, 4)))
        else:
            for _ in range(46):
                x, y = rng.randrange(1, TILE - 1), rng.randrange(3, TILE)
                dx, hh = rng.choice((-1, 0, 1)), rng.randrange(2, 5)
                pygame.draw.line(s, shade(alt, rng.uniform(0.55, 0.85)), (x, y), (x + dx, y - hh))
                s.set_at((x + dx, y - hh), shade(alt, rng.uniform(1.25, 1.5)))
            if rng.random() < 0.22:
                col = rng.choice(((240, 236, 200), (236, 200, 90), (200, 150, 220), (240, 130, 140)))
                fx, fy = rng.randrange(3, TILE - 4), rng.randrange(4, TILE - 4)
                s.fill(col, (fx, fy - 1, 1, 3))
                s.fill(col, (fx - 1, fy, 3, 1))
                s.set_at((fx, fy), (250, 214, 90))
            if rng.random() < 0.1:
                px, py = rng.randrange(3, TILE - 5), rng.randrange(3, TILE - 5)
                pygame.draw.ellipse(s, (96, 100, 94), (px, py, 4, 3))
                s.set_at((px + 1, py), (150, 154, 144))

    elif t.key == "stone":
        if path:
            s.fill(shade(base, 0.5))
            for row in range(3):
                y = row * 8
                off = 4 if row % 2 else 0
                for x0 in range(off - 8, TILE, 8):
                    r = pygame.Rect(x0 + 1, y + 1, 6, 6)
                    c = shade(alt, rng.uniform(0.88, 1.15))
                    pygame.draw.rect(s, c, r, border_radius=2)
                    pygame.draw.line(s, shade(c, 1.28), (r.left + 1, r.top), (r.right - 2, r.top))
                    pygame.draw.line(s, shade(c, 0.7), (r.left + 1, r.bottom - 1), (r.right - 2, r.bottom - 1))
            noise(s, base, rng, 24, 0.85, 1.2)
        else:
            slab_tile(s, base, alt, rng, 1.2)
            if rng.random() < 0.16:
                crack(s, rng, shade(base, 0.5), None)
            if rng.random() < 0.05:
                pygame.draw.circle(s, shade(t.accent, 0.55), (TILE // 2, TILE // 2), 5, 1)
                s.fill(shade(t.accent, 0.7), (TILE // 2 - 1, TILE // 2 - 1, 2, 2))

    else:
        if path:
            for _ in range(7):
                x, y = rng.randrange(TILE - 4), rng.randrange(TILE - 3)
                c = shade(alt, rng.uniform(0.8, 1.35))
                pygame.draw.ellipse(s, shade(c, 0.6), (x, y + 1, rng.randrange(3, 6), 3))
                pygame.draw.ellipse(s, c, (x, y, rng.randrange(3, 6), 3))
            for _ in range(9):
                s.fill(shade(alt, rng.uniform(0.8, 1.3)),
                       (rng.randrange(TILE - 3), rng.randrange(TILE - 2), rng.randrange(2, 5), 2))
            for _ in range(2):
                s.fill(t.accent, (rng.randrange(TILE), rng.randrange(TILE), 1, 1))
            if rng.random() < 0.25:
                s.fill((255, 196, 96), (rng.randrange(TILE), rng.randrange(TILE), 1, 1))
        else:
            slab_tile(s, base, alt, rng, 1.3)
            if rng.random() < 0.42:
                crack(s, rng, shade(t.accent, 0.7), (255, 196, 96))
            elif rng.random() < 0.4:
                crack(s, rng, shade(base, 0.5), None)
            for _ in range(3):
                s.fill(shade(t.accent, rng.uniform(0.5, 0.9)),
                       (rng.randrange(2, TILE - 2), rng.randrange(2, TILE - 2), 1, 1))
    return s


def make_face(t: Theme, rng: random.Random, upper: bool = False):
    s = pygame.Surface((TILE, TILE))
    s.fill(shade(t.wall_dark, 0.9))
    for row in range(3):
        y = row * 8
        off = 0 if row % 2 == 0 else 6
        for x in range(-12 + off, TILE, 12):
            r = pygame.Rect(x + 1, y + 1, 10, 6)
            c = shade(t.wall, rng.uniform(0.8, 1.15))
            pygame.draw.rect(s, c, r)
            pygame.draw.line(s, shade(c, 1.3), r.topleft, (r.right - 1, r.top))
            pygame.draw.line(s, shade(c, 1.12), r.topleft, (r.left, r.bottom - 1))
            pygame.draw.line(s, shade(c, 0.62), (r.left, r.bottom - 1), (r.right - 1, r.bottom - 1))
            pygame.draw.line(s, shade(c, 0.72), (r.right - 1, r.top), (r.right - 1, r.bottom - 1))
            for _ in range(3):
                s.set_at((rng.randrange(r.left, r.right), rng.randrange(r.top, r.bottom)),
                         shade(c, rng.uniform(0.8, 1.25)))
    if t.key == "forest":
        for _ in range(3):
            x, y0 = rng.randrange(1, TILE - 1), rng.choice((0, 7, 15))
            for j in range(rng.randrange(3, 7)):
                s.set_at((x, y0 + j), shade((72, 118, 62), rng.uniform(0.7, 1.2)))
        for _ in range(14):
            s.fill((72, 118, 62), (rng.randrange(TILE - 3), rng.randrange(TILE - 6),
                                  rng.randrange(2, 5), 1))
        if rng.random() < 0.5:
            x = rng.randrange(3, TILE - 3)
            for j in range(0, TILE - 6):
                s.set_at((x + int(math.sin(j * 0.7) * 2), j), (44, 96, 48))
                if j % 5 == 2:
                    s.fill((84, 148, 70), (x + int(math.sin(j * 0.7) * 2) + 1, j, 2, 2))
    elif t.key == "stone":
        for _ in range(2):
            x, y0 = rng.randrange(2, TILE - 2), rng.randrange(0, 6)
            for j in range(rng.randrange(8, 18)):
                s.set_at((x, y0 + j), mix(shade(t.wall, 0.6), (30, 54, 80), 0.4))
    elif t.key == "hell":
        for _ in range(5):
            y = rng.choice((0, 7, 8, 15, 16, 23))
            x, ln = rng.randrange(TILE - 6), rng.randrange(3, 8)
            s.fill(shade(t.accent, 0.85), (x, y, ln, 1))
            s.fill((255, 196, 96), (x + 1, y, max(1, ln - 3), 1))
    if rng.random() < 0.45:
        x, y = rng.randrange(3, TILE - 3), rng.randrange(3, 8)
        pts = [(x, y)]
        for _ in range(3):
            x = max(1, min(TILE - 2, x + rng.randrange(-3, 4)))
            y = min(TILE - 3, y + rng.randrange(3, 6))
            pts.append((x, y))
        pygame.draw.lines(s, shade(t.wall_dark, 1.1), False, pts, 1)
    ov = blank(TILE, TILE)
    for row in range(TILE):
        if upper:
            # shadow under the overhanging cap, then a faint fade downward
            a = 64 * max(0.0, 1 - row / 7) ** 1.5 + 12 * row / (TILE - 1)
        else:
            # light falls off toward the floor (ambient occlusion at the base)
            a = 14 + 112 * (row / (TILE - 1)) ** 2.2
        ov.fill((0, 0, 0, int(a)), (0, row, TILE, 1))
    s.blit(ov, (0, 0))
    return s


def make_cast_shadow(spr, alpha=70):
    """Flattened, sheared silhouette that falls down-right along the ground."""
    w, h = spr.get_size()
    sil = pygame.mask.from_surface(spr).to_surface(setcolor=(0, 0, 0, alpha),
                                                   unsetcolor=(0, 0, 0, 0))
    sh_h = max(6, int(h * 0.45))
    flat = pygame.transform.flip(pygame.transform.smoothscale(sil, (w, sh_h)), False, True)
    shear = 0.8
    out = blank(w + int(sh_h * shear) + 2, sh_h)
    for r in range(sh_h):
        out.blit(flat, (int(r * shear), r), (0, r, w, 1))
    return out.convert_alpha()


def make_top(t: Theme, rng: random.Random):
    s = pygame.Surface((TILE, TILE))
    s.fill(t.top)
    noise(s, t.top, rng, 60, 0.75, 1.4)
    if t.key == "forest":
        for _ in range(8):
            wrap_ellipse(s, shade((30, 60, 38), rng.uniform(0.7, 1.3)),
                         rng.randrange(TILE), rng.randrange(TILE),
                         rng.randrange(3, 6), rng.randrange(3, 6))
        for _ in range(16):
            x, y = rng.randrange(TILE - 2), rng.randrange(TILE - 1)
            s.fill((58, 104, 56), (x, y, 2, 1))
        for _ in range(6):
            s.set_at((rng.randrange(TILE), rng.randrange(TILE)), (96, 150, 78))
    elif t.key == "stone":
        for _ in range(3):
            x, y = rng.randrange(TILE), rng.randrange(TILE)
            pygame.draw.line(s, shade(t.top, 1.7), (x, y),
                             (x + rng.randrange(-5, 6), y + rng.randrange(-4, 5)))
        for _ in range(8):
            s.set_at((rng.randrange(TILE), rng.randrange(TILE)), shade(t.top, 0.6))
    elif t.key == "hell":
        for _ in range(4):
            s.fill(shade(t.accent, 0.5), (rng.randrange(TILE), rng.randrange(TILE), 1, 1))
        for _ in range(3):
            x, y = rng.randrange(TILE - 6), rng.randrange(TILE)
            s.fill(shade(t.top, 1.9), (x, y, rng.randrange(3, 7), 1))
    return s


def make_liquid(t: Theme, frame: int):
    """Seamless animated liquid built from tileable sine fields."""
    s = pygame.Surface((TILE, TILE))
    ph = frame * math.tau / LIQUID_FRAMES
    k = math.tau / TILE
    hell = t.key == "hell"
    mid, hi = t.liquid, t.liquid_hi
    deep = shade(mid, 0.72)
    crust = shade(mid, 0.26)
    for y in range(0, TILE, 2):
        for x in range(0, TILE, 2):
            v = (math.sin(x * k + ph) + math.sin(y * k * 2 - ph)
                 + 0.8 * math.sin((x + y) * k + ph * 2)
                 + 0.6 * math.sin((x - y * 2) * k - ph))
            if hell:
                if v < -1.75:
                    c = crust
                elif v < -1.3:
                    c = mix(crust, mid, 0.55)
                elif v > 2.0:
                    c = (255, 240, 170)
                elif v > 1.3:
                    c = mix(mid, hi, 0.7)
                else:
                    c = mix(deep, mid, 0.5 + 0.3 * math.sin(v))
            else:
                if v > 2.3:
                    c = (232, 246, 255)
                elif v > 1.8:
                    c = mix(mid, hi, 0.9)
                elif v > 1.15:
                    c = mix(mid, hi, 0.45)
                elif v < -1.6:
                    c = deep
                elif v < -0.9:
                    c = mix(deep, mid, 0.5)
                else:
                    c = mid
            s.fill(c, (x, y, 2, 2))
    return s


def make_glow(radius, color, strength=0.6):
    s = pygame.Surface((radius * 2, radius * 2))
    steps = max(8, radius // 2)
    for i in range(steps):
        r = int(radius * (1 - i / steps))
        k = ((i + 1) / steps) ** 2 * strength
        pygame.draw.circle(s, (int(color[0] * k), int(color[1] * k), int(color[2] * k)),
                           (radius, radius), r)
    return s


def make_light(theme: Theme):
    s = pygame.Surface((SCREEN_W * 2, SCREEN_H * 2), pygame.SRCALPHA)
    base = 178
    s.fill((*theme.ambient, base))
    radius, steps = 430, 86
    for i in range(steps):
        r = int(radius * (1 - i / steps))
        a = int(base * (r / radius) ** 1.5)
        pygame.draw.circle(s, (*theme.ambient, a), (SCREEN_W, SCREEN_H), r)
    return s.convert_alpha()


def make_vignette(strength=165):
    w, h = 96, 54
    s = pygame.Surface((w, h), pygame.SRCALPHA)
    for y in range(h):
        for x in range(w):
            dx = (x + 0.5) / w * 2 - 1
            dy = (y + 0.5) / h * 2 - 1
            d = math.sqrt(dx * dx * 0.7 + dy * dy)
            a = max(0.0, min(1.0, (d - 0.5) / 0.8))
            s.set_at((x, y), (0, 0, 0, int(strength * a * a)))
    return pygame.transform.smoothscale(s, (SCREEN_W, SCREEN_H))


def make_fog(color, w=420, h=190, maxa=30):
    s = blank(w, h)
    steps = 22
    for i in range(steps):
        k = (i + 1) / steps
        iw, ih = int(w * (1 - i / steps)), int(h * (1 - i / steps))
        if iw < 2 or ih < 2:
            break
        pygame.draw.ellipse(s, (*color, int(maxa * k * k)), ((w - iw) // 2, (h - ih) // 2, iw, ih))
    return s


def region_tint(base, center, w, h, color, alpha_max=235, steps=56):
    """Colour-grade one soft-edged elliptical region of a surface (multiply tint)."""
    W, H = base.get_size()
    layer = base.copy()
    layer.fill(color, special_flags=pygame.BLEND_RGB_MULT)
    layer = layer.convert_alpha()
    soft = blank(w, h)
    for i in range(steps):
        iw, ih = int(w * (1 - i / steps)), int(h * (1 - i / steps))
        if iw < 2 or ih < 2:
            break
        a = int(alpha_max * ((i + 1) / steps) ** 0.8)
        pygame.draw.ellipse(soft, (255, 255, 255, a), ((w - iw) // 2, (h - ih) // 2, iw, ih))
    mask = pygame.Surface((W, H), pygame.SRCALPHA)
    mask.fill((255, 255, 255, 0))
    mask.blit(soft, (center[0] - w // 2, center[1] - h // 2))
    layer.blit(mask, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
    base.blit(layer, (0, 0))


# Outline of the Lich King's snowy mountains + storm sky on the world map, as fractions of
# the screen (x, y).  Everything inside becomes lava; edit the points to reshape the area.
LICH_LAVA_POLY = [
    (0.311, 0.000), (0.766, 0.000), (0.766, 0.123), (0.717, 0.204),
    (0.675, 0.253), (0.620, 0.290), (0.536, 0.321), (0.467, 0.333),
    (0.418, 0.284), (0.384, 0.235), (0.342, 0.185), (0.318, 0.123),
]


def region_lava(base, poly):
    """Turn the area inside `poly` (screen fractions) into a volcanic underworld:
    bright snow/ice becomes glowing lava, dark rock becomes charred black."""
    W, H = base.get_size()
    gray = None
    try:
        gray = pygame.transform.grayscale(base.copy()).convert()
    except AttributeError:
        pass
    if gray is None:                                  # very old pygame: plain red multiply
        lava = base.copy()
        lava.fill((255, 90, 50), special_flags=pygame.BLEND_RGB_MULT)
    else:
        gray.blit(gray.copy(), (0, 0), special_flags=pygame.BLEND_RGB_MULT)    # contrast
        hot = gray.copy()
        hot.blit(gray, (0, 0), special_flags=pygame.BLEND_RGB_MULT)            # brightest only
        hot.fill((255, 200, 80), special_flags=pygame.BLEND_RGB_MULT)          # yellow-hot cores
        gray.fill((255, 96, 22), special_flags=pygame.BLEND_RGB_MULT)          # orange lava
        gray.blit(hot, (0, 0), special_flags=pygame.BLEND_RGB_ADD)
        gray.fill((34, 5, 3), special_flags=pygame.BLEND_RGB_ADD)              # dark red ash floor
        lava = gray
    lava = lava.convert_alpha()

    # soft mask: draw the polygon tiny, then scale up in two steps for feathered edges
    tw, th = W // 16, H // 16
    small = pygame.Surface((tw, th), pygame.SRCALPHA)
    small.fill((255, 255, 255, 0))
    pygame.draw.polygon(small, (255, 255, 255, 255),
                        [(int(x * tw), int(y * th)) for x, y in poly])
    mid = pygame.transform.smoothscale(small, (W // 4, H // 4))
    mask = pygame.transform.smoothscale(mid, (W, H))
    lava.blit(mask, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
    base.blit(lava, (0, 0))


def draw_flame(surf, x, y, t, seed, size=1.0):
    a = math.sin(t * 13 + seed) * 1.6
    b = math.sin(t * 9 + seed * 2) * 1.2
    h = (11 + 2.5 * math.sin(t * 11 + seed * 3)) * size
    w = 5 * size
    pygame.draw.polygon(surf, (214, 62, 22), [
        (x - w * 1.15, y), (x - w * 0.7 + b, y - h * 0.5), (x + a, y - h * 1.12),
        (x + w * 0.7 + b, y - h * 0.5), (x + w * 1.15, y)])
    pygame.draw.polygon(surf, (255, 112, 28), [
        (x - w, y), (x - w * 0.6 + b, y - h * 0.55), (x + a, y - h),
        (x + w * 0.6 + b, y - h * 0.55), (x + w, y)])
    pygame.draw.polygon(surf, (255, 188, 70), [
        (x - w * 0.7, y), (x + a * 0.7, y - h * 0.8), (x + w * 0.7, y)])
    pygame.draw.polygon(surf, (255, 240, 170), [
        (x - w * 0.4, y), (x + a * 0.4, y - h * 0.55), (x + w * 0.4, y)])


def draw_sparks(surf, x, y, t, seed, n=2, rise=26):
    for j in range(n):
        ph = (t * 0.9 + j / n + (hash2(seed, j) % 100) / 100) % 1.0
        sx = x + math.sin(ph * 7 + j * 2 + seed) * 4
        sy = y - ph * rise
        surf.fill(shade((255, 190, 90), 1 - ph), (int(sx), int(sy), 2, 2))


# --------------------------------------------------------------------------
# Props
# --------------------------------------------------------------------------

def make_tree(rng):
    w, h = 64, 88
    s = blank(w, h)
    cx = w // 2
    soft_shadow(s, cx + 4, h - 6, 22, 7, 90)
    bark, bark_d, bark_l = (78, 52, 34), (46, 31, 22), (116, 82, 54)
    pygame.draw.polygon(s, bark, [(cx - 13, h - 5), (cx - 6, h - 15), (cx + 6, h - 15),
                                  (cx + 13, h - 5), (cx + 5, h - 9), (cx - 5, h - 9)])
    pygame.draw.rect(s, bark, (cx - 6, h - 46, 12, 34))
    pygame.draw.rect(s, bark_l, (cx - 6, h - 46, 3, 34))
    pygame.draw.rect(s, bark_d, (cx + 3, h - 46, 3, 34))
    for y in range(h - 44, h - 14, 5):
        x = cx - 4 + rng.randrange(0, 5)
        pygame.draw.line(s, bark_d, (x, y), (x + rng.choice((-1, 0, 1)), y + 3))
    pygame.draw.line(s, bark, (cx + 5, h - 34), (cx + 14, h - 44), 3)
    pygame.draw.line(s, bark, (cx - 5, h - 30), (cx - 13, h - 40), 3)
    blobs = [(0, -66, 17), (-15, -56, 15), (15, -56, 15),
             (0, -49, 19), (-12, -38, 13), (12, -38, 13), (0, -58, 14)]
    layers = [((18, 42, 30), (0, 0), 0), ((34, 80, 44), (-2, -2), 2),
              ((60, 118, 58), (-3, -4), 5), ((100, 158, 76), (-5, -7), 9)]
    for col, off, sh in layers:
        for bx, by, br in blobs:
            j = rng.randrange(-1, 2)
            pygame.draw.circle(s, col, (cx + bx + off[0] + j, h + by + off[1]), max(3, br - sh))
    for _ in range(120):
        x, y = rng.randrange(2, w - 2), rng.randrange(4, h - 30)
        if s.get_at((x, y))[3] > 0:
            if y < h * 0.4:
                s.fill((136, 190, 100), (x, y, 2, 1))
            elif rng.random() < 0.5:
                s.fill((18, 42, 30), (x, y, 2, 1))
            else:
                s.fill((84, 140, 66), (x, y, 2, 1))
    return s


def make_bush(rng):
    w, h = 32, 24
    s = blank(w, h)
    soft_shadow(s, 16, h - 4, 14, 4, 80)
    for col, sh in (((22, 54, 34), 0), ((38, 88, 48), 1), ((64, 120, 60), 3), ((96, 156, 76), 5)):
        for bx, by, br in ((10, 14, 8), (22, 14, 8), (16, 10, 9)):
            pygame.draw.circle(s, col, (bx - sh // 2, by - sh // 2), max(3, br - sh))
    for _ in range(40):
        x, y = rng.randrange(3, w - 3), rng.randrange(3, h - 6)
        if s.get_at((x, y))[3] > 0:
            s.fill(rng.choice(((126, 180, 92), (22, 54, 34))), (x, y, 2, 1))
    for _ in range(5):
        x, y = rng.randrange(5, w - 5), rng.randrange(5, h - 7)
        if s.get_at((x, y))[3] > 0:
            s.fill((210, 66, 78), (x, y, 2, 2))
            s.set_at((x, y), (255, 160, 160))
    return s


def make_rock(rng, base, hi):
    w, h = 32, 24
    s = blank(w, h)
    soft_shadow(s, 16, h - 4, 13, 4, 90)
    j = rng.randrange(-2, 3)
    pts = [(3, h - 6), (6, 9), (14 + j, 3), (24, 7), (28, h - 8), (22, h - 4), (8, h - 4)]
    pygame.draw.polygon(s, base, pts)
    pygame.draw.polygon(s, hi, [(6, 9), (14 + j, 3), (24, 7), (16, 12)])
    pygame.draw.polygon(s, shade(base, 1.15), [(6, 9), (16, 12), (12, h - 6), (4, h - 7)])
    pygame.draw.polygon(s, shade(base, 0.65), [(28, h - 8), (22, h - 4), (14, h - 4), (18, 12)])
    pygame.draw.line(s, shade(base, 0.5), (14 + j, 5), (12, 13))
    pygame.draw.line(s, shade(base, 0.5), (12, 13), (15, 18))
    pygame.draw.polygon(s, shade(base, 0.45), pts, 1)
    for _ in range(4):
        s.fill((70, 120, 60), (rng.randrange(7, 22), rng.randrange(4, 9), 2, 1))
    return s


def make_pillar(rng, wall, hi, dark, w=26, h=58, broken=False, moss=None, glow=None):
    s = blank(w, h)
    soft_shadow(s, w // 2, h - 4, w // 2 - 1, 4, 90)
    pygame.draw.rect(s, dark, (1, h - 9, w - 2, 7))
    pygame.draw.rect(s, wall, (2, h - 11, w - 4, 4))
    pygame.draw.line(s, hi, (2, h - 11), (w - 3, h - 11))
    top = rng.randrange(18, 30) if broken else 10
    pygame.draw.rect(s, wall, (5, top, w - 10, h - top - 10))
    pygame.draw.rect(s, hi, (5, top, 4, h - top - 10))
    pygame.draw.rect(s, dark, (w - 9, top, 4, h - top - 10))
    pygame.draw.line(s, shade(wall, 0.8), (w // 2, top), (w // 2, h - 12))
    pygame.draw.line(s, shade(hi, 1.1), (7, top), (7, h - 12))
    for y in range(top + 7, h - 12, 9):
        pygame.draw.line(s, dark, (5, y), (w - 6, y))
    if broken:
        pygame.draw.polygon(s, wall, [(5, top + 2), (5, top), (9, top - 5), (13, top),
                                      (17, top - 7), (w - 6, top - 1), (w - 6, top + 2)])
        pygame.draw.polygon(s, hi, [(5, top), (9, top - 5), (11, top)])
    else:
        pygame.draw.rect(s, wall, (1, 3, w - 2, 7))
        pygame.draw.line(s, hi, (1, 3), (w - 2, 3))
        pygame.draw.rect(s, dark, (1, 9, w - 2, 1))
        pygame.draw.line(s, shade(wall, 0.7), (4, 6), (w - 5, 6))
    if moss:
        for _ in range(22):
            s.fill(shade(moss, rng.uniform(0.8, 1.25)),
                   (rng.randrange(5, w - 8), rng.randrange(top, h - 14), rng.randrange(2, 4), 2))
    if glow:
        for _ in range(3):
            x, y = rng.randrange(8, w - 8), rng.randrange(top + 2, h - 22)
            pygame.draw.line(s, glow, (x, y), (x + rng.randrange(-2, 3), y + rng.randrange(5, 10)))
    return s


def make_statue(rng, wall, hi, dark, moss=None):
    w, h = 28, 62
    s = blank(w, h)
    cx = w // 2
    soft_shadow(s, cx, h - 4, 12, 4, 90)
    pygame.draw.rect(s, dark, (3, h - 12, w - 6, 9))
    pygame.draw.rect(s, wall, (4, h - 13, w - 8, 9))
    pygame.draw.rect(s, hi, (4, h - 13, w - 8, 2))
    pygame.draw.rect(s, shade(wall, 0.8), (6, h - 20, w - 12, 8))
    pygame.draw.rect(s, hi, (6, h - 20, w - 12, 1))
    pygame.draw.polygon(s, wall, [(cx - 6, h - 20), (cx - 5, h - 36), (cx - 3, h - 42),
                                  (cx + 3, h - 42), (cx + 5, h - 36), (cx + 6, h - 20)])
    pygame.draw.polygon(s, shade(wall, 0.68), [(cx + 1, h - 20), (cx + 1, h - 42), (cx + 3, h - 42),
                                               (cx + 5, h - 36), (cx + 6, h - 20)])
    pygame.draw.polygon(s, hi, [(cx - 6, h - 20), (cx - 5, h - 36), (cx - 3, h - 42),
                                (cx - 2, h - 42), (cx - 3, h - 20)])
    pygame.draw.line(s, shade(wall, 0.6), (cx - 4, h - 33), (cx + 4, h - 22))
    pygame.draw.circle(s, wall, (cx, h - 47), 5)
    pygame.draw.circle(s, hi, (cx - 1, h - 48), 2)
    pygame.draw.line(s, wall, (cx + 5, h - 38), (cx + 9, h - 48), 3)
    pygame.draw.line(s, hi, (cx + 9, h - 48), (cx + 9, h - 60), 2)
    pygame.draw.rect(s, shade(wall, 0.8), (cx + 6, h - 50, 7, 2))
    pygame.draw.line(s, shade(wall, 0.8), (cx - 5, h - 38), (cx - 8, h - 28), 3)
    if moss:
        for _ in range(18):
            s.fill(shade(moss, rng.uniform(0.8, 1.25)),
                   (rng.randrange(4, w - 6), rng.randrange(h - 44, h - 12), rng.randrange(2, 4), 2))
    return s


def make_brazier():
    w, h = 28, 38
    s = blank(w, h)
    soft_shadow(s, 14, h - 4, 11, 4, 90)
    pygame.draw.polygon(s, (52, 48, 58), [(6, h - 4), (10, h - 16), (18, h - 16), (22, h - 4)])
    pygame.draw.line(s, (92, 88, 100), (10, h - 16), (7, h - 5))
    pygame.draw.rect(s, (36, 34, 42), (5, h - 5, 18, 3))
    pygame.draw.polygon(s, (62, 58, 68), [(3, 20), (25, 20), (20, 28), (8, 28)])
    pygame.draw.line(s, (110, 106, 120), (3, 20), (24, 20))
    pygame.draw.ellipse(s, (28, 26, 32), (3, 14, 22, 9))
    pygame.draw.ellipse(s, (206, 92, 30), (6, 15, 16, 5))
    pygame.draw.ellipse(s, (255, 170, 60), (9, 16, 10, 3))
    return s


def make_barrel():
    w, h = 24, 28
    s = blank(w, h)
    soft_shadow(s, 12, h - 4, 10, 4, 90)
    wood = (104, 72, 44)
    pygame.draw.ellipse(s, shade(wood, 0.7), (2, h - 12, 20, 9))
    pygame.draw.rect(s, wood, (2, 8, 20, h - 16))
    pygame.draw.rect(s, shade(wood, 1.2), (2, 8, 5, h - 16))
    pygame.draw.rect(s, shade(wood, 0.75), (17, 8, 5, h - 16))
    for x in (8, 12, 16):
        pygame.draw.line(s, shade(wood, 0.8), (x, 9), (x, h - 10))
    pygame.draw.ellipse(s, shade(wood, 1.1), (2, 3, 20, 10))
    pygame.draw.ellipse(s, shade(wood, 0.8), (5, 5, 14, 6))
    pygame.draw.ellipse(s, shade(wood, 0.6), (5, 5, 14, 6), 1)
    for y in (12, h - 13):
        pygame.draw.line(s, (50, 48, 56), (2, y), (21, y), 2)
        pygame.draw.line(s, (96, 94, 108), (2, y - 1), (21, y - 1))
    return s


def make_crate():
    w, h = 26, 26
    s = blank(w, h)
    soft_shadow(s, 13, h - 4, 11, 4, 90)
    wood = (112, 80, 48)
    pygame.draw.rect(s, wood, (2, 3, 22, 20))
    for y in (8, 13, 18):
        pygame.draw.line(s, shade(wood, 0.7), (3, y), (22, y))
    pygame.draw.rect(s, shade(wood, 0.6), (2, 3, 22, 20), 2)
    pygame.draw.line(s, shade(wood, 0.65), (4, 5), (21, 20), 2)
    pygame.draw.line(s, shade(wood, 0.65), (21, 5), (4, 20), 2)
    pygame.draw.line(s, shade(wood, 1.3), (3, 3), (23, 3))
    for x, y in ((4, 5), (20, 5), (4, 20), (20, 20)):
        s.fill((150, 146, 158), (x, y, 2, 2))
    return s


def make_chest():
    w, h = 28, 22
    s = blank(w, h)
    soft_shadow(s, 14, h - 3, 11, 3, 90)
    wood = (118, 78, 44)
    pygame.draw.rect(s, shade(wood, 0.65), (2, 10, 24, 10))
    pygame.draw.rect(s, wood, (3, 11, 22, 8))
    pygame.draw.rect(s, shade(wood, 1.2), (3, 11, 22, 2))
    pygame.draw.rect(s, shade(wood, 0.85), (2, 3, 24, 9),
                     border_top_left_radius=5, border_top_right_radius=5)
    pygame.draw.line(s, shade(wood, 1.3), (5, 4), (22, 4))
    for x in (6, 19):
        pygame.draw.rect(s, (60, 58, 68), (x, 3, 3, 17))
        pygame.draw.line(s, (130, 128, 144), (x, 4), (x, 19))
    pygame.draw.rect(s, (214, 176, 84), (12, 9, 4, 5))
    pygame.draw.rect(s, (60, 40, 20), (13, 11, 2, 2))
    return s


def make_gravestone(rng, wall, hi, dark, moss=None):
    w, h = 20, 28
    s = blank(w, h)
    soft_shadow(s, 10, h - 3, 8, 3, 90)
    pygame.draw.rect(s, dark, (3, 8, 14, h - 11), border_top_left_radius=7, border_top_right_radius=7)
    pygame.draw.rect(s, wall, (4, 8, 12, h - 12), border_top_left_radius=6, border_top_right_radius=6)
    pygame.draw.rect(s, hi, (4, 11, 2, h - 15))
    pygame.draw.line(s, dark, (10, 11), (10, 19))
    pygame.draw.line(s, dark, (7, 14), (13, 14))
    if moss:
        for _ in range(8):
            s.fill(moss, (rng.randrange(4, 15), rng.randrange(14, h - 6), 2, 2))
    return s


def make_stump(rng):
    w, h = 26, 22
    s = blank(w, h)
    soft_shadow(s, 13, h - 3, 10, 3, 90)
    bark, bd, bl = (78, 52, 34), (46, 31, 22), (116, 82, 54)
    pygame.draw.rect(s, bark, (5, 8, 16, h - 12))
    pygame.draw.ellipse(s, bark, (5, h - 9, 16, 7))
    pygame.draw.rect(s, bl, (5, 8, 4, h - 12))
    pygame.draw.rect(s, bd, (17, 8, 4, h - 12))
    pygame.draw.ellipse(s, (176, 138, 92), (4, 3, 18, 9))
    pygame.draw.ellipse(s, (146, 108, 70), (7, 5, 12, 5), 1)
    pygame.draw.ellipse(s, (146, 108, 70), (10, 6, 6, 3), 1)
    return s


def make_log(rng):
    w, h = 38, 20
    s = blank(w, h)
    soft_shadow(s, 19, h - 3, 16, 3, 90)
    bark, bd, bl = (78, 52, 34), (46, 31, 22), (116, 82, 54)
    pygame.draw.rect(s, bark, (5, 5, 30, 11), border_radius=5)
    pygame.draw.rect(s, bl, (6, 6, 28, 3), border_radius=2)
    for x in range(12, 34, 6):
        pygame.draw.line(s, bd, (x, 8), (x + rng.choice((-1, 0, 1)), 14))
    pygame.draw.ellipse(s, (176, 138, 92), (1, 4, 10, 12))
    pygame.draw.ellipse(s, (146, 108, 70), (3, 7, 6, 6), 1)
    for _ in range(8):
        s.fill((70, 120, 60), (rng.randrange(14, 33), rng.randrange(5, 8), 3, 2))
    return s


def make_spire(rng, t: Theme):
    w, h = 32, 58
    s = blank(w, h)
    soft_shadow(s, w // 2, h - 4, 13, 4, 100)
    lean = rng.randrange(-3, 4)
    pts = [(3, h - 5), (8, h - 26), (11, h - 38), (15 + lean, 4),
           (20, h - 36), (25, h - 24), (29, h - 5)]
    pygame.draw.polygon(s, shade(t.wall, 0.75), pts)
    pygame.draw.polygon(s, t.wall, [(3, h - 5), (8, h - 26), (11, h - 38),
                                    (15 + lean, 4), (16, h - 5)])
    pygame.draw.polygon(s, t.wall_dark, [(29, h - 5), (25, h - 24), (20, h - 36),
                                         (15 + lean, 4), (18, h - 5)])
    pygame.draw.line(s, t.wall_hi, (15 + lean, 4), (11, h - 38))
    for _ in range(3):
        x, y = rng.randrange(10, 22), rng.randrange(h - 34, h - 14)
        pygame.draw.line(s, t.accent, (x, y), (x + rng.randrange(-2, 3), y + rng.randrange(5, 10)))
        s.set_at((x, y), (255, 214, 120))
    return s


def make_crystal():
    w, h = 30, 40
    s = blank(w, h)
    soft_shadow(s, 15, h - 5, 12, 4, 100)
    pygame.draw.polygon(s, (54, 36, 34), [(2, h - 5), (6, h - 12), (24, h - 12), (28, h - 5)])
    for x, top, hw in ((8, 16, 5), (22, 14, 5), (15, 5, 6)):
        pygame.draw.polygon(s, (228, 98, 34), [(x - hw, h - 10), (x - hw + 1, top + 8),
                                              (x, top), (x + hw - 1, top + 8), (x + hw, h - 10)])
        pygame.draw.polygon(s, (255, 176, 70), [(x - hw, h - 10), (x - hw + 1, top + 8),
                                               (x, top), (x, h - 10)])
        pygame.draw.line(s, (255, 232, 150), (x - 1, top + 3), (x - 1, h - 16))
        s.set_at((x, top + 1), (255, 255, 230))
    return s


def make_obelisk(t: Theme):
    w, h = 26, 66
    s = blank(w, h)
    soft_shadow(s, w // 2, h - 4, 11, 4, 100)
    pygame.draw.polygon(s, shade(t.wall, 0.6), [(3, h - 4), (5, h - 10), (21, h - 10), (23, h - 4)])
    body = [(6, h - 10), (8, 10), (13, 2), (18, 10), (20, h - 10)]
    pygame.draw.polygon(s, t.wall, body)
    pygame.draw.polygon(s, shade(t.wall, 1.2), [(8, 10), (13, 2), (13, h - 10), (6, h - 10)])
    pygame.draw.polygon(s, shade(t.wall, 0.55), [(13, 2), (18, 10), (20, h - 10), (13, h - 10)])
    for y in range(16, h - 18, 9):
        pygame.draw.line(s, t.accent, (10, y), (16, y))
        pygame.draw.line(s, (255, 220, 140), (12, y + 2), (12, y + 5))
        s.set_at((15, y + 4), (255, 240, 180))
    return s


def make_skullpile(rng):
    w, h = 26, 20
    s = blank(w, h)
    soft_shadow(s, 13, h - 4, 11, 4, 90)
    bone, bd = (214, 200, 172), (150, 136, 112)
    for x0 in (4, 12, 18):
        pygame.draw.line(s, bd, (x0, h - 4), (x0 + 5, h - 6), 2)
    for cx, cy, r in ((8, 13, 5), (18, 13, 5), (13, 8, 6)):
        pygame.draw.circle(s, bd, (cx, cy + 1), r)
        pygame.draw.circle(s, bone, (cx, cy), r)
        s.fill((30, 18, 18), (cx - 3, cy - 1, 2, 3))
        s.fill((30, 18, 18), (cx + 1, cy - 1, 2, 3))
        s.fill(bd, (cx - 1, cy + 3, 3, 2))
    return s


def make_mushrooms(rng):
    s = blank(18, 12)
    for x, hh in ((4, 5), (11, 7)):
        pygame.draw.rect(s, (226, 214, 190), (x, 12 - hh, 2, hh))
        pygame.draw.ellipse(s, (196, 60, 62), (x - 3, 12 - hh - 3, 8, 5))
        s.fill((250, 240, 230), (x - 1, 12 - hh - 2, 1, 1))
        s.fill((250, 240, 230), (x + 2, 12 - hh - 1, 1, 1))
    return s


def make_flowers(rng):
    s = blank(20, 12)
    for _ in range(6):
        x, y = rng.randrange(1, 18), rng.randrange(4, 10)
        pygame.draw.line(s, (50, 110, 56), (x, y), (x, y + 2))
        s.fill(rng.choice(((244, 240, 210), (240, 206, 96), (206, 156, 226), (240, 130, 140))),
               (x - 1, y - 1, 2, 2))
    return s


def make_grass_tuft(rng):
    s = blank(14, 10)
    for x in range(2, 13, 2):
        hgt = rng.randrange(4, 9)
        c = shade((70, 128, 62), rng.uniform(0.8, 1.3))
        pygame.draw.line(s, c, (x, 9), (x + rng.choice((-2, -1, 0, 1, 2)), 9 - hgt))
    return s


def make_moss(rng, col):
    s = blank(26, 14)
    for _ in range(80):
        x, y = rng.randrange(1, 24), rng.randrange(1, 12)
        if ((x - 13) / 12) ** 2 + ((y - 7) / 6) ** 2 <= 1:
            s.fill((*shade(col, rng.uniform(0.75, 1.3)), 200), (x, y, 2, 2))
    return s


def make_puddle(t: Theme):
    s = blank(26, 12)
    pygame.draw.ellipse(s, (*shade(t.liquid, 0.8), 150), (0, 1, 26, 10))
    pygame.draw.ellipse(s, (*t.liquid_hi, 90), (3, 2, 14, 4))
    pygame.draw.ellipse(s, (*t.liquid_hi, 170), (6, 3, 5, 2))
    return s


def make_scorch(rng):
    s = blank(30, 20)
    pygame.draw.ellipse(s, (8, 4, 4, 120), (2, 3, 26, 14))
    pygame.draw.ellipse(s, (8, 4, 4, 150), (7, 6, 16, 8))
    for _ in range(7):
        x, y = rng.randrange(6, 24), rng.randrange(5, 14)
        s.fill((255, 160, 70, 210), (x, y, 1, 1))
    return s


def make_bones(rng):
    s = blank(24, 12)
    bone = (214, 200, 172)
    pygame.draw.line(s, bone, (3, 8), (19, 4), 2)
    pygame.draw.circle(s, bone, (3, 8), 2)
    pygame.draw.circle(s, bone, (19, 4), 2)
    pygame.draw.line(s, shade(bone, 0.8), (6, 3), (17, 9), 2)
    pygame.draw.circle(s, shade(bone, 0.8), (6, 3), 2)
    pygame.draw.circle(s, shade(bone, 0.8), (17, 9), 2)
    return s


def make_rubble(rng, base, hi):
    s = blank(28, 16)
    for _ in range(7):
        cx, cy = rng.randrange(4, 24), rng.randrange(4, 12)
        r = rng.randrange(2, 5)
        pts = [(cx - r, cy + 2), (cx - r + 1, cy - 1), (cx + 1, cy - r), (cx + r, cy - 1), (cx + r - 1, cy + 2)]
        pygame.draw.polygon(s, shade(base, rng.uniform(0.75, 1.15)), pts)
        pygame.draw.line(s, hi, pts[1], pts[2])
    return s


def make_floor_cracks(rng, color, core=None):
    s = blank(30, 16)
    x, y = 2, rng.randrange(4, 12)
    pts = [(x, y)]
    while x < 26:
        x += rng.randrange(3, 7)
        y = max(2, min(13, y + rng.randrange(-4, 5)))
        pts.append((x, y))
    pygame.draw.lines(s, color, False, pts, 2 if core else 1)
    if core:
        pygame.draw.lines(s, core, False, pts, 1)
    return s


def make_banner(t: Theme):
    s = blank(16, 30)
    if t.key == "stone":
        pygame.draw.polygon(s, (122, 30, 46), [(1, 0), (15, 0), (15, 26), (8, 21), (1, 26)])
        pygame.draw.polygon(s, (88, 20, 34), [(8, 0), (15, 0), (15, 26), (8, 21)])
        pygame.draw.rect(s, (206, 170, 80), (1, 0, 14, 3))
        pygame.draw.circle(s, (206, 170, 80), (8, 11), 3, 1)
        pygame.draw.line(s, (206, 170, 80), (8, 7), (8, 15))
        pygame.draw.line(s, (206, 170, 80), (5, 11), (11, 11))
        s.fill((206, 170, 80), (7, 22, 2, 2))
    elif t.key == "forest":
        for x, ln in ((3, 22), (8, 28), (12, 16)):
            pygame.draw.line(s, (40, 96, 48), (x, 0), (x + 1, ln), 2)
            for y in range(4, ln, 5):
                pygame.draw.circle(s, (66, 130, 62), (x + (y // 5) % 2 * 2 - 1, y), 2)
                s.set_at((x + (y // 5) % 2 * 2 - 1, y - 1), (110, 180, 88))
    else:
        pts = [(8, 0), (5, 8), (10, 15), (7, 26)]
        pygame.draw.lines(s, (110, 40, 24), False, pts, 4)
        pygame.draw.lines(s, t.accent, False, pts, 2)
        pygame.draw.lines(s, (255, 214, 110), False, pts, 1)
    return s


def outline(s, color=(12, 9, 16, 255)):
    w, h = s.get_size()
    sil = pygame.mask.from_surface(s).to_surface(setcolor=color, unsetcolor=(0, 0, 0, 0))
    out = blank(w + 2, h + 2)
    for ox, oy in ((0, 1), (2, 1), (1, 0), (1, 2)):
        out.blit(sil, (ox, oy))
    out.blit(s, (1, 1))
    return out


def make_coins(rng):
    s = blank(16, 10)
    for _ in range(rng.randrange(3, 6)):
        x, y = rng.randrange(1, 13), rng.randrange(1, 7)
        s.fill((156, 112, 32), (x, y + 1, 3, 2))
        s.fill((248, 206, 84), (x, y, 3, 2))
        s.fill((255, 244, 190), (x, y, 1, 1))
    return s


def make_webs():
    left = blank(16, 16)
    c = (226, 226, 236, 150)
    for end in ((15, 0), (15, 6), (12, 12), (6, 15), (0, 15)):
        pygame.draw.line(left, c, (0, 0), end)
    for r in (5, 9, 13):
        pygame.draw.lines(left, c, False, [(r, 0), (int(r * 0.72), int(r * 0.72)), (0, r)])
    return left.convert_alpha(), pygame.transform.flip(left, True, False).convert_alpha()


def make_carpets(t: Theme):
    rng = random.Random(404)
    if t.key == "stone":
        band, trim = (116, 28, 44), (208, 170, 80)
    elif t.key == "forest":
        band, trim = (112, 88, 60), None
    else:
        band, trim = (38, 22, 22), t.accent
    h = blank(TILE, TILE)
    h.fill(shade(band, 0.7), (0, 4, TILE, 16))
    h.fill(band, (0, 5, TILE, 14))
    if trim:
        h.fill(trim, (0, 5, TILE, 1))
        h.fill(trim, (0, 18, TILE, 1))
        h.fill(shade(trim, 0.6), (0, 7, TILE, 1))
        h.fill(shade(trim, 0.6), (0, 16, TILE, 1))
        for x in (3, 15):
            pygame.draw.polygon(h, shade(trim, 0.8), [(x, 12), (x + 3, 9), (x + 6, 12), (x + 3, 15)])
    else:
        for _ in range(26):
            h.fill(shade(band, rng.uniform(0.75, 1.25)), (rng.randrange(TILE), rng.randrange(6, 18), 1, 1))
    v = pygame.transform.rotate(h, 90)
    c = blank(TILE, TILE)
    c.blit(h, (0, 0))
    c.blit(v, (0, 0))
    c.fill(band, (5, 5, 14, 14))
    if trim:
        pygame.draw.polygon(c, shade(trim, 0.9), [(12, 7), (17, 12), (12, 17), (7, 12)])
        pygame.draw.polygon(c, band, [(12, 10), (14, 12), (12, 14), (10, 12)])
    return {1: h.convert_alpha(), 2: v.convert_alpha(), 3: c.convert_alpha()}


# --------------------------------------------------------------------------
# Art cache
# --------------------------------------------------------------------------

class Art:
    cache: dict[str, "Art"] = {}

    @classmethod
    def get(cls, theme: Theme) -> "Art":
        if theme.key not in cls.cache:
            cls.cache[theme.key] = Art(theme)
        return cls.cache[theme.key]

    def __init__(self, t: Theme):
        self.t = t
        rng = random.Random(sum(ord(c) for c in t.key) * 7919)
        self.floor = [make_floor(t, rng, False) for _ in range(10)]
        self.path = [make_floor(t, rng, True) for _ in range(8)]
        self.face = [make_face(t, rng, False) for _ in range(10)]
        self.face_up = [make_face(t, rng, True) for _ in range(10)]
        self.pool_shadow = blank(TILE, 5)
        for i in range(5):
            self.pool_shadow.fill((0, 0, 0, int(120 * (1 - i / 5) ** 1.4)), (0, i, TILE, 1))
        self.cast: dict[int, pygame.Surface] = {}
        self.top = [make_top(t, rng) for _ in range(6)]
        self.liquid_frames = [make_liquid(t, f) for f in range(LIQUID_FRAMES)]
        self.liquid_cache: dict[tuple[int, int], pygame.Surface] = {}
        self.top_cache: dict[tuple[int, int], pygame.Surface] = {}
        self.shadow: dict[int, pygame.Surface] = {}
        self.blend: dict[int, pygame.Surface] = {}
        self.build_shadows()
        self.build_blend()
        self.banner = make_banner(t).convert_alpha()
        self.light = make_light(t)
        self.torch_glows = [make_glow(r, t.glow, 0.62) for r in (96, 104, 112)]
        self.crystal_glow = make_glow(84, (255, 140, 60), 0.6)
        self.lantern_glows = [make_glow(r, (255, 214, 150), 0.42) for r in (116, 120, 124)]
        self.lava_glow = make_glow(42, t.liquid_hi, 0.4)
        self.entry_glow = make_glow(100, (70, 150, 255), 0.55)
        self.carpet = make_carpets(t)
        self.web_l, self.web_r = make_webs()
        self.props: list[tuple[str, pygame.Surface, int]] = []
        self.decals: list[tuple[pygame.Surface, int]] = []
        self.build_sprites(rng)

    def build_shadows(self):
        n = blank(TILE, 20)
        for i in range(20):
            n.fill((0, 0, 0, int(135 * (1 - i / 20) ** 1.6)), (0, i, TILE, 1))
        w = blank(8, TILE)
        for i in range(8):
            w.fill((0, 0, 0, int(80 * (1 - i / 8) ** 1.5)), (i, 0, 1, TILE))
        e = pygame.transform.flip(w, True, False)
        so = blank(TILE, 5)
        for i in range(5):
            so.fill((0, 0, 0, int(70 * (i / 4) ** 1.5)), (0, i, TILE, 1))
        for m in range(16):
            sf = blank(TILE, TILE)
            if m & 1:
                sf.blit(n, (0, 0))
            if m & 2:
                sf.blit(w, (0, 0))
            if m & 4:
                sf.blit(e, (TILE - 8, 0))
            if m & 8:
                sf.blit(so, (0, TILE - 5))
            self.shadow[m] = sf.convert_alpha()

    def build_blend(self):
        """Soft fringes where a path tile meets the surrounding floor."""
        t = self.t
        for m in range(1, 16):
            s = blank(TILE, TILE)
            rng = random.Random(m * 31 + 7)
            for bit, side in ((1, "n"), (2, "s"), (4, "w"), (8, "e")):
                if not m & bit:
                    continue
                for i in range(TILE):
                    depth = rng.randrange(3, 6)
                    for d in range(depth):
                        a = int(215 * (1 - d / depth) ** 1.3)
                        if side == "n":
                            p = (i, d)
                        elif side == "s":
                            p = (i, TILE - 1 - d)
                        elif side == "w":
                            p = (d, i)
                        else:
                            p = (TILE - 1 - d, i)
                        if s.get_at(p)[3] >= a:
                            continue
                        f = rng.uniform(0.9, 1.25) if t.key == "forest" else rng.uniform(0.7, 0.9)
                        s.set_at(p, (*shade(t.floor_alt if t.key == "forest" else t.floor, f), a))
            self.blend[m] = s.convert_alpha()

    def build_sprites(self, rng: random.Random):
        t = self.t
        P, D = self.props, self.decals
        if t.key == "forest":
            for _ in range(3):
                P.append(("tree", make_tree(rng), 5))
            for _ in range(2):
                P.append(("bush", make_bush(rng), 3))
            for _ in range(2):
                P.append(("rock", make_rock(rng, (104, 106, 98), (146, 150, 138)), 2))
            for broken in (True, True, False):
                P.append(("ruin", make_pillar(rng, t.wall, t.wall_hi, t.wall_dark,
                                              broken=broken, moss=(70, 120, 60)), 1))
            P.append(("stump", make_stump(rng), 2))
            P.append(("log", make_log(rng), 2))
            P.append(("statue", make_statue(rng, t.wall, t.wall_hi, t.wall_dark, (70, 120, 60)), 1))
            P.append(("grave", make_gravestone(rng, t.wall, t.wall_hi, t.wall_dark, (70, 120, 60)), 1))
            D.extend([(make_mushrooms(rng), 2), (make_flowers(rng), 5), (make_flowers(rng), 4),
                      (make_grass_tuft(rng), 6), (make_grass_tuft(rng), 5),
                      (make_moss(rng, (70, 120, 60)), 3),
                      (make_rubble(rng, (106, 108, 98), (150, 152, 140)), 2)])
        elif t.key == "stone":
            for broken in (False, False, True):
                P.append(("pillar", make_pillar(rng, t.wall, t.wall_hi, t.wall_dark,
                                                broken=broken), 3))
            P.append(("brazier", make_brazier(), 2))
            for _ in range(2):
                P.append(("barrel", make_barrel(), 2))
            for _ in range(2):
                P.append(("crate", make_crate(), 2))
            P.append(("statue", make_statue(rng, t.wall, t.wall_hi, t.wall_dark), 2))
            P.append(("chest", make_chest(), 1))
            D.extend([(make_rubble(rng, t.wall, t.wall_hi), 4), (make_rubble(rng, t.wall, t.wall_hi), 3),
                      (make_floor_cracks(rng, shade(t.floor, 0.55)), 4),
                      (make_floor_cracks(rng, shade(t.floor, 0.5)), 3),
                      (make_puddle(t), 2), (make_bones(rng), 1),
                      (make_moss(rng, (60, 96, 70)), 2)])
        else:
            for _ in range(3):
                P.append(("spire", make_spire(rng, t), 4))
            for _ in range(2):
                P.append(("crystal", make_crystal(), 2))
            P.append(("pillar", make_pillar(rng, t.wall, t.wall_hi, t.wall_dark,
                                            broken=True, glow=t.accent), 2))
            P.append(("obelisk", make_obelisk(t), 2))
            P.append(("skulls", make_skullpile(rng), 2))
            P.append(("brazier", make_brazier(), 1))
            D.extend([(make_rubble(rng, (70, 48, 44), (118, 70, 52)), 4),
                      (make_floor_cracks(rng, shade(t.accent, 0.7), (255, 196, 96)), 4),
                      (make_floor_cracks(rng, shade(t.floor, 0.5)), 3),
                      (make_scorch(rng), 3), (make_bones(rng), 2)])
        if t.key != "hell":
            D.append((make_coins(rng), 3))
        self.props = [(k, outline(s), w) for k, s, w in P]
        self.decals = [(s.convert_alpha(), w) for s, w in D]
        a = {"forest": 70, "stone": 80, "hell": 64}[t.key]
        self.cast = {id(sp): make_cast_shadow(sp, a) for _k, sp, _w in self.props}

    def liquid(self, frame: int, mask: int):
        key = (frame, mask)
        s = self.liquid_cache.get(key)
        if s is None:
            s = self.liquid_frames[frame].copy()
            rim = self.t.liquid_rim
            inner = mix(rim, self.t.liquid, 0.5)
            hell = self.t.key == "hell"
            glint = (255, 206, 120) if hell else (200, 226, 240)
            if mask & 2:
                s.fill(rim, (0, TILE - 3, TILE, 3))
                s.fill(inner, (0, TILE - 4, TILE, 1))
            if mask & 4:
                s.fill(rim, (0, 0, 3, TILE))
                s.fill(inner, (3, 0, 1, TILE))
            if mask & 8:
                s.fill(rim, (TILE - 3, 0, 3, TILE))
                s.fill(inner, (TILE - 4, 0, 1, TILE))
            if mask & 1:
                # far bank: you see the inner wall of the basin dropping to the liquid
                s.fill(shade(rim, 1.35), (0, 0, TILE, 1))
                vgrad(s, (0, 1, TILE, 5), shade(rim, 0.85), shade(rim, 0.4))
                for x in range(2, TILE, 8):
                    s.fill(shade(rim, 0.28), (x, 1, 1, 5))
                s.blit(self.pool_shadow, (0, 6))
                if hell:
                    s.fill((255, 170, 70), (0, 6, TILE, 1))
                else:
                    s.fill(glint, (0, 6, TILE, 1))
            self.liquid_cache[key] = s
        return s

    def top_tile(self, var: int, lip: int):
        key = (var, lip)
        s = self.top_cache.get(key)
        if s is None:
            s = self.top[var].copy()
            hi = shade(self.t.wall_hi, 0.75)
            lo = shade(hi, 0.6)
            if lip & 1:
                pygame.draw.line(s, hi, (0, 0), (TILE - 1, 0))
                pygame.draw.line(s, lo, (0, 1), (TILE - 1, 1))
            if lip & 2:
                pygame.draw.line(s, hi, (0, 0), (0, TILE - 1))
                pygame.draw.line(s, lo, (1, 0), (1, TILE - 1))
            if lip & 4:
                pygame.draw.line(s, hi, (TILE - 1, 0), (TILE - 1, TILE - 1))
                pygame.draw.line(s, lo, (TILE - 2, 0), (TILE - 2, TILE - 1))
            if lip & 8:
                # front edge of the wall cap: bright rim, stone lip, dark underside
                pygame.draw.line(s, shade(hi, 1.3), (0, TILE - 5), (TILE - 1, TILE - 5))
                s.fill(shade(self.t.wall, 1.0), (0, TILE - 4, TILE, 1))
                s.fill(shade(self.t.wall, 0.8), (0, TILE - 3, TILE, 2))
                s.fill(shade(self.t.wall_dark, 0.7), (0, TILE - 1, TILE, 1))
            self.top_cache[key] = s
        return s


# --------------------------------------------------------------------------
# Ambient layers
# --------------------------------------------------------------------------

class Motes:
    def __init__(self, theme: Theme, seed: int):
        rng = random.Random(seed)
        self.theme = theme
        self.items = [[rng.uniform(0, SCREEN_W), rng.uniform(0, SCREEN_H),
                       rng.uniform(0, 6.28), rng.uniform(0.6, 1.4)] for _ in range(52)]
        self.rng = rng
        self.halos = [make_glow(9, theme.mote, k) for k in (0.3, 0.55, 0.85)]

    def update(self, dt: float, dcx: float, dcy: float, t: float):
        k = self.theme.key
        for m in self.items:
            m[0] -= dcx * 0.85
            m[1] -= dcy * 0.85
            if k == "hell":
                m[1] -= 34 * m[3] * dt
                m[0] += math.sin(t * 2 + m[2]) * 14 * dt
            elif k == "forest":
                m[0] += math.sin(t * 0.9 + m[2]) * 18 * dt
                m[1] += math.cos(t * 0.7 + m[2]) * 12 * dt
            else:
                m[0] += math.sin(t * 0.5 + m[2]) * 6 * dt
                m[1] += 4 * m[3] * dt
            if m[0] < -6 or m[0] > SCREEN_W + 6 or m[1] < -6 or m[1] > SCREEN_H + 6:
                if k == "hell":
                    m[0], m[1] = self.rng.uniform(0, SCREEN_W), SCREEN_H + 4
                else:
                    m[0], m[1] = self.rng.uniform(0, SCREEN_W), self.rng.uniform(0, SCREEN_H)

    def draw(self, surf: pygame.Surface, t: float):
        col = self.theme.mote
        big = self.theme.key != "stone"
        for x, y, ph, sp in self.items:
            b = 0.5 + 0.5 * math.sin(t * 2.2 * sp + ph)
            if b < 0.15:
                continue
            if big:
                surf.blit(self.halos[min(2, int(b * 3))], (int(x) - 9, int(y) - 9),
                          special_flags=pygame.BLEND_RGB_ADD)
            pygame.draw.circle(surf, shade(col, 0.4 + 0.6 * b), (int(x), int(y)), 1)


class Fog:
    """Slow drifting haze sprites in screen space."""

    def __init__(self, theme: Theme, seed: int):
        rng = random.Random(seed * 3 + 1)
        col = {"forest": (190, 230, 200), "stone": (150, 160, 200), "hell": (255, 90, 40)}[theme.key]
        a = {"forest": 30, "stone": 26, "hell": 36}[theme.key]
        self.blobs = [make_fog(col, 420, 190, a), make_fog(col, 520, 230, a)]
        self.rng = rng
        self.items = [[rng.uniform(-300, SCREEN_W), rng.uniform(-60, SCREEN_H - 100),
                       rng.uniform(8, 22), rng.randrange(2)] for _ in range(7)]

    def update(self, dt: float, dcx: float, dcy: float):
        for m in self.items:
            m[0] += m[2] * dt - dcx * 0.6
            m[1] -= dcy * 0.6
            if m[0] > SCREEN_W + 40:
                m[0] = -540
                m[1] = self.rng.uniform(-60, SCREEN_H - 100)
            elif m[0] < -560:
                m[0] = SCREEN_W + 30
            if m[1] < -260:
                m[1] += SCREEN_H + 360
            elif m[1] > SCREEN_H + 100:
                m[1] -= SCREEN_H + 360

    def draw(self, surf: pygame.Surface):
        for x, y, _sp, k in self.items:
            surf.blit(self.blobs[k], (int(x), int(y)))


class Minimap:
    def __init__(self, dungeon: "Dungeon"):
        self.d = dungeon
        th = dungeon.theme
        rooms = dungeon.rooms
        x0 = max(0, min(r.x for r in rooms) - 3)
        y0 = max(0, min(r.y for r in rooms) - 3)
        x1 = min(MAP_W, max(r.right for r in rooms) + 3)
        y1 = min(MAP_H, max(r.bottom for r in rooms) + 3)
        self.box = pygame.Rect(x0, y0, x1 - x0, y1 - y0)
        self.w = 232
        self.h = int(self.w * self.box.h / self.box.w)
        if self.h > 170:
            self.h = 170
            self.w = int(170 * self.box.w / self.box.h)
        self.raw = blank(MAP_W, MAP_H)
        self.seen = bytearray(CELLS)
        self.scaled = None
        self.dirty = True
        self.last = None
        light = (230, 230, 230)
        self.colors = {
            FLOOR: mix(th.floor, light, 0.38),
            PATH: mix(th.path, light, 0.3),
            LIQUID: th.liquid_hi,
            TOP: shade(th.wall, 0.55),
            FACE: shade(th.wall_hi, 0.85),
            FACE_UP: shade(th.wall_hi, 0.7),
        }
        # the map draws itself as you explore: whole rooms when you walk in,
        # corridors only where you walk, plus a short stub past each doorway
        self.queued = bytearray(CELLS)
        self.pending: list[int] = []          # tiles waiting to be inked in, nearest first
        self.rate = 0.0                       # tiles per second for the current batch
        self.budget = 0.0
        self.fresh: list[tuple[int, float]] = []   # (tile, time painted) still in "wet ink" colour
        self.clock = 0.0
        self.ink = mix(th.accent, (255, 255, 255), 0.45)
        self.room_seen = [False] * len(rooms)
        self.mapped_bonus_given = False
        if MINIMAP_REVEAL_ALL:
            T = dungeon.tiles
            for i in range(CELLS):
                self.seen[i] = 1
                col = self.colors.get(T[i])
                if col:
                    self.raw.set_at((i % MAP_W, i // MAP_W), col)
            self.room_seen = [True] * len(rooms)
        else:
            sx, sy = dungeon.spawn
            self.reveal(int(sx // TILE), int(sy // TILE))
            self._paint(len(self.pending), 0.0, wet=False)     # the entrance is already on the map

    @property
    def rooms_found(self) -> int:
        return sum(self.room_seen)

    def _queue(self, tiles, ox, oy):
        new = []
        for x, y in tiles:
            if 0 <= x < MAP_W and 0 <= y < MAP_H:
                i = y * MAP_W + x
                if not self.queued[i]:
                    self.queued[i] = 1
                    new.append(i)
        if not new:
            return
        new.sort(key=lambda i: (i % MAP_W - ox) ** 2 + (i // MAP_W - oy) ** 2)
        self.pending += new
        self.rate = max(self.rate, len(self.pending) / 0.6, 240.0)

    def reveal(self, tx: int, ty: int):
        """Queue what the player can see from tile (tx, ty). Cheap; call every frame."""
        if MINIMAP_REVEAL_ALL or self.last == (tx, ty):
            return
        self.last = (tx, ty)
        d = self.d
        room = next((k for k, r in enumerate(d.rooms) if r.collidepoint(tx, ty)), None)
        if room is not None:
            if not self.room_seen[room]:
                self.room_seen[room] = True
                r = d.rooms[room].inflate(4, 4)
                self._queue(((x, y) for y in range(r.y, r.bottom) for x in range(r.x, r.right)), tx, ty)
                # a short stub past each doorway: you can see where exits lead off, not where to
                for (a, _b), (nx, ny, dx, dy) in getattr(d, "door_of", {}).items():
                    if a != room:
                        continue
                    stub = []
                    for step in range(5):
                        cx, cy = nx + dx * step, ny + dy * step
                        stub += [(cx + ox, cy + oy) for ox in range(-2, 3) for oy in range(-2, 3)]
                    self._queue(stub, tx, ty)
            return
        r = 3                                   # corridors: just around you
        self._queue(((x, y) for y in range(ty - r, ty + r + 1) for x in range(tx - r, tx + r + 1)
                     if (x - tx) ** 2 + (y - ty) ** 2 <= r * r + 1), tx, ty)

    def _paint(self, n: int, now: float, wet: bool = True):
        T = self.d.tiles
        for i in self.pending[:n]:
            self.seen[i] = 1
            col = self.colors.get(T[i])
            if col:
                self.raw.set_at((i % MAP_W, i // MAP_W), self.ink if wet else col)
                if wet:
                    self.fresh.append((i, now))
                self.dirty = True
        del self.pending[:n]

    def step(self, dt: float) -> bool:
        """Advance the drawing animation. Returns True once, when every room is mapped."""
        self.clock += dt
        if self.pending:
            self.budget += self.rate * dt
            n = int(self.budget)
            if n:
                self.budget -= n
                self._paint(n, self.clock)
        else:
            self.rate = self.budget = 0.0
        if self.fresh and self.clock - self.fresh[0][1] > 0.45:     # wet ink dries
            T = self.d.tiles
            keep = []
            for i, t0 in self.fresh:
                if self.clock - t0 > 0.45:
                    self.raw.set_at((i % MAP_W, i // MAP_W), self.colors[T[i]])
                    self.dirty = True
                else:
                    keep.append((i, t0))
            self.fresh = keep
        if not self.mapped_bonus_given and all(self.room_seen) and not self.pending:
            self.mapped_bonus_given = True
            return not MINIMAP_REVEAL_ALL
        return False

    def draw(self, surf, font, player, cam_x, cam_y, t, enc=None):
        if self.dirty or self.scaled is None:
            self.scaled = pygame.transform.smoothscale(
                self.raw.subsurface(self.box), (self.w, self.h))
            self.dirty = False
        th = self.d.theme
        pad, label_h = 8, 20
        panel = pygame.Rect(SCREEN_W - self.w - pad * 2 - 16, 14,
                            self.w + pad * 2, self.h + pad * 2 + label_h)
        draw_panel(surf, panel, th.accent, 225)
        mr = pygame.Rect(panel.x + pad, panel.y + pad, self.w, self.h)
        pygame.draw.rect(surf, (5, 5, 9), mr)
        surf.blit(self.scaled, mr.topleft)
        pygame.draw.rect(surf, shade(th.accent, 0.55), mr.inflate(2, 2), 1)

        sx = self.w / self.box.w
        sy = self.h / self.box.h
        surf.set_clip(mr)

        if enc is not None:
            pulse = 0.5 + 0.5 * math.sin(t * 5)
            for k, r in enumerate(self.d.rooms):
                st = enc.state[k]
                if st == "safe" or not self.room_seen[k]:      # undiscovered rooms stay hidden
                    continue
                mx = int(mr.x + (r.centerx - self.box.x) * sx)
                my = int(mr.y + (r.centery - self.box.y) * sy)
                if k == enc.boss_room and enc.boss_floor:        # boss chamber marker
                    if st in ("pending", "active"):
                        rad = int(6 + 3 * pulse)
                        pygame.draw.circle(surf, (0, 0, 0), (mx, my), rad + 2)
                        pygame.draw.circle(surf, (255, 70, 60), (mx, my), rad, 2)
                    elif st == "dormant":
                        pygame.draw.circle(surf, (130, 50, 50), (mx, my), 6, 1)
                    continue
                col = {"cleared": (110, 220, 130), "active": (255, 90, 80),
                       "pending": (240, 200, 90)}.get(st, (120, 120, 130))
                pygame.draw.circle(surf, (0, 0, 0), (mx, my), 4)
                pygame.draw.circle(surf, col, (mx, my), 3)

        inter = getattr(self.d, "interact", None)
        if inter is not None:
            for tx, ty, kind in inter.map_markers():
                if not self.seen[int(ty) * MAP_W + int(tx)]:
                    continue
                mx = int(mr.x + (tx - self.box.x) * sx)
                my = int(mr.y + (ty - self.box.y) * sy)
                if kind == "key":
                    pygame.draw.circle(surf, (0, 0, 0), (mx - 2, my), 4)
                    pygame.draw.circle(surf, (255, 214, 90), (mx - 2, my), 3, 2)
                    pygame.draw.line(surf, (255, 214, 90), (mx + 1, my), (mx + 6, my), 2)
                elif kind == "seal":
                    pts = [(mx, my - 5), (mx + 5, my), (mx, my + 5), (mx - 5, my)]
                    pygame.draw.polygon(surf, (190, 130, 255), pts)
                    pygame.draw.polygon(surf, (0, 0, 0), pts, 1)
                elif kind == "font":
                    pygame.draw.rect(surf, (0, 0, 0), (mx - 4, my - 1, 9, 4))
                    pygame.draw.rect(surf, (0, 0, 0), (mx - 1, my - 4, 4, 9))
                    pygame.draw.line(surf, (110, 200, 255), (mx - 3, my + 1), (mx + 3, my + 1), 2)
                    pygame.draw.line(surf, (110, 200, 255), (mx, my - 3), (mx, my + 3), 2)
                elif kind == "gate":
                    pygame.draw.rect(surf, (0, 0, 0), (mx - 4, my - 3, 9, 8))
                    pygame.draw.rect(surf, (230, 230, 240), (mx - 3, my - 2, 7, 6))
                    pygame.draw.circle(surf, (230, 230, 240), (mx, my - 3), 3, 1)

        ex, ey = self.d.exit_tile
        if self.seen[ey * MAP_W + ex]:
            col = self.d.exit_color
            mx = mr.x + (ex - self.box.x) * sx
            my = mr.y + (ey - self.box.y) * sy
            pygame.draw.polygon(surf, col, [(mx, my - 5), (mx + 5, my), (mx, my + 5), (mx - 5, my)])
            pygame.draw.polygon(surf, (0, 0, 0), [(mx, my - 5), (mx + 5, my), (mx, my + 5), (mx - 5, my)], 1)

        stx, sty = self.d.entry_tile
        if self.seen[sty * MAP_W + stx]:
            mx = mr.x + (stx - self.box.x) * sx
            my = mr.y + (sty - self.box.y) * sy
            pygame.draw.circle(surf, (0, 0, 0), (int(mx), int(my)), 5)
            pygame.draw.circle(surf, (90, 170, 255), (int(mx), int(my)), 4)

        view = pygame.Rect(
            mr.x + (cam_x / TILE - self.box.x) * sx,
            mr.y + (cam_y / TILE - self.box.y) * sy,
            SCREEN_W / TILE * sx, SCREEN_H / TILE * sy)
        pygame.draw.rect(surf, (200, 200, 214), view, 1)

        px = mr.x + (player.x / TILE - self.box.x) * sx
        py = mr.y + (player.y / TILE - self.box.y) * sy
        pulse = 3 + (1 if int(t * 3) % 2 == 0 else 0)
        pygame.draw.circle(surf, (0, 0, 0), (int(px), int(py)), pulse + 2)
        pygame.draw.circle(surf, (255, 240, 170), (int(px), int(py)), pulse)
        surf.set_clip(None)

        txt = font.render(f"MAP  {self.d.floor_name}    rooms {self.rooms_found}/{len(self.d.rooms)}", True,
                          (150, 220, 150) if all(self.room_seen) else th.accent)
        surf.blit(txt, (mr.x, mr.bottom + 4))
        hint = font.render("M", True, (150, 150, 160))
        surf.blit(hint, (mr.right - hint.get_width(), mr.bottom + 4))


# --------------------------------------------------------------------------
# Dungeon
# --------------------------------------------------------------------------

class Dungeon:
    def __init__(self, floor_name: str, seed: int = 0):
        self.floor_name = floor_name
        self.layout_seed = seed
        self.rng_key = f"{floor_name}|{seed}"       # every per-floor random choice mixes this in
        self.mini = minis.MINI_BY_NUM.get(dungeon_for(floor_name))
        self.family = family_for(floor_name)
        self.tier = self.mini["tier"] if self.mini else min(3, max(1, self.family))
        self.lock_rect: pygame.Rect | None = None   # pixel rect the player is confined to
        self.theme = theme_for(floor_name)
        self.art = Art.get(self.theme)
        self.seed = (sum(ord(c) for c in floor_name) * 131 + seed * 7919) & 0xFFFFFF
        self.rng = random.Random(self.rng_key)
        self.tiles = bytearray(CELLS)
        self.solid = bytearray(CELLS)
        self.edge = bytearray(CELLS)
        self.blend = bytearray(CELLS)
        self.vary = bytes(self.rng.getrandbits(8) for _ in range(CELLS))
        self.zone: set[int] = set()
        lay = dungeon_gen.generate(floor_name, seed)
        self.layout = lay
        self.rooms = [pygame.Rect(x, y, w, h) for x, y, w, h in lay.rooms]
        self.room_roles = list(lay.roles)          # "start", "combat", "stairs", "boss", ...
        self.parent = list(lay.parent)             # room to fall back to after dying
        self.routes = list(lay.routes)
        self.props: list[tuple[int, int, str, pygame.Surface]] = []
        self.decals: list[tuple[int, int, pygame.Surface]] = []
        self.wall_decor: dict[tuple[int, int], str] = {}
        self.rug = bytearray(CELLS)
        self.doors: list[tuple[pygame.Rect, bool]] = []
        self.door_of: dict[tuple[int, int], tuple] = {}   # (room, other room) -> (nx, ny, dx, dy)
        self.links = list(lay.links)

        self.interact = None    # room_features.Interactables attaches itself here
        self.carve_rooms()
        self.carve_corridors()
        self.scatter_liquid()
        room_features.decorate(self)    # themed room layouts (walls, pools, pillar rows...)
        self.build_walls()
        self.compute_flags()
        self.place_props()
        self.place_decals()
        self.place_wall_decor()

        self.start_room = self.rooms[0]
        self.exit_room = self.rooms[-1]
        self.entry_tile = (self.start_room.centerx, self.start_room.centery)
        self.entry_pos = (self.entry_tile[0] * TILE + TILE // 2,
                          self.entry_tile[1] * TILE + TILE // 2)
        self.spawn = (self.entry_pos[0], self.entry_pos[1] + TILE * 3)
        self.exit_tile = (self.exit_room.centerx, self.exit_room.centery)
        self.exit_pos = (self.exit_tile[0] * TILE + TILE // 2,
                         self.exit_tile[1] * TILE + TILE // 2)
        final = next_floor(floor_name) is None
        self.exit_color = (236, 196, 84) if final else (238, 72, 64)
        self.exit_glow = make_glow(112, self.exit_color, 0.55)

    def carve_rooms(self):
        rng = self.rng
        for k, r in enumerate(self.rooms):
            if self.room_roles[k] in ("boss", "miniboss", "lair"):
                cuts = [5] * 4                      # octagonal arenas
            elif self.room_roles[k] in ("vault", "shrine", "stairs"):
                cuts = [rng.choice((0, 2, 3)) for _ in range(4)]
            else:
                cuts = [rng.choice((0, 3, 4, 5)) for _ in range(4)]
            for j in range(r.h):
                for i in range(r.w):
                    if i + j < cuts[0]:
                        continue
                    if (r.w - 1 - i) + j < cuts[1]:
                        continue
                    if i + (r.h - 1 - j) < cuts[2]:
                        continue
                    if (r.w - 1 - i) + (r.h - 1 - j) < cuts[3]:
                        continue
                    self.tiles[(r.y + j) * MAP_W + r.x + i] = FLOOR

    def set_path(self, x: int, y: int):
        if 0 <= x < MAP_W and 0 <= y < MAP_H:
            i = y * MAP_W + x
            self.zone.add(i)
            if self.tiles[i] == VOID:
                self.tiles[i] = PATH

    def carve_corridors(self):
        """Carve each link's route (axis-aligned waypoints from dungeon_gen), 3 tiles wide,
        and frame the doorway where it meets each of its two rooms."""
        sgn = lambda v: (v > 0) - (v < 0)
        for pts in self.routes:
            for (x0, y0), (x1, y1) in zip(pts, pts[1:]):
                if y0 == y1:
                    for x in range(min(x0, x1), max(x0, x1) + 1):
                        for yy in range(y0 - 1, y0 + 2):
                            self.set_path(x, yy)
                        self.rug[y0 * MAP_W + x] |= 1
                else:
                    for y in range(min(y0, y1), max(y0, y1) + 1):
                        for xx in range(x0 - 1, x0 + 2):
                            self.set_path(xx, y)
                        self.rug[y * MAP_W + x0] |= 2
        seen = set()
        for (ia, ib), pts in zip(self.links, self.routes):
            (ax, ay), (ax2, ay2) = pts[0], pts[1]
            (bx, by), (bx2, by2) = pts[-1], pts[-2]
            ends = ((ia, ib, (ax, ay), (sgn(ax2 - ax), sgn(ay2 - ay))),
                    (ib, ia, (bx, by), (sgn(bx2 - bx), sgn(by2 - by))))
            for room, other, start, (ddx, ddy) in ends:
                door = self.find_door(self.rooms[room], ddx, ddy, start)
                if not door:
                    continue
                self.door_of[(room, other)] = door
                if door in seen:
                    continue
                seen.add(door)
                nx, ny, dx, dy = door
                if dx:
                    edge = nx * TILE if dx > 0 else (nx + 1) * TILE
                    self.doors.append((pygame.Rect(edge - 3, (ny - 1) * TILE, 6, 3 * TILE), True))
                else:
                    edge = ny * TILE if dy > 0 else (ny + 1) * TILE
                    self.doors.append((pygame.Rect((nx - 1) * TILE, edge - 3, 3 * TILE, 6), False))

    def find_door(self, r, dx, dy, start=None):
        if dx == 0 and dy == 0:
            return None
        x, y = start if start is not None else (r.centerx, r.centery)
        for _ in range(200):
            x, y = x + dx, y + dy
            if not (0 <= x < MAP_W and 0 <= y < MAP_H):
                return None
            if self.tiles[y * MAP_W + x] == PATH:
                return (x, y, dx, dy)
        return None

    def scatter_liquid(self):
        rng = self.rng
        for k, r in enumerate(self.rooms):
            if self.room_roles[k] not in ("combat", "guard", "seal", "vault"):
                continue
            cx, cy = r.centerx, r.centery
            for _ in range(rng.choice((0, 1, 1, 2))):
                rx, ry = rng.randrange(3, 6), rng.randrange(2, 4)
                if r.w < 2 * (rx + 4) + 2 or r.h < 2 * (ry + 4) + 2:
                    continue
                for _try in range(10):
                    px = rng.randrange(r.x + rx + 3, r.right - rx - 3)
                    py = rng.randrange(r.y + ry + 3, r.bottom - ry - 3)
                    if abs(px - cx) > rx + 3 and abs(py - cy) > ry + 3:
                        break
                else:
                    continue
                for y in range(py - ry, py + ry + 1):
                    for x in range(px - rx, px + rx + 1):
                        d = ((x - px) / rx) ** 2 + ((y - py) / ry) ** 2
                        if d <= 1.0 + rng.uniform(-0.25, 0.1):
                            i = y * MAP_W + x
                            if self.tiles[i] == FLOOR and i not in self.zone:
                                self.tiles[i] = LIQUID

    def build_walls(self):
        T = self.tiles
        for i in range(CELLS):
            if T[i] not in OPEN:
                continue
            x, y = i % MAP_W, i // MAP_W
            for dy in range(-3, 3):
                yy = y + dy
                if yy < 0 or yy >= MAP_H:
                    continue
                for dx in range(-2, 3):
                    xx = x + dx
                    if 0 <= xx < MAP_W and T[yy * MAP_W + xx] == VOID:
                        T[yy * MAP_W + xx] = TOP
        for i in range(CELLS - MAP_W):
            if T[i] == TOP and T[i + MAP_W] in OPEN:
                T[i] = FACE
        for i in range(CELLS - MAP_W):
            if T[i] == TOP and T[i + MAP_W] == FACE:
                T[i] = FACE_UP

    def compute_flags(self):
        T, E, B, W = self.tiles, self.edge, self.blend, MAP_W
        for i in range(W, CELLS - W):
            k = T[i]
            if k == FLOOR or k == PATH:
                f = 0
                if T[i - W] in WALLS:
                    f |= 1
                if T[i - 1] in WALLS:
                    f |= 2
                if T[i + 1] in WALLS:
                    f |= 4
                if T[i + W] in WALLS:
                    f |= 8
                E[i] = f
                if k == PATH:
                    bl = 0
                    if T[i - W] == FLOOR:
                        bl |= 1
                    if T[i + W] == FLOOR:
                        bl |= 2
                    if T[i - 1] == FLOOR:
                        bl |= 4
                    if T[i + 1] == FLOOR:
                        bl |= 8
                    B[i] = bl
            elif k == LIQUID:
                f = 0
                if T[i - W] != LIQUID:
                    f |= 1
                if T[i + W] != LIQUID:
                    f |= 2
                if T[i - 1] != LIQUID:
                    f |= 4
                if T[i + 1] != LIQUID:
                    f |= 8
                E[i] = f
            elif k == TOP:
                f = 0
                if T[i - W] in OPEN:
                    f |= 1
                if T[i - 1] in OPEN:
                    f |= 2
                if T[i + 1] in OPEN:
                    f |= 4
                if T[i + W] == FACE_UP:
                    f |= 8
                E[i] = f

    def near_zone(self, tx: int, ty: int, r: int) -> bool:
        z = self.zone
        for a in range(-r, r + 1):
            for b in range(-r, r + 1):
                if (ty + b) * MAP_W + tx + a in z:
                    return True
        return False

    def place_props(self):
        rng, art = self.rng, self.art
        weights = [p[2] for p in art.props]
        used: set[tuple[int, int]] = set()
        last = len(self.rooms) - 1
        for k, r in enumerate(self.rooms):
            cx, cy = r.centerx, r.centery
            # fewer props than before: rooms are now combat arenas and need space
            target = r.w * r.h // room_features.prop_divisor(self, k)
            placed = 0
            for _ in range(target * 8):
                if placed >= target:
                    break
                tx = rng.randrange(r.x + 2, r.right - 2)
                ty = rng.randrange(r.y + 2, r.bottom - 2)
                dx, dy = abs(tx - cx), abs(ty - cy)
                if dx <= 3 or dy <= 3:
                    continue
                if k in (0, last) and max(dx, dy) <= 7:
                    continue
                i = ty * MAP_W + tx
                if self.tiles[i] != FLOOR or self.near_zone(tx, ty, 2):
                    continue
                if any((tx + a, ty + b) in used for a in (-1, 0, 1) for b in (-1, 0, 1)):
                    continue
                kind, spr, _w = rng.choices(art.props, weights)[0]
                used.add((tx, ty))
                self.solid[i] = 1
                self.props.append((tx, ty, kind, spr))
                placed += 1
        self.props.sort(key=lambda p: p[1])

    def place_decals(self):
        rng, art = self.rng, self.art
        sprites = [d[0] for d in art.decals]
        weights = [d[1] for d in art.decals]
        for r in self.rooms:
            for _ in range(r.w * r.h // 14):
                tx, ty = rng.randrange(r.x, r.right), rng.randrange(r.y, r.bottom)
                i = ty * MAP_W + tx
                if self.tiles[i] != FLOOR or self.solid[i]:
                    continue
                spr = rng.choices(sprites, weights)[0]
                self.decals.append((tx * TILE + rng.randrange(0, TILE - 6),
                                    ty * TILE + rng.randrange(0, TILE - 6), spr))
        if self.theme.key != "hell":
            for r in self.rooms:
                for ty in range(r.y, r.bottom):
                    for tx in range(r.x, r.right):
                        i = ty * MAP_W + tx
                        if self.tiles[i] != FLOOR:
                            continue
                        e = self.edge[i] & 7
                        if e == 3 and rng.random() < 0.8:
                            self.decals.append((tx * TILE, ty * TILE, art.web_l))
                        elif e == 5 and rng.random() < 0.8:
                            self.decals.append((tx * TILE + TILE - 16, ty * TILE, art.web_r))

    def place_wall_decor(self):
        T, W = self.tiles, MAP_W
        wd = self.wall_decor
        for i in range(2, CELLS - 2):
            if T[i] != FACE:
                continue
            if T[i - 1] != FACE or T[i + 1] != FACE or T[i - 2] != FACE or T[i + 2] != FACE:
                continue
            x, y = i % W, i // W
            if any((x - d, y) in wd for d in range(1, 5)):
                continue
            h = hash2(x, y, self.seed)
            if h % 13 == 0:
                wd[(x, y)] = "torch"
            elif h % 29 == 3:
                wd[(x, y)] = "banner"

    def can_stand(self, x: float, y: float) -> bool:
        lr = self.lock_rect
        if lr is not None and not lr.collidepoint(x, y):
            return False
        for ox, oy in ((-5, -3), (5, -3), (-5, 3), (5, 3)):
            tx, ty = int((x + ox) // TILE), int((y + oy) // TILE)
            if not (0 <= tx < MAP_W and 0 <= ty < MAP_H):
                return False
            i = ty * MAP_W + tx
            if self.tiles[i] not in WALK or self.solid[i]:
                return False
        return True

    def draw_portal(self, surf, sx, sy, t, col, star=False):
        th = self.theme
        pulse = 0.5 + 0.5 * math.sin(t * 2.4)
        # raised stone plinth: floor shadow, visible side wall, then the top face
        shd = blank(120, 70)
        pygame.draw.ellipse(shd, (0, 0, 0, 120), (0, 0, 120, 70))
        surf.blit(shd, (sx - 52, sy - 22))
        sy -= 7
        for dy in range(9, 0, -1):
            c = mix(shade(th.wall, 0.32), shade(th.wall, 0.62), 1 - dy / 9)
            pygame.draw.circle(surf, c, (sx, sy + dy), 45)
        pygame.draw.circle(surf, shade(th.wall_dark, 0.9), (sx, sy), 45)
        pygame.draw.circle(surf, shade(th.wall, 0.72), (sx, sy), 43)
        for i in range(12):
            a = i * math.tau / 12
            pygame.draw.line(surf, shade(th.wall_dark, 0.8),
                             (sx + math.cos(a) * 31, sy + math.sin(a) * 31),
                             (sx + math.cos(a) * 43, sy + math.sin(a) * 43), 2)
        for i in range(12):
            a = (i + 0.5) * math.tau / 12
            b = 0.5 + 0.5 * math.sin(t * 3 + i * 0.9)
            c = mix(shade(th.wall, 0.55), col, 0.25 + 0.75 * b)
            rx, ry = int(sx + math.cos(a) * 37), int(sy + math.sin(a) * 37)
            pygame.draw.rect(surf, shade(th.wall_dark, 0.7), (rx - 3, ry - 3, 6, 6))
            pygame.draw.rect(surf, c, (rx - 2, ry - 2, 4, 4))
            surf.set_at((rx - 1, ry - 1), mix(c, (255, 255, 255), 0.5))
        pygame.draw.circle(surf, shade(th.wall_hi, 0.9), (sx, sy), 43, 2)
        pygame.draw.circle(surf, shade(th.wall_hi, 0.6), (sx, sy), 31, 2)
        # portal core
        pygame.draw.circle(surf, shade(col, 0.2 + 0.1 * pulse), (sx, sy), 29)
        for arm in range(4):
            for j in range(17):
                a = t * 2.2 + arm * math.pi / 2 + j * 0.34
                r = 3 + j * 1.6
                c = mix(shade(col, 0.75), (255, 255, 255), max(0.0, 1 - j / 14) * 0.7)
                pygame.draw.circle(surf, c, (int(sx + math.cos(a) * r), int(sy + math.sin(a) * r)),
                                   max(1, 4 - j // 5))
        pygame.draw.circle(surf, mix(col, (255, 255, 255), 0.85), (sx, sy), 4)
        pygame.draw.circle(surf, col, (sx, sy), 29, 2)
        # expanding shock rings
        rings = blank(150, 150)
        for k in range(2):
            ph = (t * 0.6 + k * 0.5) % 1.0
            pygame.draw.circle(rings, (*col, int(150 * (1 - ph))), (75, 75), int(34 + ph * 36), 2)
        surf.blit(rings, (sx - 75, sy - 75))
        # orbiting motes
        for i in range(10):
            a = -t * 0.9 + i * math.tau / 10
            rx, ry = int(sx + math.cos(a) * 52), int(sy + math.sin(a) * 52)
            b = 0.65 + 0.35 * math.sin(t * 3 + i)
            pygame.draw.rect(surf, shade(col, b), (rx - 1, ry - 1, 3, 3))
        if star:
            pts = []
            for i in range(5):
                a = -t * 0.35 + i * math.tau / 5
                pts.append((sx + math.cos(a) * 62, sy + math.sin(a) * 62))
            for i in range(5):
                pygame.draw.line(surf, shade(col, 0.8), pts[i], pts[(i + 2) % 5], 1)
            pygame.draw.circle(surf, shade(col, 0.8), (sx, sy), 62, 1)

    def draw_door(self, surf, r, vertical):
        gold, hi, dk = (186, 138, 54), (240, 200, 108), (96, 64, 26)
        pygame.draw.rect(surf, dk, r.inflate(2, 2))
        pygame.draw.rect(surf, gold, r)
        if vertical:
            pygame.draw.line(surf, hi, (r.x + 1, r.y), (r.x + 1, r.bottom - 1))
            for y in range(r.y + 8, r.bottom - 6, 8):
                surf.fill(dk, (r.x, y, r.w, 1))
            posts = [pygame.Rect(r.x - 3, y, 12, 8) for y in (r.y - 3, r.bottom - 5)]
        else:
            pygame.draw.line(surf, hi, (r.x, r.y + 1), (r.right - 1, r.y + 1))
            for x in range(r.x + 8, r.right - 6, 8):
                surf.fill(dk, (x, r.y, 1, r.h))
            posts = [pygame.Rect(x, r.y - 3, 8, 12) for x in (r.x - 3, r.right - 5)]
        for p in posts:
            pygame.draw.rect(surf, gold, p)
            pygame.draw.rect(surf, hi, (p.x, p.y, p.w, 2))
            pygame.draw.rect(surf, dk, p, 1)
            surf.fill((255, 236, 170), (p.centerx, p.centery, 1, 1))

    def draw_world(self, surf, cam_x, cam_y, t, player):
        art, th = self.art, self.theme
        T, E, V, BL = self.tiles, self.edge, self.vary, self.blend
        surf.fill((5, 5, 8))
        glows = []
        x0, y0 = cam_x // TILE, cam_y // TILE
        x1 = min(MAP_W, x0 + SCREEN_W // TILE + 2)
        y1 = min(MAP_H, y0 + SCREEN_H // TILE + 2)
        nf, npth, nfa, ntp = len(art.floor), len(art.path), len(art.face), len(art.top)
        hell = th.key == "hell"
        wd = self.wall_decor
        rug, carpet = self.rug, art.carpet
        frame_base = int(t * 4)

        for ty in range(max(0, y0), y1):
            row = ty * MAP_W
            py = ty * TILE - cam_y
            for tx in range(max(0, x0), x1):
                i = row + tx
                k = T[i]
                if k == VOID:
                    continue
                px = tx * TILE - cam_x
                v = V[i]
                if k == FLOOR:
                    surf.blit(art.floor[v % nf], (px, py))
                    if rug[i]:
                        surf.blit(carpet[rug[i]], (px, py))
                    e = E[i]
                    if e:
                        surf.blit(art.shadow[e], (px, py))
                elif k == PATH:
                    surf.blit(art.path[v % npth], (px, py))
                    bl = BL[i]
                    if bl:
                        surf.blit(art.blend[bl], (px, py))
                    if rug[i]:
                        surf.blit(carpet[rug[i]], (px, py))
                    e = E[i]
                    if e:
                        surf.blit(art.shadow[e], (px, py))
                elif k == LIQUID:
                    surf.blit(art.liquid((frame_base + (tx >> 1) + ty) % LIQUID_FRAMES, E[i]), (px, py))
                    if hell and (tx + ty) % 2 == 0:
                        glows.append((px + TILE // 2, py + TILE // 2, art.lava_glow))
                elif k == TOP:
                    surf.blit(art.top_tile(v % ntp, E[i]), (px, py))
                elif k == FACE_UP:
                    surf.blit(art.face_up[v % nfa], (px, py))
                else:
                    surf.blit(art.face[v % nfa], (px, py))
                    d = wd.get((tx, ty))
                    if d == "torch":
                        pygame.draw.rect(surf, (30, 24, 22), (px + 7, py + 17, 10, 3))
                        pygame.draw.rect(surf, (62, 48, 36), (px + 10, py + 10, 4, 9))
                        pygame.draw.rect(surf, (96, 76, 54), (px + 10, py + 10, 1, 9))
                        pygame.draw.rect(surf, (44, 34, 28), (px + 8, py + 8, 8, 3))
                        draw_flame(surf, px + 12, py + 9, t, tx * 1.7 + ty)
                        draw_sparks(surf, px + 12, py + 5, t, tx * 31 + ty)
                        glows.append((px + 12, py + 6, art.torch_glows[(int(t * 10) + tx) % 3]))
                    elif d == "banner":
                        surf.blit(art.banner, (px + 4, py - 12))

        for dx, dy, spr in self.decals:
            sx, sy = dx - cam_x, dy - cam_y
            if -40 < sx < SCREEN_W and -20 < sy < SCREEN_H:
                surf.blit(spr, (sx, sy))
        if self.interact is not None:
            self.interact.draw_floor(surf, cam_x, cam_y, t)

        for rect, vertical in self.doors:
            r = rect.move(-cam_x, -cam_y)
            if r.right > -20 and r.left < SCREEN_W + 20 and r.bottom > -20 and r.top < SCREEN_H + 20:
                self.draw_door(surf, r, vertical)

        ex, ey = int(self.exit_pos[0] - cam_x), int(self.exit_pos[1] - cam_y)
        if -90 < ex < SCREEN_W + 90 and -90 < ey < SCREEN_H + 90:
            boss = is_boss_floor(self.floor_name) and next_floor(self.floor_name) is not None
            self.draw_portal(surf, ex, ey, t, self.exit_color, boss)
            glows.append((ex, ey, self.exit_glow))
        nx, ny = int(self.entry_pos[0] - cam_x), int(self.entry_pos[1] - cam_y)
        if -90 < nx < SCREEN_W + 90 and -90 < ny < SCREEN_H + 90:
            self.draw_portal(surf, nx, ny, t, (80, 160, 255))
            glows.append((nx, ny, art.entry_glow))

        player.draw_dust(surf, cam_x, cam_y, mix(th.floor, (200, 200, 200), 0.35))

        # directional cast shadows first, so every prop and the player sit on top
        for tx, ty, kind, spr in self.props:
            px = tx * TILE - cam_x
            py = (ty + 1) * TILE - cam_y
            if px < -80 or px > SCREEN_W + 80 or py < -10 or py > SCREEN_H + 140:
                continue
            cs = art.cast.get(id(spr))
            if cs:
                surf.blit(cs, (px + (TILE - spr.get_width()) // 2, py - 2))

        feet = player.y - cam_y
        prect = pygame.Rect(int(player.x - cam_x) - 9, int(feet) - 42, 18, 42)
        drawn = False
        # pots, chests, tablets... merged into the same y-sorted pass as the props
        extras = []
        if self.interact is not None:
            items = list(self.interact.sprites())
            extras = sorted(((y - cam_y, fn) for y, fn in items
                             if -60 < y - cam_y < SCREEN_H + 90), key=lambda e: e[0])
        ei = 0
        for tx, ty, kind, spr in self.props:
            px = tx * TILE - cam_x
            py = (ty + 1) * TILE - cam_y
            if px < -60 or px > SCREEN_W + 60 or py < -10 or py > SCREEN_H + 90:
                continue
            while ei < len(extras) and extras[ei][0] <= py:
                if not drawn and extras[ei][0] > feet:
                    player.draw(surf, player.x - cam_x, feet, t)
                    drawn = True
                extras[ei][1](surf, cam_x, cam_y, t)
                ei += 1
            if not drawn and py > feet:
                player.draw(surf, player.x - cam_x, feet, t)
                drawn = True
            bx = px + (TILE - spr.get_width()) // 2
            by = py - spr.get_height() + 2
            sh_ = spr.get_height()
            if drawn and sh_ >= 48 and pygame.Rect(bx, by, spr.get_width(), sh_).colliderect(prect):
                # tall prop in front of the player: let them show through
                spr.set_alpha(135)
                surf.blit(spr, (bx, by))
                spr.set_alpha(255)
            else:
                surf.blit(spr, (bx, by))
            if kind == "brazier":
                draw_flame(surf, px + TILE // 2, by + 16, t, tx * 2.3 + ty, 1.3)
                draw_sparks(surf, px + TILE // 2, by + 6, t, tx * 17 + ty, 3, 34)
                glows.append((px + TILE // 2, by + 10, art.torch_glows[(int(t * 10) + tx) % 3]))
            elif kind in ("crystal", "obelisk"):
                glows.append((px + TILE // 2, by + (24 if kind == "crystal" else 30), art.crystal_glow))
        while ei < len(extras):
            if not drawn and extras[ei][0] > feet:
                player.draw(surf, player.x - cam_x, feet, t)
                drawn = True
            extras[ei][1](surf, cam_x, cam_y, t)
            ei += 1
        if not drawn:
            player.draw(surf, player.x - cam_x, feet, t)
        return glows


# --------------------------------------------------------------------------
# Player
# --------------------------------------------------------------------------

class Player:
    def __init__(self, dungeon: Dungeon, look: str = "hero_warrior"):
        self.x, self.y = dungeon.spawn
        self.speed_k = 1.0                 # class walk speed
        self.set_look(look)
        self.anim = 0.0
        self.moving = False
        self.face = (0.0, 1.0)
        self.dir = "down"
        self.blink = False          # set by Game while invulnerable after a hit
        self.dust: list[list[float]] = []
        self.dust_t = 0.0
        self.dash_t = 0.0                  # > 0 while dashing (Shift)
        self.dash_dir = (0.0, 1.0)
        self.shadow = blank(22, 10)
        pygame.draw.ellipse(self.shadow, (0, 0, 0, 60), (0, 0, 22, 10))
        pygame.draw.ellipse(self.shadow, (0, 0, 0, 90), (3, 2, 16, 6))

    def set_look(self, look: str):
        """Same pixel-art hero as in the overworld (npc_art.LOOKS: hero_warrior / _mage / _archer)."""
        self.look = look
        self.frames = {k: v.convert_alpha() for k, v in npc_art.make_npc_frames(npc_art.LOOKS[look]).items()}

    def place(self, x: float, y: float):
        self.x, self.y = x, y
        self.dash_t = 0.0
        self.dust.clear()

    def move(self, dx: float, dy: float, dungeon: Dungeon, dt: float):
        for p in self.dust:
            p[2] -= dt
        self.dust = [p for p in self.dust if p[2] > 0]
        speed = PLAYER_SPEED * self.speed_k
        if self.dash_t > 0:                # a dash overrides the keys for a moment
            self.dash_t = max(0.0, self.dash_t - dt)
            dx, dy = self.dash_dir
            speed = DASH_SPEED
        self.moving = dx != 0 or dy != 0
        if not self.moving:
            self.anim = 0.0
            return
        length = math.hypot(dx, dy)
        dx, dy = dx / length, dy / length
        self.face = (dx, dy)
        ax, ay = abs(dx), abs(dy)
        if ax > ay + 0.15:
            self.dir = "right" if dx > 0 else "left"
        elif ay > ax + 0.15:
            self.dir = "down" if dy > 0 else "up"
        self.anim += dt
        self.dust_t += dt
        if self.dust_t > (0.03 if self.dash_t > 0 else 0.15):
            self.dust_t = 0.0
            self.dust.append([self.x + random.uniform(-3, 3), self.y - 1, 0.45])
        nx = self.x + dx * speed * dt
        if dungeon.can_stand(nx, self.y):
            self.x = nx
        ny = self.y + dy * speed * dt
        if dungeon.can_stand(self.x, ny):
            self.y = ny

    def draw_dust(self, surf, cam_x, cam_y, col):
        for x, y, life in self.dust:
            k = life / 0.45
            r = int(2 + (1 - k) * 3)
            ds = blank(12, 12)
            pygame.draw.circle(ds, (*col, int(110 * k)), (6, 6), r)
            surf.blit(ds, (int(x - cam_x) - 6, int(y - cam_y - (1 - k) * 6) - 6))

    def draw(self, surf, sx, sy, t):
        if self.blink:
            return
        sx, sy = int(sx), int(sy)
        step = (1 if int(self.anim * 6) % 2 == 0 else 2) if self.moving else 0
        facing = {"left": "side", "right": "side"}.get(self.dir, self.dir)
        img = self.frames[(facing, step)]
        if self.dir == "left":
            img = pygame.transform.flip(img, True, False)
        surf.blit(self.shadow, (sx - 11, sy - 6))
        w, h = img.get_size()
        surf.blit(img, (sx - w // 2, sy - h + 4 - (1 if step else 0)))


# --------------------------------------------------------------------------
# Game
# --------------------------------------------------------------------------

class Game:
    def __init__(self):
        pygame.init()
        pygame.display.set_caption("RealmQuest - Beyond the Veil")
        self.settings = Settings.load()
        self.screen = self.settings.apply_display((SCREEN_W, SCREEN_H)) if self.settings.fullscreen \
            else pygame.display.set_mode((SCREEN_W, SCREEN_H))
        self.clock = pygame.time.Clock()
        self.font = pygame.font.Font(None, 30)
        self.small_font = pygame.font.Font(None, 21)
        self.big_font = pygame.font.Font(None, 68)
        self.mid_font = pygame.font.Font(None, 32)
        self.fade_surf = pygame.Surface((SCREEN_W, SCREEN_H))
        self.fade_surf.fill((0, 0, 0))
        self.vignette = make_vignette().convert_alpha()

        self.cam_x = 0.0
        self.cam_y = 0.0
        self.prev_cam = (0, 0)
        self.fade = 1.0
        self.fade_dir = -1
        self.pending = None
        self.title_t = 0.0
        self.show_map = True
        # Campaign save (gold, upgrades, cleared dungeons, keepsakes, story flags)
        self.has_save = SaveState.exists()
        self.save = SaveState.load()
        self.toasts: list[list] = []       # dungeon-side banner messages [text, color, life]
        self.shop: ShopMenu | None = None
        self.journal: Journal | None = None
        self.quests = quests.QuestBook(self.save)
        self.floor_name = "1-1"
        self.run_seed = random.getrandbits(30)   # new random floors every time you enter a dungeon
        self.floors: dict = {}                   # floors built during this dungeon run
        self.dungeon = Dungeon(self.floor_name)
        self.player = Player(self.dungeon)
        self.mode = "village"  # Explore the overworld before entering a faction dungeon
        # Procedural surface world (Oakwood Village + the three dungeon portals).
        # It renders at its own resolution onto an off-screen canvas that is
        # scaled to the game window each frame.
        self.surface_canvas = pygame.Surface((sw_mod.SCREEN_W, sw_mod.SCREEN_H)).convert()
        progress = sw_mod.Progress()
        progress.cleared = self.save.cleared          # one shared set: the save is the truth
        self.surface = sw_mod.SurfaceWorld(self.surface_canvas,
                                           on_enter_dungeon=self.enter_from_surface,
                                           progress=progress, save=self.save,
                                           on_talk=self.talk_to, on_landmark=self.use_landmark,
                                           quest_info=self.quest_info)
        self.surface.npc_alert = self.npc_marker
        self.surface.quests = self.quests
        self.pc = PlayerCombat()
        self.save.apply_to(self.pc)
        self.pc.reset()
        self.portraits = {}
        for look, speaker in (("hero", story.HERO), ("maren", story.MAREN), ("torvin", story.TORVIN),
                              ("wren", story.WREN), ("pip", story.PIP), ("hale", story.HALE), ("bram", story.BRAM),
                              ("lisbet", story.LISBET), ("refugee", story.SURVIVOR), ("merlin", story.MERLIN),
                              ("merlin", story.MERLIN_STONE)):
            self.portraits[speaker] = village.portrait(look)
        stone = self.portraits[story.MERLIN_STONE].copy()        # his voice from afar: faded and bluish
        stone.fill((40, 60, 110), special_flags=pygame.BLEND_RGB_ADD)
        stone.set_alpha(190)
        self.portraits[story.MERLIN_STONE] = stone

        self.interact = room_features.Interactables(self.dungeon, self.save)
        self.enc = Encounters(self.dungeon)
        self.minimap = Minimap(self.dungeon)
        self.motes = Motes(self.dungeon.theme, 1)
        self.fog = Fog(self.dungeon.theme, 1)
        self.snap_camera()
        self.huge_font = pygame.font.Font(None, 124)
        self.sfx = Sfx()
        self.music = Music()
        self.fx = SkillFX()                 # the hero's skills in the current place
        self.hero_hud = HeroHUD()
        self.build_keys()
        self.apply_volumes()
        self.night = night_raid.Night(self.surface, self.save, self.pc, self.sfx, self.on_night_event)
        self.wilds = wilds.Wilds(self.surface, self.save, self.pc, self.sfx, self.village_xp)
        self.night.on_xp = self.village_xp
        self.regen = 0.0
        self.state = "menu"            # "menu" (home, name, class) -> "playing"
        self.paused = False
        self.pause_sel = 0
        self.pause_settings = None     # SettingsScreen opened from the pause menu
        self.surface.draw_fx_hook = self.draw_village_fx
        self.surface.hero_hud_hook = self.draw_village_hud
        self.apply_hero()
        self.open_front()
        self.victory = False
        self.dialog: Dialog | None = None
        self.after_dialog = None       # function to call when the open dialog closes
        self.was_dead = False

    # ---- story --------------------------------------------------------------
    def boss_portrait(self, kind: str):
        return monster_sprite(kind)

    def open_dialog(self, lines, kind=None, after=None):
        portraits = dict(self.portraits)
        if kind:
            portraits[BOSS_SPEAKERS[kind]] = self.boss_portrait(kind)
        self.dialog = Dialog(lines, portraits)
        self.after_dialog = after

    # ---- the chosen hero ---------------------------------------------------------
    def apply_hero(self):
        """Name, class look, speed and portraits of the saved hero, everywhere."""
        s = self.save
        story.set_hero_name(s.hero_name)
        s.apply_to(self.pc)
        look = npc_art.hero_look(s.hero_class)
        for p in (self.surface.player, self.player):
            if getattr(p, "look", None) != look:
                p.set_look(look)
            p.speed_k = self.pc.speed_k
        self.hero_portrait = village.portrait(look)
        self.portraits[story.HERO] = self.hero_portrait

    def hero(self):
        """The hero's body in the current place (overworld or dungeon)."""
        return self.surface.player if self.mode == "village" else self.player

    def save_summary(self):
        if not self.can_continue():
            return None
        s = self.save
        return "%s  -  %s  -  Lv %d  -  %d/3 anchors" % (s.hero_name, self.pc.class_name if
                                                        self.pc.character_class == s.hero_class else
                                                        s.hero_class.title(), s.level, len(s.keepsakes))

    def open_front(self, screen="menu"):
        portraits = {c: npc_art.make_npc_frames(npc_art.LOOKS[npc_art.hero_look(c)])[("down", 0)]
                     for c in ("warrior", "mage", "archer")}
        self.front = FrontEnd(self.settings, save_info=self.save_summary(), portraits=portraits,
                              skill_keys={slot: self.key_label(slot) for slot in SLOTS})
        self.front.open(screen)
        self.state = "menu"

    def return_to_menu(self):
        """Pause menu -> Save & Quit: back to the home screen (the game is saved)."""
        if self.state == "playing" and not self.victory:
            self.autosave()
        self.paused = False
        self.pause_settings = None
        self.dialog = None
        self.shop = None
        self.journal = None
        self.night.abort()
        self.fx.clear()
        self.victory = False
        self.has_save = SaveState.exists()
        self.open_front()

    # ---- settings: keys and volume ----------------------------------------------
    def build_keys(self):
        """Action -> key codes, from Settings, plus the classic keys when they're free."""
        def code(action):
            try:
                return pygame.key.key_code(self.settings.key_for(action))
            except Exception:
                return None
        actions = ("attack", "skill", "skill_2", "special", "dash", "interact")
        keys = {a: {code(a)} - {None} for a in actions}
        bound = set().union(*keys.values())
        extras = {"attack": (pygame.K_SPACE, pygame.K_j), "dash": (pygame.K_LSHIFT, pygame.K_RSHIFT),
                  "interact": (pygame.K_e, pygame.K_RETURN, pygame.K_KP_ENTER)}
        for action, codes in extras.items():
            keys[action].update(k for k in codes if k not in bound)
        self.keys = keys

    def key_label(self, action):
        name = self.settings.key_for(action).upper()
        return {"LEFT SHIFT": "SHIFT", "RIGHT SHIFT": "SHIFT", "SPACE": "SPC"}.get(name, name)

    def apply_volumes(self):
        self.music.set_volume(self.settings.effective_volume("music"))
        self.sfx.set_volume(self.settings.effective_volume("sfx"))

    def controls_hint(self):
        k = self.key_label
        attack = "/".join(pygame.key.name(c).upper() for c in sorted(self.keys["attack"])) or k("attack")
        attack = attack.replace("SPACE", "Space")
        return (f"WASD: move  |  {attack}: attack  |  {k('skill')} {k('skill_2')} {k('special')}: skills"
                f"  |  {k('dash')}: dash  |  E: talk / use  |  Tab: journal  |  H: potion  |  M: map  |  Esc: pause")

    # ---- skills -------------------------------------------------------------------
    def skill_targets(self):
        if self.mode == "village":
            return (list(self.wilds.enemies()) + [lr for lr in self.wilds.lairs if lr.alive]
                    + [m for m in self.night.monsters if not m.dead])
        return [e for e in self.enc.enemies if not e.dead]

    def skill_blocked(self):
        if self.mode == "village":
            ground = self.wilds.ground
            return lambda x, y: not ground.can_stand(x, y)
        d = self.dungeon
        return lambda x, y: not projectile_open(d, x, y)

    def cast_skill(self, slot):
        if self.fade_dir != 0 or self.pc.dead:
            return
        if self.mode == "village" and self.surface.state != "play":
            return
        p = self.hero()
        d = self.pc.caster.cast(slot, self.pc.pools, p.x, p.y, p.face, self.pc.sword_dmg, self.fx)
        if d is None:
            self.sfx.play("no_mana" if self.pc.caster.cd[slot] <= 0 else "blip")
            return
        if self.fx.lunge:                      # Shield Bash: a short charge forward
            p.dash_dir, p.dash_t = self.fx.lunge, 0.14
            self.pc.dash_inv = max(self.pc.dash_inv, 0.25)
            self.fx.lunge = None

    def update_skills(self, dt):
        self.fx.update(dt, self.skill_targets(), self.hero(), self.skill_blocked())
        for name in self.fx.sounds:
            self.sfx.play(name)
        self.fx.sounds.clear()
        if self.fx.hits:
            self.sfx.play("hit")
            self.fx.hits = 0

    def target_hp(self):
        return sum(max(0, getattr(t, "hp", 0)) for t in self.skill_targets())

    def energy_from_hits(self, before):
        """Warrior / Archer: landing basic attacks fills the energy bar."""
        dealt = before - self.target_hp()
        if dealt > 0 and self.pc.energy_on_hit:
            self.pc.pools.add("energy", dealt * self.pc.energy_on_hit)

    def update_music(self, dt):
        p = self.surface.player
        ev = self.wilds.event
        near = bool(ev) and math.hypot(p.x - ev["x"], p.y - ev["y"]) < 700
        boss = bool(self.enc.boss_floor and self.enc.active == self.enc.boss_room)
        self.music.play(pick_place(
            state=self.state, mode=self.mode, victory=self.victory, shop=self.shop is not None,
            raid=self.night.active, event_near=near, night=self.surface.daynight.night(),
            in_village=world_lore.region_at(p.x, p.y)[0] == "Oakwood Village",
            family=family_for(self.floor_name), boss=boss))
        self.music.update(dt)

    def begin_game(self, new: bool = True, name: str | None = None, hero_class: str | None = None):
        self.state = "playing"
        self.mode = "village"
        self.victory = False
        self.paused = False
        self.fx.clear()
        sw = self.surface
        if new:
            self.night.abort()
            self.save.reset(name, hero_class)
            self.save.apply_to(self.pc)
            self.pc.reset()
            sw.player.x, sw.player.y = 1400.0, 1710.0
            sw.player.facing = "up"
        self.apply_hero()
        self.pc.reset()
        self.snap_camera()
        if new:
            self.open_dialog(INTRO_LINES, after=self.autosave)
        else:
            sw.intro = 0.0
            sw.toast("Welcome back. %d gold, %d/3 dungeons cleared." % (self.save.gold, self.save.stage),
                     (200, 230, 190))

    def finish_game(self):
        self.victory = True
        self.save.flags.add("finished")
        self.autosave()
        self.sfx.play("victory")

    def autosave(self):
        self.save.pull_from(self.pc)
        self.save.save()
        self.has_save = True

    def toast(self, text, color=(240, 230, 200), life=3.0):
        text = story.named(text)
        """Banner message in the dungeon (the overworld has its own toasts)."""
        self.toasts = self.toasts[-2:] + [[text, color, life]]

    # ---- villagers / quests / shops --------------------------------------------------
    def npc_marker(self, npc_id: str):
        """What floats over a villager: "ready" (?), "quest" (!), "news" (white !) or None."""
        m = self.quests.marker(npc_id)
        if m:
            return m
        if npc_id in story.NPC_LINES and f"talk_{npc_id}_{self.save.stage}" not in self.save.flags:
            return "news"
        return None

    def talk_to(self, npc):
        """Hand in finished quests, then news, then a new quest offer; otherwise small talk."""
        book, stage = self.quests, self.save.stage
        mine = book.for_npc(npc.id)
        lines, notes = [], []
        for q in mine:
            if book.state(q) == "ready":
                reward = book.complete(q, self.pc)
                lines += q["turnin"]
                notes.append(("Quest complete: %s  -  %s" % (q["title"], reward), (255, 226, 120)))
        if npc.id in story.NPC_LINES:
            key = f"talk_{npc.id}_{stage}"
            if key not in self.save.flags:
                self.save.flags.add(key)
                lines += story.NPC_LINES[npc.id][min(stage, 3)]
        offer = next((q for q in mine if book.state(q) == "available"), None)
        if offer:
            book.accept(offer)
            lines += offer["offer"]
            notes.append(("New quest: " + offer["title"], (150, 210, 255)))
        if npc.id == "merlin" and not lines:
            ms = book.main_step()
            lines = [(story.MERLIN, "Our next step: %s." % ms[3]["text"])] if ms else \
                list(story.NPC_LINES["merlin"][3])
            nxt = next((d for d in sw_mod.DUNGEONS if d["id"] not in self.save.cleared), None)
            if nxt and self.save.level < nxt["min_level"]:
                lines.append((story.MERLIN, "But that seal wants level %d, and you're level %d. Train in the caves, "
                              "clear the lairs, and help when trouble finds travellers."
                              % (nxt["min_level"], self.save.level)))
                fits = [m for m in minis.MINIS if m["tier"] <= max(1, self.save.level // 4 + 1)]
                if fits:
                    lines.append((story.MERLIN, "%s would suit you now (%s)." % (fits[-1]["name"], fits[-1]["level"])))
            if self.night.night_level > 0.5 and self.night.current_source():
                lines.append((story.MERLIN, "And keep an ear out for the horn. They come every night."))
        if not lines:
            active = next((q for q in mine if book.state(q) == "active"), None)
            if active:
                lines = list(active["remind"])
                if active["need"] > 1:
                    lines.append((story.HERO, "So far I have %d of %d." % (book.count(active), active["need"])))
            elif npc.id in story.NPC_LINES:
                lines = story.NPC_LINES[npc.id][min(stage, 3)]
            else:
                lines = story.REFUGEE_LINES[hash(npc.home) % len(story.REFUGEE_LINES)]

        def after():
            for text, col in notes:
                self.surface.toast(text, col)
            if notes:
                self.sfx.play("clear")
            self.autosave()
            if npc.shop:
                self.open_shop(npc.shop)
        self.open_dialog(lines, after=after)

    def use_landmark(self, lm):
        """E on a shrine, the memorial, the notice board or a quest item in the overworld."""
        sw, book, flags = self.surface, self.quests, self.save.flags
        notes = []
        kind = lm.kind
        if kind == "shrine":
            if lm.flag not in flags:
                flags.add(lm.flag)
                q = quests.SIDE_BY_ID["maren_shrines"]
                if book.state(q) in ("active", "ready"):
                    n = book.count(q)
                    notes.append(("Wayshrines visited  %d/%d" % (n, q["need"]) +
                                  ("  -  return to Maren" if n >= q["need"] else ""), (255, 214, 120)))
                else:
                    notes.append(("New lore written in your journal (Tab)", (190, 200, 240)))
            self.open_dialog(world_lore.SHRINE_VERSES[lm.idx], after=lambda: self._notes(notes))
        elif kind == "memorial":
            first = "seen_memorial" not in flags
            flags.add("seen_memorial")
            lines = list(world_lore.MEMORIAL_LINES)
            if book.active("letter"):
                book.collect("letter", "0")
                lines += world_lore.LETTER_LINES
                notes.append(("Letter delivered  -  return to Lisbet", (255, 214, 120)))
            elif first:
                notes.append(("New lore written in your journal (Tab)", (190, 200, 240)))
            self.open_dialog(lines, after=lambda: self._notes(notes))
        elif kind == "board":
            self.open_dialog(world_lore.BOARD_LINES[min(self.save.stage, 3)])
        elif kind == "sword":
            if book.active("sword"):
                book.collect("sword", "0")
                self.sfx.play("pickup")
                self._notes([("Found Goblinbane  -  return to Pip", (255, 214, 120))])
            else:
                self.open_dialog(world_lore.SWORD_LOOK)
        elif kind == "petal":
            if lm.bloom > 0.5:
                got = book.collect("petal", str(lm.idx))
                lm.picked = True
                self.sfx.play("pickup")
                if got:
                    n, need, _q = got
                    self._notes([("Moonpetal  %d/%d" % (n, need) + ("  -  return to Wren" if n >= need else ""),
                                  (200, 220, 255))])
            else:
                sw.toast(world_lore.PETAL_DAY, (200, 210, 230))
        elif kind == "hen":
            got = book.collect("hen", str(lm.idx))
            lm.send_home()
            self.sfx.play("blip")
            if got:
                n, need, _q = got
                name = ("Gertrude", "Mabel", "Duchess")[lm.idx]
                self._notes([("%s runs home!  %d/%d" % (name, n, need) + ("  -  tell Bram" if n >= need else ""),
                              (255, 214, 120))])

    def _notes(self, notes):
        for text, col in notes:
            self.surface.toast(text, col)
        self.autosave()

    def _targets(self, where):
        """Overworld positions for a quest's `where` tag (minimap markers)."""
        kind, key = where.split(":")
        sw = self.surface
        if kind == "portal":
            return [sw_mod.DUNGEON_BY_ID[key]["pos"]]
        if kind == "npc":
            return [(n.x, n.y) for n in sw.talkers() if n.id == key][:1]
        if key == "hen":
            return [(h.x, h.y) for h in sw.hens if h.available(sw)]
        if key == "shrine":
            return [(lm.x, lm.y) for lm in sw.landmarks if lm.kind == "shrine" and lm.flag not in self.save.flags]
        return [(lm.x, lm.y) for lm in sw.landmarks if lm.kind == key and lm.available(sw)]

    def quest_info(self):
        """Tracker lines and minimap markers for the overworld HUD."""
        book = self.quests
        info = {"side": [], "targets": []}
        ms = book.main_step()
        if ms:
            _ci, title, col, st = ms
            info["main"] = (title, st["text"], col)
            info["targets"] += [(x, y, (255, 214, 90)) for x, y in self._targets(st["where"])]
        for q in book.tracked():
            ready = book.state(q) == "ready"
            info["side"].append((q["title"], book.progress_text(q), (255, 214, 120) if ready else (150, 210, 255)))
            where = "npc:" + q["giver"] if ready else q["where"]
            info["targets"] += [(x, y, (150, 210, 255)) for x, y in self._targets(where)]
        return info

    def open_shop(self, shop_id: str):
        self.save.pull_from(self.pc)
        self.shop = ShopMenu(shop_id, self.save, self.pc, self.sfx)

    def drink_potion(self) -> bool:
        if self.pc.drink():
            bonus = self.save.potion_bonus()
            if bonus:
                self.pc.heal(bonus)
            self.save.pull_from(self.pc)
            self.sfx.play("potion")
            return True
        return False

    def gain_xp(self, amount, x=None, y=None, floaters=None):
        """Add XP; level-ups heal fully and show a banner. (x, y, floaters) show '+N XP'."""
        if amount <= 0:
            return
        before = self.save.level
        self.save.xp += int(amount)
        if floaters is not None and x is not None:
            floaters.append([x, y - 40, "+%d XP" % amount, 1.1, (170, 220, 255)])
        after = self.save.level
        if after > before:
            self.save.apply_to(self.pc)
            self.pc.hp = self.pc.max_hp
            msg = "LEVEL UP!  Level %d   (+%d max HP)" % (after, 4 * (after - before))
            if after // 3 > before // 3 or (after - 1) // 3 > (before - 1) // 3:
                msg += "  +1 damage"
            (self.toast if self.mode == "dungeon" else self.surface.toast)(msg, (150, 220, 255))
            self.sfx.play("victory")


    def collect_kill_xp(self):
        enc, d = self.enc, self.dungeon
        tier = getattr(d, "tier", 1)
        for x, y, hp, kind in enc.killed:
            mult = {"boss": 3, "elite": 2}.get(kind, 1)
            self.gain_xp(hp * tier * mult, x, y, self.interact.floaters)
        enc.killed.clear()
        m = getattr(d, "mini", None)
        if m and enc.state[-1] == "cleared" and not getattr(d, "lair_rewarded", False):
            d.lair_rewarded = True
            flag = "mini_" + m["id"]
            r = d.rooms[-1]
            cx, cy = r.centerx * TILE, r.centery * TILE
            if flag not in self.save.flags:
                self.save.flags.add(flag)
                xp, gold = minis.FIRST_CLEAR_XP * m["tier"], minis.FIRST_CLEAR_GOLD * m["tier"]
                self.save.gold += gold
                self.toast("%s cleared for the first time!  +%d gold" % (m["name"], gold), (255, 226, 140))
                self.gain_xp(xp, cx, cy, self.interact.floaters)
            else:
                self.toast("%s cleared!" % m["name"], (220, 230, 200))
            self.autosave()

    def after_update(self):
        self.collect_kill_xp()
        enc = self.enc
        if enc.dialog_request:
            kind, enc.dialog_request = enc.dialog_request, None
            self.open_dialog(BOSS_DIALOGS[kind], kind)
        elif enc.outro_request:
            kind, enc.outro_request = enc.outro_request, None
            self.mark_cleared(dungeon_for(self.floor_name))
            # the ending now plays back in Oakwood, after the keepsake is found
            self.open_dialog(OUTRO_DIALOGS[kind], kind)
        if self.pc.dead and not self.was_dead:
            self.sfx.play("death")
        self.was_dead = self.pc.dead

    # ---- checkpoint ----------------------------------------------------------
    def safe_spot(self, tx: int, ty: int):
        d = self.dungeon
        for rad in range(0, 8):
            for oy in range(-rad, rad + 1):
                for ox in range(-rad, rad + 1):
                    if max(abs(ox), abs(oy)) != rad:
                        continue
                    x, y = (tx + ox) * TILE + TILE // 2, (ty + oy) * TILE + TILE // 2
                    if d.can_stand(x, y):
                        return x, y
        return d.spawn

    def retry_room(self):
        """After dying: reset only the room you died in and restart from the room before it."""
        k = self.enc.retry_room()
        if k is None:
            self.change_floor(self.floor_name)
            return
        self.pc.reset()
        self.was_dead = False
        parent = getattr(self.dungeon, "parent", None)
        target = parent[k] if parent else max(0, k - 1)
        if target == 0:
            x, y = self.dungeon.spawn
        else:
            r = self.dungeon.rooms[target]
            x, y = self.safe_spot(r.centerx, r.centery)
        self.player.place(x, y)
        self.snap_camera()
        self.fade, self.fade_dir = 1.0, -1

    def dash(self):
        if self.fade_dir != 0 or self.pc.dead:
            return
        if self.mode == "village" and self.surface.state != "play":
            return
        keys = pygame.key.get_pressed()
        dx = float(keys[pygame.K_d] or keys[pygame.K_RIGHT]) - float(keys[pygame.K_a] or keys[pygame.K_LEFT])
        dy = float(keys[pygame.K_s] or keys[pygame.K_DOWN]) - float(keys[pygame.K_w] or keys[pygame.K_UP])
        if self.pc.try_dash(self.hero(), dx, dy):
            self.pc.dash_cd *= self.save.dash_factor()      # Windstep Boots
            self.sfx.play("dash")
        elif self.pc.dash_cd <= 0:
            self.sfx.play("no_mana")                         # out of stamina

    def snap_camera(self):
        self.cam_x, self.cam_y = self.camera_target()
        self.prev_cam = (int(round(self.cam_x)), int(round(self.cam_y)))

    def camera_target(self):
        if self.mode == "village":
            return 0.0, 0.0
        tx = self.player.x - SCREEN_W / 2
        ty = self.player.y - SCREEN_H / 2
        tx = max(0, min(tx, max(0, MAP_W * TILE - SCREEN_W)))
        ty = max(0, min(ty, max(0, MAP_H * TILE - SCREEN_H)))
        return tx, ty

    def change_floor(self, floor_name: str, at_exit: bool = False):
        if floor_name not in dungeon_gen.VALID_FLOORS:
            return
        if not self.is_dungeon_unlocked(dungeon_for(floor_name)):
            return
        self.mode = "dungeon"
        self.floor_name = floor_name
        cached = self.floors.get(floor_name)
        if cached:                      # back up the stairs: the floor is as you left it
            self.dungeon, self.enc, self.interact, self.minimap = cached
            self.dungeon.lock_rect = None
        else:
            seed = (self.run_seed * 1000003 + sum(ord(c) * 131 ** i for i, c in enumerate(floor_name))) & 0x3FFFFFFF
            self.dungeon = Dungeon(floor_name, seed)
            self.enc = Encounters(self.dungeon)
            self.interact = room_features.Interactables(self.dungeon, self.save)
            self.minimap = Minimap(self.dungeon)
            self.floors[floor_name] = (self.dungeon, self.enc, self.interact, self.minimap)
        self.save.pull_from(self.pc)
        self.save.apply_to(self.pc)
        self.pc.reset()
        self.toasts.clear()
        if at_exit:
            x, y = self.dungeon.exit_pos
            self.player.place(x, y + TILE * 3)
        else:
            self.player.place(*self.dungeon.spawn)
        seed = hash2(len(floor_name), ord(floor_name[0]) + ord(floor_name[2]))
        self.motes = Motes(self.dungeon.theme, seed)
        self.fog = Fog(self.dungeon.theme, seed)
        self.title_t = 0.0
        self.was_dead = False
        self.fx.clear()
        if self.state == "playing":
            self.autosave()
        self.snap_camera()

    def start_transition(self, target: str | None, at_exit: bool = False):
        if target and self.is_dungeon_unlocked(dungeon_for(target)) and self.fade_dir == 0:
            self.pending = (target, at_exit)
            self.fade_dir = 1

    def start_surface_return(self, dungeon_id: int):
        """Leave a finished dungeon through its boss-floor portal, back to Oakwood."""
        if self.fade_dir == 0:
            self.pending = ("__surface__", dungeon_id)
            self.fade_dir = 1

    def finish_surface_return(self, dungeon_id: int):
        self.return_to_surface(dungeon_id)
        self.fade, self.fade_dir = 1.0, -1
        self.surface.fade = 0.0
        self.surface.state = "play"
        sid = SURFACE_IDS.get(dungeon_id)
        self.autosave()
        if sid == "lich":
            self.open_dialog(story.EPILOGUE_LINES, after=self.finish_game)
        elif sid and f"beat_{sid}" not in self.save.flags and story.RETURN_BEATS.get(sid):
            self.save.flags.add(f"beat_{sid}")
            self.open_dialog(story.RETURN_BEATS[sid], after=self.autosave)

    def is_dungeon_unlocked(self, dungeon_id: int) -> bool:
        sid = SURFACE_IDS.get(dungeon_id)
        if sid is not None:     # the surface world's Progress decides what is open
            return self.surface.progress.is_unlocked(sw_mod.DUNGEON_BY_ID[sid])
        cleared = {SURFACE_NUMS[s] for s in self.save.cleared if s in SURFACE_NUMS}
        return dungeon_id == 1 or dungeon_id - 1 in cleared

    # ---- surface world bridge -------------------------------------------------
    def mark_cleared(self, dungeon_id: int):
        sid = SURFACE_IDS.get(dungeon_id)
        prog = self.surface.progress
        if sid is None or sid in prog.cleared:
            return
        prog.cleared.add(sid)
        self.autosave()
        d = sw_mod.DUNGEON_BY_ID[sid]
        opened = [x["name"] for x in sw_mod.DUNGEONS if x["requires"] == sid]
        msg = "%s cleared!" % d["name"]
        if opened:
            msg += "  Unlocked: " + ", ".join(opened)
        self.surface.toast(msg, (255, 230, 140))

    def enter_from_surface(self, sid: str) -> bool:
        """Called by the surface world once it has faded out on an unlocked portal."""
        floor = f"{SURFACE_NUMS[sid]}-1"
        self.night.abort()
        self.wilds.calm()
        self.run_seed = random.getrandbits(30)       # a fresh dungeon layout every visit
        self.floors.clear()
        self.change_floor(floor)
        if self.mode == "dungeon":
            self.fade, self.fade_dir = 1.0, -1
        # False: the surface world just parks the hero in front of the portal;
        # clearing is reported separately through mark_cleared().
        return False

    def return_to_surface(self, dungeon_id: int):
        sw = self.surface
        sid = SURFACE_IDS.get(dungeon_id)
        pt = next((p for p in sw.portals if p.d["id"] == sid), None)
        if pt is not None:
            sw.player.x, sw.player.y = pt.x, pt.y + 108
            sw.player.facing = "down"
        sw.pending = None
        sw.state, sw.fade = "fade_in", 1.0
        self.mode = "village"
        self.floors.clear()
        self.save.pull_from(self.pc)
        self.pc.reset()                 # a rest in the village restores HP
        self.fx.clear()
        self.snap_camera()
        self.autosave()

    def attack(self, aim=None):
        if self.fade_dir != 0 or self.pc.dead:
            return
        swung = self.pc.cd <= 0
        if swung:
            self.sfx.play("swing")
        before = self.target_hp()
        self.pc.try_attack(self.player, self.enc, aim)
        self.energy_from_hits(before)
        if swung and self.pc.swing > 0:
            self.interact.swing(self.player, self.pc.swing_dir)

    def near_exit(self) -> bool:
        ex, ey = self.dungeon.exit_pos
        return math.hypot(self.player.x - ex, self.player.y - ey) <= 56

    # ---- ui helpers -------------------------------------------------------------
    def panel(self, rect, border, alpha=205):
        """Glass panel drawn straight onto the screen."""
        draw_panel(self.screen, rect, border, alpha)

    def draw_text_shadow(self, font, text, color, x, y, alpha=255, center=False):
        img = font.render(text, True, color)
        sh = font.render(text, True, (0, 0, 0))
        if alpha < 255:
            img.set_alpha(alpha)
            sh.set_alpha(alpha)
        if center:
            x -= img.get_width() // 2
        self.screen.blit(sh, (x + 2, y + 2))
        self.screen.blit(img, (x, y))

    def draw_hud(self, cx, cy, t):
        """Zone title card that fades in when a floor starts."""
        tt = self.title_t
        if self.state != "playing" or tt > 4.0:
            return
        k = max(0.0, min(1.0, tt / 0.6, (4.0 - tt) / 0.8))
        th = self.dungeon.theme
        text = f"{th.name}  -  Floor {self.floor_name}"
        img = self.mid_font.render(text, True, (250, 240, 214))
        w, h = img.get_width() + 56, 46
        card = blank(w, h)
        draw_panel(card, card.get_rect(), th.accent, 225)
        card.blit(img, (28, (h - img.get_height()) // 2))
        card.set_alpha(int(255 * k))
        self.screen.blit(card, (SCREEN_W // 2 - w // 2, 16))

    # ---- overworld ------------------------------------------------------------------
    def draw_village(self, t):
        """Draw the procedural surface world, scaled to the game window."""
        sw, pc = self.surface, self.pc
        sw.hp, sw.max_hp, sw.potions = pc.hp, pc.max_hp, pc.potions
        sw.draw()
        pygame.transform.smoothscale(self.surface_canvas, (SCREEN_W, SCREEN_H), self.screen)
        if self.fade > 0:
            self.fade_surf.set_alpha(int(255 * min(1.0, self.fade)))
            self.screen.blit(self.fade_surf, (0, 0))

    def render(self, t, dcx, dcy, dt):
        if self.mode == "village":
            self.draw_village(t)
            return
        cx, cy = int(round(self.cam_x)), int(round(self.cam_y))
        art = self.dungeon.art
        glows = self.dungeon.draw_world(self.screen, cx, cy, t, self.player)
        glows += self.interact.glows(cx, cy)
        room_features.draw_lock_gates(self.screen, self.dungeon, self.enc, cx, cy, t, glows)
        # monsters, projectiles, barriers and the sword slash (drawn before lighting)
        self.enc.draw(self.screen, cx, cy, t, self.player, self.pc)
        self.interact.draw_fx(self.screen, cx, cy, t)
        self.player.blink = self.pc.blinking()
        psx, psy = int(self.player.x - cx), int(self.player.y - cy)

        self.screen.blit(art.light, (psx - SCREEN_W, psy - 14 - SCREEN_H))
        self.fog.update(dt, dcx, dcy)
        self.fog.draw(self.screen)
        for gx, gy, g in glows:
            self.screen.blit(g, (gx - g.get_width() // 2, gy - g.get_height() // 2),
                             special_flags=pygame.BLEND_RGB_ADD)
        fi = int((math.sin(t * 9) + math.sin(t * 14.7) + 2) / 4 * 2.99)
        lg = art.lantern_glows[fi]
        self.screen.blit(lg, (psx - lg.get_width() // 2, psy - 14 - lg.get_height() // 2),
                         special_flags=pygame.BLEND_RGB_ADD)

        self.screen.blit(self.vignette, (0, 0))

        self.motes.update(dt, dcx, dcy, t)
        self.motes.draw(self.screen, t)
        self.fx.draw(self.screen, cx, cy, t, self.mid_font)        # skills glow through the dark

        self.draw_hud(cx, cy, t)
        if self.show_map:
            self.minimap.draw(self.screen, self.small_font, self.player, cx, cy, t, self.enc)

        # player HP, objective text, boss bar, popups, banners, death screen
        self.enc.draw_hud(self.screen, cx, cy, self.pc, t)
        self.draw_dungeon_extras(cx, cy, t)

        if self.fade > 0:
            self.fade_surf.set_alpha(int(255 * min(1.0, self.fade)))
            self.screen.blit(self.fade_surf, (0, 0))

    def draw_level(self, scr, x, y, w):
        """'Lv N' badge and a thin XP bar."""
        lv, have, need = level_progress(self.save.xp)
        txt = "Lv %d" % lv
        scr.blit(self.small_font.render(txt, True, (0, 0, 0)), (x + 1, y + 1))
        scr.blit(self.small_font.render(txt, True, (170, 220, 255)), (x, y))
        bx = x + self.small_font.size(txt)[0] + 8
        bw = w - (bx - x)
        pygame.draw.rect(scr, (0, 0, 0), (bx - 1, y + 5, bw + 2, 8))
        pygame.draw.rect(scr, (30, 40, 70), (bx, y + 6, bw, 6))
        if need:
            pygame.draw.rect(scr, (120, 190, 255), (bx, y + 6, int(bw * have / need), 6))
        else:
            pygame.draw.rect(scr, (255, 214, 120), (bx, y + 6, bw, 6))

    def draw_hero_panel(self, scr, x, y):
        lv, have, need = level_progress(self.save.xp)
        return self.hero_hud.draw(scr, x, y, self.pc, name=story.hero_name(), level=lv, xp=(have, need),
                                  portrait=self.hero_portrait, class_name=self.pc.class_name)

    def draw_skill_bar(self, scr, bottom):
        W = scr.get_width()
        labels = {slot: self.key_label(slot) for slot in SLOTS}
        labels["dash"] = self.key_label("dash")
        self.hero_hud.draw_skills(scr, W - 150, bottom, self.pc, labels)

    def draw_village_hud(self, scr):
        """SurfaceWorld calls this from its HUD: hero panel + skill bar. Returns where the rest goes."""
        self.surface.controls_hint = self.controls_hint()
        bottom = self.draw_hero_panel(scr, 14, 12)
        self.draw_skill_bar(scr, scr.get_height() - 46)
        return bottom

    def draw_village_fx(self, scr, camx, camy, t):
        self.fx.draw(scr, camx, camy, t, self.mid_font)

    def draw_dungeon_extras(self, cx, cy, t):
        """Hero panel, gold counter, interaction prompt and banner toasts on top of the dungeon HUD."""
        scr = self.screen
        top = self.draw_hero_panel(scr, 12, 12)
        self.draw_skill_bar(scr, SCREEN_H - 14)
        gy = top + 14
        pygame.draw.circle(scr, (90, 60, 10), (25, gy + 1), 8)
        pygame.draw.circle(scr, (240, 196, 70), (25, gy), 6)
        pygame.draw.circle(scr, (255, 236, 150), (23, gy - 2), 2)
        img = self.small_font.render(f"{self.save.gold} gold", True, (255, 226, 130))
        scr.blit(self.small_font.render(f"{self.save.gold} gold", True, (0, 0, 0)), (39, gy - 6))
        scr.blit(img, (38, gy - 7))

        sid = SURFACE_IDS.get(dungeon_for(self.floor_name))
        y = gy + 20
        obj = self.interact.objective()
        if obj:
            text, col = obj
            scr.blit(self.small_font.render(text, True, (0, 0, 0)), (17, y + 1))
            scr.blit(self.small_font.render(text, True, col), (16, y))
            y += 22
        for q in quests.SIDE:
            if q.get("dungeon") and q["dungeon"][0] == sid and self.quests.state(q) in ("active", "ready"):
                txt = self.quests.progress_text(q)
                col = (255, 214, 120) if self.quests.state(q) == "ready" else (150, 210, 255)
                scr.blit(self.small_font.render(txt, True, (0, 0, 0)), (17, y + 1))
                scr.blit(self.small_font.render(txt, True, col), (16, y))
                y += 20

        prompt = self.interact.prompt(self.player)
        if prompt is None and self.near_exit() and self.enc.exit_open() and not self.pc.dead:
            if is_last_floor(self.floor_name) and dungeon_for(self.floor_name) in SURFACE_IDS:
                prompt = "[E]  Return to Oakwood"
            else:
                prompt = "[E]  Descend deeper"
        if prompt and self.dialog is None:
            img = self.mid_font.render(prompt, True, (250, 240, 214))
            w, h = img.get_width() + 32, 40
            px = int(self.player.x - cx) - w // 2
            py = int(self.player.y - cy) - 96
            r = pygame.Rect(px, py, w, h).clamp(scr.get_rect().inflate(-20, -20))
            draw_panel(scr, r, self.dungeon.theme.accent, 225)
            scr.blit(img, (r.x + 16, r.y + (h - img.get_height()) // 2))

        y = 162                         # under the hero panel
        for text, col, life in self.toasts:
            img = self.mid_font.render(text, True, col)
            w, h = img.get_width() + 40, 42
            card = blank(w, h)
            draw_panel(card, card.get_rect(), col, 220)
            card.blit(img, (20, (h - img.get_height()) // 2))
            card.set_alpha(int(255 * min(1.0, life / 0.5)))
            scr.blit(card, (SCREEN_W // 2 - w // 2, y))
            y += h + 6

    def on_night_event(self, kind):
        sm = getattr(self.surface, "merlin", None)
        if kind == "raid_start":
            if sm is not None:
                sm.say(random.choice(story.MERLIN_BARKS["raid"]))
            if "raid_intro" not in self.save.flags:
                self.save.flags.add("raid_intro")
                self.open_dialog(story.RAID_INTRO)
        elif kind in ("raid_won", "raid_lost"):
            if sm is not None:
                sm.say(random.choice(story.MERLIN_BARKS[kind]))
            self.autosave()

    def village_xp(self, amount, x, y):
        self.gain_xp(amount, x, y, self.wilds.floaters)

    def village_survival(self, dt):
        """Out of combat Himmel slowly heals; if he falls in the wilds, Merlin pulls him back."""
        pc, p = self.pc, self.surface.player
        if pc.dead:
            if self.night.active:
                return                                  # the raid handles its own defeat
            lost = min(30, self.save.gold // 10)
            self.save.gold -= lost
            pc.reset()
            p.x, p.y = night_raid.WARD_CENTER[0] - 40, night_raid.WARD_CENTER[1] + 60
            self.wilds.calm()
            self.surface.toast("Himmel fell... Merlin carried him home." + ("  -%d gold" % lost if lost else ""),
                               (255, 170, 150))
            sm = getattr(self.surface, "merlin", None)
            if sm is not None:
                sm.x, sm.y = p.x - 30, p.y + 6
                sm.say("Too far, too fast. Rest, then try again.")
            self.autosave()
            return
        if pc.hp < pc.max_hp and not self.night.active and not self.wilds.hostile_near(p.x, p.y, 360):
            self.regen += dt * 2.0
            if self.regen >= 1:
                pc.heal(int(self.regen))
                self.regen -= int(self.regen)

    def player_swing(self, player, dx, dy, dmg):
        """PlayerCombat.try_attack target in the overworld: raid monsters and the wilds."""
        self.night.player_swing(player, dx, dy, dmg)
        self.wilds.player_swing(player, dx, dy, dmg)

    def village_attack(self, aim=None):
        """Sword swing in the overworld."""
        pc = self.pc
        if pc.dead or pc.cd > 0:
            return
        p = self.surface.player
        if aim is None:            # Space / J: strike the way Himmel is facing
            aim = {"up": (0, -1), "down": (0, 1)}.get(p.facing, (-1, 0) if p.flip else (1, 0))
        self.sfx.play("swing")
        before = self.target_hp()
        pc.try_attack(p, self, aim)
        self.energy_from_hits(before)

    def handle_interact_events(self):
        for ev in self.interact.pop_events():
            kind = ev[0]
            if kind == "sound":
                self.sfx.play(ev[1])
            elif kind == "toast":
                self.toast(ev[1], ev[2] if len(ev) > 2 else (240, 230, 200))
            elif kind == "dialog":
                self.open_dialog(ev[1], after=self.autosave)
            elif kind == "save":
                self.autosave()
            elif kind == "heal":
                self.pc.heal(self.pc.max_hp)
            elif kind == "potion":
                if self.pc.add_potion():
                    self.save.pull_from(self.pc)
                    self.toast("Found a healing potion!", (255, 150, 160), 2.0)
                    self.sfx.play("potion")

    # ---- overlays -------------------------------------------------------------
    def veil(self, alpha):
        v = pygame.Surface((SCREEN_W, SCREEN_H), pygame.SRCALPHA)
        v.fill((0, 0, 0, alpha))
        self.screen.blit(v, (0, 0))

    def can_continue(self) -> bool:
        # a saved hero (name + class) can always be continued until the story is finished
        return self.has_save and "finished" not in self.save.flags

    PAUSE_ITEMS = (("RESUME", "resume"), ("SETTINGS", "settings"), ("SAVE & QUIT TO MENU", "menu"),
                   ("QUIT GAME", "quit"))

    def pause_rects(self):
        w, h, gap = 360, 54, 12
        top = SCREEN_H // 2 - 70
        return [pygame.Rect(SCREEN_W // 2 - w // 2, top + i * (h + gap), w, h) for i in range(len(self.PAUSE_ITEMS))]

    def draw_pause(self):
        if self.pause_settings is not None:            # settings on top of the frozen game
            canvas = pygame.Surface((ui_theme.SCREEN_W, ui_theme.SCREEN_H))
            ox, oy = (SCREEN_W - ui_theme.SCREEN_W) // 2, (SCREEN_H - ui_theme.SCREEN_H) // 2
            canvas.blit(self.screen, (0, 0), (ox, oy, ui_theme.SCREEN_W, ui_theme.SCREEN_H))
            self.pause_settings.draw(canvas)
            self.screen.blit(canvas, (ox, oy))
            return
        ui_widgets.dim(self.screen, 165)
        panel = pygame.Rect(SCREEN_W // 2 - 230, SCREEN_H // 2 - 190, 460, 400)
        ui_widgets.stone_panel(self.screen, panel)
        ui_widgets.title_plate(self.screen, (SCREEN_W // 2, panel.y + 6), "PAUSED")
        s = self.save
        ui_text(self.screen, "%s THE %s  -  LV %d" % (story.hero_name().upper(), self.pc.class_name.upper(), s.level),
                get_font(ui_theme.FONT_SMALL), ui_theme.TITLE, (SCREEN_W // 2, panel.y + 62), outline=1, center=True)
        for i, ((label, _a), r) in enumerate(zip(self.PAUSE_ITEMS, self.pause_rects())):
            ui_widgets.button(self.screen, tuple(r), label, selected=i == self.pause_sel)
        ui_text(self.screen, "UP / DOWN + ENTER    ESC: RESUME", get_font(ui_theme.FONT_SMALL), ui_theme.TEXT_DIM,
                (SCREEN_W // 2, panel.bottom - 26), outline=1, center=True)

    def pause_action(self, action):
        """Returns False when the game should quit."""
        if action == "resume":
            self.paused = False
        elif action == "settings":
            self.pause_settings = SettingsScreen(self.settings)
        elif action == "menu":
            self.return_to_menu()
        elif action == "quit":
            self.autosave()
            return False
        return True

    def handle_pause_event(self, event, key, click):
        if self.pause_settings is not None:
            ev = event
            if hasattr(event, "pos") and event.type in (pygame.MOUSEMOTION, pygame.MOUSEBUTTONDOWN,
                                                        pygame.MOUSEBUTTONUP):
                ox, oy = (SCREEN_W - ui_theme.SCREEN_W) // 2, (SCREEN_H - ui_theme.SCREEN_H) // 2
                data = dict(event.dict)
                data["pos"] = (event.pos[0] - ox, event.pos[1] - oy)
                ev = pygame.event.Event(event.type, data)
            result = self.pause_settings.handle_event(ev)
            if result == SETTINGS_BACK:
                self.pause_settings = None
                self.settings_changed()
            elif result == VIDEO_CHANGED:
                self.screen = self.settings.apply_display((SCREEN_W, SCREEN_H))
            return True
        if key == pygame.K_ESCAPE:
            self.paused = False
        elif key in (pygame.K_UP, pygame.K_w):
            self.pause_sel = (self.pause_sel - 1) % len(self.PAUSE_ITEMS)
        elif key in (pygame.K_DOWN, pygame.K_s):
            self.pause_sel = (self.pause_sel + 1) % len(self.PAUSE_ITEMS)
        elif key in (pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_SPACE):
            return self.pause_action(self.PAUSE_ITEMS[self.pause_sel][1])
        elif key == pygame.K_q:
            return self.pause_action("quit")
        elif event.type == pygame.MOUSEMOTION:
            for i, r in enumerate(self.pause_rects()):
                if r.collidepoint(event.pos):
                    self.pause_sel = i
        elif click:
            for i, r in enumerate(self.pause_rects()):
                if r.collidepoint(event.pos):
                    return self.pause_action(self.PAUSE_ITEMS[i][1])
        return True

    def settings_changed(self):
        self.settings.save()
        self.build_keys()
        self.apply_volumes()

    def draw_victory(self, t):
        self.veil(170)
        cx = SCREEN_W // 2
        self.draw_text_shadow(self.huge_font, "VICTORY", (255, 226, 120), cx, 150, 255, True)
        self.draw_text_shadow(self.mid_font, "The Veil has fallen. Oakwood is free.", (240, 236, 224), cx, 250, 255, True)
        self.draw_text_shadow(self.font, "...but somewhere beyond the mountains, the Veilwright is watching.",
                              (190, 180, 230), cx, 286, 255, True)
        s = self.save
        done = sum(1 for q in quests.SIDE if self.quests.state(q) == "done")
        self.draw_text_shadow(self.font, f"Anchors shattered: {len(s.keepsakes)}/3     Side quests: {done}/"
                              f"{len(quests.SIDE)}     Nights defended: {s.raids}     Gold: {s.gold}",
                              (220, 210, 170), cx, 326, 255, True)
        self.draw_text_shadow(self.mid_font, "%s and Merlin will return.  Thank you for playing." % story.hero_name(),
                              (200, 200, 214), cx, 372, 255, True)
        if int(t * 2) % 2 == 0:
            self.draw_text_shadow(self.font, "Press Esc to return to the menu", (255, 226, 140), cx, 440, 255, True)

    # ---- input ------------------------------------------------------------------
    def handle_event(self, event) -> bool:
        """Returns False when the game should quit."""
        key = event.key if event.type == pygame.KEYDOWN else None
        click = event.type == pygame.MOUSEBUTTONDOWN and event.button == 1
        confirm = key in (pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_SPACE)

        if self.state == "menu":
            result = self.front.handle_event(event)
            if result is None:
                if self.front.screen == "menu":
                    self.settings_changed_quiet()
                return True
            if result[0] == "quit":
                return False
            if result[0] == "continue":
                self.begin_game(new=False)
            elif result[0] == "new":
                _kind, name, hero_class = result
                self.begin_game(new=True, name=name, hero_class=hero_class)
            elif result[0] == "video":
                self.screen = self.settings.apply_display((SCREEN_W, SCREEN_H))
            return True
        if self.dialog is not None:          # a dialog swallows all other input
            if key == pygame.K_ESCAPE:
                self.dialog.skip()
            elif confirm or key == pygame.K_e or click:
                self.dialog.advance()
                self.sfx.play("blip")
            return True
        if self.shop is not None:            # so does the shop
            if key is not None and not self.shop.handle_key(key):
                self.shop = None
                self.autosave()
            return True
        if self.journal is not None:
            if key is not None and not self.journal.handle_key(key):
                self.journal = None
            return True
        if self.victory:
            if key in (pygame.K_ESCAPE, pygame.K_RETURN, pygame.K_KP_ENTER):
                self.return_to_menu()
            return True
        if self.paused:
            return self.handle_pause_event(event, key, click)

        slot = next((sl for sl in SLOTS if key in self.keys[sl]), None) if key is not None else None
        if slot is not None:
            self.cast_skill(slot)
            return True
        if key is not None and key in self.keys["dash"]:
            self.dash()
            return True

        if key in (pygame.K_TAB, pygame.K_l) and self.fade_dir == 0:
            self.journal = Journal(self.save, self.quests, self.sfx)
            self.sfx.play("blip")
            return True

        if self.mode == "village":
            sw = self.surface
            if sw.state == "play" and self.fade_dir == 0:
                if key in self.keys["attack"]:
                    self.village_attack()
                    return True
                if click:
                    camx, camy = sw.camera()
                    kx, ky = sw_mod.SCREEN_W / SCREEN_W, sw_mod.SCREEN_H / SCREEN_H
                    wx, wy = event.pos[0] * kx + camx, event.pos[1] * ky + camy
                    self.village_attack((wx - sw.player.x, wy - (sw.player.y - 14)))
                    return True
            if key == pygame.K_ESCAPE:
                self.paused, self.pause_sel = True, 0
            elif sw.state != "play" or self.fade_dir > 0:
                pass
            elif key in self.keys["interact"]:
                sw.interact()
            elif key == pygame.K_m:
                sw.show_map = not sw.show_map
            elif key in (pygame.K_h, pygame.K_p):
                if self.drink_potion():
                    sw.toast("You drink a potion", (255, 170, 170))
            return True

        if click:
            mcx, mcy = int(round(self.cam_x)), int(round(self.cam_y))
            self.attack((event.pos[0] - (self.player.x - mcx),
                         event.pos[1] - (self.player.y - 14 - mcy)))
            return True
        if key is None:
            return True
        if key == pygame.K_ESCAPE:
            self.paused, self.pause_sel = True, 0
        elif key in self.keys["interact"]:
            if self.fade_dir != 0 or self.pc.dead:
                pass
            elif self.interact.use(self.player):          # tablet / keepsake
                self.handle_interact_events()
            elif self.near_exit() and self.enc.exit_open():
                did = dungeon_for(self.floor_name)
                if is_boss_floor(self.floor_name) and self.interact.take_keepsake():
                    self.handle_interact_events()      # don't leave the keepsake behind
                    return True
                if is_last_floor(self.floor_name) and did in SURFACE_IDS:
                    self.start_surface_return(did)
                else:
                    self.start_transition(next_floor(self.floor_name))
        elif key == pygame.K_q:
            if not self.enc.locked and not self.pc.dead:
                if self.floor_name in ("1-1", "2-1", "3-1") or minis.is_mini_floor(self.floor_name):
                    self.return_to_surface(dungeon_for(self.floor_name))
                else:
                    self.start_transition(previous_floor(self.floor_name), True)
        elif key == pygame.K_r:
            if self.pc.dead:
                self.retry_room()
            elif not self.enc.locked:
                self.player.place(*self.dungeon.spawn)
        elif key in self.keys["attack"]:
            self.attack()
        elif key == pygame.K_m:
            self.show_map = not self.show_map
        elif key in (pygame.K_h, pygame.K_p):
            if self.fade_dir == 0 and self.enc.use_potion(self.player, self.pc):
                bonus = self.save.potion_bonus()      # Mending Herbs
                if bonus:
                    self.pc.heal(bonus)
                self.save.pull_from(self.pc)
                self.sfx.play("potion")
        return True

    def settings_changed_quiet(self):
        """The home screen's Settings may have changed keys or volume: pick them up."""
        self.build_keys()
        self.apply_volumes()

    def run(self):
        running = True
        t = 0.0
        self.fade_dir = -1
        while running:
            dt = min(self.clock.tick(FPS) / 1000.0, 0.05)
            t += dt

            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                elif not self.handle_event(event):
                    running = False

            # screen fades keep running behind the menus
            if self.fade_dir > 0:
                self.fade += dt * 3.5
                if self.fade >= 1.0:
                    self.fade = 1.0
                    target, at_exit = self.pending
                    if target == "__surface__":
                        self.finish_surface_return(at_exit)
                    else:
                        self.change_floor(target, at_exit)
                    self.fade_dir = -1
            elif self.fade_dir < 0:
                self.fade -= dt * 2.5
                if self.fade <= 0.0:
                    self.fade = 0.0
                    self.fade_dir = 0

            playing = self.state == "playing" and not self.paused and not self.victory
            if self.state == "playing":
                self.hero_hud.update(dt, self.pc)        # also behind dialogs, so the bars are never empty
            for tt in self.toasts:
                tt[2] -= dt
            self.toasts = [x for x in self.toasts if x[2] > 0]
            if self.shop is not None:
                self.shop.update(dt)
            menu = self.dialog is not None or self.shop is not None or self.journal is not None
            if self.mode == "village" and playing and menu:
                self.surface.update_life(dt)          # the village keeps living behind menus
            if self.dialog is not None:
                self.dialog.update(dt)
                if self.dialog.done:
                    after, self.after_dialog = self.after_dialog, None
                    self.dialog = None
                    if after:
                        after()
            elif self.shop is not None or self.journal is not None:
                pass
            elif playing:
                self.title_t += dt
                keys = pygame.key.get_pressed()
                dx = float(keys[pygame.K_d] or keys[pygame.K_RIGHT]) - float(
                    keys[pygame.K_a] or keys[pygame.K_LEFT])
                dy = float(keys[pygame.K_s] or keys[pygame.K_DOWN]) - float(
                    keys[pygame.K_w] or keys[pygame.K_UP])
                if self.fade_dir > 0 or self.pc.dead:
                    dx = dy = 0.0
                if self.mode == "village":
                    # movement, portal fades and entering dungeons are handled by
                    # the surface world (it calls enter_from_surface()).
                    self.surface.frozen = self.pc.dead
                    self.surface.update(dt)
                    free = self.fade_dir == 0 and self.surface.state == "play"
                    self.pc.update(dt)
                    self.surface.player.blink = self.pc.blinking()
                    self.night.update(dt, free)
                    self.wilds.update(dt, free)
                    if self.mode == "village":
                        self.update_skills(dt)
                    self.village_survival(dt)
                else:
                    self.player.move(dx, dy, self.dungeon, dt)
                    self.pc.update(dt)
                    self.player.blink = self.pc.blinking()
                    if self.fade_dir == 0:
                        self.enc.update(dt, self.player, self.pc)
                    self.update_skills(dt)
                    self.interact.update(dt, self.player, self.pc, self.enc)
                    self.handle_interact_events()
                    self.after_update()

            for name in self.enc.sound_queue:
                self.sfx.play(name)
            self.enc.sound_queue.clear()

            tx, ty = self.camera_target()
            k = min(1.0, dt * 8)
            self.cam_x += (tx - self.cam_x) * k
            self.cam_y += (ty - self.cam_y) * k
            cur = (int(round(self.cam_x)), int(round(self.cam_y)))
            dcx, dcy = cur[0] - self.prev_cam[0], cur[1] - self.prev_cam[1]
            self.prev_cam = cur

            if self.mode == "village":
                self.surface.t += dt          # keep torches / fireflies animating
            else:
                self.minimap.reveal(int(self.player.x // TILE), int(self.player.y // TILE))
                if self.minimap.step(dt) and self.state == "playing":      # every room found
                    bonus = 15 * self.interact.tier
                    self.save.gold += bonus
                    self.toast("Floor mapped!  +%d gold" % bonus, (150, 220, 150))
                    self.sfx.play("clear")
            self.update_music(dt)
            if self.state == "menu":
                self.front.update(dt)
                self.front.draw(self.screen)
                pygame.display.flip()
                continue
            self.render(t, dcx, dcy, dt)
            if self.shop is not None and self.dialog is None:
                self.shop.draw(self.screen, t)
            if self.journal is not None and self.dialog is None:
                self.journal.draw(self.screen, t)
            if self.dialog is not None:
                self.dialog.draw(self.screen, t)
            elif self.victory:
                self.draw_victory(t)
            elif self.paused:
                self.draw_pause()
            pygame.display.flip()

        pygame.quit()
        return 0


if __name__ == "__main__":
    raise SystemExit(Game().run())