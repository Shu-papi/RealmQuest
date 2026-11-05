"""
view.py - How the floor (world x, y) turns into pixels on the screen.

The fight itself (distances, hit circles, speeds) always happens on a flat floor with x going
right and y going down, exactly like a top-down game. A VIEW only decides where things are DRAWN:

    TopDownView   what you see is the floor: screen (x, y) = world (x, y). This is the normal
                  flat arena. By default (four_way=True) the BOSS is still drawn isometric-style:
                  he faces one of four diagonal directions, showing his back when he looks
                  up the screen. Pass four_way=False for the old plain left/right flip.
    IsoView       an optional isometric ROOM (2:1 "dimetric"): the floor is turned 45 degrees and
                  squashed in half, so the arena becomes a diamond and circles become 2:1
                  ellipses. Upright things are drawn as sprites standing on their spot.

Because only drawing changes, every attack plays exactly the same in every view.

Isometric directions (screen):
    world +x  goes down-right        world +y  goes down-left
    so "up the screen" is world (-1, -1) and "down the screen" is world (+1, +1).
"""
import math

import pygame


class TopDownView:
    name = "topdown"
    iso = False                  # True = the floor itself is drawn isometric (IsoView)
    four_way = True              # True = the boss faces 4 diagonal directions (front/back views)

    def __init__(self, four_way=True):
        self.four_way = four_way

    def project(self, x, y):
        return float(x), float(y)

    def unproject(self, sx, sy):
        return float(sx), float(sy)

    def to_world(self, mx, my):
        """Keyboard direction (right = +x, down = +y on the SCREEN) as a world direction."""
        return float(mx), float(my)

    def screen_dir(self, dx, dy):
        """A world direction as it appears on the screen."""
        return float(dx), float(dy)

    def screen_move(self, dx, dy):
        """How far (in screen pixels) a world movement of (dx, dy) really moves something: what the eye sees."""
        return float(dx), float(dy)

    def sprite_origin(self, x, y, foot_y):
        """Where to hand a sprite whose feet are `foot_y` pixels below its centre, so it stands on (x, y)."""
        sx, sy = self.project(x, y)
        return sx, sy

    def depth(self, x, y):
        return y

    def flatten(self, layer, world_origin=(0, 0)):
        """A flat layer drawn in world coordinates, as (surface, top-left) ready to blit."""
        return layer, (int(world_origin[0]), int(world_origin[1]))


class IsoView(TopDownView):
    name = "iso"
    iso = True
    four_way = True

    def __init__(self, k=0.62, world_center=(480.0, 355.0), screen_center=(480.0, 352.0)):
        self.k = k                              # screen pixels per world unit along each floor axis
        self.wx, self.wy = world_center
        self.sx0, self.sy0 = screen_center

    def project(self, x, y):
        u, v = x - self.wx, y - self.wy
        return self.sx0 + (u - v) * self.k, self.sy0 + (u + v) * self.k * 0.5

    def unproject(self, sx, sy):
        a = (sx - self.sx0) / self.k            # = u - v
        b = (sy - self.sy0) * 2.0 / self.k      # = u + v
        return self.wx + (a + b) / 2.0, self.wy + (b - a) / 2.0

    def to_world(self, mx, my):
        return float(mx + my), float(my - mx)

    def screen_dir(self, dx, dy):
        return float(dx - dy), float(dx + dy) * 0.5

    def screen_move(self, dx, dy):
        return float(dx - dy) * self.k, float(dx + dy) * self.k * 0.5

    def sprite_origin(self, x, y, foot_y):
        sx, sy = self.project(x, y)
        return sx, sy - foot_y

    def depth(self, x, y):
        return x + y

    def flatten(self, layer, world_origin=(0, 0)):
        """
        Lays a flat top-down picture onto the isometric floor: scale it, turn it 45 degrees
        clockwise, squash it to half height. Returns (surface, (left, top)) to blit.
        """
        width, height = layer.get_size()
        factor = self.k * math.sqrt(2.0)
        scaled = pygame.transform.scale(layer, (max(1, int(round(width * factor))), max(1, int(round(height * factor)))))
        turned = pygame.transform.rotate(scaled, -45)
        squashed = pygame.transform.scale(turned, (turned.get_width(), max(1, turned.get_height() // 2)))
        cx, cy = self.project(world_origin[0] + width / 2.0, world_origin[1] + height / 2.0)
        return squashed, (int(round(cx - squashed.get_width() / 2.0)), int(round(cy - squashed.get_height() / 2.0)))

    def corners(self, bounds):
        """Screen positions of the four floor corners: (top, right, bottom, left) = world (min,min), (max,min), (max,max), (min,max)."""
        left, top, right, bottom = bounds
        return (self.project(left, top), self.project(right, top),
                self.project(right, bottom), self.project(left, bottom))
