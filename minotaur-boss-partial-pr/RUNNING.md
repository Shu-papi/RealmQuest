# Running the Minotaur (with sound)

```
pip install pygame-ce                                   # (or pygame)
python src/bosses/minotaur/arena.py                     # play it. M = sound on/off, P = pause
python src/bosses/minotaur/arena.py --bot               # watch a bot fight him
python -m unittest discover -s src/bosses/tests         # run the tests
python tools/build_minotaur_sfx.py                      # rebuild the sound files (overwrites hand edits)
```

## Stand-ins (this was a partial PR)

The zip did not include some files the Minotaur imports, so these were rebuilt from how the Minotaur and its tests
use them. They are enough to run and test the fight, but **if your real repo already has them, keep yours and do not
copy these**:

| File | What it is |
| --- | --- |
| `src/bosses/base_boss.py` | `Boss`: hit points, `set_state`, hazards and projectiles, `update`, `draw` |
| `src/bosses/attacks.py` | `Projectile`, `player_pos`, `player_radius` |
| `src/bosses/pixel_art.py` | `draw_dotted_line`, `draw_pixel_ring` |
| `src/bosses/paths.py` | `asset_dir(name)` |
| `src/bosses/lich_king.py` | empty placeholder so `bosses/__init__.py` imports |
| `src/pygame_stub.py` | lets the logic tests run without pygame (drawing tests are skipped) |

Also changed: one pixel-reading test in `test_minotaur_view.py` is now marked `@needs_pygame` (it cannot work on the stub).

## Without pygame

`python -m unittest discover -s src/bosses/tests` still runs: 142 tests pass and 47 that need a real window are skipped.
Install pygame to run those too and to open the arena.
