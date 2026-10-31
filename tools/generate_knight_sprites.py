"""
generate_knight_sprites.py - builds every Warrior (knight) animation frame.

Run from the repo root:
    python tools/generate_knight_sprites.py

Input : assets/characters/knight_idle.png        (the 48x48 knight - never modified)
Output: assets/characters/knight_spritesheet.png (all frames, 75x70 cells)
        assets/characters/knight_animations.json (frame rects, timings, loop flags)
        assets/characters/animations/knight_<behaviour>.png (one strip per behaviour)

How it works: the idle knight is cut into parts (plume, head, torso, shield, legs,
sword-arm). Each frame is a "pose" that moves/tints those parts, and for the attack
and death poses the sword arm is redrawn with the same palette so the blade can
swing. The art style therefore stays identical to knight_idle.png.
"""
import json
import math
import os

from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CHAR_DIR = os.path.join(ROOT, "assets", "characters")
ANIM_DIR = os.path.join(CHAR_DIR, "animations")

FW, FH = 75, 70          # cell size (unchanged from the old sheet)
OX, OY = 14, 21          # where the 48x48 idle sprite sits inside a cell
PIVOT = (37, 49)         # cell pixel that lines up with Player.x / Player.y

PAL = {
    "a": (20, 16, 24, 255),      # outline
    "d": (86, 92, 106, 255),     # steel dark
    "e": (120, 128, 142, 255),   # steel mid
    "g": (176, 184, 196, 255),   # steel light
    "f": (214, 220, 228, 255),   # steel highlight
    "i": (214, 172, 74, 255),    # gold
    "l": (156, 120, 46, 255),    # gold dark
    "m": (94, 62, 42, 255),      # leather
    "W": (246, 249, 255, 255),   # slash flash
}

# --------------------------------------------------------------------------- parts
idle = Image.open(os.path.join(CHAR_DIR, "knight_idle.png")).convert("RGBA")


def _shield(x, y):
    return (y == 21 and x <= 10) or (22 <= y <= 37 and x <= 11) or (y in (38, 39) and x <= 12)


def _torso(x, y):
    return ((19 <= y <= 37 and 10 <= x <= 31) or (y == 38 and 13 <= x <= 14)) and not _shield(x, y)


MASKS = {
    "plume": lambda x, y: 2 <= y <= 6 and 18 <= x <= 29,
    "head": lambda x, y: 7 <= y <= 18 and 14 <= x <= 32,
    "shield": _shield,
    "torso": _torso,
    "leg_l": lambda x, y: y >= 38 and 15 <= x <= 23,
    "leg_r": lambda x, y: y >= 38 and 24 <= x <= 32,
    "arm": lambda x, y: (x >= 32 and 19 <= y <= 40) or (x >= 33 and 7 <= y < 19),
}


def extract(mask):
    out = Image.new("RGBA", idle.size, (0, 0, 0, 0))
    src, dst = idle.load(), out.load()
    for y in range(idle.height):
        for x in range(idle.width):
            if src[x, y][3] and mask(x, y):
                dst[x, y] = src[x, y]
    return out


PARTS = {k: extract(m) for k, m in MASKS.items()}

# every opaque pixel must belong to exactly one part, or frames would lose / double pixels
_cover = Image.new("L", idle.size, 0)
for _p in PARTS.values():
    _cover.paste(255, mask=_p.getchannel("A"))
assert list(_cover.getdata()) == list(idle.getchannel("A").getdata()), "part masks miss pixels"


def paste(canvas, part, x, y):
    canvas.alpha_composite(part, (x, y)) if x >= 0 and y >= 0 else canvas.paste(
        part, (x, y), part)


# --------------------------------------------------------------- procedural drawing
def disc(cx, cy, r):
    return {(x, y) for y in range(int(cy - r) - 1, int(cy + r) + 2)
            for x in range(int(cx - r) - 1, int(cx + r) + 2)
            if (x + 0.5 - cx) ** 2 + (y + 0.5 - cy) ** 2 <= r * r}


def arm_pixels(s, h, w=2.3):
    pts = set()
    n = max(2, int(math.hypot(h[0] - s[0], h[1] - s[1]) * 2))
    for i in range(n + 1):
        t = i / n
        pts |= disc(s[0] + (h[0] - s[0]) * t, s[1] + (h[1] - s[1]) * t, w)
    out = {}
    for (x, y) in pts:
        out[(x, y)] = "g" if (x, y - 1) not in pts else ("d" if (x, y + 1) not in pts else "e")
    return out


def sword_pixels(hand, theta_deg, length=17):
    """Sword whose fist is at `hand` and whose blade points along theta (0 = right, +90 = down)."""
    th = math.radians(theta_deg)
    dx, dy = math.cos(th), math.sin(th)
    nx, ny = dy, -dx                              # left-hand normal -> bright edge
    gx, gy = hand[0] + 4.5 * dx, hand[1] + 4.5 * dy   # guard centre
    out = {}
    x0, x1 = int(min(gx, gx + length * dx, hand[0]) - 12), int(max(gx, gx + length * dx, hand[0]) + 12)
    y0, y1 = int(min(gy, gy + length * dy, hand[1]) - 12), int(max(gy, gy + length * dy, hand[1]) + 12)
    for y in range(y0, y1):
        for x in range(x0, x1):
            px, py = x + 0.5 - gx, y + 0.5 - gy
            u, v = px * dx + py * dy, px * nx + py * ny
            if 1.5 <= u <= length:
                hw = 2.0 if u <= length - 4 else max(0.6, 2.0 * (length - u) / 4 + 0.4)
                if abs(v) < hw:
                    out[(x, y)] = "f" if v > 0 else "e"
            elif -1.5 <= u < 1.5 and abs(v) <= 4.5:
                out[(x, y)] = "i" if v > 0 else "l"
            elif -7 <= u < -1.5 and abs(v) < 1.3:
                out[(x, y)] = "m"
            elif -10 <= u < -7 and abs(v) < 2.0:
                out[(x, y)] = "l"
    return out


def hand_pixels(h):
    d = disc(h[0], h[1], 3.0)
    return {p: ("g" if (p[0] + p[1] < h[0] + h[1] - 1.5) else "d") for p in d}


def pauldron_pixels(ox, oy):
    out = {}
    for y, c in ((20, "f"), (21, "f"), (22, "g"), (23, "e")):
        for x in range(32, 38):
            out[(x + ox, y + oy)] = c if not (x == 37) else "e"
    return out


def put(canvas, pixels, dx=0, dy=0, outline=True, solid_only=False, clip_y=None):
    """Draw {(x,y): palette key} onto canvas (sprite coords + (dx, dy)); optional outline."""
    px = canvas.load()
    shifted = {(x + dx, y + dy): c for (x, y), c in pixels.items()
               if clip_y is None or y + dy < clip_y}
    if outline:
        for (x, y) in list(shifted):
            for nx, ny in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
                if (nx, ny) not in shifted and 0 <= nx < canvas.width and 0 <= ny < canvas.height:
                    if not solid_only or px[nx, ny][3] == 0:
                        px[nx, ny] = PAL["a"]
    for (x, y), c in shifted.items():
        if 0 <= x < canvas.width and 0 <= y < canvas.height:
            px[x, y] = PAL[c]


def swoosh(canvas, centre, radius, a0, a1, thick=5.0):
    """Tapered slash trail: thin/dim at the start angle, thick/bright at the end angle."""
    px = canvas.load()
    cx, cy = centre
    for y in range(canvas.height):
        for x in range(canvas.width):
            dx, dy = x + 0.5 - cx, y + 0.5 - cy
            r = math.hypot(dx, dy)
            a = math.degrees(math.atan2(dy, dx))
            if a1 >= a0 and not (a0 <= a <= a1):
                continue
            t = (a - a0) / (a1 - a0)
            if abs(r - radius) <= thick * t / 2 + 0.2 and t > 0.08:
                px[x, y] = PAL["W"] if t > 0.7 else (PAL["f"] if t > 0.4 else PAL["g"])


def sparkle(canvas, x, y):
    px = canvas.load()
    for ox, oy, c in ((0, 0, "W"), (1, 0, "W"), (-1, 0, "W"), (0, 1, "W"), (0, -1, "W"),
                      (2, 0, "i"), (-2, 0, "i"), (0, 2, "i"), (0, -2, "i"),
                      (2, 2, "f"), (-2, -2, "f"), (2, -2, "f"), (-2, 2, "f")):
        if 0 <= x + ox < canvas.width and 0 <= y + oy < canvas.height:
            px[x + ox, y + oy] = PAL[c]


def tint(img, colour, strength):
    out = img.copy()
    px = out.load()
    for y in range(out.height):
        for x in range(out.width):
            r, g, b, a = px[x, y]
            if a:
                keep = 0.55 if (r, g, b, a) == PAL["a"] else 1.0
                s = strength * keep
                px[x, y] = (int(r + (colour[0] - r) * s), int(g + (colour[1] - g) * s),
                            int(b + (colour[2] - b) * s), a)
    return out


# --------------------------------------------------------------------------- poses
def build_figure(body=(0, 0), head=(0, 0), plume=(0, 0), shield=(0, 0), leg_l=(0, 0),
                 leg_r=(0, 0), keep_arm=True, arm=(0, 0), legs_clip=None):
    """Assemble the body parts in cell coordinates (legs behind, then shield, torso, head, arm)."""
    c = Image.new("RGBA", (FW, FH), (0, 0, 0, 0))
    bx, by = body
    for name, off in (("leg_l", leg_l), ("leg_r", leg_r)):
        part = PARTS[name]
        if legs_clip:
            part = part.crop((0, 0, 48, legs_clip)).copy()
            part = _pad(part)
        paste(c, part, OX + off[0], OY + off[1])
    paste(c, PARTS["shield"], OX + bx + shield[0], OY + by + shield[1])
    paste(c, PARTS["torso"], OX + bx, OY + by)
    paste(c, PARTS["head"], OX + bx + head[0], OY + by + head[1])
    paste(c, PARTS["plume"], OX + bx + head[0] + plume[0], OY + by + head[1] + plume[1])
    if keep_arm:
        paste(c, PARTS["arm"], OX + bx + arm[0], OY + by + arm[1])
    return c


def _pad(img):
    out = Image.new("RGBA", (48, 48), (0, 0, 0, 0))
    out.paste(img, (0, 0))
    return out


def shear_lean(img, pivot_y, slope, squash):
    """Pixel-aligned 'fall' look: rows above the hip slide sideways and get closer to it."""
    out = Image.new("RGBA", img.size, (0, 0, 0, 0))
    for y in range(img.height):
        if y < pivot_y:
            src_y = pivot_y - round((pivot_y - y) / squash)
            sh = -round((pivot_y - y) * slope)
        else:
            src_y, sh = y, 0
        if 0 <= src_y < img.height:
            row = img.crop((0, src_y, img.width, src_y + 1))
            out.paste(row, (sh, y), row)
    return out


FRAMES = {}


def frame(name):
    def deco(fn):
        FRAMES[name] = fn
        return fn
    return deco


# --- idle -------------------------------------------------------------------------
@frame("idle_0")
def _():
    return build_figure()


@frame("idle_1")
def _():
    return build_figure(body=(0, 1))


# --- walk (feet alternate, body bobs, shield and plume lag a little) ----------------
@frame("walk_0")
def _():
    return build_figure(leg_l=(0, -3), head=(0, 0), plume=(1, 0))


@frame("walk_1")
def _():
    return build_figure(body=(0, 1), shield=(0, -1))


@frame("walk_2")
def _():
    return build_figure(leg_r=(0, -3), plume=(-1, 0), shield=(0, 1))


@frame("walk_3")
def _():
    return build_figure(body=(0, 1), shield=(0, -1))


# --- attack (wind-up -> slash -> follow-through) --------------------------------------
SHOULDER = (35, 22)


def _swing(fig, body, hand, theta, trail=None, flash=False):
    bx, by = body
    px_ = Image.new("RGBA", fig.size, (0, 0, 0, 0))
    put(px_, pauldron_pixels(0, 0), OX + bx, OY + by, outline=True, solid_only=True)
    fig.alpha_composite(px_)
    if trail:
        swoosh(fig, (OX + bx + SHOULDER[0], OY + by + SHOULDER[1]), *trail)
    layer = Image.new("RGBA", fig.size, (0, 0, 0, 0))
    h = (hand[0] + OX + bx, hand[1] + OY + by)
    s = (SHOULDER[0] + OX + bx + 1, SHOULDER[1] + OY + by + 2)
    shape = arm_pixels(s, h)
    shape.update(sword_pixels(h, theta))
    shape.update(hand_pixels(h))
    put(layer, shape, 0, 0, outline=True)
    fig.alpha_composite(layer)
    return fig


@frame("attack_0")
def _():
    fig = build_figure(body=(-1, 0), keep_arm=False, leg_l=(-1, 0), leg_r=(0, 0), head=(-1, 0))
    return _swing(fig, (-1, 0), (39, 16), -104)


@frame("attack_1")
def _():
    fig = build_figure(body=(2, 1), keep_arm=False, shield=(-1, 0), leg_l=(-2, 0), leg_r=(2, 0),
                       head=(1, 0), plume=(1, 0))
    return _swing(fig, (2, 1), (39, 24), 38, trail=(21, -75, 35, 5.5))


@frame("attack_2")
def _():
    fig = build_figure(body=(1, 2), keep_arm=False, shield=(-1, 0), leg_l=(-1, 0), leg_r=(1, 0),
                       head=(1, 1))
    return _swing(fig, (1, 2), (40, 28), 58, trail=(21, 10, 58, 3.0))


# --- hurt (red flash, knocked back, impact sparkle) ---------------------------------------
@frame("hurt_0")
def _():
    fig = build_figure(body=(-2, 1), head=(-1, 1), plume=(-1, 0), shield=(-1, 0),
                       leg_l=(-1, 0), leg_r=(-1, 0))
    fig = tint(fig, (255, 70, 60), 0.6)
    sparkle(fig, OX + 31, OY + 25)
    return fig


@frame("hurt_1")
def _():
    fig = build_figure(body=(-1, 0), head=(0, 1), plume=(-1, 0), leg_l=(-1, 0), leg_r=(-1, 0))
    return tint(fig, (255, 90, 80), 0.3)


# --- dead (stagger -> kneel -> topple -> lie down, sword dropped) -------------------------
def _limp_arm(fig, shoulder, hand):
    layer = Image.new("RGBA", fig.size, (0, 0, 0, 0))
    shape = arm_pixels(shoulder, hand)
    shape.update(hand_pixels(hand))
    put(layer, shape, 0, 0, outline=True)
    fig.alpha_composite(layer)


@frame("dead_0")
def _():
    fig = build_figure(body=(-2, 2), head=(-1, 2), plume=(-1, 0), keep_arm=False,
                       leg_l=(-1, 0), leg_r=(0, 0))
    return _swing(fig, (-2, 2), (39, 25), 118)


@frame("dead_1")
def _():
    fig = build_figure(body=(-3, 9), head=(-1, 2), plume=(-1, 0), keep_arm=False, shield=(-1, 0),
                       leg_l=(-4, -1), leg_r=(6, -1), legs_clip=48)
    layer = Image.new("RGBA", fig.size, (0, 0, 0, 0))
    h = (OX + 40, OY + 31)
    shape = arm_pixels((OX + 33, OY + 31), h)
    shape.update(sword_pixels(h, 90))
    shape.update(hand_pixels(h))
    put(layer, shape, 0, 0, outline=True, clip_y=OY + 48)
    fig.alpha_composite(layer)
    px = Image.new("RGBA", fig.size, (0, 0, 0, 0))
    put(px, pauldron_pixels(0, 0), OX - 3, OY + 9, outline=True, solid_only=True)
    fig.alpha_composite(px)
    return fig


@frame("dead_2")
def _():
    fig = build_figure(body=(0, 1), keep_arm=False, leg_l=(0, 0), leg_r=(0, 0))
    _limp_arm(fig, (OX + 35, OY + 23), (OX + 37, OY + 34))
    px = Image.new("RGBA", fig.size, (0, 0, 0, 0))
    put(px, pauldron_pixels(0, 1), OX, OY, outline=True, solid_only=True)
    fig.alpha_composite(px)
    fig = fig.rotate(42, resample=Image.NEAREST, center=(OX + 22, OY + 38))
    box = fig.getbbox()
    fig = fig.transform(fig.size, Image.AFFINE,
                        (1, 0, -max(0, 3 - box[0]), 0, 1, (FH - 3) - box[3]), Image.NEAREST)
    layer = Image.new("RGBA", fig.size, (0, 0, 0, 0))
    put(layer, sword_pixels((55, 30), 28), 0, 0, outline=True)      # thrown sword, mid-air
    fig.alpha_composite(layer)
    return fig


@frame("dead_3")
def _():
    fig = build_figure(body=(0, 0), head=(0, 0), keep_arm=False, shield=(6, 0))
    _limp_arm(fig, (OX + 35, OY + 22), (OX + 36, OY + 33))
    px = Image.new("RGBA", fig.size, (0, 0, 0, 0))
    put(px, pauldron_pixels(0, 0), OX, OY, outline=True, solid_only=True)
    fig.alpha_composite(px)
    box = fig.getbbox()
    fig = fig.crop(box).transpose(Image.ROTATE_90)       # head to the left, lying on its back
    out = Image.new("RGBA", (FW, FH), (0, 0, 0, 0))
    out.alpha_composite(fig, (1, FH - 2 - fig.height))
    layer = Image.new("RGBA", out.size, (0, 0, 0, 0))
    put(layer, sword_pixels((52, 63), 0), 0, 0, outline=True)
    out.alpha_composite(layer)
    return out


# ------------------------------------------------------------------------- manifest
ANIMATIONS = {
    "idle":   {"frames": ["idle_0", "idle_1"], "frame_duration_ms": 500, "loop": True},
    "walk":   {"frames": ["walk_0", "walk_1", "walk_2", "walk_3"], "frame_duration_ms": 120, "loop": True},
    "attack": {"frames": ["attack_0", "attack_1", "attack_2"], "frame_duration_ms": [70, 90, 140], "loop": False},
    "hurt":   {"frames": ["hurt_0", "hurt_1"], "frame_duration_ms": [80, 120], "loop": False},
    "dead":   {"frames": ["dead_0", "dead_1", "dead_2", "dead_3"], "frame_duration_ms": [100, 100, 100, 600],
               "loop": False, "hold_last_frame": True},
}


def main():
    os.makedirs(ANIM_DIR, exist_ok=True)
    rows = list(ANIMATIONS.items())
    sheet = Image.new("RGBA", (FW * 4, FH * len(rows)), (0, 0, 0, 0))
    rects, images = {}, {}
    for r, (anim, spec) in enumerate(rows):
        strip = Image.new("RGBA", (FW * len(spec["frames"]), FH), (0, 0, 0, 0))
        for c, name in enumerate(spec["frames"]):
            img = FRAMES[name]()
            images[name] = img
            sheet.alpha_composite(img, (c * FW, r * FH))
            strip.alpha_composite(img, (c * FW, 0))
            rects[name] = {"x": c * FW, "y": r * FH, "w": FW, "h": FH}
        strip.save(os.path.join(ANIM_DIR, f"knight_{anim}.png"))
    sheet.save(os.path.join(CHAR_DIR, "knight_spritesheet.png"))
    with open(os.path.join(CHAR_DIR, "knight_animations.json"), "w") as fh:
        json.dump({
            "frame_size": [FW, FH],
            "source_pivot_offset": list(PIVOT),
            "animations": ANIMATIONS,
            "spritesheet": "knight_spritesheet.png",
            "frame_rects": rects,
        }, fh, indent=2)
    print(f"wrote {len(images)} frames")
    return images


if __name__ == "__main__":
    main()
