# config/

`balance.toml` holds the numbers for the Lich King, his phases, every monster and the difficulty tiers.

* Open it in any text editor, change a number, save, restart the game.
* Notes (`# ...`) next to every line say what it does. Delete a line to get the built-in default back.
* Mistakes never crash the game: the line is ignored and a warning is printed in the console.
* `python tools/make_balance_config.py --force` resets the file to the defaults in the code (do this
  after a developer adds a new setting, so the new line shows up with its description).
* `REALMQUEST_BALANCE=path/to/other.toml` runs the game with a different file (e.g. an "easy" or
  "nightmare" copy); `REALMQUEST_BALANCE=none` ignores the config completely.

For developers: the loader is `src/balance.py`. To expose a new Lich King number, add its name to `TUNABLE` in
`bosses/lich_king/boss.py` and a description line in `tools/make_balance_config.py` (a test fails if you forget).
For a monster, any UPPERCASE number/list on its class is picked up automatically; add a description to
`MONSTER_DESC` in the tool.
