"""
loot.py - Gear dropped by monsters, lying on the ground until the hero walks over it.

    loot = GroundLoot()
    loot.drop(item, x, y)                       # pops out of a dead monster
    for item in loot.update(dt, hero, gear):    # items picked up this frame (bag had room)
        toast(...)
    loot.draw(surf, cam_x, cam_y, t)
    loot.clear()                                # leaving the place: what's left is lost

Drops hop out, sit with a light beam in their rarity colour, and drift to the hero when
close. A full bag leaves them on the ground (with a reminder now and then).
"""
from __future__ import annotations

import math
import random

import pygame

from ui.gear_icons import item_icon

PICKUP = 22          # px: walking this close picks it up
MAGNET = 70          # px: closer than this, the drop drifts toward the hero
LIFETIME = 120.0     # s: drops vanish after two minutes
LABEL = 90           # px: drops this close to the hero show their name

_font = None


def _label_font():
    global _font
    if _font is None:
        _font = pygame.font.Font(None, 20)
    return _font


class GroundLoot:
    def __init__(self):
        self.items: list[dict] = []
        self.full_t = 0.0             # time since the "bag is full" reminder
        self.bag_full = False         # True on a frame something was left behind (bag full)

    def drop(self, item, x, y):
        a = random.uniform(0, math.tau)
        self.items.append({"item": item, "x": x, "y": y, "vx": math.cos(a) * 60, "vy": math.sin(a) * 40,
                           "z": 0.0, "vz": 150.0, "age": 0.0})

    def clear(self):
        self.items.clear()

    def update(self, dt, hero, gear):
        """Move drops; returns the items that went into the bag this frame.
        `bag_full` is set when something couldn't be picked up."""
        got = []
        self.full_t += dt
        self.bag_full = False
        for d in self.items:
            d["age"] += dt
            if d["z"] > 0 or d["vz"] > 0:            # the little hop out of the monster
                d["vz"] -= 520 * dt
                d["z"] = max(0.0, d["z"] + d["vz"] * dt)
                d["x"] += d["vx"] * dt
                d["y"] += d["vy"] * dt
                if d["z"] == 0 and d["vz"] < 0:
                    d["vz"] = 0.0
                continue
            dist = math.hypot(hero.x - d["x"], hero.y - d["y"])
            if dist < MAGNET and not gear.full:
                k = min(1.0, dt * 6)
                d["x"] += (hero.x - d["x"]) * k
                d["y"] += (hero.y - d["y"]) * k
            if dist < PICKUP:
                if gear.add(d["item"]):
                    got.append(d["item"])
                    d["age"] = LIFETIME + 1
                elif self.full_t > 4.0:
                    self.full_t = 0.0
                    self.bag_full = True
        self.items = [d for d in self.items if d["age"] <= LIFETIME]
        return got

    def draw(self, surf, cx, cy, t, hero=None):
        """Drops with their beams; names show over the ones near `hero`."""
        for d in sorted(self.items, key=lambda d: d["y"]):
            item = d["item"]
            X, Y = int(d["x"] - cx), int(d["y"] - cy)
            col = item.color
            if item.rarity >= 1:                      # light beam for anything better than Common
                h = 40 + 16 * item.rarity
                beam = pygame.Surface((14, h), pygame.SRCALPHA)
                for i in range(h):
                    a = int(90 * (i / h) * (0.7 + 0.3 * math.sin(t * 3 + d["age"])))
                    pygame.draw.line(beam, (*col, a), (0, i), (13, i))
                surf.blit(beam, (X - 7, Y - h))
            pygame.draw.ellipse(surf, (0, 0, 0), (X - 10, Y - 3, 20, 6))
            bob = 0 if d["z"] > 0 else int(2 * math.sin(t * 4 + d["age"]))
            icon = item_icon(item, 26)
            fade = 255 if d["age"] < LIFETIME - 5 else int(255 * (LIFETIME - d["age"]) / 5)
            if fade < 255:
                icon = icon.copy()
                icon.set_alpha(max(0, fade))
            surf.blit(icon, icon.get_rect(midbottom=(X, Y - 2 - int(d["z"]) - bob)))
            if hero is not None and d["z"] == 0 and math.hypot(hero.x - d["x"], hero.y - d["y"]) < LABEL:
                self._label(surf, item, X, Y - 34)

    @staticmethod
    def _label(surf, item, x, y):
        font = _label_font()
        img = font.render(item.name, True, item.color)
        r = img.get_rect(midbottom=(x, y)).inflate(10, 4)
        back = pygame.Surface(r.size, pygame.SRCALPHA)
        back.fill((10, 8, 12, 170))
        surf.blit(back, r)
        pygame.draw.rect(surf, item.color, r, 1)
        surf.blit(img, img.get_rect(center=r.center))
