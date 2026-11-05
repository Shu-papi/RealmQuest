"""
base_boss.py - The blueprint every RealmQuest boss is built from (real-time / Pygame).

WHAT THE GAME NEEDS TO DO (integration contract)
    boss.update(dt, player, bounds)     every frame. dt = seconds since last frame,
                                        bounds = (left, top, right, bottom) of the arena
    boss.draw(surface)                  draws boss + its attacks + its minions
    boss.draw_health_bar(surface, font) draws the boss health bar at the top

    For the player's attacks, loop over boss.hittables(). Each one has
    .x  .y  .radius  .take_damage(amount)   (the boss itself AND its minions)

    boss.is_alive()      False as soon as HP hits 0 (death animation starts)
    boss.is_defeated()   True once the death animation is finished
    boss.drop_loot()     list of item names (call after defeat)

WHAT THE BOSS NEEDS FROM THE PLAYER
    player.rect              a pygame.Rect
    player.take_damage(n)    the player decides what to do with the damage

TO MAKE A NEW BOSS
    Inherit from Boss, then write update_ai() and draw_boss().
    See lich_king.py for a full example.
"""
import os
import random
import pygame

from .paths import REPO_ROOT


def load_sprite(filename, size=None):
    """
    Loads assets/bosses/<filename> if it exists, otherwise returns None
    (and the boss falls back to its built-in shape drawing).
    """
    root = REPO_ROOT
    path = os.path.join(root, "assets", "bosses", filename)
    if not os.path.exists(path):
        return None
    try:
        image = pygame.image.load(path).convert_alpha()
        if size:
            image = pygame.transform.scale(image, size)   # hard edges: keeps pixel art crisp
        return image
    except Exception:
        return None


class Boss:
    def __init__(self, name, max_hp, x, y, radius,
                 intro="", death_line="", loot=None, seed=None):
        self.name = name
        self.max_hp = max_hp
        self.hp = max_hp
        self.x = float(x)
        self.y = float(y)
        self.radius = radius
        self.intro = intro
        self.death_line = death_line
        self.loot = loot if loot is not None else []

        self.phase = 1
        self.state = "idle"
        self.state_time = 0.0
        self.clock = 0.0
        self.hit_flash = 0.0
        self.shake = 0.0
        self.bounds = (0, 0, 960, 640)
        self.sprite = None

        self.projectiles = []
        self.hazards = []
        self.minions = []
        self.invulnerable_states = set()
        self.rng = random.Random(seed)

    # ---------- Questions the game can ask ----------

    def is_alive(self):
        return self.hp > 0

    def is_defeated(self):
        return self.state == "dead"

    def hp_percent(self):
        return self.hp / self.max_hp

    @property
    def invulnerable(self):
        return self.state in self.invulnerable_states

    def get_intro(self):
        return self.intro

    def drop_loot(self):
        return list(self.loot)

    def hittables(self):
        """Everything the player's sword or spells can hit right now."""
        targets = [self] if self.is_alive() else []
        return targets + [m for m in self.minions if m.is_alive()]

    # ---------- Things that happen TO the boss ----------

    def take_damage(self, amount):
        """Returns the damage actually dealt (0 if the boss can't be hurt right now)."""
        if self.invulnerable or not self.is_alive():
            return 0
        self.hp = max(0, self.hp - amount)
        self.hit_flash = 0.12
        if self.hp <= 0:
            self.on_death()
        else:
            self.check_phase()
        return amount

    def heal(self, amount):
        if self.is_alive():
            self.hp = min(self.max_hp, self.hp + amount)

    def debug_set_hp_percent(self, percent):
        """Testing helper: jump the boss to a given HP percentage."""
        if self.is_alive() and not self.invulnerable:
            self.hp = max(1, int(self.max_hp * percent))
            self.check_phase()

    def check_phase(self):
        """Called after every hit. Change self.phase here. Optional."""
        pass

    def on_death(self):
        """Called once when HP reaches 0. Optional."""
        pass

    def on_hazard_hit(self, hazard):
        """Called when one of the boss's ground hazards hurts the player. Optional."""
        pass

    # ---------- Per-frame update ----------

    def set_state(self, state):
        self.state = state
        self.state_time = 0.0

    def update(self, dt, player, bounds):
        self.bounds = bounds
        self.clock += dt
        self.state_time += dt
        self.hit_flash = max(0.0, self.hit_flash - dt)
        self.shake = max(0.0, self.shake - dt * 1.5)
        self.update_ai(dt, player, bounds)
        self._update_attacks(dt, player, bounds)

    def update_ai(self, dt, player, bounds):
        raise NotImplementedError("Each boss must write its own update_ai()")

    def _update_attacks(self, dt, player, bounds):
        for p in self.projectiles:
            p.update(dt, player, bounds)
        self.projectiles = [p for p in self.projectiles if p.alive]

        for h in self.hazards:
            if h.update(dt, player):
                self.on_hazard_hit(h)
        self.hazards = [h for h in self.hazards if h.alive]

        for m in self.minions:
            m.update(dt, player, bounds)
        self.minions = [m for m in self.minions if m.is_alive()]

    def clear_attacks(self):
        self.projectiles = []
        self.hazards = []
        self.minions = []

    # ---------- Drawing ----------

    def draw(self, surface):
        for h in self.hazards:
            h.draw(surface)
        for m in self.minions:
            m.draw(surface)
        self.draw_boss(surface)
        for p in self.projectiles:
            p.draw(surface)
        self.draw_effects(surface)

    def draw_boss(self, surface):
        raise NotImplementedError("Each boss must write its own draw_boss()")

    def draw_effects(self, surface):
        pass

    def draw_debug(self, surface):
        for t in self.hittables():
            pygame.draw.circle(surface, (0, 255, 120), (int(t.x), int(t.y)), int(t.radius), 1)

    def draw_health_bar(self, surface, font):
        w, h = 520, 18
        x = (surface.get_width() - w) // 2
        y = 36
        pygame.draw.rect(surface, (30, 26, 44), (x - 3, y - 3, w + 6, h + 6))
        pygame.draw.rect(surface, (70, 40, 60), (x, y, w, h))
        fill = int(w * self.hp_percent())
        color = (127, 119, 221) if self.phase == 1 else (226, 75, 74)
        if fill > 0:
            pygame.draw.rect(surface, color, (x, y, fill, h))
        pygame.draw.line(surface, (238, 237, 254), (x + w // 2, y - 3), (x + w // 2, y + h + 3), 2)
        label = font.render(self.name, True, (238, 237, 254))
        surface.blit(label, (x, y - 26))
