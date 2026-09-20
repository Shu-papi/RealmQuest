# Bosses (`src/bosses/`)

Real-time, Pygame boss fights for RealmQuest. Currently: **the Lich King**.
Artwork lives in `assets/bosses/lich_king/` (see the README in that folder).

## Try it

Run these from the **repo root**:

```
python -m pip install pygame-ce
python src/bosses/dev/arena.py
```

`pygame-ce` is the Pygame version that installs on Python 3.14. It is used with
`import pygame` exactly like normal Pygame. Do not install both `pygame` and `pygame-ce`.

Controls: WASD move, mouse aim, click/Space sword, Shift dash.
Testing keys: P = skip to phase 2, G = god mode, H = show hitboxes, R = restart, ESC = quit.

```
python src/bosses/dev/arena.py --list                 # list every boss
python src/bosses/dev/arena.py lich_king              # fight a specific boss
python -m unittest discover -s src/bosses/tests       # automatic tests (every boss is checked)
python src/bosses/dev/check_sprites.py lich_king      # checks a boss's sprite PNGs
python src/bosses/lich_king/preview.py --live         # animated look at the Lich King's poses
```

**Adding a boss? Read [HOW_TO_ADD_A_BOSS.md](HOW_TO_ADD_A_BOSS.md).**

## Folder map

```
src/bosses/
  __init__.py            the boss registry: get_boss("lich_king"), list_bosses()
  base_boss.py           shared Boss blueprint (tell the team before changing)
  attacks.py             attacks any boss can use (Projectile)
  pixel_art.py           shared retro effects (dither, dissolve)
  paths.py               finds asset folders
  lich_king/             EVERYTHING for the Lich King: boss.py, art.py, minions, drain circle
  _template/             copy this to start a new boss
  dev/                   test arena and art tools. NOT part of the game
  tests/                 automatic tests (contract test covers every boss)
assets/bosses/<name>/    each boss's sprite PNGs
```

## For integration (DevOps)

Put `src` on the import path (or import as `src.bosses`), then:

```python
from bosses import get_boss            # or: from src.bosses import get_boss

boss = get_boss("lich_king", x=480, y=230)   # list_bosses() shows every boss

# every frame
boss.update(dt, player, (left, top, right, bottom))   # dt in seconds, arena bounds
boss.draw(screen)
boss.draw_health_bar(screen, font)

# when the player attacks
for target in boss.hittables():        # the boss AND its minions
    if in_range(target):               # target has .x .y .radius
        target.take_damage(20)

# status
boss.is_alive()      # False when HP is 0 (death animation starts)
boss.is_defeated()   # True when the death animation is done -> give rewards
boss.drop_loot()     # ["Crown of Bones", ...]
boss.death_line      # text to show
```

The boss needs only two things from the player:

- `player.rect` (a `pygame.Rect`)
- `player.take_damage(amount)` (return the damage dealt, or nothing)

If the real player uses different names, write a small adapter instead of editing the boss.

## Tuning the fight

All Lich King numbers (speed, wind-up times, bolt count, damage, healing) are at the top of
`lich_king/boss.py` in `PHASE_STATS` and the constants below it.

## Adding another boss

See [HOW_TO_ADD_A_BOSS.md](HOW_TO_ADD_A_BOSS.md).
