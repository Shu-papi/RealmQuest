"""
npc_art.py - pixel-art villagers for Oakwood.

    make_npc_frames(look)  -> {(facing, step): Surface}  walking sprites (34x54, kids 34x46)
    portrait(look_id)      -> 256x256 bust portrait for the dialog box

Sprites are drawn on a 16x24 grid (kids 16x20), outlined, then scaled 2x.
Every look has its own hair style, clothes and a held prop, so villagers
read at a glance.
"""
from __future__ import annotations

import pygame


def _shade(c, f):
    return tuple(max(0, min(255, int(v * f))) for v in c[:3])


OUTLINE = (24, 18, 24, 255)
STEEL, STEEL_D, STEEL_L = (156, 162, 178), (98, 104, 122), (214, 220, 232)
WOOD, WOOD_D = (128, 88, 52), (88, 58, 32)

LOOKS = {
    "hero":    dict(skin=(238, 192, 152), hair=(112, 64, 36), style="short", eyes=(50, 80, 140),
                    top=(58, 98, 172), pants=(74, 58, 52), boot=(46, 32, 28), acc=(150, 40, 46), extra="cape"),
    "maren":   dict(skin=(226, 186, 150), hair=(222, 222, 230), style="bun", eyes=(70, 96, 130),
                    top=(110, 70, 140), pants=(88, 56, 112), boot=(50, 36, 40), acc=(232, 200, 120),
                    extra="shawl", held="staff", robe=True, wrinkles=True),
    "torvin":  dict(skin=(206, 150, 110), hair=(92, 50, 30), style="bald", beard=(110, 60, 34), eyes=(40, 30, 26),
                    top=(150, 104, 70), pants=(64, 54, 50), boot=(40, 30, 26), acc=(84, 64, 52),
                    extra="apron", held="hammer"),
    "wren":    dict(skin=(240, 204, 170), hair=(196, 84, 44), style="hood", eyes=(60, 120, 70),
                    top=(84, 140, 92), pants=(104, 84, 62), boot=(70, 48, 32), acc=(60, 104, 66),
                    held="satchel", freckles=True),
    "pip":     dict(skin=(244, 206, 166), hair=(214, 160, 74), style="messy", eyes=(60, 90, 150),
                    top=(214, 124, 62), pants=(70, 82, 124), boot=(70, 46, 32), acc=(220, 60, 60),
                    extra="scarf", kid=True, freckles=True),
    "hale":    dict(skin=(222, 176, 140), hair=(54, 42, 36), style="helmet", eyes=(44, 54, 70),
                    top=(150, 156, 172), pants=(70, 70, 82), boot=(40, 40, 46), acc=(176, 46, 46),
                    extra="armor", held="spear", stubble=True),
    "bram":    dict(skin=(218, 172, 134), hair=(196, 196, 190), style="hat", beard=(206, 206, 200), eyes=(60, 60, 60),
                    top=(140, 128, 76), pants=(86, 70, 52), boot=(56, 42, 30), acc=(214, 184, 98),
                    held="pitchfork", wrinkles=True),
    "lisbet":  dict(skin=(236, 196, 160), hair=(104, 56, 32), style="braid", eyes=(90, 64, 40),
                    top=(182, 72, 88), pants=(130, 62, 78), boot=(70, 42, 36), acc=(240, 232, 214),
                    held="basket", robe=True),
    "refugee": dict(skin=(214, 170, 134), hair=(66, 48, 36), style="hood", eyes=(50, 40, 34),
                    top=(116, 102, 90), pants=(76, 64, 56), boot=(46, 36, 30), acc=(96, 84, 74),
                    held="bundle", soot=True),
    "merlin":  dict(skin=(232, 198, 172), hair=(236, 236, 242), style="wizard", beard=(240, 240, 246), eyes=(80, 130, 210),
                    top=(46, 60, 140), pants=(38, 48, 116), boot=(40, 34, 48), acc=(130, 210, 255),
                    held="staff", robe=True, wrinkles=True, long_beard=True, extra="stars"),
    "baker":   dict(skin=(232, 188, 150), hair=(150, 96, 52), style="short", eyes=(70, 50, 40),
                    top=(170, 150, 120), pants=(90, 74, 60), boot=(54, 40, 30), acc=(236, 230, 214),
                    extra="apron", soot=True),
    # the player's hero, one look per class (picked on the class select screen)
    "hero_warrior": dict(skin=(238, 192, 152), hair=(112, 64, 36), style="helmet", eyes=(50, 80, 140),
                         top=(150, 158, 176), pants=(74, 58, 52), boot=(46, 32, 28), acc=(178, 40, 46),
                         extra="armor", held="sword"),
    "hero_mage":    dict(skin=(238, 196, 160), hair=(70, 46, 96), style="hood", eyes=(150, 90, 220),
                         top=(92, 52, 150), pants=(64, 36, 110), boot=(42, 30, 52), acc=(120, 70, 190),
                         held="staff", robe=True, extra="stars"),
    "hero_archer":  dict(skin=(234, 190, 150), hair=(196, 150, 80), style="hood", eyes=(60, 120, 70),
                         top=(118, 88, 54), pants=(70, 82, 52), boot=(70, 48, 32), acc=(58, 116, 64),
                         held="bow"),
}

CLASS_LOOKS = {"warrior": "hero_warrior", "mage": "hero_mage", "archer": "hero_archer"}


def hero_look(character_class):
    """Look id for the player's hero of this class ('warrior' / 'mage' / 'archer')."""
    return CLASS_LOOKS.get(character_class, "hero_warrior")


POLES = ("staff", "spear", "pitchfork", "sword", "bow")


def _mix_pink(skin):
    return (min(255, skin[0] + 10), int(skin[1] * 0.82), int(skin[2] * 0.82))


def _outlined(s, scale):
    w, h = s.get_size()
    sil = pygame.mask.from_surface(s).to_surface(setcolor=OUTLINE, unsetcolor=(0, 0, 0, 0))
    out = pygame.Surface((w + 2, h + 2), pygame.SRCALPHA)
    for dx, dy in ((0, 1), (2, 1), (1, 0), (1, 2)):
        out.blit(sil, (dx, dy))
    out.blit(s, (1, 1))
    return pygame.transform.scale(out, ((w + 2) * scale, (h + 2) * scale))


def make_npc_frames(look):
    """Walking frames {(facing, step): Surface}, drawn at double detail (32 px wide, 1x)."""
    frames = {}
    for facing in ("down", "up", "side"):
        for step in (0, 1, 2):
            frames[(facing, step)] = _outlined(_figure_hd(look, facing, step), 1)
    return frames


_PORTRAITS: dict = {}


def portrait(look_id):
    p = _PORTRAITS.get(look_id)
    if p is None:
        p = _PORTRAITS[look_id] = _outlined(_bust_hd(LOOKS[look_id]), 2)     # 260x260 incl. outline
    return p


# =========================================================================== #
#  HD art: map sprites on a 32-wide grid (double the old detail, same size on
#  screen) and 256x256 dialog portraits (drawn on 128x128, scaled 2x).
# =========================================================================== #
GOLD = (236, 196, 92)
TOP = 6                      # head room above the head for hats, buns and plumes


def _hi(c, f=1.18):
    return tuple(max(0, min(255, int(v * f))) for v in c[:3])


def _figure_hd(lk, facing, step):
    kid = lk.get("kid", False)
    H = 44 if kid else 52
    s = pygame.Surface((32, H), pygame.SRCALPHA)
    f = s.fill
    el = lambda c, r: pygame.draw.ellipse(s, c, r)
    poly = lambda c, pts: pygame.draw.polygon(s, c, pts)
    skin, hair = lk["skin"], lk["hair"]
    skin_d, skin_l = _shade(skin, 0.8), _hi(skin, 1.07)
    hair_d, hair_l = _shade(hair, 0.72), _hi(hair, 1.22)
    top, pants, boot, acc = lk["top"], lk["pants"], lk["boot"], lk["acc"]
    top_d, top_l = _shade(top, 0.72), _hi(top, 1.18)
    style, extra, held = lk["style"], lk.get("extra"), lk.get("held")
    robe = lk.get("robe", False)
    eye = lk.get("eyes", (40, 30, 30))
    # body layout
    hy = TOP + (3 if kid else 2)                 # head top
    hh = 17                                      # head height
    bt = hy + hh - 1                             # torso top
    bh = 9 if kid else 12                        # torso height
    lt = bt + bh                                 # legs top
    ll = H - 3 - lt                              # leg length (boots below)
    sw = (0, 1, -1)[step]                        # arm swing / leg stride

    # ---------------------------------------------------------------- behind the body
    if held in POLES and facing != "up":
        _held_hd(s, lk, held, facing, H, bt, front=False)
    if extra == "cape" and facing != "down":
        poly(_shade(acc, 0.85), [(9, bt + 1), (23, bt + 1), (25, lt + ll - 2), (7, lt + ll - 2)])
    if held == "bundle" and facing in ("side", "up"):
        el((150, 130, 100), (5 if facing == "side" else 8, bt, 16, 12))
        el((120, 100, 76), (5 if facing == "side" else 8, bt + 7, 16, 5))

    # ---------------------------------------------------------------- legs and boots
    if facing != "side":
        for i, lx in enumerate((10, 17)):
            n = ll + ((-1, 0)[i] if step == 1 else ((0, -1)[i] if step == 2 else 0))
            f(pants, (lx, lt, 5, n)); f(_shade(pants, 0.78), (lx + 3, lt, 2, n))
            f(boot, (lx - 1, lt + n - 1, 7, 4)); f(_hi(boot, 1.35), (lx, lt + n - 1, 3, 1))
    else:
        for i, lx in enumerate((12, 16)):
            x = lx + (sw * 2 if i else -sw * 2)
            f(_shade(pants, 0.82 if i == 0 else 1.0), (x, lt, 5, ll))
            f(boot, (x, lt + ll - 1, 7, 4)); f(_hi(boot, 1.35), (x + 1, lt + ll - 1, 3, 1))
    if robe:
        rl = ll + 1
        poly(pants, [(8, lt - 2), (24, lt - 2), (27, lt + rl), (5, lt + rl)])
        poly(_shade(pants, 0.75), [(20, lt - 2), (24, lt - 2), (27, lt + rl), (21, lt + rl)])
        f(_hi(pants, 1.15), (9, lt - 1, 2, rl - 1))
        f(_shade(pants, 0.6), (5, lt + rl - 1, 23, 2))
        for x in (12, 17):
            f(_shade(pants, 0.86), (x, lt + 2, 1, rl - 3))          # folds

    # ---------------------------------------------------------------- torso and arms
    if facing == "side":
        f(top, (11, bt, 11, bh)); f(top_d, (11, bt, 2, bh)); f(top_l, (19, bt + 1, 2, bh - 2))
        if not robe:
            f((88, 60, 34), (11, bt + bh - 3, 11, 2))
        ax = 15 + sw * 2
        f(top_d, (ax, bt + 2, 4, bh - 3)); f(skin, (ax, bt + bh - 1, 4, 3))
    else:
        body = acc if (facing == "up" and extra == "cape") else top
        bd, bl = _shade(body, 0.72), _hi(body, 1.18)
        el(body, (6, bt - 1, 20, 6))                                      # shoulders
        f(body, (8, bt + 1, 16, bh - 1))
        f(bl, (8, bt + 1, 2, bh - 2)); f(bd, (21, bt + 1, 3, bh - 1))
        if facing == "down":
            f(skin_d, (14, bt, 4, 2))                                     # neck shadow
            if not robe:
                f((88, 60, 34), (8, bt + bh - 3, 16, 2)); f((214, 176, 80), (15, bt + bh - 3, 2, 2))
            else:
                f(_shade(body, 0.85), (15, bt + 3, 2, bh - 3))
        dl, dr = (sw, -sw) if facing == "down" else (0, 0)
        for x, d in ((5, dl), (24, dr)):                                  # arms
            f(top_d, (x, bt + 1, 3, bh - 2 + d)); f(_hi(top_d, 1.2), (x, bt + 1, 1, bh - 3 + d))
            f(skin, (x, bt + bh - 1 + d, 3, 3)); f(skin_d, (x + 2, bt + bh + d, 1, 2))

    # ---------------------------------------------------------------- clothing extras
    if facing != "up":
        if extra == "apron":
            ax, aw = (10, 12) if facing == "down" else (16, 6)
            f(acc, (ax, bt + 3, aw, bh + 3)); f(_shade(acc, 0.8), (ax, bt + bh + 5, aw, 1))
            f(_shade(acc, 0.7), (ax + 1, bt, 1, 3)); f(_shade(acc, 0.7), (ax + aw - 2, bt, 1, 3))
            if facing == "down":
                f(_shade(acc, 0.85), (ax + 4, bt + 6, 4, 3))               # pocket
        elif extra == "shawl":
            poly(acc, [(6, bt - 1), (26, bt - 1), (22, bt + 5), (16, bt + 7), (10, bt + 5)] if facing == "down"
                 else [(10, bt), (22, bt), (20, bt + 5), (12, bt + 5)])
            f(GOLD, (15, bt + 4, 2, 2))
        elif extra == "scarf":
            f(acc, (8, bt - 1, 16, 3) if facing == "down" else (11, bt - 1, 11, 3))
            f(_shade(acc, 0.8), (20 if facing == "down" else 12, bt + 2, 3, 5))
        elif extra == "armor":
            if facing == "down":
                f(STEEL, (9, bt + 1, 14, bh - 3)); f(STEEL_L, (10, bt + 2, 3, bh - 5)); f(STEEL_D, (20, bt + 1, 3, bh - 3))
                f(acc, (14, bt + 2, 4, bh - 4)); f(GOLD, (15, bt + 4, 2, 2))
                el(STEEL_L, (4, bt - 2, 8, 6)); el(STEEL_L, (20, bt - 2, 8, 6))
            else:
                f(STEEL, (12, bt + 1, 9, bh - 3)); el(STEEL_L, (13, bt - 2, 8, 6))
        elif extra == "cape" and facing == "down":
            f(acc, (6, bt, 2, bh)); f(acc, (24, bt, 2, bh)); f(GOLD, (9, bt, 2, 2)); f(GOLD, (21, bt, 2, 2))
        elif extra == "stars":
            for x, y in ((10, bt + 3), (20, bt + 6), (8, lt + 3), (19, lt + 6), (23, lt + 2), (13, lt + 8)):
                if facing == "down" or 11 <= x <= 22:
                    f(GOLD, (x, y, 1, 1))
    elif extra in ("shawl", "scarf"):
        f(acc, (7, bt - 1, 18, 4))
    if held == "satchel" and facing == "down":
        pygame.draw.line(s, (110, 74, 42), (8, bt), (22, bt + bh - 1), 2)
        f((110, 74, 42), (20, bt + bh - 2, 6, 5)); f((140, 96, 56), (20, bt + bh - 2, 6, 1))
    if lk.get("soot") and facing == "down":
        f(_shade(top, 0.55), (11, bt + 4, 2, 1)); f(_shade(top, 0.55), (19, bt + 2, 2, 1))

    # ---------------------------------------------------------------- head
    ey = hy + 8
    if facing == "down":
        el(skin, (7, hy, 18, hh)); f(skin_d, (21, hy + 4, 3, hh - 7))
        el(skin_l, (9, hy + 3, 6, 5))
        f(skin_d, (6, ey, 2, 3)); f(skin_d, (24, ey, 2, 3))                    # ears
        for x in (10, 18):
            f((248, 246, 240), (x, ey, 4, 3)); f(eye, (x + 1, ey, 2, 3))
            f((20, 16, 16), (x + 1, ey + 1, 2, 1)); f((255, 255, 255), (x + 1, ey, 1, 1))
            f(hair_d if style != "bald" else skin_d, (x, ey - 2, 4, 1))         # brows
        f(skin_d, (15, ey + 3, 2, 2))                                          # nose
        f(_shade((200, 90, 90), skin[0] / 255), (14, ey + 6, 4, 1))            # mouth
        if lk.get("freckles"):
            for x in (10, 12, 19, 21):
                f(_shade(skin, 0.8), (x, ey + 4, 1, 1))
        elif not lk.get("beard"):
            f(_mix_pink(skin), (9, ey + 4, 3, 1)); f(_mix_pink(skin), (20, ey + 4, 3, 1))
        if lk.get("wrinkles"):
            f(skin_d, (9, ey + 3, 2, 1)); f(skin_d, (21, ey + 3, 2, 1)); f(skin_d, (13, hy + 4, 6, 1))
        if lk.get("stubble"):
            for x in range(10, 22, 2):
                f(_shade(skin, 0.82), (x, ey + 5 + (x % 4 == 0), 1, 1))
        if lk.get("soot"):
            f(_shade(skin, 0.68), (20, ey + 3, 2, 2))
        if lk.get("beard"):
            b = lk["beard"]
            poly(b, [(8, ey + 3), (24, ey + 3), (23, ey + 8), (16, ey + 11), (9, ey + 8)])
            poly(_shade(b, 0.8), [(19, ey + 3), (24, ey + 3), (23, ey + 8), (17, ey + 11)])
            f(_shade(b, 0.7), (12, ey + 5, 8, 1)); f(_shade((200, 90, 90), skin[0] / 255), (14, ey + 6, 4, 1))
            if lk.get("long_beard"):
                poly(b, [(10, ey + 9), (22, ey + 9), (19, bt + bh), (16, bt + bh + 3), (13, bt + bh)])
                poly(_shade(b, 0.82), [(18, ey + 9), (22, ey + 9), (19, bt + bh), (16, bt + bh + 3)])
                for y in range(ey + 11, bt + bh, 3):
                    f(_shade(b, 0.88), (14, y, 3, 1))
        _hair_hd(s, lk, style, "down", hy, hair, hair_d, hair_l, skin)
    elif facing == "up":
        el(skin, (7, hy, 18, hh)); f(skin_d, (6, ey, 2, 3)); f(skin_d, (24, ey, 2, 3))
        _hair_hd(s, lk, style, "up", hy, hair, hair_d, hair_l, skin)
    else:
        el(skin, (9, hy, 17, hh)); f(skin_d, (10, hy + 5, 4, hh - 8))
        f(skin, (25, ey + 1, 2, 3))                                            # nose
        f(skin_d, (12, ey, 3, 4))                                              # ear
        f((248, 246, 240), (20, ey, 3, 3)); f(eye, (21, ey, 2, 3)); f((255, 255, 255), (21, ey, 1, 1))
        f(hair_d if style != "bald" else skin_d, (20, ey - 2, 4, 1))
        f(_shade((200, 90, 90), skin[0] / 255), (22, ey + 6, 3, 1))
        if lk.get("beard"):
            b = lk["beard"]
            poly(b, [(15, ey + 3), (25, ey + 3), (24, ey + 9), (18, ey + 10)])
            if lk.get("long_beard"):
                poly(b, [(17, ey + 9), (24, ey + 9), (22, bt + bh + 2), (19, bt + bh)])
        _hair_hd(s, lk, style, "side", hy, hair, hair_d, hair_l, skin)

    if held and not (held in POLES and facing == "up"):
        _held_hd(s, lk, held, facing, H, bt, front=True)
    if held in POLES and facing == "up":
        _held_hd(s, lk, held, facing, H, bt, front=True)
    return s


def _hair_hd(s, lk, style, facing, hy, hair, hair_d, hair_l, skin):
    f = s.fill
    el = lambda c, r: pygame.draw.ellipse(s, c, r)
    poly = lambda c, pts: pygame.draw.polygon(s, c, pts)
    acc = lk["acc"]
    side = facing == "side"
    x0 = 9 if side else 7
    if style == "hood":
        if facing == "up":
            el(_shade(acc, 0.85), (x0 - 3, hy - 3, 24, 22))
            el(acc, (x0 - 2, hy - 3, 22, 21))
            return
        el(_shade(acc, 0.85), (x0 - 3, hy - 3, 24, 12))
        el(acc, (x0 - 2, hy - 3, 22, 11))
        el(_hi(acc, 1.15), (x0 + 2, hy - 2, 10, 4))
        if facing == "down":
            f(acc, (4, hy + 4, 4, 13)); f(acc, (24, hy + 4, 4, 13))
            f(hair, (9, hy + 4, 14, 2))
        else:
            f(acc, (x0 - 2, hy + 4, 7, 13)); f(hair, (x0 + 5, hy + 4, 8, 2))
        return
    if style == "helmet":
        el(STEEL_D, (x0 - 2, hy - 2, 21, 12)); el(STEEL, (x0 - 2, hy - 2, 20, 11)); el(STEEL_L, (x0 + 1, hy - 1, 7, 4))
        f(STEEL_D, (x0 - 2, hy + 6, 21, 2))
        if facing == "down":
            f(STEEL_D, (15, hy + 6, 2, 5))
        f(hair, (x0 - 1, hy + 8, 3, 4))
        poly(acc, [(15, hy - 2), (18, hy - 2), (22, hy - 7), (16, hy - 6)])        # plume
        f(_hi(acc, 1.2), (16, hy - 5, 3, 1))
        return
    if style == "hat":
        f(hair, (x0, hy + 6, 3, 6)); f(hair, (x0 + 15, hy + 6, 3, 6))
        el(_shade(acc, 0.8), (x0 - 5, hy + 3, 28, 7)); el(acc, (x0 - 5, hy + 2, 28, 6))
        f(acc, (x0 + 3, hy - 3, 12, 7)); f(_hi(acc, 1.15), (x0 + 4, hy - 3, 4, 2)); f((150, 66, 44), (x0 + 3, hy + 2, 12, 2))
        return
    if style == "wizard":
        hc = lk["top"]
        f(hair, (x0 - 1, hy + 5, 4, 12)); f(hair, (x0 + 15, hy + 5, 4, 12) if not side else (x0, hy + 5, 5, 12))
        poly(_shade(hc, 0.8), [(x0 + 1, hy + 4), (x0 + 17, hy + 4), (x0 + 12, hy - 6), (x0 + 8, hy - 6)])
        poly(hc, [(x0 + 2, hy + 3), (x0 + 16, hy + 3), (x0 + 11, hy - 6), (x0 + 8, hy - 6)])
        poly(hc, [(x0 + 11, hy - 6), (x0 + 18, hy - 4), (x0 + 16, hy - 2), (x0 + 10, hy - 4)])   # floppy tip
        f(GOLD, (x0 + 17, hy - 4, 2, 2))
        el(_shade(hc, 0.7), (x0 - 4, hy + 2, 26, 6)); el(hc, (x0 - 4, hy + 1, 26, 5))
        f(GOLD, (x0 + 2, hy + 1, 14, 2))
        f(GOLD, (x0 + 7, hy - 2, 1, 1)); f(GOLD, (x0 + 11, hy - 4, 1, 1))
        return
    if style == "bald":
        el(_hi(skin, 1.12), (x0 + 4, hy + 1, 6, 3))
        f(hair, (x0, hy + 6, 3, 6)); f(hair, (x0 + 15, hy + 6, 3, 6))
        if facing == "up":
            f(hair, (x0 + 1, hy + 8, 16, 5))
        return
    # hair you can actually see
    if facing == "up":
        el(hair, (x0 - 1, hy - 1, 20, 17)); el(hair_l, (x0 + 3, hy, 8, 4)); f(hair_d, (x0 + 1, hy + 12, 16, 3))
        if style == "bun":
            pygame.draw.circle(s, hair, (16, hy - 1), 4); pygame.draw.circle(s, hair_d, (16, hy + 4), 3)
        elif style == "braid":
            for i in range(6):
                f(hair if i % 2 else hair_d, (14, hy + 14 + i * 2, 4, 2))
            f(acc, (14, hy + 26, 4, 2))
        elif style == "messy":
            for x in (8, 12, 17, 22):
                poly(hair, [(x - 2, hy + 1), (x + 2, hy + 1), (x, hy - 3)])
        return
    el(hair, (x0 - 1, hy - 2, 20 if not side else 18, 10))
    el(hair_l, (x0 + 3, hy - 1, 7, 3))
    if side:
        f(hair, (x0, hy + 2, 6, 9)); f(hair_d, (x0, hy + 8, 5, 3))
    else:
        f(hair, (x0 - 1, hy + 2, 3, 8)); f(hair, (x0 + 16, hy + 2, 3, 7))
        poly(hair, [(x0 + 3, hy + 3), (x0 + 10, hy + 3), (x0 + 6, hy + 6)])          # fringe
        f(hair_d, (x0 + 1, hy + 4, 16, 1))
    if style == "bun":
        pygame.draw.circle(s, hair, (16 if not side else 11, hy - 2), 4)
        pygame.draw.circle(s, hair_l, (15 if not side else 10, hy - 3), 1)
    elif style == "braid":
        bx = 25 if not side else 10
        for i in range(7):
            f(hair if i % 2 else hair_d, (bx, hy + 8 + i * 2, 3, 2))
        f(acc, (bx, hy + 22, 3, 2))
    elif style == "messy":
        for x in (8, 11, 15, 19, 23) if not side else (10, 14, 18, 22):
            poly(hair, [(x - 2, hy), (x + 2, hy), (x, hy - 4)])
    elif style == "short" and not side:
        f(hair, (x0 + 15, hy + 2, 3, 4))


def _held_hd(s, lk, held, facing, H, bt, front):
    f = s.fill
    acc = lk["acc"]
    x = 26 if facing != "side" else 24
    if held == "staff":
        f(WOOD, (x, TOP + 4, 2, H - TOP - 4)); f(WOOD_D, (x + 1, TOP + 4, 1, H - TOP - 4))
        pygame.draw.circle(s, _shade(acc, 0.7), (x + 1, TOP + 3), 4)
        pygame.draw.circle(s, acc, (x + 1, TOP + 3), 3)
        f((255, 255, 255), (x, TOP + 1, 1, 2))
    elif held == "spear":
        f(WOOD, (x, TOP + 6, 2, H - TOP - 6))
        pygame.draw.polygon(s, STEEL, [(x - 1, TOP + 7), (x + 3, TOP + 7), (x + 1, TOP - 2)])
        f(STEEL_L, (x, TOP, 1, 5)); f(acc, (x - 1, TOP + 8, 4, 2))
    elif held == "sword":
        top = bt - 6
        f(STEEL_D, (x, top, 3, H - top - 14)); f(STEEL_L, (x, top, 1, H - top - 15))
        f(GOLD, (x - 2, H - 14, 7, 2)); f(WOOD_D, (x, H - 12, 3, 4)); f(GOLD, (x, H - 8, 3, 2))
    elif held == "bow":
        pygame.draw.arc(s, WOOD_D, (x - 5, TOP + 6, 9, H - TOP - 12), -1.5, 1.5, 2)
        pygame.draw.line(s, (230, 226, 210), (x - 1, TOP + 7), (x - 1, H - 7), 1)
    elif held == "pitchfork":
        f(WOOD, (x, TOP + 6, 2, H - TOP - 6)); f(STEEL_D, (x - 2, TOP + 5, 6, 2))
        for dx in (-2, 1, 3):
            f(STEEL, (x + dx, TOP - 1, 1, 6))
    elif held == "hammer" and front:
        x = 25
        f(WOOD, (x, bt + 6, 2, 10)); f(STEEL_D, (x - 2, bt + 3, 6, 4)); f(STEEL_L, (x - 2, bt + 3, 2, 1))
    elif held == "basket" and front and facing != "up":
        x = 1 if facing == "down" else 16
        f((176, 126, 64), (x, bt + 9, 8, 6)); f((130, 88, 40), (x, bt + 13, 8, 1))
        f(acc, (x, bt + 8, 8, 2)); f((210, 50, 50), (x + 2, bt + 7, 2, 2)); f((210, 50, 50), (x + 5, bt + 7, 2, 2))
        pygame.draw.arc(s, (130, 88, 40), (x, bt + 3, 8, 10), 0, 3.14, 1)
    elif held == "satchel" and front and facing == "side":
        f((110, 74, 42), (10, bt + 7, 6, 5))
    elif held == "bundle" and front and facing == "down":
        pygame.draw.line(s, (150, 130, 100), (8, bt), (23, bt + 10), 2)


def _bust_hd(lk):
    """128x128 bust portrait; portrait() scales it to 256x256."""
    s = pygame.Surface((128, 128), pygame.SRCALPHA)
    f = s.fill
    el = lambda c, r: pygame.draw.ellipse(s, c, r)
    poly = lambda c, pts: pygame.draw.polygon(s, c, pts)
    skin, hair = lk["skin"], lk["hair"]
    skin_d, skin_dd, skin_l = _shade(skin, 0.82), _shade(skin, 0.68), _hi(skin, 1.08)
    hair_d, hair_l = _shade(hair, 0.7), _hi(hair, 1.25)
    top, acc = lk["top"], lk["acc"]
    top_d, top_l = _shade(top, 0.7), _hi(top, 1.18)
    eye = lk.get("eyes", (40, 30, 30))
    style, extra, held = lk["style"], lk.get("extra"), lk.get("held")
    kid = lk.get("kid", False)
    hx, hy, hw, hh = (34, 30, 60, 64) if kid else (32, 22, 64, 70)       # head box
    cx = hx + hw // 2
    ey = hy + hh * 47 // 100
    mouth = _shade((196, 92, 92), skin[0] / 255)

    # ---------------------------------------------------------------- behind
    if held == "sword":
        x = 108
        f(STEEL_D, (x, 0, 8, 128)); f(STEEL, (x + 1, 0, 5, 128)); f(STEEL_L, (x + 1, 0, 2, 128))
    elif held == "bow":
        pygame.draw.arc(s, WOOD_D, (90, -6, 34, 140), -1.45, 1.45, 6)
        pygame.draw.arc(s, WOOD, (91, -6, 32, 140), -1.45, 1.45, 3)
        pygame.draw.line(s, (232, 228, 214), (104, 0), (104, 128), 1)
    elif held in POLES:
        x = 108
        f(WOOD_D, (x, 0, 7, 128)); f(WOOD, (x + 1, 0, 4, 128))
        if held == "staff":
            pygame.draw.circle(s, _shade(acc, 0.6), (x + 3, 12), 11)
            pygame.draw.circle(s, acc, (x + 3, 12), 9)
            pygame.draw.circle(s, _hi(acc, 1.3), (x + 1, 9), 4)
            f((255, 255, 255), (x, 7, 2, 2))
        elif held == "spear":
            poly(STEEL_D, [(x - 4, 22), (x + 10, 22), (x + 3, 0)]); poly(STEEL, [(x - 2, 20), (x + 8, 20), (x + 3, 2)])
            f(acc, (x - 2, 23, 11, 4))
        else:
            f(STEEL_D, (x - 8, 16, 22, 4))
            for dx in (-7, 2, 11):
                f(STEEL, (x + dx, 0, 3, 18))
    if style == "hood":
        el(_shade(acc, 0.75), (hx - 10, hy - 10, hw + 20, hh + 34))
    if style in ("braid", "bun", "short", "messy") and not kid:
        el(hair_d, (hx - 4, hy + 6, hw + 8, hh - 4))                           # hair behind the head
    if style == "wizard":
        f(hair, (hx - 6, hy + 18, 14, 48)); f(hair, (hx + hw - 8, hy + 18, 14, 48))
        f(_shade(hair, 0.85), (hx - 6, hy + 52, 14, 14)); f(_shade(hair, 0.85), (hx + hw - 8, hy + 52, 14, 14))
    if extra == "cape":
        el(_shade(acc, 0.8), (0, 92, 128, 70))

    # ---------------------------------------------------------------- shoulders and clothes
    el(top_d, (4, 92, 120, 80)); el(top, (8, 94, 112, 76)); el(top_l, (14, 98, 38, 34))
    for x in (40, 86):
        pygame.draw.line(s, _shade(top, 0.82), (x, 108), (x + (6 if x < 64 else -6), 128), 2)   # folds
    f(skin_d, (cx - 11, hy + hh - 8, 22, 22))                                                    # neck
    poly(skin_dd, [(cx - 11, hy + hh + 6), (cx + 11, hy + hh + 6), (cx, hy + hh + 16)])
    poly(_shade(top, 0.6), [(cx - 18, 96), (cx + 18, 96), (cx, 112)])                             # collar shadow
    if extra == "apron":
        f(acc, (cx - 24, 104, 48, 24)); f(_shade(acc, 0.75), (cx - 24, 104, 48, 3))
        f(_shade(acc, 0.7), (cx - 22, 92, 5, 14)); f(_shade(acc, 0.7), (cx + 17, 92, 5, 14))
        f(_shade(acc, 0.85), (cx - 8, 112, 16, 10))
    elif extra == "shawl":
        poly(acc, [(6, 104), (cx - 12, 92), (cx, 112), (cx + 12, 92), (122, 104), (122, 116), (6, 116)])
        poly(_shade(acc, 0.8), [(cx, 112), (cx + 12, 92), (122, 104), (122, 116)])
        pygame.draw.circle(s, GOLD, (cx, 110), 5); pygame.draw.circle(s, _hi(GOLD, 1.2), (cx - 1, 109), 2)
    elif extra == "scarf":
        f(acc, (cx - 30, 90, 60, 12)); f(_shade(acc, 0.75), (cx - 30, 99, 60, 3)); f(acc, (cx + 10, 100, 14, 28))
        for y in (106, 114, 122):
            f(_shade(acc, 0.8), (cx + 10, y, 14, 2))
    elif extra == "armor":
        el(STEEL_D, (-2, 90, 44, 32)); el(STEEL, (0, 90, 40, 28)); el(STEEL_L, (6, 92, 16, 10))
        el(STEEL_D, (86, 90, 44, 32)); el(STEEL, (88, 90, 40, 28)); el(STEEL_L, (94, 92, 16, 10))
        f(STEEL, (cx - 22, 100, 44, 28)); f(STEEL_D, (cx + 14, 100, 8, 28))
        f(acc, (cx - 8, 102, 16, 26)); f(GOLD, (cx - 4, 108, 8, 6))
    elif extra == "cape":
        el(acc, (-6, 96, 34, 40)); el(acc, (100, 96, 34, 40))
        pygame.draw.circle(s, GOLD, (cx - 22, 102), 5); pygame.draw.circle(s, GOLD, (cx + 22, 102), 5)
    elif extra == "stars":
        for x, y in ((20, 110), (34, 122), (98, 112), (108, 124), (cx - 30, 100), (cx + 34, 104)):
            poly(GOLD, [(x, y - 3), (x + 1, y - 1), (x + 3, y), (x + 1, y + 1), (x, y + 3), (x - 1, y + 1), (x - 3, y), (x - 1, y - 1)])
    if held == "satchel":
        pygame.draw.line(s, (110, 74, 42), (14, 96), (110, 128), 6); pygame.draw.line(s, (140, 96, 56), (14, 94), (110, 126), 2)
    if held == "bundle":
        pygame.draw.line(s, (150, 130, 100), (10, 98), (100, 128), 8)
    if held == "basket":
        el((176, 126, 64), (2, 104, 40, 26)); f((130, 88, 40), (2, 112, 40, 3))
        pygame.draw.circle(s, (210, 50, 50), (14, 106), 5); pygame.draw.circle(s, (200, 60, 40), (26, 105), 5)
    if lk.get("soot"):
        f(_shade(top, 0.5), (24, 112, 6, 3)); f(_shade(top, 0.5), (96, 106, 8, 3))

    # ---------------------------------------------------------------- the face
    el(skin_dd, (hx - 1, hy, hw + 2, hh + 2))
    el(skin, (hx, hy, hw - 2, hh - 2))
    poly(skin_d, [(cx + 14, hy + 10), (hx + hw - 2, hy + hh // 2), (cx + 12, hy + hh - 2), (cx + 20, hy + hh // 2)])
    el(skin_l, (hx + 8, hy + 14, 20, 18))
    for x in (hx - 6, hx + hw - 6):                                                    # ears
        el(skin_d, (x, ey - 8, 12, 20)); el(skin_dd, (x + 3, ey - 4, 5, 10))
    for ex in (cx - 17, cx + 5):                                                       # eyes
        el((248, 246, 240), (ex, ey - 4, 13, 9))
        pygame.draw.circle(s, eye, (ex + 7, ey), 4)
        pygame.draw.circle(s, _shade(eye, 0.5), (ex + 7, ey), 2)
        f((255, 255, 255), (ex + 5, ey - 2, 2, 2))
        pygame.draw.arc(s, skin_dd, (ex - 1, ey - 6, 15, 10), 0.2, 2.9, 2)             # upper lid
        brow = hair_d if style != "bald" else skin_dd
        pygame.draw.line(s, brow, (ex, ey - 10), (ex + 12, ey - 11 + (1 if ex < cx else -1)), 3)
    poly(skin_d, [(cx, ey + 2), (cx + 4, ey + 14), (cx - 4, ey + 15)])                   # nose
    f(skin_dd, (cx - 4, ey + 14, 3, 2)); f(skin_dd, (cx + 2, ey + 14, 3, 2))
    pygame.draw.line(s, mouth, (cx - 8, ey + 22), (cx + 8, ey + 22), 3)                 # mouth
    pygame.draw.line(s, _hi(mouth, 1.2), (cx - 5, ey + 24), (cx + 5, ey + 24), 1)
    if lk.get("freckles"):
        for x, y in ((-20, 10), (-15, 13), (-11, 9), (11, 9), (15, 13), (20, 10)):
            f(_shade(skin, 0.78), (cx + x, ey + y, 2, 2))
    elif not lk.get("beard"):
        el(_mix_pink(skin), (cx - 24, ey + 10, 12, 5)); el(_mix_pink(skin), (cx + 12, ey + 10, 12, 5))
    if lk.get("wrinkles"):
        for dy in (0, 4):
            pygame.draw.line(s, skin_dd, (cx - 14, hy + 10 + dy), (cx + 14, hy + 10 + dy), 1)
        pygame.draw.line(s, skin_dd, (cx - 26, ey + 6), (cx - 20, ey + 10), 1)
        pygame.draw.line(s, skin_dd, (cx + 26, ey + 6), (cx + 20, ey + 10), 1)
    if lk.get("stubble"):
        for x in range(cx - 18, cx + 19, 3):
            for y in range(ey + 18, ey + 30, 3):
                if (x + y) % 2 == 0:
                    f(_shade(skin, 0.78), (x, y, 1, 1))
    if lk.get("soot"):
        el(_shade(skin, 0.68), (cx + 12, ey + 8, 8, 5)); el(_shade(skin, 0.72), (hx + 10, hy + 12, 8, 4))
    if lk.get("beard"):
        b = lk["beard"]
        bd = _shade(b, 0.78)
        poly(b, [(hx + 4, ey + 8), (hx + hw - 6, ey + 8), (hx + hw - 10, ey + 30), (cx, ey + 40), (hx + 8, ey + 30)])
        poly(bd, [(cx + 6, ey + 8), (hx + hw - 6, ey + 8), (hx + hw - 10, ey + 30), (cx + 2, ey + 40)])
        poly(b, [(cx - 16, ey + 16), (cx - 2, ey + 14), (cx - 2, ey + 20), (cx - 18, ey + 22)])     # moustache
        poly(b, [(cx + 16, ey + 16), (cx + 2, ey + 14), (cx + 2, ey + 20), (cx + 18, ey + 22)])
        pygame.draw.line(s, mouth, (cx - 6, ey + 23), (cx + 6, ey + 23), 2)
        for i in range(6):
            pygame.draw.line(s, _shade(b, 0.88), (hx + 12 + i * 8, ey + 26), (hx + 14 + i * 8, ey + 34), 1)
        if lk.get("long_beard"):
            poly(b, [(cx - 20, ey + 30), (cx + 20, ey + 30), (cx + 12, 118), (cx, 128), (cx - 12, 118)])
            poly(bd, [(cx + 4, ey + 30), (cx + 20, ey + 30), (cx + 12, 118), (cx, 128)])
            for y in range(ey + 36, 124, 7):
                pygame.draw.line(s, _shade(b, 0.86), (cx - 8, y), (cx - 2, y + 4), 1)
                pygame.draw.line(s, _shade(b, 0.86), (cx + 3, y + 2), (cx + 8, y + 6), 1)

    # ---------------------------------------------------------------- hair / headwear in front
    if style in ("short", "bun", "braid", "messy"):
        el(hair, (hx - 4, hy - 6, hw + 8, 30))
        f(hair, (hx - 4, hy + 8, 10, 28 if style != "braid" else 44)); f(hair, (hx + hw - 6, hy + 8, 10, 26))
        el(hair_l, (hx + 8, hy - 3, 26, 9))
        for i in range(6):                                                          # strands
            x = hx + 6 + i * 9
            pygame.draw.line(s, hair_d, (x, hy + 2), (x + 4, hy + 18), 1)
        poly(hair, [(hx + 10, hy + 14), (cx + 6, hy + 14), (hx + 20, hy + 26)])           # fringe
        poly(hair, [(cx + 2, hy + 14), (hx + hw - 6, hy + 14), (hx + hw - 10, hy + 24)])
        if style == "bun":
            pygame.draw.circle(s, hair_d, (cx, hy - 8), 13); pygame.draw.circle(s, hair, (cx, hy - 9), 11)
            pygame.draw.circle(s, hair_l, (cx - 4, hy - 13), 4)
        elif style == "braid":
            for i in range(8):
                el(hair if i % 2 else hair_d, (hx + hw - 2, hy + 30 + i * 10, 14, 12))
            f(acc, (hx + hw, hy + 112 - 30, 10, 5))
        elif style == "messy":
            for x, h in ((-2, 10), (10, 14), (24, 12), (38, 15), (52, 11), (64, 9)):
                poly(hair, [(hx + x - 6, hy + 2), (hx + x + 6, hy + 2), (hx + x, hy - h)])
    elif style == "bald":
        el(_hi(skin, 1.14), (cx - 14, hy + 2, 20, 8))
        f(hair, (hx - 4, ey - 8, 10, 18)); f(hair, (hx + hw - 6, ey - 8, 10, 18))
    elif style == "hood":
        el(acc, (hx - 10, hy - 12, hw + 20, 44)); el(_hi(acc, 1.15), (hx + 4, hy - 9, 30, 9))
        f(acc, (hx - 10, hy + 10, 14, 60)); f(acc, (hx + hw - 4, hy + 10, 14, 60))
        f(_shade(acc, 0.7), (hx + 3, hy + 12, 3, 52)); f(_shade(acc, 0.7), (hx + hw - 6, hy + 12, 3, 52))
        f(hair, (hx + 6, hy + 14, hw - 12, 6)); f(hair, (hx + 6, hy + 18, 10, 10))
    elif style == "helmet":
        f(hair, (hx - 4, ey - 8, 10, 22)); f(hair, (hx + hw - 6, ey - 8, 10, 22))
        el(STEEL_D, (hx - 8, hy - 12, hw + 16, 48)); el(STEEL, (hx - 8, hy - 12, hw + 14, 44))
        el(STEEL_L, (hx + 2, hy - 8, 22, 12))
        f(STEEL_D, (hx - 8, hy + 22, hw + 16, 8)); f(STEEL_L, (hx - 8, hy + 22, hw + 16, 2))
        f(STEEL_D, (cx - 4, hy + 24, 8, 26)); f(STEEL, (cx - 2, hy + 24, 3, 24))
        for x in range(hx - 4, hx + hw + 6, 10):
            pygame.draw.circle(s, STEEL_L, (x, hy + 26), 2)
        poly(acc, [(cx - 6, hy - 10), (cx + 6, hy - 10), (cx + 26, hy - 30), (cx + 2, hy - 24)])      # plume
        poly(_hi(acc, 1.2), [(cx, hy - 12), (cx + 4, hy - 12), (cx + 20, hy - 26)])
    elif style == "hat":
        f(hair, (hx - 4, ey - 10, 10, 20)); f(hair, (hx + hw - 6, ey - 10, 10, 20))
        el(_shade(acc, 0.7), (hx - 22, hy + 4, hw + 44, 20)); el(acc, (hx - 22, hy + 2, hw + 44, 18))
        f(acc, (hx + 8, hy - 18, hw - 16, 26)); el(acc, (hx + 8, hy - 24, hw - 16, 12))
        f(_hi(acc, 1.12), (hx + 12, hy - 18, 12, 20)); f((150, 66, 44), (hx + 8, hy + 2, hw - 16, 6))
    elif style == "wizard":
        hc = top
        poly(_shade(hc, 0.75), [(hx - 2, hy + 10), (hx + hw + 2, hy + 10), (cx + 14, 0), (cx - 4, 0)])
        poly(hc, [(hx + 2, hy + 8), (hx + hw - 2, hy + 8), (cx + 12, 0), (cx - 2, 0)])
        poly(hc, [(cx + 10, 0), (cx + 40, 6), (cx + 34, 14), (cx + 8, 8)])                          # flop
        pygame.draw.circle(s, GOLD, (cx + 38, 10), 4)
        el(_shade(hc, 0.6), (hx - 22, hy + 4, hw + 44, 18)); el(hc, (hx - 22, hy + 2, hw + 44, 16))
        el(_hi(hc, 1.25), (hx - 10, hy + 3, 40, 6))
        f(GOLD, (hx + 2, hy + 2, hw - 4, 5)); f(_hi(GOLD, 1.2), (hx + 2, hy + 2, hw - 4, 1))
        for x, y in ((cx - 10, hy - 10), (cx + 6, hy - 4), (cx + 2, 6)):
            poly(GOLD, [(x, y - 3), (x + 1, y - 1), (x + 3, y), (x + 1, y + 1), (x, y + 3), (x - 1, y + 1), (x - 3, y), (x - 1, y - 1)])
    return s
