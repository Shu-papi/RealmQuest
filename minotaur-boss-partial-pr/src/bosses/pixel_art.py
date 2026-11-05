"""STAND-IN (rebuilt so the partial PR runs on its own): chunky dotted lines and rings on the pixel grid."""
import math

import pygame


def _snap(value, dot):
    return int(value) // dot * dot


def draw_dotted_line(surface, start, end, colour, gap=8, dot=4):
    """A line of square dots `gap` pixels apart."""
    (x0, y0), (x1, y1) = start, end
    length = math.hypot(x1 - x0, y1 - y0)
    steps = max(1, int(length // gap))
    for i in range(steps + 1):
        t = i / steps
        pygame.draw.rect(surface, colour, (_snap(x0 + (x1 - x0) * t, dot), _snap(y0 + (y1 - y0) * t, dot), dot, dot))


def draw_pixel_ring(surface, center, radius, colour, dot=4, count=24):
    """A ring of `count` square dots."""
    cx, cy = center
    radius = max(0.0, radius)
    for i in range(count):
        angle = math.tau * i / count
        pygame.draw.rect(surface, colour, (_snap(cx + math.cos(angle) * radius, dot),
                                           _snap(cy + math.sin(angle) * radius, dot), dot, dot))
