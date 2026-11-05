"""shockwave.py - The Minotaur's ground hazards: the slam's warning circle (Shockwave) and a falling boulder (RockFall)."""
import math
import pygame

from ..attacks import player_pos


class Shockwave:
    """
    A circle on the ground. It shows a warning for `duration` seconds, then bursts.
    If the player is still inside when it bursts, they take damage. Leave the circle in time!
    """
    BURST_TIME = 0.3

    def __init__(self, x, y, radius, duration, damage):
        self.x = float(x)
        self.y = float(y)
        self.radius = radius
        self.duration = duration
        self.damage = damage
        self.timer = 0.0
        self.state = "warning"           # warning -> burst -> done

    @property
    def alive(self):
        return self.state != "done"

    def update(self, dt, player):
        """Returns True on the frame the shockwave bursts and actually hurts the player."""
        self.timer += dt
        if self.state == "warning" and self.timer >= self.duration:
            self.state = "burst"
            self.timer = 0.0
            px, py = player_pos(player)
            if math.hypot(px - self.x, py - self.y) <= self.radius:
                dealt = player.take_damage(self.damage)
                # Some player classes return nothing; treat that as "was hit"
                return dealt is None or dealt > 0
        elif self.state == "burst" and self.timer >= self.BURST_TIME:
            self.state = "done"
        return False

    def draw(self, surface):
        r = int(self.radius)
        size = r * 2 + 4
        layer = pygame.Surface((size, size), pygame.SRCALPHA)
        center = (r + 2, r + 2)
        if self.state == "warning":
            progress = min(1.0, self.timer / self.duration)
            pygame.draw.circle(layer, (226, 75, 74, 60), center, r)
            pygame.draw.circle(layer, (239, 140, 60, 120), center, max(2, int(r * progress)))
            pygame.draw.circle(layer, (255, 190, 110, 230), center, r, 3)
        else:
            fade = max(0.0, 1.0 - self.timer / self.BURST_TIME)
            pygame.draw.circle(layer, (255, 220, 170, int(200 * fade)), center, r)
        surface.blit(layer, (int(self.x) - r - 2, int(self.y) - r - 2))

    def draw_ground(self, surface):
        """Everything here lies flat on the floor (the isometric view turns it into an ellipse)."""
        self.draw(surface)

    def draw_air(self, surface, view=None):
        """Nothing stands up."""


class RockFall:
    """
    A boulder dropped from above. A dark shadow and a ring grow on the ground for `duration`
    seconds while the rock falls, then it lands and hurts anyone still inside the ring.
    Same interface as Shockwave (update / draw / alive), so the boss treats them alike.
    """
    BURST_TIME = 0.35
    DROP_HEIGHT = 360

    ROCK = [
        ".kkkk.",
        "kllhhk",
        "kllllk",
        "kdlllk",
        ".kddk.",
    ]
    COLOURS = {"k": (28, 22, 30), "l": (128, 112, 100), "h": (186, 170, 150), "d": (84, 72, 70)}

    def __init__(self, x, y, radius, duration, damage):
        self.x = float(x)
        self.y = float(y)
        self.radius = radius
        self.duration = max(0.05, duration)
        self.damage = damage
        self.timer = 0.0
        self.state = "warning"           # warning -> burst -> done

    @property
    def alive(self):
        return self.state != "done"

    def update(self, dt, player):
        """Returns True on the frame the rock lands and actually hurts the player."""
        self.timer += dt
        if self.state == "warning" and self.timer >= self.duration:
            self.state = "burst"
            self.timer = 0.0
            px, py = player_pos(player)
            if math.hypot(px - self.x, py - self.y) <= self.radius:
                dealt = player.take_damage(self.damage)
                return dealt is None or dealt > 0
        elif self.state == "burst" and self.timer >= self.BURST_TIME:
            self.state = "done"
        return False

    def _fall(self):
        """0 = just started falling, 1 = landed."""
        return min(1.0, self.timer / self.duration) if self.state == "warning" else 1.0

    def draw(self, surface):
        """Flat (top-down) drawing: the ground marks, then the rock above them."""
        self.draw_ground(surface)
        self.draw_air(surface)

    def draw_ground(self, surface):
        """The shadow, the ring and the burst: all flat on the floor."""
        r = int(self.radius)
        size = r * 2 + 4
        layer = pygame.Surface((size, size), pygame.SRCALPHA)
        center = (r + 2, r + 2)
        if self.state == "warning":
            progress = self._fall()
            pygame.draw.circle(layer, (20, 14, 24, int(60 + 90 * progress)), center, max(3, int(r * (0.35 + 0.65 * progress))))
            pygame.draw.circle(layer, (226, 120, 74, 200), center, r, 3)
        else:
            fade = max(0.0, 1.0 - self.timer / self.BURST_TIME)
            pygame.draw.circle(layer, (230, 200, 160, int(170 * fade)), center, int(r * (1.1 - 0.3 * fade)))
        surface.blit(layer, (int(self.x) - r - 2, int(self.y) - r - 2))

    def draw_air(self, surface, view=None):
        """
        The falling boulder and the flying chips of stone.
        Seen from above (the normal arena) the boulder drops straight towards the camera's floor: it
        starts big and close to the camera and shrinks to its real size where it lands, and the chips
        fly out in a flat circle. In the isometric room it falls down the screen instead.
        """
        iso = view is not None and getattr(view, "iso", False)
        px, py = (self.x, self.y) if view is None else view.project(self.x, self.y)
        if self.state == "warning":
            fall = (1.0 - self._fall()) ** 2
            if iso:
                top = int(py - self.DROP_HEIGHT * fall) // 4 * 4 - 40
                left = int(px) // 4 * 4 - 12
                block = 4
            else:
                block = max(4, int(round(4 * (1.0 + 1.6 * fall))))               # 10 px blocks high up -> 4 px on the floor
                left = int(px) - 3 * block
                top = int(py) - int(2.5 * block)
            for row, line in enumerate(self.ROCK):
                for col, ch in enumerate(line):
                    if ch != ".":
                        pygame.draw.rect(surface, self.COLOURS[ch], (left + col * block, top + row * block, block, block))
        else:
            fade = max(0.0, 1.0 - self.timer / self.BURST_TIME)
            for i in range(8):
                angle = i * math.tau / 8 + 0.4
                dist = self.radius * 0.5 * (1.0 - fade) + 8
                if iso:
                    cx = int(px + math.cos(angle) * dist) // 4 * 4
                    cy = int(py + math.sin(angle) * dist * 0.7 - 30 * math.sin((1 - fade) * math.pi)) // 4 * 4
                else:                                                            # a flat circle of flying chips
                    cx = int(px + math.cos(angle) * dist) // 4 * 4
                    cy = int(py + math.sin(angle) * dist) // 4 * 4
                pygame.draw.rect(surface, (150, 134, 120), (cx, cy, 4, 4))
