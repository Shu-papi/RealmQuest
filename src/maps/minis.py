"""
minis.py - the six mini dungeons (caves and ruins) scattered around the vale.

Mini dungeons are short (one floor, about six rooms) and replayable: a new random
layout every visit, XP and gold every time, and a bigger reward the first time
the lair is cleared. They are where Himmel grows strong enough for the main dungeons.

    num      dungeon number used for the floor name ("<num>-1")
    family   which monsters live there: 1 goblins (forest), 2 berserkers (ruins),
             3 the dead (underworld). Also picks the tile theme.
    tier     XP / gold multiplier
"""

MINIS = [
    dict(id="burrow", num=11, name="Mossy Burrow", family=1, tier=1, level="Lv 1-3",
         pos=(430, 2080), color=(130, 210, 90)),
    dict(id="thorn_den", num=12, name="Thornwood Den", family=1, tier=1, level="Lv 2-4",
         pos=(1050, 2230), color=(170, 220, 80)),
    dict(id="watchtower", num=13, name="Old Watchtower", family=2, tier=2, level="Lv 4-7",
         pos=(1220, 2860), color=(230, 170, 110)),
    dict(id="crypt", num=14, name="Sunken Crypt", family=2, tier=2, level="Lv 5-8",
         pos=(2780, 2840), color=(210, 140, 120)),
    dict(id="ash_pit", num=15, name="Ashen Pit", family=3, tier=3, level="Lv 8-11",
         pos=(3740, 760), color=(255, 110, 70)),
    dict(id="bone_hollow", num=16, name="Bone Hollow", family=3, tier=3, level="Lv 9-12",
         pos=(3960, 1780), color=(200, 170, 255)),
]
for _m in MINIS:
    _m.update(mini=True, requires=None, min_level=1)

MINI_BY_ID = {m["id"]: m for m in MINIS}
MINI_BY_NUM = {m["num"]: m for m in MINIS}
FIRST_CLEAR_XP = 40          # x tier, the first time a lair falls
FIRST_CLEAR_GOLD = 30        # x tier


def is_mini_floor(floor_name: str) -> bool:
    return int(floor_name.split("-")[0]) in MINI_BY_NUM
