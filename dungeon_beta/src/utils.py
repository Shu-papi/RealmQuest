import os
import math
import pygame

_IMAGE_CACHE = {}


def load_image(path, size=None, fallback_color=(255, 0, 255), fallback_shape="rect"):
    """
    Loads an image from disk. If the file doesn't exist yet (you haven't
    dropped your sprite in), returns a simple placeholder surface instead
    of crashing, so the game always runs.
    """
    cache_key = (path, size)
    if cache_key in _IMAGE_CACHE:
        return _IMAGE_CACHE[cache_key]

    surface = None
    if os.path.isfile(path):
        try:
            surface = pygame.image.load(path).convert_alpha()
            if size:
                surface = pygame.transform.smoothscale(surface, size)
        except pygame.error:
            surface = None

    if surface is None:
        w, h = size if size else (48, 48)
        surface = pygame.Surface((w, h), pygame.SRCALPHA)
        if fallback_shape == "circle":
            pygame.draw.circle(surface, fallback_color, (w // 2, h // 2), min(w, h) // 2)
        else:
            pygame.draw.rect(surface, fallback_color, (0, 0, w, h), border_radius=6)
        pygame.draw.rect(surface, (0, 0, 0), (0, 0, w, h), width=2, border_radius=6)

    _IMAGE_CACHE[cache_key] = surface
    return surface


def load_sound(path):
    if os.path.isfile(path):
        try:
            return pygame.mixer.Sound(path)
        except pygame.error:
            return None
    return None


def vec_to(a, b):
    return (b[0] - a[0], b[1] - a[1])


def length(v):
    return math.hypot(v[0], v[1])


def normalize(v):
    l = length(v)
    if l == 0:
        return (0, 0)
    return (v[0] / l, v[1] / l)


def distance(a, b):
    return math.hypot(a[0] - b[0], a[1] - b[1])
