"""
recipes.py - How every sound effect in assets/audio/sfx/ is made (DEV TOOL ONLY).

Each recipe is a small function: recipe(seed) -> numpy array. Sounds that play a lot (hits, bolts, shatters) have
several VARIANTS (the seed changes a little: pitch, timing), and the game picks one at random so a fight doesn't
sound like a machine gun firing the same sample.

To change a sound:  edit its recipe, run  python src/audio/dev/make_sounds.py  and listen.
To use a sound you recorded yourself: just drop a .wav in assets/audio/sfx/ with the same name. No code.
"""
import numpy as np

from . import synth as s
from .synth import (bp, drive, echo, finish, formant, glide, hp, layer, lp, noise, osc, perc, ramp, reverb, rng, swell,
                    sweep_bp, sweep_lp, times)


# ----------------------------------------------------------------------------------------------------------
# building blocks that several sounds share
# ----------------------------------------------------------------------------------------------------------

def ping(freq, seconds, decay=0.05):
    return np.sin(2 * np.pi * freq * times(seconds)) * perc(seconds, 0.0008, decay)


def bell(freq, seconds, ratios=(1.0, 2.4, 3.9, 5.6), decay=0.6):
    """A struck metal thing: several inharmonic partials, the high ones dying first."""
    t = times(seconds)
    out = np.zeros(len(t))
    for i, ratio in enumerate(ratios):
        out += np.sin(2 * np.pi * freq * ratio * t) * np.exp(-t / (decay / (1 + 0.45 * i))) / (1 + 0.5 * i)
    return out * np.minimum(t / 0.002, 1.0)


def thump(f0, f1, seconds, decay=0.12):
    return osc("sine", glide(f0, f1, seconds)) * perc(seconds, 0.002, decay)


def clack(freq, seconds=0.12, seed=0, ring=0.02):
    """Bone on bone: a tiny noise tick plus a few short, dry rings."""
    t = times(seconds)
    tick = bp(noise(seconds, seed) * perc(seconds, 0.0004, 0.005), 1400, 7000)
    body = sum(np.sin(2 * np.pi * freq * k * t) * np.exp(-t / (ring / (1 + 0.5 * i)))
               for i, k in enumerate((1.0, 1.62, 2.41)))
    return tick * 1.2 + body * 0.35


def clatter(seconds, count, seed=0, low=900, high=2600, ring=0.02, taper=True):
    """Lots of clacks at random moments: a pile of bones."""
    r = rng(seed)
    parts = []
    for _ in range(count):
        at = float(r.uniform(0, seconds * 0.85))
        gain = float(r.uniform(0.4, 1.0)) * ((1 - 0.65 * at / seconds) if taper else 1.0)
        parts.append((clack(float(r.uniform(low, high)), 0.12, int(r.integers(1 << 30)), ring), at, gain))
    return layer(seconds, parts)


def whoosh(seconds, f0, f1, seed=0, width=0.9, peak=0.5):
    n = noise(seconds, seed)
    return sweep_bp(n, glide(f0, f1, seconds), width) * swell(seconds, peak, 1.2)


def blast(seconds=0.8, f0=110.0, decay=0.25, burst_decay=0.18, seed=0, debris=0.4):
    """An explosion: a deep boom, a fireball of noise that cools from bright to dull, a crack and flying rubble."""
    boom = thump(f0, 28, seconds, decay)
    fire = sweep_lp(noise(seconds, seed) * perc(seconds, 0.002, burst_decay), glide(5200, 220, seconds))
    crack = hp(noise(0.08, seed + 1) * perc(0.08, 0.0005, 0.012), 1500)
    rubble = clatter(seconds * 0.8, 6, seed + 2, 600, 2200, 0.02) * debris
    return layer(seconds, [(boom, 0, 1.0), (fire, 0, 1.1), (crack, 0, 0.6), (rubble, 0.03, 1.0)])


def choir(freqs, seconds, vowel=(700, 1100, 2500), vib=5.2, depth=0.006, seed=0):
    """Ghostly voices: buzzy saws with a vowel carved out of them."""
    r = rng(seed)
    t = times(seconds)
    mix = np.zeros(len(t))
    for f in freqs:
        for det in (-0.007, 0.0, 0.007):
            wobble = 1 + depth * np.sin(2 * np.pi * (vib + r.uniform(-0.6, 0.6)) * t + r.uniform(0, 6.28))
            mix += osc("saw", f * (1 + det) * wobble)
    out = np.zeros(len(t))
    for centre, gain in zip(vowel, (1.0, 0.7, 0.25)):
        out += gain * formant(mix, centre, 5.0)
    return out / max(1, len(freqs))


def roar(seconds, base, harsh, seed=0):
    """A huge undead roar: a growling buzz that opens and closes like a mouth."""
    t = times(seconds)
    u = t / seconds
    pitch = base * (0.8 + 0.55 * np.sin(np.pi * u ** 0.7)) * (1 + 0.02 * np.sin(2 * np.pi * 7 * t))
    buzz = osc("saw", pitch) * (1 + 0.6 * np.sin(2 * np.pi * (34 + 8 * harsh) * t))
    voice = drive(buzz, 2.0 + 3.0 * harsh)
    shaped = sweep_bp(voice, glide(1100, 420, seconds), 1.3) + 0.5 * lp(voice, 320)
    air = hp(noise(seconds, seed), 1800) * swell(seconds, 0.35) * (0.15 + 0.2 * harsh)
    return (shaped + air) * swell(seconds, 0.22, 0.8)


# ----------------------------------------------------------------------------------------------------------
# the Lich King: being hit, the Soul Ward, his windows
# ----------------------------------------------------------------------------------------------------------

def boss_hit(seed=0):
    r = rng(seed)
    body = thump(float(190 * r.uniform(0.9, 1.1)), 55, 0.24, 0.07)
    crack = lp(noise(0.24, seed) * perc(0.24, 0.001, 0.02), 3200)
    return finish(layer(0.26, [(body, 0, 1.0), (crack, 0, 0.7), (clack(float(1800 * r.uniform(0.9, 1.2)), 0.2, seed), 0, 0.5)]))


def ward_break(seed=0):
    d = 1.5
    r = rng(5)
    glass = layer(d, [(ping(float(r.uniform(2500, 9000)), 0.2, 0.03), float(r.uniform(0.02, 0.8)), float(r.uniform(0.15, 0.5)))
                      for _ in range(46)])
    boom = thump(230, 38, 1.1, 0.35)
    suck = hp(noise(0.2, 2), 1500) * ramp(0.2, 0.0, 1.0, 2.0)
    crash = hp(noise(0.5, 4) * perc(0.5, 0.002, 0.12), 2500)
    return finish(reverb(layer(d, [(suck, 0, 0.5), (glass, 0.18, 1.0), (boom, 0.18, 1.0), (crash, 0.18, 0.6)]), 1.2, 0.3))


def ward_hum(seed=0):
    """LOOPS (2 s). Every pitch is a whole number of waves per loop, so there is no click where it wraps round."""
    d = 2.0
    t = times(d)
    parts = [(f, g) for f, g in ((110, 1.0), (165, 0.6), (220, 0.5), (330, 0.3), (440, 0.15))]
    out = sum(g * (np.sin(2 * np.pi * f * t) + np.sin(2 * np.pi * (f + 0.5) * t)) for f, g in parts)
    out = out * (1 + 0.25 * np.sin(2 * np.pi * 2 * t)) + 0.15 * np.sin(2 * np.pi * 880 * t) * (1 + np.sin(2 * np.pi * 1 * t))
    return finish(out, 0.9, 0.0, 0.0)


# ----------------------------------------------------------------------------------------------------------
# the Lich King: attacks (a wind-up sound, then the release)
# ----------------------------------------------------------------------------------------------------------

def drain_burst(seed=0):
    r = rng(seed)
    thud = thump(float(105 * r.uniform(0.9, 1.1)), 38, 0.5, 0.17)
    hollow = lp(noise(0.5, seed) * perc(0.5, 0.004, 0.14), 900)
    return finish(reverb(layer(0.7, [(thud, 0, 0.9), (hollow, 0, 0.7), (blast(0.6, 100, 0.2, 0.15, seed + 9, 0.3), 0, 0.9)]), 0.6, 0.2))


def grasp_windup(seed=0):
    d = 0.95
    rumble = lp(noise(d, 4, "brown"), 260) * swell(d, 0.85, 1.0) * 2.0
    r = rng(6)
    cracks = layer(d, [(clack(float(r.uniform(500, 1400)), 0.1, int(r.integers(999)), 0.03), float(r.uniform(0.1, d - 0.15)),
                        float(r.uniform(0.3, 0.9))) for _ in range(7)])
    return finish(layer(d, [(rumble, 0, 1.0), (cracks, 0, 0.8)]), 0.9, 0.01, 0.03)


def grasp_burst(seed=0):
    r = rng(seed)
    dirt = lp(noise(0.5, seed) * perc(0.5, 0.003, 0.14), 1000)
    crunch = clatter(0.45, 7, seed + 3, 600, 1800, 0.03, False)
    thud = thump(float(120 * r.uniform(0.9, 1.1)), 45, 0.4, 0.13)
    return finish(layer(0.55, [(dirt, 0, 0.9), (crunch, 0, 0.9), (thud, 0, 1.0)]))


def nova_windup(seed=0):
    d = 1.15
    t = times(d)
    sub = osc("sine", glide(45, 210, d)) * (1 + 0.5 * np.sin(2 * np.pi * 9 * t))
    suck = sweep_lp(noise(d, 8), glide(200, 4500, d)) * ramp(d, 0.1, 1.0, 2.0)
    return finish(layer(d, [(sub * ramp(d, 0.2, 1.0, 1.5), 0, 0.8), (suck, 0, 0.8)]), 0.9, 0.01, 0.01)


def summon_windup(seed=0):
    d = 1.25
    chant = choir([73.4, 110.0, 146.8], d, (450, 800, 2300), 4.5, 0.008, 4) * swell(d, 0.8, 1.0)
    hits = [(thump(70, 40, 0.25, 0.09), 0.1 + 0.3 * i, 0.8) for i in range(4)]
    return finish(reverb(layer(d, [(chant, 0, 1.0)] + hits), 1.2, 0.3), 0.9, 0.01, 0.03)


def summon_rise(seed=0):
    d = 1.5
    t = times(d)
    rumble = lp(noise(d, 7, "brown"), 300) * swell(d, 0.3, 1.0) * 2.0
    wail = osc("sine", glide(380, 880, d) * (1 + 0.015 * np.sin(2 * np.pi * 6 * t))) * swell(d, 0.5, 1.0) * 0.35
    bones = clatter(1.2, 14, 12, 700, 2600, 0.025, False)
    return finish(reverb(layer(d, [(rumble, 0, 1.0), (wail, 0.1, 0.8), (bones, 0.1, 0.9), (thump(90, 35, 0.6, 0.2), 0.05, 1.0)]), 1.0, 0.25))


def volley_fire(seed=0):
    """The Shadow Volley leaves his hands: a fireball launch with a boom."""
    r = rng(seed)
    return finish(layer(0.6, [(blast(0.55, float(130 * r.uniform(0.9, 1.1)), 0.12, 0.12, seed, 0.3), 0, 1.0),
                              (whoosh(0.45, 1500, 380, seed + 5, 1.1, 0.2), 0, 0.8)]))


def barrage_bolt(seed=0):
    """One shot of the Soul Barrage: a deep cannon thump (twenty of them in a row make a drum roll of explosions)."""
    r = rng(seed)
    return finish(blast(0.26, float(150 * r.uniform(0.9, 1.15)), 0.06, 0.05, seed, 0.0), 0.9, 0.001, 0.02)


def acolyte_bolt(seed=0):
    r = rng(seed)
    return finish(layer(0.42, [(blast(0.4, float(190 * r.uniform(0.9, 1.1)), 0.08, 0.09, seed, 0.2), 0, 1.0),
                               (whoosh(0.3, 1200, 350, seed + 2, 1.0, 0.15), 0, 0.7)]))


def roar_phase2(seed=0):
    d = 1.9
    out = roar(d, 78, 0.5, 1)
    return finish(reverb(layer(d, [(out, 0, 1.0), (thump(90, 30, 1.0, 0.4), 0, 0.9)]), 1.4, 0.3))


def roar_phase3(seed=0):
    """The Last Stand: a deeper, harsher roar with a scream on top and a floor-shaking boom."""
    d = 2.1
    low = roar(d, 62, 1.0, 2)
    scream = roar(d, 190, 1.0, 3) * 0.35
    boom = thump(100, 24, 1.3, 0.5)
    return finish(reverb(layer(d, [(low, 0, 1.0), (scream, 0.05, 0.8), (boom, 0, 1.0), (hp(noise(0.3, 1) * perc(0.3, 0.001, 0.05), 1500), 0, 0.5)]),
                         1.7, 0.35))


def lich_intro(seed=0):
    d = 2.3
    t = times(d)
    rumble = lp(noise(d, 1, "brown"), 180) * swell(d, 0.7, 1.0) * 2.5
    sub = osc("sine", glide(36, 58, d)) * swell(d, 0.8, 1.0)
    voices = choir([73.4, 110.0, 146.8, 220.0], d, seed=2) * swell(d, 0.8, 1.0)
    bones = clatter(1.6, 14, 21, 600, 2000, 0.03, False)
    toll = bell(98, 2.0, (1.0, 2.0, 3.0, 4.2), 1.4)
    return finish(reverb(layer(d, [(rumble, 0, 1.0), (sub, 0, 0.9), (voices, 0.2, 0.6), (bones, 0.3, 0.6), (toll, 1.55, 0.7)]), 1.8, 0.35))


def lich_death(seed=0):
    d = 3.2
    fall = roar(2.0, 70, 0.9, 5) * ramp(2.0, 1.0, 0.0, 1.2)
    souls = choir([293.7, 440.0, 587.3, 880.0], 2.6, (800, 1200, 2800), 5.5, 0.01, 9) * swell(2.6, 0.55, 1.0)
    r = rng(8)
    sparks = layer(d, [(ping(float(r.uniform(1500, 5200)), 0.3, 0.12), float(r.uniform(0.4, 2.6)), float(r.uniform(0.1, 0.35))) for _ in range(28)])
    return finish(reverb(layer(d, [(fall, 0, 1.0), (thump(110, 22, 1.5, 0.6), 0, 1.0), (souls, 0.7, 0.5), (sparks, 0, 0.8)]), 2.4, 0.4), 0.92, 0.01, 0.05)


def phase3_stomp(seed=0):
    return finish(layer(0.4, [(thump(85, 28, 0.38, 0.12), 0, 1.0), (lp(noise(0.3, 4) * perc(0.3, 0.002, 0.05), 700), 0, 0.5)]))


# ----------------------------------------------------------------------------------------------------------
# skeletons: reusable in every area
# ----------------------------------------------------------------------------------------------------------

def monster_spawn(seed=0):
    r = rng(seed)
    dirt = lp(noise(0.55, seed) * swell(0.55, 0.3, 1.0), 700)
    bones = clatter(0.5, 5, seed + 30, 700, 1800, 0.03, False)
    return finish(layer(0.6, [(dirt, 0, 0.9), (bones, 0.15, 0.8), (thump(float(95 * r.uniform(0.9, 1.1)), 45, 0.4, 0.12), 0.12, 0.8)]))


def bone_hit(seed=0):
    r = rng(seed)
    return finish(layer(0.2, [(clack(float(r.uniform(1100, 2000)), 0.18, seed, 0.025), 0, 1.0),
                              (clack(float(r.uniform(1500, 2600)), 0.15, seed + 1, 0.02), 0.025, 0.6)]))


def bone_shatter(seed=0):
    r = rng(seed)
    return finish(layer(0.9, [(clatter(0.8, 12, seed + 5, 700, 2800, 0.025), 0, 1.0),
                              (thump(float(150 * r.uniform(0.9, 1.1)), 50, 0.3, 0.08), 0, 0.7),
                              (osc("sine", glide(500, 1100, 0.5)) * swell(0.5, 0.3, 1.0), 0.1, 0.08)]))


def brute_hit(seed=0):
    r = rng(seed)
    return finish(layer(0.3, [(thump(float(120 * r.uniform(0.9, 1.1)), 55, 0.28, 0.09), 0, 1.0),
                              (clack(float(r.uniform(700, 1100)), 0.2, seed, 0.04), 0, 0.9)]))


def brute_shatter(seed=0):
    r = rng(seed)
    return finish(reverb(layer(1.1, [(clatter(0.9, 16, seed + 7, 400, 1800, 0.035), 0, 1.0),
                                     (thump(float(80 * r.uniform(0.9, 1.1)), 30, 0.7, 0.22), 0, 1.0)]), 0.7, 0.2))


def skeleton_windup(seed=0):
    d = 0.32
    r = rng(4)
    rattle = layer(d, [(clack(float(r.uniform(900, 1700)), 0.08, int(r.integers(999)), 0.015), 0.03 * i, 0.5 + 0.03 * i) for i in range(9)])
    return finish(rattle, 0.85, 0.002, 0.01)


def sword_swish(seed=0):
    r = rng(seed)
    return finish(whoosh(0.24, float(1400 * r.uniform(0.9, 1.1)), float(4200 * r.uniform(0.9, 1.1)), seed, 0.9, 0.45), 0.9, 0.004, 0.02)


def brute_windup(seed=0):
    d = 0.7
    t = times(d)
    voice = drive(osc("saw", glide(62, 44, d)) * (1 + 0.5 * np.sin(2 * np.pi * 22 * t)), 3)
    return finish(sweep_bp(voice, glide(500, 900, d), 1.4) * swell(d, 0.6, 1.0) + lp(voice, 200) * 0.4 * swell(d, 0.6, 1.0), 0.9, 0.01, 0.03)


def brute_swipe(seed=0):
    return finish(layer(0.34, [(whoosh(0.34, 1100, 300, 6, 1.1, 0.35), 0, 1.0), (thump(110, 50, 0.3, 0.1), 0.1, 0.5)]))


def brute_slam(seed=0):
    d = 0.8
    return finish(reverb(layer(d, [(thump(100, 28, 0.7, 0.2), 0, 1.0), (lp(noise(0.4, 2) * perc(0.4, 0.001, 0.09), 2200), 0, 0.9),
                                   (clatter(0.4, 8, 5, 700, 2200, 0.03, False), 0.02, 0.6)]), 0.8, 0.2))


def bow_draw(seed=0):
    d = 0.45
    creak = sweep_bp(noise(d, 3, "pink"), glide(300, 1100, d), 0.5) * swell(d, 0.8, 1.0)
    ticks = layer(d, [(clack(2100, 0.05, 3, 0.01), 0.07 * i, 0.4) for i in range(1, 6)])
    return finish(layer(d, [(creak, 0, 1.0), (ticks, 0, 0.5)]), 0.85, 0.01, 0.03)


def acolyte_raise(seed=0):
    d = 0.95
    suck = osc("sine", glide(80, 320, d)) * ramp(d, 0.2, 1.0, 1.5) * 0.7
    rumble = lp(noise(d, 2, "brown"), 300) * swell(d, 0.7, 1.0) * 2.0
    return finish(reverb(layer(d, [(suck, 0, 1.0), (rumble, 0, 0.8), (clatter(0.5, 6, 4, 800, 2000, 0.03, False), 0.45, 0.7),
                                   (thump(90, 40, 0.3, 0.1), 0.6, 0.9)]), 0.9, 0.25))


# ----------------------------------------------------------------------------------------------------------
# the hero (stand-ins for the arena; the Player team can use or replace them)
# ----------------------------------------------------------------------------------------------------------

def player_swing(seed=0):
    r = rng(seed)
    return finish(whoosh(0.2, float(1800 * r.uniform(0.9, 1.1)), float(5200 * r.uniform(0.9, 1.1)), seed, 1.0, 0.4), 0.85, 0.004, 0.02)


def player_dash(seed=0):
    return finish(whoosh(0.26, 600, 3200, 2, 1.2, 0.7), 0.85, 0.004, 0.03)


def player_hurt(seed=0):
    r = rng(seed)
    grunt = drive(osc("saw", glide(float(300 * r.uniform(0.9, 1.1)), 120, 0.25)), 2.0) * perc(0.25, 0.004, 0.09)
    return finish(layer(0.3, [(sweep_bp(grunt, glide(900, 500, 0.25), 1.2), 0, 0.9), (thump(120, 55, 0.25, 0.07), 0, 0.9),
                              (lp(noise(0.12, seed) * perc(0.12, 0.001, 0.02), 2500), 0, 0.5)]))


# ----------------------------------------------------------------------------------------------------------
# stings
# ----------------------------------------------------------------------------------------------------------

def victory_sting(seed=0):
    d = 4.0
    parts = []
    for i, note in enumerate((50, 57, 62, 66, 69, 74)):                       # a rising D major arpeggio...
        f = s.midi_hz(note)
        tone = lp(osc("saw", f, 2.6) + 0.5 * osc("saw", f * 1.004, 2.6), 2600) * s.adsr(2.6, 0.04, 0.3, 0.6, 1.2)
        parts.append((tone, 0.14 * i, 0.3))
    for note in (50, 57, 62, 66, 69):                                          # ...then the whole chord, held
        f = s.midi_hz(note)
        tone = lp(osc("saw", f, 3.2) + 0.5 * osc("saw", f * 0.996, 3.2), 2200) * s.adsr(3.2, 0.06, 0.4, 0.7, 1.6)
        parts.append((tone, 0.9, 0.22))
    parts.append((bell(587.3, 3.0, (1.0, 2.0, 3.0, 4.2), 1.6), 0.9, 0.35))
    return finish(reverb(layer(d, parts), 2.0, 0.35), 0.9, 0.01, 0.1)


def defeat_sting(seed=0):
    d = 3.6
    fall = lp(osc("saw", glide(110, 34, 2.4)), 700) * swell(2.4, 0.1, 1.0)
    voices = choir([73.4, 77.8, 110.0], 3.0, (450, 800, 2300), 4.0, 0.01, 3) * swell(3.0, 0.3, 1.0)
    toll = bell(65.4, 3.4, (1.0, 1.5, 2.0, 2.74, 4.1), 1.8)
    return finish(reverb(layer(d, [(fall, 0, 0.9), (voices, 0.1, 0.5), (toll, 0, 0.9), (thump(80, 25, 0.8, 0.3), 0, 1.0)]), 2.2, 0.4), 0.9, 0.01, 0.1)


# ----------------------------------------------------------------------------------------------------------
# HEAVY versions: thuds, blasts and crashes instead of pings and zaps
# ----------------------------------------------------------------------------------------------------------

def explosion(seconds, size=1.0, seed=0):
    """A proper blast: a sub-bass boom, a wall of noise, a sharp crack and flying debris."""
    boom = thump(float(120 * (1.0 / size ** 0.3)), 24, seconds, 0.30 * size)
    sub = thump(58, 22, seconds, 0.45 * size)
    blast = lp(noise(seconds, seed) * perc(seconds, 0.002, 0.22 * size), 3200)
    crack = hp(noise(seconds, seed + 1) * perc(seconds, 0.0008, 0.035), 1500)
    debris = clatter(seconds, int(10 + 8 * size), seed + 2, 500, 3200, 0.02)
    return layer(seconds, [(boom, 0, 1.0), (sub, 0, 0.8), (blast, 0, 0.9), (crack, 0, 0.7), (debris, 0.03, 0.35)])


def growl_charge(seconds, low, high, seed=0, wobble=16.0):
    """A charging-up sound that is a snarling, building roar rather than a whining tone."""
    t = times(seconds)
    voice = drive(osc("saw", glide(low, high, seconds)) * (1 + 0.5 * np.sin(2 * np.pi * wobble * t)), 3.5)
    fire = sweep_lp(noise(seconds, seed), glide(300, 4200, seconds)) * ramp(seconds, 0.15, 1.0, 1.6)
    return layer(seconds, [(lp(voice, 1400) * ramp(seconds, 0.25, 1.0, 1.4), 0, 0.8), (fire, 0, 0.9)])


def volley_windup(seed=0):
    d = 0.9
    return finish(growl_charge(d, 55, 120, 11, 14.0), 0.9, 0.01, 0.01)


def barrage_windup(seed=0):
    """A drum roll that speeds up and swells: boom-boom-boomboomboom..."""
    d = 0.9
    t = 0.0
    hits = []
    while t < d - 0.05:
        u = t / d
        hits.append((thump(130 - 30 * u, 45, 0.16, 0.05), t, 0.45 + 0.55 * u))
        t += 0.17 - 0.13 * u
    rumble = lp(noise(d, 4, "brown"), 400) * ramp(d, 0.2, 1.0, 1.5) * 2.0
    return finish(layer(d, hits + [(rumble, 0, 0.8)]), 0.9, 0.005, 0.01)


def barrage_blast(seed=0):
    """The Soul Barrage opens up: one big cannon blast."""
    return finish(reverb(explosion(1.2, 1.0, 7), 1.0, 0.25))


def nova_blast(seed=0):
    """THE big one: a double boom, a wall of noise, bones flying everywhere."""
    d = 2.2
    return finish(reverb(layer(d, [(explosion(1.8, 1.8, 3), 0, 1.0), (explosion(1.2, 1.2, 9), 0.09, 0.7),
                                   (clatter(1.2, 30, 9, 900, 4200, 0.02), 0.05, 0.6)]), 1.8, 0.32))


def drain_windup(seed=0):
    d = 1.0
    hum = choir([82.4, 110.0], d, (400, 700, 2200), seed=1) * 0.5
    rumble = lp(noise(d, 3, "brown"), 300) * 2.0
    crackle = hp(noise(d, 5), 3500) * ramp(d, 0.0, 0.3, 2.0) * 0.4
    return finish(reverb(layer(d, [(hum * swell(d, 0.8), 0, 1.0), (rumble * swell(d, 0.7, 1.0), 0, 0.8), (crackle, 0, 0.6)]), 0.8, 0.2),
                  0.9, 0.01, 0.02)


def drain_heal(seed=0):
    """He drinks your life: a dark surge and a heavy gulp."""
    d = 0.55
    surge = sweep_bp(noise(d, 6), glide(200, 1200, d), 1.2) * swell(d, 0.7, 1.0)
    voice = lp(drive(osc("saw", glide(80, 190, d)), 3.0), 900) * swell(d, 0.7, 1.0)
    return finish(layer(d, [(surge, 0, 1.0), (voice, 0, 0.7), (thump(110, 45, 0.3, 0.1), 0.3, 0.9)]), 0.9, 0.01, 0.03)


def rain_windup(seed=0):
    d = 0.8
    hiss = hp(noise(d, 2), 2500) * ramp(d, 0.05, 0.6, 2.0) * 0.5
    rumble = lp(noise(d, 8, "brown"), 280) * swell(d, 0.9, 1.0) * 2.0
    return finish(layer(d, [(hiss, 0, 0.8), (rumble, 0, 1.0)]), 0.9, 0.01, 0.02)


def rain_burst(seed=0):
    """A small explosion where a soul-circle bursts."""
    r = rng(seed)
    return finish(layer(0.35, [(thump(float(150 * r.uniform(0.9, 1.15)), 38, 0.35, 0.08), 0, 1.0),
                               (lp(noise(0.25, seed) * perc(0.25, 0.001, 0.06), 2600), 0, 0.9),
                               (hp(noise(0.1, seed + 1) * perc(0.1, 0.0008, 0.015), 1800), 0, 0.5)]))


def grasp_root(seed=0):
    """Bony fingers clamp round your ankles: a heavy crunch and a thud."""
    return finish(layer(0.5, [(clatter(0.35, 9, 3, 400, 1400, 0.03, False), 0, 1.0), (thump(120, 45, 0.4, 0.12), 0, 1.0),
                              (lp(noise(0.15, 2) * perc(0.15, 0.001, 0.03), 1500), 0, 0.7)]))


def ward_deflect(seed=0):
    r = rng(seed)
    clang = bell(float(300 * r.uniform(0.95, 1.1)), 0.5, (1.0, 2.76, 5.4), 0.22)
    return finish(reverb(layer(0.55, [(clang, 0, 0.7), (thump(150, 50, 0.3, 0.07), 0, 1.0),
                                      (hp(noise(0.08, seed) * perc(0.08, 0.0005, 0.012), 1500), 0, 0.8)]), 0.4, 0.2))


def boss_hit_open(seed=0):
    """A hit while he is open (+50%): a heavier impact with a deep boom, so the player FEELS the bonus."""
    base = boss_hit(seed + 11)
    return finish(layer(0.55, [(base, 0, 1.0), (thump(85, 28, 0.5, 0.16), 0, 1.0), (bell(330, 0.4, (1.0, 2.0, 3.0), 0.2), 0, 0.3),
                               (hp(noise(0.12, seed + 5) * perc(0.12, 0.0008, 0.02), 1800), 0, 0.5)]))


def exhaust_open(seed=0):
    """A gong and a deep boom: 'HIT HIM NOW'."""
    d = 2.2
    gong = bell(196, d, (1.0, 1.5, 2.0, 2.74, 3.2, 4.1, 5.43), 1.5)
    strike = lp(noise(0.3, 1) * perc(0.3, 0.001, 0.04), 1800)
    return finish(reverb(layer(d, [(gong, 0, 0.9), (strike, 0, 0.8), (thump(90, 28, 0.9, 0.3), 0, 1.0)]), 1.6, 0.28))


def ward_up(seed=0):
    """The barrier slams shut: a deep thrum building up, then a boom."""
    d = 1.3
    thrum = choir([55.0, 82.4, 110.0], d, (400, 700, 2200), 4.0, 0.006, 2) * swell(d, 0.7, 1.0)
    suck = sweep_lp(noise(d, 3), glide(250, 3500, d)) * ramp(d, 0.1, 1.0, 1.8)
    return finish(reverb(layer(d, [(thrum, 0, 0.9), (suck, 0, 0.7), (explosion(0.7, 0.8, 5), 0.6, 0.9)]), 1.0, 0.25))


def teleport_out(seed=0):
    d = 0.5
    return finish(layer(d, [(whoosh(d, 3600, 260, 2, 1.1, 0.15), 0, 1.0), (thump(110, 36, 0.4, 0.1), 0, 0.9)]))


def teleport_in(seed=0):
    d = 0.55
    return finish(layer(d, [(whoosh(d, 260, 3600, 3, 1.1, 0.85), 0, 0.9), (explosion(0.35, 0.6, 4), 0.3, 0.9)]))


def acolyte_charge(seed=0):
    d = 0.75
    whisper = sweep_bp(noise(d, 5), glide(900, 2200, d), 0.7) * swell(d, 0.8, 1.0)
    hum = choir([110.0, 164.8], d, (450, 800, 2300), 4.5, 0.008, 6) * swell(d, 0.8, 1.0)
    return finish(layer(d, [(whisper, 0, 0.7), (hum, 0, 0.8)]), 0.85, 0.01, 0.03)


def acolyte_mend(seed=0):
    """A soft, warm swell of ghostly voices (no tinkling)."""
    d = 0.8
    return finish(reverb(choir([196.0, 246.9, 293.7], d, (700, 1100, 2500), 5.0, 0.007, 3) * swell(d, 0.45, 1.0), 0.8, 0.25))


def arrow_shoot(seed=0):
    """A bowstring snapping and an arrow tearing through the air: a dry thwack and a rush, no twang."""
    r = rng(seed)
    thwack = bp(noise(0.12, seed) * perc(0.12, 0.0006, 0.018), 350, 2600)
    rush = whoosh(0.28, float(3000 * r.uniform(0.9, 1.1)), 700, seed + 1, 0.9, 0.2)
    tok = clack(float(r.uniform(500, 800)), 0.12, seed + 2, 0.03)
    return finish(layer(0.3, [(thwack, 0, 1.0), (rush, 0.01, 0.8), (tok, 0, 0.7), (thump(180, 70, 0.12, 0.03), 0, 0.6)]))


# name -> (recipe, number of variants, loops?)
SFX = {
    "boss_hit": (boss_hit, 3), "boss_hit_open": (boss_hit_open, 3), "ward_deflect": (ward_deflect, 3),
    "ward_up": (ward_up, 1), "ward_break": (ward_break, 1), "ward_hum": (ward_hum, 1), "exhaust_open": (exhaust_open, 1),
    "volley_windup": (volley_windup, 1), "volley_fire": (volley_fire, 3), "volley_fire": (volley_fire, 3),
    "drain_windup": (drain_windup, 1), "drain_burst": (drain_burst, 3), "drain_heal": (drain_heal, 1),
    "rain_windup": (rain_windup, 1), "rain_burst": (rain_burst, 4),
    "grasp_windup": (grasp_windup, 1), "grasp_burst": (grasp_burst, 3), "grasp_root": (grasp_root, 1),
    "nova_windup": (nova_windup, 1), "nova_blast": (nova_blast, 1),
    "barrage_windup": (barrage_windup, 1), "barrage_blast": (barrage_blast, 1), "barrage_bolt": (barrage_bolt, 4), "barrage_bolt": (barrage_bolt, 4),
    "summon_windup": (summon_windup, 1), "summon_rise": (summon_rise, 1),
    "teleport_out": (teleport_out, 1), "teleport_in": (teleport_in, 1),
    "roar_phase2": (roar_phase2, 1), "roar_phase3": (roar_phase3, 1),
    "lich_intro": (lich_intro, 1), "lich_death": (lich_death, 1), "phase3_stomp": (phase3_stomp, 1),
    "monster_spawn": (monster_spawn, 3), "bone_hit": (bone_hit, 4), "bone_shatter": (bone_shatter, 3),
    "brute_hit": (brute_hit, 3), "brute_shatter": (brute_shatter, 2),
    "skeleton_windup": (skeleton_windup, 1), "sword_swish": (sword_swish, 3),
    "brute_windup": (brute_windup, 1), "brute_swipe": (brute_swipe, 1), "brute_slam": (brute_slam, 1),
    "bow_draw": (bow_draw, 1), "arrow_shoot": (arrow_shoot, 3),
    "acolyte_charge": (acolyte_charge, 1), "acolyte_mend": (acolyte_mend, 1), "acolyte_raise": (acolyte_raise, 1), "acolyte_bolt": (acolyte_bolt, 2), "acolyte_bolt": (acolyte_bolt, 2),
    "player_swing": (player_swing, 3), "player_dash": (player_dash, 1), "player_hurt": (player_hurt, 3),
    "victory_sting": (victory_sting, 1), "defeat_sting": (defeat_sting, 1),
}
