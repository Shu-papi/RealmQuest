"""
world_lore.py - places and stories scattered across the Oakwood overworld.

    Shrine      four ancient wayshrines that tell the valley's history
    Memorial    the Wall of Names on the eastern overlook, where the Veil is closest
    Board       Oakwood's notice board (rumours change with the story)
    SwordStump  Pip's lost wooden sword at the Old Mill
    Moonpetal   silver flowers that only bloom after dusk
    Hen         Old Bram's runaway hens
    REGIONS     named areas; the overworld shows a banner when you enter one

Landmarks are interacted with through SurfaceWorld.nearest_interactable();
what happens (dialog, quest progress) is decided by the Game.
"""
from __future__ import annotations

import math

import pygame

try:
    from . import story
    from .village import CHICKEN, Critter, _step_toward
except ImportError:
    import story
    from village import CHICKEN, Critter, _step_toward


def _shade(c, f):
    return tuple(max(0, min(255, int(v * f))) for v in c[:3])


# --------------------------------------------------------------------------- #
#  the map
# --------------------------------------------------------------------------- #
SHRINES = [   # (x, y, name, rune colour)
    (520, 1190, "Shrine of Roots", (120, 230, 140)),
    (2380, 1300, "Shrine of Dawn", (255, 210, 110)),
    (2440, 760, "Shrine of Iron", (255, 120, 80)),
    (860, 560, "Shrine of Frost", (150, 190, 255)),
]
MEMORIAL = (2230, 1600)
MILL = (560, 1460)
SWORD = (640, 1530)
BOARD = (1338, 1590)
PETALS = [(1580, 1250), (1930, 1250), (1700, 1390), (1190, 1340), (2010, 1430), (1560, 1400)]
HENS = [(700, 1770), (2160, 1390), (1120, 860)]
COOP = (1050, 1640)

REGIONS = [   # circles first, then broad fallbacks in region_at()
    ("Oakwood Village", (1400, 1680), 330, (232, 210, 150)),
    ("Goblin Hollow", (780, 1030), 300, (120, 220, 130)),
    ("Red Ridge", (2100, 930), 360, (240, 130, 100)),
    ("The Barrowlands", (1400, 360), 520, (190, 150, 255)),
    ("The Old Mill", MILL, 190, (200, 190, 160)),
    ("Veil's Edge", MEMORIAL, 200, (170, 200, 255)),
    ("Millbrook", (2230, 2800), 330, (232, 200, 120)),
    ("Silverrun Bridge", (2080, 2420), 120, (150, 190, 240)),
    ("Old Ford Bridge", (1000, 2400), 110, (150, 190, 240)),
    ("Mossy Burrow", (430, 2080), 150, (130, 210, 90)),
    ("Thornwood Den", (1050, 2230), 140, (170, 220, 80)),
    ("Old Watchtower", (1220, 2860), 160, (230, 170, 110)),
    ("Sunken Crypt", (2780, 2840), 160, (210, 140, 120)),
    ("Ashen Pit", (3740, 760), 170, (255, 110, 70)),
    ("Bone Hollow", (3960, 1780), 170, (200, 170, 255)),
]


def region_at(x, y):
    for name, (cx, cy), r, col in REGIONS:
        if (x - cx) ** 2 + (y - cy) ** 2 < r * r:
            return name, col
    if 2950 <= x and 200 <= y < 2200:
        return "The Deep Forest", (120, 200, 170)
    if y >= 2200:
        if abs(y - _river_y(x)) < 90:
            return "Silverrun River", (130, 180, 240)
        if y < _river_y(x):
            return "Thornwood" if x < 1900 else "Eastmarch Hills", (170, 210, 120)
        return "The Southfields", (220, 196, 120)
    if x < 1120:
        return "Whisperwood", (130, 200, 140)
    if x > 1880:
        return "Eastmarch Hills", (210, 200, 140)
    if y < 820:
        return "The Barrowlands", (190, 150, 255)
    return "Oakwood Vale", (170, 220, 150)


_RIVER = [(-40, 2330), (400, 2290), (800, 2380), (1000, 2400), (1300, 2350), (1700, 2440), (2080, 2420),
          (2500, 2380), (2900, 2470), (3300, 2420), (3700, 2500), (4100, 2460), (4440, 2490)]


def _river_y(x):
    for (x0, y0), (x1, y1) in zip(_RIVER, _RIVER[1:]):
        if x0 <= x <= x1:
            return y0 + (y1 - y0) * (x - x0) / (x1 - x0)
    return 2450


def reserve(big_circles):
    """Clearings that must stay free of trees and rocks."""
    for x, y, _n, _c in SHRINES:
        big_circles.append((x, y, 90))
    big_circles.append((MEMORIAL[0], MEMORIAL[1], 120))
    big_circles.append((MILL[0], MILL[1] + 20, 170))
    for x, y in PETALS:
        big_circles.append((x, y, 34))
    for x, y in HENS:
        big_circles.append((x, y, 80))


# --------------------------------------------------------------------------- #
#  text
# --------------------------------------------------------------------------- #
SHRINE = story.SHRINE
MEMORIAL_SPK = story.MEMORIAL
BOARD_SPK = story.BOARD

SHRINE_VERSES = [
    [(SHRINE, "Moss has grown into the carving, but the words are still clear:"),
     (SHRINE, "'Before the Veil, the valley was a crossroads. Caravans, pilgrims, armies. Always armies.'"),
     (SHRINE, "'When the great war came over the mountains, two masters swore the valley would not burn.'"),
     (story.HERO, "The Shrine of Roots. So the valley wasn't always closed off."),
     (story.MERLIN_STONE, "No. It used to be the busiest road in the north. Hard to believe now.")],
    [(SHRINE, "The stone is warm where the morning sun touches it:"),
     (SHRINE, "'The masters raised three stones of Thorn, Blood and Bone, and wove the sky between them.'"),
     (SHRINE, "'The war passed by and never saw the valley. For a time, the people called it a miracle.'"),
     (story.HERO, "The anchors were meant to protect the vale. What went wrong?"),
     (story.MERLIN_STONE, "Read the next stone. It says it better than I could.")],
    [(SHRINE, "Red iron has been hammered into the stone, bent into the shape of a closed gate:"),
     (SHRINE, "'The war ended. One master said: open the sky. The other said: never. The world will only hurt them again.'"),
     (SHRINE, "'The stones began to hunger. Things crawled out of them at night, and the gate stayed shut.'"),
     (story.HERO, "The one who said 'never'... that's the Veilwright."),
     (story.MERLIN_STONE, "...Yes.")],
    [(SHRINE, "Frost clings to the stone, but it melts where you touch it:"),
     (SHRINE, "'The one who wished to open the sky stayed behind, to guard the people from the cage. The other left, and watches still.'"),
     (SHRINE, "'When a hero is called from beyond, the stones will remember how to break.'"),
     (story.HERO, "Called from beyond. That's me."),
     (story.MERLIN_STONE, "That's you. I waited a very long time for these stones to be right.")],
]

MEMORIAL_LINES = [
    (MEMORIAL_SPK, "A long wall of grey stones, built right up against the shimmer of the Veil. It hums softly here."),
    (MEMORIAL_SPK, "Names are carved into every stone. Some taken by the night raids. Some who walked into the Veil and never came back."),
    (MEMORIAL_SPK, "Aldric Vane. Marta Fennick. The Brook twins. Old Tamas the bell-ringer. Tamsin. Orrin. Fenn."),
    (story.HERO, "So many names. I'll make sure no one has to add another one."),
]
LETTER_LINES = [
    (story.HERO, "I put Lisbet's letter under a flat stone, beside Aldric's name."),
    (story.HERO, "'Dear Aldric. Merlin summoned a hero. Maybe this year the sky opens. If it does, come home. - Lisbet.'"),
]

BOARD_LINES = [
    [(BOARD_SPK, "NIGHT WATCH ROTA: two at the west road, two at the plaza. Sound the horn at the first goblin. - Capt. Hale"),
     (BOARD_SPK, "LOST: three hens with red ribbons, scattered by the last raid. Answer to Gertrude, Mabel and Duchess. See Old Bram."),
     (BOARD_SPK, "NOTICE: the eastern and northern gates are sealed. The Veil does not take requests."),
     (BOARD_SPK, "A child's drawing of a sword, labelled GOBLINBANE, pinned in the corner.")],
    [(BOARD_SPK, "NO GOBLINS LAST NIGHT! Free cider at the tavern. (Torvin is paying, he doesn't know yet.)"),
     (BOARD_SPK, "WARNING: the east gate is open. Berserkers still raid the farms at night. Stay inside after dusk."),
     (BOARD_SPK, "WANTED: Moonpetals, fresh, picked after dusk. Good coin. - Wren")],
    [(BOARD_SPK, "WELCOME, farm folk of the east road. The west field is yours for as long as you need it. - The folk of Oakwood"),
     (BOARD_SPK, "The northern sky has turned purple at night. Keep your hearths lit. Keep your children close."),
     (BOARD_SPK, "Has anyone seen Merlin sleep? Ever? Asking for Pip.")],
    [(BOARD_SPK, "THE VEIL IS DOWN. Expedition to the far side of the mountains forming. Sign below. - Capt. Hale"),
     (BOARD_SPK, "Signed: Pip. Pip. Pip (again). Bram (for the chickens)."),
     (BOARD_SPK, "The night is quiet. The stars are clear. Thank you, Himmel. Thank you, Merlin.")],
]

SWORD_LOOK = [(story.HERO, "A child's wooden sword, wedged in an old stump. 'GOBLINBANE' is carved into the hilt. Somebody must be missing it.")]
PETAL_DAY = "A closed silver bud. It must bloom at night."


# --------------------------------------------------------------------------- #
#  sprites
# --------------------------------------------------------------------------- #
def _shrine_img(col):
    s = pygame.Surface((56, 96), pygame.SRCALPHA)
    pygame.draw.ellipse(s, (0, 0, 0, 80), (2, 80, 52, 16))
    for x, y, r in ((10, 84, 7), (46, 85, 6), (40, 88, 4), (16, 89, 4)):
        pygame.draw.circle(s, (96, 98, 100), (x, y), r)
        pygame.draw.circle(s, (130, 132, 134), (x - 1, y - 1), r - 2)
    body = [(16, 88), (12, 30), (18, 10), (30, 4), (40, 12), (44, 34), (40, 88)]
    pygame.draw.polygon(s, (86, 90, 96), body)
    pygame.draw.polygon(s, (120, 124, 130), [(16, 88), (12, 30), (18, 10), (30, 4), (30, 88)])
    pygame.draw.polygon(s, (40, 42, 48), body, 2)
    for x, y in ((14, 70), (18, 76), (38, 64), (36, 80), (22, 16)):                      # moss
        pygame.draw.circle(s, (70, 116, 60), (x, y), 3)
    pygame.draw.line(s, _shade(col, 0.35), (28, 28), (28, 66), 3)
    return s


def _rune_pts():
    return [((28, 26), (28, 66)), ((20, 36), (28, 46)), ((36, 36), (28, 46)), ((22, 58), (34, 58)), ((24, 30), (32, 30))]


def _memorial_img():
    s = pygame.Surface((110, 86), pygame.SRCALPHA)
    pygame.draw.ellipse(s, (0, 0, 0, 80), (6, 70, 98, 16))
    rows = [(12, 72, 7), (20, 60, 6), (30, 49, 5), (42, 38, 3), (50, 28, 2)]
    for x0, y, n in rows:
        for i in range(n):
            x = x0 + i * 14
            pygame.draw.ellipse(s, (54, 50, 50), (x, y - 2, 16, 13))
            pygame.draw.ellipse(s, (82, 76, 74), (x + 1, y - 2, 13, 10))
            pygame.draw.line(s, (36, 32, 32), (x + 3, y + 3), (x + 9, y + 5), 1)
    pygame.draw.rect(s, (110, 84, 52), (52, 6, 6, 30))                       # wooden marker
    pygame.draw.rect(s, (110, 84, 52), (42, 12, 26, 5))
    pygame.draw.rect(s, (70, 52, 30), (42, 12, 26, 5), 1)
    for x, c in ((14, (230, 210, 120)), (92, (220, 120, 160)), (22, (240, 240, 230)), (86, (230, 210, 120))):
        pygame.draw.line(s, (60, 110, 50), (x, 82), (x, 76), 1)
        pygame.draw.circle(s, c, (x, 75), 2)
    return s


CANDLES = [(30, 56), (62, 46), (82, 60), (46, 66)]


def _mill_img():
    s = pygame.Surface((200, 170), pygame.SRCALPHA)
    pygame.draw.ellipse(s, (0, 0, 0, 80), (14, 140, 172, 30))
    # broken sail lying on the ground
    for i in range(5):
        pygame.draw.line(s, (96, 70, 44), (120 + i * 12, 150), (176 + i * 4, 120 + i * 5), 3)
    pygame.draw.line(s, (80, 58, 36), (118, 152), (196, 140), 4)
    pygame.draw.line(s, (80, 58, 36), (126, 118), (190, 142), 3)
    # tower stump: stone body with a jagged broken top
    top = [(40, 150), (34, 70), (44, 58), (54, 64), (62, 40), (74, 52), (88, 36), (100, 60), (112, 52), (122, 74), (118, 150)]
    pygame.draw.polygon(s, (128, 120, 108), top)
    pygame.draw.polygon(s, (100, 94, 86), [(80, 150), (88, 36), (100, 60), (112, 52), (122, 74), (118, 150)])
    for y in range(76, 150, 12):                                             # masonry
        off = 0 if (y // 12) % 2 else 9
        pygame.draw.line(s, (84, 78, 72), (38, y), (120, y), 1)
        for x in range(42 + off, 118, 18):
            pygame.draw.line(s, (84, 78, 72), (x, y), (x, y + 12), 1)
    pygame.draw.polygon(s, (50, 46, 44), top, 2)
    pygame.draw.rect(s, (36, 26, 22), (68, 112, 22, 38), border_top_left_radius=11, border_top_right_radius=11)
    pygame.draw.rect(s, (24, 18, 16), (72, 84, 10, 12))                      # window
    pygame.draw.line(s, (70, 50, 30), (62, 44), (24, 22), 5)                  # snapped beam
    for x, y, r in ((30, 150, 9), (130, 154, 7), (20, 140, 6), (140, 146, 5)):
        pygame.draw.circle(s, (110, 104, 96), (x, y), r)
        pygame.draw.circle(s, (140, 134, 124), (x - 2, y - 2), r - 3)
    for x, y in ((46, 140), (110, 130), (58, 100), (104, 96)):                # ivy
        pygame.draw.circle(s, (64, 112, 56), (x, y), 4)
        pygame.draw.circle(s, (84, 140, 70), (x - 1, y - 1), 2)
    return s


def _board_img():
    s = pygame.Surface((64, 76), pygame.SRCALPHA)
    pygame.draw.ellipse(s, (0, 0, 0, 80), (6, 66, 52, 10))
    for x in (10, 50):
        pygame.draw.rect(s, (96, 66, 38), (x, 14, 5, 58))
    pygame.draw.polygon(s, (120, 64, 46), [(2, 14), (32, 2), (62, 14), (58, 18), (6, 18)])
    pygame.draw.rect(s, (128, 92, 56), (6, 20, 52, 34))
    pygame.draw.rect(s, (80, 56, 32), (6, 20, 52, 34), 2)
    for x, y, w, h, c in ((10, 24, 14, 12, (236, 228, 200)), (26, 23, 12, 16, (240, 220, 160)),
                          (40, 25, 14, 10, (230, 230, 220)), (12, 39, 16, 11, (220, 214, 190)),
                          (34, 38, 18, 13, (244, 236, 214))):
        pygame.draw.rect(s, c, (x, y, w, h))
        for ly in range(y + 3, y + h - 1, 3):
            pygame.draw.line(s, (120, 110, 100), (x + 2, ly), (x + w - 3, ly), 1)
        pygame.draw.circle(s, (180, 40, 40), (x + w // 2, y + 1), 1)
    return s


def _stump_img(with_sword):
    s = pygame.Surface((40, 50), pygame.SRCALPHA)
    pygame.draw.ellipse(s, (0, 0, 0, 80), (2, 40, 36, 10))
    pygame.draw.rect(s, (100, 70, 42), (8, 28, 24, 16))
    pygame.draw.ellipse(s, (150, 112, 70), (8, 23, 24, 10))
    pygame.draw.ellipse(s, (120, 86, 52), (12, 25, 16, 6), 1)
    pygame.draw.line(s, (70, 48, 28), (14, 34), (14, 42), 1)
    if with_sword:
        pygame.draw.polygon(s, (196, 160, 110), [(18, 28), (22, 28), (22, 6), (20, 2), (18, 6)])
        pygame.draw.line(s, (150, 116, 76), (21, 6), (21, 27), 1)
        pygame.draw.rect(s, (120, 70, 40), (13, 0, 14, 3))
        pygame.draw.rect(s, (90, 50, 28), (18, -6, 4, 7))
    return s


def _petal_img(bloom):
    s = pygame.Surface((18, 22), pygame.SRCALPHA)
    pygame.draw.line(s, (60, 110, 60), (9, 21), (9, 10), 1)
    pygame.draw.ellipse(s, (60, 110, 60), (3, 14, 6, 3))
    if bloom:
        for a in range(5):
            ang = a * math.tau / 5 - math.pi / 2
            pygame.draw.circle(s, (210, 225, 255), (9 + int(math.cos(ang) * 4), 8 + int(math.sin(ang) * 4)), 3)
        pygame.draw.circle(s, (250, 250, 210), (9, 8), 2)
    else:
        pygame.draw.ellipse(s, (150, 170, 170), (6, 4, 6, 8))
        pygame.draw.line(s, (120, 140, 140), (9, 5), (9, 11), 1)
    return s


def _hen_frames():
    out = []
    for img in CHICKEN:
        h = img.copy()
        pygame.draw.rect(h, (210, 30, 40), (3, 9, 9, 2))
        pygame.draw.rect(h, (240, 60, 60), (6, 11, 2, 3))
        out.append(h)
    return out


# --------------------------------------------------------------------------- #
#  landmarks
# --------------------------------------------------------------------------- #
class Landmark:
    kind = "landmark"
    reach = 64

    def __init__(self, img, x, y, foot=4, quest=None):
        self.img = img
        self.x, self.y = x, y
        w, h = img.get_size()
        self.rect = pygame.Rect(int(x - w // 2), int(y + foot - h), w, h)
        self.sort_y = y
        self.quest = quest

    def available(self, world):
        return True

    def visible(self, world):
        return True

    def prompt(self, world):
        return "[E]  Look"

    def draw(self, scr, cx, cy, t):
        scr.blit(self.img, (self.rect.x - cx, self.rect.y - cy))

    def lights(self, t):
        return []


class Shrine(Landmark):
    kind = "shrine"

    def __init__(self, idx):
        x, y, name, col = SHRINES[idx]
        super().__init__(_shrine_img(col), x, y, foot=6)
        self.idx, self.name, self.col = idx, name, col
        self.flag = "got_shrine_%d" % idx

    def prompt(self, world):
        return "[E]  Read the %s" % self.name

    def draw(self, scr, cx, cy, t):
        super().draw(scr, cx, cy, t)
        k = 0.65 + 0.35 * math.sin(t * 2.2 + self.idx)
        col = _shade(self.col, k)
        ox, oy = self.rect.x - cx, self.rect.y - cy
        for a, b in _rune_pts():
            pygame.draw.line(scr, col, (ox + a[0], oy + a[1]), (ox + b[0], oy + b[1]), 2)
        if int(t * 1.5 + self.idx) % 3 == 0:
            ph = (t * 1.5) % 1.0
            scr.fill(_shade(self.col, 1.2), (ox + 28 + int(math.sin(t * 5) * 8), oy + 30 - int(ph * 30), 2, 2))

    def lights(self, t):
        return [(self.x, self.y - 40, 110, _shade(self.col, 0.55))]


class Memorial(Landmark):
    kind = "memorial"
    IMG = None

    def __init__(self):
        if Memorial.IMG is None:
            Memorial.IMG = _memorial_img()
        super().__init__(Memorial.IMG, MEMORIAL[0], MEMORIAL[1], foot=8)

    def prompt(self, world):
        if world.quest_active("letter"):
            return "[E]  Leave Lisbet's letter"
        return "[E]  Pay your respects"

    def draw(self, scr, cx, cy, t):
        super().draw(scr, cx, cy, t)
        for i, (x, y) in enumerate(CANDLES):
            X, Y = self.rect.x + x - cx, self.rect.y + y - cy
            scr.fill((236, 226, 200), (X - 1, Y, 3, 6))
            f = 0.8 + 0.2 * math.sin(t * 10 + i * 2)
            h = int(5 * f) + 2
            pygame.draw.ellipse(scr, (255, 170, 60), (X - 2, Y - h, 5, h + 1))
            pygame.draw.ellipse(scr, (255, 240, 160), (X - 1, Y - h + 2, 3, h - 1))

    def lights(self, t):
        return [(self.x, self.y - 26, 120, (170, 110, 50))]


class Board(Landmark):
    kind = "board"
    reach = 56

    def __init__(self):
        super().__init__(_board_img(), BOARD[0], BOARD[1], foot=4)

    def prompt(self, world):
        return "[E]  Read the notice board"


class SwordStump(Landmark):
    kind = "sword"
    reach = 50

    def __init__(self):
        self.imgs = (_stump_img(True), _stump_img(False))
        super().__init__(self.imgs[0], SWORD[0], SWORD[1], foot=6, quest="pip_sword")
        self.flag = "got_sword_0"

    def available(self, world):
        return not world.has_flag(self.flag)

    def prompt(self, world):
        return "[E]  Take the wooden sword" if world.quest_active("sword") else "[E]  Look at the wooden sword"

    def draw(self, scr, cx, cy, t):
        self.img = self.imgs[0 if not self.flag_cache else 1]
        super().draw(scr, cx, cy, t)

    flag_cache = False


class Moonpetal(Landmark):
    kind = "petal"
    reach = 40
    IMGS = None

    def __init__(self, idx):
        if Moonpetal.IMGS is None:
            Moonpetal.IMGS = (_petal_img(False), _petal_img(True))
        x, y = PETALS[idx]
        super().__init__(Moonpetal.IMGS[0], x, y, foot=1, quest="wren_moonpetal")
        self.idx = idx
        self.flag = "got_petal_%d" % idx
        self.picked = False
        self.bloom = 0.0

    def visible(self, world):
        return not self.picked

    def available(self, world):
        return not self.picked and world.quest_active("petal")

    def prompt(self, world):
        return "[E]  Pick the Moonpetal" if self.bloom > 0.5 else "[E]  Look at the closed bud"

    def draw(self, scr, cx, cy, t):
        self.img = Moonpetal.IMGS[1 if self.bloom > 0.5 else 0]
        super().draw(scr, cx, cy, t)
        if self.bloom > 0.5:
            k = 0.5 + 0.5 * math.sin(t * 3 + self.x)
            scr.fill((230, 240, 255), (int(self.x - cx + math.cos(t + self.y) * 10), int(self.y - cy - 16 - k * 8), 2, 2))

    def lights(self, t):
        if self.bloom > 0.5:
            return [(self.x, self.y - 8, 50, (90, 110, 150))]
        return []


class Hen(Critter):
    kind = "hen"
    reach = 46
    FRAMES = None

    def __init__(self, idx, rng):
        if Hen.FRAMES is None:
            Hen.FRAMES = _hen_frames()
        x, y = HENS[idx]
        super().__init__(x, y, 60, rng)
        self.idx = idx
        self.flag = "got_hen_%d" % idx
        self.quest = "bram_hens"
        self.going_home = False
        self.homed = False

    def send_home(self):
        self.going_home = True
        self.target = None
        self.home = (COOP[0] + self.rng.randint(-30, 30), COOP[1] + self.rng.randint(-12, 12))

    def settle(self):
        """Already caught in an earlier session: start at the coop."""
        self.home = (COOP[0] + self.rng.randint(-30, 30), COOP[1] + self.rng.randint(-12, 12))
        self.x, self.y = self.home
        self.radius = 40
        self.homed = True

    def available(self, world):
        return not self.going_home and not self.homed and world.quest_active("hen")

    def prompt(self, world):
        return "[E]  Shoo the hen home"

    def update(self, dt, world):
        self.anim += dt
        if self.going_home:
            if math.dist((self.x, self.y), self.home) <= 150 * dt + 2:
                self.x, self.y = self.home
                self.going_home, self.homed, self.radius = False, True, 40
            else:
                _step_toward(self, self.home[0], self.home[1], 150, dt, world, solid=False)
            self.moving = True
        else:
            self.moving = self.wander(dt, world, 30)
        self._sync()

    def draw(self, scr, cx, cy, t):
        img = Hen.FRAMES[1 if (not self.moving and int(self.anim * 2.5 + self.idx) % 5 == 0) else 0]
        if self.flip:
            img = pygame.transform.flip(img, True, False)
        hop = -2 if self.moving and int(self.anim * 12) % 2 else 0
        scr.blit(img, (int(self.x - cx) - 9, int(self.y - cy) - 18 + hop))


# --------------------------------------------------------------------------- #
#  populate
# --------------------------------------------------------------------------- #
def populate(world, add_prop, rng):
    add_prop(_mill_img(), MILL[0], MILL[1], foot=20, col=(MILL[0] - 62, MILL[1] - 40, 84, 34), radius=90)
    lms = [Shrine(i) for i in range(len(SHRINES))]
    lms += [Memorial(), Board(), SwordStump()]
    lms += [Moonpetal(i) for i in range(len(PETALS))]
    world.landmarks = lms
    for lm in lms:
        if lm.kind in ("shrine", "memorial", "board", "sword"):
            w = {"shrine": 30, "memorial": 80, "board": 46, "sword": 22}[lm.kind]
            world.colliders.append(pygame.Rect(lm.x - w // 2, lm.y - 10, w, 10))
    world.hens = [Hen(i, rng) for i in range(len(HENS))]
