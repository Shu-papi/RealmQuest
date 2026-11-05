"""
dungeon_gen.py - random, branching floor layouts (pure data, no pygame).

    generate(floor_name, seed) -> Layout

Every floor has about 10 rooms on a 5 x 4 grid of cells. A main path runs from the
entrance to a gated room (the stairs on floors 1-2, the boss chamber on floor 3) and
branches hang off it: dead ends with loot, a shrine, and the rooms that hold the key
(floors 1-2) or the boss seals (floor 3).

Room 0 is always the entrance and the LAST room is always the gated room, so
`rooms[-1]` is the exit room and the boss room is `len(rooms) - 1`, as the rest of
the game expects.

Corridors only join rooms in neighbouring cells. Their bends run down the middle of the
gap between the two cells, so a corridor never runs along a room's wall and two
corridors never cross.
"""
from __future__ import annotations

import random
from dataclasses import dataclass, field

MAP_W, MAP_H = 288, 162
COLS, ROWS = 5, 4
CELL_W, CELL_H = 56, 39
X0, Y0 = 4, 3
MARGIN = 4                      # free tiles between a room and its cell edge (corridor space)
INNER_W, INNER_H = CELL_W - 2 * MARGIN, CELL_H - 2 * MARGIN      # 48 x 31

# roles with no monsters
SAFE_ROLES = {"start", "shrine", "trap", "stairs", "antechamber"}
MINI_FIRST = 11                 # dungeon numbers from here on are mini dungeons (see minis.py)
# rooms whose clearing drops a floor key / boss seal
KEY_ROLES = {"guard", "miniboss"}
SEAL_ROLES = {"seal", "miniboss"}
GATED_ROLES = {"stairs", "boss"}


@dataclass
class Layout:
    rooms: list                       # [(x, y, w, h)] in tiles
    roles: list                       # role name per room
    links: list                       # [(a, b)]
    routes: list                      # per link: list of (x, y) waypoints, a -> b
    parent: list                      # parent room per room (on the way back to the entrance)
    cells: list = field(default_factory=list)
    gated: int = -1                   # index of the gated room (always the last one)


def _size(role, rng, axis):
    """Room size (w, h) for a role. `axis` is 'h' or 'v': the direction of its main link."""
    r = rng.randint
    if role == "start":
        return r(20, 24), r(15, 18)
    if role == "boss":
        return r(44, INNER_W), r(28, INNER_H)
    if role in ("miniboss", "lair"):
        return r(32, 38), r(24, 28)
    if role in ("guard", "seal"):
        return r(26, 32), r(18, 23)
    if role in ("vault", "shrine", "stairs"):
        return r(16, 20), r(13, 15)
    if role == "trap":
        return (r(36, 44), r(13, 14)) if axis == "h" else (r(14, 16), r(26, 30))
    if role == "antechamber":
        return (r(28, 34), r(14, 16)) if axis == "h" else (r(16, 18), r(22, 26))
    # combat: chambers, long halls and tall halls
    shape = rng.random()
    if shape < 0.55:
        return r(26, 38), r(18, 26)
    if shape < 0.8:
        return r(38, 46), r(14, 17)
    return r(18, 24), r(26, 30)


def _recipe(floor, rng, mini=False):
    """(main path roles, branches). Each branch is a list of roles grown outward."""
    if mini:      # short and sweet: a few rooms, then the lair with its mini-boss
        path = ["start", "combat", "combat", "lair"]
        branches = rng.choice([[["vault"], ["combat"]], [["shrine"], ["combat", "vault"]],
                               [["trap", "vault"]], [["combat"], ["shrine"]]])
        return path, branches
    extras = rng.choice([[["shrine"], ["vault"]], [["combat", "vault"]], [["vault"], ["combat"]],
                         [["shrine"], ["combat", "vault"]]])
    if floor == 3:
        path = ["start", "combat", "combat", "antechamber", "boss"]
        branches = [["combat", "seal"], ["seal"], ["miniboss"], ["shrine"]]
    else:
        path = ["start", "combat", "combat", "combat", "combat", "stairs"]
        key = ["combat", "guard"] if floor == 1 else ["trap", "miniboss"]
        branches = [key] + extras
    return path, branches


def _neighbours(c):
    x, y = c
    for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
        nx, ny = x + dx, y + dy
        if 0 <= nx < COLS and 0 <= ny < ROWS:
            yield (nx, ny)


def _walk(rng, length):
    """Self-avoiding random walk over the cell grid (depth-first with backtracking)."""
    start = (rng.randrange(COLS), rng.randrange(ROWS))
    path = [start]

    def dfs():
        if len(path) == length:
            return True
        opts = [n for n in _neighbours(path[-1]) if n not in path]
        rng.shuffle(opts)
        for n in opts:
            path.append(n)
            if dfs():
                return True
            path.pop()
        return False

    return path if dfs() else None


def _graph(floor, rng, mini=False):
    path_roles, branches = _recipe(floor, rng, mini)
    cells = _walk(rng, len(path_roles))
    if cells is None:
        return None
    roles = list(path_roles)
    parent = [-1] + list(range(len(cells) - 1))
    links = [(i, i + 1) for i in range(len(cells) - 1)]
    used = set(cells)
    last = len(path_roles) - 1
    for br in branches:
        important = br[-1] in KEY_ROLES | SEAL_ROLES
        # attach to the entrance or a plain combat room; key / seal branches never hang off
        # the room right before the gate, so the player has to go exploring for them
        hosts = [k for k, role in enumerate(roles) if role in ("start", "combat")
                 and k != last and not (important and k >= last - 1 and k < len(path_roles))]
        rng.shuffle(hosts)
        placed = False
        for h in hosts:
            chain, cur = [], cells[h]
            for _ in br:
                opts = [n for n in _neighbours(cur) if n not in used and n not in chain]
                if not opts:
                    break
                cur = rng.choice(opts)
                chain.append(cur)
            if len(chain) != len(br):
                continue
            prev = h
            for role, c in zip(br, chain):
                cells.append(c)
                roles.append(role)
                used.add(c)
                k = len(cells) - 1
                parent.append(prev)
                links.append((prev, k))
                prev = k
            placed = True
            break
        if not placed:
            return None
    # an occasional loop between two plain rooms that happen to be neighbours
    if rng.random() < 0.5:
        plain = [k for k, role in enumerate(roles) if role in ("start", "combat")]
        pairs = [(a, b) for a in plain for b in plain if a < b
                 and abs(cells[a][0] - cells[b][0]) + abs(cells[a][1] - cells[b][1]) == 1
                 and (a, b) not in links and (b, a) not in links]
        if pairs:
            links.append(rng.choice(pairs))
    return cells, roles, links, parent, last


def _route(a, b, ca, cb, rng):
    """Waypoints from inside room a to inside room b (rooms as (x, y, w, h), cells ca, cb)."""
    ax, ay, aw, ah = a
    bx, by, bw, bh = b
    if ca[1] == cb[1]:                       # side by side
        flip = cb[0] < ca[0]
        if flip:
            ax, ay, aw, ah, bx, by, bw, bh = bx, by, bw, bh, ax, ay, aw, ah
        lo, hi = max(ay, by) + 5, min(ay + ah, by + bh) - 6
        if lo <= hi:
            y = rng.randint(lo, hi)
            pts = [(ax + aw - 4, y), (bx + 3, y)]
        else:
            ya, yb = rng.randint(ay + 5, ay + ah - 6), rng.randint(by + 5, by + bh - 6)
            gx = (ax + aw + bx) // 2
            pts = [(ax + aw - 4, ya), (gx, ya), (gx, yb), (bx + 3, yb)]
    else:                                    # one above the other
        flip = cb[1] < ca[1]
        if flip:
            ax, ay, aw, ah, bx, by, bw, bh = bx, by, bw, bh, ax, ay, aw, ah
        lo, hi = max(ax, bx) + 5, min(ax + aw, bx + bw) - 6
        if lo <= hi:
            x = rng.randint(lo, hi)
            pts = [(x, ay + ah - 4), (x, by + 3)]
        else:
            xa, xb = rng.randint(ax + 5, ax + aw - 6), rng.randint(bx + 5, bx + bw - 6)
            gy = (ay + ah + by) // 2
            pts = [(xa, ay + ah - 4), (xa, gy), (xb, gy), (xb, by + 3)]
    return pts[::-1] if flip else pts


def generate(floor_name: str, seed: int = 0) -> Layout:
    num, floor = (int(v) for v in floor_name.split("-"))
    mini = num >= MINI_FIRST
    for attempt in range(500):
        rng = random.Random("%s|%d|%d" % (floor_name, seed, attempt))
        g = _graph(floor, rng, mini)
        if g is None:
            continue
        cells, roles, links, parent, gated = g

        # main axis of each room = direction of the link to its parent (or first child)
        def axis(k):
            other = parent[k] if parent[k] >= 0 else next((b for a, b in links if a == k), k)
            return "h" if cells[other][1] == cells[k][1] else "v"

        rects = []
        for k, (c, role) in enumerate(zip(cells, roles)):
            w, h = _size(role, rng, axis(k))
            w, h = min(w, INNER_W), min(h, INNER_H)
            x = X0 + c[0] * CELL_W + MARGIN + rng.randint(0, INNER_W - w)
            y = Y0 + c[1] * CELL_H + MARGIN + rng.randint(0, INNER_H - h)
            rects.append((x, y, w, h))

        # order: entrance first, gated room last, the rest breadth-first from the entrance
        kids = {k: [] for k in range(len(cells))}
        for k, p in enumerate(parent):
            if p >= 0:
                kids[p].append(k)
        order, queue = [], [0]
        while queue:
            k = queue.pop(0)
            if k != gated:
                order.append(k)
            queue += kids[k]
        order.append(gated)
        new = {old: i for i, old in enumerate(order)}

        rooms = [rects[o] for o in order]
        rroles = [roles[o] for o in order]
        rcells = [cells[o] for o in order]
        rparent = [max(0, new[parent[o]]) if parent[o] >= 0 else 0 for o in order]
        rlinks = [(new[a], new[b]) for a, b in links]
        routes = [_route(rooms[a], rooms[b], rcells[a], rcells[b], rng) for a, b in rlinks]
        return Layout(rooms, rroles, rlinks, routes, rparent, rcells, len(rooms) - 1)
    raise RuntimeError("could not lay out floor %s" % floor_name)


VALID_FLOORS = {f"{d}-{f}" for d in range(1, 10) for f in (1, 2, 3)} | {f"{d}-1" for d in range(11, 17)}
