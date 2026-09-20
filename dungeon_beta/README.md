# Dungeon Beta

A 2D top-down roguelike/RPG built with Python + Pygame, in the style of
*Soul Knight* / *Enter the Gungeon*. This is the beta scope: Hub → Spirit
NPC → Dungeon 1 (slime room → King Slime boss) → "thanks for testing" screen.

## 1. Setup

Works in VS Code or PyCharm — the code is identical either way.

```bash
python -m venv venv
source venv/bin/activate      # Windows: venv\Scripts\activate
pip install -r requirements.txt
python main.py
```

> **Windows note:** this project uses `pygame-ce` (the actively maintained
> community fork of pygame) instead of plain `pygame`. Same `import pygame`
> in the code, nothing to change — it's just far less likely to fail to
> install on newer Python versions, since plain `pygame` sometimes tries to
> compile from source on Windows and fails without Visual C++ build tools.
> If you ever see a build error like that, `pip install pygame-ce` is the fix.

## 2. Controls

| Key / Input        | Action                                              |
|---------------------|------------------------------------------------------|
| `W A S D`            | Move                                                  |
| Left Click            | Slash (hold to charge a bigger slash, release to swing) |
| `Space`              | Dash (brief invulnerability, phases through hits)    |
| `Q`                  | Special ability — AoE slash. Meter only fills by **landing hits** |
| `F`                  | Interact / talk (used on the Spirit in the hub)       |
| `Esc`                | Quit                                                  |

## 3. Project structure

```
main.py                     entry point
src/
  settings.py                all tunable numbers + controls + colors live here
  utils.py                   image/sound loader (auto placeholder if a file is missing)
  entities/
    player.py                Knight: movement, slash/charge, dash, AoE ability
    slime.py                 basic enemy, mini healthbar above its head
    king_slime.py             boss: telegraph -> jump -> land attack pattern, full bottom healthbar
    spirit.py                 hub NPC, dungeon-entry dialogue
  scenes/
    hub.py                    class select (Knight unlocked, others "beta locked"), spirit
    dungeon.py                 room 1 (slimes) -> room 2 (King Slime) -> portal -> end screen
    game.py                    scene manager / main loop
  ui/
    bars.py                    mini enemy healthbars, boss bar, player HUD, charge meter
assets/
  sprites/
    characters/knight/         knight_idle.png, knight_walk.png, knight_slash.png, sword.png
    monsters/slime/             slime_idle.png, slime_attack.png
    bosses/king_slime/          king_slime_idle.png, king_slime_telegraph.png, king_slime_jump.png, king_slime_attack.png
    map/hub/                    hub_floor.png, spirit.png
    map/dungeon/                 dungeon_floor.png, portal.png
    ui/                          player HP bar, ability meter, mini enemy bars, boss bar, charge bar
  sfx/                          drop .wav/.ogg files here (see below)
  music/                        drop background tracks here
```

## 4. Swapping in your own sprites

Every sprite is loaded by **exact filename** from the folders above
(see `src/settings.py` for the paths, `src/utils.py::load_image` for the loader).
**Just overwrite the PNG with the same filename** — no code changes needed.
If a file is ever missing, the game auto-generates a colored placeholder shape
instead of crashing, so you can always run the beta even mid-art-pass.

Recommended sprite size to match the current scale:
- Knight: 48x48 (or any square size — it's auto-scaled)
- Slime: 40x40
- King Slime: 110x110 (attack frame 140x140)
- Portal / Spirit: ~56-70px

To add new animation frames (e.g. a walk cycle instead of one static walk
image), the cleanest path is to extend `load_image` calls in `player.py` /
`slime.py` / `king_slime.py` into small lists of frames and cycle through
them with a timer — the current code deliberately keeps one image per state
so it's easy to expand once you have real spritesheets.

## 5. Reskinning the HP / ability / charge bars

Every bar (player HP, the Q-ability meter, each enemy's mini healthbar,
the boss's bottom bar, and the charge meter above the knight's head)
is built from **two images**: a `_frame` (border/background, always fully
visible) and a `_fill` (the colored bar that drains, cropped left-to-right
to match the current percentage — not squashed/stretched).

All of them live in `assets/sprites/ui/` and are wired up in `src/ui/bars.py`:

| File | Size (px) | Used for |
|---|---|---|
| `player_hp_frame.png` / `player_hp_fill.png` | 260x24 | Top-left player health bar |
| `ability_frame.png` / `ability_fill.png` | 260x16 | Q-ability meter |
| `ability_fill_ready.png` | 260x16 | Swapped in automatically once the ability is fully charged |
| `enemy_mini_hp_frame.png` / `enemy_mini_hp_fill.png` | 36x5 | Floating bar over each slime's head |
| `boss_hp_frame.png` / `boss_hp_fill.png` | 768x26 | King Slime's full-width bottom bar |
| `charge_frame.png` / `charge_fill.png` | 46x7 | Charge meter over the knight's head while holding a slash |

To reskin: overwrite any of these PNGs with the same filename — no code
changes needed. Exact sizes are defined once in `src/settings.py`
(`PLAYER_HP_BAR_SIZE`, `ENEMY_MINI_BAR_SIZE`, etc.), so if you want a
bigger or smaller bar, change the size there and drop in art at that new
size (or any size — it's auto-scaled either way).

## 6. Where to get free sprites (safe to use, no licensing issues)

I generated simple original placeholder art so the game runs out of the box,
but for real polish, these sites have game-ready, often CC0/free pixel art
in this exact top-down dungeon-crawler style:

- **Kenney.nl** — huge library of CC0 (zero-restriction) game asset packs,
  including top-down dungeon tiles and characters.
- **itch.io** → search "free" + "top down" or "dungeon crawler" asset packs
  (many creators publish CC0 or free-for-personal/academic-use packs).
- **OpenGameArt.org** — filter by license (CC0 / CC-BY) for sprites, tiles,
  and SFX.
- **Sprout Lands / CraftPix "freebies"** sections — stylized RPG character
  and slime-style enemy packs.

Since this is a non-commercial school project, CC-BY packs are fine too —
just keep a note of the attribution in case your teacher asks.

## 7. SFX / Music

Drop `.wav` or `.ogg` files into `assets/sfx/` and `assets/music/`. Suggested
starter set (not wired into code yet, filenames are up to you once you add
them — I left `src/utils.py::load_sound` ready for this):

- `slash.wav`, `charge_release.wav`, `dash.wav`, `ability_ready.wav`
- `slime_hit.wav`, `slime_death.wav`
- `king_slime_jump.wav`, `king_slime_land.wav`, `king_slime_death.wav`
- `spirit_talk.wav`, `portal_enter.wav`
- `hub_theme.ogg`, `dungeon_theme.ogg`, `boss_theme.ogg`

**Freesound.org** (CC0 filter) and **Kenney.nl's audio packs** are good
free sources for retro-fantasy SFX.

## 8. What's implemented in this beta

- Hub with class-select UI (Knight active, Archer/Mage marked "beta locked")
- Spirit NPC with Y/N dialogue to enter the dungeon
- Knight: slash, hold-to-charge slash (charge bar over head), dash
  (i-frames), AoE special (`Q`, meter only fills by landing hits), health bar
- Room 1: 4 slimes, each with a small floating healthbar
- Room 2: King Slime boss with its own telegraph → jump → slam pattern and
  a full-width bottom healthbar (boss-only treatment, per your spec)
- Portal spawns after the boss dies → walking into it ends the beta with a
  "thanks for testing" screen

## 9. Natural next steps (post-beta)

- Archer / Mage classes + their own dodge and special ability
- Real spritesheet-based animation instead of single-frame states
- Procedural or hand-authored room layouts instead of one fixed layout
- Save/checkpoint system between dungeons
