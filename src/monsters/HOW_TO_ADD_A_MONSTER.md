# How to add a monster (about 30 minutes)

Example: a **Wolf**. Replace `wolf` with your monster's name everywhere.

## 1. Art  ->  `assets/monsters/wolf/`

Two files:

* `frames.png`: one horizontal strip, every frame the same size, side by side. Draw these animations
  (the numbers are what the skeletons have; more frames = smoother):

  | animation | frames | when it plays |
  |---|---|---|
  | `idle`    | 4 | standing still (breathing, weapon sway) |
  | `walk`    | 8 | moving: one frame per few pixels walked, so legs match the speed |
  | `windup`  | 3 | the warning before an attack, spread over the whole wind-up time |
  | `strike`  | 3 | the attack itself, spread over `STRIKE_TIME` |
  | `recover` | 2 | after the attack, spread over `RECOVER_TIME` |
  | `hurt`    | 1 | when staggered by a hit. **The death shatter uses this pose too.** |

  **Required minimum: `walk`, `windup`, `strike`.** `idle`, `recover` and `hurt` are optional: if missing, the game
  reuses a walk/strike frame, so a quick first version still works.
  Only fully opaque or fully transparent pixels (no half-transparent edges). Leave empty rows above the head
  for raised weapons so they are not cut off.
* `sprite.json`: which frames belong to which animation:
  ```json
  {"scale": 2, "frame_size": [44, 56], "anchor": [22, 53],
   "animations": {"idle": [0,1,2,3], "walk": [4,5,6,7,8,9,10,11], "windup": [12,13,14],
                  "strike": [15,16,17], "recover": [18,19], "hurt": [20]}}
  ```
  `anchor` = the pixel where its feet touch the floor (the shadow goes there). `scale` = how many screen pixels
  one art pixel becomes (the skeletons use 2; the Lich King uses 4).

**Glowing parts:** paint eyes `(255,0,255)`, runes `(0,255,255)`, orbs `(255,255,0)`. The game turns them into
glowing, pulsing, per-variant colours. Paint bone with the skeleton bone colours if you want variants to recolour it
(see `BONE_PAINTED` in `sprites.py`).

**Two ways to make the art:** draw it in any pixel editor, or copy `dev/make_sprites.py`. The skeletons are built from a
tiny rig (hips/knees/shoulders/elbows); a pose is a handful of numbers, so changing an animation means editing numbers,
not redrawing pixels. `python src/monsters/dev/make_sprites.py --sheets some_folder` shows every frame as a picture.

## 2. Code  ->  `src/monsters/wolf.py`

```python
import math
from .attacks import player_pos
from .base_monster import Monster

class Wolf(Monster):
    NAME = "wolf"                 # = the asset folder name
    DISPLAY_NAME = "Wolf"
    MAX_HP, RADIUS, SPEED, DAMAGE, FOOT = 18, 14, 150.0, 6, 30   # FOOT = pixels from (x, y) down to its feet
    STEP_LENGTH = 5.0             # pixels per walk frame: smaller = legs move faster
    STRIKE_TIME, RECOVER_TIME = 0.2, 0.5   # the strike/recover animations are spread over these
    LOOT = (("Wolf Pelt", 0.5),)
    GOLD = (0, 3)

    def think(self, dt, player, bounds):          # called every frame while it is "alive and active"
        px, py = player_pos(player)
        dx, dy, dist = self.vector_to(px, py)
        self.face(px)
        if self.state == "chase":
            self.move(dx, dy, self.speed, dt)
            if self.cooldown <= 0 and dist < 70:
                self.begin_windup(0.4)            # ALWAYS give a warning before a hit
        elif self.state == "windup":
            if self.state_time >= self.windup_time:
                self.set_state("strike")
        # ...strike, recover: see skeleton/warrior.py
```

States you use: `chase` (default), `windup`, `strike`, `recover`. The base class handles spawning, being hit,
knockback, stagger, death, shatter animation, loot, drawing.

**Rule of the game: every attack needs a visible warning** (`draw_floor` for floor shapes, `draw_effects` for beams).
Helpers: `ground_circle`, `ground_lane`, `dotted_line`, `pixel_ring` in `fx.py`.

## 3. Register it  ->  `src/monsters/__init__.py`

Two lines marked `ADD HERE`: the import, and `"wolf": Wolf,` in `MONSTERS`.

## 4. Check it

```
python src/monsters/dev/arena.py                  # add a key for it, or: group.spawn("wolf", ...)
python -m unittest discover -s src/monsters/tests # every registered monster is tested automatically
```

The tests check: art loads in every variant, it can be killed, it draws, it stays in bounds, it
can't be hurt while spawning, it drops loot.


## Sounds

Spawning, getting hit and falling apart already make sound. To give your monster its own, set `SFX_SPAWN`,
`SFX_HURT`, `SFX_DIE`, `SFX_WINDUP` and `SFX_STRIKE` on the class to file names in `assets/audio/sfx/`
(`None` = silent). For anything else call `audio.play("name", x=self.x)`. See `src/audio/README.md`.
