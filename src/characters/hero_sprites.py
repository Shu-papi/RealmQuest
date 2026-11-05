"""
hero_sprites.py - The team's merged heroes, sized for the game world.

    Warrior -> the Knight      (src/characters/player.py + assets/characters/knight_animations.json)
    Mage    -> Kendi           (characters/kendi_pygame/kendi_sprites.py + its sprite folders)
    Archer  -> the Elf Archer  (src/characters/elf_code/sprite_animation/config.py
                                + assets/characters/elf_archer/ and its anchors.json)

No art is drawn here: every frame, timing and alignment point comes from those packs.
This module only resizes the frames to the size of the villagers and plays them.

    hero = HeroSprite("mage")
    hero.act("attack", 0.36)          # one-shot swing / cast, squeezed into 0.36 s
    hero.draw(screen, feet_x, feet_y, moving=True, left=False)

    portrait("archer")   # 260x260, full body: dialog box (stands above it)
    bust("archer")       # head and shoulders: the HUD panel
    card("archer")       # the class-select picture
"""
import importlib.util
import json
import sys
from pathlib import Path
from statistics import median

import pygame

REPO = Path(__file__).resolve().parents[2]
HEIGHT = 58                     # body height in the world, in px (villagers are about 52)
CLASSES = ("warrior", "mage", "archer")
LOOK_CLASS = {"hero_warrior": "warrior", "hero_mage": "mage", "hero_archer": "archer"}

KNIGHT_PLAYER = REPO / "src" / "characters" / "player.py"
KENDI_MODULE = REPO / "characters" / "kendi_pygame" / "kendi_sprites.py"
ELF_CONFIG = REPO / "src" / "characters" / "elf_code" / "sprite_animation" / "config.py"
ELF_ASSETS = REPO / "assets" / "characters" / "elf_archer"

# what the game asks for -> the animation of each pack that shows it
STATES = {
    "warrior": {"idle": "idle", "move": "run", "attack": "attack", "special": "attack",
                "hurt": "hurt", "dead": "dead"},       # only the Knight's pack has hurt / dead frames
    "mage":    {"idle": "idle", "move": "run", "attack": "attack", "special": "attack"},
    "archer":  {"idle": "idle", "move": "run", "attack": "quick_attack", "special": "charge_attack"},
}


def class_of(look_or_class):
    """'hero_mage' or 'mage' -> 'mage' (anything unknown is the Warrior)."""
    c = LOOK_CLASS.get(look_or_class, look_or_class)
    return c if c in CLASSES else "warrior"


def _module(name, path):
    """Import a teammate's file by path (their folders are not Python packages)."""
    if name in sys.modules:
        return sys.modules[name]
    if not Path(path).exists():                 # the built game ships these files compiled (.pyc), not as source
        path = Path(path).with_suffix(".pyc")
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod             # dataclasses look their module up while it loads
    try:
        spec.loader.exec_module(mod)
    except Exception:
        del sys.modules[name]
        raise
    return mod


def _alpha(img):
    try:
        return img.convert_alpha()
    except pygame.error:            # no window yet (tests): keep the raw surface
        return img


_PNGS = {}


def _png(path):
    """A source frame, decoded once (bigger copies for the menus reuse it)."""
    key = str(path)
    if key not in _PNGS:
        _PNGS[key] = _alpha(pygame.image.load(key))
    return _PNGS[key]


def _resize(img, k, smooth):
    size = (max(1, round(img.get_width() * k)), max(1, round(img.get_height() * k)))
    if size == img.get_size():
        return img
    if smooth:                      # painted art (Kendi, the Elf): smooth when shrinking
        return pygame.transform.smoothscale(img, size)
    return pygame.transform.scale(img, size)        # the Knight is pixel art: keep it crisp


def _visible_h(img):
    return img.get_bounding_rect(min_alpha=1).height or img.get_height()


class Clip:
    """One animation: frames facing right + their foot anchors, durations, loop flag."""

    def __init__(self, frames, durations, loop, k, smooth):
        self.right, self.left = [], []
        for img, (ax, ay) in frames:
            box = img.get_bounding_rect(min_alpha=1)        # drop the empty margins first (less to scale)
            if box.w and box.h:
                img = img.subsurface(box)
                ax, ay = ax - box.x, ay - box.y
            img = _resize(img, k, smooth)
            if img.get_size() == box.size:
                img = img.copy()                            # keep it independent of the cached source
            ax, ay = ax * k, ay * k
            self.right.append((img, (round(ax), round(ay))))
            self.left.append((pygame.transform.flip(img, True, False), (round(img.get_width() - ax), round(ay))))
        self.durations = list(durations)
        self.loop = loop
        self.length = sum(self.durations)

    def index(self, t):
        t = t % self.length if self.loop else min(t, self.length - 1e-6)
        for i, d in enumerate(self.durations):
            if t < d:
                return i
            t -= d
        return len(self.durations) - 1

    def frame(self, t, left=False):
        return (self.left if left else self.right)[self.index(t)]


# --------------------------------------------------------------------------- loaders
def _load_knight(height=HEIGHT):
    """The Knight, through the Warrior team's own SpriteAnimator and json."""
    player = _module("rq_knight_player", KNIGHT_PLAYER)
    anim = player.SpriteAnimator("knight", player.ASSET_DIR)
    data = anim.data
    idle0 = anim.frames[data["animations"]["idle"]["frames"][0]][0]
    box = idle0.get_bounding_rect(min_alpha=1)
    # their pivot is the body centre; the game stands heroes on their feet
    feet_drop = box.bottom - anim.pivots[data["animations"]["idle"]["frames"][0]][False][1]
    k = height / box.h
    clips = {}
    for name, a in data["animations"].items():
        frames = [(anim.frames[f][0], (anim.pivots[f][False][0], anim.pivots[f][False][1] + feet_drop))
                  for f in a["frames"]]
        d = a["frame_duration_ms"]
        durations = [(d[i] if isinstance(d, list) else d) / 1000.0 for i in range(len(frames))]
        clips[name] = Clip(frames, durations, bool(a.get("loop")), k, smooth=False)
    return clips


def _load_kendi(height=HEIGHT):
    """Kendi the Mage, with the Mage team's frame counts, fps and foot anchors."""
    kendi = _module("rq_kendi_sprites", KENDI_MODULE)
    clips = {}
    for name, cfg in kendi.ANIMATIONS.items():
        imgs = [_png(kendi.SPRITE_DIR / name / f"{name}_{i:02d}.png") for i in range(1, cfg["frames"] + 1)]
        # Kendi() sizes each animation to the same visible height. The attack frames carry
        # a big spell flash, so measure that one by its plain stance (its shortest frame).
        heights = [_visible_h(i) for i in imgs]
        k = height / (median(heights) if cfg["loop"] else min(heights))
        frames = [(img, cfg["anchor"]) for img in imgs]
        clips[name] = Clip(frames, [1.0 / cfg["fps"]] * len(imgs), cfg["loop"], k, smooth=True)
    return clips


def _load_elf(height=HEIGHT):
    """The Elf Archer, with the Archer team's specs (fps, per-frame ms) and anchors.json."""
    config = _module("rq_elf_config", ELF_CONFIG)
    anchors_file = ELF_ASSETS / "anchors.json"
    anchors = json.loads(anchors_file.read_text()) if anchors_file.exists() else {}
    loaded = {}
    for name, spec in config.ANIMATIONS.items():
        frames = []
        for file in config.list_frame_files(ELF_ASSETS, spec):
            img = _png(file)
            if file.name in anchors.get(name, {}):
                ax, bottom = anchors[name][file.name]
                anchor = (ax + 0.5, bottom + 1)                # same rule as sprite_animation/assets.py
            else:
                b = img.get_bounding_rect(min_alpha=40)
                anchor = (b.centerx, b.bottom)
            frames.append((img, anchor))
        loaded[name] = (spec, frames)
    k = height / median(_visible_h(img) for img, _ in loaded["idle"][1])   # one scale for every clip
    return {name: Clip(frames, [spec.frame_duration(i) / 1000.0 for i in range(len(frames))],
                       spec.loop, k, smooth=True)
            for name, (spec, frames) in loaded.items()}


_LOADERS = {"warrior": _load_knight, "mage": _load_kendi, "archer": _load_elf}
_BANKS = {}


def clips(cls, height=HEIGHT):
    """All animations of a class at a body height, loaded once and shared.
    Bigger copies (menus) come straight from the high-res sources, so they stay sharp."""
    key = (class_of(cls), int(height))
    if key not in _BANKS:
        _BANKS[key] = _LOADERS[key[0]](key[1])
    return _BANKS[key]


# --------------------------------------------------------------------------- the hero
class HeroSprite:
    """Plays one hero's animations: idle / move underneath, attack / special / hurt on top,
    and a death pose. Heroes whose pack has no hurt / dead frames flash red when hurt and
    are drawn tipped over when they fall."""

    HURT_FLASH = 0.18

    def __init__(self, cls, height=HEIGHT):
        self.cls = class_of(cls)
        self.height = int(height)
        self.clips = clips(self.cls, self.height)
        self.map = STATES[self.cls]
        self.dead = False
        self.dead_t = 0.0
        self.flash = 0.0            # red tint left (heroes without hurt frames)
        self._tint = {}
        self.base = "idle"
        self.base_t = 0.0
        self.action = None          # "attack" / "special" while a one-shot plays
        self.action_t = 0.0
        self.action_k = 1.0         # playback speed of the one-shot
        self._last = None

    def clip(self, state):
        return self.clips[self.map[state]]

    def has(self, state):
        return state in self.map

    def act(self, kind="attack", duration=None):
        """Start a one-shot. `duration` (s) speeds it up to fit the game's attack timing."""
        if self.dead:
            return
        if kind == "hurt":
            self.flash = self.HURT_FLASH
            if not self.has("hurt"):
                return
            if self.action in ("attack", "special"):     # don't cut a swing short
                return
        if not self.has(kind):
            return
        clip = self.clip(kind)
        self.action, self.action_t = kind, 0.0
        self.action_k = clip.length / duration if duration and duration < clip.length else 1.0

    def set_dead(self, dead):
        if dead and not self.dead:
            self.dead_t, self.action = 0.0, None
        self.dead = dead

    def update(self, dt, moving):
        self.flash = max(0.0, self.flash - dt)
        if self.dead:
            self.dead_t += dt
            return
        base = "move" if moving else "idle"
        if base != self.base:
            self.base, self.base_t = base, 0.0
        self.base_t += dt
        if self.action:
            self.action_t += dt * self.action_k
            if self.action_t >= self.clip(self.action).length:
                self.action = None

    def frame(self, left=False):
        if self.dead and self.has("dead"):
            return self.clip("dead").frame(self.dead_t, left)
        if self.dead:
            return self.clip("idle").frame(0.0, left)
        if self.action:
            return self.clip(self.action).frame(self.action_t, left)
        return self.clip(self.base).frame(self.base_t, left)

    def draw(self, surf, x, y, moving=False, left=False):
        """Update from the wall clock and blit with the feet on (x, y). Returns the rect."""
        now = pygame.time.get_ticks() / 1000.0
        dt = 0.0 if self._last is None else min(0.1, max(0.0, now - self._last))
        self._last = now
        self.update(dt, moving)
        img, (ax, ay) = self.frame(left)
        if self.dead and not self.has("dead"):           # no death frames: tip over and fade
            k = min(1.0, self.dead_t / 0.35)
            img = pygame.transform.rotate(img, (-90 if not left else 90) * k)
            img.set_alpha(int(255 - 100 * k))
            return surf.blit(img, img.get_rect(midbottom=(round(x), round(y))))
        if self.flash > 0 and not (self.has("hurt") and self.action == "hurt"):
            img = self._red(img)
        return surf.blit(img, (round(x - ax), round(y - ay)))

    def _red(self, img):
        """The same frame tinted red (cached per frame surface)."""
        red = self._tint.get(id(img))
        if red is None or red[0] is not img:
            tinted = img.copy()
            tinted.fill((140, 0, 0), special_flags=pygame.BLEND_RGB_ADD)
            tinted.fill((255, 120, 120), special_flags=pygame.BLEND_RGB_MULT)
            red = self._tint[id(img)] = (img, tinted)
        return red[1]


# --------------------------------------------------------------------------- pictures
def _source_idle(cls):
    """First idle frame at the pack's own resolution, cropped (portraits stay sharp)."""
    cls = class_of(cls)
    if cls == "warrior":
        player = _module("rq_knight_player", KNIGHT_PLAYER)
        anim = player.SpriteAnimator("knight", player.ASSET_DIR)
        img = anim.frames[anim.data["animations"]["idle"]["frames"][0]][0]
    elif cls == "mage":
        kendi = _module("rq_kendi_sprites", KENDI_MODULE)
        img = _alpha(pygame.image.load(str(kendi.SPRITE_DIR / "idle" / "idle_01.png")))
    else:
        config = _module("rq_elf_config", ELF_CONFIG)
        img = _alpha(pygame.image.load(str(config.list_frame_files(ELF_ASSETS, config.ANIMATIONS["idle"])[0])))
    return img.subsurface(img.get_bounding_rect(min_alpha=1)).copy()


_PICS = {}


def _figure(cls, max_h):
    """The idle pose about max_h tall: native size for painted art, whole-number zoom for the Knight."""
    img = _source_idle(cls)
    if class_of(cls) == "warrior":
        return _resize(img, max(1, max_h // img.get_height()), smooth=False)
    if img.get_height() > max_h:
        return _resize(img, max_h / img.get_height(), smooth=True)
    return img


def portrait(cls, size=260):
    """Full body on a size x size canvas, feet at the bottom (the dialog's standing picture)."""
    key = ("portrait", class_of(cls), size)
    if key not in _PICS:
        fig = _figure(cls, size - 24)
        canvas = pygame.Surface((size, size), pygame.SRCALPHA)
        canvas.blit(fig, ((size - fig.get_width()) // 2, size - fig.get_height()))
        _PICS[key] = canvas
    return _PICS[key]


def bust(cls):
    """Head and shoulders, square (the HUD portrait box)."""
    key = ("bust", class_of(cls))
    if key not in _PICS:
        fig = _figure(cls, 236)
        side = min(fig.get_width(), int(fig.get_height() * 0.55))
        x = (fig.get_width() - side) // 2
        _PICS[key] = fig.subsurface((x, 0, side, side)).copy()
    return _PICS[key]


def card(cls, max_h=128):
    """The idle pose for the class-select card."""
    key = ("card", class_of(cls), max_h)
    if key not in _PICS:
        img = _source_idle(cls)
        if class_of(cls) != "warrior":         # the card scales pixel art itself in whole steps
            img = _resize(img, max_h / img.get_height(), smooth=True)
        _PICS[key] = img
    return _PICS[key]
