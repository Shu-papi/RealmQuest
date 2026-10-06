# Minotaur sprites

> **STATUS: PLACEHOLDER ART.** The PNGs in this folder are simple stand-ins so the boss is
> playable and testable while the final sprite is still being drawn. They are meant to be
> **overwritten** by the final art. No Python changes are needed to swap them.

```
python src/bosses/dev/check_sprites.py minotaur    # checks the PNGs and explains any mistakes
python src/bosses/minotaur/preview.py              # saves a sheet of poses (minotaur_preview.png)
python src/bosses/minotaur/preview.py --live       # animated preview in a window (ESC quits)
python src/bosses/dev/arena.py minotaur            # the real fight
```

## Files

| File | Required | What it is |
|------|----------|------------|
| `body_phase1_a.png` | yes | Phase 1 body, frame A |
| `body_phase1_b.png` | no | Phase 1 body, frame B (swapped with A about 2.5 times a second: breathing / stomping) |
| `body_phase2_a.png` | no | Phase 2 (enraged, below 50% HP) body, frame A. Uses phase 1 art if missing |
| `body_phase2_b.png` | no | Phase 2 body, frame B |
| `sprite.json` | no | Placement numbers (below) |

**Every PNG must be the same size.** The placeholders are **48 x 56** pixels with a
**transparent** background, and the game draws each pixel as a 4 x 4 block (192 x 224 on
screen). Only fully solid or fully transparent pixels: turn anti-aliasing off in your editor.

Tip: open `body_phase1_a.png` in your pixel editor and paint over it, so the canvas size and
position are already right. Frame B can be a copy of frame A with a small change (for example
the body shifted up by 1 pixel).

## How the game uses the art

The game **does not** recolour or animate the sprite itself except for these effects, so you
do not need to draw them:

- **Hit flash:** the whole sprite turns white for a moment.
- **Attack warning:** the sprite blinks red during the wind-up of a charge or slam.
- **Slam wind-up:** the sprite lifts up 3 pixels.
- **Death:** the sprite fades out.
- **Idle bob:** the sprite moves up and down by 1 pixel.

Phase 2 looks different only if you provide the `body_phase2_*` files. The placeholders use a
darker red fur and brighter red eyes for phase 2.

## `sprite.json`

Every key is optional. Numbers are in sprite pixels unless noted.

| Key | Meaning |
|-----|---------|
| `scale` | Screen pixels per sprite pixel (4 = each pixel is a 4x4 block) |
| `anchor` | `[x, y]` pixel that sits exactly on the boss's position. Hits and attacks are measured from here. Roughly the middle of the body |
| `shadow` | `{"y": rows below the anchor, "widths": [row widths]}`, the pixel shadow on the floor |
| `bob` | How far he bobs up and down |

**If your final sprite is a different size**, update `anchor` (and `shadow.y`, so the shadow sits
under the hooves). The hitbox is a circle set in `src/bosses/minotaur/boss.py` (`radius=46`);
change it there if the new sprite is much bigger or smaller.

If the sprites are missing or broken the game does not crash: it draws simple shapes and prints
what is wrong. Run `python src/bosses/dev/check_sprites.py minotaur` for details.
