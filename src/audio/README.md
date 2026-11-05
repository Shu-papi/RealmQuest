# RealmQuest audio

Sound effects, looping sounds and boss music for the whole game. The sounds are plain `.wav` files in
`assets/audio/` (change a file, hear the change, no Python needed).

## For the game team: 2 lines

```python
import audio                       # or: from src import audio
audio.init(settings)               # ONCE at start-up (settings = ui.settings_data.Settings, optional)
```

That is all. The Lich King and every skeleton already play their own sounds. No sound card? `init` returns
False and everything stays silent, nothing crashes. Also useful:

| Call | What it does |
|------|--------------|
| `audio.play("bone_hit", x=monster.x)` | one sound (x = screen pixels, pans left/right, optional) |
| `audio.music("lich_p2")` / `audio.stop_music(2.0)` | music loop, crossfades |
| `audio.loop("ward_hum", True)` | a sound that lasts while something is true (call every frame) |
| `audio.stop_all()` | leaving the area / restarting the fight |
| `audio.apply_settings(settings)` | volume sliders (`Settings.apply_audio()` already calls it) |
| `audio.toggle_muted()` | mute |

When the player dies call `audio.stop_music()` and `audio.play("defeat_sting")`. The boss plays its own
`victory_sting`. The real Player class should call `audio.play("player_hurt" / "player_swing" / "player_dash")`
(the boss arena does this for its stand-in player).

## Try it

```
python src/bosses/dev/arena.py        # P = next phase, M = mute
```

## What plays when (Lich King)

* Intro: `lich_intro` + music `lich_p1`. Phase 2/3: roar + crossfade to `lich_p2` / `lich_p3`.
* Every attack: `<attack>_windup` (cut off exactly when the attack fires), then its release sound
  (`nova_blast`, `*_burst` for circles and hands, `summon_rise`; projectiles are deliberately silent).
* Hits: `boss_hit`; a brighter `boss_hit_open` while he is exhausted or stunned (+50%), so the window is audible.
* Phase 3 Soul Ward: `ward_up`, a `ward_hum` loop while it lasts, `ward_deflect` when you hit it, `ward_break` when it shatters.
* `exhaust_open` (gong) = "hit him now". Death: `lich_death`, music fades, then `victory_sting`.

## Skeletons (every area)

`Monster` plays `monster_spawn`, `bone_hit`, `bone_shatter` automatically. Each monster can pick its own:

```python
class Wolf(Monster):
    SFX_HURT = "wolf_yelp"; SFX_DIE = "wolf_die"; SFX_WINDUP = "wolf_growl"; SFX_STRIKE = "wolf_bite"
```
Drop `wolf_yelp.wav` etc. into `assets/audio/sfx/`. Set an attribute to `None` for silence.

## Mixing (src/audio/sounds.py)

One table: loudness, cooldown (stops machine-gun repeats), max voices, priority (spam is dropped first) and
ducking (roars and blasts turn the music down). Files named `name__v1.wav`, `name__v2.wav` ... are variants
picked at random. A new file with no entry still plays at default settings.

## Remaking the sounds (optional, needs numpy)

```
python src/audio/dev/make_sounds.py            # remake everything
python src/audio/dev/make_sounds.py boss_hit   # one sound
python src/audio/dev/make_sounds.py --report   # lengths, loudness, clipping
```
Real monster recordings (see `assets/audio/CREDITS.md`, mind its terms) are built by `src/audio/dev/import_pack.py`.
Recipes are in `src/audio/dev/recipes.py` (effects) and `music.py` (the three loops). The game itself needs
only pygame.

Tests: `python -m unittest discover -s src/audio/tests`

## Using real recordings (e.g. roars)

Download a free roar (OpenGameArt, itch.io and Freesound have CC0 / free packs: check each licence and credit the
author if it asks) and drop it into `assets/audio/sfx/`, named after the sound it replaces:

* `roar_phase2.wav`  (phase 1 -> 2),  `roar_phase3.wav`  (the enrage),  `lich_intro.wav`,  `lich_death.wav`
* `.wav` or `.ogg` both work. Delete the old file with the same name, or give several takes numbered
  names (`roar_phase3__v1.wav`, `roar_phase3__v2.wav`) and one is picked at random.
* Too loud or quiet? Change its `gain` in `src/audio/sounds.py`.

(`make_sounds.py` only overwrites files it makes itself, so run it with a sound name, not bare, once you have swapped in your own.)
