"""
grasping_hand.py - The Lich King's Grasping Hands: skeletal hands that burst out of the floor.

First the ground cracks and splits (the warning): a patch of broken floor with glowing seams spreads and
bone fingertips start to poke through. Then a bone hand bursts up. If you are still standing there it
hurts AND roots you in place for a moment (if the player supports statuses).
"""
import math
import random

try:
    import audio                                             # src/ is on sys.path
except ImportError:                                          # run as src.bosses
    from src import audio
from ..attacks import apply_status, player_pos
from .effects import (BONE, BONE_LIGHT, BONE_SHADE, OUTLINE, FxLayer, PIXEL, crack_points, draw_polyline,
                      ease_out, jagged_points, lerp_color, shock_ring, theme, with_alpha)

DUST = (120, 108, 140)
SOIL = (30, 18, 56)


class GraspingHand:
    BURST_TIME = 0.8
    CRACKS = 6

    def __init__(self, x, y, radius, duration, damage, root_seconds, seed=0.0, phase=2):
        self.x = float(x)
        self.y = float(y)
        self.radius = radius
        self.duration = duration
        self.damage = damage
        self.root_seconds = root_seconds
        self.phase = phase
        self.timer = 0.0
        self.state = "warning"          # warning -> burst -> done
        self.seed = seed

    @property
    def alive(self):
        return self.state != "done"

    def update(self, dt, player):
        """Returns True on the frame the hand bursts out and actually hurts the player."""
        self.timer += dt
        if self.state == "warning" and self.timer >= self.duration:
            self.state = "burst"
            self.timer = 0.0
            audio.play("grasp_burst", self.x)
            px, py = player_pos(player)
            if math.hypot(px - self.x, py - self.y) <= self.radius:
                dealt = player.take_damage(self.damage)
                hurt = dealt is None or dealt > 0
                if hurt:
                    if apply_status(player, "root", self.root_seconds):
                        audio.play("grasp_root", self.x)
                return hurt
        elif self.state == "burst" and self.timer >= self.BURST_TIME:
            self.state = "done"
        return False

    # ---------- drawing ----------

    def draw(self, surface):
        pad = int(self.radius * 1.5) + 30
        fx = FxLayer(self.x - pad, self.y - pad - 70, pad * 2, pad * 2 + 80)
        if self.state == "warning":
            self._draw_warning(fx)
        else:
            self._draw_hand(fx)
        fx.draw(surface)

    def _crack_angles(self):
        return [self.seed + i * math.tau / self.CRACKS + math.sin(self.seed * 7 + i * 2.3) * 0.25
                for i in range(self.CRACKS)]

    def _draw_warning(self, fx):
        colors = theme(self.phase)
        r = self.radius
        t = min(1.0, self.timer / self.duration)
        flash = max(0.0, (self.timer - (self.duration - 0.22)) / 0.22)
        rumble = PIXEL if (t > 0.7 and int(self.timer * 30) % 2) else 0               # the ground shudders
        cx, cy = self.x + rumble, self.y
        # a patch of broken ground: dark, ragged, never a clean circle
        rim = jagged_points(cx, cy, r, self.seed, count=15)
        fx.polygon(rim, with_alpha(SOIL, 190), soft=True)
        fx.polygon(jagged_points(cx, cy, max(PIXEL * 2, r * t * 0.92), self.seed + 1, count=11),
                   with_alpha(colors["glow"], 120 + 100 * flash), soft=True)
        dash = int(self.timer * 9)
        edge = lerp_color(BONE_SHADE, BONE_LIGHT, flash)
        for i in range(len(rim)):                                                        # marching dashes on the rim
            if (i + dash) % 3:
                fx.line(rim[i], rim[(i + 1) % len(rim)], edge)
        # glowing cracks spread from the middle
        grow = ease_out(min(1.0, t * 1.5))
        pulse = 0.5 + 0.5 * math.sin(self.timer * 9)
        glow = lerp_color(colors["main"], colors["hot"], max(flash, 0.25 * pulse))
        for k, ang in enumerate(self._crack_angles()):
            pts = crack_points(cx, cy, ang, r * 0.98, self.seed * 10 + k, segments=5)
            draw_polyline(fx, pts, OUTLINE, width=2, upto=grow)
            draw_polyline(fx, pts, glow, width=1, upto=grow)
        if t > 0.62:                                                                     # fingertips push through
            up = (t - 0.62) / 0.38
            for k in range(5):
                ang = k * math.tau / 5 + self.seed
                bx, by = cx + math.cos(ang) * r * 0.32, cy + math.sin(ang) * r * 0.22
                fx.line((bx, by), (bx, by - 14 * up), BONE, width=1)
                fx.dot(bx, by - 14 * up, BONE_LIGHT)
            rng = random.Random(int(self.timer * 14) + int(self.seed * 100))           # soil jumping off the floor
            for _ in range(int(6 * up)):
                fx.dot(cx + rng.uniform(-r, r) * 0.8, cy - rng.uniform(2, 24), DUST)

    def _draw_hand(self, fx):
        colors = theme(self.phase)
        u = self.timer / self.BURST_TIME
        if u < 0.25:
            rise = ease_out(u / 0.25)
        elif u < 0.7:
            rise = 1.0
        else:
            rise = max(0.0, 1.0 - (u - 0.7) / 0.3)
        x, y, r = self.x, self.y, self.radius
        # the split ground stays behind, fading
        fx.polygon(jagged_points(x, y, r, self.seed, count=15), with_alpha(SOIL, 200 * (1 - u)), soft=True)
        for k, ang in enumerate(self._crack_angles()):
            draw_polyline(fx, crack_points(x, y, ang, r * 0.98, self.seed * 10 + k, segments=5),
                          lerp_color(colors["main"], OUTLINE, u), width=1)
        if u < 0.35:                                                                    # dust shockwave on emergence
            shock_ring(fx, x, y, r * 1.35 * ease_out(u / 0.35), with_alpha(DUST, 255 * (1 - u / 0.35)),
                       with_alpha(OUTLINE, 255 * (1 - u / 0.35)), thickness=1)
        if rise <= 0:
            return
        arm = 46 * rise
        shake = round(math.sin(self.timer * 60) * 1.5) if u < 0.25 else 0
        top = y - arm
        for off in (-5, 3):                                                             # forearm: two bones
            fx.rect(x + off - 2 + shake, top, x + off + 7 + shake, y, OUTLINE)
            fx.rect(x + off + shake, top, x + off + 5 + shake, y, BONE)
            fx.line((x + off + 5 + shake, top), (x + off + 5 + shake, y), BONE_SHADE)
        pl, pt = x - 13 + shake, top - 14
        fx.rect(pl - 3, pt - 3, pl + 28, pt + 18, OUTLINE)                              # palm
        fx.rect(pl, pt, pl + 25, pt + 15, BONE)
        fx.line((pl + 2, pt + 13), (pl + 23, pt + 13), BONE_SHADE)
        curl = 0.35 + 0.65 * (1 - rise)
        for k, spread in enumerate((-1.1, -0.55, 0.0, 0.55, 1.1)):                      # five clawed fingers
            base = (pl + 12 + spread * 9, pt)
            ang = -math.pi / 2 + spread * 0.55
            length1 = 15 if k not in (0, 4) else 12
            knuckle = (base[0] + math.cos(ang) * length1, base[1] + math.sin(ang) * length1)
            ang2 = ang - spread * 0.5 * curl - (0.5 if spread == 0 else 0) * curl
            tip = (knuckle[0] + math.cos(ang2) * 11, knuckle[1] + math.sin(ang2) * 11)
            fx.line(base, knuckle, OUTLINE, width=3)
            fx.line(knuckle, tip, OUTLINE, width=3)
            fx.line(base, knuckle, BONE, width=2)
            fx.line(knuckle, tip, BONE_LIGHT, width=2)
        for i in range(10):                                                             # a spray of soil and bone dust
            t = min(1.0, u * 2.2)
            if t >= 1.0:
                break
            ang = i * math.tau / 10 + self.seed
            fx.dot(x + math.cos(ang) * (8 + 30 * t), y - 4 - abs(math.sin(i * 1.3)) * 22 * t - 14 * t,
                   DUST if i % 2 else BONE_SHADE, size=2 if i % 3 == 0 else 1)
