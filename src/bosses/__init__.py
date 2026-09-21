"""
RealmQuest boss package (real-time, Pygame).

    from bosses import get_boss, list_bosses      # or: from src.bosses import ...
    from bosses import LichKing

    boss = get_boss("lich_king", x=480, y=230)

    # every frame:
    boss.update(dt, player, (left, top, right, bottom))
    boss.draw(screen)
    boss.draw_health_bar(screen, font)

    # when the player swings a sword or casts a spell:
    for target in boss.hittables():
        ...check distance...
        target.take_damage(20)

Each boss lives in its own folder (src/bosses/<name>/). To add one, see
HOW_TO_ADD_A_BOSS.md. Only the two lines marked ADD HERE change in this file.
"""
from .base_boss import Boss
from .lich_king import LichKing            # ADD HERE (1/2): import your boss

BOSSES = {
    "lich_king": LichKing,
    # ADD HERE (2/2): "dragon": Dragon,
}


def get_boss(name, x=480, y=230):
    if name not in BOSSES:
        raise ValueError(f"Unknown boss '{name}'. Choose from: {list(BOSSES)}")
    return BOSSES[name](x=x, y=y)


def list_bosses():
    return list(BOSSES)
