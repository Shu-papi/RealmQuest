"""STAND-IN: the real Lich King is not part of this partial PR. This only lets `bosses/__init__.py` import.
Keep your real bosses/lich_king/ and delete this file."""
from .base_boss import Boss


class LichKing(Boss):
    def __init__(self, x=480, y=230, seed=None):
        super().__init__("Lich King", 300, x, y, 40, seed=seed)

    def update_ai(self, dt, player, bounds):
        pass
