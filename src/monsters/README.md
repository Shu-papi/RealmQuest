# Monsters

Small enemies that **any part of the game can reuse**: a crypt guard, an ambush event, a boss's
minions. Bosses live in `src/bosses/`; monsters live here. Art lives in `assets/monsters/<name>/`.

## The skeleton family

Each one has a full animation set (21 frames): **idle, walk (8-frame cycle), wind-up, strike, recover, hurt**, and
shatters into bone pieces when killed.

| Name (`spawn_monster("...")`) | HP | Role | What to do |
|---|---|---|---|
| `skeleton_warrior` | 20 | Melee. Red lane on the floor, then a lunge | Sidestep or dash, then punish |
| `skeleton_archer` | 14 | Keeps its distance, dotted aim line, glowing arrows | Sidestep after the line locks; rush it |
| `skeleton_brute` | 90 | Slow, can't be interrupted. Overhead maul slam (red circle) | Leave the circle; hit it while the hammer is stuck |
| `skeleton_acolyte` | 16 | Heals wounded friends, raises new warriors, fires slow bolts | **Kill it first** |

Every attack has a warning (the Lich King rule: *no hit without a telegraph*).

### Difficulty tiers (same monsters, tougher: reuse them across areas)

One word makes any monster tougher, so a late area can reuse the same skeletons:

`spawn_monster("skeleton_warrior", x, y, tier="veteran")`

| Tier | HP | Damage | Speed | Good for |
|---|---|---|---|---|
| `normal` (default) | x1 | x1 | x1 | the first areas |
| `veteran` | x1.6 | x1.15 | x1.05 | mid-game crypts and ambushes |
| `elite` | x2.5 | x1.25 | x1.1 | mini-boss guards, hard events |
| `undying` | x3 | x1.3 | x1.15 | the Lich King's army |

Raised dead and acolyte heals scale with the acolyte's tier. Explicit numbers (`hp_scale=`, `damage_scale=`,
`speed_scale=`) always beat the tier. Edit `TIERS` in `monsters/__init__.py` to retune them all at once.

### Variants (same monsters, new look: reuse them across areas)

`spawn_monster("skeleton_archer", x, y, variant="frost")`

`bone` (default) · `cursed` (hellfire, used by the Lich King) · `frost` · `ember` · `plague`

See them all: `assets/monsters/preview_all_variants.png` or run `python src/monsters/dev/preview.py`.
Add your own look by adding an entry to `VARIANTS` in `sprites.py`.

## Using monsters in your map or event

```python
from monsters import MonsterGroup, deal_damage        # or: from src.monsters import ...

group = MonsterGroup()
group.spawn("skeleton_warrior", 300, 400)                                  # one
group.spawn_wave(["skeleton_warrior"] * 3 + ["skeleton_acolyte"], bounds, player)   # an ambush
group.spawn("skeleton_brute", 500, 300, variant="ember", hp_scale=1.5)     # tougher, themed

# every frame
group.update(dt, player, bounds)        # bounds = (left, top, right, bottom)
group.draw(screen)                      # draws shadows, warnings, monsters, bone shatter, arrows

# when the player attacks something
for target in group.hittables():
    if in_range(target):
        deal_damage(target, 20, source=(player_x, player_y))   # source = knockback direction

for drop in group.take_drops():         # {"x", "y", "items": [...], "xp", "monster"}
    spawn_loot(drop["x"], drop["y"], drop["items"])

if group.is_clear():                    # "defeat all enemies" events
    open_the_door()
screen_shake = group.shake              # 0..1, the brute's slam sets it
```

`spawn_monster(name, x, y, **options)` options: `variant`, `seed`, `spawn=False` (appear instantly),
`hp_scale`, `damage_scale`, `loot` (replace the loot table).

**What a monster needs from your Player:** `player.rect` (a `pygame.Rect`) and `player.take_damage(n)`. That's all.

**Bosses:** put monsters in `boss.minions` (see `bosses/lich_king/minions.py`). Monsters use the same
shape as bosses (`x, y, radius, take_damage, is_alive, update, draw`).

## Files

```
monsters/
  __init__.py       the registry (MONSTERS) + spawn_monster() + deal_damage()
  base_monster.py   Monster: spawn animation, hit flash, knockback, stagger, shatter death, loot
  group.py          MonsterGroup: updates/draws many, spacing, drops, waves, raised dead
  sprites.py        loads the PNG strips, VARIANTS, animates the glowing eyes/runes
  fx.py             particles, pixel rings, floor warnings (reusable for spells and hazards)
  attacks.py        Arrow, SoulBolt
  skeleton/         warrior.py archer.py brute.py acolyte.py  (read warrior.py first)
  dev/              arena.py (fight them), preview.py (see art), make_sprites.py (rig + poses that paint the art)
  tests/            test_monsters.py
```

## Try it

```
python src/monsters/dev/arena.py                         # 1-4 spawn monsters, 5 = wave, V = variant
python src/monsters/dev/preview.py                       # every frame + live animation (UP/DOWN monster, LEFT/RIGHT variant)
python -m unittest discover -s src/monsters/tests        # tests
```

Adding a new monster: **HOW_TO_ADD_A_MONSTER.md**
