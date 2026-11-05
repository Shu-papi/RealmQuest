# Lich King sprites

These PNG files ARE the Lich King. Change a PNG, run the game, and he looks different.
No Python needed.

```
python src/bosses/dev/check_sprites.py lich_king     # checks your files, explains any mistakes
python src/bosses/lich_king/preview.py               # saves a picture of every pose (lich_king_preview.png)
python src/bosses/lich_king/preview.py --live        # animated window (ESC quits)
python src/bosses/dev/arena.py                       # the real fight (press P to jump to phase 2)
```

## What he looks like

* **Phase 1, the Frozen Sovereign:** royal violet cloak, spiked gold crown, a tall dark collar, round steel
  pauldrons with curved bone horns, a ribcage cage holding his glowing soul-core, gold chains, a skull belt buckle,
  chained cuffs, a soul-flame floating over his left hand and a skull-and-orb staff in his right.
* **Phase 2, the Hellfire Tyrant:** crimson cloak, blackened steel, taller horns, a burning crown, glowing magma
  cracks and huge torn bat-wings.
* **Phase 3, the Last Stand (below 25% HP):** no new art needed. The phase 2 art turns white-hot (the colours blend
  towards a hot palette), everything animates faster, more souls and embers appear, and ghostly afterimages trail
  behind him. Phase 3 is the same two PNG files as phase 2.
* **Live effects (code, no art needed):** aura, rising embers, three (five in phase 2) soul-skulls orbiting him,
  a turning rune circle on the floor, soul-wisps drifting from his hem, energy motes streaming into his
  core while he winds up an attack, shockwaves when he transforms and a soul-burst when he dies.

## The poses (22 frames per phase)

| Pose | Frames | When it plays |
|------|--------|---------------|
| `idle`    | 4 | floating about (the loop speeds with the frame count) |
| `volley`  | 3 | shadow volley wind-up: hands gather energy, then fling wide |
| `drain`   | 2 | life drain wind-up: arms press down at the ground |
| `summon`  | 3 | calling the army: staff and arm thrust to the sky |
| `recover` | 2 | catching his breath after an attack |
| `hurt`    | 1 | flinch when hit (also used while he dies) |
| `roar`    | 2 | the phase transitions |
| `nova`    | 3 | Bone Nova wind-up: he coils in on himself, clenches, then explodes outward |
| `grasp`   | 2 | Grasping Hands: arms out and down, claws spread |

A wind-up pose is spread over the whole wind-up, so the frames match the warning the player sees.
**Only `idle` is required.** A pose that is missing from the art simply falls back to `idle`.

## The files

| File | Required | What it is |
|------|----------|------------|
| `frames_phase1.png` | yes | Every phase 1 frame in one horizontal strip |
| `frames_phase2.png` | no | Every phase 2 frame (phase 1 art is used if missing) |
| `sprite.json` | yes | How big one frame is, which frames are which pose, placement numbers |
| `lich_king_palette.gpl` | no | Palette to load into your editor |

Each frame is **96 x 128 pixels** and shown at 3x. All frames sit side by side on the same canvas, in the order
listed under `animations` in `sprite.json`. Leave empty rows above him: raised crowns, staffs and wings must not
touch the top edge. Use only fully solid or fully transparent pixels.

`sprite.json` (the important parts):

```json
{
  "scale": 3,
  "frame_size": [96, 128],
  "anchor": [48, 78],
  "shadow": {"y": 49, "widths": [30, 42, 30]},
  "animations": {"idle": [0, 1, 2, 3], "volley": [4, 5, 6], "drain": [7, 8], "summon": [9, 10, 11],
                 "recover": [12, 13], "hurt": [14], "roar": [15, 16], "nova": [17, 18, 19], "grasp": [20, 21]},
  "orbit": {"center": [48, 82], "radius": [30, 9], "count": {"1": 3, "2": 5}},
  "wisps": {"y": 118, "x": [31, 65]}
}
```

* `anchor`: the pixel that sits on the boss's position (his chest). `shadow`: where the floor shadow and rune
  circle go. `orbit`: the soul-skulls (set a count to 0 to remove them). `wisps`: where the hem dissolves.

## Marker colours (glowing parts)

Paint the glowing parts in these EXACT colours. The game replaces them with live, animated glow, and a different
colour per phase and per attack. Move or reshape them by repainting; no code changes.

| Marker | RGB | Hex | What it does |
|--------|-----|-----|--------------|
| `eye` | 255, 0, 255 | `#FF00FF` | eyes, always glowing |
| `eye_flare` | 255, 102, 255 | `#FF66FF` | extra eye glow during a wind-up |
| `eye_burst` | 255, 176, 255 | `#FFB0FF` | peak eye glow just before he fires |
| `core` | 0, 255, 255 | `#00FFFF` | soul-core (heartbeat pulse) |
| `core_rim` | 0, 136, 136 | `#008888` | soul-core dark edge |
| `core_hi` | 170, 255, 255 | `#AAFFFF` | soul-core bright centre |
| `orb` | 255, 255, 0 | `#FFFF00` | staff orb |
| `orb_shine` | 255, 255, 170 | `#FFFFAA` | staff orb highlight |
| `flame` | 255, 136, 0 | `#FF8800` | **one pixel**: where the big soul-flame burns (its base) |
| `fire` | 255, 85, 0 | `#FF5500` | **one pixel**: base of a small flame (crown tip, horn tip) |
| `vein` | 255, 51, 153 | `#FF3399` | runes, cracks, gems: a glow ripples down them |

`flame` and `fire` are position-only: the pixel itself disappears and a flame burns upward from it.
Put each marker in every frame, because the flame follows his hand as the pose changes.

## Two ways to make the art

**1. Let the generator draw it (what the shipped art does).** `src/bosses/dev/make_lich_sprites.py` is a small
bone rig (shoulders, elbows, hands, a floating body, cape and wings). A pose is a handful of numbers, so to change
an animation you edit numbers (see `poses()`), not pixels. To change how he looks, edit the drawing functions.

```
python src/bosses/dev/make_lich_sprites.py                    # rebuilds the PNGs and sprite.json
python src/bosses/dev/make_lich_sprites.py --sheets folder    # also saves contact sheets to check every pose
```

**2. Paint it yourself.** Open `frames_phase1.png` in a pixel editor and paint over it (or add frames).
Keep your editor's own file (`.aseprite` etc.) in a `source/` folder here so layers are not lost.

### Pixel-art editor tips

You need a **pixel art editor** (not Photoshop-style tools: they blur things). Free options: **Piskel** (runs in
the browser), **Pixelorama**, **LibreSprite**, **PixiEditor**. Aseprite is paid and the industry favourite.

* Load `lich_king_palette.gpl` (Palette menu -> Load). Use the plain 1-pixel pencil and turn anti-aliasing OFF.
* Silhouette first, then flat colours, then 3-tone shading from the top-left, then a 1-pixel dark outline.
* Fewer colours looks better (the checker warns above 40). Big shapes and sharp points make a boss feel dangerous.
* Never use blur, smudge, gradient or resize tools.
* Learn more: search **Lospec pixel art tutorials**, **Slynyrd Pixelblog**, **saint11 pixel art tutorials**.

## Old format (still works)

The earlier format with `body_phase1_a.png` / `_b.png` (a 2-frame cloak flutter), `body_phase2_*.png` and a
separate `staff.png` still loads, so older art keeps working. If `frames_phase1.png` is present it is used instead.
In that format the flame and crown fire are positioned with `"flame"` and `"crown_fire"` in `sprite.json`.

## Sounds

The Lich King's sounds and his three music loops are in `assets/audio/` (see `src/audio/README.md`). Every attack
has a wind-up sound, a release sound and a bright ring on hits while he is open. Call `audio.init()` once in the
game and they play; `python src/bosses/dev/arena.py` already does (M mutes).
