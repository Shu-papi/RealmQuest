# Prototype Guide (VS Code)

Prototype: `prototypes/characters/main.py` (Python + Pygame).

## 1. Setup (once)

1. Install [Python 3.10+](https://python.org). Tick **Add to PATH**.
2. In VS Code, install the **Python** extension.
3. Open the repo folder: **File > Open Folder**.
4. Open the terminal (``Ctrl+` ``) and run:
   ```
   pip install pygame
   ```
   Not found? Try `py -m pip install pygame` (Windows) or `pip3` (Mac/Linux).

## 2. Run

```
python prototypes/characters/main.py
```
Or open `main.py` and click the **Run** ▶ button (top right).

Controls: **← →** move, **Space** attack, **1 / 2 / 3** warrior / mage / archer, **Esc** quit.

## 3. Use your sprites

Put sheets in `assets/characters/`:

```
<character>_idle.png   <character>_walk.png   <character>_attack.png
(e.g. warrior_idle.png, mage_attack.png, archer_walk.png)
```

Rules: frames are **square**, side by side in one row, transparent background (e.g. 7 x 32px = 224x32).
Frame count is detected automatically. Missing sheets fall back to placeholders.

Set FPS and damage frame in `ANIMS` / `DAMAGE_FRAME`, and stats in `CHARACTERS`, at the top of `main.py`.

## 4. How the code works

| Piece | What it does |
|---|---|
| `CHARACTERS`, `ANIMS` | All numbers, one row per character. |
| `load_frames()` | Slices a sheet into frames. |
| `Character.state` | `idle` / `walk` / `attack`. One at a time. |
| `frame_index` | `time in state x fps` gives the current frame. |
| `update(dt)` | Input, state changes, movement. Runs every tick. |
| `strike()` | Damage frame: melee reach check, or spawn a `Projectile`. |
| `Projectile` | Flies, hits the target, or expires at max range. |
| `draw()` | Draws the current frame, flipped when facing left. |
| Main loop | Events, update, draw, repeat at 60 FPS. |

Key idea: damage happens **on a specific frame** (`DAMAGE_FRAME`), once per attack (`hit_done`).

## 5. Practice (do these yourself)

1. Change `damage` and `cooldown` in `CHARACTERS`. Observe.
2. Add your real `warrior_idle.png`. Fix drift if it jitters.
3. Draw `walk`, `attack` sheets for each character and drop them in.
4. Add a `hurt` state: press `H`, play it, return to idle.
5. Add a `death` state when the *warrior's* HP hits 0.
6. Add a 4th character: one new row in `CHARACTERS` and one key in `SWITCH_KEYS`.
7. Read the docs for anything unfamiliar: <https://www.pygame.org/docs/>

## 6. Debugging

- Read the **last line** of the error. It names the file and line.
- `print(variable)` to inspect values.
- Click left of a line number to set a breakpoint, then press **F5** to step through.

## 7. Commit (VS Code)

1. Click branch name (bottom-left), **Create new branch**: `feature/character-prototype`.
2. **Source Control** (`Ctrl+Shift+G`), then **+** on your files.
3. Write a message, **Commit**, **Publish Branch**.
4. On GitHub, **Compare & pull request**.

Terminal version:
```
git checkout -b feature/character-prototype
git add prototypes/ docs/ assets/
git commit -m "Add warrior prototype and guide"
git push -u origin feature/character-prototype
```
