"""
A tiny fake 'pygame' used ONLY when real pygame isn't installed, so the boss
logic can still be tested. If you have pygame installed, the real one is used.
"""
import sys
import types
from unittest.mock import MagicMock


class Rect:
    def __init__(self, x, y, width, height):
        self.x, self.y, self.width, self.height = x, y, width, height

    @property
    def centerx(self):
        return self.x + self.width // 2

    @property
    def centery(self):
        return self.y + self.height // 2

    @property
    def center(self):
        return (self.centerx, self.centery)

    @center.setter
    def center(self, value):
        self.x = value[0] - self.width // 2
        self.y = value[1] - self.height // 2


class Surface:
    def __init__(self, size=(0, 0), flags=0):
        self.size = size

    def get_width(self):
        return self.size[0]

    def get_height(self):
        return self.size[1]

    def blit(self, *args, **kwargs):
        pass

    def fill(self, *args, **kwargs):
        pass

    def set_alpha(self, *args, **kwargs):
        pass

    def set_at(self, *args, **kwargs):
        pass


class Font:
    def __init__(self, name=None, size=20):
        self.size = size

    def render(self, text, antialias, color):
        return Surface((len(text) * 8, self.size))


def install():
    module = types.ModuleType("pygame")
    module.Rect = Rect
    module.Surface = Surface
    module.SRCALPHA = 65536
    module.BLEND_RGBA_MULT = 8
    module.draw = MagicMock()
    module.image = MagicMock()
    module.transform = MagicMock()
    module.font = types.SimpleNamespace(init=lambda: None, Font=Font)
    sys.modules["pygame"] = module
