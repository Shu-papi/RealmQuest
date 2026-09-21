"""
_template/boss.py - START HERE when making a new boss.

This is a tiny but COMPLETE boss: it stands still, warns you (turns red),
then fires one bolt at you. It draws itself as a plain circle. Copy this
folder, rename things, then make it yours.

WHAT YOU MUST KEEP (the game and the automatic tests rely on these)
  * update_ai(dt, player, bounds)   decides what the boss does each frame
  * draw_boss(surface)              draws the boss
  * on_death()                      must lead to the state "dying", then "dead"
  * the state "dead" is what makes is_defeated() True (rewards are given then)

STATE HABIT: give every state its own small function called _do_<state>.
update_ai() below calls the right one automatically.
Always show a WARNING (wind-up) before a dangerous attack so players can react.
"""
import math
import pygame

from ..base_boss import Boss
from ..attacks import Projectile


class TemplateBoss(Boss):
    def __init__(self, x=480, y=230, seed=None):
        super().__init__(
            name="Template Boss",          # shown above the health bar
            max_hp=200,
            x=x,
            y=y,
            radius=40,                     # how big his hitbox is (pixels)
            intro="A plain circle blocks your way.",
            death_line="The template boss pops.",
            loot=["Template Trophy"],
            seed=seed,
        )
        self.invulnerable_states = {"dying", "dead"}   # states where he can't be hurt
        self.set_state("idle")
        self.cooldown = 1.5

    # ------------------------------------------------------------------
    # AI: one small function per state
    # ------------------------------------------------------------------

    def update_ai(self, dt, player, bounds):
        getattr(self, "_do_" + self.state)(dt, player, bounds)

    def _do_idle(self, dt, player, bounds):
        self.cooldown -= dt
        if self.cooldown <= 0:
            self.set_state("windup")                   # warn the player first

    def _do_windup(self, dt, player, bounds):
        if self.state_time >= 0.8:                     # 0.8 seconds of warning
            angle = math.atan2(player.rect.centery - self.y,
                               player.rect.centerx - self.x)
            #                            x,      y,      angle, speed, damage
            self.projectiles.append(Projectile(self.x, self.y, angle, 300, 10))
            self.cooldown = 1.5
            self.set_state("idle")

    def _do_dying(self, dt, player, bounds):
        if self.state_time >= 1.0:
            self.set_state("dead")

    def _do_dead(self, dt, player, bounds):
        pass

    def on_death(self):
        self.clear_attacks()
        self.set_state("dying")

    # ------------------------------------------------------------------
    # Drawing (swap this for pixel art later)
    # ------------------------------------------------------------------

    def draw_boss(self, surface):
        if self.state == "dead":
            return
        if self.hit_flash > 0:
            color = (255, 255, 255)                    # white flash when hit
        elif self.state == "windup":
            color = (226, 75, 74)                      # red = "attack coming!"
        else:
            color = (127, 119, 221)
        pygame.draw.circle(surface, color, (int(self.x), int(self.y)), self.radius)
