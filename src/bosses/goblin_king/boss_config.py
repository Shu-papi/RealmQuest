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
    "hits": {12: (170, 100, 120)},  # overhead slam, 120 degree cone
    "dash": (5, 9, 220),           # rush forward
}

# Special attack: Critical Cleave
SPECIAL = {
    "frames": list(range(0, 21)),
    "fps": 12,
    "once": True,
    "hits": {5: (250, 20, 360),    # tornado spin (all around him)
             12: (230, 120, 120)},  # ground slam, 120 degree cone
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


# ======================================================================================================
# CONFIG FILE: config/bosses/goblin_king.toml sets the numbers above (src/balance.py).
# ======================================================================================================
try:
    import balance as _balance                              # src/ is on the path
except ImportError:
    try:
        from src import balance as _balance
    except ImportError:                                     # standalone demo (no src/ on the path): defaults
        _balance = None

_DAMAGE = {"slam_damage": ("heavy", 12), "spin_damage": ("special", 5), "ground_slam_damage": ("special", 12)}
_DUNGEON = ("max_hp", "speed", "dist_k", "base_scale")


def _get_dungeon():
    out = {k: IN_GAME[k] for k in _DUNGEON}
    out.update({k: IN_GAME["damage"][a][f] for k, (a, f) in _DAMAGE.items()})
    return out


_REACH = {"slam_reach": ("heavy", HEAVY, 12), "spin_reach": ("special", SPECIAL, 5),
          "ground_slam_reach": ("special", SPECIAL, 12)}


def _reach_prop(key):
    """A config line for one hit's reach: the first number of its (reach, damage, arc) tuple."""
    _, anim, frame = _REACH[key]

    def get():
        return anim["hits"][frame][0]

    def put(v):
        _, d, arc = anim["hits"][frame]
        anim["hits"][frame] = (v, d, arc)
    return _balance.Prop(get, put)


def _set_dungeon(table):
    for k in _DUNGEON:
        IN_GAME[k] = table[k]
    for k, (a, f) in _DAMAGE.items():
        IN_GAME["damage"][a][f] = table[k]


if _balance is not None:
    _balance.declare(
        "bosses", "goblin_king", "VALDUR, THE GOBLIN KING",
        "Boss of the Goblin Dungeon (floor 1-3). Ranges are in arena pixels: in the dungeon they are x [dungeon] dist_k.",
        globals(),
        {"aggro_range": "AGGRO_RANGE", "heavy_trigger_range": "HEAVY_TRIGGER_RANGE",
         "special_trigger_range": "SPECIAL_TRIGGER_RANGE", "heavy_cooldown": "HEAVY_COOLDOWN",
         "special_cooldown": "SPECIAL_COOLDOWN", "special_cooldown_enraged": "SPECIAL_COOLDOWN_ENRAGED",
         "enrage_hp_fraction": "ENRAGE_HP_FRACTION", "start_heavy_cooldown": "START_HEAVY_COOLDOWN",
         "start_special_cooldown": "START_SPECIAL_COOLDOWN", "phase2_hp_fraction": "PHASE2_HP_FRACTION",
         "summon_time": "SUMMON_TIME", "phase2_speed_k": "PHASE2_SPEED_K", "phase2_summons": "PHASE2_SUMMONS",
         "summon_ring": "SUMMON_RING",
         **{k: _reach_prop(k) for k in _REACH},
         "dungeon": _balance.Prop(_get_dungeon, _set_dungeon)},
        docs={"aggro_range": "He wakes when the hero comes this close.",
              "heavy_trigger_range": "He uses Berserker Rush (overhead slam) when the hero is this close.",
              "special_trigger_range": "He uses Critical Cleave (spin + slam) when the hero is this close.",
              "heavy_cooldown": "Seconds between Berserker Rushes.",
              "special_cooldown": "Seconds between Critical Cleaves.",
              "special_cooldown_enraged": "...when he is below enrage_hp_fraction of his health.",
              "enrage_hp_fraction": "Below this share of his health he cleaves more often.",
              "start_heavy_cooldown": "Seconds before his first Berserker Rush.",
              "start_special_cooldown": "Seconds before his first Critical Cleave.",
              "phase2_hp_fraction": "At this share of his health he roars and calls his minions (once).",
              "summon_time": "Seconds he roars (can't be hurt meanwhile).",
              "phase2_speed_k": "His walk speed x this in phase 2.",
              "phase2_summons": "Who comes: \"minion\", \"shaman\", \"slime\", \"boar\" or \"extra\" (a random one).",
              "summon_ring": "How far from him they appear (pixels).",
              "slam_reach": "How far Berserker Rush's overhead slam reaches (arena px, x dist_k in the dungeon).",
              "spin_reach": "How far Critical Cleave's tornado spin reaches, all around him.",
              "ground_slam_reach": "How far Critical Cleave's ground slam reaches.",
              "dungeon": "In the dungeon: max_hp, speed (px/s), dist_k (ranges x this), base_scale (sprite size), "
                         "and the damage of his slam, his tornado spin and his ground slam."})
