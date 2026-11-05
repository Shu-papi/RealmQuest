"""
Goblin King's monsters: sprite sheet layout and starter stats.
Every sheet has 3 rows x 4 frames. Row 0 = idle, row 1 = move, row 2 = attack.
The stats below are PLACEHOLDERS (my assumptions) - change them once you decide
how the monsters should play.
"""

import os

# Sheets live in assets/monsters/goblin_army/ (repo root)
ASSET_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
                         "assets", "monsters", "goblin_army")

FRAMES_PER_ROW = 4
ROWS = {"idle": 0, "move": 1, "attack": 2}
FPS = {"idle": 4, "move": 8, "attack": 8}

# sheet = file name inside ASSET_DIR
# Frame size = size of ONE frame in the sheet (the sheet is 4 frames wide, 3 rows tall).
# facing: "front" = faces the camera, "right" = side view facing right (mirror it for left)
MONSTERS = {
    "goblin_general": {
        "sheet": "goblin_general_sheet.png", "frame": (48, 48), "facing": "front",
        "hp": 220, "speed": 55, "aggro_range": 260,
        "attack": {"name": "sword slash", "damage": 18, "reach": 60, "cooldown": 2.0},
    },
    "giant_boar": {
        "sheet": "giant_boar_sheet.png", "frame": (72, 48), "facing": "right",
        "hp": 160, "speed": 75, "aggro_range": 300,
        "attack": {"name": "charge", "damage": 20, "reach": 220, "cooldown": 5.0,
                   "charge_speed": 260},
    },
    "slime_blue": {
        "sheet": "slime_blue_sheet.png", "frame": (32, 32), "facing": "front",
        "hp": 40, "speed": 35, "aggro_range": 180,
        "attack": {"name": "splash", "damage": 6, "reach": 36, "cooldown": 1.5,
                   "effect": "slow"},
    },
    "slime_red": {
        "sheet": "slime_red_sheet.png", "frame": (32, 32), "facing": "front",
        "hp": 40, "speed": 35, "aggro_range": 180,
        "attack": {"name": "ember burst", "damage": 6, "reach": 36, "cooldown": 1.5,
                   "effect": "burn"},
    },
    "slime_green": {
        "sheet": "slime_green_sheet.png", "frame": (32, 32), "facing": "front",
        "hp": 40, "speed": 35, "aggro_range": 180,
        "attack": {"name": "acid spit", "damage": 6, "reach": 36, "cooldown": 1.5,
                   "effect": "poison"},
    },
}
