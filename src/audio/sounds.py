"""
sounds.py - How LOUD each sound is and how it behaves when a fight gets busy.  THE place to balance the mix.

Every sound file in assets/audio/sfx/ is already normalised, so these numbers are the whole mix:

    gain      0..1+   how loud (the player's volume sliders are applied on top)
    cooldown  seconds the SAME sound is refused after it played (stops 20 bolts becoming one buzz)
    voices    how many copies may play at once (more are dropped)
    priority  0 = background spam (dropped first when the mixer is full)   1 = normal
              2 = important (steals a voice if it must)                    3 = never dropped
    duck      (amount, seconds)  the music dips by `amount` (0..1) for `seconds`, so a roar or a blast cuts through

A sound with no entry here still plays with the DEFAULT numbers, so you can drop a new .wav into
assets/audio/sfx/ and use it straight away.
"""
DEFAULT = {"gain": 0.7, "cooldown": 0.0, "voices": 4, "priority": 1, "duck": None}


LOUDNESS = 1.4                 # one knob for the whole mix: every gain below is multiplied by this (then capped at 1)


def _s(gain, cooldown=0.0, voices=4, priority=1, duck=None):
    return {"gain": min(1.0, gain * LOUDNESS), "cooldown": cooldown, "voices": voices, "priority": priority, "duck": duck}


SOUNDS = {
    # ---- the Lich King: taking damage, his windows, the Soul Ward ----
    "boss_hit":        _s(0.80, 0.05, 3),
    "boss_hit_open":   _s(0.90, 0.05, 3),
    "ward_deflect":    _s(0.60, 0.08, 2),
    "ward_up":         _s(0.80, 0.0, 1, 2, (0.12, 0.4)),
    "ward_break":      _s(1.00, 0.0, 1, 3, (0.25, 0.6)),
    "exhaust_open":    _s(0.90, 0.0, 1, 2, (0.15, 0.5)),
    # ---- the Lich King: attacks ----
    "volley_windup":   _s(0.55, 0.0, 2),
    "volley_fire":     _s(0.80, 0.04, 3),
    "drain_windup":    _s(0.50, 0.0, 2),
    "drain_burst":     _s(0.65, 0.06, 4),
    "drain_heal":      _s(0.60, 0.1, 2),
    "rain_windup":     _s(0.40, 0.0, 1),
    "rain_burst":      _s(0.45, 0.05, 4, 0),
    "grasp_windup":    _s(0.50, 0.0, 1),
    "grasp_burst":     _s(0.60, 0.06, 4, 0),
    "grasp_root":      _s(0.70, 0.1, 2, 2),
    "nova_windup":     _s(0.60, 0.0, 1),
    "nova_blast":      _s(1.00, 0.0, 2, 2, (0.22, 0.5)),
    "barrage_windup":  _s(0.50, 0.0, 1),
    "barrage_blast":   _s(1.00, 0.0, 1, 2, (0.15, 0.4)),
    "barrage_bolt":    _s(0.50, 0.06, 5, 0),
    "summon_windup":   _s(0.60, 0.0, 1),
    "summon_rise":     _s(0.80, 0.0, 2, 2, (0.15, 0.4)),
    "teleport_out":    _s(0.50, 0.0, 1),
    "teleport_in":     _s(0.55, 0.0, 1),
    "phase3_stomp":    _s(0.50, 0.15, 1, 0),
    # ---- the Lich King: the big moments ----
    "roar_phase2":     _s(1.00, 0.0, 1, 3, (0.30, 1.0)),
    "roar_phase3":     _s(1.00, 0.0, 1, 3, (0.35, 1.2)),
    "lich_intro":      _s(0.90, 0.0, 1, 3, (0.12, 0.8)),
    "lich_death":      _s(1.00, 0.0, 1, 3, (0.50, 2.0)),
    "victory_sting":   _s(1.00, 0.0, 1, 3, (1.00, 4.0)),
    "defeat_sting":    _s(1.00, 0.0, 1, 3, (1.00, 4.0)),
    # ---- skeletons (shared by every area and event) ----
    "monster_spawn":   _s(0.40, 0.08, 4, 0),
    "bone_hit":        _s(0.55, 0.04, 4),
    "bone_shatter":    _s(0.65, 0.05, 4),
    "brute_hit":       _s(0.65, 0.05, 3),
    "brute_shatter":   _s(0.80, 0.05, 3),
    "skeleton_windup": _s(0.35, 0.10, 3, 0),
    "sword_swish":     _s(0.45, 0.05, 3, 0),
    "brute_windup":    _s(0.60, 0.0, 2),
    "brute_swipe":     _s(0.60, 0.0, 2),
    "brute_slam":      _s(0.90, 0.0, 2, 2),
    "bow_draw":        _s(0.35, 0.08, 3, 0),
    "arrow_shoot":     _s(0.50, 0.05, 3, 0),
    "acolyte_charge":  _s(0.40, 0.0, 2, 0),
    "acolyte_mend":    _s(0.50, 0.0, 2),
    "acolyte_raise":   _s(0.70, 0.0, 2),
    "acolyte_bolt":    _s(0.60, 0.04, 3, 0),
    # ---- the hero (stand-ins used by the boss arena) ----
    "player_swing":    _s(0.50, 0.1, 2),
    "player_dash":     _s(0.50, 0.1, 1),
    "player_hurt":     _s(0.85, 0.1, 2, 2),
}

# sounds that LOOP while something is true (see audio.loop). name -> gain
LOOPS = {
    "ward_hum": 0.30,
}

# music: name -> gain (loud: this is a boss fight. The big sound effects dip it for a moment, see `duck`)
MUSIC = {
    "lich_p1": 0.85,
    "lich_p2": 0.90,
    "lich_p3": 1.00,
}
DEFAULT_MUSIC_GAIN = 0.85


def spec(name):
    """The numbers for one sound (the defaults if it has no entry)."""
    entry = dict(DEFAULT)
    entry.update(SOUNDS.get(name, {}))
    return entry
