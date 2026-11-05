# Minotaur sprites

> **STATUS: ISOMETRIC BOSS + WALK CYCLE (v5).** The sprites follow the hunched Minotaur template painting
> (curled horns, red eyes, skull belt, steel bracers) with the axe removed. They are plain PNGs, so
> you can paint over them in any pixel editor at any time. No Python changes are needed to swap them.
>
> They were built from `tools/reference/minotaur_template.png` by
> `python tools/build_minotaur_sprites.py`. Re-running that script **overwrites hand edits** to the
> every sprite PNG and `sprite.json`, so only use it to start over.

## Walking

He has a real 8-frame leg cycle (the legs of the painting swing from the hips and lift, one
after the other), and the frame is chosen by **how far he has actually moved on screen**
(`WALK_CYCLE_PX` = 76 screen pixels per full cycle, in `boss.py`), so a planted foot stays
planted instead of skating. When he stands still the legs stop; in the air they do not walk;
during a full charge the cycle is capped so the legs never flicker. Body bob, sway and the
squash on each footstep are in sync with the frames.

## The isometric boss

The arena is the normal flat room. **Only the boss is isometric-style**: he faces one of four
diagonal directions, turning to look at you or to run where he is going.

| You are... | He shows... |
| --- | --- |
| below him, to the right | front view, looking right |
| below him, to the left | front view, looking left |
| above him, to the right | back view, looking right |
| above him, to the left | back view, looking left |

Front/back changes fade over a moment and left/right is a quick turn, so nothing pops. He also
stands on an oval floor shadow and has the 8-frame walk cycle for each direction. (The back views
are an approximation made from the front art; see the file table.) This all lives in `boss.py`
and `art.py`, and works with any floor.

To get the old plain left/right flip instead, use `boss.view = TopDownView(four_way=False)`.

**Effects are top-down.** Only the boss is isometric. Every skill, damage and other effect is drawn
as seen from ABOVE, like the floor:

- Slam, leap landing, charge crash and footstep dust spread in a true circle, with no gravity.
- Boulders drop straight towards the floor: big and close to the camera when they start, shrinking to their real size where they land, and flying chips make a flat circle.
- Fireballs, rings, the charge lane and the hit circles are flat circles on the floor.
- Hit sparks fly out evenly in every direction and just slow down (no upward kick, no falling).
- The stun stars circle his head in a true circle.

(The optional isometric room below deliberately keeps its own side-on effects, because there the
floor itself is tilted.)

**Optional isometric room.** If you also want the floor itself isometric, run
`python src/bosses/minotaur/arena.py --iso-room`: the floor is turned 45 degrees and squashed 2:1,
circles become ellipses, and upright things stand on their spot (`view.py`, `iso_art.py`). It is the
same fight, only drawn differently, and is off by default. To use it in your own game set
`boss.view = IsoView()`, draw `boss.draw_ground(layer)` and hazards' `draw_ground(layer)` on a flat
layer that you flatten with `view.flatten(...)`, then `boss.draw_body(surface, view)` and
`boss.draw_particles(surface)` for what stands up.

## The fight: skills, moods and animation

He picks his next skill **at random** (weighted by how far you are, never the same one three
times in a row), and every skill has a clear wind-up so you can react.

| Skill | What you see | What to do |
| --- | --- | --- |
| **Charge** | lowers his head, paws the ground, red lane appears | step out of the lane; he is stunned after he hits the wall (hit him: 1.5x damage) |
| **Slam** | fists overhead, orange circle on the ground | leave the circle (phase 2 adds a ring of rocks) |
| **Roar** | arms flung wide, embers gather, then a **ring of fireballs** | walk through the gaps (phase 2: a second, slower ring) |
| **Rocks** | fists to the sky, **dark circles** appear; boulders fall | keep moving: the first boulder always lands on you |
| **Leap** | crouches, then jumps (can't be hurt in the air) | the circle shows where he lands: it is where you were standing |

Between attacks he is never still: each time he goes idle he rolls a mood. He **chases** you,
**circles** you, or **taunts** (a stomp, a snort or a roar). His wait times are a little random too.
He also turns to face you, leans into a charge, squashes when he lands, wobbles when stunned, and
kneels and topples over when he dies. Skill numbers (damage, wind-up times, how many fireballs or
boulders) are in `PHASE_STATS` at the top of `boss.py`.

## Playing the fight (the arena)

`src/bosses/minotaur/arena.py` is a self-contained, playable Labyrinth arena. It only uses the
boss's public surface, and nothing else in the game imports it.

```
python src/bosses/minotaur/arena.py            play it (flat arena, isometric boss)
python src/bosses/minotaur/arena.py --iso-room the optional isometric room
python src/bosses/minotaur/arena.py --bot      watch a bot fight him
python src/bosses/minotaur/arena.py --shot out.png --seconds 14     headless screenshot
```

| Key | Action |
| --- | --- |
| WASD / arrows, mouse | move, aim |
| left click / J / SPACE | sword (18 damage, 0.38 s cooldown) |
| right click / K / SHIFT | dodge roll (0.34 s of invulnerability, 0.7 s cooldown) |
| P / R / ESC | pause / restart / quit |
| M | sound on / off (`--mute` starts with it off) |
| 1 / 2 / 3 | testing: jump to phase 2 / heal / kill him |

The play area is the same (40, 110, 920, 600) the tests use. Player damage, HP and speed are
plain constants at the top of the `Player` and `Arena` classes, so tune them to match your real
player. The arena draws everything on the same 4 x 4 pixel grid as the sprites.

## Sound effects

Every part of the fight has a sound: his footsteps, snorts and roars, each skill's wind-up and its hit
(charge, slam, fireball ring, boulders, leap), the stun, the phase-change roar, his death; and for the
player the sword swing, roll, hits, blocks, getting hurt and the win / lose jingles (28 sounds in all,
33 files). They come from `sfx/*.wav` and are played by `src/bosses/minotaur/sfx.py`:

- **They follow the action.** A sound starts when the thing happens (a wind-up when he enters it, a
  slam or a boulder on the exact frame it bursts, a footstep with each step) and is panned left or right
  by where it happens on the screen. The wind-up sounds are timed to the telegraphs, so they also work as an audio cue.
- **They never change the fight.** Sounds are only played from the boss, never decided by them, and use
  their own random numbers.
- **They never crash the game.** No sound card, no mixer (a test run), a missing or broken file: that sound
  is just skipped. `boss.sfx = None` makes him completely silent.
- **Balance** the mix in `VOLUMES` at the top of `sfx.py` (a footstep should not be as loud as a slam);
  `board.volume` is the master volume.

They were synthesised from scratch (no recordings, nothing to license) by
`python tools/build_minotaur_sfx.py`, which uses only the Python standard library. Edit a sound's function
in that file and re-run it to retune that sound (`python tools/build_minotaur_sfx.py slam` rebuilds just one).
Re-running it **overwrites hand-swapped files**. To use your own recording instead, drop a WAV or OGG in
`sfx/` with the same name (`slam.wav`), or `step_1.wav`, `step_2.wav`, `step_3.wav` for a sound with variants
(the game picks one at random and never the same twice in a row).

In your own game, sound just works as long as the Pygame mixer is running (`pygame.init()` starts it). For
the best result call `pygame.mixer.pre_init(44100, -16, 2, 512)` before `pygame.init()`: stereo, so the panning
works, and a small buffer, so a sound is not late. Call `boss.sfx.load()` once at start-up so the files are
read before the fight, not during it. Sound names and what plays them:

| Sound | Played when |
| --- | --- |
| `roar_big` | he storms in (intro), and the phase-change roar |
| `thud` | he lands after the intro, and when he falls dead |
| `step`, `stomp`, `snort`, `roar` | walking; the stomp, snort or roar taunt |
| `charge_windup`, `charge`, `crash`, `stun` | pawing the floor; the run; hitting the wall; the stun |
| `slam_windup`, `slam` | fists up; the slam bursts (also the leap's landing, louder for bigger circles) |
| `cast_windup`, `fireball` | embers gather; the ring of fireballs leaves |
| `rain_windup`, `rock` | calling the rocks; each boulder landing |
| `leap_windup`, `leap` | crouching; the jump |
| `death` | the groan as he dies |
| `swing`, `roll`, `hit`, `hit_heavy`, `block` | sword, roll, a hit, the 1.5x hit on a stunned boss, hitting him while he is invulnerable |
| `hurt`, `player_down`, `victory`, `defeat` | you take damage; you fall; he dies; the defeat jingle |

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
| `pose_raise_phase1.png`, `pose_raise_phase2.png` | no | Both fists overhead. Used for the slam wind-up, the rock call and mid-leap |
| `pose_cast_phase1.png`, `pose_cast_phase2.png` | no | Arms flung wide. Used for the fireball roar and the phase-change roar |
| `sprite.json` | no | Placement numbers (below) |

| `walk_phase1.png`, `walk_phase2.png` | no | The walk cycle: 8 frames side by side (448 x 56). Frame 0 = left foot planted forward |
| `back_phase1.png`, `back_phase2.png` | no | Seen from behind (he shows his back when you are above him) |
| `pose_raise_back_phase*.png`, `pose_cast_back_phase*.png` | no | The two poses, from behind |
| `walk_back_phase1.png`, `walk_back_phase2.png` | no | The walk cycle, from behind |

Everything marked "no" is optional: if a file is missing he falls back to the closest picture
(no walk file = he bobs along; no back file = he shows his front). The **back views are an
approximation** made from the front art (face and belt emblem painted out, darkened, a mane of
fur tufts added): paint real back views over them if you want them to look better.

**Every PNG must be the same size.** The sprites are **56 x 56** pixels with a
**transparent** background, and the game draws each pixel as a 4 x 4 block (224 x 224 on
screen). Only fully solid or fully transparent pixels: turn anti-aliasing off in your editor.

Tip: open `body_phase1_a.png` in your pixel editor and paint over it, so the canvas size and
position are already right. Frame B can be a copy of frame A with a small change (for example
the body shifted up by 1 pixel).

## How the game uses the art

The game animates the sprite in code, so you do not need to draw any of these. It is smooth
because:

- **Springs, not jumps.** Lean, squash, lift and shadow chase their targets like a damped spring.
  Wind-ups ease in with no overshoot, landings squash and rebound, and nothing ever snaps when he
  changes state. The numbers (`omega` = snappiness, `zeta` = bounciness) are per state in
  `_animation()` in `boss.py`.
- **Poses cross-fade.** Raising or spreading his arms fades between the two pictures over 0.14 s
  instead of switching.
- **Turning is a quick squeeze,** not an instant mirror: he narrows, flips while narrow, widens.
- **No rounding.** Movement is drawn at full screen resolution, so a lean of half a degree or a
  nudge of a quarter sprite-pixel really shows.
- **Warning glow pulses** instead of blinking, and the hit flash fades out.

What it animates:

- **Lean, squash and stretch:** he leans into charges, crouches before a leap, squashes when he
  lands (all pivoting around his feet, so he never slides).
- **Facing:** the PNGs look **left**; he is mirrored to face you. Set `"faces": "right"` in
  `sprite.json` if you redraw him looking right.
- **Hit flash:** the whole sprite turns white for a moment.
- **Attack warning:** the sprite blinks red during every wind-up.
- **Lift:** he rises for the slam and flies up for the leap (his shadow shrinks).
- **Walking:** a bob, sway and a footstep squash with dust puffs.
- **After-images and dust:** a blur trail while charging and leaping, steam from his nose.
- **Death:** he kneels, topples over and fades out.

Phase 2 looks different only if you provide the `body_phase2_*` files. The shipped art uses
crimson fur, white-hot eyes, a glowing mouth and lava-like cracks on the chest and arm.

The `body_phase*_b.png` frames are still generated (and the art code still supports them), but
the boss no longer flips between frame A and B: that swap was a 4-pixel pop. Breathing, stepping
and stomping are now done by smooth squash, lean and lift in code, so frame A is all he needs.

The two poses are made from the painting by rotating each arm around its shoulder (see
`POSES` in `tools/build_minotaur_sprites.py`), then shrinking them with the same palette as the
body frames. You can also paint them by hand: open `body_phase1_a.png` and move the arms.

## `sprite.json`

Every key is optional. Numbers are in sprite pixels unless noted.

| Key | Meaning |
|-----|---------|
| `scale` | Screen pixels per sprite pixel (4 = each pixel is a 4x4 block) |
| `anchor` | `[x, y]` pixel that sits exactly on the boss's position. Hits and attacks are measured from here. Roughly the middle of the body |
| `shadow` | `{"y": rows below the anchor, "widths": [row widths]}`, the pixel shadow on the floor |
| `bob` | How far he bobs up and down |
| `pivot` | `[x, y]` pixel he leans and squashes around. Default: his feet (anchor x, 4 pixels above the bottom edge) |
| `faces` | `"left"` (default) or `"right"`: which way your PNGs look. He is mirrored to face the player |

**If your final sprite is a different size**, update `anchor` (and `shadow.y`, so the shadow sits
under the hooves). The hitbox is a circle set in `src/bosses/minotaur/boss.py` (`radius=46`);
change it there if the new sprite is much bigger or smaller.

If the sprites are missing or broken the game does not crash: it draws simple shapes and prints
what is wrong. Run `python src/bosses/dev/check_sprites.py minotaur` for details.
