"""
Goblin King (Valdur) - real-time boss for the Goblin Dungeon.

Code:    src/bosses/goblin_king/   (goblin_king.py + boss_config.py)
Art:     assets/bosses/goblin_king/

Play it on its own (from the repo root):
    python src/bosses/goblin_king/goblin_king.py
Tests:
    python -m unittest discover -s src/bosses/goblin_king/tests
"""
import math
from pathlib import Path

import pygame

try:                                   # imported as a package: bosses.goblin_king
    from . import boss_config as cfg
except ImportError:                    # run directly as a script
    import boss_config as cfg

SCREEN_W, SCREEN_H = 800, 500
REPO_ROOT = Path(__file__).resolve().parents[3]
ASSET_DIR = REPO_ROOT / "assets" / "bosses" / "goblin_king"


def load_image(path):
    return pygame.image.load(str(ASSET_DIR / path)).convert_alpha()

BIG_ATTACKS = {"heavy": cfg.HEAVY, "special": cfg.SPECIAL}


def get_anim(state):
    return BIG_ATTACKS.get(state) or cfg.ANIMS[state]


# ====================== SPRITE LOADING ======================
def pixel_art(frame, scale, pixel_size):
    """Resize a frame by `scale` and turn it into chunky, crisp pixels.
    1) shrink to a small grid  2) cut soft edges  3) enlarge with hard edges."""
    p = pixel_size
    output_w = max(1, round(frame.get_width() * scale))
    output_h = max(1, round(frame.get_height() * scale))
    w = max(1, round(output_w / p))
    h = max(1, round(output_h / p))
    small = pygame.transform.scale(frame, (w, h))
    if cfg.HARD_EDGES:
        mask = pygame.mask.from_surface(small, cfg.ALPHA_CUTOFF)
        solid = small.copy()
        solid.fill((0, 0, 0, 255), special_flags=pygame.BLEND_RGBA_MAX)   # make opaque
        small = mask.to_surface(setsurface=solid, unsetcolor=(0, 0, 0, 0))
    return pygame.transform.scale(small, (output_w, output_h))


def smooth_or_pixel(frame, scale, native_nearest=False, force_pixel=False,
                    pixel_size=cfg.PIXEL_SIZE_BASE):
    if (cfg.PIXELATE or force_pixel) and pixel_size > 1:
        return pixel_art(frame, scale, pixel_size)
    size = (round(frame.get_width() * scale), round(frame.get_height() * scale))
    if native_nearest:
        return pygame.transform.scale(frame, size)
    return pygame.transform.smoothscale(frame, size)


def compute_big_scale(base_scale=None):
    """Scale for the heavy/special sheets so the boss's idle pose is exactly as
    tall as the base sheet's idle pose (no size pop when an attack starts)."""
    if not cfg.AUTO_MATCH_SIZE:
        return cfg.BIG_SCALE
    base = load_image(cfg.SHEET).subsurface(
        pygame.Rect(0, 0, cfg.FRAME_W, cfg.FRAME_H))
    big = load_image(cfg.HEAVY_SHEET).subsurface(
        pygame.Rect(0, 0, cfg.BIG_CELL, cfg.BIG_CELL))
    base_h = base.get_bounding_rect().height * (base_scale or cfg.BASE_SCALE)
    big_h = big.get_bounding_rect().height
    return base_h / big_h


def slice_base_sheet(path, base_scale=None):
    """frames[row][col] for idle and walk."""
    sheet = load_image(path)
    cols = sheet.get_width() // cfg.FRAME_W
    rows = sheet.get_height() // cfg.FRAME_H
    frames = []
    for r in range(rows):
        row = []
        for c in range(cols):
            rect = pygame.Rect(c * cfg.FRAME_W, r * cfg.FRAME_H, cfg.FRAME_W, cfg.FRAME_H)
            row.append(smooth_or_pixel(sheet.subsurface(rect), base_scale or cfg.BASE_SCALE,
                                       native_nearest=True, force_pixel=cfg.PIXELATE_BASE,
                                       pixel_size=cfg.PIXEL_SIZE_BASE))
        frames.append(row)
    return frames


def slice_big_sheet(path, scale):
    """Cut a grid sheet into right-facing and mirrored frames."""
    sheet = load_image(path)
    right, left = [], []
    for r in range(cfg.BIG_GRID):
        for c in range(cfg.BIG_GRID):
            rect = pygame.Rect(c * cfg.BIG_CELL, r * cfg.BIG_CELL, cfg.BIG_CELL, cfg.BIG_CELL)
            img = smooth_or_pixel(sheet.subsurface(rect), scale,
                                  force_pixel=cfg.PIXELATE_ATTACKS,
                                  pixel_size=cfg.PIXEL_SIZE_ATTACKS)
            right.append(img)
            left.append(pygame.transform.flip(img, True, False))
    return {"right": right, "left": left,
            "ax": cfg.BIG_ANCHOR[0] * scale,
            "ay": cfg.BIG_ANCHOR[1] * scale}


def sector_points(cx, cy, radius, angle, arc, squash=1.0, steps=24):
    """Points of a pie slice on the ground, centred on `angle` (radians).
    `squash` flattens it vertically. arc >= 360 gives a full oval."""
    full = arc >= 360
    span = math.radians(arc)
    start = angle - span / 2
    pts = [] if full else [(cx, cy)]
    for i in range(steps + 1):
        a = start + span * i / steps
        pts.append((cx + math.cos(a) * radius, cy + math.sin(a) * radius * squash))
    return pts


# ====================== BOSS ======================
class GoblinKing:
    """The Goblin King. `tuning` overrides boss_config for one instance (the game uses
    boss_config.IN_GAME): base_scale, dist_k, squash, max_hp, speed, damage, overhead."""

    def __init__(self, x, y, tuning=None):
        t = dict(tuning or {})
        self.x, self.y = x, y
        self.base_scale = t.get("base_scale", cfg.BASE_SCALE)
        self.k = self.base_scale / cfg.BASE_SCALE            # sprite size compared to the config
        self.dk = t.get("dist_k", 1.0)                       # ranges and dash distances
        self.squash = t.get("squash", cfg.GROUND_SQUASH)
        self.feet_offset = cfg.FEET_OFFSET * self.k
        self.bar_offset = 90 * self.k
        self.show_overhead = t.get("overhead", True)
        self.max_hp = self.hp = t.get("max_hp", cfg.MAX_HP)
        self.speed = t.get("speed", cfg.WALK_SPEED)
        self.aggro_range = cfg.AGGRO_RANGE * self.dk
        self.forget_range = None if cfg.FORGET_RANGE is None else cfg.FORGET_RANGE * self.dk
        self.heavy_range = cfg.HEAVY_TRIGGER_RANGE * self.dk
        self.special_range = cfg.SPECIAL_TRIGGER_RANGE * self.dk
        dmg = t.get("damage", {})
        self.hits = {name: {f: (reach * self.dk, dmg.get(name, {}).get(f, d), arc)
                            for f, (reach, d, arc) in anim.get("hits", {}).items()}
                     for name, anim in BIG_ATTACKS.items()}
        self.dir = "down"
        self.facing_left = False
        self.state = "idle"
        self.frame_time = 0.0
        self.frame_index = 0
        self.heavy_cooldown = cfg.START_HEAVY_COOLDOWN
        self.special_cooldown = cfg.START_SPECIAL_COOLDOWN
        self.hits_done = set()
        self.dead = False
        self.hurt_timer = 0.0
        self.aggro = False
        self.alert_timer = 0.0
        self.attack_angle = 0.0      # direction of the current attack (radians)
        self.font = pygame.font.SysFont(None, 24)
        self.alert_font = pygame.font.SysFont(None, 56)

        self.big_scale = compute_big_scale(self.base_scale)
        self.load_frames()

    def load_frames(self):
        """(Re)build every sprite frame."""
        self.base = slice_base_sheet(cfg.SHEET, self.base_scale)
        self.big = {"heavy": slice_big_sheet(cfg.HEAVY_SHEET, self.big_scale),
                    "special": slice_big_sheet(cfg.SPECIAL_SHEET, self.big_scale)}

    # ---------- helpers ----------
    @property
    def busy(self):
        return self.state in BIG_ATTACKS

    @property
    def ground(self):
        """Point on the floor under the boss's feet."""
        return self.x, self.y + self.feet_offset

    def offset_to(self, target):
        """(dx, dy) from his feet to the target, with dy stretched back out so
        distances and angles are measured on the squashed floor."""
        gx, gy = self.ground
        return target.x - gx, (target.y - gy) / self.squash

    def set_state(self, state):
        if self.state != state:
            self.state = state
            self.frame_index = 0
            self.frame_time = 0.0

    def wake(self):
        """Trigger the boss. Once triggered he stays aggressive."""
        if not self.aggro:
            self.aggro = True
            self.alert_timer = cfg.ALERT_TIME      # shows the "!" icon

    def start_attack(self, name):
        """name: 'attack' (basic), 'heavy' or 'special'."""
        if self.dead or self.busy:
            return
        self.set_state(name)
        self.hits_done = set()
        # Big attacks only face left or right.
        if name in BIG_ATTACKS:
            self.attack_angle = math.pi if self.facing_left else 0.0
        else:
            self.attack_angle = {"right": 0.0, "left": math.pi,
                                 "down": math.pi / 2, "up": -math.pi / 2}[self.dir]
        if name == "heavy":
            self.heavy_cooldown = cfg.HEAVY_COOLDOWN
        elif name == "special":
            enraged = self.hp < self.max_hp * cfg.ENRAGE_HP_FRACTION
            self.special_cooldown = (cfg.SPECIAL_COOLDOWN_ENRAGED if enraged
                                     else cfg.SPECIAL_COOLDOWN)

    def take_damage(self, amount):
        self.hp = max(0, self.hp - amount)
        self.hurt_timer = cfg.HURT_FLASH_TIME     # red flash
        self.wake()                               # being hit also triggers him
        if self.hp == 0:
            self.dead = True
            self.set_state("idle")

    def in_arc(self, dx, dy, arc):
        """True if the offset (dx, dy) is inside the attack's cone."""
        if arc >= 360:
            return True
        diff = math.atan2(dy, dx) - self.attack_angle
        diff = (diff + math.pi) % (2 * math.pi) - math.pi
        return abs(diff) <= math.radians(arc) / 2

    # ---------- update ----------
    def update(self, dt, target):
        self.hurt_timer = max(0.0, self.hurt_timer - dt)
        self.alert_timer = max(0.0, self.alert_timer - dt)
        if self.dead:
            return
        self.heavy_cooldown = max(0.0, self.heavy_cooldown - dt)
        self.special_cooldown = max(0.0, self.special_cooldown - dt)

        gx, gy = self.ground
        rdx, rdy = target.x - gx, target.y - gy            # real offset (for moving)
        real = max(math.hypot(rdx, rdy), 0.001)
        fdx, fdy = self.offset_to(target)                  # floor offset (for ranges)
        dist = max(math.hypot(fdx, fdy), 0.001)

        if not self.busy:
            if not self.aggro and dist <= self.aggro_range:
                self.wake()
            elif (self.aggro and self.forget_range is not None
                  and dist > self.forget_range):
                self.aggro = False

            if not self.aggro:
                self.set_state("idle")          # hasn't noticed the player yet
            else:
                self.facing_left = fdx < 0
                if abs(fdx) > abs(fdy):
                    self.dir = "left" if fdx < 0 else "right"
                else:
                    self.dir = "up" if fdy < 0 else "down"

                if self.special_cooldown == 0 and dist <= self.special_range:
                    self.start_attack("special")
                elif self.heavy_cooldown == 0 and dist <= self.heavy_range:
                    self.start_attack("heavy")
                elif dist > self.heavy_range:
                    self.set_state("walk")
                    self.x += rdx / real * self.speed * dt
                    self.y += rdy / real * self.speed * dt
                else:
                    self.set_state("idle")

        anim = get_anim(self.state)

        # rush / jump forward during the dash frames
        dash = anim.get("dash")
        if dash and dash[0] <= self.frame_index <= dash[1] and dist > 40 * self.dk:
            self.x += rdx / real * dash[2] * self.dk * dt
            self.y += rdy / real * dash[2] * self.dk * dt

        # advance animation
        self.frame_time += dt
        if self.frame_time >= 1 / anim["fps"]:
            self.frame_time = 0.0
            self.frame_index += 1
            if self.frame_index >= len(anim["frames"]):
                if anim["once"]:
                    self.set_state("idle")
                    return
                self.frame_index = 0

        # deal damage on hit frames (once per hit)
        hit = self.hits.get(self.state, {}).get(self.frame_index)
        if hit and self.frame_index not in self.hits_done:
            self.hits_done.add(self.frame_index)
            reach, damage, arc = hit
            tdx, tdy = self.offset_to(target)
            if math.hypot(tdx, tdy) <= reach and self.in_arc(tdx, tdy, arc):
                self.hurt_target(target, damage)

    @staticmethod
    def hurt_target(target, damage):
        """target.hurt(damage) when the target has it (the game's hero), else target.hp -= damage."""
        hurt = getattr(target, "hurt", None)
        if callable(hurt):
            hurt(damage)
        else:
            target.hp -= damage

    # ---------- indicators ----------
    def draw_telegraph(self, screen):
        """Warning drawn on the floor at the boss's feet. It shows the real hit
        area (a flat cone or oval) and fills up until the hit lands."""
        if not cfg.SHOW_INDICATORS or self.dead or not self.busy:
            return
        anim = get_anim(self.state)
        hits = self.hits.get(self.state, {})
        upcoming = [f for f in hits
                    if f >= self.frame_index and f not in self.hits_done]
        if not upcoming:
            return
        hit_frame = min(upcoming)
        reach, _, arc = hits[hit_frame]
        # smooth progress through the frames, so slow attacks fill up slowly
        pos = self.frame_index + self.frame_time * anim["fps"]
        progress = min(1.0, pos / hit_frame) if hit_frame > 0 else 1.0

        # Attack indicators are viewed directly from above, unlike the floor.
        sq = 1.0
        w = int(reach * 2) + 8
        h = int(reach * 2 * sq) + 8
        cx, cy = w // 2, h // 2
        layer = pygame.Surface((w, h), pygame.SRCALPHA)
        color = cfg.TELEGRAPH_COLOR
        full = sector_points(cx, cy, reach, self.attack_angle, arc, sq)
        filled = sector_points(cx, cy, max(1.0, reach * progress), self.attack_angle, arc, sq)
        pygame.draw.polygon(layer, color + (45,), full)           # danger zone
        pygame.draw.polygon(layer, color + (120,), filled)        # fills up
        pygame.draw.polygon(layer, color + (220,), full, 3)       # outline
        gx, gy = self.ground
        screen.blit(layer, (gx - cx, gy - cy))

    def draw_overhead(self, screen):
        """Boss name above the HP bar, and a '!' when he notices the player."""
        if not cfg.SHOW_INDICATORS or self.dead or not self.show_overhead:
            return
        bar_y = self.y - self.bar_offset
        name = self.font.render(cfg.BOSS_NAME, True, (255, 255, 255))
        screen.blit(name, name.get_rect(midbottom=(self.x, bar_y - 3)))
        if self.alert_timer > 0:
            mark = self.alert_font.render("!", True, (255, 220, 50))
            screen.blit(mark, mark.get_rect(midbottom=(self.x, bar_y - 22)))

    # ---------- draw ----------
    def draw(self, screen, cam=(0, 0)):
        """Draw at world position minus `cam` (the game's camera); (0, 0) = screen coords."""
        if cam == (0, 0):
            return self._draw(screen)
        self.x, self.y = self.x - cam[0], self.y - cam[1]
        try:
            self._draw(screen)
        finally:
            self.x, self.y = self.x + cam[0], self.y + cam[1]

    def _draw(self, screen):
        self.draw_telegraph(screen)          # on the floor, under the sprite

        anim = get_anim(self.state)
        pos = min(self.frame_index, len(anim["frames"]) - 1)
        col = anim["frames"][pos]

        if self.state in BIG_ATTACKS:
            sheet = self.big[self.state]
            side = "left" if self.facing_left else "right"
            image = sheet[side][col]
            ax = image.get_width() - sheet["ax"] if self.facing_left else sheet["ax"]
            top_left = (self.x - ax, self.y + self.feet_offset - sheet["ay"])
        else:
            image = self.base[cfg.DIRECTION_ROWS[self.dir]][col]
            bounds = image.get_bounding_rect()
            top_left = (
                self.x - image.get_width() / 2,
                self.y + self.feet_offset - bounds.bottom,
            )

        if self.hurt_timer > 0 or self.dead:
            image = image.copy()
            if self.hurt_timer > 0:
                # red flash: multiply by the tint colour, then add a little red
                image.fill(cfg.HURT_TINT + (255,), special_flags=pygame.BLEND_RGBA_MULT)
                image.fill((90, 0, 0, 0), special_flags=pygame.BLEND_RGB_ADD)
            if self.dead:
                image.set_alpha(100)
        screen.blit(image, top_left)

        if not self.show_overhead:
            return
        # boss HP bar
        bar_w = 80
        bar_x, bar_y = self.x - bar_w / 2, self.y - self.bar_offset
        pygame.draw.rect(screen, (64, 0, 0), (bar_x, bar_y, bar_w, 8))
        pygame.draw.rect(screen, (220, 50, 50),
                         (bar_x, bar_y, bar_w * self.hp / self.max_hp, 8))
        self.draw_overhead(screen)


class Player:
    """Stand-in player. x, y is the point on the floor where he stands."""
    def __init__(self, x, y):
        self.x, self.y = x, y
        self.hp = 100
        self.speed = 140


def main():
    pygame.init()
    screen = pygame.display.set_mode((SCREEN_W, SCREEN_H))
    pygame.display.set_caption("Goblin King Boss")
    clock = pygame.time.Clock()
    font = pygame.font.SysFont(None, 24)

    player = Player(150, 400)
    boss = GoblinKing(560, 200)

    running = True
    while running:
        dt = min(clock.tick(60) / 1000, 0.05)

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_SPACE:
                    fdx, fdy = boss.offset_to(player)
                    if math.hypot(fdx, fdy) < 90:
                        boss.take_damage(25)
                elif event.key == pygame.K_2:
                    boss.start_attack("heavy")
                elif event.key == pygame.K_3:
                    boss.start_attack("special")
                elif event.key == pygame.K_p:
                    cfg.PIXELATE = not cfg.PIXELATE      # toggle pixels live
                    boss.load_frames()

        keys = pygame.key.get_pressed()
        step = player.speed * dt
        if keys[pygame.K_LEFT] or keys[pygame.K_a]:
            player.x -= step
        if keys[pygame.K_RIGHT] or keys[pygame.K_d]:
            player.x += step
        if keys[pygame.K_UP] or keys[pygame.K_w]:
            player.y -= step
        if keys[pygame.K_DOWN] or keys[pygame.K_s]:
            player.y += step

        boss.update(dt, player)

        screen.fill((44, 42, 53))
        boss.draw(screen)
        pygame.draw.circle(screen, (68, 170, 255), (int(player.x), int(player.y)), 10)

        lines = [f"Player HP: {max(0, player.hp)}   Boss: {boss.state}   Triggered: {boss.aggro}   Pixelate: {cfg.PIXELATE}",
                 "Move: arrows/WASD   Hit boss: Space   Force attack: 2 heavy, 3 special   P: toggle pixels"]
        for i, text in enumerate(lines):
            screen.blit(font.render(text, True, (255, 255, 255)), (10, 10 + i * 22))
        if boss.dead:
            screen.blit(font.render("Goblin King defeated!", True, (255, 255, 255)), (330, 240))
        if player.hp <= 0:
            screen.blit(font.render("You died!", True, (255, 255, 255)), (365, 240))

        pygame.display.flip()

    pygame.quit()
if __name__ == "__main__":
    main()