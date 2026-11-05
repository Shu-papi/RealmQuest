"""
make_sprites.py - Paints the skeleton family's pixel art and saves it as PNG strips.

You do NOT have to run this to play the game: the PNGs it makes are already committed in
assets/monsters/. It exists so the art is reproducible and easy to tweak (change a pose or a
colour, re-run). You can also paint over the PNGs by hand in any pixel editor.

    python src/monsters/dev/make_sprites.py                       rebuild all four monsters
    python src/monsters/dev/make_sprites.py skeleton_archer       just one
    python src/monsters/dev/make_sprites.py --sheets out_folder   also save zoomed motion sheets
                                                                  (one row per animation) to check the motion

HOW THE ART IS MADE
    Each monster is a small SKELETON RIG: hips, knees, shoulders, elbows, hands. A pose is just
    a dictionary of numbers (how high the body bobs, where each foot and hand is, how far the
    sword is tilted...). Two-bone "IK" solves where the knees and elbows go, so legs really bend
    and arms really swing. A walk cycle is 8 poses computed from a sine wave; attacks are a few
    hand-picked key poses (anticipation -> strike -> follow-through).

    Poses are painted with "material" letters (B = bone, I = iron, C = cloth...). A shading pass
    gives every material 3 tones (light / main / dark) from the top-left, and a 1-pixel dark
    outline is added around the whole figure. That keeps all four monsters in one style.

    To change an animation, edit the poses in <monster>_poses() (e.g. warrior_poses) and re-run.

ANIMATIONS EACH MONSTER HAS (21 frames)
    idle 4   walk 8   windup 3   strike 3   recover 2   hurt 1

GLOW MARKERS (same idea as the Lich King)
    Eyes, runes and orbs are painted in exact marker colours. The game swaps them for glowing,
    pulsing colours at runtime (and a different colour per variant):
        (255, 0, 255)   eye       (0, 255, 255)   glow (runes, hand glyph)
        (255, 255, 0)   orb       (staff orb)
"""
import json
import math
import os
import sys

import pygame

HERE = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
OUT_DIR = os.path.join(REPO_ROOT, "assets", "monsters")

OUTLINE = (10, 8, 18)

# material letter -> (light, main, dark)
MATERIALS = {
    "B": ((250, 247, 235), (222, 216, 196), (168, 160, 158)),    # bone
    "I": ((170, 172, 205), (108, 110, 150), (62, 60, 92)),       # iron
    "R": ((214, 140, 84), (150, 86, 52), (104, 56, 40)),         # rust / leather
    "W": ((160, 118, 80), (128, 92, 60), (80, 58, 44)),          # wood
    "G": ((255, 226, 120), (224, 172, 44), (150, 100, 34)),      # gold
    "1": ((110, 98, 205), (70, 60, 150), (44, 38, 104)),         # indigo cloth (warrior)
    "2": ((92, 150, 130), (52, 100, 92), (30, 60, 62)),          # moss cloth (archer)
    "3": ((170, 90, 200), (120, 50, 150), (70, 28, 96)),         # violet cloth (acolyte)
    "4": ((160, 80, 70), (112, 50, 52), (70, 30, 38)),           # dried-blood leather (brute)
    "5": ((236, 120, 140), (196, 62, 90), (122, 32, 62)),        # red scarf / feathers
}
# letters that are one flat colour
FLAT = {
    "S": (14, 10, 24),         # socket / deep shadow
    "d": (33, 29, 46),         # dark detail
    "k": (112, 102, 116),      # bone crack / rib gap
    "E": (255, 0, 255),        # MARKER eye
    "M": (0, 255, 255),        # MARKER glow
    "O": (255, 255, 0),        # MARKER orb
    "s": (200, 196, 214),      # bowstring
}

SCALE = 2


# ----------------------------------------------------------------------
# Painting toolkit
# ----------------------------------------------------------------------

class Art(dict):
    """(x, y) -> letter. Later paint covers earlier paint."""

    def px(self, x, y, t):
        self[(int(x), int(y))] = t

    def rect(self, x0, y0, x1, y1, t):
        for y in range(int(y0), int(y1) + 1):
            for x in range(int(x0), int(x1) + 1):
                self[(x, y)] = t

    def line(self, x0, y0, x1, y1, t, w=1):
        x0, y0, x1, y1 = int(x0), int(y0), int(x1), int(y1)
        dx, dy = abs(x1 - x0), abs(y1 - y0)
        sx, sy = (1 if x0 < x1 else -1), (1 if y0 < y1 else -1)
        err = dx - dy
        while True:
            for ox in range(w):
                for oy in range(w):
                    self[(x0 + ox, y0 + oy)] = t
            if (x0, y0) == (x1, y1):
                break
            e2 = 2 * err
            if e2 > -dy:
                err -= dy
                x0 += sx
            if e2 < dx:
                err += dx
                y0 += sy

    def disc(self, cx, cy, r, t):
        for y in range(int(cy - r), int(cy + r) + 1):
            for x in range(int(cx - r), int(cx + r) + 1):
                if (x - cx) ** 2 + (y - cy) ** 2 <= r * r + r * 0.6:
                    self[(x, y)] = t

    def rows(self, x, y, rows, t):
        """Paint rows of '#' (filled) / '.' (skip) with the top-left at x, y."""
        for dy, row in enumerate(rows):
            for dx, ch in enumerate(row):
                if ch == "#":
                    self[(x + dx, y + dy)] = t
                elif ch not in ".":
                    self[(x + dx, y + dy)] = ch


def finish(art, width, height):
    """Shade materials, add the outline and return a pygame Surface (logical pixels)."""
    shaded = {}
    for (x, y), t in art.items():
        if t in MATERIALS:
            def differs(dx, dy):
                return art.get((x + dx, y + dy)) != t
            lit = differs(0, -1) or differs(-1, 0)       # light comes from the top-left
            shadow = differs(0, 1) or differs(1, 0)
            tone = 1 if (lit == shadow) else (0 if lit else 2)
            shaded[(x, y)] = MATERIALS[t][tone]
        else:
            shaded[(x, y)] = FLAT[t]
    edge = set()
    for (x, y) in shaded:
        for n in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
            if n not in shaded:
                edge.add(n)
    surface = pygame.Surface((width, height), pygame.SRCALPHA)
    for pos in edge:
        if 0 <= pos[0] < width and 0 <= pos[1] < height:
            surface.set_at(pos, OUTLINE + (255,))
    for (x, y), color in shaded.items():
        if 0 <= x < width and 0 <= y < height:
            surface.set_at((x, y), color + (255,))
    return surface


# ----------------------------------------------------------------------
# Rig helpers: joints, two-bone limbs (IK) and poses you can blend
# ----------------------------------------------------------------------

def rnd(v):
    return int(math.floor(v + 0.5))


def lerp(a, b, t):
    return a + (b - a) * t


def smooth(t):
    t = max(0.0, min(1.0, t))
    return t * t * (3 - 2 * t)


def ik(p0, p1, l1, l2, bend):
    """
    Two-bone limb from p0 (hip/shoulder) towards p1 (foot/hand).
    Returns (joint, end): the knee/elbow, and where the limb really ends (it can't stretch).
    `bend` = +1 / -1 chooses which way the knee/elbow points.
    """
    dx, dy = p1[0] - p0[0], p1[1] - p0[1]
    d = math.hypot(dx, dy) or 0.01
    d = max(abs(l1 - l2) + 0.05, min(l1 + l2 - 0.05, d))
    norm = math.hypot(dx, dy) or 1.0
    ux, uy = dx / norm, dy / norm
    along = (l1 * l1 - l2 * l2 + d * d) / (2 * d)
    out = math.sqrt(max(0.0, l1 * l1 - along * along))
    joint = (p0[0] + ux * along - uy * out * bend, p0[1] + uy * along + ux * out * bend)
    end = (p0[0] + ux * d, p0[1] + uy * d)
    return joint, end


def limb(art, p0, p1, t="B", w=2):
    art.line(rnd(p0[0]), rnd(p0[1]), rnd(p1[0]), rnd(p1[1]), t, w)


def bone_limb(art, p0, p1, l1, l2, bend, t="B", w=2, knob=True):
    """Draw a jointed limb; returns (joint, end)."""
    joint, end = ik(p0, p1, l1, l2, bend)
    limb(art, p0, joint, t, w)
    limb(art, joint, end, t, w)
    if knob:
        art.rect(rnd(joint[0]) - 1, rnd(joint[1]) - 1, rnd(joint[0]) + 1, rnd(joint[1]) + 1, t)
    return joint, end


def blend(a, b, t):
    """Blend two poses (dicts of numbers / (x, y) pairs) by t = 0..1."""
    out = {}
    for key, va in a.items():
        vb = b[key]
        if isinstance(va, tuple):
            out[key] = (lerp(va[0], vb[0], t), lerp(va[1], vb[1], t))
        else:
            out[key] = lerp(va, vb, t)
    return out


def with_pose(rest, **changes):
    pose = dict(rest)
    pose.update(changes)
    return pose


def sweep(rest, keys, count):
    """`count` evenly spaced poses along a list of key poses (each key = dict of changes)."""
    poses = [with_pose(rest, **k) for k in keys]
    out = []
    for i in range(count):
        t = i / max(1, count - 1) * (len(poses) - 1)
        lo = min(int(t), len(poses) - 2)
        out.append(blend(poses[lo], poses[lo + 1], smooth(t - lo)))
    return out


def skull(art, cx, top, w=8, jaw_open=0):
    """A front-facing skull: cranium, cheeks, sockets (with eye markers), nose, teeth, jaw."""
    jaw_open = rnd(jaw_open)
    left = cx - w // 2
    art.rows(left + 2, top, ["#" * (w - 4)], "B")
    art.rows(left + 1, top + 1, ["#" * (w - 2)], "B")
    art.rect(left, top + 2, left + w - 1, top + 5, "B")
    art.rows(left + 1, top + 6, ["#" * (w - 2)], "B")
    art.rect(left + 1, top + 3, left + 2, top + 4, "S")
    art.rect(left + w - 3, top + 3, left + w - 2, top + 4, "S")
    for x in (left + 1, left + 2, left + w - 3, left + w - 2):
        art.px(x, top + 4, "E")
    art.px(cx - 1, top + 5, "S")
    art.px(cx, top + 5, "S")
    row = top + 7
    for g in range(jaw_open):                                   # open mouth: a dark gap
        art.rect(left + 2, row + g, left + w - 3, row + g, "S")
    teeth = row + jaw_open
    art.rect(left + 2, teeth, left + w - 3, teeth, "B")
    for i in range(left + 2, left + w - 2):
        if (i - left) % 2 == 1:
            art.px(i, teeth, "k")
    if jaw_open:
        art.rect(left + 3, teeth + 1, left + w - 4, teeth + 1, "B")


def ribcage(art, x0, y0, x1, y1, gaps=(2, 4, 6)):
    art.rect(x0, y0, x1, y1, "B")
    for g in gaps:
        if y0 + g < y1:
            art.rect(x0 + 1, y0 + g, x1 - 1, y0 + g, "k")
    mid = (x0 + x1) // 2
    art.rect(mid, y0, mid + 1, y1, "B")


def walk_phase(k, count=8):
    return k / float(count)


def foot_path(phase, rest_x, side, lift=4.5, sway=1.0):
    """(x offset, height above the floor) of one foot in a walk cycle (phase 0..1)."""
    p = phase % 1.0
    h = lift * math.sin(math.pi * p / 0.5) if p < 0.5 else 0.0
    return (rest_x + side * sway * math.cos(math.tau * p) * 0.6, h)
# ----------------------------------------------------------------------
# 1. SKELETON WARRIOR  (44 x 44, feet on row 40)
#    Rusted spiked helm with a purple plume, shield with a gold boss, notched sword.
# ----------------------------------------------------------------------

W_CX, W_FY = 22, 41
W_REST = dict(bob=0.0, crouch=0.0, lean=0.0, head=(0.0, 0.0), jaw=0,
              footL=(-4.0, 0.0), footR=(4.0, 0.0),
              handL=(-3.0, 10.0), handR=(3.0, 10.0), sword=0.35,
              plume=0.0, tabard=0.0, bendL=1, bendR=-1)


def warrior(P):
    a = Art()
    cx = W_CX
    hy = 28 + P["crouch"] + P["bob"]                 # hip height
    uy = rnd(P["crouch"] + P["bob"])                 # how far the upper body moved up/down
    ux = cx + rnd(P["lean"])                         # and sideways

    # --- legs (two-bone, knees bend outward) ---
    for side, bend, foot in ((-1, 1, P["footL"]), (1, -1, P["footR"])):
        hip = (cx + side * 3, hy)
        target = (cx + foot[0], W_FY - foot[1])
        knee, end = bone_limb(a, hip, target, 6.8, 6.8, bend)
        a.px(rnd(knee[0]), rnd(knee[1]), "R")                      # rusted knee guard
        ex, ey = rnd(end[0]), rnd(end[1])
        if side < 0:
            a.rect(ex - 3, ey - 1, ex + 1, ey, "B")
        else:
            a.rect(ex - 1, ey - 1, ex + 3, ey, "B")
        mx, my = rnd((knee[0] + end[0]) / 2), rnd((knee[1] + end[1]) / 2)
        a.rect(mx - 1, my, mx, my + 1, "I")                         # shin guard

    # --- pelvis, belt and tabard ---
    h = rnd(hy)
    a.rect(cx - 4, h - 3, cx + 3, h, "B")
    a.rect(cx - 1, h - 2, cx, h - 1, "k")
    a.rect(cx - 5, h - 4, cx + 4, h - 4, "R")
    a.rect(cx - 1, h - 4, cx, h - 4, "G")
    for dy in range(0, 10):
        sway = rnd(P["tabard"] * dy / 9.0)
        a.rect(cx - 2 + sway, h - 3 + dy, cx + 1 + sway + (0 if dy < 8 else -1), h - 3 + dy, "1")
    a.px(cx - 2 + rnd(P["tabard"]), h + 7, "1")

    # --- spine, ribcage, neck ---
    limb(a, (cx, h - 4), (ux, 23 + uy), "B", 2)
    ribcage(a, ux - 5, 15 + uy, ux + 4, 23 + uy, gaps=(2, 4, 6))
    a.rect(ux - 1, 13 + uy, ux, 14 + uy, "B")

    # --- head: skull, kettle helm, plume ---
    hx = ux + rnd(P["head"][0])
    ht = 2 + uy + rnd(P["head"][1])
    skull(a, hx, ht + 3, 10, P["jaw"])
    a.rows(hx - 2, ht - 1, ["####"], "I")
    a.rows(hx - 3, ht, ["######"], "I")
    a.rows(hx - 4, ht + 1, ["########"], "I")
    a.rect(hx - 5, ht + 2, hx + 4, ht + 3, "I")
    a.rect(hx - 1, ht + 4, hx, ht + 6, "I")                         # nasal guard
    a.px(hx - 3, ht + 1, "R")
    a.px(hx + 2, ht, "R")
    a.px(hx + 3, ht + 3, "R")
    a.px(hx - 4, ht + 2, "R")
    pl = rnd(P["plume"])
    a.rect(hx - 1, ht - 3, hx, ht - 2, "1")
    a.px(hx + pl, ht - 4, "1")
    a.px(hx + 1 + pl, ht - 3, "1")
    a.px(hx + 2 + pl + (1 if pl else 0), ht - 2, "1")
    a.px(hx - 1 - (1 if pl else 0), ht - 4, "1")

    # --- left arm and shield ---
    shL = (ux - 7, 17 + uy)
    handL = (shL[0] + P["handL"][0], shL[1] + P["handL"][1])
    joint, end = bone_limb(a, shL, handL, 6, 6, P["bendL"])
    hxl, hyl = rnd(end[0]), rnd(end[1])
    a.rect(hxl - 1, hyl - 1, hxl, hyl, "B")
    a.disc(hxl - 1, hyl, 6, "I")
    a.disc(hxl - 1, hyl, 4, "1")
    a.px(hxl - 1, hyl, "G")
    a.px(hxl - 2, hyl - 1, "G")
    a.px(hxl, hyl + 1, "G")
    a.px(hxl - 5, hyl + 3, "R")
    a.px(hxl + 2, hyl - 4, "R")
    # spiked pauldron
    a.disc(shL[0], shL[1] - 1, 3, "I")
    a.px(shL[0] - 2, shL[1] - 5, "I")
    a.px(shL[0], shL[1] - 6, "I")
    a.px(shL[0] + 2, shL[1] - 5, "I")
    a.px(shL[0] - 1, shL[1] - 1, "R")

    # --- right arm and sword ---
    shR = (ux + 6, 17 + uy)
    handR = (shR[0] + P["handR"][0], shR[1] + P["handR"][1])
    a.disc(shR[0], shR[1], 2, "B")
    a.rect(shR[0] - 2, shR[1], shR[0] + 2, shR[1], "R")
    joint, end = bone_limb(a, shR, handR, 6, 6, P["bendR"])
    gx, gy = end
    a.rect(rnd(gx) - 1, rnd(gy) - 1, rnd(gx), rnd(gy), "B")
    th = P["sword"]
    dx, dy = math.sin(th), -math.cos(th)
    px_, py_ = -dy, dx
    limb(a, (gx - dx * 3, gy - dy * 3), (gx + dx * 2, gy + dy * 2), "W", 1)           # grip
    a.px(rnd(gx - dx * 4), rnd(gy - dy * 4), "G")                                       # pommel
    limb(a, (gx + dx * 2 - px_ * 3, gy + dy * 2 - py_ * 3),
         (gx + dx * 2 + px_ * 3, gy + dy * 2 + py_ * 3), "G", 1)                        # guard
    limb(a, (gx + dx * 4, gy + dy * 4), (gx + dx * 17, gy + dy * 17), "I", 2)          # blade
    a.px(rnd(gx + dx * 10), rnd(gy + dy * 10), "S")                                     # notch
    a.px(rnd(gx + dx * 7), rnd(gy + dy * 7), "R")
    a.px(rnd(gx + dx * 14), rnd(gy + dy * 14), "R")
    return a


def warrior_poses():
    R = W_REST
    idle = sweep(R, [dict(bob=0.0, plume=0, head=(0, 0), handR=(3, 11), sword=0.35, jaw=0),
                     dict(bob=-1.0, plume=1, head=(0, 0), handR=(3, 10.5), sword=0.4),
                     dict(bob=-1.0, plume=1, head=(0, -1), handR=(3, 10), sword=0.45),
                     dict(bob=0.0, plume=0, head=(0, 0), handR=(3, 10.5), sword=0.4),
                     dict(bob=0.0, plume=0, head=(0, 0), handR=(3, 11), sword=0.35)], 4)
    walk = []
    for k in range(8):
        ph = walk_phase(k)
        s = math.sin(math.tau * ph)
        footL = foot_path(ph, -4, -1)
        footR = foot_path(ph + 0.5, 4, 1)
        walk.append(with_pose(R, bob=-1.1 * abs(s), lean=0.9 * s, head=(0.5 * s, -0.8 * abs(s)),
                              footL=footL, footR=footR,
                              handL=(-3.5 + 0.5 * s, 11 - 3.5 * s), handR=(3.5 - 0.5 * s, 11 + 3.5 * s),
                              sword=0.35 + 0.22 * s, plume=-2.2 * math.sin(math.tau * ph - 0.9),
                              tabard=-1.6 * s))
    windup = [
        with_pose(R, crouch=1.0, lean=-1, head=(0, 0), jaw=1, handL=(-4, 8), handR=(5, 4), sword=0.8,
                  footL=(-5, 0), footR=(5, 0), tabard=1),
        with_pose(R, crouch=2.5, lean=-1, head=(-1, -1), jaw=2, handL=(-2, 3), handR=(5, -5),
                  sword=0.35, footL=(-6, 0), footR=(6, 0), plume=-1, tabard=1, bendR=1),
        with_pose(R, crouch=3.0, lean=-2, head=(-1, -1), jaw=2, handL=(-1, 1), handR=(3, -11),
                  sword=0.05, footL=(-6, 0), footR=(6, 0), plume=-2, tabard=2, bendR=1),
    ]
    strike = [
        with_pose(R, crouch=1.0, lean=1, head=(1, 1), jaw=2, handL=(-4, 5), handR=(3, -2),
                  sword=1.5, footL=(-5, 0), footR=(6, 1), plume=2, tabard=-2, bendR=1),
        with_pose(R, crouch=3.5, lean=3, head=(2, 2), jaw=2, handL=(-5, 6), handR=(4, 8),
                  sword=2.5, footL=(-6, 0), footR=(7, 0), plume=3, tabard=-3),
        with_pose(R, crouch=4.0, lean=3, head=(2, 2), jaw=1, handL=(-5, 7), handR=(3, 13),
                  sword=3.0, footL=(-6, 0), footR=(7, 0), plume=2, tabard=-3),
    ]
    recover = [
        with_pose(R, crouch=3.0, lean=2, head=(1, 1), handR=(3, 13), sword=2.9, footL=(-6, 0),
                  footR=(6, 0), tabard=-2),
        with_pose(R, crouch=1.0, lean=1, head=(0, 0), handR=(3, 12), sword=2.0, footL=(-5, 0),
                  footR=(5, 0), tabard=-1),
    ]
    hurt = [with_pose(R, bob=-1.0, crouch=1.0, lean=-3, head=(-2, -1), jaw=2, handL=(-6, 5),
                      handR=(7, 5), sword=1.2, footL=(-5, 0), footR=(5, 1), plume=-3, tabard=3)]
    return dict(idle=idle, walk=walk, windup=windup, strike=strike, recover=recover, hurt=hurt)
# ----------------------------------------------------------------------
# 2. SKELETON ARCHER  (44 x 56, feet on row 41 + 12 headroom)
#    Hooded in a moss-green cloak, red scarf, quiver on the back, long bow.
#    The bow arm points to the RIGHT of the picture; the game flips it to face you.
# ----------------------------------------------------------------------

A_CX, A_FY = 22, 41
A_REST = dict(bob=0.0, crouch=0.0, lean=0.0, head=(0.0, 0.0), jaw=0,
              footL=(-3.0, 0.0), footR=(3.0, 0.0), hem=0.0, scarf=0.0,
              handB=(5.0, 6.0), handD=(-2.0, 11.0), draw=-1.0, arrow=0)


def ring(a, cx, cy, r, t="M", steps=16):
    for i in range(steps):
        ang = math.tau * i / steps
        a.px(rnd(cx + math.cos(ang) * r), rnd(cy + math.sin(ang) * r), t)


def archer(P):
    a = Art()
    cx = A_CX
    hy = 29.5 + P["crouch"] + P["bob"]
    uy = rnd(P["crouch"] + P["bob"])
    ux = cx + rnd(P["lean"])

    # --- quiver on the back (behind everything) ---
    a.rect(ux - 10, 11 + uy, ux - 8, 19 + uy, "W")
    a.rect(ux - 10, 14 + uy, ux - 8, 14 + uy, "R")
    for i, x in enumerate((ux - 10, ux - 9, ux - 8)):
        a.px(x, 8 + uy - (i % 2), "5")
        a.px(x, 9 + uy, "B")

    # --- legs peeking out below the cloak ---
    for side, bend, foot in ((-1, 1, P["footL"]), (1, -1, P["footR"])):
        hip = (cx + side * 3, hy)
        target = (cx + foot[0], A_FY - foot[1])
        knee, end = bone_limb(a, hip, target, 6.0, 6.0, bend)
        ex, ey = rnd(end[0]), rnd(end[1])
        if side < 0:
            a.rect(ex - 3, ey - 1, ex + 1, ey, "B")
        else:
            a.rect(ex - 1, ey - 1, ex + 3, ey, "B")

    # --- cloak ---
    top, bottom = 14 + uy, 36 + uy
    for y in range(top, bottom + 1):
        t = (y - top) / float(bottom - top)
        centre = ux * (1 - t) + cx * t + P["hem"] * t * t * 3.0
        half = 5.0 + t * 6.5
        x0, x1 = rnd(centre - half), rnd(centre + half)
        if y > bottom - 2:                                        # ragged hem
            for x in range(x0, x1 + 1):
                if (x + y + rnd(P["hem"] * 2)) % 3:
                    a.px(x, y, "2")
        else:
            a.rect(x0, y, x1, y, "2")
    a.px(rnd(cx + P["hem"] * 3 - 9), bottom + 1, "2")
    a.px(rnd(cx + P["hem"] * 3 + 8), bottom + 1, "2")
    # open front showing the ribs
    ribcage(a, ux - 3, 16 + uy, ux + 2, 27 + uy, gaps=(1, 3, 5, 7, 9))
    a.rect(ux - 4, 16 + uy, ux - 4, 28 + uy, "d")
    a.rect(ux + 3, 16 + uy, ux + 3, 28 + uy, "d")
    a.rect(ux - 1, 29 + uy, ux, 31 + uy, "d")                     # belt hint
    a.px(ux - 1, 29 + uy, "G")

    # --- scarf with a trailing end ---
    a.rect(ux - 5, 14 + uy, ux + 5, 15 + uy, "5")
    wave = P["scarf"]
    for i in range(7):
        a.px(ux + 6 + i, 15 + uy + rnd(math.sin(i * 0.9 + wave) * 1.6 + i * 0.35), "5")
        a.px(ux + 6 + i, 16 + uy + rnd(math.sin(i * 0.9 + wave) * 1.6 + i * 0.35), "5")

    # --- hood and the skull inside it ---
    hx = ux + rnd(P["head"][0])
    ht = 2 + uy + rnd(P["head"][1])
    a.rows(hx - 3, ht, ["######"], "2")
    a.rows(hx - 5, ht + 1, ["##########"], "2")
    a.rows(hx - 6, ht + 2, ["############"], "2")
    for y in range(ht + 3, ht + 13):
        a.rect(hx - 7, y, hx + 6, y, "2")
    for i in range(4):                                            # the hood's tail droops behind
        a.px(hx - 8 - i // 2, ht + 8 + i, "2")
        a.px(hx - 7 - i // 2, ht + 9 + i, "2")
    a.rect(hx - 5, ht + 3, hx + 4, ht + 13, "S")
    skull(a, hx, ht + 3, 10, P["jaw"])
    a.rect(hx - 5, ht + 3, hx + 4, ht + 4, "S")                   # hood shadow over the brow
    a.rect(hx - 6, ht + 6, hx - 6, ht + 9, "S")
    a.rect(hx + 5, ht + 6, hx + 5, ht + 9, "S")

    # --- arms: right = bow arm, left = string hand ---
    shR = (ux + 6, 17 + uy)
    shL = (ux - 6, 17 + uy)
    handB = (shR[0] + P["handB"][0], shR[1] + P["handB"][1])
    draw = P["draw"]
    bow_h = 11
    arrow_on = P["arrow"]
    if draw >= 0:
        nock = (handB[0] - 2.5 * draw - 11 * draw, handB[1])
        handD = nock
    else:
        nock = (handB[0], handB[1])
        handD = (shL[0] + P["handD"][0], shL[1] + P["handD"][1])
    # the bow
    hxb, hyb = rnd(handB[0]), rnd(handB[1])
    dr = max(0.0, draw)
    for i in range(-bow_h, bow_h + 1):
        tt = i / float(bow_h)
        a.px(hxb + rnd(3.5 * (1 - tt * tt) - 2.5 * dr * tt * tt) , hyb + i, "W")
        a.px(hxb + rnd(3.5 * (1 - tt * tt) - 2.5 * dr * tt * tt) + 1, hyb + i, "W")
    tip_x = hxb + rnd(-2.5 * dr)
    a.rect(hxb + 2, hyb - 1, hxb + 5, hyb + 1, "R")               # grip wrap
    nx = rnd(nock[0])
    a.line(tip_x, hyb - bow_h, nx, hyb, "s")
    a.line(nx, hyb, tip_x, hyb + bow_h, "s")
    if arrow_on:
        a.line(nx, hyb, hxb + 9, hyb, "W")
        a.rect(hxb + 9, hyb - 1, hxb + 12, hyb, "I")
        a.px(nx, hyb - 1, "5")
        a.px(nx + 1, hyb - 1, "5")
        a.px(nx, hyb + 1, "5")
    # arms drawn over the bow/cloak
    joint, end = bone_limb(a, shR, handB, 5.5, 5.5, -1 if handB[1] > shR[1] + 3 else 1, "2", 2)
    a.rect(rnd(end[0]) - 1, rnd(end[1]) - 1, rnd(end[0]) + 1, rnd(end[1]) + 1, "B")
    elbow_dir = 1 if draw >= 0 else 1
    joint, end = bone_limb(a, shL, handD, 5.5, 5.5, elbow_dir, "2", 2)
    a.rect(rnd(end[0]) - 1, rnd(end[1]) - 1, rnd(end[0]), rnd(end[1]), "B")
    return a


def archer_poses():
    R = A_REST
    idle = sweep(R, [dict(), dict(bob=-1.0, scarf=0.8, hem=0.4, head=(0, 0)),
                     dict(bob=-1.0, scarf=1.6, hem=0.8, head=(0, -1), handD=(-2, 10.5)),
                     dict(bob=0.0, scarf=2.4, hem=0.4), dict(scarf=3.2)], 4)
    walk = []
    for k in range(8):
        ph = walk_phase(k)
        s = math.sin(math.tau * ph)
        walk.append(with_pose(R, bob=-1.0 * abs(s), lean=0.8 * s, head=(0.5 * s, -0.7 * abs(s)),
                              footL=foot_path(ph, -3, -1, lift=3.0), footR=foot_path(ph + 0.5, 3, 1, lift=3.0),
                              hem=-0.9 * s, scarf=ph * math.tau * 1.0 + 1.0,
                              handB=(5 + 0.3 * s, 6 + 1.2 * s), handD=(-2.5 + 0.5 * s, 11 - 3.5 * s)))
    windup = [
        with_pose(R, crouch=0.5, handB=(7, 3), draw=0.0, arrow=1, head=(0, 0), scarf=1.0),
        with_pose(R, crouch=1.0, lean=-1, handB=(11, -1), draw=0.55, arrow=1, head=(0, 0), scarf=1.6, hem=-0.5),
        with_pose(R, crouch=1.5, lean=-2, handB=(12, -2), draw=1.0, arrow=1, head=(-1, 0), scarf=2.2, hem=-1.0),
    ]
    strike = [
        with_pose(R, crouch=0.5, lean=1, handB=(12, -3), draw=0.0, arrow=0, handD=(-9, -1), head=(1, 0), scarf=3.0, hem=0.8),
        with_pose(R, crouch=0.0, lean=2, handB=(11, -1), draw=-1.0, arrow=0, handD=(-8, 4), head=(1, 0), scarf=3.8, hem=1.2),
        with_pose(R, crouch=0.5, lean=1, handB=(9, 2), draw=-1.0, arrow=0, handD=(-6, 8), scarf=4.2, hem=0.8),
    ]
    recover = [
        with_pose(R, crouch=0.5, handB=(8, 4), handD=(-4, 9), scarf=3.0),
        with_pose(R, handB=(6, 5), handD=(-3, 10), scarf=2.0),
    ]
    hurt = [with_pose(R, bob=-1.0, crouch=1.0, lean=-3, head=(-2, -1), jaw=2, handB=(8, 0), handD=(-7, 5),
                      scarf=4.0, hem=2.0, footL=(-4, 0), footR=(4, 1))]
    return dict(idle=idle, walk=walk, windup=windup, strike=strike, recover=recover, hurt=hurt)
# ----------------------------------------------------------------------
# 3. BONE BRUTE  (64 x 74, feet on row 50 + 20 headroom)
#    Ram-horned skull with tusks, spiked iron pauldron, chain bandolier, huge two-handed maul.
# ----------------------------------------------------------------------

B_CX, B_FY = 32, 50
B_REST = dict(bob=0.0, crouch=0.0, lean=0.0, head=(0.0, 0.0), jaw=0,
              footL=(-6.0, 0.0), footR=(6.0, 0.0),
              handL=(-3.0, 14.0), handR=(4.0, 12.0), maul=0.4, twohand=0.0, sway=0.0)


def brute(P):
    a = Art()
    cx = B_CX
    hy = 34 + P["crouch"] + P["bob"]
    uy = rnd(P["crouch"] + P["bob"])
    ux = cx + rnd(P["lean"])
    h = rnd(hy)

    # --- legs: thick bones, iron greaves, iron-toed feet ---
    for side, bend, foot in ((-1, 1, P["footL"]), (1, -1, P["footR"])):
        hip = (cx + side * 5, hy)
        target = (cx + foot[0], B_FY - foot[1])
        knee, end = bone_limb(a, hip, target, 8.2, 8.2, bend, "B", 3)
        mx, my = rnd((knee[0] + end[0]) / 2), rnd((knee[1] + end[1]) / 2)
        a.rect(mx - 1, my - 1, mx + 2, my + 2, "I")
        a.px(rnd(knee[0]), rnd(knee[1]), "R")
        ex, ey = rnd(end[0]), rnd(end[1])
        if side < 0:
            a.rect(ex - 4, ey - 1, ex + 2, ey, "B")
            a.rect(ex - 5, ey - 2, ex - 3, ey, "I")
        else:
            a.rect(ex - 2, ey - 1, ex + 4, ey, "B")
            a.rect(ex + 3, ey - 2, ex + 5, ey, "I")

    # --- loincloth, belt, skull buckle ---
    a.rect(cx - 8, h - 5, cx + 7, h - 2, "I")
    for x in range(cx - 8, cx + 8, 4):
        a.px(x + 1, h - 5, "G")
    for i, x in enumerate(range(cx - 7, cx + 7)):
        a.rect(x + rnd(P["sway"] * 0.5), h - 1, x + rnd(P["sway"] * 0.5), h + 3 + (i * 7) % 4, "4")
    a.rect(cx - 2, h - 6, cx + 1, h - 3, "B")
    a.px(cx - 1, h - 4, "S")
    a.px(cx, h - 4, "S")
    # pelvis
    a.rect(cx - 5, h - 2, cx + 4, h, "B")

    # --- barrel chest ---
    limb(a, (cx, h - 5), (ux, 28 + uy), "B", 3)
    ribcage(a, ux - 10, 17 + uy, ux + 9, 29 + uy, gaps=(2, 4, 6, 8, 10))
    a.rect(ux - 10, 17 + uy, ux - 9, 29 + uy, "B")
    a.rect(ux + 8, 17 + uy, ux + 9, 29 + uy, "B")
    a.rect(ux - 2, 13 + uy, ux + 1, 16 + uy, "B")                  # thick neck
    # bandolier + chain
    limb(a, (ux - 9, 18 + uy), (ux + 8, 30 + uy), "4", 2)
    for i in range(0, 14, 3):
        a.px(ux - 7 + i, 20 + uy + rnd(i * 0.68), "G")
    limb(a, (ux + 8, 18 + uy), (ux - 7, 28 + uy), "I", 1)
    a.px(ux, 23 + uy, "I")

    # --- head: skull, tusks, ram horns ---
    hx = ux + rnd(P["head"][0])
    ht = 4 + uy + rnd(P["head"][1])
    skull(a, hx, ht, 12, P["jaw"])
    a.rect(hx - 5, ht + 2, hx + 4, ht + 2, "k")                   # heavy brow
    a.rect(hx - 4, ht + 3, hx - 2, ht + 5, "S")
    a.rect(hx + 1, ht + 3, hx + 3, ht + 5, "S")
    a.rect(hx - 3, ht + 4, hx - 2, ht + 5, "E")
    a.rect(hx + 2, ht + 4, hx + 3, ht + 5, "E")
    j = rnd(P["jaw"])
    a.px(hx - 5, ht + 7 + j, "B")
    a.px(hx + 4, ht + 7 + j, "B")
    a.px(hx - 5, ht + 6, "B")                                      # tusks pointing up
    a.px(hx + 4, ht + 6, "B")
    for side in (-1, 1):
        pts = ((6, 1), (8, 0), (10, 0), (11, 2), (11, 4), (10, 6))
        for (dx, dy) in pts:
            x = hx + side * dx - (1 if side < 0 else 0)
            a.rect(x, ht + dy, x + 1, ht + dy + 1, "B")

    # --- shoulders: iron spiked pauldron (left), bone ball with rusty ring (right) ---
    shL = (ux - 12, 20 + uy)
    shR = (ux + 11, 20 + uy)

    # --- the maul and arms ---
    th = P["maul"]
    dx, dy = math.sin(th), -math.cos(th)
    handR = (shR[0] + P["handR"][0], shR[1] + P["handR"][1])
    grip = handR
    two = P["twohand"]
    handL_free = (shL[0] + P["handL"][0], shL[1] + P["handL"][1])
    handL_grip = (grip[0] - dx * 6, grip[1] - dy * 6)
    handL = (lerp(handL_free[0], handL_grip[0], two), lerp(handL_free[1], handL_grip[1], two))

    # handle first (behind the hands)
    limb(a, (grip[0] - dx * 7, grip[1] - dy * 7), (grip[0] + dx * 19, grip[1] + dy * 19), "W", 2)
    hx2, hy2 = grip[0] + dx * 22, grip[1] + dy * 22
    X, Y = rnd(hx2), rnd(hy2)
    a.rect(X - 5, Y - 4, X + 4, Y + 3, "I")
    a.rect(X - 5, Y - 1, X + 4, Y, "R")
    for (sx, sy) in ((X - 6, Y - 3), (X - 6, Y + 2), (X + 5, Y - 3), (X + 5, Y + 2),
                     (X - 2, Y - 5), (X + 1, Y - 5), (X - 2, Y + 4), (X + 1, Y + 4)):
        a.px(sx, sy, "I")
    a.px(X - 3, Y - 2, "S")
    a.px(X + 2, Y + 2, "S")

    jL, endL = bone_limb(a, shL, handL, 8, 8, 1 if two < 0.5 else -1, "B", 3)
    a.rect(rnd(endL[0]) - 2, rnd(endL[1]) - 2, rnd(endL[0]) + 1, rnd(endL[1]) + 1, "I")   # iron knuckles
    a.disc(shL[0], shL[1], 5, "I")
    a.disc(shL[0], shL[1], 3, "R")
    a.px(shL[0], shL[1], "I")
    for (sx, sy) in ((shL[0] - 4, shL[1] - 5), (shL[0], shL[1] - 7), (shL[0] + 4, shL[1] - 5)):
        limb(a, (sx, sy + 1), (sx, sy + 3), "I", 1)
        a.px(sx, sy, "I")
    a.disc(shR[0], shR[1], 4, "B")
    a.rect(shR[0] - 4, shR[1], shR[0] + 4, shR[1] + 1, "R")
    jR, endR = bone_limb(a, shR, handR, 8, 8, -1, "B", 3)
    a.rect(rnd(endR[0]) - 2, rnd(endR[1]) - 2, rnd(endR[0]) + 1, rnd(endR[1]) + 1, "I")
    return a


def brute_poses():
    R = B_REST
    idle = sweep(R, [dict(), dict(bob=-1.0, jaw=0, handL=(-3, 13.5), handR=(4, 11.5), sway=1),
                     dict(bob=-1.0, jaw=1, head=(0, -1), handL=(-3, 13), handR=(4, 11), sway=1, maul=0.45),
                     dict(bob=0.0, jaw=0, sway=0), dict()], 4)
    walk = []
    for k in range(8):
        ph = walk_phase(k)
        s = math.sin(math.tau * ph)
        walk.append(with_pose(R, bob=-1.5 * abs(s) + 0.5, lean=1.6 * s, head=(0.8 * s, -1.0 * abs(s)),
                              footL=foot_path(ph, -6, -1, lift=4.0), footR=foot_path(ph + 0.5, 6, 1, lift=4.0),
                              handL=(-3.5 + 0.6 * s, 14 - 3.5 * s), handR=(4 - 0.6 * s, 12 + 3 * s),
                              maul=0.4 + 0.14 * s, sway=-2.0 * s))
    windup = [
        with_pose(R, crouch=1.5, lean=-1, jaw=1, handR=(6, 4), twohand=0.6, maul=0.55,
                  footL=(-7, 0), footR=(7, 0)),
        with_pose(R, crouch=3.0, lean=-2, head=(-1, -1), jaw=2, handR=(6, -6), twohand=1.0, maul=0.25,
                  footL=(-8, 0), footR=(8, 0), sway=1),
        with_pose(R, crouch=4.0, lean=-3, head=(-1, -2), jaw=3, handR=(4, -16), twohand=1.0, maul=0.0,
                  footL=(-8, 0), footR=(8, 0), sway=2),
    ]
    strike = [
        with_pose(R, crouch=2.0, lean=1, head=(1, 1), jaw=3, handR=(3, -4), twohand=1.0, maul=0.95,
                  footL=(-8, 0), footR=(8, 0), sway=-2),
        with_pose(R, crouch=7.0, lean=3, head=(2, 3), jaw=3, handR=(5, 3), twohand=1.0, maul=2.85,
                  footL=(-8, 0), footR=(9, 0), sway=-3),
        with_pose(R, crouch=7.5, lean=3, head=(2, 3), jaw=2, handR=(5, 3), twohand=1.0, maul=2.95,
                  footL=(-9, 0), footR=(9, 0), sway=-3),
    ]
    recover = [
        with_pose(R, crouch=7.0, lean=3, head=(2, 3), jaw=1, handR=(5, 3), twohand=1.0, maul=2.95,
                  footL=(-9, 0), footR=(9, 0), sway=-2),
        with_pose(R, crouch=4.0, lean=2, head=(1, 1), handR=(5, 6), twohand=1.0, maul=2.2,
                  footL=(-8, 0), footR=(8, 0), sway=-1),
    ]
    hurt = [with_pose(R, bob=-1.0, crouch=1.5, lean=-3, head=(-2, -1), jaw=3, handL=(-6, 8),
                      handR=(7, 8), maul=1.0, footL=(-7, 0), footR=(7, 1), sway=3)]
    return dict(idle=idle, walk=walk, windup=windup, strike=strike, recover=recover, hurt=hurt)
# ----------------------------------------------------------------------
# 4. SKELETON ACOLYTE  (44 x 58, floor point row 44 + 10 headroom)
#    Hovering violet-robed priest: gold-trimmed hood, glowing runes, orb staff, glyph in his open hand.
# ----------------------------------------------------------------------

C_CX, C_FY = 22, 44
C_REST = dict(bob=0.0, lean=0.0, head=(0.0, 0.0), jaw=0, hem=0.0, wisp=0.0,
              handL=(-5.0, 9.0), handR=(4.0, 8.0), glow=0.3, staff=0.0, orb=2)


def acolyte(P):
    a = Art()
    cx = C_CX
    uy = rnd(P["bob"])
    ux = cx + rnd(P["lean"])

    # --- the robe: widens into a ragged hem that dissolves into wisps ---
    top, bottom = 15 + uy, 37 + uy
    for y in range(top, bottom + 1):
        t = (y - top) / float(bottom - top)
        centre = ux * (1 - t) + cx * t + P["hem"] * t * t * 4.0
        half = 5.0 + t * 6.5
        a.rect(rnd(centre - half), y, rnd(centre + half), y, "3")
    wisp = P["wisp"]
    for i, x in enumerate(range(cx - 11, cx + 12)):
        sway = rnd(P["hem"] * 4.0)
        if (i + rnd(wisp)) % 3 != 0:
            a.px(x + sway, bottom + 1, "3")
        if (i + rnd(wisp)) % 3 == 1:
            a.px(x + sway, bottom + 2, "3")
        if (i * 2 + rnd(wisp * 2)) % 5 == 0:
            a.px(x + sway, bottom + 3, "d")
    # gold trim and chest rune
    for y in range(top + 1, bottom + 1):
        t = (y - top) / float(bottom - top)
        centre = ux * (1 - t) + cx * t + P["hem"] * t * t * 4.0
        a.rect(rnd(centre) - 1, y, rnd(centre), y, "G")
    a.rect(ux - 5, 14 + uy, ux + 4, 14 + uy, "G")
    for (dx, dy) in ((0, 0), (-1, 0), (0, 1), (-1, 1), (-2, 1), (1, 1), (0, 2), (-1, 2)):
        a.px(ux + dx, 19 + uy + dy, "M")

    # --- hood, horned skull mask ---
    hx = ux + rnd(P["head"][0])
    ht = 1 + uy + rnd(P["head"][1])
    a.rows(hx - 2, ht, ["####"], "3")
    a.rows(hx - 4, ht + 1, ["########"], "3")
    a.rows(hx - 5, ht + 2, ["##########"], "3")
    for y in range(ht + 3, ht + 13):
        a.rect(hx - 6, y, hx + 5, y, "3")
    a.rect(hx - 4, ht + 4, hx + 3, ht + 12, "S")
    skull(a, hx, ht + 4, 8, P["jaw"])
    a.rect(hx - 4, ht + 4, hx + 3, ht + 5, "S")
    for (dx, dy) in ((-6, 3), (-7, 2), (-7, 1), (5, 3), (6, 2), (6, 1)):                # little horns
        a.px(hx + dx, ht + dy + 1, "B")
    a.rect(hx - 3, ht + 13, hx + 2, ht + 13, "G")                                         # choker

    # --- arms: left casts, right holds the staff ---
    shL = (ux - 6, 17 + uy)
    shR = (ux + 6, 17 + uy)
    handR = (shR[0] + P["handR"][0], shR[1] + P["handR"][1])
    handL = (shL[0] + P["handL"][0], shL[1] + P["handL"][1])

    # staff (behind the sleeve)
    sx = rnd(handR[0]) + 1
    lift = P["staff"]
    ytop = rnd(handR[1] - 24 + lift)
    limb(a, (sx, ytop + 5), (sx, handR[1] + 14), "W", 1)
    a.rect(sx - 1, ytop + 3, sx + 1, ytop + 3, "G")
    a.px(sx - 2, ytop + 2, "B")
    a.px(sx + 2, ytop + 2, "B")
    a.px(sx - 1, ytop + 2, "B")
    a.px(sx + 1, ytop + 2, "B")
    r = P["orb"]
    a.disc(sx, ytop - 1, r, "O")

    joint, end = bone_limb(a, shR, handR, 6, 6, -1, "3", 3, knob=False)
    a.rect(rnd(end[0]) - 1, rnd(end[1]) - 1, rnd(end[0]) + 1, rnd(end[1]) + 1, "B")
    a.rect(rnd(end[0]) - 2, rnd(end[1]) - 2, rnd(end[0]) + 2, rnd(end[1]) - 2, "G")
    joint, end = bone_limb(a, shL, handL, 6, 6, 1, "3", 3, knob=False)
    ex, ey = rnd(end[0]), rnd(end[1])
    a.rect(ex - 1, ey - 1, ex + 1, ey + 1, "B")
    a.rect(ex - 2, ey, ex + 2, ey, "G")
    # the glyph floating over his open hand
    g = P["glow"]
    if g > 0.05:
        gr = 1.5 + 3.5 * g
        ring(a, ex, ey - 5 - g * 2, gr, "M", steps=max(8, int(gr * 5)))
        a.px(ex, rnd(ey - 5 - g * 2), "M")
        if g > 0.5:
            a.disc(ex, rnd(ey - 5 - g * 2), 1, "M")
    return a


def acolyte_poses():
    R = C_REST
    idle = sweep(R, [dict(bob=0.0, hem=0.2, wisp=0, glow=0.25, orb=2),
                     dict(bob=-2.0, hem=0.5, wisp=1, glow=0.35, handL=(-5, 8), orb=2),
                     dict(bob=-3.0, hem=0.2, wisp=2, glow=0.45, handL=(-5, 7.5), handR=(4, 7.5), orb=3),
                     dict(bob=-1.5, hem=-0.2, wisp=3, glow=0.35, orb=2),
                     dict(bob=0.0, hem=0.2, wisp=4, glow=0.25, orb=2)], 4)
    walk = []
    for k in range(8):
        ph = walk_phase(k)
        s = math.sin(math.tau * ph)
        c = math.cos(math.tau * ph)
        walk.append(with_pose(R, bob=-2.0 + 1.5 * s, lean=1.6 * c, hem=-1.0 * c, wisp=k,
                              head=(0.6 * c, -0.5 * s), handL=(-5 - 0.8 * c, 9 + 1.5 * s),
                              handR=(4 + 0.5 * c, 8 + 1.0 * s), glow=0.3, staff=0.5 * s,
                              orb=2 + (1 if k % 4 < 2 else 0)))
    windup = [
        with_pose(R, bob=-3.0, head=(0, -1), handL=(-5, 3), handR=(4, 4), glow=0.6, staff=1, wisp=1, hem=0.4, orb=3),
        with_pose(R, bob=-5.0, head=(0, -1), handL=(-5, -4), handR=(5, -2), glow=0.85, staff=3, wisp=2, hem=0.6, orb=3),
        with_pose(R, bob=-6.0, head=(0, -2), handL=(-4, -9), handR=(5, -6), glow=1.0, staff=5, wisp=3, hem=0.8, orb=4),
    ]
    strike = [
        with_pose(R, bob=-4.0, lean=-1, head=(-1, 0), jaw=1, handL=(-12, 2), handR=(6, -3), glow=1.0, staff=4,
                  wisp=4, hem=1.4, orb=4),
        with_pose(R, bob=-3.0, lean=-2, head=(-1, 1), jaw=2, handL=(-14, 5), handR=(5, 2), glow=1.0, staff=2,
                  wisp=5, hem=2.0, orb=3),
        with_pose(R, bob=-2.0, lean=-1, head=(0, 0), jaw=1, handL=(-10, 7), handR=(4, 6), glow=0.6, staff=1,
                  wisp=6, hem=1.4, orb=3),
    ]
    recover = [
        with_pose(R, bob=-2.0, handL=(-8, 8), handR=(4, 7), glow=0.4, wisp=7, hem=0.8),
        with_pose(R, bob=-1.0, handL=(-6, 9), glow=0.3, wisp=8, hem=0.3),
    ]
    hurt = [with_pose(R, bob=-2.0, lean=3, head=(-2, -1), jaw=2, handL=(-9, 3), handR=(8, 4), glow=0.0,
                      staff=2, hem=-2.0, wisp=2, orb=1)]
    return dict(idle=idle, walk=walk, windup=windup, strike=strike, recover=recover, hurt=hurt)
# ----------------------------------------------------------------------
# Writing the files
# ----------------------------------------------------------------------

ANIMATION_ORDER = ["idle", "walk", "windup", "strike", "recover", "hurt"]

MONSTER_ART = {
    "skeleton_warrior": dict(draw=warrior, poses=warrior_poses, size=(44, 56), anchor=(22, 53), pad=12),
    "skeleton_archer": dict(draw=archer, poses=archer_poses, size=(44, 56), anchor=(22, 53), pad=12),
    "skeleton_brute": dict(draw=brute, poses=brute_poses, size=(76, 76), anchor=(32, 70), pad=20),
    "skeleton_acolyte": dict(draw=acolyte, poses=acolyte_poses, size=(44, 66), anchor=(22, 60), pad=16),
}


def frames_for(spec):
    """[(animation, [Surface, ...]), ...] for one monster."""
    w, h = spec["size"]
    poses = spec["poses"]()
    pad = spec.get("pad", 0)          # blank rows added on top so raised weapons are not cut off

    def draw(pose):
        art = spec["draw"](pose)
        return finish(Art({(x, y + pad): t for (x, y), t in art.items()}), w, h)

    return [(name, [draw(p) for p in poses[name]]) for name in ANIMATION_ORDER]


def build_strip(spec):
    groups = frames_for(spec)
    w, h = spec["size"]
    total = sum(len(f) for _n, f in groups)
    strip = pygame.Surface((w * total, h), pygame.SRCALPHA)
    index, layout = 0, {}
    for name, frames in groups:
        layout[name] = list(range(index, index + len(frames)))
        for frame in frames:
            strip.blit(frame, (index * w, 0))
            index += 1
    return strip, layout


def write_all(sheet_dir=None, only=None):
    for name, spec in MONSTER_ART.items():
        if only and name not in only:
            continue
        folder = os.path.join(OUT_DIR, name)
        os.makedirs(folder, exist_ok=True)
        strip, layout = build_strip(spec)
        pygame.image.save(strip, os.path.join(folder, "frames.png"))
        config = {"scale": SCALE, "frame_size": list(spec["size"]),
                  "anchor": list(spec["anchor"]), "animations": layout}
        with open(os.path.join(folder, "sprite.json"), "w", encoding="utf-8") as handle:
            json.dump(config, handle, indent=2)
        print("wrote", os.path.relpath(folder, REPO_ROOT))
        if sheet_dir:
            save_debug_sheet(name, spec, os.path.join(sheet_dir, name + "_motion.png"))


def save_debug_sheet(name, spec, path, zoom=3):
    """A zoomed picture with one row per animation, to check the motion."""
    groups = frames_for(spec)
    w, h = spec["size"]
    widest = max(len(f) for _n, f in groups)
    sheet = pygame.Surface((widest * w * zoom, len(groups) * h * zoom))
    sheet.fill((43, 38, 60))
    for row, (_animation, frames) in enumerate(groups):
        for col, frame in enumerate(frames):
            big = pygame.transform.scale(frame, (w * zoom, h * zoom))
            sheet.blit(big, (col * w * zoom, row * h * zoom))
            pygame.draw.line(sheet, (60, 54, 84), (col * w * zoom, row * h * zoom),
                             (col * w * zoom, (row + 1) * h * zoom))
    pygame.image.save(sheet, path)
    print("wrote", path)


if __name__ == "__main__":
    pygame.init()
    sheet_dir = None
    if "--sheets" in sys.argv:
        sheet_dir = sys.argv[sys.argv.index("--sheets") + 1]
    only = [a for a in sys.argv[1:] if a in MONSTER_ART]
    write_all(sheet_dir, only)
