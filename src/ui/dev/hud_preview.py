"""
hud_preview.py - Try the HUD on its own, without the rest of the game.

Run from the repo root:
    python src/ui/dev/hud_preview.py

KEYS
    H      take 1 damage (armor soaks it first, then health, like Soul Knight)
    E      use 20 energy (like firing a weapon)
    A      regain 1 armor
    R      refill everything
    ESC    quit

The player here is a stand-in. The real player class belongs to the
Characters & Skills team. The HUD only needs the six numbers below.
"""
import os
import sys

SRC_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)

import pygame

from ui.hud import HUD

W, H = 640, 360
BACKGROUND = (34, 30, 40)
HINT = (200, 200, 200)


class PreviewPlayer:
    def __init__(self):
        self.max_hp, self.max_armor, self.max_energy = 5, 5, 200
        self.refill()

    def refill(self):
        self.hp, self.armor, self.energy = self.max_hp, self.max_armor, self.max_energy

    def take_damage(self, amount):
        soaked = min(self.armor, amount)
        self.armor -= soaked
        self.hp = max(0, self.hp - (amount - soaked))

    def use_energy(self, amount):
        if self.energy >= amount:
            self.energy -= amount
            return True
        return False


def main():
    pygame.init()
    screen = pygame.display.set_mode((W, H))
    pygame.display.set_caption("RealmQuest - HUD preview")
    clock = pygame.time.Clock()
    hint_font = pygame.font.Font(None, 22)

    player = PreviewPlayer()
    hud = HUD(x=12, y=12)

    running = True
    while running:
        dt = clock.tick(60) / 1000
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    running = False
                elif event.key == pygame.K_h:
                    player.take_damage(1)
                elif event.key == pygame.K_e:
                    player.use_energy(20)
                elif event.key == pygame.K_a:
                    player.armor = min(player.max_armor, player.armor + 1)
                elif event.key == pygame.K_r:
                    player.refill()

        hud.update(dt, player)

        screen.fill(BACKGROUND)
        hud.draw(screen)
        hint = hint_font.render("H: damage   E: use energy   A: +1 armor   R: refill   ESC: quit",
                                True, HINT)
        screen.blit(hint, (12, H - 30))
        pygame.display.flip()

    pygame.quit()


if __name__ == "__main__":
    main()
