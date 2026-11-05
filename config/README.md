# config/

One settings file per boss, monster and hero class. The game reads them when it starts.

```
config/
  bosses/        goblin_king.toml   minotaur.toml   lich_king.toml
  monsters/      every dungeon monster, elite and mini-boss
                 goblin_minion  goblin_shaman  slime  wild_boar  goblin_war_boar  goblin_general
                 orc_warrior  orc_shaman  treant  elder_treant  orc_warlord
                 skeleton_warrior  skeleton_archer  skeleton_acolyte  skeleton_brute  skeleton_warden  skeleton_army
                 (the overworld uses these same files: a goblin minion in the vale is the one in the dungeon.
                 Tier 1 near Oakwood = the Goblin Dungeon's mobs, tier 2 = the Berserker's, tier 3 = the Lich's.)
                 goblin_raider  berserker_raider  deadling
  characters/    warrior.toml  mage.toml  archer.toml   (each class: stats, basic attack, bars, [skills])
                 hero.toml      (shared by every class: sword, potions, dash)
  tiers.toml     difficulty tiers (health / damage / speed multipliers for monsters)
```

* Open a file in any text editor, change a number and save. A running game picks it up within a second
  (a message says "Config reloaded" - or how many lines were wrong). Monsters and bosses already fighting
  keep the same share of their health. No restart needed.
* Every line has a note (`# ...`) saying what it does. Delete a line, or a whole file, to get the built-in default back.
* Mistakes never crash the game: the line is ignored and a warning is printed in the console, e.g.
  `[RealmQuest balance] [monsters.slime] unknown setting 'sped' - ignored. Did you mean 'speed'?`
* The numbers in a boss file apply **exactly as typed**: the health bar shows `max_hp`, and every attack takes its
  damage off the hero (his armour then reduces it). The `[dungeon]` table has two optional scale knobs, both 1 = off:
  `hp_power` (a sword hit of 2 does 2 x this to the boss, and the bar shows his health divided by it) and
  `damage_k` (his hits on the hero x this).

## Resetting and presets

* `python tools/make_config_files.py` writes any file that is missing (it never touches your edits);
  `--force` rewrites them all from the defaults in the code; `--list` shows every file and what it holds.
* `lich_king.toml`, `skeleton_*.toml` and `tiers.toml` have hand-written notes: reset those with git.
* `REALMQUEST_BALANCE=path/to/folder` runs the game with a different config folder (e.g. a copy for an
  "easy" or "nightmare" run); `REALMQUEST_BALANCE=path/to/file.toml` uses one file with every section in it
  (`python tools/make_balance_config.py` writes one for the Lich King and the skeletons);
  `REALMQUEST_BALANCE=none` ignores the config completely.

## For developers

The loader is `src/balance.py`. The code that owns a number says which file may change it, right next to the
number, with `balance.declare(group, name, title, about, globals(), fields={...}, docs={...})` (see the end of
`src/maps/combat.py` for examples). Add the name and a note there, then run `python tools/make_config_files.py`
so the new line shows up in the file. `src/maps/tests/test_config_files.py` checks that every file loads with no
warnings, holds the code's defaults, and that an edited value really reaches the game.

The Lich King's numbers are listed in `TUNABLE` in `bosses/lich_king/boss.py`; a skeleton picks up any UPPERCASE
number on its class (descriptions: `MONSTER_DESC` in `tools/make_balance_config.py`).
