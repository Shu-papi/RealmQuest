"""soul_bolt.py - The Lich King's Shadow Volley bolt: a screaming ghost skull trailing soul-fire."""
import math

from ..attacks import Projectile
from .effects import FxLayer, soul_skull, theme, with_alpha


class SoulBolt(Projectile):
    """A fast bolt of soul-fire shaped like a ghost skull. Its colour follows the phase (violet, crimson, white-hot)."""

    def __init__(self, x, y, angle, speed, damage, phase=1):
        colors = theme(phase)
        super().__init__(x, y, angle, speed, damage, radius=8, color=colors["main"])
        self.angle = angle
        self.phase = phase
        self.age = 0.0

    def update(self, dt, player, bounds):
        self.age += dt
        super().update(dt, player, bounds)

    def draw(self, surface):
        colors = theme(self.phase)
        pad = 48
        fx = FxLayer(self.x - pad, self.y - pad, pad * 2, pad * 2)
        fx.circle((self.x, self.y), 24, with_alpha(colors["glow"], 130), soft=True)      # a dithered halo
        soul_skull(fx, self.x, self.y, colors["main"], tail_angle=self.angle + math.pi, flicker=self.age, big=True)
        fx.dot(self.x + math.cos(self.angle) * 12, self.y + math.sin(self.angle) * 12, colors["hot"], size=2)
        fx.draw(surface)
