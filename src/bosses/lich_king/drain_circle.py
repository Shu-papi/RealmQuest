"""drain_circle.py - The Lich King's life-drain ground circle: a turning necromantic rune circle."""
import math

try:
    import audio                                             # src/ is on sys.path
except ImportError:                                          # run as src.bosses
    from src import audio
from ..attacks import player_pos
from .effects import (FxLayer, PIXEL, ease_out, hexagram, lerp_color, rune_ring, shock_ring, theme,
                      with_alpha)


class DrainCircle:
    """
    A rune circle on the ground. It charges up for `duration` seconds (runes turning, the glow
    filling outwards), then bursts. If the player is still inside, they take damage.
    """
    BURST_TIME = 0.3
    SFX_BURST = "drain_burst"

    def __init__(self, x, y, radius, duration, damage, phase=1):
        self.x = float(x)
        self.y = float(y)
        self.radius = radius
        self.duration = duration
        self.damage = damage
        self.phase = phase
        self.timer = 0.0
        self.state = "warning"   # warning -> burst -> done

    @property
    def alive(self):
        return self.state != "done"

    def update(self, dt, player):
        """Returns True on the frame the circle bursts and actually hurts the player."""
        self.timer += dt
        if self.state == "warning" and self.timer >= self.duration:
            self.state = "burst"
            self.timer = 0.0
            audio.play(self.SFX_BURST, self.x)
            px, py = player_pos(player)
            if math.hypot(px - self.x, py - self.y) <= self.radius:
                dealt = player.take_damage(self.damage)
                # Some player classes return nothing; treat that as "was hit"
                return dealt is None or dealt > 0
        elif self.state == "burst" and self.timer >= self.BURST_TIME:
            self.state = "done"
        return False

    # ---------- drawing ----------

    def draw(self, surface):
        colors = theme(self.phase)
        r = self.radius
        pad = int(r * 1.6) + 40
        fx = FxLayer(self.x - pad, self.y - pad - 60, pad * 2, pad * 2 + 60)
        cx, cy = self.x, self.y
        if self.state == "warning":
            self._draw_charging(fx, cx, cy, r, colors)
        else:
            self._draw_burst(fx, cx, cy, r, colors)
        fx.draw(surface)

    def _draw_charging(self, fx, cx, cy, r, colors):
        t = min(1.0, self.timer / self.duration)
        flash = max(0.0, (self.timer - (self.duration - 0.25)) / 0.25)        # 0 -> 1 in the last quarter second
        spin = self.timer * 1.3 + self.x * 0.01
        # the glowing ground: a dim pool, and a brighter glow that fills outwards as the spell charges
        fx.circle((cx, cy), r, with_alpha(colors["dark"], 120), soft=True)
        fx.circle((cx, cy), max(PIXEL * 2, r * t), with_alpha(colors["glow"], 120 + 90 * flash), soft=True)
        ring = lerp_color(colors["main"], colors["hot"], flash)
        fx.circle((cx, cy), r, ring, width=1)                                  # outer ring
        fx.circle((cx, cy), r * 0.74, with_alpha(ring, 170), width=1)          # inner ring
        rune_ring(fx, cx, cy, r * 0.87, ring, spin, count=12, speed=0.5, line=False)
        hexagram(fx, cx, cy, r * 0.55, with_alpha(colors["glow"], 235), -spin * 0.7)
        fx.dot(cx, cy, colors["hot"], size=2)
        for i in range(7):                                                     # soul motes spiral inwards
            frac = (self.timer * 0.9 + i / 7.0) % 1.0
            a = i * 0.9 + frac * 3.0 + spin
            fx.dot(cx + math.cos(a) * r * (1 - frac) * 0.95, cy + math.sin(a) * r * (1 - frac) * 0.95,
                   with_alpha(colors["main"], 255), size=2 if i % 2 else 1)
        if flash > 0:                                                          # "NOW": a pulse just before it bursts
            fx.circle((cx, cy), r + PIXEL * (2 + 2 * flash), colors["hot"], width=1)

    def _draw_burst(self, fx, cx, cy, r, colors):
        u = self.timer / self.BURST_TIME
        fade = max(0.0, 1.0 - u)
        radius = r * (0.65 + 0.7 * ease_out(u))
        shock_ring(fx, cx, cy, radius, with_alpha(colors["hot"], 255 * fade), with_alpha(colors["glow"], 255 * fade),
                   thickness=2)
        fx.circle((cx, cy), radius, with_alpha(colors["main"], 110 * fade), soft=True)
        for i in range(9):                                                     # columns of soul-light rise out of it
            a = i * math.tau / 9 + 0.4
            bx, by = cx + math.cos(a) * r * 0.6, cy + math.sin(a) * r * 0.45
            height = (60 + 60 * ((i * 5) % 7) / 7.0) * ease_out(u) * (1 - 0.3 * u)
            fx.line((bx, by), (bx, by - height), with_alpha(colors["glow"], 255 * fade), width=3)
            fx.line((bx, by), (bx, by - height), with_alpha(colors["main"], 255 * fade), width=2)
            fx.line((bx, by), (bx, by - height * 0.7), with_alpha(colors["hot"], 255 * fade), width=1)
            fx.dot(bx, by - height, with_alpha(colors["hot"], 255 * fade), size=3)


class SoulRain(DrainCircle):
    """
    A small rune circle from the Lich King's Soul Rain. It looks and bursts like a drain circle but it only
    hurts: it does NOT heal him (so the player is never punished twice for the same mistake).
    """
    heals = False
    SFX_BURST = "rain_burst"
