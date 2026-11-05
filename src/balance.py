"""
balance.py - Reads  config/balance.toml  and applies it to the Lich King and every monster.

    You never need to edit this file. To change the game's numbers, open  config/balance.toml,
    change a value, save, and start the game again.

HOW IT WORKS
    The numbers still live in the code as DEFAULTS (so the game runs even if the config is missing).
    When the boss / monster packages are imported they call the apply_* functions below, which overwrite
    those defaults with whatever the config file says. A bad value never crashes the game: it is ignored
    and a warning is printed in the console, e.g.
        [RealmQuest balance] [boss.phase3] 'combo' should be a whole number, got 'lots' - ignored.

    REALMQUEST_BALANCE=/some/other.toml   use another config file (handy for testing a difficulty)
    REALMQUEST_BALANCE=none               ignore the config completely (pure code defaults)
"""
import difflib
import os
import sys

try:
    import tomllib                                       # Python 3.11+
except ImportError:                                      # pragma: no cover
    tomllib = None

SRC_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(SRC_DIR)
DEFAULT_PATH = os.path.join(REPO_ROOT, "config", "balance.toml")
TOP_LEVEL = ("boss", "monsters", "tiers")

_cache = {}
_warned = set()


def warn(message):
    """Print a problem once (to the console) and carry on."""
    if message not in _warned:
        _warned.add(message)
        print(f"[RealmQuest balance] {message}", file=sys.stderr)


def config_path():
    return os.environ.get("REALMQUEST_BALANCE") or DEFAULT_PATH


def load():
    """The parsed config file as a dict ({} if it is missing, switched off or broken)."""
    path = config_path()
    if path in _cache:
        return _cache[path]
    data = {}
    if path.lower() == "none":
        pass
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
        target[name] = value
    else:
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
    table = section("monsters")
    for name, settings in table.items():
        cls = monsters.get(name)
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
        tier = tiers.setdefault(name, {"hp_scale": 1.0, "damage_scale": 1.0, "speed_scale": 1.0})
        _apply_dict(tier, settings, f"tiers.{name}")


# ----------------------------------------------------------------------
# the Lich King
# ----------------------------------------------------------------------

BOSS_ALIASES = {"max_hp": "BOSS_MAX_HP", "name": "BOSS_NAME", "radius": "BOSS_RADIUS", "intro": "BOSS_INTRO",
                "death_line": "BOSS_DEATH_LINE", "loot": "BOSS_LOOT"}
BOSS_OWNED_ELSEWHERE = ("summons",)        # read by lich_king/minions.py


def apply_boss(namespace, tunable, phase_stats):
    """Apply [boss] (and [boss.phase1..3]) to boss.py's constants. `namespace` is boss.py's globals()."""
    table = section("boss")
    phase_keys = {f"phase{number}": number for number in phase_stats}
    for key, number in phase_keys.items():
        if key in table:
            _apply_dict(phase_stats[number], table[key], f"boss.{key}")
    apply_table(namespace, table, "boss", set(tunable), BOSS_ALIASES,
                skip=tuple(phase_keys) + BOSS_OWNED_ELSEWHERE)


def apply_summons(cost, weight, limit, tier_holder):
    """Apply [boss.summons] tier = "..." and [boss.summons.<monster>] (cost / weight / limit) from minions.py."""
    table = section("boss")
    summons = table.get("summons", {})
    if not isinstance(summons, dict):
        warn("[boss.summons] should be a table - ignored.")
        return
    tables = {"cost": cost, "weight": weight, "limit": limit}
    for monster, settings in summons.items():
        if monster == "tier":
            if isinstance(settings, str):
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
                tables[key][monster] = new
