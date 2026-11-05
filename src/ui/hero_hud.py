"""
hero_hud.py - The hero's panel in the game: portrait, name, level, HP and the class bars
(Mage: Mana + Stamina, Warrior / Archer: Stamina + Energy), potions, and the skill bar.

    hud = HeroHUD()
    hud.update(dt, pc)                       # pc = the game's PlayerCombat
    bottom = hud.draw(screen, x, y, pc, name="Aria", level=3, xp=(40, 90), portrait=surface)
    hud.draw_skills(screen, centre_x, bottom_y, pc, keys={"skill": "K", ...})

It only SHOWS numbers; the game owns them. Bars drain with the same pale "ghost" piece as
the team's HUD (hud.StatBar).
"""
import math

import pygame

from . import theme
from .assets import get_font, get_image, nine_slice
from .hud import StatBar, HEART, DIAMOND, _lighter

try:
    from skills.classes import BAR_COLORS, DASH_STAMINA
except ImportError:          # the UI can still be previewed without the skills package
    DASH_STAMINA = 25
    BAR_COLORS = {"hp": (214, 52, 52), "stamina": (226, 190, 60), "mana": (70, 120, 236),
                  "energy": (236, 128, 40)}

BOLT = [
    "....oo..",
    "...oXo..",
    "..oXo...",
    ".oXXXXo.",
    "..oXXo..",
    "..oXo...",
    ".oXo....",
    ".oo.....",
]
ICONS = {"hp": HEART, "stamina": BOLT, "mana": DIAMOND, "energy": DIAMOND}
LABELS = {"hp": "HP", "stamina": "STAMINA", "mana": "MANA", "energy": "ENERGY"}

PANEL_W, PANEL_H = 360, 136
PORTRAIT = 76
BAR_W = 236
SLOT = 58
SLOT_GAP = 10


def _icon(surface, pattern, color, x, y, scale=2):
    colors = {"X": color, "o": (20, 10, 6)}
    for r, row in enumerate(pattern):
        for c, ch in enumerate(row):
            if ch in colors:
                surface.fill(colors[ch], (x + c * scale, y + r * scale, scale, scale))


class HeroHUD:
    def __init__(self):
        self.bars = {}
        self.time = 0.0
        self._frame = None
        self._slot = None
        self._slot_lit = None

    def _bar(self, name):
        b = self.bars.get(name)
        if b is None:
            b = self.bars[name] = StatBar(name, BAR_COLORS.get(name, (200, 200, 200)), ICONS.get(name, DIAMOND))
        return b

    def update(self, dt, pc):
        self.time += dt
        self._bar("hp").set(pc.hp, pc.max_hp)
        for name in pc.pools.order:
            self._bar(name).set(pc.pools.get(name), pc.pools.max(name))
        for b in self.bars.values():
            b.update(dt)

    # ------------------------------------------------------------------ panel
    def draw(self, surface, x, y, pc, name="", level=1, xp=(0, 0), portrait=None, class_name="",
             points=0, shield=0.0):
        """Draws the panel at (x, y). Returns the y just below it.
        points: unspent stat points (a pulsing badge); shield: 0..1 of a barrier left (on the HP bar)."""
        if self._frame is None:
            slot = get_image("slot.png")
            self._frame = nine_slice(slot, PANEL_W, PANEL_H, 14) if slot is not None else False
        if self._frame:
            surface.blit(self._frame, (x, y))
        else:
            pygame.draw.rect(surface, (20, 10, 6), (x - 2, y - 2, PANEL_W + 4, PANEL_H + 4))
            pygame.draw.rect(surface, (74, 36, 18), (x, y, PANEL_W, PANEL_H))

        # portrait
        box = pygame.Rect(x + 14, y + 14, PORTRAIT, PORTRAIT)
        pygame.draw.rect(surface, (14, 10, 10), box.inflate(4, 4))
        pygame.draw.rect(surface, theme.STONE_DARK, box)
        if portrait is not None:
            k = min(box.w / portrait.get_width(), box.h / portrait.get_height())
            img = pygame.transform.smoothscale(portrait, (int(portrait.get_width() * k),
                                                          int(portrait.get_height() * k)))
            surface.blit(img, img.get_rect(midbottom=box.midbottom))
        pygame.draw.rect(surface, theme.BRASS, box.inflate(4, 4), 2)

        # name, class and level + XP
        font = get_font(theme.FONT_HUD)
        small = get_font(theme.FONT_SMALL)
        tx = box.right + 12
        self._text(surface, name or "Hero", font, theme.TITLE, tx, y + 10)
        self._text(surface, f"LV {level}  {class_name.upper()}", small, (170, 220, 255), tx, y + 38)
        if points > 0:                                   # stat points waiting: a badge on the portrait
            badge = small.render(f"+{points}", True, (40, 24, 6))
            br = pygame.Rect(0, 0, badge.get_width() + 10, badge.get_height() + 4)
            br.topright = (box.right + 6, box.y - 6)
            glow = 0.5 + 0.5 * math.sin(pygame.time.get_ticks() / 180)
            pygame.draw.rect(surface, (20, 10, 6), br.inflate(4, 4), border_radius=6)
            pygame.draw.rect(surface, (255, int(190 + 50 * glow), 80), br, border_radius=6)
            surface.blit(badge, badge.get_rect(center=br.center))
        have, need = xp
        xb = pygame.Rect(tx + 150, y + 42, PANEL_W - (tx - x) - 164, 8)
        pygame.draw.rect(surface, (10, 6, 6), xb.inflate(2, 2))
        pygame.draw.rect(surface, (30, 40, 70), xb)
        frac = (have / need) if need else 1.0
        pygame.draw.rect(surface, (120, 190, 255) if need else (255, 214, 120),
                         (xb.x, xb.y, int(xb.w * max(0.0, min(1.0, frac))), xb.h))

        # bars: HP, then the class's two bars
        by = y + 60
        names = ["hp"] + list(pc.pools.order)
        bar_w = PANEL_W - (tx - 4 - x) - 16          # stay inside the wooden frame
        for i, nm in enumerate(names):
            h = 18 if nm == "hp" else 13
            self._draw_bar(surface, self._bar(nm), nm, tx - 4, by, bar_w, h)
            if nm == "hp" and shield > 0:                # a barrier: pale blue over the HP bar
                sw = int((bar_w - 20) * min(1.0, shield))
                layer = pygame.Surface((sw, h), pygame.SRCALPHA)
                layer.fill((150, 210, 255, 120))
                surface.blit(layer, (tx - 4 + 20, by))
                pygame.draw.rect(surface, (210, 240, 255), (tx - 4 + 20, by, sw, h), 2)
            by += h + 6

        # potions (under the portrait)
        px, py = box.x + 6, box.bottom + 12
        pygame.draw.rect(surface, (40, 20, 24), (px + 4, py, 8, 4))
        pygame.draw.ellipse(surface, (20, 10, 10), (px - 1, py + 3, 18, 18))
        pygame.draw.ellipse(surface, (220, 60, 80), (px + 1, py + 5, 14, 14))
        pygame.draw.ellipse(surface, (255, 170, 180), (px + 4, py + 7, 4, 4))
        self._text(surface, f"x{pc.potions}  H", small, theme.TEXT, px + 22, py + 5)
        return y + PANEL_H + 6

    def _draw_bar(self, surface, bar, nm, left, top, w, h):
        _icon(surface, ICONS.get(nm, DIAMOND), bar.color, left - 2, top + (h - 16) // 2)
        left += 20
        w -= 20
        pygame.draw.rect(surface, (20, 10, 6), (left - 2, top - 2, w + 4, h + 4))
        pygame.draw.rect(surface, (32, 26, 22), (left, top, w, h))
        ghost_w = int(w * bar.ghost_fraction())
        fill_w = int(w * bar.fill_fraction())
        if ghost_w > fill_w:
            pygame.draw.rect(surface, (240, 225, 200), (left, top, ghost_w, h))
        if fill_w > 0:
            pygame.draw.rect(surface, bar.color, (left, top, fill_w, h))
            pygame.draw.rect(surface, _lighter(bar.color), (left, top, fill_w, max(2, h // 5)))
        small = get_font(theme.FONT_SMALL)
        label = f"{LABELS.get(nm, nm.upper())} {int(bar.value)}/{int(bar.max_value)}"
        img = small.render(label, False, (255, 255, 255))
        sh = small.render(label, False, (20, 10, 6))
        tx, ty = left + 6, top + (h - img.get_height()) // 2 + 1
        surface.blit(sh, (tx + 1, ty + 1))
        surface.blit(img, (tx, ty))

    @staticmethod
    def _text(surface, text, font, color, x, y):
        surface.blit(font.render(text, False, (20, 10, 6)), (x + 2, y + 2))
        surface.blit(font.render(text, False, color), (x, y))

    # ------------------------------------------------------------------ skill bar
    def draw_skills(self, surface, cx, bottom, pc, keys):
        """Three skill slots (+ dash) centred on cx, sitting on `bottom`."""
        caster, pools = pc.caster, pc.pools
        slots = [(slot, caster.defs[slot]) for slot in ("skill", "skill_2", "special")]
        n = len(slots) + 1
        total = n * SLOT + (n - 1) * SLOT_GAP
        x = cx - total // 2
        y = bottom - SLOT
        small = get_font(theme.FONT_SMALL)
        if self._slot is None:
            s, lit = get_image("slot.png"), get_image("slot_selected.png")
            self._slot = nine_slice(s, SLOT, SLOT, 14) if s is not None else False
            self._slot_lit = nine_slice(lit, SLOT, SLOT, 14) if lit is not None else False
        for i, (slot, d) in enumerate(slots):
            rx = x + i * (SLOT + SLOT_GAP)
            ready = caster.cd[slot] <= 0
            afford = pools.can_spend(caster.resource, d.cost)
            self._slot_box(surface, rx, y, ready and afford, special=slot == "special")
            draw_glyph(surface, d.id, pygame.Rect(rx + 9, y + 9, SLOT - 18, SLOT - 18), d.color)
            if not ready:
                frac = caster.cooldown_fraction(slot)
                shade = pygame.Surface((SLOT - 12, int((SLOT - 12) * frac)), pygame.SRCALPHA)
                shade.fill((0, 0, 0, 170))
                surface.blit(shade, (rx + 6, y + 6 + (SLOT - 12) - shade.get_height()))
                self._text(surface, f"{caster.cd[slot]:.0f}" if caster.cd[slot] >= 1 else
                           f"{caster.cd[slot]:.1f}", get_font(theme.FONT_HUD), theme.TEXT,
                           rx + SLOT // 2 - 8, y + SLOT // 2 - 14)
            elif not afford:
                tint = pygame.Surface((SLOT - 12, SLOT - 12), pygame.SRCALPHA)
                tint.fill((60, 0, 0, 120))
                surface.blit(tint, (rx + 6, y + 6))
            self._key(surface, keys.get(slot, "?"), rx, y)
            cost = small.render(str(d.cost), False, BAR_COLORS.get(caster.resource, (255, 255, 255)))
            surface.blit(cost, (rx + SLOT - cost.get_width() - 5, y + SLOT - cost.get_height() - 3))
        # dash
        rx = x + len(slots) * (SLOT + SLOT_GAP)
        dash_ready = pc.dash_cd <= 0 and pools.can_spend("stamina", DASH_STAMINA)
        self._slot_box(surface, rx, y, dash_ready)
        draw_glyph(surface, "dash", pygame.Rect(rx + 9, y + 9, SLOT - 18, SLOT - 18), BAR_COLORS["stamina"])
        if not dash_ready:
            tint = pygame.Surface((SLOT - 12, SLOT - 12), pygame.SRCALPHA)
            tint.fill((0, 0, 0, 140))
            surface.blit(tint, (rx + 6, y + 6))
        self._key(surface, keys.get("dash", "SHIFT"), rx, y)

    def _slot_box(self, surface, x, y, lit, special=False):
        img = self._slot_lit if lit else self._slot
        if img:
            surface.blit(img, (x, y))
        else:
            pygame.draw.rect(surface, (20, 10, 6), (x - 2, y - 2, SLOT + 4, SLOT + 4))
            pygame.draw.rect(surface, theme.TORCH if lit else (64, 36, 18), (x, y, SLOT, SLOT))
        if special and lit:
            k = 0.5 + 0.5 * math.sin(self.time * 5)
            pygame.draw.rect(surface, (255, int(180 + 60 * k), 80), (x - 3, y - 3, SLOT + 6, SLOT + 6), 2)

    def _key(self, surface, label, x, y):
        small = get_font(theme.FONT_SMALL)
        img = small.render(label, False, (255, 240, 200))
        w = img.get_width() + 8
        pygame.draw.rect(surface, (20, 10, 6), (x - 4, y - 8, w, 16))
        pygame.draw.rect(surface, theme.BRASS, (x - 4, y - 8, w, 16), 1)
        surface.blit(img, (x, y - 7))


def draw_glyph(surface, skill_id, r, color):
    """A small hand-drawn picture of a skill inside rect r."""
    cx, cy = r.center
    R = r.w // 2
    dark = (30, 20, 16)
    if skill_id == "blade_ward":
        pygame.draw.circle(surface, color, (cx, cy), R - 5, 2)
        for i in range(3):
            a = i * 2.09 + 0.4
            bx, by = cx + math.cos(a) * (R - 6), cy + math.sin(a) * (R - 6)
            tx, ty = bx + math.cos(a + 1.57) * 9, by + math.sin(a + 1.57) * 9
            pygame.draw.line(surface, (220, 226, 240), (bx, by), (tx, ty), 4)
        pygame.draw.circle(surface, (178, 40, 46), (cx, cy), 5)
    elif skill_id == "shield_bash":
        pts = [(cx - R + 6, cy - R + 6), (cx + R - 6, cy - R + 6), (cx + R - 6, cy), (cx, cy + R - 3),
               (cx - R + 6, cy)]
        pygame.draw.polygon(surface, dark, pts)
        pygame.draw.polygon(surface, color, [(x * 0.9 + cx * 0.1, y * 0.9 + cy * 0.1) for x, y in pts])
        pygame.draw.line(surface, (178, 40, 46), (cx, cy - R + 9), (cx, cy + R - 9), 4)
    elif skill_id == "earthsplitter":
        pygame.draw.polygon(surface, (120, 80, 50), [(cx, cy + R - 4), (cx - R + 2, cy - R + 4), (cx + R - 2, cy - R + 4)])
        for dx in (-9, 0, 9):
            pygame.draw.line(surface, dark, (cx, cy + R - 6), (cx + dx, cy - R + 8), 3)
        pygame.draw.circle(surface, color, (cx, cy + R - 6), 5)
    elif skill_id in ("fireball", "meteor"):
        if skill_id == "meteor":
            pygame.draw.line(surface, (255, 200, 120), (cx + R - 4, cy - R + 4), (cx, cy), 6)
        pygame.draw.circle(surface, (150, 40, 20), (cx - 2, cy + 2), R - 6)
        pygame.draw.circle(surface, color, (cx - 2, cy + 2), R - 9)
        pygame.draw.circle(surface, (255, 240, 180), (cx - 5, cy - 1), R // 3)
    elif skill_id == "arcane_barrier":
        pygame.draw.circle(surface, (40, 60, 110), (cx, cy), R - 4)
        pygame.draw.circle(surface, color, (cx, cy), R - 4, 3)
        pygame.draw.circle(surface, (240, 250, 255), (cx, cy), R - 10, 1)
        for i in range(6):
            a = i * math.pi / 3
            pygame.draw.circle(surface, (240, 250, 255), (int(cx + math.cos(a) * (R - 10)),
                                                          int(cy + math.sin(a) * (R - 10))), 2)
    elif skill_id in ("arrow_volley", "piercing_shot", "rain_of_arrows", "dash"):
        if skill_id == "dash":
            for i, dy in enumerate((-8, 0, 8)):
                pygame.draw.line(surface, color, (cx - R + 4 + i * 3, cy + dy), (cx + R - 10, cy + dy), 3)
            pygame.draw.polygon(surface, color, [(cx + R - 12, cy - 12), (cx + R - 2, cy), (cx + R - 12, cy + 12)])
            return
        if skill_id == "rain_of_arrows":
            arrows = [((cx + dx, cy - R + 4), (cx + dx, cy + R - 6)) for dx in (-10, 0, 10)]
        elif skill_id == "arrow_volley":
            arrows = [((cx - R + 4, cy + dy * 2), (cx + R - 4, cy + dy)) for dy in (-7, 0, 7)]
        else:
            arrows = [((cx - R + 2, cy + R - 4), (cx + R - 2, cy - R + 4))]
            pygame.draw.line(surface, color, arrows[0][0], arrows[0][1], 7)
        for a, b in arrows:
            pygame.draw.line(surface, (140, 96, 56), a, b, 3)
            ang = math.atan2(b[1] - a[1], b[0] - a[0])
            tip = [b, (b[0] - math.cos(ang - 0.5) * 8, b[1] - math.sin(ang - 0.5) * 8),
                   (b[0] - math.cos(ang + 0.5) * 8, b[1] - math.sin(ang + 0.5) * 8)]
            pygame.draw.polygon(surface, (230, 232, 240), tip)
    else:
        pygame.draw.circle(surface, color, (cx, cy), R - 4)
