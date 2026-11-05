"""
build_minotaur_sfx.py - makes every Minotaur sound effect from scratch (no recordings, no extra packages).

    python tools/build_minotaur_sfx.py            # writes assets/bosses/minotaur/sfx/*.wav
    python tools/build_minotaur_sfx.py --list     # just prints the sound names

Only the Python standard library is used. Each sound is built from a few simple parts (noise, sine and saw
waves, filters, volume envelopes), so you can tune one by editing its function below and re-running this
script. The game plays plain WAV files, so you can ALSO swap any file for your own recording: keep the same
file name (for example `slam.wav`, or `step_1.wav` / `step_2.wav` / `step_3.wav` for a sound with variants).
Re-running this script overwrites hand-made files, so only run it to start over.

Format: 16-bit mono, 22050 Hz (chunky on purpose, it suits the pixel art). The runtime list of names is
`SOUND_NAMES` in src/bosses/minotaur/sfx.py; the test suite checks that every name has a file.
"""
import math
import os
import random
import struct
import sys
import wave

RATE = 22050
OUT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                       "assets", "bosses", "minotaur", "sfx")


# ---------------------------------------------------------------------------
# building blocks (a "sound" is just a list of floats between -1 and 1)
# ---------------------------------------------------------------------------

def n_samples(seconds):
    return max(1, int(seconds * RATE))


def noise(seconds, rng):
    return [rng.uniform(-1.0, 1.0) for _ in range(n_samples(seconds))]


def curve(points, n):
    """A value that moves through (time 0..1, value) points in a straight line. Used for pitch and filter sweeps."""
    out = []
    for i in range(n):
        t = i / max(1, n - 1)
        for (t0, v0), (t1, v1) in zip(points, points[1:]):
            if t <= t1:
                k = 0.0 if t1 == t0 else (t - t0) / (t1 - t0)
                out.append(v0 + (v1 - v0) * k)
                break
        else:
            out.append(points[-1][1])
    return out


def lowpass(samples, cutoff):
    """One-pole low-pass. `cutoff` is a number in Hz or a list with one Hz value per sample (a sweep)."""
    out, y = [], 0.0
    for i, x in enumerate(samples):
        fc = cutoff[i] if isinstance(cutoff, list) else cutoff
        a = 1.0 - math.exp(-math.tau * fc / RATE)
        y += a * (x - y)
        out.append(y)
    return out


def highpass(samples, cutoff):
    low = lowpass(samples, cutoff)
    return [x - l for x, l in zip(samples, low)]


def bandpass(samples, low_hz, high_hz):
    """Rough band: keep what lies between two cutoffs (each a number or a sweep list)."""
    return highpass(lowpass(samples, high_hz), low_hz)


def tone(freq, seconds, shape="sine", vibrato=0.0, vibrato_hz=6.0):
    """A wave. `freq` is a number or a list of Hz values per sample (a pitch sweep). Phase is kept continuous."""
    n = n_samples(seconds)
    out, phase = [], 0.0
    for i in range(n):
        f = freq[i] if isinstance(freq, list) else freq
        f *= 1.0 + vibrato * math.sin(math.tau * vibrato_hz * i / RATE)
        phase += f / RATE
        p = phase % 1.0
        if shape == "sine":
            out.append(math.sin(math.tau * p))
        elif shape == "saw":
            out.append(2.0 * p - 1.0)
        elif shape == "square":
            out.append(1.0 if p < 0.5 else -1.0)
        elif shape == "triangle":
            out.append(4.0 * abs(p - 0.5) - 1.0)
        else:
            raise ValueError(shape)
    return out


def envelope(samples, points):
    """Multiply by a volume curve given as (time 0..1, volume) points."""
    env = curve(points, len(samples))
    return [s * e for s, e in zip(samples, env)]


def decay(samples, seconds, power=1.0, attack=0.002):
    """Quick attack, then an exponential die-away that reaches ~0 after `seconds`."""
    out = []
    a = max(1, int(attack * RATE))
    for i, s in enumerate(samples):
        t = i / RATE
        k = min(1.0, i / a) * math.exp(-5.0 * (t / seconds) ** power) if seconds > 0 else 0.0
        out.append(s * k)
    return out


def mix(*layers, gains=None):
    n = max(len(layer) for layer in layers)
    gains = gains or [1.0] * len(layers)
    out = [0.0] * n
    for layer, g in zip(layers, gains):
        for i, s in enumerate(layer):
            out[i] += s * g
    return out


def delay(samples, seconds):
    return [0.0] * n_samples(seconds) + list(samples)


def pad(samples, seconds):
    return list(samples) + [0.0] * n_samples(seconds)


def am(samples, rate_hz, depth, rng_phase=0.0):
    """Tremolo / growl: wobble the volume."""
    return [s * (1.0 - depth + depth * (0.5 + 0.5 * math.sin(math.tau * rate_hz * i / RATE + rng_phase)))
            for i, s in enumerate(samples)]


def drive(samples, amount):
    """Soft distortion: makes a plain wave sound angry and thick."""
    return [math.tanh(s * amount) for s in samples]


def clicks(seconds, count, rng, power=1.0, strength=1.0, high=1800):
    """Little crunchy ticks scattered in time (pebbles, embers, rubble). power > 1 bunches them early."""
    out = [0.0] * n_samples(seconds)
    for _ in range(count):
        pos = int((rng.random() ** power) * (len(out) - 40))
        size = rng.randint(8, 28)
        amp = rng.uniform(0.3, 1.0) * strength
        for j in range(size):
            out[pos + j] += rng.uniform(-1, 1) * amp * math.exp(-4.0 * j / size)
    return highpass(out, high)


def boom_tone(f_start, f_end, length, die_away, rich=1.3, knock=0.7):
    """A falling-pitch boom. A plain low sine is mostly below 100 Hz, which laptop and phone speakers barely
    play, so two helpers are mixed in: a distorted copy (adds higher harmonics) and a very short 'knock' an
    octave or so higher. Small speakers play those, so the hit still thumps; big speakers still get the bass."""
    n = n_samples(length)
    base = tone(curve([(0, f_start), (1, f_end)], n), length)
    boom = decay(mix(base, drive(base, 6.0), gains=[1.0, rich]), die_away)
    top = decay(tone(curve([(0, f_start * 2.6), (1, f_start * 1.3)], n), length), 0.045)
    return mix(boom, top, gains=[1.0, knock])


def fade_edges(samples, fade_in=0.0015, fade_out=0.012):
    """Ramp the first and last few milliseconds so a sound never clicks when it starts or stops."""
    n = len(samples)
    a, b = int(fade_in * RATE), int(fade_out * RATE)
    out = list(samples)
    for i in range(min(a, n)):
        out[i] *= i / a
    for i in range(min(b, n)):
        out[n - 1 - i] *= i / b
    return out


def finish(samples, peak=0.9):
    """Remove DC offset, normalise to `peak`, soft-limit and fade the edges."""
    mean = sum(samples) / len(samples)
    samples = [s - mean for s in samples]
    top = max(abs(s) for s in samples) or 1.0
    samples = [s / top * peak for s in samples]
    return fade_edges(samples)


def write_wav(path, samples):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    frames = b"".join(struct.pack("<h", int(max(-1.0, min(1.0, s)) * 32767)) for s in samples)
    with wave.open(path, "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(RATE)
        wav.writeframes(frames)


# ---------------------------------------------------------------------------
# the player
# ---------------------------------------------------------------------------

def swing(rng):
    """Sword whoosh: noise whose brightness sweeps up and back down."""
    n = n_samples(0.24)
    air = bandpass(noise(0.24, rng), 500, curve([(0, 1200), (0.45, 5200), (1, 1500)], n))
    air = envelope(air, [(0, 0), (0.35, 1), (0.7, 0.6), (1, 0)])
    return finish(air, 0.7)


def roll(rng):
    """Dodge roll: a soft cloth-and-dust scuff."""
    n = n_samples(0.30)
    scuff = lowpass(noise(0.30, rng), curve([(0, 3000), (1, 700)], n))
    scuff = envelope(scuff, [(0, 0), (0.12, 1), (0.5, 0.55), (1, 0)])
    thump = boom_tone(130, 70, 0.30, 0.12)
    return finish(mix(scuff, thump, gains=[1.0, 0.35]), 0.6)


def hit(rng, heavy=False):
    """Sword hits the Minotaur: a thump, a crunch and a metallic tick. `heavy` is the stunned (1.5x) hit."""
    length = 0.42 if heavy else 0.28
    n = n_samples(length)
    thump = boom_tone(190 if heavy else 160, 55, length, 0.16 if heavy else 0.11)
    crunch = decay(highpass(noise(length, rng), 900), 0.07 if heavy else 0.05)
    ring = mix(*[decay(tone(f, length), 0.10 + 0.02 * i) for i, f in enumerate((1180, 1830, 2640))],
               gains=[0.5, 0.35, 0.25])
    parts = [thump, crunch, ring]
    gains = [1.0, 0.8, 0.5 if not heavy else 0.8]
    if heavy:                                              # stun bonus: a bright "ding" on top
        parts.append(decay(tone(1760, length), 0.30))
        gains.append(0.4)
    return finish(mix(*parts, gains=gains), 0.9)


def block(rng):
    """Blocked (he is invulnerable): a dull metal clang."""
    n = n_samples(0.30)
    clang = mix(*[decay(tone(f, 0.30, "triangle"), 0.12 + 0.03 * (4 - i)) for i, f in enumerate((820, 1330, 1980, 2740))],
                gains=[0.6, 0.5, 0.35, 0.25])
    tick = decay(highpass(noise(0.30, rng), 2500), 0.02)
    return finish(mix(clang, tick, gains=[1.0, 0.5]), 0.7)


def hurt(rng):
    """The player takes a hit: a punch plus a short falling 'oof'."""
    n = n_samples(0.38)
    punch = boom_tone(150, 50, 0.38, 0.10)
    oof = lowpass(tone(curve([(0, 260), (1, 120)], n), 0.38, "saw", vibrato=0.03, vibrato_hz=28), 900)
    oof = envelope(oof, [(0, 0), (0.1, 1), (0.5, 0.5), (1, 0)])
    grit = decay(lowpass(noise(0.38, rng), 2500), 0.08)
    return finish(mix(punch, oof, grit, gains=[1.0, 0.6, 0.6]), 0.9)


def player_down(rng):
    """The player falls: a long sad drop and a thud."""
    n = n_samples(1.1)
    drop = lowpass(tone(curve([(0, 300), (1, 60)], n), 1.1, "saw", vibrato=0.02, vibrato_hz=5), 700)
    drop = envelope(drop, [(0, 0), (0.05, 1), (0.8, 0.5), (1, 0)])
    thud = delay(boom_tone(110, 40, 0.5, 0.2), 0.45)
    return finish(mix(drop, thud, gains=[0.8, 1.0]), 0.9)


def victory(rng):
    """The Minotaur is dead: a short rising fanfare."""
    notes = [(262, 0.0), (330, 0.14), (392, 0.28), (523, 0.42)]
    parts = []
    for freq, start in notes:
        body = mix(tone(freq, 0.9, "square"), tone(freq * 2, 0.9, "triangle"), gains=[0.35, 0.5])
        parts.append(delay(decay(lowpass(body, 3500), 0.5 if start < 0.42 else 0.9), start))
    return finish(mix(*parts), 0.8)


def defeat(rng):
    """The player is beaten: three slow falling notes."""
    parts = []
    for freq, start in [(330, 0.0), (277, 0.3), (220, 0.6)]:
        body = mix(tone(freq, 1.0, "triangle"), tone(freq * 0.5, 1.0, "sine"), gains=[0.6, 0.6])
        parts.append(delay(decay(lowpass(body, 2200), 0.55 if start < 0.6 else 0.8), start))
    return finish(mix(*parts), 0.8)


# ---------------------------------------------------------------------------
# the Minotaur: body
# ---------------------------------------------------------------------------

def step(rng, pitch=1.0):
    """One heavy footstep: a thump with a little gravel."""
    n = n_samples(0.2)
    thump = boom_tone(95 * pitch, 48 * pitch, 0.2, 0.09, knock=1.2)
    grit = decay(lowpass(noise(0.2, rng), 1400), 0.05)
    return finish(mix(thump, grit, gains=[1.0, 0.55]), 0.85)


def stomp(rng):
    """A taunting stomp: a bigger step with a rumble behind it."""
    n = n_samples(0.45)
    boom = boom_tone(90, 38, 0.45, 0.20, knock=1.2)
    rumble = decay(lowpass(noise(0.45, rng), 300), 0.22)
    grit = decay(lowpass(noise(0.45, rng), 2200), 0.06)
    return finish(mix(boom, rumble, grit, gains=[1.0, 0.7, 0.45]), 0.95)


def snort(rng):
    """Two angry snorts through the nose."""
    def puff(seed_rng):
        n = n_samples(0.16)
        body = bandpass(noise(0.16, seed_rng), curve([(0, 500), (1, 300)], n), curve([(0, 2600), (1, 1400)], n))
        return envelope(body, [(0, 0), (0.15, 1), (0.6, 0.5), (1, 0)])
    first = puff(rng)
    second = delay(puff(rng), 0.19)
    low = lowpass(tone(70, 0.4, "saw"), 200)
    low = envelope(low, [(0, 0), (0.1, 1), (0.5, 0.2), (1, 0)])
    return finish(mix(first, second, low, gains=[1.0, 0.9, 0.4]), 0.8)


def growl(length, start_hz, end_hz, rng, wobble=30.0, grit=0.5, peak=0.9):
    """A throaty growl: a low buzzing wave, wobbled in volume, run through a moving 'mouth' filter."""
    n = n_samples(length)
    pitch = curve([(0, start_hz), (0.35, start_hz * 1.12), (1, end_hz)], n)
    voice = tone(pitch, length, "saw", vibrato=0.015, vibrato_hz=7)
    voice = am(voice, wobble, 0.55)
    breath = lowpass(noise(length, rng), 1500)
    body = mix(voice, breath, gains=[1.0, grit])
    body = drive(body, 2.2)
    mouth = curve([(0, 500), (0.3, 1600), (0.7, 900), (1, 400)], n)
    body = lowpass(body, mouth)
    return body


def roar(rng):
    """The taunt roar: about a second long."""
    body = growl(1.0, 95, 60, rng, wobble=28)
    body = envelope(body, [(0, 0), (0.08, 1), (0.6, 0.9), (1, 0)])
    return finish(body, 0.9)


def roar_big(rng):
    """The giant roar (the intro and the phase change): lower, longer, with rock-shaking bass under it."""
    length = 1.7
    body = growl(length, 80, 45, rng, wobble=24, grit=0.7)
    body = envelope(body, [(0, 0), (0.1, 1), (0.7, 1), (1, 0)])
    sub = tone(curve([(0, 55), (1, 32)], n_samples(length)), length)
    sub = envelope(sub, [(0, 0), (0.15, 1), (0.8, 0.8), (1, 0)])
    rubble = envelope(clicks(length, 40, rng, power=1.0, strength=0.4, high=900), [(0, 0.2), (0.3, 1), (1, 0)])
    return finish(mix(body, sub, rubble, gains=[1.0, 0.8, 0.3]), 0.95)


def death(rng):
    """He dies: a long groan that sinks and fades. (The thud when he hits the floor is its own sound.)"""
    length = 1.25
    body = growl(length, 85, 28, rng, wobble=11, grit=0.4)
    body = envelope(body, [(0, 0), (0.06, 1), (0.6, 0.7), (1, 0)])
    return finish(body, 0.9)


def thud(rng):
    """He hits the floor."""
    n = n_samples(0.7)
    boom = boom_tone(80, 30, 0.7, 0.3, knock=1.3)
    dust = decay(lowpass(noise(0.7, rng), 500), 0.25)
    return finish(mix(boom, dust, gains=[1.0, 0.6]), 0.95)


# ---------------------------------------------------------------------------
# the Minotaur: skills
# ---------------------------------------------------------------------------

def charge_windup(rng):
    """Lowers his head and paws the floor: scrapes and a snort."""
    length = 0.75
    scrapes = []
    for k in range(5):
        n = n_samples(0.12)
        scrape = lowpass(noise(0.12, rng), curve([(0, 3000), (1, 900)], n))
        scrape = envelope(scrape, [(0, 0), (0.15, 1), (1, 0)])
        thump = boom_tone(80, 60, 0.12, 0.05)
        scrapes.append(delay(mix(scrape, thump, gains=[1.0, 0.7]), 0.13 * k + 0.06))
    return finish(mix(*scrapes, snort(rng), gains=[1.0] * 5 + [0.6]), 0.9)


def charge(rng):
    """He sprints: a fast galloping rumble that builds and then fades."""
    length = 0.9
    parts = []
    t = 0.0
    gap = 0.13
    while t < length - 0.12:
        parts.append(delay(step(rng, pitch=0.9), t))
        t += gap
        gap = max(0.085, gap * 0.93)
    gallop = mix(*parts)
    gallop = envelope(gallop, [(0, 0.5), (0.4, 1), (1, 0.3)])
    n = n_samples(length)
    wind = lowpass(noise(length, rng), curve([(0, 400), (0.5, 1800), (1, 600)], n))
    wind = envelope(wind, [(0, 0), (0.4, 1), (1, 0)])
    return finish(mix(gallop, wind, gains=[1.0, 0.45]), 0.9)


def crash(rng):
    """He smashes into the wall: a giant boom and falling stones."""
    n = n_samples(0.9)
    boom = boom_tone(100, 30, 0.9, 0.35)
    smash = decay(lowpass(noise(0.9, rng), 3500), 0.12)
    stones = envelope(clicks(0.9, 45, rng, power=1.8, strength=0.7), [(0, 1), (1, 0)])
    return finish(mix(boom, smash, stones, gains=[1.0, 0.9, 0.6]), 0.95)


def stun(rng):
    """Dizzy: a woozy wobbling 'bonk' and three tiny star chimes."""
    n = n_samples(0.9)
    bonk = lowpass(tone(curve([(0, 420), (1, 160)], n), 0.9, "triangle", vibrato=0.05, vibrato_hz=9), 1500)
    bonk = envelope(bonk, [(0, 0), (0.03, 1), (0.5, 0.4), (1, 0)])
    chimes = [delay(decay(tone(f, 0.5), 0.22), 0.12 + 0.17 * i) for i, f in enumerate((1568, 1976, 2349))]
    return finish(mix(bonk, *chimes, gains=[1.0, 0.25, 0.25, 0.25]), 0.8)


def slam_windup(rng):
    """Fists go up: a rising strain that stops just before the hit."""
    length = 1.0
    n = n_samples(length)
    strain = lowpass(tone(curve([(0, 48), (1, 115)], n), length, "saw", vibrato=0.02, vibrato_hz=8), 400)
    swell = lowpass(noise(length, rng), curve([(0, 200), (1, 1400)], n))
    out = mix(strain, swell, gains=[1.0, 0.55])
    out = envelope(out, [(0, 0), (0.85, 1), (0.97, 0.9), (1, 0)])
    return finish(out, 0.8)


def slam(rng):
    """The slam lands: the loudest boom, with a crackle of rubble."""
    n = n_samples(1.0)
    boom = boom_tone(115, 28, 1.0, 0.40)
    sub = decay(tone(curve([(0, 55), (1, 24)], n), 1.0), 0.50)
    crack = decay(lowpass(noise(1.0, rng), 4000), 0.10)
    rubble = envelope(clicks(1.0, 60, rng, power=1.6, strength=0.6), [(0, 1), (1, 0)])
    return finish(mix(boom, sub, crack, rubble, gains=[1.0, 0.8, 0.9, 0.5]), 0.95)


def cast_windup(rng):
    """Embers gather: crackling that speeds up and a rising shimmer."""
    length = 0.85
    n = n_samples(length)
    crackle = clicks(length, 70, rng, power=0.6, strength=0.8, high=1500)
    crackle = envelope(crackle, [(0, 0.3), (1, 1)])
    shimmer = tone(curve([(0, 280), (1, 880)], n), length, "triangle", vibrato=0.02, vibrato_hz=14)
    shimmer = lowpass(envelope(shimmer, [(0, 0), (0.9, 0.8), (1, 0)]), 2500)
    hum = lowpass(noise(length, rng), curve([(0, 300), (1, 1200)], n))
    hum = envelope(hum, [(0, 0), (1, 0.7)])
    return finish(mix(crackle, shimmer, hum, gains=[0.9, 0.5, 0.5]), 0.8)


def fireball(rng):
    """The ring of fireballs bursts out: a big whoosh and a fiery 'fwoomp'."""
    length = 0.8
    n = n_samples(length)
    whoosh = bandpass(noise(length, rng), 300, curve([(0, 5000), (1, 800)], n))
    whoosh = envelope(whoosh, [(0, 0), (0.1, 1), (0.5, 0.6), (1, 0)])
    fwoomp = boom_tone(220, 70, length, 0.25, rich=0.4)
    sparks = decay(clicks(length, 40, rng, power=1.4, strength=0.8, high=2000), 0.5)
    return finish(mix(whoosh, fwoomp, sparks, gains=[1.0, 0.9, 0.5]), 0.9)


def rain_windup(rng):
    """He calls the rocks: the ceiling groans and pebbles trickle."""
    length = 1.0
    n = n_samples(length)
    rumble = lowpass(noise(length, rng), curve([(0, 150), (0.6, 400), (1, 250)], n))
    rumble = am(rumble, 14, 0.5)
    rumble = envelope(rumble, [(0, 0), (0.5, 1), (0.9, 1), (1, 0)])
    pebbles = envelope(clicks(length, 26, rng, power=1.0, strength=0.5, high=1400), [(0, 0.2), (0.8, 1), (1, 0.4)])
    groan = lowpass(tone(curve([(0, 62), (1, 54)], n), length, "saw"), 260)
    groan = envelope(groan, [(0, 0), (0.4, 0.7), (1, 0)])
    return finish(mix(rumble, pebbles, groan, gains=[1.0, 0.5, 0.5]), 0.8)


def rock(rng, pitch=1.0):
    """A boulder lands: a stony thump and a spray of chips."""
    n = n_samples(0.5)
    thump = boom_tone(105 * pitch, 42 * pitch, 0.5, 0.17, knock=1.1)
    crunch = decay(lowpass(noise(0.5, rng), 2800 * pitch), 0.09)
    chips = envelope(clicks(0.5, 22, rng, power=1.5, strength=0.7, high=1800), [(0, 1), (1, 0)])
    return finish(mix(thump, crunch, chips, gains=[1.0, 0.8, 0.5]), 0.9)


def leap_windup(rng):
    """Crouches: a short strained grunt and a leathery creak."""
    n = n_samples(0.5)
    grunt = lowpass(tone(curve([(0, 70), (1, 105)], n), 0.5, "saw", vibrato=0.03, vibrato_hz=12), 450)
    grunt = envelope(grunt, [(0, 0), (0.3, 1), (0.85, 0.7), (1, 0)])
    creak = bandpass(noise(0.5, rng), 600, 1600)
    creak = envelope(am(creak, 40, 0.8), [(0, 0), (0.4, 0.8), (1, 0)])
    return finish(mix(grunt, creak, gains=[1.0, 0.35]), 0.8)


def leap(rng):
    """The jump: a push-off thump and a whoosh that rises."""
    length = 0.6
    n = n_samples(length)
    push = boom_tone(130, 60, length, 0.10)
    air = bandpass(noise(length, rng), 300, curve([(0, 800), (0.6, 4200), (1, 2500)], n))
    air = envelope(air, [(0, 0), (0.25, 1), (0.7, 0.7), (1, 0)])
    return finish(mix(push, air, gains=[0.9, 0.9]), 0.85)


# ---------------------------------------------------------------------------
# the list
# ---------------------------------------------------------------------------
# name -> list of recipes. A name with several recipes is a sound with variants: the game picks one at random
# so repeated footsteps and rocks do not sound machine-gunned. Files are `name.wav`, or `name_1.wav`,
# `name_2.wav`... when there is more than one.

RECIPES = {
    "swing": [swing],
    "roll": [roll],
    "hit": [lambda r: hit(r), lambda r: hit(r)],
    "hit_heavy": [lambda r: hit(r, heavy=True)],
    "block": [block],
    "hurt": [hurt],
    "player_down": [player_down],
    "victory": [victory],
    "defeat": [defeat],
    "step": [lambda r: step(r, 1.0), lambda r: step(r, 0.9), lambda r: step(r, 1.1)],
    "stomp": [stomp],
    "snort": [snort],
    "roar": [roar],
    "roar_big": [roar_big],
    "death": [death],
    "thud": [thud],
    "charge_windup": [charge_windup],
    "charge": [charge],
    "crash": [crash],
    "stun": [stun],
    "slam_windup": [slam_windup],
    "slam": [slam],
    "cast_windup": [cast_windup],
    "fireball": [fireball],
    "rain_windup": [rain_windup],
    "rock": [lambda r: rock(r, 1.0), lambda r: rock(r, 0.85), lambda r: rock(r, 1.15)],
    "leap_windup": [leap_windup],
    "leap": [leap],
}


def file_names(name):
    """The WAV file names for one sound name."""
    count = len(RECIPES[name])
    return [name + ".wav"] if count == 1 else [f"{name}_{i + 1}.wav" for i in range(count)]


def build(out_dir=OUT_DIR, only=None):
    written = []
    for name, recipes in RECIPES.items():
        if only and name not in only:
            continue
        for index, (recipe, fname) in enumerate(zip(recipes, file_names(name))):
            rng = random.Random(f"minotaur-{name}-{index}")      # same sound every run
            path = os.path.join(out_dir, fname)
            write_wav(path, recipe(rng))
            written.append(path)
    return written


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    if "--list" in argv:
        for name in RECIPES:
            print(name, len(RECIPES[name]))
        return
    only = [a for a in argv if not a.startswith("-")] or None
    for path in build(only=only):
        print("wrote", os.path.relpath(path))


if __name__ == "__main__":
    main()
