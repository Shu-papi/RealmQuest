"""
make_config_files.py - Writes config/ : one settings file per boss, monster and hero class.

    python tools/make_config_files.py            # write the files that are missing (never touches your edits)
    python tools/make_config_files.py --force    # rewrite every file from the numbers in the code (a reset)
    python tools/make_config_files.py --list     # just list the files and what they hold
    python tools/make_config_files.py --root DIR # work on DIR (a copy of config/) instead of config/

The game reads these files at start-up (src/balance.py). Each part of the code says which of its numbers a file
may set (balance.declare(...), next to the numbers), and this tool writes the files from those declarations
with the code's default values and a note on every line.

Not written here (they have their own hand-written notes, and were split out of the old config/balance.toml):
    config/bosses/lich_king.toml   config/monsters/skeleton_*.toml   config/tiers.toml
    Reset those with  python tools/make_balance_config.py --force  (one file), or git.
    This tool still adds a missing [dungeon] table to lich_king.toml.
"""
import json
import os
import sys
import textwrap

os.environ["REALMQUEST_BALANCE"] = "none"          # read the code's own defaults, not the current files
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "src"))

FOLDERS = {"bosses": "bosses", "monsters": "monsters", "overworld": os.path.join("monsters", "overworld"),
           "characters": "characters"}
HAND_WRITTEN = {("bosses", "lich_king")}          # (+ the skeleton_*.toml and tiers.toml, not declared here)
NOTE_COLUMN = 42
COMMON = ("Change a number and save (no restart). Delete a line (or this file) and the game uses its built-in\n"
          "default. A mistake never crashes the game: the bad line is ignored and a warning is printed in the console.\n"
          "Times are in SECONDS, distances in PIXELS, \"damage\" is the health the hero loses.")


def load_specs():
    """Import everything that declares a config file and return balance.SPECS."""
    import pygame
    pygame.display.init()
    pygame.display.set_mode((1, 1))
    from src.maps import combat, night_raid, wilds                      # noqa: F401  (they declare their files)
    import bosses                                                       # noqa: F401  (the Minotaur)
    import bosses.in_game                                               # noqa: F401
    import bosses.goblin_king.boss_config                               # noqa: F401
    import monsters.in_game                                             # noqa: F401
    import balance
    return balance.SPECS


def value_of(spec, key):
    """The default value of one setting of a declared file."""
    row = spec["row"]
    if row is not None and key in spec["row_fields"]:
        table, row_key = row
        return table[row_key][spec["row_fields"].index(key)]
    field = spec["fields"][key]
    if hasattr(field, "get") and hasattr(field, "set"):
        return field.get()
    for target, fields in spec["targets"]:
        if key in fields:
            return target[field] if isinstance(target, dict) else getattr(target, field)
    raise KeyError(key)


def toml(value):
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return repr(value)
    if isinstance(value, str):
        return json.dumps(value)
    if isinstance(value, (list, tuple)):
        return "[" + ", ".join(toml(v) for v in value) + "]"
    raise TypeError(f"can't write {value!r}")


def line(key, value, note):
    text = f"{key} = {toml(value)}"
    if note:
        text = text.ljust(NOTE_COLUMN - 1) + " # " + note
    return text


def notes(text, width=110):
    return "\n".join("# " + l for l in textwrap.wrap(text, width - 2)) if text else ""


def table_text(key, value, note):
    out = [notes(note), f"[{key}]"] if note else [f"[{key}]"]
    out += [line(k, v, "") for k, v in value.items()]
    return "\n".join(out)


def file_text(spec):
    keys = list(spec["row_fields"]) + [k for k in spec["fields"] if k not in spec["row_fields"]]
    plain, tables = [], []
    for key in keys:
        value = value_of(spec, key)
        note = spec["docs"].get(key, "")
        if isinstance(value, dict):
            tables.append(table_text(key, value, note))
        else:
            plain.append(line(key, value, note))
    bar = "# " + "=" * 108
    head = [bar, f"#  RealmQuest  -  {spec['title']}"]
    head += ["#  " + l for l in textwrap.wrap(spec["about"], 106)]
    head += ["#"] + ["#  " + l for l in COMMON.splitlines()] + [bar, ""]
    return "\n".join(head + plain + [""] + ["\n\n".join(tables)]).rstrip() + "\n"


def main(argv):
    force = "--force" in argv
    specs = load_specs()
    config = os.path.join(ROOT, "config")
    if "--root" in argv:
        config = os.path.abspath(argv[argv.index("--root") + 1])
    for (group, name), spec in sorted(specs.items()):
        path = os.path.join(config, FOLDERS[group], name + ".toml")
        rel = os.path.relpath(path, ROOT)
        if "--list" in argv:
            print(f"{rel:48} {', '.join(list(spec['row_fields']) + [k for k in spec['fields'] if k not in spec['row_fields']])}")
            continue
        if (group, name) in HAND_WRITTEN or (os.path.exists(path) and not force):
            if os.path.exists(path):                               # add any missing [table] at the end
                import tomllib
                with open(path, "rb") as f:
                    have = tomllib.load(f)
                extra = [table_text(k, value_of(spec, k), spec["docs"].get(k, ""))
                         for k in spec["fields"] if k not in have and isinstance(value_of(spec, k), dict)]
                if extra:
                    with open(path, "a", encoding="utf-8") as f:
                        f.write("\n\n" + "\n\n".join(extra) + "\n")
                    print("added", ", ".join(k for k in spec["fields"] if k not in have), "to", rel)
            continue
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(file_text(spec))
        print("wrote", rel)


if __name__ == "__main__":
    main(sys.argv[1:])
