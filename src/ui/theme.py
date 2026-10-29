"""
theme.py - Shared colours and sizes for every screen in src/ui/ (menu, settings, inventory).

Style: dark stone dungeon, with wood and brass only on edges, and warm torch-orange
for whatever is selected. These colours match the pictures in assets/ui/ and are
also used for the plain-shape fallback when a picture is missing.
"""

SCREEN_W, SCREEN_H = 960, 640       # same size as the bosses team's test arena

# fonts: (file in assets/ui/fonts/, size). Change these to try other fonts.
FONT_TITLE = ("Jersey10-Regular.ttf", 70)
FONT_BUTTON = ("Jersey10-Regular.ttf", 40)
FONT_SMALL = ("Silkscreen-Regular.ttf", 16)
FONT_HUD = ("Jersey10-Regular.ttf", 28)
FONT_LABEL = ("Jersey10-Regular.ttf", 30)

# stone, wood and brass
STONE = (52, 54, 64)
STONE_DARK = (30, 31, 39)
STONE_LIGHT = (78, 80, 92)
PANEL = (24, 25, 33)
WOOD = (104, 62, 32)
WOOD_DARK = (64, 36, 18)
BRASS = (214, 158, 52)
OUTLINE = (10, 8, 8)

# torch accents (selected things)
TORCH = (240, 140, 30)
TORCH_LIGHT = (255, 196, 80)

# text
TEXT = (246, 236, 216)
TEXT_DIM = (178, 168, 150)
TEXT_SHADOW = (10, 8, 8)
TITLE = (255, 238, 196)             # cream, painted on the wooden sign
TITLE_SHADOW = (58, 28, 10)          # dark brown outline

# fallback night scene (only used if assets/ui/menu_bg.png is missing)
SKY = [(8, 10, 24), (12, 14, 32), (16, 18, 40), (20, 22, 48), (26, 28, 56)]
STAR = (210, 214, 236)
MOON = (226, 220, 190)
FOREST = (14, 30, 24)
GRASS = (22, 44, 30)
