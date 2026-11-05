"""
in_game.py - The Goblin King as a dungeon enemy (the boss of Goblin Dungeon floor 1-3).

Gives GoblinKing the same interface as the game's combat.Enemy, so the Encounters code
can treat him like any other monster:

    boss = GoblinKingEnemy(x, y)          # x, y = the point under his feet (world pixels)
    boss.update(dt, player, dungeon, pc)  # AI; his hits go through pc.hurt (dash i-frames work)
    boss.take_damage(n); boss.dead; boss.hp; boss.max_hp
    boss.draw(surface, cam_x, cam_y)

Numbers come from boss_config.IN_GAME. Phase 2 (boss_config PHASE2_*): at half HP he roars,
can't be hurt for SUMMON_TIME, then take_summons() turns True once and Encounters spawns
his minions around him.
"""
try:
    from . import boss_config as cfg
    from .goblin_king import GoblinKing
except ImportError:
    import boss_config as cfg
    from goblin_king import GoblinKing


class _Target:
    """What GoblinKing.update needs from the hero: a floor point and hurt(damage)."""

    def __init__(self, player, pc, dungeon, boss):
        self.x, self.y = player.x, player.y
        self._player, self._pc, self._dungeon, self._boss = player, pc, dungeon, boss

    def hurt(self, damage):
        gx, gy = self._boss.ground
        self._pc.hurt(damage, self._player, self._dungeon, gx, gy)


class GoblinKingEnemy:
    kind = "boss"
    cc_immune = True              # skills can't stun or slow a king
    skin = None

    def __init__(self, x, y, name="Valdur, Goblin King"):
        self.boss = GoblinKing(x, y, cfg.IN_GAME)
        self.boss.y -= self.boss.feet_offset          # GoblinKing.y is his body, not his feet
        self._name = name
        self.radius = 34
        self.color = (126, 62, 52)
        self.damage = cfg.IN_GAME["damage"]["heavy"][12]
        self.attack_cd = 0.0
        self.hit_flash = 0.0
        self.stun_t = self.slow_t = 0.0

    # ---- Enemy interface ----------------------------------------------------------
    @property
    def x(self):
        return self.boss.x

    @property
    def y(self):
        return self.boss.y + self.boss.feet_offset

    @property
    def hp(self):
        return self.boss.hp

    @property
    def max_hp(self):
        return self.boss.max_hp

    @property
    def dead(self):
        return self.boss.hp <= 0

    @property
    def state(self):
        return self.boss.state

    @property
    def name(self):
        return self._name + (" - Enraged" if self.boss.phase == 2 else "")

    # ---- phase 2 (at half HP he roars and the room spawns his minions) ---------------
    @property
    def phase(self):
        return self.boss.phase

    @property
    def summoning(self):
        """True while he roars (he can't be hurt)."""
        return self.boss.summoning

    def take_summons(self):
        """True once, the moment the roar ends: the room should spawn cfg.PHASE2_SUMMONS."""
        if self.boss.summon_ready:
            self.boss.summon_ready = False
            return True
        return False

    def pop_sounds(self):
        """Sound names he made since the last call (axe swing, ground slam)."""
        out, self.boss.sounds = self.boss.sounds, []
        return out

    def take_damage(self, amount):
        if not self.dead and not self.summoning:
            self.boss.take_damage(amount)
            self.hit_flash = 0.12

    def update(self, dt, player, dungeon, pc):
        if self.dead:
            return
        self.hit_flash = max(0.0, self.hit_flash - dt)
        if pc.dead:                       # stand still once the hero has fallen
            return
        self.boss.wake()                  # the fight starts the moment the boss room locks
        before = (self.boss.x, self.boss.y)
        self.boss.update(dt, _Target(player, pc, dungeon, self.boss))
        if not dungeon.can_stand(self.x, self.y):     # walls stop his walk and his dash
            self.boss.x, self.boss.y = before

    def draw(self, surf, cx, cy):
        if not self.dead:
            self.boss.draw(surf, (cx, cy))
