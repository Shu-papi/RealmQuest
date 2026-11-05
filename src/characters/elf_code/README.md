# Elf Archer – Sprite Animation System

Idle · Walk · Run · Quick Attack · Charge Attack, built for **pygame** (Python 3.9+).

Frame timing, state switching, facing, pixel-exact scaling and per-frame alignment are
all handled for you. Drop `sprite_animation/` and `assets/` into any pygame project.

---

## 1. Quick start

```bash
pip install -r requirements.txt     # just pygame
python main.py                      # original size
python main.py --scale 2            # crisp 2x pixel-perfect zoom
```

| Key | Action |
|---|---|
| `A` / `D` or `←` / `→` | Walk |
| hold `Shift` | Run |
| `J` or `Z` | Quick attack |
| hold `K` or `X`, then release | Charge attack (draw → glow → fire on release) |
| `F1` | Debug overlay (anchor cross, frame box, state, frame number, events) |
| `Esc` | Quit |

---

## 2. Project layout

```
main.py                    Interactive demo
requirements.txt           pygame
sprite_animation/
    config.py              ★ Animation speeds, looping, events  (edit this to tune)
    player.py              Frame sequencing + timing (pure Python)
    controller.py          Input -> which animation plays (pure Python)
    assets.py              PNG loading, anchors, scaling, mirroring (pygame)
    character.py           AnimatedCharacter: movement + animation + draw (pygame)
assets/
    idle/  walk/  run/  quick_attack/  charge_attack/     the extracted PNG frames
    anchors.json           per-frame alignment points (see §5)
tools/build_anchors.py     regenerates anchors.json (+ optional preview sheets)
tests/test_animation.py    22 headless tests
```

### Required assets

The five ZIPs were extracted into `assets/` like this:

| ZIP | Folder | Frames |
|---|---|---|
| `elf_archer_idle_sprites.zip` | `assets/idle/` | 16 |
| `elf_archer_walk_sprites.zip` | `assets/walk/` | 16 |
| `elf_archer_run_sprites.zip` | `assets/run/` | 12 |
| `elf_yelena_quickshot_sprites.zip` | `assets/quick_attack/` | 22 |
| `elf_yelena_chargedshot_sprites.zip` | `assets/charge_attack/` | 25 |

Frames must end in a number (`..._01.png`). They are sorted **numerically**, so the
random order inside a ZIP doesn't matter. To use different art, replace the PNGs, keep
the folder names (or edit `config.py`), then run `python tools/build_anchors.py`.

---

## 3. Using it in your own game

```python
import pygame
from sprite_animation import AnimationLibrary, AnimatedCharacter

pygame.init()
screen = pygame.display.set_mode((1000, 600))      # must exist BEFORE loading images

library = AnimationLibrary(scale=1)                # load once, share between characters
hero = AnimatedCharacter(library, x=500, y=490)    # (x, y) = where her FEET touch the ground

# game loop
dt = clock.tick(120) / 1000                        # seconds
events = hero.update(dt, move_x=+1, running=False) # move_x: -1 / 0 / +1 (or analog -1..1)
hero.draw(screen)

# actions
hero.quick_attack()                                # e.g. on key/button press
hero.start_charge()                                # on charge-button DOWN
hero.release_charge()                              # on charge-button UP

for e in events:                                   # react to animation events
    if e == "fire":    spawn_arrow(hero.x, hero.y, hero.controller.facing)
    if e == "charged": play_sound("bow_glow")
```

`controller.facing` is `+1` (right) or `-1` (left) – use it as the arrow direction.

### Event reference

| Event | When | Default frame |
|---|---|---|
| `fire` | Quick attack: arrow leaves the bow | frame 7 (`index 6`) |
| `charged` | Charge attack: bow reaches full glow, once | first glow frame |
| `fire` | Charge attack: released shot | frame 13 (`index 12`) |

Need more? Add `{frame_index: "name"}` to an `events` dict in `config.py`.

### Using only the logic, without pygame

`AnimationPlayer` and `AnimationController` don't import pygame. Use them with any
renderer (arcade, raylib, Godot-via-Python…): read `controller.animation_name`,
`controller.frame_index` and `controller.facing` each frame and draw your own image.

---

## 4. How the animation behaves

* **Idle** when stationary; **Walk** when moving; **Run** when moving with Shift held.
* **Quick attack** plays once, plants her feet, and locks facing. Pressing it again
  during an attack is remembered for 180 ms and fires the moment the current one ends.
* **Charge attack** = draw the bow → glowing frames loop *while you hold the button* →
  **release** to fire the piercing shot. Releasing before the glow starts cancels the
  shot (bow lowered, no arrow). Holding forever is fine.
* After any attack she goes straight back to whatever input asks for (still holding
  Shift + direction → back to Run with no idle flash).
* **Walk ↔ Run** keep the same cycle position so the legs don't snap back to frame 1.
* A very short pause in movement (60 ms) doesn't flicker to Idle.
* Timing uses elapsed time, not frame counts, so speed is identical at any FPS, and a
  lag spike skips frames instead of slowing the animation.

No cross-fading is used between animations: with pixel art, blending two poses just
produces blurry ghosting. Clean cuts with matched alignment and phase look better.

### Tuning (all in `sprite_animation/config.py`)

| Want to change | Edit |
|---|---|
| Animation speed | `fps=` of that `AnimationSpec` |
| Hold an impact frame | `frame_ms={12: 120}` (milliseconds) |
| Which frames repeat while charging | `hold_loop=(7, 11)` |
| Where `fire` happens | `events={6: "fire"}` |
| Walk/run movement speed | `AnimatedCharacter(walk_speed=…, run_speed=…)` |
| Idle flicker delay / attack buffer / phase sync | `ControllerSettings(idle_grace_ms, attack_buffer_ms, keep_phase)` |

If her feet seem to slide, raise or lower `walk_speed` / `run_speed` until the ground
speed matches the stride.

---

## 5. Image quality & alignment

* PNGs are loaded with `convert_alpha()` – full per-pixel transparency, no colorkeys.
* **No smoothing, ever.** Zoom is integer-only (`scale=2, 3…`) using nearest-neighbour,
  so every pixel stays sharp and all five animations keep identical proportions.
  A non-integer scale is rejected on purpose.
* Left-facing frames are exact mirrors, generated once at load time.
* Draw positions are rounded to whole pixels to avoid shimmering.
* **Alignment:** the PNGs are tightly cropped, so each frame has a different size
  (the attack frames are bigger still because of the arrow and shard effects). Drawing
  them at a shared top-left corner would make her jitter. `anchors.json` stores, for
  every frame, the point (body centre, soles of the boots) that is pinned to
  `(hero.x, hero.y)`. Regenerate it any time with:

  ```bash
  pip install numpy scipy pillow
  python tools/build_anchors.py --preview     # writes assets/_preview/*_aligned.png
  ```
  Open the previews to check: red line = ground, blue line = body centre. You can also
  hand-edit `anchors.json` (`"file.png": [anchor_x, lowest_body_pixel_row]`).

Known trade-off: because feet are pinned to the ground, the small airborne bob in the
run cycle is flattened (she always looks planted). To restore a bob, hand-edit the
second number of the run entries in `anchors.json` (a smaller row = a higher body).

---

## 6. Tests

```bash
python -m unittest discover -s tests -v
```

Covers timing, frame skipping, looping, events, charge hold/release/cancel, state
switching, facing, phase sync, attack buffering and asset integrity. No window needed.

---

## 7. Troubleshooting

| Problem | Fix |
|---|---|
| `RuntimeError: Call pygame.display.set_mode…` | Create the window *before* `AnimationLibrary(...)` |
| `FileNotFoundError: No PNG frames for 'walk'…` | Extract the ZIP into `assets/walk/` |
| `ValueError: scale must be a whole number` | Use `scale=1, 2, 3…` |
| Warning: `anchors.json not found` | `python tools/build_anchors.py` |
| Character floats/sinks | `y` is the ground line where the feet touch |
