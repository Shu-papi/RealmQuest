# How to add a boss

Every boss lives in its own folder, so several people can build bosses at the same time
without touching each other's files. Example below: a boss called `dragon`.

## Steps

1. **Update and make your branch** (from the repo root):
   ```
   git checkout main
   git pull
   git checkout -b feature/dragon-boss
   ```
2. **Copy the template.** Copy the folder `src/bosses/_template/` to `src/bosses/dragon/`.
   The folder name must be lowercase with underscores (`stone_golem`, not `Stone Golem`).
3. **Rename the class.** In `src/bosses/dragon/boss.py`, change `TemplateBoss` to `Dragon`.
   Do the same in `src/bosses/dragon/__init__.py`.
4. **Make it yours.** Edit `boss.py`: name, HP, intro and death lines, loot, the attacks, and
   `draw_boss`. Read the comments at the top of the template first.
5. **Register it.** Open `src/bosses/__init__.py` and change the two lines marked `ADD HERE`:
   ```python
   from .dragon import Dragon
   ...
   "dragon": Dragon,
   ```
6. **Play it.**
   ```
   python src/bosses/dev/arena.py dragon
   ```
7. **Run the tests.** Your boss is checked automatically (does it attack, draw, take damage,
   die, and drop loot?):
   ```
   python -m unittest discover -s src/bosses/tests
   ```
8. **Artwork** goes in `assets/bosses/dragon/`. Until you have art, draw with shapes like the
   template does. To use PNG sprites like the Lich King, read `assets/bosses/lich_king/README.md`
   and `src/bosses/lich_king/art.py`.
9. **Commit only your own files** and open a Pull Request:
   ```
   git status
   git add src/bosses/dragon src/bosses/__init__.py assets/bosses/dragon
   git commit -m "Add Dragon boss"
   git push -u origin feature/dragon-boss
   ```

## Rules of the road

- **Put everything specific to your boss inside `src/bosses/<your_boss>/`**: its minions,
  special attacks, and art code. Never edit another person's boss folder.
- **Shared files** are `base_boss.py`, `attacks.py`, `pixel_art.py`, `paths.py`, and the `dev/`
  and `tests/` folders. Tell the team before changing them, because every boss uses them.
- **`src/bosses/__init__.py` is edited by everyone** (two lines each), so Git may report a
  conflict when two bosses merge. Keep BOTH people's lines and delete the `<<<<`, `====`, `>>>>`
  markers.
- **Always warn before a dangerous attack** (a wind-up the player can see and react to).

## What the game expects from your boss

- `update_ai(dt, player, bounds)` and `draw_boss(surface)` are yours to write.
- Reaching the state `"dead"` is what marks the boss as defeated. `on_death()` should move to a
  `"dying"` state, then `"dead"`.
- A state called `"transition"` shows a "powers up" banner in the test arena.
- The player only needs `player.rect` and `player.take_damage(amount)`.
