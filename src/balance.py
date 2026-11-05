"""
balance.py - Reads the config files in  config/  and applies them to every boss, monster and hero class.

    config/bosses/<boss>.toml          goblin_king, minotaur, lich_king
    config/monsters/<monster>.toml     every dungeon monster, elite and mini-boss (skeletons, goblins, orcs ...)
    (the wilds and the night raids use the dungeon monsters' files: one file per monster, everywhere)
    config/characters/<class>.toml     warrior, mage, archer   (+ hero.toml: shared by every class)
    config/tiers.toml                  difficulty tiers (health / damage / speed multipliers)

    You never need to edit this file. To change the game's numbers, open the file of the thing you want
    to change, change a value and save: a running game picks it up within a second or two (the Game polls
    ConfigWatcher and calls reload()). Delete a line (or a whole file) and the game uses its built-in
    default for it again.

HOW IT WORKS
    The numbers still live in the code as DEFAULTS (so the game runs even if the config is missing).
    When the boss / monster packages are imported they call the apply_* functions below, which overwrite
    those defaults with whatever the config file says. A bad value never crashes the game: it is ignored
    and a warning is printed in the console, e.g.
        [RealmQuest balance] [boss.phase3] 'combo' should be a whole number, got 'lots' - ignored.

    REALMQUEST_BALANCE=/some/folder       use another config folder (laid out like config/)
    REALMQUEST_BALANCE=/some/other.toml   use ONE file with every section in it ([boss], [monsters.x], [tiers.x],
                                          [bosses.x], [overworld.x], [characters.x]): handy for a difficulty preset
    REALMQUEST_BALANCE=none               ignore the config completely (pure code defaults)

LIVE RELOAD
    Every apply call (declare, apply_monsters, apply_boss, apply_summons) is recorded, and the first time a
    value is overwritten its code default is kept. reload() puts every default back, reads the files again
    and replays the recorded applies, so an edit (or a deleted line) takes effect without a restart.
    Objects that copied a number when they were made (a monster's health ...) are refreshed by the Game
    (dungeon_map.Game.on_config_reloaded). on_reload(fn) runs fn after every reload.
"""
import copy
import difflib
import os
import sys
import time

try:
    import tomllib                                       # Python 3.11+
except ImportError:                                      # pragma: no cover
    tomllib = None

SRC_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(SRC_DIR)
DEFAULT_PATH = os.path.join(REPO_ROOT, "config")          # the config folder (one file per thing)
TOP_LEVEL = ("boss", "monsters", "tiers", "bosses", "overworld", "characters")
# folder (inside config/) -> section. The Lich King's file is also the old [boss] section.
GROUP_DIRS = {"bosses": "bosses", "monsters": "monsters", "overworld": os.path.join("monsters", "overworld"),
              "characters": "characters"}
# Monster files that are NOT src/monsters classes (the dungeon's own monsters, read by src/maps/combat.py and
# src/monsters/in_game.py): [monsters.<name>] for these is not a mistake.
GAME_MONSTERS = {"goblin_minion", "goblin_shaman", "slime", "wild_boar", "goblin_war_boar", "goblin_general",
                 "orc_warrior", "orc_shaman", "treant", "elder_treant", "orc_warlord", "skeleton_warden",
                 "skeleton_army"}

_cache = {}
_warned = set()
_sink = None            # a list while reload() runs: it collects the warnings for the on-screen message
_defaults = {}          # key -> restore(): puts the code default back (kept the first time a value is changed)
_steps = []             # every apply call, in order, so reload() can replay them
_listeners = []         # fn() called after every reload
_replaying = False
_MISSING = object()


def warn(message):
    """Print a problem once (to the console) and carry on."""
    if _sink is not None and message not in _sink:
        _sink.append(message)
    if message not in _warned:
        _warned.add(message)
        print(f"[RealmQuest balance] {message}", file=sys.stderr)


# ----------------------------------------------------------------------
# live reload: remember the defaults, replay the applies
# ----------------------------------------------------------------------

def _keep_item(container, key):
    """Before container[key] changes for the first time, keep its default."""
    tag = ("item", id(container), key)
    if tag in _defaults:
        return
    old = copy.deepcopy(container[key]) if key in container else _MISSING

    def restore(c=container, k=key, v=old):
        if v is _MISSING:
            c.pop(k, None)
        else:
            c[k] = copy.deepcopy(v)
    _defaults[tag] = restore


def _keep_attr(obj, name):
    tag = ("attr", id(obj), name)
    if tag in _defaults:
        return
    own = name in vars(obj) if hasattr(obj, "__dict__") else True
    old = copy.deepcopy(getattr(obj, name)) if own else _MISSING

    def restore(o=obj, n=name, v=old):
        if v is _MISSING:
            if n in vars(o):
                delattr(o, n)                            # back to the inherited default
        else:
            setattr(o, n, copy.deepcopy(v))
    _defaults[tag] = restore


def _keep_prop(prop):
    tag = ("prop", id(prop))
    if tag in _defaults:
        return
    old = copy.deepcopy(prop.get())
    _defaults[tag] = lambda p=prop, v=old: p.set(copy.deepcopy(v))


def _step(fn):
    """Record an apply call (once) so reload() can replay it."""
    if not _replaying:
        _steps.append(fn)


def on_reload(fn):
    """Run fn() after every reload (for values a module works out from its settings)."""
    _listeners.append(fn)
    return fn


def reload():
    """Read the config files again and re-apply them over the code defaults.
    Returns the warnings (bad lines) found this time."""
    global _sink, _replaying
    _cache.clear()
    _warned.clear()
    _sink = []
    try:
        for restore in list(_defaults.values()):
            restore()
        _replaying = True
        try:
            for fn in list(_steps):
                fn()
        finally:
            _replaying = False
        for fn in list(_listeners):
            try:
                fn()
            except Exception as error:                   # a listener must never stop the game
                warn(f"after reloading: {error!r}")
        return list(_sink)
    finally:
        _sink = None


def config_files():
    """{path: modified time} of every config file the game reads now."""
    path = config_path()
    out = {}
    if path.lower() == "none":
        return out
    if os.path.isdir(path):
        for root, _dirs, names in os.walk(path):
            if os.path.basename(root) == "presets":
                continue
            for name in names:
                if name.endswith(".toml"):
                    full = os.path.join(root, name)
                    try:
                        out[full] = os.path.getmtime(full)
                    except OSError:
                        pass
    elif os.path.exists(path):
        try:
            out[path] = os.path.getmtime(path)
        except OSError:
            pass
    return out


class ConfigWatcher:
    """Notices when a config file is saved (or added / deleted).

        watch = ConfigWatcher()
        changed = watch.poll(now)        # every frame; checks the files every `interval` seconds
        if changed: warnings = reload()  # changed = the file names that changed

    A change is reported once the files have stayed the same for `settle` seconds, so a save that is
    still being written is not read half-way."""

    def __init__(self, interval=0.5, settle=0.3, clock=time.monotonic):
        self.interval, self.settle, self.clock = interval, settle, clock
        self.applied = config_files()
        self.seen = dict(self.applied)
        self.seen_t = 0.0
        self.next = 0.0

    def poll(self, now=None):
        now = self.clock() if now is None else now
        if now < self.next:
            return None
        self.next = now + self.interval
        files = config_files()
        if files != self.seen:
            self.seen, self.seen_t = files, now
            return None
        if self.seen != self.applied and now - self.seen_t >= self.settle:
            changed = sorted(os.path.basename(p) for p in set(self.seen) | set(self.applied)
                             if self.seen.get(p) != self.applied.get(p))
            self.applied = dict(self.seen)
            return changed
        return None


def config_path():
    return os.environ.get("REALMQUEST_BALANCE") or DEFAULT_PATH


def _read(path):
    """One TOML file as a dict ({} and a warning if it can't be read)."""
    if tomllib is None:
        warn("Python 3.11+ is needed to read the config files - using the built-in defaults.")
        return {}
    try:
        with open(path, "rb") as handle:
            return tomllib.load(handle)
    except (OSError, ValueError) as error:               # tomllib.TOMLDecodeError is a ValueError
        warn(f"could not read '{path}' ({error}) - using the built-in defaults for it.")
        return {}


def _load_folder(root):
    """config/ laid out one file per thing -> the same sections a single file would have."""
    data = {}
    for section_name, sub in GROUP_DIRS.items():
        folder = os.path.join(root, sub)
        if os.path.isdir(folder):
            data[section_name] = {name[:-5]: _read(os.path.join(folder, name))
                                  for name in sorted(os.listdir(folder)) if name.endswith(".toml")}
    if data.get("overworld"):
        warn("config/monsters/overworld/ is not read any more: the wilds and the night raids use the dungeon "
             "monsters' files (config/monsters/<monster>.toml).")
    lich = data.get("bosses", {}).get("lich_king")
    if lich:
        data["boss"] = lich                              # (the Lich King's settings, read by apply_boss)
    tiers = os.path.join(root, "tiers.toml")
    if os.path.exists(tiers):
        data["tiers"] = _read(tiers)
    if os.path.exists(os.path.join(root, "balance.toml")):
        warn("config/balance.toml is not read any more: its settings now live in config/bosses/lich_king.toml, "
             "config/monsters/skeleton_*.toml and config/tiers.toml.")
    return data


def load():
    """Every config setting as one dict of sections ({} if switched off or missing)."""
    path = config_path()
    if path in _cache:
        return _cache[path]
    data = {}
    if path.lower() == "none":
        pass
    elif os.path.isdir(path):
        data = _load_folder(path)
    elif not os.path.exists(path):
        if path != DEFAULT_PATH:
            warn(f"config file '{path}' not found - using the built-in defaults.")
    elif tomllib is None:
        warn("Python 3.11+ is needed to read the config file - using the built-in defaults.")
    else:
        try:
            with open(path, "rb") as handle:
                data = tomllib.load(handle)
        except (OSError, ValueError) as error:           # tomllib.TOMLDecodeError is a ValueError
            warn(f"could not read '{path}' ({error}) - using the built-in defaults.")
            data = {}
        for key in data:
            if key not in TOP_LEVEL:
                warn(f"unknown section [{key}] - ignored. Known sections: {', '.join(TOP_LEVEL)}.")
    _cache[path] = data
    return data


def section(name):
    value = load().get(name, {})
    return value if isinstance(value, dict) else {}


def entity(group, name):
    """The settings of one thing, e.g. entity("monsters", "orc_shaman") ({} if it has no file)."""
    value = section(group).get(name, {})
    if not isinstance(value, dict):
        warn(f"[{group}.{name}] should be a table of settings - ignored.")
        return {}
    return value


class Prop:
    """A setting that is not a plain constant: read with get(), written with set(value) (e.g. one entry of a
    list, or a number inside a frame table). Its default is whatever get() returns."""

    def __init__(self, get, set):                         # noqa: A002 (mirrors property())
        self.get, self.set = get, set


SPECS = {}          # (group, name) -> what a config file holds (tools/make_config_files.py writes the files from it)


def declare(group, name, title, about, target=None, fields=None, row=None, row_fields=(), docs=None, skip=(),
            partial=False):
    """
    Say that config/<group>/<name>.toml exists and what it holds, then apply it. Called by the code that owns
    the numbers, right after their defaults:

        balance.declare("monsters", "orc_shaman", "ORC SHAMAN", "Calls down meteors.", globals(),
                        fields={"meteor_cooldown": "METEOR_CD"}, row=(BERSERKER_MOBS, "shaman"),
                        row_fields=ROW, docs={"meteor_cooldown": "Seconds between meteors."})

    fields values are constant NAMES in `target`, or Prop objects. docs = one comment per key (for the file).
    partial=True: another part of the code owns the rest of this file (e.g. bosses/in_game.py reads only the
    [dungeon] table of minotaur.toml): its keys are added to the file's description and the other keys are
    not reported as unknown.
    """
    spec = SPECS.get((group, name))
    if spec is None or not partial:
        new = dict(group=group, name=name, title=title, about=about, targets=[], fields={}, row=row,
                   row_fields=tuple(row_fields), docs={}, skip=tuple(skip))
        if spec is not None:                              # a partial part declared first: keep its keys
            new["fields"].update(spec["fields"])
            new["docs"].update(spec["docs"])
            new["targets"] = spec["targets"]
            new["skip"] = tuple(k for k in new["skip"] if k not in spec["fields"])
        spec = SPECS[(group, name)] = new
    spec["fields"].update(fields or {})
    spec["docs"].update(docs or {})
    spec["targets"].append((target, dict(fields or {})))
    if partial:
        def run():
            settings = entity(group, name)
            wanted = {k: v for k, v in settings.items() if k in (fields or {})}
            return _apply_settings(wanted, group, name, target, fields, None, (), ())
    else:
        def run():
            return apply_entity(group, name, target, fields, row, row_fields, skip)
    _step(run)
    return run()


def apply_entity(group, name, target, fields=None, row=None, row_fields=(), skip=()):
    """
    Apply config/<group>/<name>.toml to the code that owns it.
        target      a module's globals() (or an object) whose constants the file can set
        fields      {key in the file: NAME of the constant}   (a dict constant takes a table: [key])
        row         (table, key): a tuple row like GOBLIN_MOBS["minion"] = (name, hp, speed, ...)
        row_fields  the file keys for that row's places, in order, e.g. ("name", "hp", "speed", ...)
        skip        keys another part of the code reads (no "unknown setting" warning for them)
    A wrong value never crashes the game: it is ignored with a warning. Returns the values applied.
    """
    return _apply_settings(entity(group, name), group, name, target, fields, row, row_fields, skip)


def _apply_settings(settings, group, name, target, fields, row, row_fields, skip):
    fields = fields or {}
    path = f"{group}.{name}"
    count = 0
    for key, value in settings.items():
        if key in skip:
            continue
        if row is not None and key in row_fields:
            table, row_key = row
            values = list(table[row_key])
            i = row_fields.index(key)
            ok, new = coerce(values[i], value, f"[{path}] '{key}'")
            if ok:
                values[i] = new
                _keep_item(table, row_key)
                table[row_key] = tuple(values)
                count += 1
        elif key in fields and isinstance(fields[key], Prop):
            prop = fields[key]
            _keep_prop(prop)
            default = prop.get()
            if isinstance(default, dict):
                table = dict(default)
                count += _apply_dict(table, value, f"{path}.{key}")
                prop.set(table)
            else:
                ok, new = coerce(default, value, f"[{path}] '{key}'")
                if ok:
                    prop.set(new)
                    count += 1
        elif key in fields:
            const = fields[key]
            default = _get(target, const)
            if isinstance(default, dict):
                count += _apply_dict(default, value, f"{path}.{key}")
            else:
                ok, new = coerce(default, value, f"[{path}] '{key}'")
                if ok:
                    _put(target, const, new)
                    count += 1
        else:
            names = list(row_fields) + list(fields) + list(skip)
            close = difflib.get_close_matches(key, names, n=1)
            warn(f"[{path}] unknown setting '{key}' - ignored." + (f" Did you mean '{close[0]}'?" if close else ""))
    return count


# ----------------------------------------------------------------------
# checking one value against the default it replaces
# ----------------------------------------------------------------------

def _kind(value):
    if isinstance(value, bool):
        return "true/false"
    if isinstance(value, int):
        return "a whole number"
    if isinstance(value, float):
        return "a number"
    if isinstance(value, str):
        return "text"
    return "a list"


def coerce(default, value, where):
    """Return (ok, new_value). Reports a warning (naming `where`) when the value does not fit."""
    if isinstance(default, bool):
        if isinstance(value, bool):
            return True, value
    elif isinstance(default, int):
        if isinstance(value, int) and not isinstance(value, bool):
            return _not_negative(value, where)
        if isinstance(value, float) and value.is_integer():
            return _not_negative(int(value), where)
    elif isinstance(default, float):
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            return _not_negative(float(value), where)
    elif isinstance(default, str):
        if isinstance(value, str):
            return True, value
    elif isinstance(default, (list, tuple)):
        ok, result = _coerce_sequence(default, value, where)
        if ok:
            return True, tuple(result) if isinstance(default, tuple) else result
        return False, None
    else:
        return True, value
    warn(f"{where} should be {_kind(default)}, got {value!r} - ignored.")
    return False, None


def _not_negative(value, where):
    if value < 0:
        warn(f"{where} cannot be negative (got {value}) - ignored.")
        return False, None
    return True, value


def _coerce_sequence(default, value, where):
    if not isinstance(value, list):
        warn(f"{where} should be a list like [1, 2], got {value!r} - ignored.")
        return False, None
    if not default:                                       # nothing to compare with: accept it as written
        return True, value
    kinds = {type(item) for item in default}
    fixed = (len(kinds) > 1) or all(isinstance(item, (int, float)) for item in default)
    if fixed:                                             # e.g. (min, max), a colour, ("Item", chance)
        if len(value) != len(default):
            warn(f"{where} should have exactly {len(default)} values, got {len(value)} - ignored.")
            return False, None
        templates = list(default)
    else:                                                 # a list of things: every entry looks like the first
        templates = [default[0]] * len(value)
    result = []
    for number, (template, item) in enumerate(zip(templates, value)):
        ok, new = coerce(template, item, f"{where}[{number}]")
        if not ok:
            return False, None
        result.append(new)
    return True, result


# ----------------------------------------------------------------------
# applying a table of settings to a target (a module's globals dict, or a class)
# ----------------------------------------------------------------------

def _get(target, name):
    return target.get(name) if isinstance(target, dict) else getattr(target, name, None)


def _put(target, name, value):
    if isinstance(target, dict):
        _keep_item(target, name)
        target[name] = value
    else:
        _keep_attr(target, name)
        setattr(target, name, value)


def apply_table(target, table, path, allowed, aliases=None, skip=()):
    """
    Copy settings from `table` onto `target`. A key like `windup_time` sets WINDUP_TIME (or the alias).
    Only names in `allowed` may be set. A table-inside-a-table whose name is not a setting is just a
    heading used to keep the file tidy ([boss.damage], [boss.ward] ...) and is read as if it were flat.
    Returns the number of values applied.
    """
    aliases = aliases or {}
    count = 0
    for key, value in table.items():
        if key in skip:
            continue
        name = aliases.get(key, key.upper())
        if name in allowed:
            default = _get(target, name)
            if isinstance(default, dict):
                count += _apply_dict(default, value, f"{path}.{key}" if path else key)
            else:
                ok, new = coerce(default, value, f"[{path}] '{key}'")
                if ok:
                    _put(target, name, new)
                    count += 1
        elif isinstance(value, dict):                     # a heading: read what is inside it
            count += apply_table(target, value, f"{path}.{key}", allowed, aliases, skip)
        else:
            _unknown(key, path, allowed, aliases)
    return count


def _apply_dict(default, value, path):
    if not isinstance(value, dict):
        warn(f"[{path}] should be a table of settings - ignored.")
        return 0
    count = 0
    for key, item in value.items():
        if key not in default:
            _unknown(key, path, list(default), {}, upper=False)
            continue
        ok, new = coerce(default[key], item, f"[{path}] '{key}'")
        if ok:
            _keep_item(default, key)
            default[key] = new
            count += 1
    return count


def _unknown(key, path, allowed, aliases, upper=True):
    names = [{v: k for k, v in aliases.items()}.get(n, n.lower() if upper else n) for n in allowed]
    close = difflib.get_close_matches(key, names, n=1)
    hint = f" Did you mean '{close[0]}'?" if close else ""
    warn(f"[{path}] unknown setting '{key}' - ignored.{hint}")


# ----------------------------------------------------------------------
# monsters
# ----------------------------------------------------------------------

# Things that describe the ART or the code, not the balance: not settable from the config.
MONSTER_HIDDEN = {"NAME", "DISPLAY_NAME", "FOOT", "STEP_LENGTH", "IDLE_FPS", "START_STATE", "INVULNERABLE_STATES"}


def monster_settings(cls):
    """{ATTRIBUTE: default} for every number / text / list a monster class lets you tune (in file order)."""
    found = {}
    for klass in reversed(cls.__mro__):
        if klass is object:
            continue
        for name, value in vars(klass).items():
            if name.isupper() and name not in MONSTER_HIDDEN and isinstance(
                    value, (bool, int, float, str, tuple, list, dict)):
                found[name] = value
    return found


def apply_monsters(monsters, tiers):
    """Apply [monsters.<name>] to the monster classes and [tiers.<name>] to the TIERS table."""
    _step(lambda: apply_monsters(monsters, tiers))
    table = section("monsters")
    for name, settings in table.items():
        cls = monsters.get(name)
        if cls is None and name in GAME_MONSTERS:
            continue                                     # read by the dungeon code (see GAME_MONSTERS)
        if cls is None:
            close = difflib.get_close_matches(name, list(monsters), n=1)
            warn(f"[monsters.{name}] is not a monster - ignored."
                 + (f" Did you mean '{close[0]}'?" if close else ""))
        elif not isinstance(settings, dict):
            warn(f"[monsters.{name}] should be a table of settings - ignored.")
        else:
            apply_table(cls, settings, f"monsters.{name}", monster_settings(cls))
    for name, settings in section("tiers").items():
        if not isinstance(settings, dict):
            warn(f"[tiers.{name}] should be a table of settings - ignored.")
            continue
        if name not in tiers:
            _keep_item(tiers, name)
        tier = tiers.setdefault(name, {"hp_scale": 1.0, "damage_scale": 1.0, "speed_scale": 1.0})
        _apply_dict(tier, settings, f"tiers.{name}")


# ----------------------------------------------------------------------
# the Lich King
# ----------------------------------------------------------------------

BOSS_ALIASES = {"max_hp": "BOSS_MAX_HP", "name": "BOSS_NAME", "radius": "BOSS_RADIUS", "intro": "BOSS_INTRO",
                "death_line": "BOSS_DEATH_LINE", "loot": "BOSS_LOOT"}
BOSS_OWNED_ELSEWHERE = ("summons", "dungeon")   # read by lich_king/minions.py and bosses/in_game.py


def apply_boss(namespace, tunable, phase_stats):
    """Apply [boss] (and [boss.phase1..3]) to boss.py's constants. `namespace` is boss.py's globals()."""
    _step(lambda: apply_boss(namespace, tunable, phase_stats))
    table = section("boss")
    phase_keys = {f"phase{number}": number for number in phase_stats}
    for key, number in phase_keys.items():
        if key in table:
            _apply_dict(phase_stats[number], table[key], f"boss.{key}")
    apply_table(namespace, table, "boss", set(tunable), BOSS_ALIASES,
                skip=tuple(phase_keys) + BOSS_OWNED_ELSEWHERE)


def apply_summons(cost, weight, limit, tier_holder):
    """Apply [boss.summons] tier = "..." and [boss.summons.<monster>] (cost / weight / limit) from minions.py."""
    _step(lambda: apply_summons(cost, weight, limit, tier_holder))
    table = section("boss")
    summons = table.get("summons", {})
    if not isinstance(summons, dict):
        warn("[boss.summons] should be a table - ignored.")
        return
    tables = {"cost": cost, "weight": weight, "limit": limit}
    for monster, settings in summons.items():
        if monster == "tier":
            if isinstance(settings, str):
                _keep_item(tier_holder, "minion_tier")
                tier_holder["minion_tier"] = settings       # (checked against the real tiers when he summons)
            else:
                warn(f"[boss.summons] 'tier' should be text like \"undying\", got {settings!r} - ignored.")
            continue
        if monster not in cost:
            close = difflib.get_close_matches(monster, ["tier"] + list(cost), n=1)
            warn(f"[boss.summons.{monster}] is not a monster the Lich King can call - ignored."
                 + (f" Did you mean '{close[0]}'?" if close else ""))
            continue
        if not isinstance(settings, dict):
            warn(f"[boss.summons.{monster}] should be a table of settings - ignored.")
            continue
        for key, value in settings.items():
            if key not in tables:
                _unknown(key, f"boss.summons.{monster}", list(tables), {}, upper=False)
                continue
            ok, new = coerce(tables[key][monster], value, f"[boss.summons.{monster}] '{key}'")
            if ok:
                _keep_item(tables[key], monster)
                tables[key][monster] = new
