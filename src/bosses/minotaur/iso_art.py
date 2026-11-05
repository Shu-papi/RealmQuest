"""
iso_art.py - The isometric Labyrinth chamber.

It reuses the top-down floor picture (tiles, cracks, the labyrinth mosaic) by turning it 45 degrees
and squashing it, then adds what an isometric room needs: tall brick walls on the two BACK edges
(with the portcullis gate and the banners), and the stone edge of the floor slab at the FRONT.

Everything is built once; only the torch flames move each frame.
"""
import math

import pygame

WINDOW = (960, 640)
FLOOR_TILE_SHADE = (18, 14, 26)


class IsoArenaArt:
    WALL_H = 100                   # how tall the back walls stand on screen
    SLAB = 26                      # how thick the floor slab looks at the front edges

    def __init__(self, flat, view, bounds=(40, 110, 920, 600), torch_columns=(144, 336, 624, 816),
                 side_torches=(244, 484)):
        """flat = the top-down ArenaArt (floor + wall strip pictures), view = an IsoView."""
        self.flat = flat
        self.view = view
        self.bounds = bounds
        self.torches = []                                   # screen positions of the flame bases
        self._torch_columns = torch_columns
        self._side_torches = side_torches
        self.background = self._build()
        self.vignette = flat.vignette

    # ------------------------------------------------------------------ drawing the room
    def _build(self):
        view, (left, top, right, bottom) = self.view, self.bounds
        bg = pygame.Surface(WINDOW)
        for y in range(WINDOW[1]):                          # a dark void around the room, a little lighter low down
            shade = y // 70
            pygame.draw.line(bg, (6 + shade, 5 + shade, 12 + shade * 2), (0, y), (WINDOW[0], y))
        A, B, C, D = view.corners(self.bounds)              # top, right, bottom, left corners on screen
        H, S = self.WALL_H, self.SLAB

        self._slab(bg, B, C, (50, 44, 68), 0.55)            # front-right face
        self._slab(bg, D, C, (38, 33, 54), 0.40)            # front-left face

        floor = pygame.Surface((right - left, bottom - top), pygame.SRCALPHA)
        floor.blit(self.flat.background, (0, 0), pygame.Rect(left, top, right - left, bottom - top))
        flat_floor, position = view.flatten(floor, (left, top))
        bg.blit(flat_floor, position)

        self._wall_shadows(bg, A, B, D)
        self._north_wall(bg, A, B, H)
        self._west_wall(bg, A, D, H)
        self._torch_spots(bg, A, B, D, H)
        pygame.draw.line(bg, (20, 16, 28), (A[0], A[1]), (A[0], A[1] - H), 3)      # the corner post
        return bg

    def _slab(self, bg, p, q, colour, light):
        """The side of the floor slab along the edge p-q: stone blocks."""
        S = self.SLAB
        points = [p, q, (q[0], q[1] + S), (p[0], p[1] + S)]
        pygame.draw.polygon(bg, colour, points)
        steps = max(2, int(abs(q[0] - p[0]) // 34))
        for i in range(steps + 1):                           # vertical joints between the stones
            t = i / steps
            x = p[0] + (q[0] - p[0]) * t
            y = p[1] + (q[1] - p[1]) * t
            pygame.draw.line(bg, tuple(int(c * 0.6) for c in colour), (x, y), (x, y + S), 2)
        pygame.draw.line(bg, tuple(min(255, int(c + 40 * light)) for c in colour), p, q, 2)     # lit top edge
        pygame.draw.line(bg, tuple(int(c * 0.55) for c in colour), (p[0], p[1] + S), (q[0], q[1] + S), 2)

    def _wall_shadows(self, bg, A, B, D):
        """A soft dark band on the floor where the walls meet it."""
        k = self.view.k
        layer = pygame.Surface(WINDOW, pygame.SRCALPHA)
        for width, alpha in ((22, 40), (14, 55), (7, 70)):
            n = (-width * k, width * k * 0.5)               # one step "into the room" from the north wall
            w = (width * k, width * k * 0.5)                # ...and from the west wall
            pygame.draw.polygon(layer, (0, 0, 0, alpha), [A, B, (B[0] + n[0], B[1] + n[1]), (A[0] + n[0], A[1] + n[1])])
            pygame.draw.polygon(layer, (0, 0, 0, alpha), [A, D, (D[0] + w[0], D[1] + w[1]), (A[0] + w[0], A[1] + w[1])])
        bg.blit(layer, (0, 0))

    def _shear_blit(self, bg, texture, x0, y_bottom_at_x0, slope, height):
        """Draw a flat picture as a wall slanting down the screen, one column at a time."""
        for i in range(texture.get_width()):
            y = int(round(y_bottom_at_x0 - height + i * slope))
            bg.blit(texture, (int(round(x0)) + i, y), pygame.Rect(i, 0, 1, height))

    def _north_wall(self, bg, A, B, H):
        """The back wall along the north edge: the top-down wall strip (bricks, gate, banners) stood upright."""
        width = int(round(B[0] - A[0]))
        strip = pygame.Surface((880, 112))
        strip.blit(self.flat.background, (0, 0), pygame.Rect(40, 0, 880, 112))
        texture = pygame.transform.scale(strip, (width, H))
        self._shear_blit(bg, texture, A[0], A[1], (B[1] - A[1]) / (B[0] - A[0]), H)
        cap = [(A[0], A[1] - H), (B[0], B[1] - H), (B[0], B[1] - H + 7), (A[0], A[1] - H + 7)]
        pygame.draw.polygon(bg, (92, 84, 112), cap)
        pygame.draw.line(bg, (122, 112, 146), (A[0], A[1] - H), (B[0], B[1] - H), 2)
        pygame.draw.line(bg, (14, 11, 20), A, B, 2)

    def _west_wall(self, bg, A, D, H):
        """The back wall along the west edge: fresh brick, a little darker (it faces a different way)."""
        width = int(round(A[0] - D[0]))
        brick = type(self.flat)._brick
        lo = pygame.Surface((width // 4 + 1, H // 4))
        for y in range(lo.get_height()):
            for x in range(lo.get_width()):
                lo.set_at((x, y), brick(x + 3, y + 2))
        texture = pygame.transform.scale(lo, (lo.get_width() * 4, H))
        texture.fill((214, 208, 222), special_flags=pygame.BLEND_RGB_MULT)
        slope = (A[1] - D[1]) / (A[0] - D[0])
        self._shear_blit(bg, texture, D[0], D[1], slope, H)
        pygame.draw.polygon(bg, (80, 73, 100), [(D[0], D[1] - H), (A[0], A[1] - H), (A[0], A[1] - H + 7), (D[0], D[1] - H + 7)])
        pygame.draw.line(bg, (112, 103, 136), (D[0], D[1] - H), (A[0], A[1] - H), 2)
        pygame.draw.line(bg, (14, 11, 20), D, A, 2)

    def _torch_spots(self, bg, A, B, D, H):
        """Where the flames burn: on the north wall (brackets are already in its picture) and the west wall."""
        view = self.view
        top = self.bounds[1]
        left = self.bounds[0]
        for wx in self._torch_columns:                      # the bracket in the wall strip sits 43 px above the wall's foot
            px, py = view.project(wx, top)
            self.torches.append((px, py - 43))
        for wy in self._side_torches:
            px, py = view.project(left, wy)
            base = (px, py - 52)
            pygame.draw.rect(bg, (34, 30, 42), (base[0] - 3, base[1], 7, 20))
            pygame.draw.rect(bg, (66, 60, 78), (base[0] - 2, base[1], 4, 20))
            pygame.draw.rect(bg, (66, 60, 78), (base[0] - 6, base[1] + 2, 12, 4))
            self.torches.append(base)

    def draw_torches(self, surface, clock):
        self.flat.draw_torches(surface, clock, self.torches)
