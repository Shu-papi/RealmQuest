"""
arena.py - Fight monsters yourself! (test harness with a placeholder player)

Run (from the repo root):
    python src/monsters/dev/arena.py

CONTROLS
    1 2 3 4     spawn a Skeleton Warrior / Archer / Brute / Acolyte at the mouse
    5           spawn an ambush wave (warriors + archer + acolyte)
    V           cycle the variant for new spawns (bone, cursed, frost, ember, plague)
    K           kill everything (watch them shatter)
    C           clear the arena instantly
    WASD/Arrows move   Mouse aim   Click/SPACE sword   SHIFT dash (can't be hurt while dashing)
    G god mode   H show hitboxes   M mute   R reset   ESC quit

The real player class will be written by another team. Monsters only need
player.rect and player.take_damage(amount), so the Player below is just a stand-in.
"""
import math
import os
import sys

import pygame

SRC_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)

from bosses.dev import arena as boss_arena          # noqa: E402  (reuse the stand-in player)
from monsters import MonsterGroup, deal_damage, list_variants  # noqa: E402

W, H, BOUNDS = boss_arena.W, boss_arena.H, boss_arena.BOUNDS
TEXT = boss_arena.TEXT
SWORD_RANGE, SWORD_DAMAGE = boss_arena.SWORD_RANGE, boss_arena.SWORD_DAMAGE
KEYS = {pygame.K_1: "skeleton_warrior", pygame.K_2: "skeleton_archer",
        pygame.K_3: "skeleton_brute", pygame.K_4: "skeleton_acolyte"}
WAVE = ["skeleton_warrior", "skeleton_warrior", "skeleton_warrior",
        "skeleton_archer", "skeleton_acolyte"]


class Player(boss_arena.Player):
    """The stand-in player, but its sword pushes monsters back (knockback needs the source)."""

    def _sword_hit(self, group):
        fx, fy = self.facing
        for target in group.hittables():
            dx, dy = target.x - self.x, target.y - self.y
            dist = math.hypot(dx, dy)
            if dist > SWORD_RANGE + target.radius:
                continue
            if dist > target.radius + 20:
                cos_angle = max(-1.0, min(1.0, (dx * fx + dy * fy) / dist))
                if math.acos(cos_angle) > math.radians(75):
                    continue
            deal_damage(target, SWORD_DAMAGE, source=(self.x, self.y))


class Game:
    def __init__(self):
        self.world = pygame.Surface((W, H))
        self.font = pygame.font.Font(None, 24)
        self.small = pygame.font.Font(None, 20)
        self.rng_shake = __import__("random").Random()
        self.show_hitboxes = False
        self.variant_index = 0
        self.log = []
        self.reset()

    @property
    def variant(self):
        return list_variants()[self.variant_index]

    def reset(self):
        self.player = Player(480, 500)
        self.group = MonsterGroup()
        self.log = []
        self.group.spawn("skeleton_warrior", 480, 250, variant=self.variant)

    def spawn(self, name, pos):
        x = max(BOUNDS[0] + 30, min(BOUNDS[2] - 30, pos[0]))
        y = max(BOUNDS[1] + 30, min(BOUNDS[3] - 30, pos[1]))
        self.group.spawn(name, x, y, variant=self.variant)

    def update(self, dt, inp, events):
        for e in events:
            if e.type != pygame.KEYDOWN:
                continue
            if e.key in KEYS:
                self.spawn(KEYS[e.key], pygame.mouse.get_pos())
            elif e.key == pygame.K_5:
                self.group.spawn_wave(WAVE, BOUNDS, self.player, variant=self.variant)
            elif e.key == pygame.K_v:
                self.variant_index = (self.variant_index + 1) % len(list_variants())
            elif e.key == pygame.K_k:
                for m in list(self.group.monsters):
                    m.take_damage(10000) if not m.spawning else m.kill()
            elif e.key == pygame.K_c:
                self.group.clear(shatter=False)
                self.group.remains = []
            elif e.key == pygame.K_g:
                self.player.god = not self.player.god
            elif e.key == pygame.K_h:
                self.show_hitboxes = not self.show_hitboxes
            elif e.key == pygame.K_r:
                self.reset()
                return
        self.player.update(dt, inp, BOUNDS, self.group)
        self.group.update(dt, self.player, BOUNDS)
        for drop in self.group.take_drops():
            text = f"{drop['monster']}: " + (", ".join(drop["items"]) or "nothing") + f"  (+{drop['xp']} xp)"
            self.log = (self.log + [text])[-4:]

    def draw(self, screen):
        left, top, right, bottom = BOUNDS
        world = self.world
        world.fill(boss_arena.BACKGROUND)
        pygame.draw.rect(world, boss_arena.FLOOR, (left, top, right - left, bottom - top))
        for x in range(left, right + 1, 40):
            pygame.draw.line(world, boss_arena.GRID, (x, top), (x, bottom))
        for y in range(top, bottom + 1, 40):
            pygame.draw.line(world, boss_arena.GRID, (left, y), (right, y))
        pygame.draw.rect(world, boss_arena.WALL, (left, top, right - left, bottom - top), 3)

        self.group.draw(world)
        self.player.draw(world)
        if self.show_hitboxes:
            self.group.draw_debug(world)

        shake = self.group.shake * 8
        offset = (int(self.rng_shake.uniform(-shake, shake)), int(self.rng_shake.uniform(-shake, shake)))
        screen.fill(boss_arena.BACKGROUND)
        screen.blit(world, offset)
        self.draw_ui(screen)

    def text(self, screen, font, message, color, pos):
        screen.blit(font.render(message, True, color), pos)

    def draw_ui(self, screen):
        p = self.player
        pygame.draw.rect(screen, (30, 26, 44), (20, 20, 206, 20))
        pygame.draw.rect(screen, (70, 40, 60), (23, 23, 200, 14))
        fill = int(200 * p.hp / p.max_hp)
        if fill > 0:
            pygame.draw.rect(screen, (29, 158, 117), (23, 23, fill, 14))
        if p.hp <= 0:
            self.text(screen, self.font, "You died. Press R", (226, 75, 74), (240, 22))
        self.text(screen, self.small,
                  f"1 Warrior  2 Archer  3 Brute  4 Acolyte  5 Wave  |  V variant: {self.variant}  |  "
                  f"K kill all  C clear  G god{' (ON)' if p.god else ''}  H hitboxes  R reset",
                  (150, 148, 170), (20, 52))
        self.text(screen, self.small, f"monsters alive: {self.group.alive_count()}", TEXT, (20, 76))
        for i, line in enumerate(self.log):
            self.text(screen, self.small, "loot  " + line, (250, 199, 117), (20, H - 100 + i * 20))


def main():
    pygame.init()
    import audio
    from bosses.dev.arena import load_settings
    audio.init(load_settings())                  # monsters make their own sounds; no sound card = silent
    screen = pygame.display.set_mode((W, H))
    pygame.display.set_caption("RealmQuest - monster arena")
    clock = pygame.time.Clock()
    game = Game()
    running = True
    while running:
        dt = min(clock.tick(60) / 1000.0, 0.05)
        events = pygame.event.get()
        for e in events:
            if e.type == pygame.QUIT or (e.type == pygame.KEYDOWN and e.key == pygame.K_ESCAPE):
                running = False
        for e in events:
            if e.type == pygame.KEYDOWN and e.key == pygame.K_m:
                audio.toggle_muted()
        inp = boss_arena.read_input(events)
        audio.update(dt)
        game.update(dt, inp, events)
        game.draw(screen)
        pygame.display.flip()
    audio.shutdown()
    pygame.quit()


if __name__ == "__main__":
    main()
