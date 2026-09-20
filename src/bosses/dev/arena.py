"""
arena.py - Fight the boss yourself! (test harness with a placeholder player)

Run (from the repo root):
    python src/bosses/dev/arena.py              fight the first boss
    python src/bosses/dev/arena.py lich_king    fight a specific boss
    python src/bosses/dev/arena.py --list       show all bosses

CONTROLS
    WASD / Arrow keys   move
    Mouse               aim
    Left click / SPACE  sword swing
    SHIFT               dash (you can't be hurt while dashing)
    R                   restart
    P                   (testing) skip the boss straight to phase 2
    G                   (testing) god mode on/off
    H                   (testing) show hitboxes
    ESC                 quit

The real player class will be written by another team. The boss only needs
player.rect and player.take_damage(amount), so the Player below is just a stand-in.
"""
import math
import os
import random
import sys

import pygame

SRC_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)

from bosses import get_boss, list_bosses  # noqa: E402

W, H = 960, 640
BOUNDS = (40, 110, 920, 600)      # left, top, right, bottom of the arena floor

BACKGROUND = (14, 12, 22)
FLOOR = (33, 29, 46)
GRID = (43, 38, 60)
WALL = (83, 74, 183)
TEXT = (238, 237, 254)

PLAYER_RADIUS = 14
PLAYER_SPEED = 260
DASH_SPEED = 720
DASH_TIME = 0.16
DASH_COOLDOWN = 0.9
SWORD_RANGE = 62
SWORD_DAMAGE = 20
SWORD_COOLDOWN = 0.4


class Player:
    """Placeholder player: moves, dashes and swings a sword."""

    def __init__(self, x, y):
        self.x = float(x)
        self.y = float(y)
        self.rect = pygame.Rect(0, 0, PLAYER_RADIUS * 2, PLAYER_RADIUS * 2)
        self.rect.center = (round(self.x), round(self.y))
        self.max_hp = 100
        self.hp = 100
        self.god = False
        self.invuln = 0.0
        self.dash_time = 0.0
        self.dash_cd = 0.0
        self.dash_dir = (0.0, 0.0)
        self.swing_time = 0.0
        self.swing_cd = 0.0
        self.facing = (0.0, -1.0)

    def take_damage(self, amount):
        if self.god or self.hp <= 0 or self.invuln > 0 or self.dash_time > 0:
            return 0
        self.hp = max(0, self.hp - amount)
        self.invuln = 0.7
        return amount

    def update(self, dt, inp, bounds, boss):
        self.invuln = max(0.0, self.invuln - dt)
        self.dash_cd = max(0.0, self.dash_cd - dt)
        self.swing_time = max(0.0, self.swing_time - dt)
        self.swing_cd = max(0.0, self.swing_cd - dt)

        mx, my = inp["move"]
        length = math.hypot(mx, my)
        if length > 0:
            mx, my = mx / length, my / length

        if self.dash_time > 0:
            self.dash_time -= dt
            self.x += self.dash_dir[0] * DASH_SPEED * dt
            self.y += self.dash_dir[1] * DASH_SPEED * dt
        else:
            self.x += mx * PLAYER_SPEED * dt
            self.y += my * PLAYER_SPEED * dt
            if inp["dash"] and self.dash_cd <= 0 and length > 0:
                self.dash_time = DASH_TIME
                self.dash_cd = DASH_COOLDOWN
                self.dash_dir = (mx, my)

        left, top, right, bottom = bounds
        self.x = max(left + PLAYER_RADIUS, min(right - PLAYER_RADIUS, self.x))
        self.y = max(top + PLAYER_RADIUS, min(bottom - PLAYER_RADIUS, self.y))
        self.rect.center = (round(self.x), round(self.y))

        ax, ay = inp["aim"]
        d = math.hypot(ax - self.x, ay - self.y)
        if d > 1:
            self.facing = ((ax - self.x) / d, (ay - self.y) / d)

        if inp["attack"] and self.swing_cd <= 0 and self.dash_time <= 0:
            self.swing_time = 0.18
            self.swing_cd = SWORD_COOLDOWN
            self._sword_hit(boss)

    def _sword_hit(self, boss):
        fx, fy = self.facing
        for target in boss.hittables():
            dx, dy = target.x - self.x, target.y - self.y
            dist = math.hypot(dx, dy)
            if dist > SWORD_RANGE + target.radius:
                continue
            if dist > target.radius + 20:
                cos_angle = max(-1.0, min(1.0, (dx * fx + dy * fy) / dist))
                if math.acos(cos_angle) > math.radians(75):
                    continue
            target.take_damage(SWORD_DAMAGE)

    def draw(self, surface):
        cx, cy = int(self.x), int(self.y)
        if self.invuln > 0 and self.dash_time <= 0 and int(self.invuln * 20) % 2 == 0:
            return
        color = (180, 220, 255) if self.dash_time > 0 else (66, 150, 240)
        pygame.draw.ellipse(surface, (18, 15, 28), (cx - 14, cy + 10, 28, 10))
        pygame.draw.circle(surface, color, (cx, cy), PLAYER_RADIUS)
        pygame.draw.circle(surface, (12, 68, 124), (cx, cy), PLAYER_RADIUS, 2)
        fx, fy = self.facing
        pygame.draw.line(surface, TEXT, (cx, cy), (int(cx + fx * 22), int(cy + fy * 22)), 3)
        if self.swing_time > 0:
            base = math.atan2(fy, fx)
            points = [(cx, cy)]
            for i in range(9):
                a = base - 1.3 + 2.6 * i / 8
                points.append((int(cx + math.cos(a) * SWORD_RANGE),
                               int(cy + math.sin(a) * SWORD_RANGE)))
            pygame.draw.polygon(surface, TEXT, points, 2)


def empty_input():
    return {"move": (0, 0), "aim": (W // 2, H // 2), "attack": False, "dash": False,
            "restart": False, "phase2": False, "god": False, "hitboxes": False}


class Game:
    def __init__(self, boss_name=None):
        self.boss_name = boss_name or list_bosses()[0]
        self.world = pygame.Surface((W, H))
        self.overlay = pygame.Surface((W, H), pygame.SRCALPHA)
        self.overlay.fill((0, 0, 0, 150))
        self.font = pygame.font.Font(None, 26)
        self.big_font = pygame.font.Font(None, 72)
        self.small_font = pygame.font.Font(None, 20)
        self.rng = random.Random()
        self.show_hitboxes = False
        self.reset()

    def reset(self):
        self.player = Player(480, 520)
        self.boss = get_boss(self.boss_name, 480, 230)
        self.result = None      # None, "victory" or "defeat"

    def update(self, dt, inp):
        if inp["restart"]:
            self.reset()
            return
        if inp["god"]:
            self.player.god = not self.player.god
        if inp["hitboxes"]:
            self.show_hitboxes = not self.show_hitboxes
        if inp["phase2"] and self.boss.phase == 1:
            self.boss.debug_set_hp_percent(0.5)

        if self.result is None:
            self.player.update(dt, inp, BOUNDS, self.boss)
        self.boss.update(dt, self.player, BOUNDS)

        if self.result is None:
            if self.player.hp <= 0:
                self.result = "defeat"
            elif self.boss.is_defeated():
                self.result = "victory"

    # ---------- drawing ----------

    def draw(self, screen):
        left, top, right, bottom = BOUNDS
        world = self.world
        world.fill(BACKGROUND)
        pygame.draw.rect(world, FLOOR, (left, top, right - left, bottom - top))
        for x in range(left, right + 1, 40):
            pygame.draw.line(world, GRID, (x, top), (x, bottom))
        for y in range(top, bottom + 1, 40):
            pygame.draw.line(world, GRID, (left, y), (right, y))
        pygame.draw.rect(world, WALL, (left, top, right - left, bottom - top), 3)

        self.boss.draw(world)
        self.player.draw(world)
        if self.show_hitboxes:
            self.boss.draw_debug(world)

        shake = self.boss.shake * 8
        offset = (int(self.rng.uniform(-shake, shake)), int(self.rng.uniform(-shake, shake)))
        screen.fill(BACKGROUND)
        screen.blit(world, offset)
        self.draw_ui(screen)

    def text(self, surface, font, message, color, center):
        image = font.render(message, True, color)
        surface.blit(image, (center[0] - image.get_width() // 2,
                             center[1] - image.get_height() // 2))

    def draw_ui(self, screen):
        boss = self.boss
        boss.draw_health_bar(screen, self.font)

        if boss.clock < 3.5 and self.result is None:
            self.text(screen, self.small_font, boss.get_intro(), TEXT, (W // 2, 84))
        elif boss.state == "transition":
            self.text(screen, self.small_font, f"{boss.name} unleashes its true power!",
                      (226, 75, 74), (W // 2, 84))

        bar_w = 200
        pygame.draw.rect(screen, (30, 26, 44), (20, H - 32, bar_w + 6, 20))
        pygame.draw.rect(screen, (70, 40, 60), (23, H - 29, bar_w, 14))
        fill = int(bar_w * self.player.hp / self.player.max_hp)
        if fill > 0:
            pygame.draw.rect(screen, (29, 158, 117), (23, H - 29, fill, 14))
        label = "HP" + ("  (GOD MODE)" if self.player.god else "")
        self.text(screen, self.small_font, label, TEXT, (60 if not self.player.god else 90, H - 44))

        self.text(screen, self.small_font,
                  "WASD move | Mouse aim | Click/Space sword | Shift dash | "
                  "P phase 2 | G god | H hitboxes | R restart",
                  (150, 148, 170), (W // 2 + 120, H - 20))

        if self.result is not None:
            screen.blit(self.overlay, (0, 0))
            if self.result == "victory":
                self.text(screen, self.big_font, "VICTORY", (151, 196, 89), (W // 2, 230))
                self.text(screen, self.font, boss.death_line, TEXT, (W // 2, 290))
                self.text(screen, self.font, "Loot: " + ", ".join(boss.drop_loot()),
                          (250, 199, 117), (W // 2, 330))
            else:
                self.text(screen, self.big_font, "DEFEATED", (226, 75, 74), (W // 2, 250))
            self.text(screen, self.font, "Press R to fight again", TEXT, (W // 2, 400))


def read_input(events):
    keys = pygame.key.get_pressed()
    inp = empty_input()
    mx = int(bool(keys[pygame.K_d] or keys[pygame.K_RIGHT])) - int(bool(keys[pygame.K_a] or keys[pygame.K_LEFT]))
    my = int(bool(keys[pygame.K_s] or keys[pygame.K_DOWN])) - int(bool(keys[pygame.K_w] or keys[pygame.K_UP]))
    inp["move"] = (mx, my)
    inp["aim"] = pygame.mouse.get_pos()
    for e in events:
        if e.type == pygame.KEYDOWN:
            if e.key == pygame.K_SPACE:
                inp["attack"] = True
            elif e.key in (pygame.K_LSHIFT, pygame.K_RSHIFT):
                inp["dash"] = True
            elif e.key == pygame.K_r:
                inp["restart"] = True
            elif e.key == pygame.K_p:
                inp["phase2"] = True
            elif e.key == pygame.K_g:
                inp["god"] = True
            elif e.key == pygame.K_h:
                inp["hitboxes"] = True
        elif e.type == pygame.MOUSEBUTTONDOWN and e.button == 1:
            inp["attack"] = True
    return inp


def main():
    args = sys.argv[1:]
    if args and args[0] == "--list":
        print("Bosses:", ", ".join(list_bosses()))
        return
    name = args[0] if args else list_bosses()[0]
    if name not in list_bosses():
        print(f"Unknown boss '{name}'. Choose from: {', '.join(list_bosses())}")
        return

    pygame.init()
    screen = pygame.display.set_mode((W, H))
    pygame.display.set_caption(f"RealmQuest - {name} boss test")
    clock = pygame.time.Clock()
    game = Game(name)

    running = True
    while running:
        dt = min(clock.tick(60) / 1000.0, 0.05)
        events = pygame.event.get()
        for e in events:
            if e.type == pygame.QUIT or (e.type == pygame.KEYDOWN and e.key == pygame.K_ESCAPE):
                running = False
        game.update(dt, read_input(events))
        game.draw(screen)
        pygame.display.flip()

    pygame.quit()


if __name__ == "__main__":
    main()
