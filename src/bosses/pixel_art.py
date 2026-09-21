"""
pixel_art.py - Tiny toolkit for drawing retro pixel art from text.

HOW IT WORKS
    A sprite is a list of strings. Every character is one pixel:

        "..GG.."        '.' = transparent
        ".GggG."        any other letter = a colour looked up in a PALETTE dict

    Sprites are painted onto a small "logical" canvas (for example 52x50 pixels)
    and then scaled up with NEAREST-NEIGHBOUR (no blurring), so every logical
    pixel becomes a crisp SCALE x SCALE block. That is the classic retro look.

The functions here know nothing about bosses, so any teammate can reuse them
for minions, projectiles, items, etc.
"""
import pygame

TRANSPARENT = "."


def mirror(rows):
    """Turn a left half into a full symmetrical sprite (each row + its reverse)."""
    return [row + row[::-1] for row in rows]


class Canvas:
    """A small logical canvas you paint pixels on, then scale up once."""

    def __init__(self, width, height):
        self.width = width
        self.height = height
        self.pixels = {}                     # (x, y) -> (r, g, b)

    def put(self, x, y, color):
        if 0 <= x < self.width and 0 <= y < self.height:
            self.pixels[(x, y)] = color

    def paint(self, rows, palette, left, top, flip=False):
        """Paint a text sprite with its top-left corner at (left, top)."""
        for dy, row in enumerate(rows):
            if flip:
                row = row[::-1]
            for dx, ch in enumerate(row):
                if ch == TRANSPARENT:
                    continue
                color = palette.get(ch)
                if color is not None:
                    self.put(left + dx, top + dy, color)

    def paint_centered(self, rows, palette, center_x, top, inner=0):
        """
        Paint one HALF of a symmetrical sprite on both sides of center_x.
        `rows` are written outer edge -> centre line. `inner` is how many pixels
        from the centre line the last character sits (0 = touching the centre).
        """
        for dy, row in enumerate(rows):
            for i, ch in enumerate(reversed(row)):
                if ch == TRANSPARENT:
                    continue
                color = palette.get(ch)
                if color is None:
                    continue
                dist = inner + i
                self.put(center_x - 1 - dist, top + dy, color)   # left side
                self.put(center_x + dist, top + dy, color)        # right side

    def outline(self, color):
        """Add a 1-pixel outline around everything painted so far."""
        edge = []
        for (x, y) in self.pixels:
            for nx, ny in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
                if (nx, ny) not in self.pixels:
                    edge.append((nx, ny))
        for nx, ny in edge:
            self.put(nx, ny, color)

    def silhouette(self, color):
        """Recolour every painted pixel (used for the white 'I was hit' flash)."""
        self.pixels = {pos: color for pos in self.pixels}

    def to_surface(self, scale):
        """Scale up with hard pixel edges and return a per-pixel-alpha Surface."""
        small = pygame.Surface((self.width, self.height), pygame.SRCALPHA)
        for (x, y), color in self.pixels.items():
            small.set_at((x, y), color)
        return pygame.transform.scale(small, (self.width * scale, self.height * scale))


def dither_disc(canvas, cx, cy, radius, color, phase=0):
    """
    Fill a circle with a checkerboard pattern. Dithering is how old consoles
    faked transparency / glow without real alpha.
    """
    r2 = radius * radius
    for y in range(cy - radius, cy + radius + 1):
        for x in range(cx - radius, cx + radius + 1):
            if (x - cx) ** 2 + (y - cy) ** 2 <= r2 and (x + y + phase) % 2 == 0:
                canvas.put(x, y, color)


def validate_rows(name, rows, width=None):
    """Raise a helpful error if a sprite has rows of different lengths."""
    if width is None:
        width = len(rows[0])
    for i, row in enumerate(rows):
        if len(row) != width:
            raise ValueError(f"{name}: row {i} is {len(row)} chars wide, expected {width}: {row!r}")


# ----------------------------------------------------------------------
# Retro effects
# ----------------------------------------------------------------------
_BAYER4 = ((0, 8, 2, 10), (12, 4, 14, 6), (3, 11, 1, 9), (15, 7, 13, 5))
DISSOLVE_STEPS = 16


def dissolve_mask(width, height, level, scale):
    """
    A pixel-dissolve mask. level 16 keeps every pixel, level 0 keeps none, and
    the pixels vanish in a classic ordered-dither pattern in between.
    Use it with:  layer.blit(mask, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
    """
    small = pygame.Surface((width, height), pygame.SRCALPHA)
    for y in range(height):
        for x in range(width):
            if _BAYER4[y % 4][x % 4] < level:
                small.set_at((x, y), (255, 255, 255, 255))
    return pygame.transform.scale(small, (width * scale, height * scale))


def draw_dotted_line(surface, start, end, color, dot=4, gap=12):
    """A dotted line made of square 'pixels', snapped to the pixel grid."""
    (x0, y0), (x1, y1) = start, end
    length = max(1.0, ((x1 - x0) ** 2 + (y1 - y0) ** 2) ** 0.5)
    steps = int(length // gap)
    for i in range(steps + 1):
        t = i * gap / length
        x = int((x0 + (x1 - x0) * t) // dot) * dot
        y = int((y0 + (y1 - y0) * t) // dot) * dot
        pygame.draw.rect(surface, color, (x, y, dot, dot))


def draw_pixel_ring(surface, center, radius, color, dot=4, count=20):
    """A ring of square pixels (a retro stand-in for a circle outline)."""
    import math
    cx, cy = center
    for i in range(count):
        a = math.tau * i / count
        x = int((cx + math.cos(a) * radius) // dot) * dot
        y = int((cy + math.sin(a) * radius) // dot) * dot
        pygame.draw.rect(surface, color, (x, y, dot, dot))
