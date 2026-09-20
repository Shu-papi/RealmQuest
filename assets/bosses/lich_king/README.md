# Lich King sprites

These PNG files ARE the Lich King. Change a PNG, run the game, and he looks different.
No Python needed.

```
python src/bosses/dev/check_sprites.py lich_king               # checks your files, explains any mistakes
python src/bosses/lich_king/preview.py --live    # animated preview of every pose (ESC quits)
python src/bosses/dev/arena.py                             # the real fight
```

---

## Part 1: Making sprites yourself (beginner guide)

### 1. Pick a tool

You need a **pixel art editor** (not Photoshop-style painting tools: they blur things).

| Tool | Cost | Notes |
|------|------|-------|
| **Piskel** | Free | Runs in your browser, nothing to install. Easiest start |
| **Pixelorama** | Free, open source | Full desktop editor with layers and animation |
| **LibreSprite** | Free, open source | Looks and feels like Aseprite |
| **PixiEditor** | Free, open source | Modern interface |
| **Aseprite** | Paid (about $20 one-time) | The industry favourite. Buy it from the official site. Avoid sites offering "free full version" downloads |

Any of them works. Everything below is the same in all of them.

### 2. Set up

1. **Open a starter file instead of a blank one.** Open `body_phase1_a.png` and paint over
   it. It is already the right size, has the right colours, and shows you how a finished
   sprite is built.
2. **New sprite from scratch?** Make the canvas **54 x 61 pixels** with a **transparent**
   background. It is tiny on purpose: the game shows each pixel as a 4x4 block.
3. **Load the palette** `lich_king_palette.gpl` (in this folder). It contains our colours
   and the special marker colours (Part 2). Palette menu -> Load / Import.
4. **Turn OFF anti-aliasing / soft brushes.** Use the plain 1-pixel pencil. Use "pixel
   perfect" mode if your editor has it (it removes doubled-up corners).
5. Zoom in a lot (800%+). Never use blur, smudge, gradient or resize tools.

### 3. Drawing order that works

1. **Silhouette first.** Fill the whole shape with one flat colour. Squint: can you tell
   it is a king with a crown, spiked shoulders and a staff? A boss must read as a strong
   shape before any detail exists.
2. **Flat colours.** Bone, gold, cloak, steel, each in its main colour.
3. **Shading.** Use 3 tones per material (light / main / dark). Pick ONE light direction
   (from the top) and keep it. Light on top edges, shadow underneath.
4. **Outline.** A 1-pixel dark outline around the whole figure (`outline` colour in the
   palette) makes him pop off the floor.
5. **Details last:** cracks, rivets, teeth, trim.

Tips that make sprites look professional:
- **Fewer colours is better.** 16 to 32 total. Reuse palette colours instead of inventing new ones.
- **Draw HALF and mirror it.** Use your editor's symmetry / mirror mode for the body, then
  add the asymmetric bits (staff hand, flame hand) by hand.
- **Chunky beats detailed.** At 4x size, a single pixel is a big square. Simple, bold
  shapes look stronger than lots of tiny detail.
- **Big shapes, sharp points.** Spikes, horns, a tall collar and a wide, ragged cloak all
  make a boss feel dangerous.
- **Avoid "jaggies"**: lines should step evenly (2-2-2 or 3-3-3), not randomly.

### 4. The two-frame cloak flutter

The cloak animates by swapping two images. Make `body_phase1_b.png` by copying
`body_phase1_a.png` and changing **only the bottom hem** (shift the ragged points).
Same for phase 2. Keep everything else identical or he will "jump".

### 5. Save, check, look

1. Export as **PNG at 100% size** (never scaled), with a transparent background.
2. `python src/bosses/dev/check_sprites.py lich_king` fixes 90% of problems before you even open the game.
3. `python src/bosses/lich_king/preview.py --live` shows every pose animated.
4. Keep your editor's own file (`.aseprite`, `.pixil`, ...) in a `source/` folder here
   so layers are not lost. Commit it to GitHub too.

### 6. Where to learn more

Search for: **Lospec pixel art tutorials**, **Slynyrd Pixelblog**, **Pedro Medeiros
(saint11) pixel art tutorials**, and the book **Pixel Logic** by Michafrar. Lospec also has
thousands of ready-made palettes to try.

---

## Part 2: Technical spec

### Files

| File | Required | What it is |
|------|----------|------------|
| `body_phase1_a.png` | yes | Phase 1 body, cloak frame A |
| `staff.png` | yes | The staff (drawn behind the body; lifts when summoning) |
| `body_phase1_b.png` | no | Phase 1, cloak frame B |
| `body_phase2_a.png` | no | Phase 2 body (uses phase 1 art if missing) |
| `body_phase2_b.png` | no | Phase 2, cloak frame B |
| `sprite.json` | no | Placement numbers (below) |
| `lich_king_palette.gpl` | no | Palette to load into your editor |

**Every PNG must be the same size** (the starter files are 54 x 61) and be drawn on the same
canvas: the staff sits in its correct place *within* its own image, so you can stack all
files on top of each other in your editor. Only fully solid or fully transparent pixels.

### Marker colours (glowing parts)

Paint the glowing parts in these EXACT colours. The game replaces them with live, animated
glow. Move or reshape the eyes by repainting the markers; no code changes.

| Marker | RGB | Hex | Use in |
|--------|-----|-----|--------|
| `eye` | 255, 0, 255 | `#FF00FF` | body: eyes, always glowing |
| `eye_flare` | 255, 102, 255 | `#FF66FF` | body: extra eye glow while winding up |
| `eye_burst` | 255, 176, 255 | `#FFB0FF` | body: peak eye glow just before firing |
| `core` | 0, 255, 255 | `#00FFFF` | body: chest gem glow (heartbeat pulse) |
| `core_rim` | 0, 136, 136 | `#008888` | body: chest gem dark edge |
| `core_hi` | 170, 255, 255 | `#AAFFFF` | body: chest gem bright centre |
| `orb` | 255, 255, 0 | `#FFFF00` | staff: the orb |
| `orb_shine` | 255, 255, 170 | `#FFFFAA` | staff: orb highlight |

Colours are set by the game: phase 1 is cold teal, phase 2 is red, and each attack tints
them (amber = volley, green = drain, pink = summon). Use the palette swatches rather than
eyedropping by eye. The checker warns you if a marker is even slightly off.

### `sprite.json`

Every key is optional. Numbers are in sprite pixels unless noted.

| Key | Meaning |
|-----|---------|
| `scale` | Screen pixels per sprite pixel (4 = each pixel is a 4x4 block) |
| `anchor` | `[x, y]` pixel that sits exactly on the boss's position. Hits and attack spawns are measured from here |
| `shadow` | `{"y": rows below the anchor, "widths": [row widths]}`, the pixel shadow on the floor |
| `flame` | `[x, y]` bottom-centre of the soul flame held in the left hand |
| `crown_fire` | Phase 2 fire on the crown: a list of `[x, y, extra_height]` |
| `staff_lift` | How many pixels the staff rises when summoning |
| `bob` | How far he floats up and down |
| `aura_radius` | Size of the dithered glow behind him |

If the sprites are missing or broken, the game does not crash. It draws a magenta box with
an X and prints what is wrong. Run `python src/bosses/dev/check_sprites.py lich_king` for details.
