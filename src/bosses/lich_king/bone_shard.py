"""bone_shard.py - The sharp bone slivers of the Lich King's Bone Nova."""
import math

from ..attacks import Projectile
from .effects import BONE, BONE_LIGHT, BONE_SHADE, OUTLINE, FxLayer, lerp_color


class BoneShard(Projectile):
    """
    A spike of bone. It leaves the Lich King slowly and speeds up, so the gaps in the
    ring are easy to read before the shards get fast. A trail of bone dust follows it.
    """
    RAMP_TIME = 0.55          # seconds to reach full speed

    def __init__(self, x, y, angle, speed, damage):
        super().__init__(x, y, angle, speed, damage, radius=7, color=BONE)
        self.angle = angle
        self.top_speed = speed
        self.age = 0.0
        self.trail = []

    def update(self, dt, player, bounds):
        if not self.alive:
            return
        self.age += dt
        self.trail.append((self.x, self.y))
        self.trail = self.trail[-7:]
        speed = self.top_speed * min(1.0, 0.3 + 0.7 * self.age / self.RAMP_TIME)
        self.vx = math.cos(self.angle) * speed
        self.vy = math.sin(self.angle) * speed
        super().update(dt, player, bounds)

    def draw(self, surface):
        pad = 40
        fx = FxLayer(self.x - pad, self.y - pad, pad * 2, pad * 2)
        for i, (tx, ty) in enumerate(self.trail):                      # bone dust, fading behind the shard
            k = (i + 1) / float(len(self.trail) + 1)
            fx.dot(tx, ty, lerp_color(OUTLINE, BONE_SHADE, k), size=2 if k > 0.6 else 1)
        ca, sa = math.cos(self.angle), math.sin(self.angle)
        x, y = self.x, self.y
        tip = (x + ca * 16, y + sa * 16)
        tail = (x - ca * 11, y - sa * 11)
        left = (x - ca * 3 - sa * 5, y - sa * 3 + ca * 5)
        right = (x - ca * 3 + sa * 5, y - sa * 3 - ca * 5)
        fx.polygon([tip, left, tail, right], OUTLINE)                  # outlined bone spike
        inner = [(x + ca * 12, y + sa * 12), (x - ca * 3 - sa * 2.5, y - sa * 3 + ca * 2.5),
                 (x - ca * 8, y - sa * 8), (x - ca * 3 + sa * 2.5, y - sa * 3 - ca * 2.5)]
        fx.polygon(inner, BONE)
        fx.line((x - ca * 7, y - sa * 7), (x + ca * 11, y + sa * 11), BONE_LIGHT)
        fx.draw(surface)
