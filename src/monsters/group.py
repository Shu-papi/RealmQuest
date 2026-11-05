"""
group.py - MonsterGroup: manages a bunch of monsters for a map, a room or an event.

    group = MonsterGroup()
    group.spawn("skeleton_warrior", 300, 400)                 # one monster
    group.spawn_wave(["skeleton_warrior"] * 3 + ["skeleton_archer"], bounds, player)   # an ambush

    # every frame
    group.update(dt, player, bounds)
    group.draw(surface)                      # sorted so monsters lower on screen are drawn in front

    # when the player attacks
    for target in group.hittables():
        ...check distance...
        deal_damage(target, 20, source=(player_x, player_y))

    for drop in group.take_drops():          # loot from monsters that just died
        drop["x"], drop["y"], drop["items"], drop["xp"]

It handles the boring parts: monsters shoving apart instead of stacking, the shatter animation after
death, friends that help each other (acolytes), raised-from-the-dead monsters, loot, screen shake.
"""
import math
import random

MAX_MONSTERS = 24                    # hard cap, so a runaway acolyte can't fill the screen


def separate(monsters, strength=0.6):
    """Push overlapping monsters apart so a crowd spreads out around the player."""
    live = [m for m in monsters if m.is_alive() and not m.spawning]
    for i in range(len(live)):
        a = live[i]
        for j in range(i + 1, len(live)):
            b = live[j]
            dx, dy = b.x - a.x, b.y - a.y
            gap = (a.radius + b.radius) * 0.85
            d = math.hypot(dx, dy)
            if d >= gap:
                continue
            if d < 1e-6:
                dx, dy, d = 1.0, 0.0, 1.0
            push = (gap - d) * strength * 0.5
            wa = b.radius / float(a.radius + b.radius)        # the lighter one moves more
            wb = 1.0 - wa
            a.x -= dx / d * push * 2 * wa
            a.y -= dy / d * push * 2 * wa
            b.x += dx / d * push * 2 * wb
            b.y += dy / d * push * 2 * wb


def collect_requests(monsters, limit=MAX_MONSTERS):
    """Monsters that others asked for (acolytes raising the dead). Returns the new ones."""
    new = []
    for m in monsters:
        for baby in m.take_spawn_requests():
            if len(monsters) + len(new) < limit:
                new.append(baby)
    return new


class MonsterGroup:
    def __init__(self, seed=None):
        from . import spawn_monster                                  # noqa: PLC0415
        self._spawn = spawn_monster
        self.rng = random.Random(seed)
        self.monsters = []           # alive (and still rising from the ground)
        self.remains = []            # dead, still playing the shatter animation
        self.drops = []
        self.shake = 0.0

    # ---------- adding monsters ----------

    def add(self, monster):
        monster.allies = self.monsters
        self.monsters.append(monster)
        return monster

    def spawn(self, name, x, y, **options):
        options.setdefault("seed", self.rng.random())
        return self.add(self._spawn(name, x, y, **options))

    def spawn_wave(self, names, bounds, player, min_distance=240, **options):
        """Spawn several monsters at random spots at least `min_distance` away from the player."""
        left, top, right, bottom = bounds
        px, py = player.rect.centerx, player.rect.centery
        made = []
        for name in names:
            x = y = 0.0
            for _attempt in range(20):
                x = self.rng.uniform(left + 40, right - 40)
                y = self.rng.uniform(top + 40, bottom - 40)
                if math.hypot(x - px, y - py) >= min_distance:
                    break
            made.append(self.spawn(name, x, y, **options))
        return made

    # ---------- questions ----------

    def hittables(self):
        return [m for m in self.monsters if m.is_alive()]

    def alive_count(self):
        return len(self.hittables())

    def is_clear(self):
        """True when every monster is dead (useful for 'defeat all enemies' events)."""
        return not self.hittables()

    def take_drops(self):
        drops, self.drops = self.drops, []
        return drops

    # ---------- every frame ----------

    def update(self, dt, player, bounds):
        for m in [m for m in self.monsters if not m.is_alive()]:
            self.monsters.remove(m)
            self.remains.append(m)
            self.drops.append({"x": m.x, "y": m.foot_y, "items": m.drop_loot(), "xp": m.xp,
                               "monster": m.NAME})
        for m in self.monsters:
            m.allies = self.monsters
            m.update(dt, player, bounds)
        for m in self.remains:
            m.update(dt, player, bounds)
        self.remains = [m for m in self.remains if not m.finished]
        separate(self.monsters)
        for baby in collect_requests(self.monsters):
            self.add(baby)
        self.shake = max([0.0] + [m.shake for m in self.monsters])

    def draw(self, surface):
        everyone = self.remains + self.monsters
        for m in sorted(everyone, key=lambda m: m.foot_y):
            m.draw(surface)

    def draw_debug(self, surface):
        for m in self.monsters:
            m.draw_debug(surface)

    def clear(self, shatter=True):
        """Remove every monster (shattering them, or instantly)."""
        for m in self.monsters:
            if shatter:
                m.kill()
                self.remains.append(m)
        self.monsters = []
