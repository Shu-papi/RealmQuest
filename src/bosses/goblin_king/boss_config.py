"""
Goblin King boss configuration.
Edit the values here; goblin_king.py reads everything from this file.
"""

# ====================== FILES ======================
# These PNGs live in assets/bosses/goblin_king/ (repo root)
SHEET         = "Vargut_Actions.png"                     # idle / walk
HEAVY_SHEET   = "Vargut-asm_axe_berserker_rush-v2.png"   # heavy attack
SPECIAL_SHEET = "Vargut-asm_axe_critical_cleave-v2.png"  # special attack

# ====================== LOOK ======================
PIXELATE     = False   # True = pixelate all boss sprites
PIXELATE_BASE = True   # Keep idle and walking sprites crisp
# Attack sheets are high-resolution art; keep their detail when scaling them down.
PIXELATE_ATTACKS = False
PIXEL_SIZE_BASE = 1    # idle/walk pixel size (higher = chunkier; use whole numbers)
PIXEL_SIZE_ATTACKS = 3 # attack pixel size (higher = chunkier)
# Preserve the source sheets' antialiased alpha edges for smoother silhouettes.
HARD_EDGES   = False
ALPHA_CUTOFF = 80     # 0-255: pixels fainter than this disappear (HARD_EDGES only)

BASE_SCALE = 5        # scale of the base sheet (48x48 frames)
AUTO_MATCH_SIZE = True   # True = heavy/special frames are scaled automatically so the
                         # boss is the same height as in idle/walk (recommended)
BIG_SCALE  = 0.82     # only used when AUTO_MATCH_SIZE is False (512x512 cells)

# ====================== SHEET LAYOUT ======================
FRAME_W, FRAME_H = 48, 48          # base sheet frame size
DIRECTION_ROWS = {"down": 0, "left": 1, "right": 2, "up": 3}

BIG_CELL   = 256                   # heavy / special sheet cell size (5 x 5 grid)
BIG_GRID   = 5                     # 5 x 5 cells
BIG_ANCHOR = (132, 229)            # boss's feet inside each big cell
FEET_OFFSET = 60                   # feet sit this many px below the boss centre

# ====================== GROUND ======================
# Ranges and attack areas are measured on the floor at the boss's feet.
# The floor is drawn squashed vertically (like a top-down RPG view):
# 1.0 = perfect circles, smaller = flatter ovals.
GROUND_SQUASH = 0.4

# ====================== INDICATORS ======================
SHOW_INDICATORS = True             # master switch for everything below
BOSS_NAME       = "Valdur"    # name shown above the boss's HP bar
ALERT_TIME      = 1.0              # seconds the "!" shows when he notices the player
TELEGRAPH_COLOR = (255, 40, 40)    # attack warning drawn on the ground

# ====================== HURT FLASH ======================
HURT_FLASH_TIME = 0.2              # seconds the boss stays red after being hit
HURT_TINT = (255, 70, 70)          # colour multiplied onto the sprite (lower G/B = redder)

# ====================== STATS ======================
MAX_HP     = 2500
WALK_SPEED = 50                    # pixels per second

# Aggro: the boss stays idle until the player gets inside AGGRO_RANGE (px).
# After that he is triggered and keeps chasing and attacking, even if the
# player runs outside the range again.
AGGRO_RANGE  = 300
FORGET_RANGE = None                # None = never gives up. Or a distance, e.g. 700,
                                   # past which he loses interest and goes idle again.

# Attack trigger distances (px)
HEAVY_TRIGGER_RANGE   = 150
SPECIAL_TRIGGER_RANGE = 250

# Cooldowns (seconds)
HEAVY_COOLDOWN            = 7.0
SPECIAL_COOLDOWN          = 8.0
SPECIAL_COOLDOWN_ENRAGED  = 6.0    # used when HP is below ENRAGE_HP_FRACTION
ENRAGE_HP_FRACTION        = 0.5
START_HEAVY_COOLDOWN      = 6.0    # delay before the first heavy attack
START_SPECIAL_COOLDOWN    = 6.0    # delay before the first special

# ====================== PHASE 2 ======================
# At PHASE2_HP_FRACTION of his HP he stops, roars and calls in his minions (once).
# He can't be hurt while he roars (SUMMON_TIME seconds). In the game, the room spawns
# PHASE2_SUMMONS around him: "minion", "shaman", "slime", "boar", or "extra" (a random
# minion / slime / boar). Standalone demo: he just roars, nobody comes.
PHASE2_HP_FRACTION = 0.5
SUMMON_TIME        = 1.2
PHASE2_SPEED_K     = 1.2          # walk speed x this in phase 2
PHASE2_SUMMONS     = ["minion", "minion", "shaman", "extra"]
SUMMON_RING        = 110          # px from his feet where the minions appear
SUMMON_COLOR       = (120, 230, 90)

# ====================== ANIMATIONS ======================
# frames : column numbers in the sheet, played in order (repeat a column to hold it longer)
# fps    : animation speed (lower = slower)
# once   : True = play one time then return to idle
# hits   : {frame position: (reach in px, damage, arc in degrees)}
#          frame position = place in the frames list, counting from 0
#          arc = how wide the cone is in front of the boss (360 = all around him)
# dash   : (first frame, last frame, speed) boss moves toward the player

ANIMS = {
    "idle":   {"frames": [9, 10, 11],   "fps": 4,  "once": False},
    "walk":   {"frames": [0, 1, 2], "fps": 8,  "once": False},
}

# Heavy attack: Berserker Rush
HEAVY = {
    "frames": list(range(0, 18)),
    "fps": 12,
    "once": True,
    "hits": {12: (120, 100, 120)},  # overhead slam, 120 degree cone
    "dash": (5, 9, 220),           # rush forward
}

# Special attack: Critical Cleave
SPECIAL = {
    "frames": list(range(0, 21)),
    "fps": 12,
    "once": True,
    "hits": {5: (170, 20, 360),    # tornado spin (all around him)
             12: (150, 120, 120)},  # ground slam, 120 degree cone
    "dash": (7, 10, 260),          # jump toward the player
}
# Sounds (assets/sfx/, names from src/maps/sfx.py FILE_SOUNDS): attack -> {frame: sound}.
# The swing starts two frames before a hit so the whoosh leads into it.
SOUNDS = {
    "heavy": {10: "king_swing", 12: "king_slam"},
    "special": {3: "king_swing", 10: "king_swing", 12: "king_slam"},
}

# ====================== IN THE GAME ======================
# The dungeon fight (src/maps) uses these instead of the numbers above, so the
# boss matches the game's scale: the hero has ~40-60 HP and hits for ~2-10.
IN_GAME = {
    "base_scale": 3,          # sprite size (about 2.5x the hero)
    "dist_k": 0.6,            # ranges, attack reach and dash distances x this
    "squash": 1.0,            # the dungeon is seen from above: hit areas are round
    "max_hp": 110,
    "speed": 70,
    "overhead": False,        # the game draws his name + HP bar at the top of the screen
    "damage": {"heavy": {12: 7},              # overhead slam
               "special": {5: 4, 12: 8}},     # tornado spin, ground slam
}
