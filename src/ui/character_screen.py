"""
character_screen.py - The hero's gear, bag and stats in one window (I key). The game pauses.

    screen = CharacterScreen(save, pc, portrait, on_change=..., play=sfx.play)
    result = screen.handle_event(event)        # CLOSE when the player leaves
    screen.update(dt); screen.draw(surface)

LEFT:   stats (HP, attack, defense, attack speed, ...) and the stat points to spend
MIDDLE: what the hero wears: helmet, armor, boots, weapon, trinket
RIGHT:  the bag (24 slots) and the details of the item under the cursor, compared with
        what is worn in that slot

Mouse: click a bag item to wear it, a worn item to take it off, [+] to spend a point,
right-click a bag item to sell it. Keys: arrows move, Tab switches area, Enter uses,
X sells, R gives back every stat point, Esc / I closes.

`on_change()` is called after anything changes, so the game can re-apply the stats and save.
"""
import math

import pygame

from . import theme, widgets
from .assets import get_font
from .gear_icons import draw_item_slot
from .text import draw_text, text_width
from inventory.gear import (ATTRS, BAG_SIZE, SLOTS, SLOT_NAMES, STAT_ORDER, attr_text, format_stat)

CLOSE = "close"

W, H = 1152, 648
PANEL = pygame.Rect(30, 26, 1092, 596)
STATS_BOX = pygame.Rect(54, 92, 330, 500)
EQUIP_BOX = pygame.Rect(400, 92, 290, 500)
BAG_BOX = pygame.Rect(706, 92, 392, 500)
CELL, GAP, COLS = 54, 9, 6
BAG_X, BAG_Y = BAG_BOX.x + 14, BAG_BOX.y + 40
EQ_SIZE = 62
# where each worn slot sits around the hero picture
EQ_POS = {"helmet": (EQUIP_BOX.x + 20, EQUIP_BOX.y + 70), "armor": (EQUIP_BOX.x + 20, EQUIP_BOX.y + 170),
          "boots": (EQUIP_BOX.x + 20, EQUIP_BOX.y + 270), "weapon": (EQUIP_BOX.right - 20 - EQ_SIZE, EQUIP_BOX.y + 70),
          "trinket": (EQUIP_BOX.right - 20 - EQ_SIZE, EQUIP_BOX.y + 170)}
ATTR_Y = STATS_BOX.y + 296
ATTR_ROW = 36
FOCI = ("bag", "equip", "attrs")


class CharacterScreen:
    def __init__(self, save, pc, portrait=None, on_change=None, play=None, toggle_key="i"):
        self.save, self.pc = save, pc
        self.gear = save.gear
        self.portrait = portrait
        self.on_change = on_change or (lambda: None)
        self.play = play or (lambda name: None)
        self.toggle_key = toggle_key
        self.focus = "bag"
        self.index = {"bag": 0, "equip": 0, "attrs": 0}
        self.hover = None              # (focus, index) under the mouse
        self.msg, self.msg_col, self.msg_t = "", theme.TEXT, 0.0
        self.sell_armed = None         # bag index waiting for a second X (Rare and better)
        self.time = 0.0
        self.resource = "Mana" if pc.resource == "mana" else "Energy"

    # ------------------------------------------------------------------ helpers
    def _say(self, text, col=theme.TEXT):
        self.msg, self.msg_col, self.msg_t = text, col, 2.6

    def _changed(self):
        self.on_change()

    def selected_item(self):
        """The item whose details are shown: under the mouse, else the keyboard selection."""
        focus, i = self.hover if self.hover else (self.focus, self.index[self.focus])
        if focus == "bag":
            return self.gear.bag[i] if i < len(self.gear.bag) else None
        if focus == "equip":
            return self.gear.equipped[SLOTS[i]]
        return None

    # ------------------------------------------------------------------ actions
    def use_bag(self, i):
        if i >= len(self.gear.bag):
            return
        item = self.gear.bag[i]
        if not self.gear.can_equip(item):
            self._say("Only a %s can use that." % item.hero_class.title(), (255, 140, 120))
            self.play("blip")
            return
        self.gear.equip(i)
        self.sell_armed = None
        self._say("Equipped %s." % item.name, item.color)
        self.play("equip")
        self._changed()

    def use_equip(self, i):
        slot = SLOTS[i]
        item = self.gear.equipped[slot]
        if item is None:
            return
        if not self.gear.unequip(slot):
            self._say("Your bag is full.", (255, 140, 120))
            self.play("blip")
            return
        self._say("Took off %s." % item.name)
        self.play("equip")
        self._changed()

    def sell(self, i):
        if i >= len(self.gear.bag):
            return
        item = self.gear.bag[i]
        if item.rarity >= 2 and self.sell_armed != i:
            self.sell_armed = i
            self._say("Sell %s for %d gold?  Press X again." % (item.name, item.sell_value), (255, 214, 120))
            return
        self.sell_armed = None
        gold = self.gear.sell(i)
        self.save.gold += gold
        self._say("Sold %s for %d gold." % (item.name, gold), (255, 226, 130))
        self.play("sell")
        self.index["bag"] = min(self.index["bag"], max(0, len(self.gear.bag) - 1))
        self._changed()

    def spend(self, i):
        aid, name, _per = ATTRS[i]
        if self.save.spend_point(aid):
            self._say("+1 %s" % name, (150, 220, 255))
            self.play("ui_select")
            self._changed()
        else:
            self._say("No stat points left. Level up to earn more.", (255, 140, 120))
            self.play("no_mana")

    def reset_points(self):
        if not self.save.alloc:
            return
        self.save.reset_points()
        self._say("Stat points given back. Spend them again.", (150, 220, 255))
        self.play("ui_back")
        self._changed()

    def activate(self):
        i = self.index[self.focus]
        {"bag": self.use_bag, "equip": self.use_equip, "attrs": self.spend}[self.focus](i)

    # ------------------------------------------------------------------ layout
    def bag_rect(self, i):
        r, c = divmod(i, COLS)
        return pygame.Rect(BAG_X + c * (CELL + GAP), BAG_Y + r * (CELL + GAP), CELL, CELL)

    def eq_rect(self, i):
        x, y = EQ_POS[SLOTS[i]]
        return pygame.Rect(x, y, EQ_SIZE, EQ_SIZE)

    def plus_rect(self, i):
        return pygame.Rect(STATS_BOX.right - 46, ATTR_Y + i * ATTR_ROW + 1, 28, 19)

    def _hit(self, pos):
        for i in range(BAG_SIZE):
            if self.bag_rect(i).collidepoint(pos):
                return "bag", i
        for i in range(len(SLOTS)):
            if self.eq_rect(i).collidepoint(pos):
                return "equip", i
        for i in range(len(ATTRS)):
            if self.plus_rect(i).inflate(8, 8).collidepoint(pos):
                return "attrs", i
        return None

    # ------------------------------------------------------------------ input
    def move(self, dx, dy):
        f = self.focus
        i = self.index[f]
        if f == "bag":
            r, c = divmod(i, COLS)
            c, r = (c + dx) % COLS, (r + dy) % (BAG_SIZE // COLS)
            self.index[f] = r * COLS + c
        elif f == "equip":
            self.index[f] = (i + dy + dx) % len(SLOTS)
        else:
            self.index[f] = (i + dy) % len(ATTRS)
        self.hover = None
        self.play("ui_move")

    def handle_event(self, event):
        if event.type == pygame.KEYDOWN:
            k = event.key
            if k == pygame.K_ESCAPE or pygame.key.name(k) == self.toggle_key:
                self.play("ui_back")
                return CLOSE
            if k == pygame.K_TAB:
                step = -1 if event.mod & pygame.KMOD_SHIFT else 1
                self.focus = FOCI[(FOCI.index(self.focus) + step) % len(FOCI)]
                self.hover = None
                self.play("ui_move")
            elif k in (pygame.K_LEFT, pygame.K_a):
                self.move(-1, 0)
            elif k in (pygame.K_RIGHT, pygame.K_d):
                self.move(1, 0)
            elif k in (pygame.K_UP, pygame.K_w):
                self.move(0, -1)
            elif k in (pygame.K_DOWN, pygame.K_s):
                self.move(0, 1)
            elif k in (pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_SPACE, pygame.K_e):
                self.activate()
            elif k == pygame.K_x and self.focus == "bag":
                self.sell(self.index["bag"])
            elif k == pygame.K_r:
                self.reset_points()
        elif event.type == pygame.MOUSEMOTION:
            self.hover = self._hit(event.pos)
            if self.hover:
                self.focus, self.index[self.hover[0]] = self.hover
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button in (1, 3):
            hit = self._hit(event.pos)
            if hit is None:
                if event.button == 1 and not PANEL.collidepoint(event.pos):
                    return CLOSE
                return None
            self.focus, self.index[hit[0]] = hit
            if event.button == 3:
                if hit[0] == "bag":
                    self.sell(hit[1])
            else:
                self.activate()
        return None

    def update(self, dt):
        self.time += dt
        if self.msg_t > 0:
            self.msg_t -= dt

    # ------------------------------------------------------------------ drawing
    def stat_rows(self):
        """[(label, value text)] of the hero's current stats (everything applied)."""
        pc = self.pc
        bar = pc.pools.bars.get(pc.resource, [0, 0, 0])
        cut = 100 - 100 * 20 / (20 + max(0, pc.defense))
        return [
            ("Max HP", "%d" % pc.max_hp),
            ("Attack", "%.1f" % pc.attack_power),
            ("Defense", "%d  (-%d%% dmg)" % (pc.defense, round(cut))),
            ("Attack Speed", "%.2f / s" % (1.0 / pc.swing_cd)),
            ("Move Speed", "%d%%" % round(pc.speed_k * 100)),
            ("Crit Chance", "%d%%" % round(pc.crit)),
            ("Max " + self.resource, "%d" % bar[1]),
            (self.resource + " Regen", "%.1f / s" % bar[2]),
        ]

    def draw(self, surface):
        widgets.dim(surface, 170)
        widgets.stone_panel(surface, PANEL)
        widgets.title_plate(surface, (PANEL.centerx, PANEL.y + 4), "CHARACTER")
        self._draw_stats(surface)
        self._draw_equip(surface)
        self._draw_bag(surface)
        hint = "CLICK / ENTER: WEAR   RIGHT-CLICK / X: SELL   TAB: SWITCH   R: RESET POINTS   ESC / I: CLOSE"
        font = get_font(theme.FONT_SMALL)
        draw_text(surface, hint, font, theme.TEXT_DIM, (PANEL.centerx - text_width(font, hint) // 2, PANEL.bottom - 26),
                  outline=1, shadow=False)

    def _box(self, surface, rect, title, active):
        pygame.draw.rect(surface, theme.OUTLINE, rect.inflate(4, 4))
        pygame.draw.rect(surface, theme.STONE_DARK, rect)
        pygame.draw.rect(surface, theme.BRASS if active else theme.WOOD_DARK, rect, 2)
        draw_text(surface, title, get_font(theme.FONT_LABEL), theme.TITLE, (rect.x + 14, rect.y + 6), outline=2)

    def _draw_stats(self, surface):
        r = STATS_BOX
        self._box(surface, r, "STATS", self.focus == "attrs")
        s = self.save
        label = get_font(theme.FONT_HUD)
        small = get_font(theme.FONT_SMALL)
        draw_text(surface, "%s  -  LV %d %s" % (s.hero_name, s.level, self.pc.class_name.upper()), small,
                  (170, 220, 255), (r.x + 16, r.y + 42), outline=1, shadow=False)
        y = r.y + 64
        for name, value in self.stat_rows():
            draw_text(surface, name, label, theme.TEXT_DIM, (r.x + 16, y), outline=1, shadow=False)
            draw_text(surface, value, label, theme.TEXT, (r.right - 16 - text_width(label, value), y), outline=1,
                      shadow=False)
            y += 26
        pts = s.stat_points
        head = "STAT POINTS: %d" % pts
        col = theme.TORCH_LIGHT if pts and int(self.time * 3) % 2 == 0 else (theme.TORCH if pts else theme.TEXT_DIM)
        draw_text(surface, head, label, col, (r.x + 16, ATTR_Y - 28), outline=2)
        for i, (aid, name, _per) in enumerate(ATTRS):
            y = ATTR_Y + i * ATTR_ROW
            sel = self.focus == "attrs" and self.index["attrs"] == i
            if sel:
                pygame.draw.rect(surface, theme.STONE, (r.x + 8, y, r.w - 16, ATTR_ROW - 2))
                pygame.draw.rect(surface, theme.BRASS, (r.x + 8, y, 3, ATTR_ROW - 2))
            n = s.alloc.get(aid, 0)
            draw_text(surface, "%s  %d" % (name, n), label, theme.TEXT, (r.x + 18, y + 2), outline=1, shadow=False)
            draw_text(surface, attr_text(aid, self.resource), small, theme.TEXT_DIM, (r.x + 18, y + 22),
                      outline=1, shadow=False)
            pr = self.plus_rect(i)
            ok = pts > 0
            pygame.draw.rect(surface, theme.OUTLINE, pr.inflate(4, 4))
            pygame.draw.rect(surface, theme.TORCH if ok else theme.WOOD_DARK, pr)
            draw_text(surface, "+", label, theme.TEXT if ok else theme.TEXT_DIM, pr.center, outline=2, center=True)

    def _draw_equip(self, surface):
        r = EQUIP_BOX
        self._box(surface, r, "EQUIPMENT", self.focus == "equip")
        if self.portrait is not None:
            img = self.portrait
            box = pygame.Rect(r.centerx - 48, r.y + 70, 96, 250)
            k = min(box.w / img.get_width(), box.h / img.get_height())
            if k >= 1:
                k = int(k)
                img = pygame.transform.scale(img, (int(img.get_width() * k), int(img.get_height() * k)))
            else:
                img = pygame.transform.smoothscale(img, (int(img.get_width() * k), int(img.get_height() * k)))
            surface.blit(img, img.get_rect(midbottom=box.midbottom))
        small = get_font(theme.FONT_SMALL)
        for i, slot in enumerate(SLOTS):
            rect = self.eq_rect(i)
            sel = self.focus == "equip" and self.index["equip"] == i
            draw_item_slot(surface, rect, self.gear.equipped[slot], sel, empty_label=SLOT_NAMES[slot][:4].upper())
            draw_text(surface, SLOT_NAMES[slot].upper(), small, theme.TEXT_DIM,
                      (rect.centerx - text_width(small, SLOT_NAMES[slot].upper()) // 2, rect.bottom + 6),
                      outline=1, shadow=False)
        # gold under the picture
        label = get_font(theme.FONT_HUD)
        g = "%d gold" % self.save.gold
        gy = r.bottom - 44
        pygame.draw.circle(surface, (90, 60, 10), (r.centerx - text_width(label, g) // 2 - 14, gy + 14), 9)
        pygame.draw.circle(surface, (240, 196, 70), (r.centerx - text_width(label, g) // 2 - 14, gy + 13), 7)
        draw_text(surface, g, label, (255, 226, 130), (r.centerx - text_width(label, g) // 2, gy), outline=2)

    def _draw_bag(self, surface):
        r = BAG_BOX
        self._box(surface, r, "BAG  %d / %d" % (len(self.gear.bag), BAG_SIZE), self.focus == "bag")
        for i in range(BAG_SIZE):
            item = self.gear.bag[i] if i < len(self.gear.bag) else None
            sel = self.focus == "bag" and self.index["bag"] == i
            draw_item_slot(surface, self.bag_rect(i), item, sel,
                           dim=item is not None and not self.gear.can_equip(item))
        self._draw_details(surface, pygame.Rect(r.x + 12, BAG_Y + 4 * (CELL + GAP) + 6, r.w - 24, 190))

    def _draw_details(self, surface, box):
        pygame.draw.rect(surface, (22, 18, 18), box)
        pygame.draw.rect(surface, theme.WOOD_DARK, box, 1)
        label = get_font(theme.FONT_HUD)
        small = get_font(theme.FONT_SMALL)
        item = self.selected_item()
        x, y = box.x + 12, box.y + 8
        if self.msg_t > 0:
            draw_text(surface, self.msg, small, self.msg_col, (x, box.bottom - 22), outline=1, shadow=False)
        if item is None:
            draw_text(surface, "Point at an item to see it.", small, theme.TEXT_DIM, (x, y + 4), outline=1,
                      shadow=False)
            return
        draw_text(surface, item.name, label, item.color, (x, y), outline=2)
        who = "Any hero" if item.hero_class is None else item.hero_class.title() + " only"
        sub = "%s  -  Tier %d  -  %s" % (SLOT_NAMES[item.slot], item.tier, who)
        ok = self.gear.can_equip(item)
        draw_text(surface, sub, small, theme.TEXT_DIM if ok else (255, 130, 110), (x, y + 30), outline=1, shadow=False)
        worn = self.gear.equipped.get(item.slot) is item
        diff = {} if worn else self.gear.compare(item)
        stats = item.stats
        yy = y + 52
        for k in STAT_ORDER:
            if k not in stats and k not in diff:
                continue
            num, name = format_stat(k, stats.get(k, 0), self.resource)
            draw_text(surface, "%s %s" % (num, name), small, theme.TEXT, (x, yy), outline=1, shadow=False)
            d = diff.get(k, 0)
            if d:
                dn, _ = format_stat(k, d, self.resource)
                draw_text(surface, dn, small, (120, 230, 120) if d > 0 else (240, 110, 100),
                          (box.right - 14 - text_width(small, dn), yy), outline=1, shadow=False)
            yy += 18
        tail = "WORN" if worn else "Sells for %d gold" % item.sell_value
        draw_text(surface, tail, small, (255, 226, 130) if not worn else (150, 220, 255),
                  (box.right - 14 - text_width(small, tail), box.bottom - 42), outline=1, shadow=False)
