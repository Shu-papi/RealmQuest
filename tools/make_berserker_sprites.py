"""
make_berserker_sprites.py - Draws the Berserker Dungeon's monsters as pixel art (pygame only, no extra installs).

    python tools/make_berserker_sprites.py              # writes the sheets + configs
    python tools/make_berserker_sprites.py --preview P  # ...and a preview of every frame at 4x into P

Writes, for each monster, assets/monsters/berserker/<name>/sheet.png (one row of frames, FACING LEFT) and
config.json in the same format as assets/monsters/goblin_minion/goblin_config.json, so
src/monsters/game_sprites.py loads them like the goblin minion:

    orc_warrior   idle 4, walk 6, attack 4 (axe slash)
    orc_shaman    idle 4, walk 6, attack/cast 5 (raises the skull staff, a meteor orb grows, release)
    treant        idle 4, walk 4, attack 4 (drives its branches into the ground: the root attack)
    orc_warlord   the orc warrior, recoloured (blood-red skin, black-and-gold armour): the mini-boss

Every picture is built from a few shapes per body part, then shaded (light from the top-left) and outlined.
The output is the same every run. Tweak a palette or a pose below and run it again.
"""
import json
import math
import os
import sys

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
import pygame  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "assets", "monsters", "berserker")
OUTLINE = (24, 16, 22)

# ---------------------------------------------------------------------------------------------- palettes
ORC = {
    "skin": ((126, 168, 74), (94, 136, 56), (62, 96, 40)),       # light, mid, dark
    "tusk": ((246, 240, 214), (206, 196, 160), (160, 150, 120)),
    "eye": ((255, 214, 80), (255, 214, 80), (255, 214, 80)),
    "hair": ((60, 44, 40), (40, 30, 28), (26, 20, 20)),
    "leather": ((150, 104, 66), (116, 78, 48), (80, 52, 34)),
    "cloth": ((112, 70, 52), (86, 52, 40), (60, 36, 30)),
    "metal": ((214, 216, 222), (158, 162, 174), (104, 108, 122)),
    "wood": ((150, 108, 64), (114, 80, 46), (80, 54, 32)),
    "boot": ((86, 62, 48), (62, 44, 36), (40, 28, 24)),
    "trim": ((180, 150, 90), (140, 110, 64), (100, 76, 44)),
}
WARLORD = dict(ORC)
WARLORD.update({
    "skin": ((198, 92, 76), (158, 58, 50), (110, 34, 34)),       # blood-red
    "eye": ((255, 250, 170), (255, 250, 170), (255, 250, 170)),
    "leather": ((74, 66, 78), (50, 44, 54), (30, 26, 34)),       # black armour...
    "cloth": ((92, 30, 34), (70, 22, 26), (48, 14, 18)),
    "metal": ((255, 226, 120), (222, 176, 64), (160, 116, 36)),  # ...with gold
    "trim": ((255, 226, 120), (222, 176, 64), (160, 116, 36)),
    "hair": ((30, 26, 30), (20, 18, 22), (12, 10, 14)),
})
SHAMAN = dict(ORC)
SHAMAN.update({
    "skin": ((112, 156, 86), (84, 124, 64), (56, 88, 46)),
    "robe": ((132, 64, 52), (100, 44, 40), (68, 28, 30)),
    "bone": ((240, 232, 210), (204, 192, 166), (150, 140, 120)),
    "orb": ((255, 236, 150), (255, 140, 60), (210, 70, 40)),
    "feather": ((60, 150, 160), (40, 110, 124), (26, 74, 86)),
})
TREANT = {
    "bark": ((140, 102, 66), (104, 74, 46), (70, 48, 30)),
    "bark2": ((120, 86, 54), (88, 62, 38), (58, 40, 26)),
    "leaf": ((132, 190, 84), (88, 150, 62), (52, 104, 46)),
    "leaf2": ((180, 210, 96), (120, 170, 70), (70, 120, 50)),
    "glow": ((210, 255, 160), (150, 240, 110), (80, 190, 70)),
    "moss": ((110, 150, 70), (80, 118, 52), (54, 84, 38)),
}


# ---------------------------------------------------------------------------------------------- drawing kit
class Canvas:
    """A small transparent picture drawn with shaded shapes; every shape is (part, tone) aware."""

    def __init__(self, w, h, palette):
        self.s = pygame.Surface((w, h), pygame.SRCALPHA)
        self.p = palette

    def c(self, part, tone=1):
        return self.p[part][tone]

    def rect(self, part, x, y, w, h, shade=True):
        """A box: mid colour, a lit top-left edge and a dark bottom-right edge."""
        x, y, w, h = int(round(x)), int(round(y)), int(round(w)), int(round(h))
        if w <= 0 or h <= 0:
            return
        self.s.fill(self.c(part, 1), (x, y, w, h))
        if shade and w > 1 and h > 1:
            self.s.fill(self.c(part, 0), (x, y, w, 1))
            self.s.fill(self.c(part, 0), (x, y, 1, h))
            self.s.fill(self.c(part, 2), (x, y + h - 1, w, 1))
            self.s.fill(self.c(part, 2), (x + w - 1, y, 1, h))

    def blob(self, part, cx, cy, rx, ry, shade=True):
        """A shaded ellipse: dark rim at the bottom-right, a highlight at the top-left."""
        r = pygame.Rect(int(round(cx - rx)), int(round(cy - ry)), int(round(rx * 2)), int(round(ry * 2)))
        if r.w <= 0 or r.h <= 0:
            return
        pygame.draw.ellipse(self.s, self.c(part, 2 if shade else 1), r)
        if shade and r.w > 2 and r.h > 2:
            pygame.draw.ellipse(self.s, self.c(part, 1), r.inflate(-2, -2).move(-1, -1))
            hl = pygame.Rect(0, 0, max(1, r.w // 3), max(1, r.h // 3))
            hl.topleft = (r.x + max(1, r.w // 5), r.y + max(1, r.h // 5))
            pygame.draw.ellipse(self.s, self.c(part, 0), hl)

    def line(self, part, a, b, width=2, tone=1):
        pygame.draw.line(self.s, self.c(part, tone), (int(round(a[0])), int(round(a[1]))),
                         (int(round(b[0])), int(round(b[1]))), width)

    def poly(self, part, pts, tone=1):
        pygame.draw.polygon(self.s, self.c(part, tone), [(int(round(x)), int(round(y))) for x, y in pts])

    def px(self, part, x, y, tone=1):
        if 0 <= x < self.s.get_width() and 0 <= y < self.s.get_height():
            self.s.set_at((int(x), int(y)), self.c(part, tone))

    def done(self):
        """Add the dark outline around everything that was drawn."""
        w, h = self.s.get_size()
        solid = [[self.s.get_at((x, y)).a > 0 for x in range(w)] for y in range(h)]
        for y in range(h):
            for x in range(w):
                if solid[y][x]:
                    continue
                if any(0 <= x + dx < w and 0 <= y + dy < h and solid[y + dy][x + dx]
                       for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1))):
                    self.s.set_at((x, y), OUTLINE)
        return self.s


def polar(origin, angle_deg, length):
    a = math.radians(angle_deg)
    return origin[0] + math.cos(a) * length, origin[1] + math.sin(a) * length


# ---------------------------------------------------------------------------------------------- the orcs
# All figures face LEFT: their front is toward x = 0. Feet stand on y = FEET.
ORC_W, ORC_H, ORC_FEET = 48, 48, 44


def orc_body(cv, bob=0, step=0.0, lean=0):
    """Legs, torso, head and the back arm of an orc. Returns the front shoulder (for the weapon arm)."""
    cx = 24 + lean
    # legs (step: -1..1 swings them)
    for side, k in ((1, step), (-1, -step)):
        lx = cx + side * 4 + k * 3
        cv.rect("cloth", lx - 3, 33 + bob, 6, 7)
        cv.rect("boot", lx - 4 - (1 if side < 0 else 0), 39 + bob + max(0, -k), 8, 5 - max(0, -k))
    # torso: broad, leaning forward (left)
    cv.blob("skin", cx, 26 + bob, 9, 9)
    cv.rect("leather", cx - 8, 25 + bob, 16, 8)                 # chest plate / harness
    cv.line("trim", (cx - 7, 21 + bob), (cx + 6, 31 + bob), 1, 0)
    cv.rect("trim", cx - 9, 32 + bob, 18, 2)                   # belt
    cv.px("metal", cx - 1, 32 + bob, 0)
    # back arm (behind the body, to the right)
    cv.blob("skin", cx + 9, 27 + bob, 3, 5)
    # head: big jaw, low brow, tusks, a topknot
    hx, hy = cx - 5, 15 + bob
    cv.blob("skin", hx, hy, 7, 7)
    cv.blob("skin", hx - 2, hy + 4, 5, 3)                      # jaw
    cv.rect("hair", hx - 1, hy - 9, 4, 4, shade=False)          # topknot
    cv.rect("hair", hx + 1, hy - 7, 5, 2, shade=False)
    cv.rect("skin", hx - 7, hy - 2, 7, 2, shade=False)          # heavy brow
    cv.px("eye", hx - 4, hy)
    cv.px("eye", hx - 5, hy)
    cv.px("tusk", hx - 6, hy + 5, 0)
    cv.px("tusk", hx - 6, hy + 4, 0)
    cv.px("tusk", hx - 2, hy + 5, 0)
    cv.px("skin", hx + 6, hy - 1, 2)                           # ear
    cv.px("skin", hx + 7, hy - 2, 2)
    return (cx - 7, 23 + bob)


def axe(cv, shoulder, angle, reach=13):
    """The front arm and its axe at `angle` degrees (0 = pointing right, 180 = left/forward)."""
    hand = polar(shoulder, angle, 6)
    cv.line("skin", shoulder, hand, 3)
    tip = polar(hand, angle, reach)
    cv.line("wood", hand, tip, 2)
    # the blade: a wedge across the end of the haft
    a = angle + 90
    b1, b2 = polar(tip, a, 5), polar(tip, a - 180, 2)
    back = polar(tip, angle, -5)
    cv.poly("metal", [b1, polar(b1, angle, -5), back, b2, tip])
    cv.line("metal", b1, polar(b1, angle, -5), 1, 0)            # bright edge
    cv.blob("skin", hand[0], hand[1], 2, 2, shade=False)        # fist


def orc_warrior_frames(palette):
    frames = []
    for i in range(4):                                          # idle: breathing
        bob = (0, 0, 1, 1)[i]
        cv = Canvas(ORC_W, ORC_H, palette)
        sh = orc_body(cv, bob)
        axe(cv, sh, 120 + bob * 4)
        frames.append(cv.done())
    for i in range(6):                                          # walk
        ph = i / 6 * math.tau
        cv = Canvas(ORC_W, ORC_H, palette)
        sh = orc_body(cv, int(round(abs(math.sin(ph)))), math.sin(ph))
        axe(cv, sh, 125 + math.sin(ph) * 14)
        frames.append(cv.done())
    for angle, lean, bob in ((-80, 2, 0), (200, -2, 1), (150, -3, 1), (110, 0, 0)):    # attack: raise, SLASH...
        cv = Canvas(ORC_W, ORC_H, palette)
        sh = orc_body(cv, bob, 0.0, lean)
        axe(cv, sh, angle, 14)
        if angle == 200:                                        # the swoosh of the slash
            for k, r in enumerate((15, 17, 19)):
                arc = pygame.Rect(sh[0] - r, sh[1] - r, r * 2, r * 2)
                pygame.draw.arc(cv.s, (255, 255, 255, 170 - k * 50), arc, math.radians(150), math.radians(250), 1)
        frames.append(cv.done())
    return frames


ORC_ANIMS = {
    "idle": {"frames": [0, 1, 2, 3], "durations": [260, 220, 260, 220], "loop": True},
    "walk": {"frames": [4, 5, 6, 7, 8, 9], "durations": [110] * 6, "loop": True},
    "attack": {"frames": [10, 11, 12, 13], "durations": [260, 90, 140, 260], "loop": False, "hit_frame": 1},
}


def shaman_body(cv, bob=0, step=0.0):
    """A hunched orc in a ragged robe, bone necklace and feather."""
    p = cv
    cx = 25
    for side, k in ((1, step), (-1, -step)):                    # feet under the robe
        p.rect("boot", cx + side * 4 + k * 3 - 3, 40 + bob, 6, 4)
    p.poly("robe", [(cx - 9, 41 + bob), (cx + 10, 41 + bob), (cx + 7, 22 + bob), (cx - 6, 22 + bob)])
    p.poly("robe", [(cx - 9, 41 + bob), (cx - 3, 41 + bob), (cx - 4, 24 + bob), (cx - 6, 22 + bob)], 0)
    p.poly("robe", [(cx + 4, 41 + bob), (cx + 10, 41 + bob), (cx + 7, 22 + bob)], 2)
    for i in range(5):                                          # ragged hem
        p.px("robe", cx - 8 + i * 4, 41 + bob, 2)
    p.rect("cloth", cx - 6, 30 + bob, 13, 2)                    # sash
    hx, hy = cx - 4, 17 + bob
    p.blob("robe", hx + 2, hy - 1, 7, 6)                        # hood behind the head
    p.blob("skin", hx, hy + 1, 5, 5)
    p.px("eye", hx - 3, hy)
    p.px("tusk", hx - 4, hy + 4, 0)
    p.px("tusk", hx - 1, hy + 4, 0)
    for i in range(5):                                          # bone necklace
        p.px("bone", hx - 2 + i * 2, hy + 7, 0)
    p.line("feather", (hx + 6, hy - 6), (hx + 10, hy - 11), 2)
    return (cx - 6, 25 + bob)


def staff(cv, shoulder, angle, orb_r=2, glow=0):
    hand = polar(shoulder, angle, 6)
    cv.line("skin", shoulder, hand, 3)
    top = polar(hand, angle, 16)
    bottom = polar(hand, angle, -8)
    cv.line("wood", bottom, top, 2)
    cv.blob("bone", top[0], top[1], 3, 3)                       # the skull
    cv.px("orb", int(top[0]) - 1, int(top[1]), 2)
    if orb_r:
        ox, oy = polar(top, angle, orb_r + 2)
        if glow:
            pygame.draw.circle(cv.s, (255, 150, 60, 90), (int(ox), int(oy)), orb_r + 3)
        cv.blob("orb", ox, oy, orb_r, orb_r)
    cv.blob("skin", hand[0], hand[1], 2, 2, shade=False)


SHAMAN_H, SHAMAN_DROP = 60, 12          # a taller frame, the shaman drawn lower: room for the raised staff and orb


def orc_shaman_frames(palette):
    frames = []
    d = SHAMAN_DROP
    for i in range(4):
        bob = (0, 0, 1, 1)[i]
        cv = Canvas(ORC_W, SHAMAN_H, palette)
        sh = shaman_body(cv, bob + d)
        staff(cv, sh, 250, orb_r=(1, 2, 2, 1)[i])
        frames.append(cv.done())
    for i in range(6):
        ph = i / 6 * math.tau
        cv = Canvas(ORC_W, SHAMAN_H, palette)
        sh = shaman_body(cv, int(round(abs(math.sin(ph)))) + d, math.sin(ph))
        staff(cv, sh, 250 + math.sin(ph) * 8, orb_r=1)
        frames.append(cv.done())
    for angle, orb, glow in ((240, 2, 0), (262, 3, 1), (272, 4, 1), (276, 6, 1), (250, 1, 0)):   # cast
        cv = Canvas(ORC_W, SHAMAN_H, palette)
        sh = shaman_body(cv, d)
        staff(cv, sh, angle, orb, glow)
        frames.append(cv.done())
    return frames


SHAMAN_ANIMS = {
    "idle": {"frames": [0, 1, 2, 3], "durations": [240] * 4, "loop": True},
    "walk": {"frames": [4, 5, 6, 7, 8, 9], "durations": [130] * 6, "loop": True},
    "attack": {"frames": [10, 11, 12, 13, 14], "durations": [160, 160, 180, 160, 240], "loop": False,
               "hit_frame": 3},
    "cast": {"frames": [10, 11, 12, 13, 14], "durations": [160, 160, 180, 160, 240], "loop": False,
             "hit_frame": 3},
}


# ---------------------------------------------------------------------------------------------- the treant
TREANT_W, TREANT_H, TREANT_FEET = 56, 64, 60


def treant_frame(cv, sway=0.0, step=0.0, arms=0.0, cracks=0):
    """A walking tree. sway: canopy lean, step: root-feet shuffle, arms: 0 = up, 1 = driven into the ground."""
    cx = 28
    for side, k in ((1, step), (-1, -step)):                    # root feet
        fx = cx + side * 7 + k * 3
        cv.poly("bark2", [(fx - 6, 60), (fx + 6, 60), (fx + 3, 48), (fx - 3, 48)])
        cv.line("bark", (fx - 6, 60), (fx - 9, 61), 2, 2)
        cv.line("bark", (fx + 5, 60), (fx + 8, 61), 2, 2)
    # trunk body
    cv.poly("bark", [(cx - 10, 50), (cx + 11, 50), (cx + 9, 22), (cx - 8, 22)])
    cv.poly("bark", [(cx - 10, 50), (cx - 5, 50), (cx - 4, 24), (cx - 8, 22)], 0)
    cv.poly("bark", [(cx + 6, 50), (cx + 11, 50), (cx + 9, 22)], 2)
    for x0 in (cx - 3, cx + 2, cx + 6):                         # bark grooves
        cv.line("bark2", (x0, 26), (x0 + 1, 48), 1, 2)
    cv.blob("moss", cx - 6, 46, 4, 2)
    # face: two glowing hollows and a mouth (facing left)
    cv.rect("bark2", cx - 8, 32, 4, 3, shade=False)
    cv.rect("bark2", cx - 1, 32, 4, 3, shade=False)
    cv.px("glow", cx - 7, 33, 0)
    cv.px("glow", cx, 33, 0)
    cv.line("bark2", (cx - 7, 40), (cx, 41), 2, 2)
    # branch arms
    for side in (-1, 1):
        sx = cx + side * 9
        up = polar((sx, 27), -90 + side * 50 * (1 - arms) + (side * 20 if arms else 0), 1)
        end_angle = (-140 if side < 0 else -40) * (1 - arms) + (100 if side < 0 else 80) * arms
        elbow = polar((sx, 27), end_angle, 10)
        tip = polar(elbow, end_angle + side * 15, 9 + 4 * arms)
        cv.line("bark", (sx, 27), elbow, 4)
        cv.line("bark", elbow, tip, 3)
        cv.line("bark2", polar(elbow, end_angle - 60, 4), elbow, 2)
        if arms < 0.5:
            cv.blob("leaf", tip[0], tip[1], 3, 3)
        del up
    # canopy
    sx = sway * 2
    for (dx, dy, r, part) in ((-8, 14, 9, "leaf"), (6, 13, 9, "leaf"), (-1, 7, 10, "leaf2"),
                              (-10, 8, 6, "leaf"), (9, 6, 6, "leaf2"), (0, 18, 8, "leaf")):
        cv.blob(part, cx + dx + sx, dy, r, r * 0.8)
    for (dx, dy) in ((-6, 4), (5, 9), (-2, 12), (8, 15)):
        cv.px("leaf2", cx + dx + int(sx), dy, 0)
    if cracks:                                                  # the root attack: glowing cracks at its feet
        for k in range(cracks):
            a = 200 + k * 47
            p0 = (cx, 61)
            p1 = polar(p0, a % 360, 6 + k * 2)
            cv.line("glow", p0, (p1[0], min(63, p1[1] + 2)), 1, 1)
    return cv


def treant_frames(palette):
    frames = []
    for i in range(4):
        sway = math.sin(i / 4 * math.tau)
        frames.append(treant_frame(Canvas(TREANT_W, TREANT_H, palette), sway=sway).done())
    for i in range(4):
        st = math.sin(i / 4 * math.tau)
        frames.append(treant_frame(Canvas(TREANT_W, TREANT_H, palette), sway=st * 0.5, step=st).done())
    for arms, cracks in ((0.0, 0), (0.6, 1), (1.0, 4), (0.7, 2)):
        frames.append(treant_frame(Canvas(TREANT_W, TREANT_H, palette), arms=arms, cracks=cracks).done())
    return frames


TREANT_ANIMS = {
    "idle": {"frames": [0, 1, 2, 3], "durations": [320] * 4, "loop": True},
    "walk": {"frames": [4, 5, 6, 7], "durations": [200] * 4, "loop": True},
    "attack": {"frames": [8, 9, 10, 11], "durations": [260, 160, 300, 260], "loop": False, "hit_frame": 2},
}


# ---------------------------------------------------------------------------------------------- output
MONSTERS = {
    #  name           frames                               anims          (w, h)                anchor (x, feet)
    "orc_warrior": (lambda: orc_warrior_frames(ORC), ORC_ANIMS, (ORC_W, ORC_H), (24, ORC_FEET)),
    "orc_warlord": (lambda: orc_warrior_frames(WARLORD), ORC_ANIMS, (ORC_W, ORC_H), (24, ORC_FEET)),
    "orc_shaman": (lambda: orc_shaman_frames(SHAMAN), SHAMAN_ANIMS, (ORC_W, SHAMAN_H), (25, ORC_FEET + SHAMAN_DROP)),
    "treant": (lambda: treant_frames(TREANT), TREANT_ANIMS, (TREANT_W, TREANT_H), (28, TREANT_FEET)),
}


def build(name):
    make, anims, (w, h), anchor = MONSTERS[name]
    frames = make()
    sheet = pygame.Surface((w * len(frames), h), pygame.SRCALPHA)
    for i, f in enumerate(frames):
        sheet.blit(f, (i * w, 0))
    config = {
        "sprite": {"sheet": "sheet.png", "frame_width": w, "frame_height": h, "anchor": list(anchor),
                   "facing_default": "left"},
        "animations": anims,
        "made_by": "tools/make_berserker_sprites.py",
    }
    return sheet, config


def main(argv):
    pygame.display.init()
    pygame.display.set_mode((1, 1))
    preview_path = argv[argv.index("--preview") + 1] if "--preview" in argv else None
    sheets = {}
    for name in MONSTERS:
        sheet, config = build(name)
        folder = os.path.join(OUT, name)
        os.makedirs(folder, exist_ok=True)
        pygame.image.save(sheet, os.path.join(folder, "sheet.png"))
        with open(os.path.join(folder, "config.json"), "w", encoding="utf-8") as f:
            json.dump(config, f, indent=2)
        sheets[name] = sheet
        print("wrote", os.path.relpath(folder, ROOT), sheet.get_size())
    if preview_path:
        k = 4
        width = max(s.get_width() for s in sheets.values()) * k
        height = sum(s.get_height() for s in sheets.values()) * k + 8 * len(sheets)
        out = pygame.Surface((width, height))
        out.fill((70, 66, 84))
        y = 0
        for s in sheets.values():
            out.blit(pygame.transform.scale(s, (s.get_width() * k, s.get_height() * k)), (0, y))
            y += s.get_height() * k + 8
        pygame.image.save(out, preview_path)
        print("preview:", preview_path)


if __name__ == "__main__":
    main(sys.argv[1:])
