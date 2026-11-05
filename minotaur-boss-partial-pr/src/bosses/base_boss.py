"""
STAND-IN (rebuilt from what the Minotaur and its tests expect, so the partial PR runs on its own).
If your real repo already has bosses/base_boss.py, keep yours and delete this one.

A boss has hit points, a state machine (`state`, `state_time`, `set_state`), a list of ground hazards and of
projectiles, and subclasses fill in `update_ai(dt, player, bounds)` and the `_do_<state>` methods.
"""
import random

import pygame


class Boss:
    def __init__(self, name, max_hp, x, y, radius, intro="", death_line="", loot=None, seed=None):
        self.name = name
        self.max_hp = max_hp
        self.hp = max_hp
        self.x, self.y = float(x), float(y)
        self.radius = radius
        self.intro = intro
        self.death_line = death_line
        self.loot = list(loot or [])
        self.rng = random.Random(seed)
        self.state = "idle"
        self.state_time = 0.0
        self.clock = 0.0
        self.shake = 0.0
        self.hit_flash = 0.0
        self.phase = 1
        self.hazards = []
        self.projectiles = []
        self.invulnerable_states = set()

    # -- state ----------------------------------------------------------------
    def set_state(self, state):
        self.state = state
        self.state_time = 0.0

    def hp_percent(self):
        return self.hp / self.max_hp

    def is_alive(self):
        return self.hp > 0 and self.state not in ("dying", "dead")

    def is_defeated(self):
        return self.state == "dead"

    def drop_loot(self):
        return list(self.loot)

    def hittables(self):
        return [self]

    def clear_attacks(self):
        self.hazards = []
        self.projectiles = []

    # -- damage ---------------------------------------------------------------
    def take_damage(self, amount):
        """Returns the damage dealt (0 while he cannot be hurt)."""
        if self.state in self.invulnerable_states or self.hp <= 0:
            return 0
        self.hp = max(0, self.hp - amount)
        self.hit_flash = 0.1
        if self.hp <= 0:
            self.on_death()
        else:
            self.check_phase()
        return amount

    def debug_set_hp_percent(self, fraction):
        self.hp = max(1, int(self.max_hp * fraction))
        self.check_phase()

    def check_phase(self):
        """Subclasses change phase here."""

    def on_death(self):
        """Subclasses start their death animation here."""

    # -- per frame ------------------------------------------------------------
    def update(self, dt, player, bounds):
        self.clock += dt
        self.state_time += dt
        self.hit_flash = max(0.0, self.hit_flash - dt)
        self.shake = max(0.0, self.shake - dt * 2.2)
        if self.state != "dead":
            self.update_ai(dt, player, bounds)
        for hazard in self.hazards:
            hazard.update(dt, player)
        self.hazards = [h for h in self.hazards if h.alive]
        for shot in self.projectiles:
            shot.update(dt, player, bounds)
        self.projectiles = [s for s in self.projectiles if s.alive]

    def update_ai(self, dt, player, bounds):
        raise NotImplementedError

    # -- drawing --------------------------------------------------------------
    def draw(self, surface):
        self.draw_boss(surface)
        self.draw_effects(surface)

    def draw_boss(self, surface):
        pass

    def draw_effects(self, surface):
        pass

    def draw_health_bar(self, surface, font):
        width, x = 500, (surface.get_width() - 500) // 2
        pygame.draw.rect(surface, (20, 14, 20), (x - 2, 18, width + 4, 20))
        pygame.draw.rect(surface, (200, 50, 50), (x, 20, int(width * self.hp / self.max_hp), 16))
        surface.blit(font.render(self.name, True, (240, 236, 250)), (x, 40))
