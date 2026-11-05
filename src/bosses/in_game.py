"""
in_game.py - Arena bosses (Lich King, Minotaur) as dungeon enemies.

The arena bosses were written for a 960x640 window. The dungeon has a scrolling camera. BossEnemy sits
between the two so neither side changes. The numbers in config/bosses/<boss>.toml apply AS TYPED: the bar
shows the file's max_hp and every attack takes the file's damage off the hero (before his armour):

    boss = BossEnemy("minotaur", room_x, room_y, room_w, room_h)     # the room's pixel rectangle
    boss.update(dt, player, dungeon, pc)     # AI; every hit goes through pc.hurt (dash i-frames work)
    boss.take_damage(n); boss.dead; boss.hp; boss.max_hp
    boss.draw(surface, cam_x, cam_y)

HOW IT WORKS
    * The boss lives in ROOM coordinates: (0, 0) is the room's top-left corner, so its arena maths
      (bounds, telegraphs, charges) work unchanged. The hero is converted into those coordinates.
    * It is drawn onto a copy of the room's part of the screen and pasted back, so glows and
      additive effects blend with the real floor.
    * IN_GAME below holds two OPTIONAL scale knobs per boss. Both are 1.0 = off, so the file's numbers are
      exactly what you see and take:
          hp_power   a hit of 2 does 2 x hp_power to the boss (and its minions). The HP shown is the
                     real HP divided by it, so heals and phase thresholds keep working as designed.
          damage_k   every boss / minion hit on the hero is multiplied by this (then PlayerCombat applies defence)
      (The first version used hp_power 15 / 3 and damage_k 0.5 to fit a 2-damage sword and a 40-HP hero.)
    * The Lich King's skeletons are shown to the game as MinionEnemy objects (the hero can hit them,
      they give no XP) and are updated by the boss itself.
    * Both bosses make their own sounds (audio package / the Minotaur's soundboard).
"""
import pygame

try:
    import audio                                             # src/ is on sys.path
    from monsters.in_game import Painter                     # draws arena-style things on a scrolling screen
except ImportError:                                          # run as src.bosses
    from src import audio
    from src.monsters.in_game import Painter

# Scale knobs for the dungeon fights (config/bosses/<boss>.toml [dungeon]). 1.0 = the file's numbers as typed.
# hp_power: bigger = the boss dies faster (the bar shows his HP divided by it). damage_k: bigger = it hurts more.
IN_GAME = {
    "lich_king": {"name": "The Lich King", "hp_power": 1.0, "damage_k": 1.0, "hit_radius": 40,
                  "color": (132, 92, 190)},
    "minotaur": {"name": "The Minotaur", "hp_power": 1.0, "damage_k": 1.0, "hit_radius": 40,
                 "color": (132, 82, 48)},
}

EDGE_X = 50                  # the arena bounds sit this far inside the room (px)
EDGE_TOP = 110               # ...and this far below the top wall (the sprites are tall)
EDGE_BOTTOM = 50
HERO_RADIUS = 12             # the hero's hit circle as the boss sees it
HERO_LIFT = 10               # the boss aims at the hero's body, not at the feet


class _HeroShim:
    """What the arena bosses read from the player: rect, x, y, radius, take_damage, apply_status."""

    radius = HERO_RADIUS

    def __init__(self, owner):
        self.owner = owner
        self.rect = pygame.Rect(0, 0, HERO_RADIUS * 2, HERO_RADIUS * 2)
        self.x = self.y = 0.0
        self.player = self.pc = self.dungeon = None

    def refresh(self, player, pc, dungeon):
        self.player, self.pc, self.dungeon = player, pc, dungeon
        self.x = player.x - self.owner.ox
        self.y = player.y - HERO_LIFT - self.owner.oy
        self.rect.center = (round(self.x), round(self.y))

    def take_damage(self, amount):
        """A boss hit. Returns the damage meant (0 when nothing was hurt)."""
        owner = self.owner
        if self.pc is None or not owner.boss.is_alive():       # a dying boss's leftovers do nothing
            return 0
        damage = max(1, round(amount * owner.damage_k))
        return damage if self.pc.hurt(damage, self.player, self.dungeon, owner.x, owner.y) else 0

    def apply_status(self, name, seconds):
        """'root' (can't walk or dash) or 'slow' (half speed). A dashing hero is immune."""
        pc, player = self.pc, self.player
        if pc is None or pc.dead or pc.dash_inv > 0 or not hasattr(player, "afflict"):
            return False
        player.afflict(name, seconds)
        return True


class MinionEnemy:
    """One of a boss's summons (a skeleton) seen as a dungeon enemy. The boss moves and draws it."""

    kind = "minion"
    summoned = True              # gone when the boss falls
    no_reward = True             # no XP or loot: the Lich King can call them again and again
    cc_immune = True
    skin = None
    color = (214, 208, 190)

    def __init__(self, owner, minion):
        self.owner = owner
        self.minion = minion
        self.damage = 0
        self.stun_t = self.slow_t = self.hit_flash = 0.0

    @property
    def x(self):
        return self.owner.ox + self.minion.x

    @property
    def y(self):
        return self.owner.oy + self.minion.y

    @property
    def radius(self):
        return self.minion.radius

    @property
    def hp(self):
        return self.minion.hp / self.owner.hp_power

    @property
    def max_hp(self):
        return self.minion.max_hp / self.owner.hp_power

    @property
    def name(self):
        return getattr(self.minion, "NAME", "Skeleton").replace("_", " ").title()

    @property
    def dead(self):
        return not self.owner.boss.is_alive() or not self.minion.is_alive()

    def take_damage(self, amount):
        if not self.dead:
            self.minion.take_damage(amount * self.owner.hp_power)

    def update(self, dt, player, dungeon, pc):
        pass                                    # the boss updates its minions

    def pop_sounds(self):
        return []

    def draw(self, surf, cx, cy):
        pass                                    # the boss draws its minions


_FOOT = {"minotaur": 88.0}       # fallback if the boss class has no FOOT_Y


def _module_value(boss, name):
    """A constant from the boss's own module (e.g. FOOT_Y, or BOSS_MAX_HP as its config file says now)."""
    import sys
    return getattr(sys.modules.get(type(boss).__module__), name, None)


def _module_max_hp(boss):
    return _module_value(boss, "BOSS_MAX_HP")


class BossEnemy:
    """An arena boss with the same interface as combat.Enemy."""

    kind = "boss"
    cc_immune = True             # skills can't stun or slow a boss
    skin = None

    def __init__(self, key, room_x, room_y, room_w, room_h):
        from . import get_boss                           # (bosses/__init__ imports this module's neighbours)
        cfg = IN_GAME[key]
        self.key = key
        self.ox, self.oy = float(room_x), float(room_y)
        self.w, self.h = int(room_w), int(room_h)
        self.hp_power = float(cfg["hp_power"])
        self.damage_k = float(cfg["damage_k"])
        self.radius = cfg["hit_radius"]
        self.color = cfg["color"]
        self._name = cfg["name"]
        self.bounds = (EDGE_X, EDGE_TOP, self.w - EDGE_X, self.h - EDGE_BOTTOM)
        self.boss = get_boss(key, x=self.w / 2, y=self.h * 0.3)
        self.damage = 0
        self.attack_cd = 0.0
        self.hit_flash = 0.0
        self.stun_t = self.slow_t = 0.0
        self.audio_music = key == "lich_king"          # he plays his own music (dungeon_map quiets the map music)
        self.hero = _HeroShim(self)
        self._proxies = {}                               # id(minion) -> MinionEnemy
        self._painter = Painter(self.ox, self.oy, self.w, self.h)

    # ---- Enemy interface ------------------------------------------------------------
    @property
    def x(self):
        return self.ox + self.boss.x

    @property
    def foot(self):
        """How far his feet are below his position (the Minotaur's position is his body)."""
        return float(_module_value(self.boss, "FOOT_Y") or _FOOT.get(self.key, 0.0))

    @property
    def y(self):
        """His hit circle: half-way between his body and his feet, so it sits on what you see."""
        return self.oy + self.boss.y + self.foot * 0.5

    @property
    def hp(self):
        return self.boss.hp / self.hp_power

    @property
    def max_hp(self):
        return self.boss.max_hp / self.hp_power

    @property
    def dead(self):
        return self.boss.is_defeated()                   # after the death animation

    @property
    def state(self):
        return self.boss.state

    @property
    def phase(self):
        return self.boss.phase

    @property
    def name(self):
        return self._name + (" - Enraged" if self.boss.phase >= 2 else "")

    def pop_sounds(self):
        return []                                        # it makes its own sounds

    def take_damage(self, amount):
        if self.boss.is_alive():
            if self.boss.take_damage(amount * self.hp_power):
                self.hit_flash = 0.12

    def update(self, dt, player, dungeon, pc):
        self.hit_flash = max(0.0, self.hit_flash - dt)
        if pc.dead:                                      # stand still once the hero has fallen
            return
        self.hero.refresh(player, pc, dungeon)
        bx, by = self.boss.x, self.boss.y
        self.boss.update(dt, self.hero, self.bounds)
        # walls and the room's chamfered corners stop his feet; he slides along them
        fx, fy = self.ox, self.oy + self.foot
        nx, ny = self.boss.x, self.boss.y
        if not dungeon.can_stand(fx + nx, fy + ny):
            if dungeon.can_stand(fx + nx, fy + by):
                self.boss.x, self.boss.y = nx, by
            elif dungeon.can_stand(fx + bx, fy + ny):
                self.boss.x, self.boss.y = bx, ny
            else:
                self.boss.x, self.boss.y = bx, by

    def refresh_config(self):
        """The config files changed: re-read [dungeon] (hp_power, damage_k, hit_radius) and his
        maximum health, keeping the same share of health left."""
        cfg = IN_GAME[self.key]
        self.hp_power = float(cfg["hp_power"])
        self.damage_k = float(cfg["damage_k"])
        self.radius = cfg["hit_radius"]
        b = self.boss
        new_max = _module_max_hp(b)
        if new_max and b.max_hp and new_max != b.max_hp and b.is_alive():
            share = b.hp / b.max_hp
            b.max_hp = new_max
            b.hp = max(1, round(new_max * share))

    # ---- the Lich King's skeletons ----------------------------------------------------
    def new_minions(self):
        """MinionEnemy objects for summons the game does not know yet (Encounters adds them)."""
        fresh = []
        if not self.boss.is_alive():
            return fresh
        live = {id(m) for m in self.boss.minions}
        for gone in [k for k in self._proxies if k not in live]:
            del self._proxies[gone]
        for minion in self.boss.minions:
            if id(minion) not in self._proxies and minion.is_alive():
                self._proxies[id(minion)] = proxy = MinionEnemy(self, minion)
                fresh.append(proxy)
        return fresh

    def dispose(self):
        """The room is reset (the hero fell) or left: stop the boss's music and loops."""
        audio.stop_music(fade=0.6)
        audio.loop("ward_hum", False)

    def set_volume(self, volume):
        """Sound-effect volume 0..1 for bosses that have their own soundboard (the Minotaur)."""
        board = getattr(self.boss, "sfx", None)
        if board is not None:
            board.volume = max(0.0, min(1.0, volume))

    # ---- drawing -----------------------------------------------------------------------
    def draw(self, surf, cx, cy):
        """Draw the boss on a copy of the room's visible part of the screen, then paste it back."""
        self._painter.paint(surf, cx, cy, self.boss.draw)


_PORTRAITS = {}


def portrait(key):
    """A picture of the boss for the story dialogs (None if it can't be drawn): the boss is drawn once, standing."""
    if key not in _PORTRAITS:
        img = None
        try:
            from . import get_boss
            boss = get_boss(key, x=300, y=300)
            boss.set_state("idle")
            boss.state_time = 5.0
            boss.sfx = None                                  # (the Minotaur) draw only, make no sound
            canvas = pygame.Surface((600, 600), pygame.SRCALPHA)
            boss.draw_boss(canvas)
            img = canvas.subsurface(canvas.get_bounding_rect()).copy()
        except Exception:
            img = None
        _PORTRAITS[key] = img
    return _PORTRAITS[key]


# ======================================================================================================
# CONFIG FILES: the [dungeon] table of config/bosses/minotaur.toml and config/bosses/lich_king.toml sets IN_GAME.
# ======================================================================================================
try:
    import balance as _balance                              # src/ is on the path
except ImportError:                                         # run as src.bosses
    from src import balance as _balance


def _dungeon(key):
    return _balance.Prop(lambda: IN_GAME[key], lambda table: IN_GAME[key].update(table))


for _key in IN_GAME:
    _balance.declare(
        "bosses", _key, "", "", None, {"dungeon": _dungeon(_key)},
        docs={"dungeon": "In the dungeon: name = his health-bar name, hit_radius = how close a sword swing must be, "
                         "color = placeholder. hp_power and damage_k are OPTIONAL scale knobs: 1 = the numbers in "
                         "this file apply exactly as typed (the bar shows max_hp, every attack takes its damage off "
                         "the hero before his armour). hp_power = 15 means a sword hit of 2 does 30 to him and the "
                         "bar shows his health / 15; damage_k = 0.5 halves every hit on the hero."},
        partial=True)
