"""
Draws the Goblin King's monsters as pixel art and saves one sprite sheet per monster.
Run from the repo root:  python src/monsters/make_monsters.py   (needs: pip install pillow)
Writes the sheets and monsters_preview.png to assets/monsters/goblin_army/.

Every sheet has 3 rows x 4 frames:   row 0 = idle,  row 1 = move,  row 2 = attack
"""
import math
import os
from PIL import Image, ImageDraw

HERE = os.path.dirname(os.path.abspath(__file__))
OUT_DIR = os.path.join(os.path.dirname(os.path.dirname(HERE)), "assets", "monsters", "goblin_army")
OUT = (24, 17, 32, 255)                       # outline colour


# ====================== PALETTES (mid, light, dark) ======================
# Same family of colours as the Goblin King: blue skin, fur, royal red, gold.
def C(r, g, b, a=255):
    return (r, g, b, a)


SKIN = (C(98, 142, 222), C(150, 186, 246), C(62, 92, 170))
FUR = (C(122, 88, 54), C(164, 122, 78), C(82, 57, 36))
GOLD = (C(224, 172, 72), C(252, 218, 122), C(150, 102, 42))
RED = (C(176, 52, 72), C(214, 92, 104), C(112, 30, 52))
CREAM = (C(232, 226, 214), C(250, 246, 238), C(182, 172, 176))
STEEL = (C(158, 164, 184), C(214, 220, 236), C(96, 100, 128))
SNOUT = (C(190, 130, 120), C(228, 170, 160), C(130, 84, 86))
HOOF = (C(70, 52, 48), C(100, 80, 70), C(44, 32, 34))

SLIMES = {
    "blue":  (C(84, 138, 236), C(160, 204, 255), C(44, 80, 172)),
    "red":   (C(226, 78, 78), C(255, 150, 130), C(150, 38, 56)),
    "green": (C(96, 196, 92), C(170, 238, 140), C(48, 124, 66)),
}


# ====================== DRAWING HELPERS ======================
def new(w, h):
    return Image.new("RGBA", (w, h), (0, 0, 0, 0))


def shaded_ellipse(d, box, pal):
    """Ellipse with a light spot top-left and a dark rim bottom-right."""
    x0, y0, x1, y1 = box
    mid, lt, dk = pal
    w, h = x1 - x0, y1 - y0
    d.ellipse(box, fill=dk)
    d.ellipse((x0, y0, x1 - 1, y1 - 1), fill=mid)
    d.ellipse((x0 + max(1, w // 6), y0 + max(1, h // 8),
               x0 + w // 2 + 1, y0 + h // 3 + 1), fill=lt)


def shaded_rect(d, x0, y0, x1, y1, pal):
    mid, lt, dk = pal
    d.rectangle([x0, y0, x1, y1], fill=mid)
    d.line([(x0, y0), (x1, y0)], fill=lt)
    d.line([(x1, y0), (x1, y1)], fill=dk)
    d.line([(x0, y1), (x1, y1)], fill=dk)


def clip_below(img, y):
    """Make every row below y transparent."""
    px = img.load()
    for yy in range(max(0, y + 1), img.height):
        for xx in range(img.width):
            px[xx, yy] = (0, 0, 0, 0)


def outline(img, col=OUT):
    w, h = img.size
    src = img.copy().load()
    px = img.load()
    for y in range(h):
        for x in range(w):
            if src[x, y][3] == 0:
                for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                    nx, ny = x + dx, y + dy
                    if 0 <= nx < w and 0 <= ny < h and src[nx, ny][3] > 0:
                        px[x, y] = col
                        break


def blend(a, b, t):
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3)) + (255,)


# ====================== GOBLIN GENERAL (48 x 48, front view) ======================
def goblin_general(bob=0, ll=0, rl=0, ang=12, hand=(35, 27), shout=False, lean=0):
    im = new(48, 48)
    d = ImageDraw.Draw(im)
    b = bob
    ox = lean

    # legs and feet
    for lx, lift in ((18, ll), (27, rl)):
        shaded_rect(d, lx + ox, 35 + b, lx + 3 + ox, 42 - lift, SKIN)
        shaded_ellipse(d, (lx - 1 + ox, 40 - lift, lx + 5 + ox, 44 - lift), SKIN)

    # white tabard under the armour
    d.polygon([(19 + ox, 33 + b), (28 + ox, 33 + b), (29 + ox, 40 + b), (18 + ox, 40 + b)],
              fill=CREAM[0])
    d.line([(18 + ox, 40 + b), (29 + ox, 40 + b)], fill=RED[0])
    d.line([(23 + ox, 34 + b), (23 + ox, 39 + b)], fill=CREAM[2])

    # torso: red armour with gold plate, belt and emblem
    shaded_rect(d, 15 + ox, 21 + b, 32 + ox, 33 + b, RED)
    shaded_rect(d, 19 + ox, 22 + b, 28 + ox, 28 + b, GOLD)
    d.polygon([(23 + ox, 23 + b), (21 + ox, 27 + b), (26 + ox, 27 + b)], fill=CREAM[0])
    shaded_rect(d, 15 + ox, 31 + b, 32 + ox, 33 + b, GOLD)

    # arms
    shaded_rect(d, 11 + ox, 24 + b, 13 + ox, 32 + b, SKIN)
    hx, hy = hand
    d.line([(33 + ox, 24 + b), (hx + ox, hy + b)], fill=SKIN[0], width=3)

    # gold shoulder plates
    shaded_ellipse(d, (11 + ox, 18 + b, 19 + ox, 26 + b), GOLD)
    shaded_ellipse(d, (28 + ox, 18 + b, 36 + ox, 26 + b), GOLD)

    # shield on the left arm
    shaded_ellipse(d, (3 + ox, 22 + b, 14 + ox, 38 + b), RED)
    d.ellipse((3 + ox, 22 + b, 14 + ox, 38 + b), outline=GOLD[0])
    d.polygon([(8 + ox, 26 + b), (5 + ox, 32 + b), (11 + ox, 32 + b)], fill=GOLD[0])

    # ears (behind the head)
    d.polygon([(20 + ox, 12 + b), (8 + ox, 8 + b), (20 + ox, 17 + b)], fill=SKIN[0])
    d.polygon([(28 + ox, 12 + b), (40 + ox, 8 + b), (28 + ox, 17 + b)], fill=SKIN[0])
    d.polygon([(18 + ox, 12 + b), (11 + ox, 10 + b), (18 + ox, 15 + b)], fill=C(224, 120, 140))
    d.polygon([(30 + ox, 12 + b), (37 + ox, 10 + b), (30 + ox, 15 + b)], fill=C(224, 120, 140))

    # head and face
    shaded_ellipse(d, (18 + ox, 8 + b, 30 + ox, 21 + b), SKIN)
    d.rectangle([21 + ox, 14 + b, 22 + ox, 15 + b], fill=C(255, 214, 80))
    d.rectangle([26 + ox, 14 + b, 27 + ox, 15 + b], fill=C(255, 214, 80))
    d.point((22 + ox, 15 + b), fill=C(160, 30, 40))
    d.point((26 + ox, 15 + b), fill=C(160, 30, 40))
    d.line([(20 + ox, 13 + b), (23 + ox, 14 + b)], fill=SKIN[2])
    d.line([(28 + ox, 13 + b), (25 + ox, 14 + b)], fill=SKIN[2])
    if shout:
        d.rectangle([21 + ox, 17 + b, 27 + ox, 20 + b], fill=C(60, 14, 30))
        d.rectangle([22 + ox, 17 + b, 23 + ox, 18 + b], fill=CREAM[0])
        d.rectangle([25 + ox, 17 + b, 26 + ox, 18 + b], fill=CREAM[0])
    else:
        d.line([(22 + ox, 18 + b), (26 + ox, 18 + b)], fill=SKIN[2])
        d.point((21 + ox, 18 + b), fill=CREAM[0])
        d.point((27 + ox, 18 + b), fill=CREAM[0])

    # gold helmet with a red plume
    helm = new(48, 48)
    hd = ImageDraw.Draw(helm)
    shaded_ellipse(hd, (17 + ox, 3 + b, 31 + ox, 16 + b), GOLD)
    clip_below(helm, 11 + b)
    im.alpha_composite(helm)
    d.line([(17 + ox, 11 + b), (31 + ox, 11 + b)], fill=RED[0])
    d.rectangle([23 + ox, 11 + b, 24 + ox, 16 + b], fill=GOLD[0])
    d.polygon([(22 + ox, 4 + b), (25 + ox, -2 + b), (29 + ox, 2 + b), (27 + ox, 5 + b)], fill=RED[0])

    # sword
    a = math.radians(ang)
    L = 19
    tx, ty = hx + ox + L * math.sin(a), hy + b - L * math.cos(a)
    d.line([(hx + ox, hy + b), (tx, ty)], fill=STEEL[0], width=4)
    d.line([(hx + ox, hy + b), (tx, ty)], fill=STEEL[1], width=2)
    gx, gy = math.cos(a) * 3, math.sin(a) * 3
    d.line([(hx + ox - gx, hy + b - gy), (hx + ox + gx, hy + b + gy)], fill=GOLD[0], width=2)
    d.ellipse((hx + ox - 2, hy + b - 2, hx + ox + 2, hy + b + 2), fill=SKIN[0])

    outline(im)
    return im


def general_frames():
    idle = [goblin_general(bob=b) for b in (0, 1, 1, 0)]
    walk = [goblin_general(bob=b, ll=l, rl=r, lean=1)
            for b, l, r in ((0, 0, 0), (1, 2, 0), (0, 0, 0), (1, 0, 2))]
    attack = [goblin_general(ang=-25, hand=(35, 19)),
              goblin_general(ang=10, hand=(35, 14), shout=True),
              goblin_general(ang=100, hand=(35, 24), shout=True, lean=2),
              goblin_general(ang=170, hand=(33, 30), lean=1)]
    return [idle, walk, attack]


# ====================== GIANT BOAR (72 x 48, side view facing right) ======================
FUR_DOTS = [(18, 24), (22, 30), (28, 33), (34, 22), (38, 31), (42, 26), (15, 29),
            (26, 19), (31, 28), (20, 34)]


def boar(dx=0, bob=0, hd=0, legs=(0, 0, 0, 0), lift=(0, 0, 0, 0), dust=0, mouth=False):
    im = new(72, 48)
    d = ImageDraw.Draw(im)
    ground = 42
    xs = (16, 40, 22, 46)                       # far back, far front, near back, near front

    def leg(i, pal):
        x = xs[i] + legs[i]
        top = 32 + bob
        bottom = ground - lift[i]
        shaded_rect(d, x - 2, top, x + 1, bottom, pal)
        shaded_rect(d, x - 2, bottom - 2, x + 1, bottom, HOOF)

    # far legs
    dark = (FUR[2], FUR[0], C(56, 38, 26))
    leg(0, dark)
    leg(1, dark)

    # tail
    for p in ((9, 22), (8, 21), (8, 20), (9, 19), (10, 19)):
        d.point((p[0] + dx, p[1] + bob), fill=FUR[2])

    # mane spikes (behind the body)
    for i in range(6):
        x = 15 + dx + i * 5
        top = 16 + bob + int(abs(i - 2.5) * 1.3)
        d.polygon([(x, top + 2), (x + 2, top - 6), (x + 5, top + 2)], fill=FUR[2])

    # body
    shaded_ellipse(d, (10 + dx, 13 + bob, 50 + dx, 38 + bob), FUR)
    for (fx, fy) in FUR_DOTS:
        d.point((fx + dx, fy + bob), fill=FUR[2])

    # red war blanket with gold trim and emblem
    d.polygon([(25 + dx, 15 + bob), (40 + dx, 15 + bob), (42 + dx, 29 + bob), (23 + dx, 29 + bob)],
              fill=RED[0])
    d.line([(25 + dx, 15 + bob), (23 + dx, 29 + bob)], fill=RED[1])
    d.line([(40 + dx, 15 + bob), (42 + dx, 29 + bob)], fill=RED[2])
    d.rectangle([23 + dx, 28 + bob, 42 + dx, 30 + bob], fill=GOLD[0])
    d.polygon([(32 + dx, 19 + bob), (29 + dx, 25 + bob), (35 + dx, 25 + bob)], fill=GOLD[0])

    # near legs
    leg(2, FUR)
    leg(3, FUR)

    # head
    hb = bob + hd
    d.polygon([(46 + dx, 22 + hb), (49 + dx, 14 + hb), (53 + dx, 22 + hb)], fill=FUR[2])
    d.polygon([(48 + dx, 21 + hb), (49 + dx, 17 + hb), (51 + dx, 21 + hb)], fill=SNOUT[1])
    shaded_ellipse(d, (43 + dx, 19 + hb, 59 + dx, 37 + hb), FUR)
    shaded_ellipse(d, (53 + dx, 26 + hb, 63 + dx, 36 + hb), SNOUT)
    d.point((60 + dx, 29 + hb), fill=HOOF[2])
    d.point((60 + dx, 32 + hb), fill=HOOF[2])
    if mouth:
        d.rectangle([54 + dx, 34 + hb, 61 + dx, 36 + hb], fill=C(60, 14, 30))
    # tusks
    d.polygon([(54 + dx, 35 + hb), (58 + dx, 35 + hb), (61 + dx, 27 + hb)], fill=CREAM[0])
    d.polygon([(54 + dx, 35 + hb), (56 + dx, 35 + hb), (59 + dx, 28 + hb)], fill=CREAM[1])
    # angry eye
    d.rectangle([50 + dx, 25 + hb, 52 + dx, 27 + hb], fill=C(230, 50, 50))
    d.point((51 + dx, 26 + hb), fill=C(255, 220, 120))
    d.line([(48 + dx, 23 + hb), (53 + dx, 25 + hb)], fill=FUR[2], width=2)
    # gold collar (relates to the king's gold)
    d.line([(44 + dx, 33 + bob), (47 + dx, 37 + hb)], fill=GOLD[0], width=2)

    outline(im)

    # dust puffs are soft, so they are drawn after the outline
    if dust:
        dd = ImageDraw.Draw(im)
        for i in range(dust + 1):
            r = 2 + i
            cx, cy = 8 + dx - i * 4, ground - 2 - i
            dd.ellipse((cx - r, cy - r, cx + r, cy + r), fill=(235, 225, 205, 150))
    return im


def boar_frames():
    idle = [boar(bob=b, hd=h) for b, h in ((0, 0), (1, 0), (1, 1), (0, 0))]
    walk_legs = [(-2, 2, 2, -2), (0, 0, 0, 0), (2, -2, -2, 2), (0, 0, 0, 0)]
    walk_lift = [(0, 0, 0, 0), (2, 0, 0, 2), (0, 0, 0, 0), (0, 2, 2, 0)]
    walk = [boar(bob=(i % 2), legs=walk_legs[i], lift=walk_lift[i]) for i in range(4)]
    attack = [boar(dx=-3, bob=1, hd=3, legs=(-3, -2, -2, -1)),
              boar(dx=3, hd=2, legs=(-4, 4, 4, -4), dust=1),
              boar(dx=5, bob=-1, hd=2, legs=(4, -4, -4, 4), dust=2, mouth=True),
              boar(dx=2, legs=(1, 1, 1, 1), dust=1)]
    return [idle, walk, attack]


# ====================== SLIME (32 x 32, front view) ======================
def slime(kind, w=22, h=16, dx=0, dy=0, mouth=0, glint=True):
    pal = SLIMES[kind]
    im = new(32, 32)
    d = ImageDraw.Draw(im)
    cx = 16 + dx
    base = 28 - dy
    x0, x1 = cx - w // 2, cx + w // 2
    top = base - h

    body = new(32, 32)
    bd = ImageDraw.Draw(body)
    shaded_ellipse(bd, (x0, top, x1, base + int(h * 0.55)), pal)
    clip_below(body, base)
    im.alpha_composite(body)
    d = ImageDraw.Draw(im)
    d.line([(x0 + 2, base), (x1 - 2, base)], fill=pal[2])          # wet bottom edge

    # type decoration on top
    if kind == "red":                                              # little flames
        d.polygon([(cx - 2, top + 2), (cx - 1, top - 4), (cx + 1, top + 2)], fill=C(255, 170, 60))
        d.polygon([(cx + 1, top + 3), (cx + 3, top - 2), (cx + 4, top + 3)], fill=C(255, 120, 50))
        d.point((cx - 1, top - 1), fill=C(255, 236, 140))
    elif kind == "blue":                                           # water drop
        d.polygon([(cx, top - 4), (cx - 2, top + 1), (cx + 2, top + 1)], fill=pal[1])
        d.point((cx - 1, top), fill=C(255, 255, 255))
    else:                                                          # poison bubbles
        d.ellipse((cx - 4, top - 2, cx - 1, top + 1), fill=pal[1])
        d.ellipse((cx + 1, top - 4, cx + 4, top - 1), fill=pal[1])
        d.point((cx + 2, top - 3), fill=C(255, 255, 255))

    # a gold coin it swallowed (relates to the king's treasure)
    coin = blend(pal[0], GOLD[0], 0.75)
    gx, gy = cx + w // 5, base - max(4, h // 4)
    d.rectangle([gx, gy, gx + 2, gy + 2], fill=coin)
    d.point((gx, gy), fill=blend(pal[1], GOLD[1], 0.8))

    # highlight
    if glint:
        d.point((x0 + 4, top + max(3, h // 5)), fill=C(255, 255, 255))
        d.point((x0 + 5, top + max(3, h // 5)), fill=C(255, 255, 255))
        d.point((x0 + 4, top + max(3, h // 5) + 1), fill=C(255, 255, 255))

    # face
    ey = top + int(h * 0.42)
    for ex in (cx - 4, cx + 2):
        d.rectangle([ex, ey, ex + 2, ey + 3], fill=C(24, 17, 32))
        d.point((ex, ey), fill=C(255, 255, 255))
    if mouth:
        d.rectangle([cx - 2, ey + 6, cx + 2, ey + 9], fill=C(60, 14, 30))
        d.point((cx - 2, ey + 6), fill=C(255, 255, 255))
        d.point((cx + 2, ey + 6), fill=C(255, 255, 255))
    else:
        d.line([(cx - 2, ey + 6), (cx + 2, ey + 6)], fill=pal[2])

    outline(im)
    # soft ground shadow under it
    sh = new(32, 32)
    sd = ImageDraw.Draw(sh)
    sd.ellipse((x0 - 1, 27, x1 + 1, 31), fill=(0, 0, 0, 70))
    sh.alpha_composite(im)
    return sh


def slime_frames(kind):
    idle = [slime(kind, w, h) for w, h in ((22, 17), (23, 16), (24, 14), (22, 16))]
    move = [slime(kind, 25, 12),                           # squash
            slime(kind, 19, 21, dy=0),                     # stretch up
            slime(kind, 20, 19, dy=6),                     # in the air
            slime(kind, 26, 11)]                           # landing
    attack = [slime(kind, 26, 12),                         # crouch
              slime(kind, 19, 21, dy=1),                   # rear up
              slime(kind, 27, 16, dy=3, mouth=1),          # lunge with open mouth
              slime(kind, 24, 14, mouth=1)]                # recover
    return [idle, move, attack]


# ====================== SHEETS + PREVIEW ======================
def make_sheet(rows, frame_w, frame_h, name):
    sheet = new(frame_w * 4, frame_h * 3)
    for r, frames in enumerate(rows):
        for c, f in enumerate(frames):
            sheet.paste(f, (c * frame_w, r * frame_h))
    os.makedirs(OUT_DIR, exist_ok=True)
    path = os.path.join(OUT_DIR, name)
    sheet.save(path)
    return sheet


def main():
    sheets = {
        "Goblin General": make_sheet(general_frames(), 48, 48, "goblin_general_sheet.png"),
        "Giant Boar": make_sheet(boar_frames(), 72, 48, "giant_boar_sheet.png"),
    }
    for kind in SLIMES:
        sheets[f"{kind.title()} Slime"] = make_sheet(slime_frames(kind), 32, 32, f"slime_{kind}_sheet.png")

    # preview image: every sheet enlarged, on a dark background
    S = 4
    pad = 16
    imgs = [(n, s.resize((s.width * S, s.height * S), Image.NEAREST)) for n, s in sheets.items()]
    cols = [imgs[:2], imgs[2:]]
    W = max(sum(i.width for _, i in c) + pad * (len(c) + 1) for c in cols)
    H = sum(max(i.height for _, i in c) + 40 for c in cols) + pad
    prev = Image.new("RGBA", (W, H), (44, 42, 53, 255))
    pd = ImageDraw.Draw(prev)
    y = pad
    for group in cols:
        x = pad
        for name, img in group:
            pd.text((x, y), name, fill=(255, 255, 255))
            prev.alpha_composite(img, (x, y + 16))
            x += img.width + pad
        y += max(i.height for _, i in group) + 40
    prev.convert("RGB").save(os.path.join(OUT_DIR, "monsters_preview.png"))
    print("done")


if __name__ == "__main__":
    main()
