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
Testing keys: P = jump to the next phase (press it twice for phase 3), G = god mode, H = show hitboxes, R = restart, ESC = quit.

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
  lich_king/             EVERYTHING for the Lich King: boss.py, art.py, minions.py (which skeletons he calls), drain circle
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
        target.take_damage(20)         # or deal_damage(target, 20, source=(px, py)) from
                                       # `monsters`: the same, plus knockback on minions

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

**Optional: status effects.** If the player also has `apply_status(name, seconds)`, bosses use it for
`"root"` (cannot move or dash) and `"slow"` (half speed). The Lich King's Grasping Hands root you.
Return `False` while the player is invulnerable (dashing, god mode) and nothing happens. A player without
this method simply ignores the effect, so nothing breaks. The stand-in player in `dev/arena.py`
shows one way to do it.

## The Lich King's fight

The Lich King is the **last boss**, so the fight is built to feel **overwhelming**: a huge health pool
(`BOSS_MAX_HP = 3000`), skills chained back to back, and an undying skeleton army. It is still beatable.

| Phase | HP | Attacks | Chain |
|-------|----|---------|-------|
| 1 | 100-50% | **Shadow Volley**, **Life Drain** (heals him if it hits), **Soul Rain** | 2 attacks |
| 2 | 50-25% | + **Bone Nova**, **Grasping Hands**, **Soul Barrage**, **skeleton army** (8 slots), teleporting | 3 attacks |
| 3 "Last Stand" | below 25% | Everything faster and denser (double nova, 8 hands, 20-bolt barrage, 10-circle rain) | 4 attacks |

**How you win:** after every chain he is **exhausted** ("SOULFIRE SPENT"). A golden ring pulses round him and he takes
**+50% damage** for 2 to 2.6 seconds. That is your window. Between windows you dodge: every wind-up is telegraphed,
the volley and barrage **freeze their aim for the last 0.3 s** (sidestep or dash!), every nova has a green gap,
every rain has holes between its circles, and a barrage is harmless outside its wedge. He calls his army the
moment each new phase begins.

* **Soul Rain:** small rune circles burst one after another, one under you, the rest scattered around. They never
  heal him and they are kept apart so there is always a gap to stand in.
* **Soul Barrage:** a stream of bolts sweeps across a red wedge aimed at you. Everything outside the wedge is safe.
* **Skeleton army:** his minions are the **"undying" tier**: 3x health, +30% damage, +15% speed (`tier="undying"`,
  see `src/monsters/README.md`). Brutes cost two army slots.

* **Bone Nova:** a ring of bone shards with one **safe gap**. Dotted rays show every shard's path and the gap is
  marked in green. Phase 3 fires a second ring, with its gap on the opposite side.
* **Grasping Hands:** cracks spread over the floor (one is always under you) and skeletal hands burst up one after
  another. A hit hurts and roots you for about a second. Hands do not heal him.
* **Last Stand:** he is white-hot with ghostly afterimages. The drain heals him less, and his wind-ups are never
  shorter than about half a second, so every attack can still be read and dodged.

Every attack has a visible wind-up. A test checks that none ever drops below 0.45 seconds.

**Tuning:** `BOSS_MAX_HP`, `PHASE_STATS` (chain length `combo`, window `exhaust`, army size `minion_cap`, and every
attack's numbers), `EXHAUST_BONUS`, `AIM_LOCK` and the `*_DAMAGE` constants are all at the top of `lich_king/boss.py`.
The health pool was sized for the test arena's 20-damage sword; if the real weapons hit for 7-18, lower `BOSS_MAX_HP`
until a full fight takes about 3 to 5 minutes.

### How to read his warnings

| Attack | What you see before it hits | What it looks like when it fires |
|--------|-----------------------------|----------------------------------|
| Shadow Volley | A glowing lane for EVERY bolt, with runes on the floor and soul-light racing down it | Ghost-skull bolts trailing soul-fire (violet, crimson, then white-hot) |
| Life Drain | A turning rune circle with a hexagram; it fills with glow and pulses just before it bursts | A shock ring and columns of soul-light. Stolen life flows back to him as a green soul stream |
| Bone Nova | The floor is faintly red, EXCEPT a glowing **green gap** with arrows flowing outward. Bone spikes ring him, one per shard | A rune-studded shockwave, the floor splits with glowing fissures, bone shards with dust trails |
| Grasping Hands | The floor cracks into a broken patch with glowing seams. Fingertips poke through, then it shudders | Bone hands burst out in a spray of soil and dust |
| Skeleton army | Necromantic sigils open where each skeleton will rise, with soul-light flowing to each from him | The skeletons climb out of the sigils |
| Soul Rain | Small turning rune circles, one under you; they pulse and burst one after another | Shock rings and soul-light columns (no green life stream: they do not heal him) |
| Soul Barrage | A red wedge from him to you with chevrons showing the sweep direction. It freezes 0.3 s before the first bolt | A stream of bolts sweeping across the wedge; a bright line marks the bolt being fired now |
| Exhausted | A golden pulsing ring with arrows pointing at him, a ring of dots that runs down, and "SOULFIRE SPENT" under his health bar | Nothing: this one is **your** attack window (+50% damage) |

Colour language: **red haze = danger, green = safe**, and everything flashes bright for the last quarter second
before it hits.

### The spell-effects toolkit (reusable)

`lich_king/effects.py` draws every effect on a low-resolution canvas (1 canvas pixel = 3 screen pixels, the same
size as the Lich King's sprite pixels) and scales it up, so effects line up with the art. Translucent shapes are
**dithered** (a checkerboard) the retro way instead of smoothly blended.

```python
from bosses.lich_king.effects import FxLayer, rune_ring, hexagram, theme

fx = FxLayer(left, top, width, height)                  # the screen area you will draw in
colors = theme(phase)                                   # spell colours for phase 1, 2 or 3
fx.circle((x, y), 80, colors["glow"] + (120,), soft=True)    # a dithered glowing disc
rune_ring(fx, x, y, 80, colors["main"], clock)          # a ring of turning runes
fx.draw(screen)                                         # scale up and draw
```

Also in there: `hexagram`, `jagged_points` (broken ground), `crack_points`, `soul_ribbon`, `chevron`, `spike`,
`shock_ring`, `soul_skull`, and the self-playing `ShockBurst` / `GroundCracks`. Use `clip_to(surface, bounds)` to
keep floor effects inside the arena.

## Tuning the fight

All Lich King numbers (speed, wind-up times, bolt count, damage, healing) are at the top of
`lich_king/boss.py` in `PHASE_STATS` and the constants below it.

## Adding another boss

See [HOW_TO_ADD_A_BOSS.md](HOW_TO_ADD_A_BOSS.md).
