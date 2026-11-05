"""
shop.py - keyboard shop overlay for Oakwood's merchants.

    menu = ShopMenu("torvin", save, pc, sfx)
    menu.handle_key(key)   -> False once the player leaves the shop
    menu.update(dt); menu.draw(screen, t)

Purchases change the SaveState and are pushed onto PlayerCombat with
save.apply_to(pc), so combat code never needs to know about the shop.

Torvin's Forge has two tabs (A / D or Left / Right): Upgrades, and Gear for the hero's
class (inventory.gear.shop_stock: better pieces after every dungeon). Gear goes into the
bag; wear it from the character screen (I).
"""
from __future__ import annotations

import math

import pygame

try:
    from . import combat as _combat       # POTION_MAX is read live (the config file can change it)
except ImportError:                       # running from inside src/maps
    import combat as _combat

from inventory.gear import Item, shop_stock, format_stat, STAT_ORDER     # combat.py put src/ on the path
from ui.gear_icons import item_icon

GEAR_ROWS = 5                             # gear rows visible at once (the list scrolls)

CATALOG = {
    "torvin": {
        "title": "Torvin's Forge",
        "greet": "Steel doesn't care who you are. It only cares how sharp it is.",
        "color": (232, 150, 70),
        "gear": True,                     # second tab: weapons and armor for the hero
        "items": [
            dict(id="sword", name="Sharpened Steel", desc="+1 sword damage per level",
                 attr="sword_lv", prices=(60, 140, 260)),
            dict(id="armor", name="Riveted Armor", desc="+8 max HP per level",
                 attr="armor_lv", prices=(50, 120, 220)),
            dict(id="boots", name="Windstep Boots", desc="Dash recharges 25% faster per level",
                 attr="boots_lv", prices=(90, 200)),
        ],
    },
    "wren": {
        "title": "Wren's Remedies",
        "greet": "Drink the red ones. Never the green ones. Trust me.",
        "color": (120, 210, 130),
        "items": [
            dict(id="potion", name="Healing Potion", desc="One more potion for the road (H to drink)",
                 price=25),
            dict(id="herbs", name="Mending Herbs", desc="Every potion heals +6 more",
                 attr="herb_lv", prices=(70, 160)),
        ],
    },
}


class ShopMenu:
    def __init__(self, shop_id, save, pc, sfx=None):
        self.cat = CATALOG[shop_id]
        self.save, self.pc, self.sfx = save, pc, sfx
        self.tabs = ["upgrades", "gear"] if self.cat.get("gear") else ["upgrades"]
        self.tab = 0
        self.stock = shop_stock(save.hero_class, save.stage) if "gear" in self.tabs else []
        self.scroll = 0
        self.sel = 0
        self.msg, self.msg_col, self.msg_t = self.cat["greet"], (220, 220, 210), 0.0
        self.shake = 0.0
        self.flash = 0.0
        self.open = True
        self.f_title = pygame.font.Font(None, 46)
        self.f_item = pygame.font.Font(None, 32)
        self.f_small = pygame.font.Font(None, 23)

    @property
    def on_gear(self):
        return self.tabs[self.tab] == "gear"

    @property
    def items(self):
        return self.stock if self.on_gear else self.cat["items"]

    def switch_tab(self, step):
        if len(self.tabs) < 2:
            return
        self.tab = (self.tab + step) % len(self.tabs)
        self.sel = self.scroll = 0
        self._play("blip")

    # ---- pricing -------------------------------------------------------------
    def level(self, it):
        return getattr(self.save, it["attr"]) if "attr" in it else None

    def price(self, it):
        """Gold cost, or None when the item can't be bought (maxed / full)."""
        if isinstance(it, Item):
            return it.price
        if "attr" in it:
            lv = self.level(it)
            return it["prices"][lv] if lv < len(it["prices"]) else None
        if it["id"] == "potion" and self.pc.potions >= _combat.POTION_MAX:
            return None
        return it["price"]

    def _say(self, text, col):
        self.msg, self.msg_col, self.msg_t = text, col, 2.5

    def _play(self, name):
        if self.sfx:
            self.sfx.play(name)

    def buy(self):
        it = self.items[self.sel]
        cost = self.price(it)
        if cost is None:
            self._say("Sold out. Nothing more I can do for you there.", (200, 200, 190))
            self._play("blip")
            return False
        if self.save.gold < cost:
            self._say("You need %d more gold." % (cost - self.save.gold), (255, 130, 120))
            self.shake = 0.35
            self._play("hurt")
            return False
        if isinstance(it, Item):
            if not self.save.gear.add(Item(it.base, it.rarity)):
                self._say("Your bag is full. Sell something first (I).", (255, 130, 120))
                self._play("blip")
                return False
            self.save.gold -= cost
            self.flash = 0.4
            self._say("%s - it's in your bag. Wear it from the character screen (I)." % it.name, it.color)
            self._play("pickup")
            return True
        self.save.gold -= cost
        self.save.pull_from(self.pc)
        if "attr" in it:
            setattr(self.save, it["attr"], self.level(it) + 1)
            self.save.apply_to(self.pc)
            if it["id"] == "armor":
                self.pc.heal(8)
        elif it["id"] == "potion":
            self.pc.add_potion()
            self.save.pull_from(self.pc)
        self.flash = 0.4
        self._say("%s - a fine choice!" % it["name"], (255, 226, 130))
        self._play("pickup")
        return True

    # ---- input -----------------------------------------------------------------
    def handle_key(self, key):
        if key in (pygame.K_ESCAPE, pygame.K_q, pygame.K_BACKSPACE):
            self.open = False
            self._play("blip")
        elif key in (pygame.K_a, pygame.K_LEFT):
            self.switch_tab(-1)
        elif key in (pygame.K_d, pygame.K_RIGHT, pygame.K_TAB):
            self.switch_tab(1)
        elif key in (pygame.K_w, pygame.K_UP):
            self.sel = (self.sel - 1) % len(self.items)
            self._play("blip")
        elif key in (pygame.K_s, pygame.K_DOWN):
            self.sel = (self.sel + 1) % len(self.items)
            self._play("blip")
        elif key in (pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_SPACE, pygame.K_e):
            self.buy()
        if self.on_gear:                  # keep the selection inside the visible rows
            self.scroll = min(max(self.scroll, self.sel - GEAR_ROWS + 1), self.sel)
        return self.open

    def update(self, dt):
        self.shake = max(0.0, self.shake - dt)
        self.flash = max(0.0, self.flash - dt)
        if self.msg_t > 0:
            self.msg_t -= dt
            if self.msg_t <= 0:
                self.msg, self.msg_col = self.cat["greet"], (220, 220, 210)

    # ---- drawing -----------------------------------------------------------------
    def draw(self, surf, t):
        W, H = surf.get_size()
        veil = pygame.Surface((W, H), pygame.SRCALPHA)
        veil.fill((0, 0, 0, 150))
        surf.blit(veil, (0, 0))
        col = self.cat["color"]
        rows = max(len(self.cat["items"]), GEAR_ROWS if self.stock else 0)
        tabs_h = 40 if len(self.tabs) > 1 else 0
        pw, ph = 680, 104 + tabs_h + 74 * rows + 54
        px, py = W // 2 - pw // 2, H // 2 - ph // 2
        if self.shake:
            px += int(math.sin(t * 80) * 8 * self.shake / 0.35)
        panel = pygame.Rect(px, py, pw, ph)
        pygame.draw.rect(surf, (16, 14, 20), panel, border_radius=12)
        pygame.draw.rect(surf, col, panel, 3, border_radius=12)
        pygame.draw.rect(surf, (70, 56, 40), panel.inflate(-12, -12), 1, border_radius=9)

        title = self.f_title.render(self.cat["title"], True, (250, 240, 220))
        surf.blit(title, (px + 28, py + 22))
        # gold
        gtxt = self.f_item.render("%d gold" % self.save.gold, True, (255, 226, 130))
        gx = px + pw - gtxt.get_width() - 30
        pygame.draw.circle(surf, (90, 60, 10), (gx - 16, py + 36), 10)
        pygame.draw.circle(surf, (240, 196, 70), (gx - 16, py + 35), 8)
        surf.blit(gtxt, (gx, py + 25))
        msg = self.f_small.render(self.msg, True, self.msg_col)
        surf.blit(msg, (px + 30, py + 70))

        y = py + 104
        if tabs_h:
            for i, name in enumerate(("Upgrades", "Gear for you")):
                tr = pygame.Rect(px + 20 + i * 170, y, 160, 30)
                on = i == self.tab
                pygame.draw.rect(surf, col if on else (40, 36, 44), tr, 0 if on else 1, border_radius=6)
                img = self.f_small.render(name, True, (20, 16, 14) if on else (200, 196, 186))
                surf.blit(img, img.get_rect(center=tr.center))
            y += tabs_h
        if self.on_gear:
            self._draw_gear(surf, t, px, y, pw, col)
            foot = self.f_small.render("W/S: choose    A/D: tab    Enter / E: buy    Esc: leave", True, (200, 196, 180))
            surf.blit(foot, (px + pw // 2 - foot.get_width() // 2, py + ph - 38))
            return
        for i, it in enumerate(self.items):
            row = pygame.Rect(px + 20, y, pw - 40, 66)
            sel = i == self.sel
            cost = self.price(it)
            if sel:
                glow = (*col, 60 + int(40 * (0.5 + 0.5 * math.sin(t * 4)))) if not self.flash else (255, 240, 160, 120)
                hl = pygame.Surface(row.size, pygame.SRCALPHA)
                pygame.draw.rect(hl, glow, hl.get_rect(), border_radius=8)
                surf.blit(hl, row)
                pygame.draw.rect(surf, col, row, 2, border_radius=8)
            else:
                pygame.draw.rect(surf, (40, 36, 44), row, 1, border_radius=8)
            name_col = (245, 240, 228) if cost is not None else (140, 140, 140)
            surf.blit(self.f_item.render(it["name"], True, name_col), (row.x + 16, row.y + 8))
            surf.blit(self.f_small.render(it["desc"], True, (180, 180, 186)), (row.x + 16, row.y + 40))
            if "attr" in it:            # level pips
                lv, mx = self.level(it), len(it["prices"])
                for k in range(mx):
                    c = (255, 214, 90) if k < lv else (60, 56, 64)
                    pygame.draw.rect(surf, c, (row.x + 330 + k * 18, row.y + 14, 12, 12), border_radius=3)
            elif it["id"] == "potion":
                surf.blit(self.f_small.render("owned %d / %d" % (self.pc.potions, _combat.POTION_MAX), True,
                                              (200, 160, 170)), (row.x + 330, row.y + 12))
            if cost is None:
                ptxt = self.f_item.render("MAX" if "attr" in it else "FULL", True, (150, 150, 150))
            else:
                ok = self.save.gold >= cost
                ptxt = self.f_item.render("%d g" % cost, True, (255, 226, 130) if ok else (220, 110, 100))
            surf.blit(ptxt, (row.right - ptxt.get_width() - 18, row.y + 18))
            y += 74

        hint = "W/S: choose    A/D: tab    Enter / E: buy    Esc: leave" if tabs_h else \
            "W/S: choose     Enter / E: buy     Esc: leave"
        foot = self.f_small.render(hint, True, (200, 196, 180))
        surf.blit(foot, (px + pw // 2 - foot.get_width() // 2, py + ph - 38))

    def _draw_gear(self, surf, t, px, y, pw, col):
        res = "Mana" if self.pc.resource == "mana" else "Energy"
        for i in range(self.scroll, min(len(self.stock), self.scroll + GEAR_ROWS)):
            it = self.stock[i]
            row = pygame.Rect(px + 20, y, pw - 40, 66)
            if i == self.sel:
                glow = (*col, 60 + int(40 * (0.5 + 0.5 * math.sin(t * 4)))) if not self.flash else (255, 240, 160, 120)
                hl = pygame.Surface(row.size, pygame.SRCALPHA)
                pygame.draw.rect(hl, glow, hl.get_rect(), border_radius=8)
                surf.blit(hl, row)
                pygame.draw.rect(surf, col, row, 2, border_radius=8)
            else:
                pygame.draw.rect(surf, (40, 36, 44), row, 1, border_radius=8)
            box = pygame.Rect(row.x + 10, row.y + 8, 50, 50)
            pygame.draw.rect(surf, (30, 24, 22), box)
            pygame.draw.rect(surf, it.color, box, 2)
            icon = item_icon(it, 40)
            surf.blit(icon, icon.get_rect(center=box.center))
            surf.blit(self.f_item.render(it.name, True, it.color), (row.x + 72, row.y + 8))
            parts = []
            for k in STAT_ORDER:
                if k in it.stats:
                    num, name = format_stat(k, it.stats[k], res)
                    parts.append("%s %s" % (num, name))
            surf.blit(self.f_small.render(",  ".join(parts), True, (180, 180, 186)), (row.x + 72, row.y + 40))
            worn = self.save.gear.equipped.get(it.slot)
            gain = sum(v for v in self.save.gear.compare(it).values())
            if worn is not None and worn == it:
                tag, tcol = "worn", (150, 220, 255)
            elif gain > 0:
                tag, tcol = "upgrade", (120, 230, 120)
            else:
                tag, tcol = "", (0, 0, 0)
            if tag:
                timg = self.f_small.render(tag, True, tcol)
                surf.blit(timg, (row.right - timg.get_width() - 18, row.y + 42))
            ok = self.save.gold >= it.price
            ptxt = self.f_item.render("%d g" % it.price, True, (255, 226, 130) if ok else (220, 110, 100))
            surf.blit(ptxt, (row.right - ptxt.get_width() - 18, row.y + 10))
            y += 74
        if len(self.stock) > GEAR_ROWS:          # scroll bar
            track = pygame.Rect(px + pw - 14, y - 74 * GEAR_ROWS, 5, 74 * GEAR_ROWS - 8)
            pygame.draw.rect(surf, (40, 36, 44), track, border_radius=3)
            h = track.h * GEAR_ROWS // len(self.stock)
            top = track.y + (track.h - h) * self.scroll // max(1, len(self.stock) - GEAR_ROWS)
            pygame.draw.rect(surf, col, (track.x, top, track.w, h), border_radius=3)
