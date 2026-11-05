"""
make_lich_sprites.py - Paints the Lich King's pixel art (both phases, every pose) as PNG strips.

You do NOT have to run this to play: the PNGs are already in assets/bosses/lich_king/. It exists so the
art is reproducible and tweakable (edit a pose or a colour, re-run), exactly like the skeleton monsters.
You can also paint over the PNGs by hand in any pixel editor (see assets/bosses/lich_king/README.md).

    python src/bosses/dev/make_lich_sprites.py                  rebuild the PNGs + sprite.json
    python src/bosses/dev/make_lich_sprites.py --sheets folder  also save zoomed contact sheets to check poses

HOW IT IS BUILT
    A small rig (shoulders, elbows, hands, a floating body, a cape, wings) driven by "poses": dictionaries of
    numbers. Two-bone IK bends the arms. Poses are blended for the in-between frames. Materials (B = bone,
    V = royal cloak, G = gold...) get 3 shaded tones and an outline automatically (shared with the monsters'
    generator in src/monsters/dev/make_sprites.py).

GLOW MARKERS (exact colours the game turns into live, animated glow). See the README for the full list.
"""
import json
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SRC_DIR = os.path.dirname(os.path.dirname(HERE))
REPO_ROOT = os.path.dirname(SRC_DIR)
sys.path.insert(0, os.path.join(SRC_DIR, "monsters", "dev"))

import pygame                                                       # noqa: E402
import make_sprites as ms                                            # noqa: E402  (shared toolkit)
from make_sprites import Art, rnd, lerp, ik, blend, with_pose, sweep, finish   # noqa: E402

OUT_DIR = os.path.join(REPO_ROOT, "assets", "bosses", "lich_king")

# ---- extra materials and marker colours (added to the shared toolkit) ----
ms.MATERIALS.update({
    "V": ((132, 116, 224), (86, 72, 168), (52, 42, 112)),      # phase 1 royal cloak (front)
    "v": ((84, 70, 160), (50, 40, 108), (30, 24, 70)),         # phase 1 cloak lining
    "C": ((214, 72, 104), (156, 38, 74), (96, 22, 54)),        # phase 2 crimson cloak
    "c": ((120, 34, 70), (74, 20, 48), (44, 12, 30)),          # phase 2 lining
    "A": ((116, 104, 132), (70, 62, 88), (40, 34, 56)),        # blackened steel armour
})
ms.FLAT.update({
    "e": (255, 102, 255), "x": (255, 176, 255),                # eye_flare, eye_burst
    "m": (0, 136, 136), "h": (170, 255, 255),                  # core_rim, core_hi
    "o": (255, 255, 170),                                      # orb_shine
    "F": (255, 136, 0),                                        # flame: base of the soul-flame in his hand
    "f": (255, 85, 0),                                         # fire: base of a small flame (crown, horns)
    "n": (255, 51, 153),                                       # vein: glowing runes / cracks / gems
})

W, H = 96, 128
CX = 48                 # body centre column
THEME = {
    1: dict(front="V", lining="v", armor="I"),
    2: dict(front="C", lining="c", armor="A"),
}

# ----------------------------------------------------------------------
# Small drawing helpers
# ----------------------------------------------------------------------


def taper(a, p0, p1, t, r0, r1):
    """A tapered tube (sleeve) from p0 to p1."""
    steps = int(max(abs(p1[0] - p0[0]), abs(p1[1] - p0[1]))) + 1
    for i in range(steps + 1):
        f = i / float(steps)
        a.disc(rnd(lerp(p0[0], p1[0], f)), rnd(lerp(p0[1], p1[1], f)), lerp(r0, r1, f), t)


def seg(a, p0, p1, t, w=1):
    a.line(rnd(p0[0]), rnd(p0[1]), rnd(p1[0]), rnd(p1[1]), t, w)


def polar(p, ang, length):
    return (p[0] + math.cos(ang) * length, p[1] + math.sin(ang) * length)


def bony_hand(a, pos, ang, spread=1.0, curl=0):
    """A skeletal hand: palm + four long fingers fanning out along `ang` (radians)."""
    palm = polar(pos, ang, 1.5)
    a.disc(rnd(palm[0]), rnd(palm[1]), 1.4, "B")
    for off, length in ((-0.62, 4), (-0.2, 5), (0.2, 5), (0.62, 4)):
        fa = ang + off * spread
        base = polar(palm, fa, 1.5)
        tip = polar(palm, fa + curl * 0.25 * (1 if off > 0 else -1), length + 1.5)
        seg(a, base, tip, "B", 1)
    thumb = polar(palm, ang + (1.5 if True else -1.5) * spread * 0.9, 3)
    seg(a, palm, thumb, "B", 1)


def sleeve_arm(a, shoulder, target, bend, cloth, trim="G"):
    """A wide sleeved arm: returns (elbow, wrist, direction angle)."""
    joint, end = ik(shoulder, target, 11.0, 11.0, bend)
    taper(a, shoulder, joint, cloth, 4.2, 3.6)
    taper(a, joint, end, cloth, 3.6, 3.0)
    ang = math.atan2(end[1] - joint[1], end[0] - joint[0])
    cuff = polar(end, ang, 0.5)
    a.disc(rnd(cuff[0]), rnd(cuff[1]), 3.0, trim)
    a.disc(rnd(cuff[0]), rnd(cuff[1]), 1.6, "S")
    return joint, end, ang


def draw_chain(a, wrist, sway, links=4):
    """Short broken shackle chain dangling from a wrist."""
    x, y = wrist
    for i in range(links):
        x2 = x + math.sin(sway + i * 0.7) * (1 + i * 0.5)
        a.px(rnd(x2), rnd(y + 4 + i * 2), "I")
        a.px(rnd(x2), rnd(y + 5 + i * 2), "I")
    a.px(rnd(x), rnd(y + 4 + links * 2), "G")


# ----------------------------------------------------------------------
# The parts
# ----------------------------------------------------------------------

def fill_poly(a, pts, tok):
    """Fill a polygon (list of (x, y)) with one material, scanline by scanline."""
    ys = [p[1] for p in pts]
    for y in range(int(math.floor(min(ys))), int(math.ceil(max(ys))) + 1):
        xs = []
        for i in range(len(pts)):
            (x0, y0), (x1, y1) = pts[i], pts[(i + 1) % len(pts)]
            if (y0 <= y < y1) or (y1 <= y < y0):
                xs.append(x0 + (y - y0) / (y1 - y0) * (x1 - x0))
        xs.sort()
        for j in range(0, len(xs) - 1, 2):
            for x in range(int(math.ceil(xs[j])), int(math.floor(xs[j + 1])) + 1):
                a.px(x, y, tok)


def draw_wings(a, ux, by, wing, phase, flap, membrane="C"):
    """Phase 2: huge bat-wings behind him: dark steel struts, claws, scalloped crimson membranes.
    wing 0 = folded ... 1 = fully spread."""
    spread = [-68, -46, -24, -2]
    folded = [-104, -98, -92, -86]
    lengths = [34, 38, 35, 28]
    for side in (-1, 1):
        root = (ux + side * 10, 32 + by)
        tips = []
        for i in range(4):
            deg = lerp(folded[i], spread[i], wing) + flap * (i - 1.5) * 1.3
            ang = math.radians(deg if side > 0 else 180 - deg)
            length = lengths[i] * (0.8 + 0.2 * wing)
            tips.append(polar(root, ang, length))
        for i in range(3):
            t0, t1 = tips[i], tips[i + 1]
            mid = ((t0[0] + t1[0]) / 2.0, (t0[1] + t1[1]) / 2.0)
            notch = (lerp(mid[0], root[0], 0.28), lerp(mid[1], root[1], 0.28))
            fill_poly(a, [root, t0, notch, t1], membrane)
            seg(a, root, notch, "n", 1)                              # a glowing vein down each panel
        for i, tip in enumerate(tips):
            elbow = polar(root, math.atan2(tip[1] - root[1], tip[0] - root[0]), lengths[i] * 0.45)
            seg(a, root, tip, "A", 2)
            a.px(rnd(elbow[0]), rnd(elbow[1]), "G")
            claw = polar(tip, math.atan2(tip[1] - root[1], tip[0] - root[0]), 4)
            seg(a, tip, claw, "B", 1)


def draw_cape(a, ux, by, P, th):
    top = 36 + by
    hem = 86 + by
    flare = P["flare"]
    for y in range(top, hem + 1):
        t = (y - top) / float(hem - top)
        centre = ux + P["cape"] * 4.5 * t * t
        half = 14 + t * (19 + flare * 5)
        for x in range(rnd(centre - half), rnd(centre + half) + 1):
            zig = (3, 8, 2, 6, 10, 4, 7)[(x + rnd(P["cape"] * 2)) % 7]
            if y <= hem - zig:
                a.px(x, y, th["lining"])
    # a pale rim along the cape's edge so it reads against the dark background
    for y in range(top + 2, hem - 8, 3):
        t = (y - top) / float(hem - top)
        centre = ux + P["cape"] * 4.5 * t * t
        half = 14 + t * (19 + flare * 5)
        a.px(rnd(centre - half) + 1, y, "n")
        a.px(rnd(centre + half) - 1, y, "n")


def draw_robe(a, ux, by, P, th):
    belt = 56 + by
    hem = 85 + by
    flare = P["flare"]
    for y in range(belt, hem + 1):
        t = (y - belt) / float(hem - belt)
        centre = ux + P["cape"] * 2.5 * t * t
        half = 9 + t * (10 + flare * 2)
        for x in range(rnd(centre - half), rnd(centre + half) + 1):
            zig = (2, 6, 1, 5, 8, 3)[(x + rnd(P["cape"])) % 6]
            if y <= hem - zig:
                a.px(x, y, th["front"])
    # gold trim down the front, with glowing runes
    for y in range(belt + 2, hem - 2):
        t = (y - belt) / float(hem - belt)
        c = rnd(ux + P["cape"] * 2.5 * t * t)
        a.rect(c - 1, y, c, y, "G")
        if (y - belt) % 6 == 3:
            a.px(c - 3, y, "n")
            a.px(c + 2, y, "n")


def draw_staff(a, hx, hy, P):
    lift, tilt = P["staff"] * 0.5, P["tilt"]
    top = (hx + tilt * 6, hy - 27 - lift)
    bottom = (hx - tilt * 6, hy + 38 - lift)
    seg(a, top, bottom, "W", 2)
    for f in (0.2, 0.55, 0.8):                                   # gold bands
        px_ = lerp(top[0], bottom[0], f)
        py_ = lerp(top[1], bottom[1], f)
        a.rect(rnd(px_) - 1, rnd(py_), rnd(px_) + 2, rnd(py_) + 1, "G")
    a.px(rnd(bottom[0]), rnd(bottom[1]) + 2, "G")
    a.px(rnd(bottom[0]), rnd(bottom[1]) + 3, "G")
    tx, ty = rnd(top[0]), rnd(top[1])
    # a bone skull cradle and golden prongs holding the orb
    a.rect(tx - 2, ty + 1, tx + 3, ty + 4, "B")
    a.px(tx - 1, ty + 3, "S")
    a.px(tx + 2, ty + 3, "S")
    for k in range(7):
        a.px(tx - 4 - (k // 3), ty - k, "G")
        a.px(tx + 5 + (k // 3), ty - k, "G")
    a.px(tx - 3, ty + 1, "G")
    a.px(tx + 4, ty + 1, "G")
    a.disc(tx, ty - 5, 3.6, "O")
    a.px(tx - 1, ty - 7, "o")
    a.px(tx, ty - 7, "o")


def draw_collar(a, ux, by, th):
    """A tall, dark, spiked collar fanning out behind his skull."""
    base = (ux, 30 + by)
    for deg, length in ((-160, 17), (-132, 23), (-104, 25), (-76, 25), (-48, 23), (-20, 17)):
        tip = polar(base, math.radians(deg), length)
        seg(a, base, tip, th["lining"], 3)
        seg(a, polar(base, math.radians(deg), length * 0.55), tip, th["armor"], 1)
        a.px(rnd(tip[0]), rnd(tip[1]), "G")


def lich_skull(a, cx, top, jaw):
    """A big, 16-pixel-wide skull with slanted angry eyes and a jaw that can drop open."""
    rows = [(5, 10), (3, 12), (2, 13), (0, 15), (0, 15), (0, 15), (0, 15), (0, 15), (1, 14), (2, 13), (3, 12)]
    left = cx - 8
    for dy, (x0, x1) in enumerate(rows):
        a.rect(left + x0, top + dy, left + x1, top + dy, "B")
    for side in (0, 1):
        def X(v):
            return left + (v if side == 0 else 15 - v)
        for dy, (v0, v1) in ((3, (1, 4)), (4, (1, 5)), (5, (1, 6)), (6, (3, 6))):
            for v in range(v0, v1 + 1):
                a.px(X(v), top + dy, "S")
        # glow layers: E always on, e on wind-up, x at the peak (the slant makes them look furious)
        for v, dy in ((4, 5), (5, 5), (6, 5), (4, 6), (5, 6), (6, 6)):
            a.px(X(v), top + dy, "E")
        for v, dy in ((2, 4), (3, 4), (4, 4), (5, 4), (2, 5), (3, 5)):
            a.px(X(v), top + dy, "e")
        for v, dy in ((1, 3), (2, 3), (3, 3), (4, 3), (1, 4)):
            a.px(X(v), top + dy, "x")
        for v in range(2, 8):                                    # heavy brow ridge
            a.px(X(v), top + 2 - (1 if v < 4 else 0), "k")
        a.px(X(0), top + 6, "k")                                 # cracks
        a.px(X(1), top + 8, "k")
    for dx in (-1, 0):                                           # nose
        a.px(cx + dx, top + 7, "S")
        a.px(cx + dx, top + 8, "S")
    a.px(cx - 1, top + 9, "S")
    a.px(cx, top + 9, "S")
    # mouth: teeth, fangs and a jaw that drops open
    j = rnd(jaw)
    row = top + 11
    for g in range(j):
        a.rect(left + 3, row + g, left + 12, row + g, "S")
    t = row + j
    a.rect(left + 3, t, left + 12, t, "B")
    for x in range(left + 3, left + 13):
        if (x - left) % 2 == 1:
            a.px(x, t, "k")
    for fx in (left + 2, left + 13):                             # fangs
        a.rect(fx, t, fx, t + 2, "B")
    a.rect(left + 4, t + 1, left + 11, t + 2, "B")
    a.rect(left + 5, t + 3, left + 10, t + 3, "B")
    return t + 3


def draw_crown(a, cx, top, phase):
    base = top - 1
    a.rect(cx - 8, base, cx + 7, base + 2, "G")
    spikes = [(-7, 4), (-4, 7), (-1, 10), (2, 10), (5, 7), (8, 4)] if phase == 1 else \
             [(-8, 6), (-5, 10), (-3, 8), (0, 14), (3, 8), (5, 10), (8, 6)]
    for dx, height in spikes:
        for k in range(height):
            w = 2 if k < height - 3 else 1
            a.rect(cx + dx, base - k, cx + dx + w - 1, base - k, "G")
        if phase == 2:
            a.px(cx + dx, base - height - 1, "f")
    a.rect(cx - 1, base, cx, base + 1, "n")                      # forehead gem
    a.px(cx - 5, base + 1, "n")
    a.px(cx + 4, base + 1, "n")
    a.rect(cx - 8, base + 2, cx + 7, base + 2, "G")


def draw_torso(a, ux, by, P, th):
    # ribcage with an open centre: a gold cage around the glowing soul-core
    top, bot = 34 + by, 53 + by
    a.rect(ux - 10, top, ux + 9, top + 1, "B")                     # collar bones
    for y in range(top + 2, bot):
        t = (y - top) / float(bot - top)
        half = 10 - (1 if t > 0.7 else 0)
        a.rect(ux - half, y, ux - 4, y, "B")
        a.rect(ux + 3, y, ux + half - 1, y, "B")
        if (y - top) % 3 == 1:
            a.rect(ux - half + 1, y, ux - 5, y, "k")
            a.rect(ux + 4, y, ux + half - 2, y, "k")
    a.rect(ux - 3, top + 2, ux + 2, bot - 1, "S")
    cy = top + 9
    for dx in range(-3, 4):
        for dy in range(-3, 4):
            d = abs(dx) + abs(dy)
            if d == 5 and (dx + dy) % 2 == 0:
                a.px(ux + dx, cy + dy, "G")
            if d == 3:
                a.px(ux + dx, cy + dy, "m")
            elif 1 <= d <= 2:
                a.px(ux + dx, cy + dy, "M")
            elif d == 0:
                a.px(ux + dx, cy + dy, "h")
    a.rect(ux - 1, bot - 4, ux, bot, "B")                          # spine
    # gold chains across the chest
    for side in (-1, 1):
        for i in range(14):
            x = ux + side * (12 - i * 0.85)
            y = top + 2 + i * 0.7 + math.sin(i / 14.0 * math.pi) * 3
            a.px(rnd(x), rnd(y), "G")
    # belt with a skull buckle
    a.rect(ux - 13, bot + 1, ux + 12, bot + 3, "G")
    a.rect(ux - 3, bot, ux + 2, bot + 5, "B")
    a.px(ux - 2, bot + 2, "S")
    a.px(ux + 1, bot + 2, "S")
    a.px(ux - 1, bot + 4, "k")
    a.px(ux, bot + 4, "k")


def draw_pauldron(a, cx, cy, side, th, phase, raise_):
    arm = th["armor"]
    r = 9 if phase == 1 else 10
    # layered plate: outer shell, inner dome, gold rim studs, jewelled centre
    a.disc(cx, cy, r, arm)
    a.disc(cx, cy, r - 3, arm)
    for deg in range(0, 360, 24):
        a.px(rnd(cx + math.cos(math.radians(deg)) * (r - 1)),
             rnd(cy + math.sin(math.radians(deg)) * (r - 1)), "G")
    a.disc(cx, cy, 2.2, "G")
    a.px(cx, cy, "n")
    # a big curved horn growing out of the plate
    if phase == 1:
        pts = [(5, -6), (9, -11), (14, -14), (19, -13), (21, -9)]
    else:
        pts = [(4, -7), (8, -15), (11, -23), (14, -29)]
    path = [(cx + side * dx, cy + dy) for dx, dy in pts]
    for i in range(len(path) - 1):
        r0 = 2.8 - i * (2.1 / (len(path) - 1))
        taper(a, path[i], path[i + 1], "B", r0, max(0.7, r0 - 0.6))
    if phase == 2:
        a.px(rnd(path[-1][0]), rnd(path[-1][1]) - 1, "f")
        # second, shorter horn and magma cracks
        p2 = [(cx + side * 9, cy - 5), (cx + side * 15, cy - 9), (cx + side * 19, cy - 8)]
        for i in range(2):
            taper(a, p2[i], p2[i + 1], "B", 2.0 - i * 0.7, 1.0)
        for k in range(5):
            a.px(cx - 3 + k, cy + 2 + (k * 2) % 4, "n")
    # two short armour spikes along the rim
    for deg in (-50, -15):
        d = deg if side > 0 else -180 - deg
        tip = polar((cx, cy), math.radians(d), r + 5)
        seg(a, polar((cx, cy), math.radians(d), r - 2), tip, arm, 2)
        a.px(rnd(tip[0]), rnd(tip[1]), "G")


# ----------------------------------------------------------------------
# The whole Lich King
# ----------------------------------------------------------------------

REST = dict(bob=0.0, lean=0.0, head=(0.0, 0.0), jaw=0.0, shoulder=0.0,
            handL=(-10.0, 17.0), handR=(9.0, 15.0), bendL=1, bendR=-1,
            staff=0.0, tilt=0.0, cape=0.0, flare=0.0, wisp=0.0, wing=0.15, flap=0.0, chain=0.0, claw=1.0)


def lich(P, phase):
    a = Art()
    th = THEME[phase]
    by = rnd(P["bob"])
    ux = CX + rnd(P["lean"])
    sh_y = 39 + by + rnd(P["shoulder"])
    shL = (ux - 16, sh_y)
    shR = (ux + 16, sh_y)
    tgtL = (shL[0] + P["handL"][0], shL[1] + P["handL"][1])
    tgtR = (shR[0] + P["handR"][0], shR[1] + P["handR"][1])
    jL, eL = ik(shL, tgtL, 11.0, 11.0, P["bendL"])
    jR, eR = ik(shR, tgtR, 11.0, 11.0, P["bendR"])

    # --- behind the body ---
    if phase == 2:
        draw_wings(a, ux, by, P["wing"], phase, P["flap"], th["front"])
    draw_cape(a, ux, by, P, th)
    draw_staff(a, rnd(eR[0]) + 1, rnd(eR[1]), P)
    draw_collar(a, ux, by, th)
    draw_robe(a, ux, by, P, th)

    # --- body and head ---
    draw_torso(a, ux, by, P, th)
    hx = ux + rnd(P["head"][0])
    top = 12 + by + rnd(P["head"][1])
    a.rect(hx - 2, top + 13, hx + 1, top + 22, "B")                # neck vertebrae
    for y in (top + 16, top + 19):
        a.rect(hx - 2, y, hx + 1, y, "k")
    lich_skull(a, hx, top, P["jaw"])
    draw_crown(a, hx, top, phase)

    # --- arms, hands, chains ---
    joint, end, ang = sleeve_arm(a, shL, tgtL, P["bendL"], th["front"])
    bony_hand(a, (end[0], end[1]), ang, spread=P["claw"])
    flame_at = (rnd(end[0]), rnd(end[1]) - 5)                        # the soul-flame floats above his palm
    draw_chain(a, end, P["chain"], 4)
    joint, end, ang = sleeve_arm(a, shR, tgtR, P["bendR"], th["front"])
    gx, gy = rnd(end[0]) + 1, rnd(end[1])
    a.disc(gx, gy, 2.2, "B")                                       # fist wrapped round the staff
    for k in (-2, 0, 2):
        a.px(gx - 3, gy + k, "B")
        a.px(gx + 3, gy + k, "B")
    draw_chain(a, end, -P["chain"], 3)

    # pauldrons last so they cover the shoulder joints
    draw_pauldron(a, shL[0], shL[1] - 1, -1, th, phase, 0)
    draw_pauldron(a, shR[0], shR[1] - 1, 1, th, phase, 0)
    a.px(flame_at[0], flame_at[1], "F")                              # painted last: nothing may cover it
    return a


def poses():
    R = REST
    idle = []
    for k in range(4):
        s = math.sin(math.tau * k / 4.0)
        c = math.cos(math.tau * k / 4.0)
        idle.append(with_pose(R, bob=-2.0 - 2.0 * s, cape=0.9 * c, wisp=k * 1.6, wing=0.2 + 0.18 * (s + 1) / 2,
                              flap=s, handL=(-10 + 0.5 * c, 17 - 1.2 * s), handR=(9, 15 - 0.8 * s),
                              chain=k * 1.5, head=(0, -0.4 * s)))
    volley = [
        with_pose(R, bob=-3, handL=(-5, 11), handR=(6, 13), head=(0, 1), cape=1.0, wing=0.45, staff=0, wisp=1,
                  flap=1),
        with_pose(R, bob=-5, handL=(-10, 3), handR=(11, 6), head=(0, -1), jaw=1, cape=1.8, flare=1, wing=0.75,
                  staff=2, wisp=2, flap=-1, chain=2),
        with_pose(R, bob=-7, handL=(-17, -9), handR=(15, -5), head=(0, -2), jaw=3, cape=2.6, flare=2, wing=1.0,
                  staff=4, tilt=0.15, wisp=3, flap=1, chain=3),
    ]
    drain = [
        with_pose(R, bob=-1, handL=(-8, 25), handR=(8, 24), head=(0, 2), jaw=1, cape=-0.6, wing=0.3, wisp=1,
                  staff=-2),
        with_pose(R, bob=1, handL=(-10, 31), handR=(10, 28), head=(0, 3), jaw=2, cape=-1.2, flare=1.5,
                  wing=0.2, wisp=2, staff=-4, shoulder=1),
    ]
    summon = [
        with_pose(R, bob=-3, handL=(-13, 8), handR=(5, -9), head=(0, -1), cape=1.2, wing=0.5, staff=4, wisp=1),
        with_pose(R, bob=-6, handL=(-17, -2), handR=(4, -18), head=(0, -2), jaw=2, cape=2.0, flare=1.5, wing=0.8,
                  staff=7, wisp=2, flap=1),
        with_pose(R, bob=-8, handL=(-20, -8), handR=(3, -24), head=(0, -3), jaw=4, cape=2.8, flare=2.2, wing=1.0,
                  staff=10, tilt=-0.1, wisp=3, flap=-1),
    ]
    recover = [
        with_pose(R, bob=0, handL=(-9, 21), handR=(8, 19), head=(0, 1), cape=-1.0, wing=0.3, wisp=1),
        with_pose(R, bob=-1, handL=(-10, 19), handR=(9, 17), cape=-0.4, wing=0.25, wisp=2),
    ]
    hurt = [with_pose(R, bob=-3, lean=-4, head=(-3, -1), jaw=3, handL=(-17, 9), handR=(16, 6), cape=2.4,
                      flare=1, wing=0.9, shoulder=-2, chain=3, wisp=2, flap=2)]
    roar = [
        with_pose(R, bob=-6, handL=(-18, -4), handR=(16, -2), head=(0, -2), jaw=4, cape=2.6, flare=2, wing=1.0,
                  staff=4, wisp=1, flap=1, chain=2),
        with_pose(R, bob=-9, handL=(-21, -11), handR=(18, -10), head=(0, -4), jaw=6, cape=3.2, flare=2.6, wing=1.0,
                  staff=9, wisp=2, flap=-1, chain=3),
    ]
    # Bone Nova: coil in on himself, clench, then explode outwards
    nova = [
        with_pose(R, bob=1, handL=(-4, 15), handR=(5, 14), head=(0, 2), cape=-1.2, wing=0.1, shoulder=1, wisp=1),
        with_pose(R, bob=3, handL=(-1, 9), handR=(2, 9), head=(0, 3), jaw=1, cape=-2.2, wing=0.0, shoulder=2,
                  wisp=2, claw=0.6),
        with_pose(R, bob=-10, handL=(-23, -7), handR=(21, -7), head=(0, -4), jaw=6, cape=3.6, flare=3.2, wing=1.0,
                  staff=8, wisp=3, flap=1, chain=3, claw=1.8),
    ]
    # Grasping Hands: arms out and down, claws spread, commanding the dead from the floor
    grasp = [
        with_pose(R, bob=-1, handL=(-14, 13), handR=(13, 11), head=(0, 1), jaw=1, cape=-0.6, wing=0.4, wisp=1,
                  claw=1.7),
        with_pose(R, bob=1, handL=(-12, 28), handR=(12, 27), head=(0, 3), jaw=3, cape=-1.6, flare=1.6, wing=0.25,
                  shoulder=1, wisp=2, staff=-3, claw=1.9),
    ]
    return dict(idle=idle, volley=volley, drain=drain, summon=summon, recover=recover, hurt=hurt, roar=roar,
                nova=nova, grasp=grasp)


ORDER = ["idle", "volley", "drain", "summon", "recover", "hurt", "roar", "nova", "grasp"]
PAD = 32                  # blank rows on top: raised crowns, staffs and wings are never cut off
ANCHOR = (CX, 46 + PAD)
SCALE = 3


def build_strip(phase):
    p = poses()
    frames, layout, index = [], {}, 0
    for name in ORDER:
        layout[name] = list(range(index, index + len(p[name])))
        for pose in p[name]:
            art = lich(pose, phase)
            frames.append(finish(Art({(x, y + PAD): t for (x, y), t in art.items()}), W, H))
            index += 1
    strip = pygame.Surface((W * len(frames), H), pygame.SRCALPHA)
    for i, f in enumerate(frames):
        strip.blit(f, (i * W, 0))
    return strip, layout, frames


def write_all(sheet_dir=None):
    os.makedirs(OUT_DIR, exist_ok=True)
    layout = None
    for phase in (1, 2):
        strip, layout, frames = build_strip(phase)
        pygame.image.save(strip, os.path.join(OUT_DIR, f"frames_phase{phase}.png"))
        print("wrote", f"frames_phase{phase}.png", len(frames), "frames")
        if sheet_dir:
            os.makedirs(sheet_dir, exist_ok=True)
            save_sheet(frames, os.path.join(sheet_dir, f"lich_phase{phase}.png"))
    config = {
        "scale": SCALE, "frame_size": [W, H], "anchor": list(ANCHOR),
        "shadow": {"y": 49, "widths": [30, 42, 30]},
        "animations": layout,
        "bob": 1.5, "aura_radius": 34,
        "orbit": {"center": [CX, 50 + PAD], "radius": [30, 9], "count": {"1": 3, "2": 5}},
        "wisps": {"y": 86 + PAD, "x": [CX - 17, CX + 17]},
    }
    with open(os.path.join(OUT_DIR, "sprite.json"), "w", encoding="utf-8") as handle:
        json.dump(config, handle, indent=2)
    print("wrote sprite.json")


def save_sheet(frames, path, zoom=2, columns=6):
    rows = (len(frames) + columns - 1) // columns
    sheet = pygame.Surface((columns * W * zoom, rows * H * zoom))
    sheet.fill((43, 38, 60))
    for i, f in enumerate(frames):
        big = pygame.transform.scale(f, (W * zoom, H * zoom))
        sheet.blit(big, ((i % columns) * W * zoom, (i // columns) * H * zoom))
    pygame.image.save(sheet, path)
    print("wrote", path)


if __name__ == "__main__":
    pygame.init()
    out = sys.argv[sys.argv.index("--sheets") + 1] if "--sheets" in sys.argv else None
    write_all(out)
