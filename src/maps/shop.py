"""
shop.py - keyboard shop overlay for Oakwood's merchants.

    menu = ShopMenu("torvin", save, pc, sfx)
    menu.handle_key(key)   -> False once the player leaves the shop
    menu.update(dt); menu.draw(screen, t)

Purchases change the SaveState and are pushed onto PlayerCombat with
save.apply_to(pc), so combat code never needs to know about the shop.
"""
from __future__ import annotations

import math

import pygame

try:
    from .combat import POTION_MAX
except ImportError:                       # running from inside src/maps
    from combat import POTION_MAX

CATALOG = {
    "torvin": {
        "title": "Torvin's Forge",
        "greet": "Steel doesn't care who you are. It only cares how sharp it is.",
        "color": (232, 150, 70),
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
        self.items = self.cat["items"]
        self.save, self.pc, self.sfx = save, pc, sfx
        self.sel = 0
        self.msg, self.msg_col, self.msg_t = self.cat["greet"], (220, 220, 210), 0.0
        self.shake = 0.0
        self.flash = 0.0
        self.open = True
        self.f_title = pygame.font.Font(None, 46)
        self.f_item = pygame.font.Font(None, 32)
        self.f_small = pygame.font.Font(None, 23)

    # ---- pricing -------------------------------------------------------------
    def level(self, it):
        return getattr(self.save, it["attr"]) if "attr" in it else None

    def price(self, it):
        """Gold cost, or None when the item can't be bought (maxed / full)."""
        if "attr" in it:
            lv = self.level(it)
            return it["prices"][lv] if lv < len(it["prices"]) else None
        if it["id"] == "potion" and self.pc.potions >= POTION_MAX:
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
        elif key in (pygame.K_w, pygame.K_UP):
            self.sel = (self.sel - 1) % len(self.items)
            self._play("blip")
        elif key in (pygame.K_s, pygame.K_DOWN):
            self.sel = (self.sel + 1) % len(self.items)
            self._play("blip")
        elif key in (pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_SPACE, pygame.K_e):
            self.buy()
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
        pw, ph = 640, 104 + 74 * len(self.items) + 54
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
                surf.blit(self.f_small.render("owned %d / %d" % (self.pc.potions, POTION_MAX), True,
                                              (200, 160, 170)), (row.x + 330, row.y + 12))
            if cost is None:
                ptxt = self.f_item.render("MAX" if "attr" in it else "FULL", True, (150, 150, 150))
            else:
                ok = self.save.gold >= cost
                ptxt = self.f_item.render("%d g" % cost, True, (255, 226, 130) if ok else (220, 110, 100))
            surf.blit(ptxt, (row.right - ptxt.get_width() - 18, row.y + 18))
            y += 74

        foot = self.f_small.render("W/S: choose     Enter / E: buy     Esc: leave", True, (200, 196, 180))
        surf.blit(foot, (px + pw // 2 - foot.get_width() // 2, py + ph - 38))
