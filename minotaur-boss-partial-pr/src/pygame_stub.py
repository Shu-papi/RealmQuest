"""
STAND-IN (the tests import this when pygame is not installed): just enough of pygame for the boss LOGIC tests
(movement, skills, damage, sounds) to run. Drawing and the real-window tests are skipped (`needs_pygame`).
For the full suite and the playable arena:  pip install pygame-ce
"""
import sys
import types
from unittest import mock


class Rect:
    def __init__(self, x=0, y=0, w=0, h=0):
        self.x, self.y, self.width, self.height = x, y, w, h

    @property
    def center(self):
        return (self.x + self.width // 2, self.y + self.height // 2)

    @center.setter
    def center(self, value):
        self.x, self.y = value[0] - self.width // 2, value[1] - self.height // 2

    w = property(lambda s: s.width)
    h = property(lambda s: s.height)


class _Module(types.ModuleType):
    def __getattr__(self, name):
        if name.startswith("__") or name == "get_sdl_version":      # so tests can tell this is NOT real pygame
            raise AttributeError(name)
        value = mock.MagicMock(name="pygame." + name)
        setattr(self, name, value)
        return value


def install():
    if "pygame" in sys.modules and hasattr(sys.modules["pygame"], "get_sdl_version"):
        return
    module = _Module("pygame")
    module.Rect = Rect
    module.mixer = types.SimpleNamespace(get_init=lambda: None)     # no audio
    sys.modules["pygame"] = module
