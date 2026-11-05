"""
music.py - The three boss-fight music loops (DEV TOOL ONLY). Output: assets/audio/music/lich_p1.wav, _p2, _p3.

Same chords and the same brass theme in every phase, so the fight is ONE piece of music that keeps getting angrier.
The fight starts at full intensity (war drums, brass, a roaring choir) and each phase adds layers and speed.
Every loop is built on a musical grid (8 bars) and every filter / echo is circular, so it repeats with no click.

    Phase 1  "Frozen Sovereign"   96 BPM   war drums, a pounding bass, brass stabs, choir. Already a battle.
    Phase 2  "Hellfire Tyrant"   120 BPM   + a kick on every beat, sixteenth hats, racing arpeggio, higher choir.
    Phase 3  "Last Stand"        150 BPM   + double kicks, snare rolls, sixteenth bass, screaming choir, a riser.

Tweak the numbers in LOOPS or the patterns in the build_* functions, then run make_sounds.py.
"""
import numpy as np

from . import synth as s
from .recipes import bell, choir, clack, thump
from .synth import add_wrapped, bp, drive, hp, lp, noise, osc, perc, reverb, swell, times

BARS = 8
# chord per bar: Dm  Dm  Bb  A  |  Dm  Dm  Eb  A      (the Eb is the "something is wrong" note)
PROGRESSION = [(38, (62, 65, 69)), (38, (62, 65, 69)), (34, (58, 62, 65)), (33, (57, 61, 64)),
               (38, (62, 65, 69)), (38, (62, 65, 69)), (39, (63, 67, 70)), (33, (57, 61, 64))]
MOTIF = (74, 73, 69, 70)                  # D  C#  A  Bb : the Lich King's theme (falls like a bell tolling)

LOOPS = {"lich_p1": 96.0, "lich_p2": 120.0, "lich_p3": 150.0}


class Grid:
    def __init__(self, bpm):
        self.bpm = bpm
        self.beat = 60.0 / bpm
        self.bar = 4 * self.beat
        self.length = BARS * self.bar
        self.buf = np.zeros(s.n_samples(self.length))

    def when(self, bar, beat):
        return bar * self.bar + beat * self.beat

    def add(self, sound, bar, beat, gain=1.0):
        add_wrapped(self.buf, sound, self.when(bar, beat), gain)

    def loop_hz(self, freq):
        """Nudge a pitch so a whole number of waves fit in the loop (a held tone then wraps without a click)."""
        return round(freq * self.length) / self.length


# ----------------------------------------------------------------------------------------------------------
# instruments
# ----------------------------------------------------------------------------------------------------------

def kick(power=1.0):
    click = lp(noise(0.03, 1) * perc(0.03, 0.0005, 0.006), 4000)
    return s.layer(0.38, [(thump(150, 42, 0.38, 0.11 * power), 0, 1.0), (click, 0, 0.4)])


def taiko(length=0.6):
    body = thump(105, 48, length, 0.22)
    skin = lp(noise(0.08, 2) * perc(0.08, 0.001, 0.02), 1800)
    return s.layer(length, [(body, 0, 1.0), (skin, 0, 0.5)])


def snare():
    body = np.sin(2 * np.pi * 190 * times(0.2)) * perc(0.2, 0.001, 0.05)
    return s.layer(0.25, [(body, 0, 0.6), (bp(noise(0.25, 3) * perc(0.25, 0.001, 0.07), 900, 6000), 0, 0.9)])


def hat(open_=False):
    length = 0.22 if open_ else 0.06
    return hp(noise(length, 4) * perc(length, 0.0005, 0.08 if open_ else 0.015), 6500) * 0.6


def crash():
    return hp(noise(2.0, 6) * perc(2.0, 0.002, 0.6), 3000) * 0.6


def pluck(freq, length=0.3):
    t = times(length)
    tone = osc("saw", freq, length) + 0.5 * osc("sine", freq / 2, length)
    return lp(tone, 700 + 900 * freq / 100.0) * perc(length, 0.003, length * 0.35)


def brass(midis, length):
    out = np.zeros(s.n_samples(length))
    for m in midis:
        f = s.midi_hz(m)
        out += osc("saw", f, length) + osc("saw", f * 1.005, length)
    swelling = s.glide(500, 2600, length)
    return s.sweep_lp(out, swelling) * s.adsr(length, 0.05, 0.12, 0.7, 0.15) * 0.25


def pad(midis, length, seed=0, vowel=(700, 1100, 2500)):
    voices = choir([s.midi_hz(m) for m in midis], length, vowel, seed=seed)
    return voices * s.adsr(length, length * 0.35, 0.2, 0.8, length * 0.35)


def finish_loop(buf, wet=0.22, peak=0.9, push=2.6):
    """Reverb, then squash the loudest hits (push) so the whole track is LOUD and dense, not just its drum peaks."""
    out = reverb(buf, 2.2, wet, 3200, cyclic=True)
    out = hp(out, 28, 1, cyclic=True)
    out = np.tanh(out / (np.percentile(np.abs(out), 99) + 1e-9) * push * 0.6) / np.tanh(push * 0.6)
    return out / (np.max(np.abs(out)) + 1e-9) * peak


# ----------------------------------------------------------------------------------------------------------
# shared layers
# ----------------------------------------------------------------------------------------------------------

def add_drone(g, gain, brightness):
    t = times(g.length)
    f = g.loop_hz(73.4)
    sway = 1 + 0.25 * np.sin(2 * np.pi * (2.0 / g.length) * t)                    # slow breathing, 2 cycles per loop
    tone = osc("saw", f, g.length) + 0.6 * osc("saw", g.loop_hz(73.4 * 1.5), g.length) + osc("sine", f / 2, g.length)
    g.buf += lp(tone, brightness, 2, cyclic=True) * sway * gain


def add_pads(g, gain, vowel=(700, 1100, 2500), octave=0, per_bar=1):
    for bar, (_root, chord) in enumerate(PROGRESSION):
        sound = pad([m + octave for m in chord], g.bar * 1.25, seed=bar, vowel=vowel)
        g.add(sound, bar, 0, gain)


def add_motif(g, bars, gain, spacing=1.0, octave=0, length=1.4):
    for bar in bars:
        for i, midi in enumerate(MOTIF):
            g.add(bell(s.midi_hz(midi + octave), length, (1.0, 2.0, 3.0, 4.2), 0.9) * 0.6, bar, i * spacing, gain)


def add_wind(g, gain):
    n = lp(noise(g.length, 11, "pink"), 1400, 2, cyclic=True)
    t = times(g.length)
    g.buf += n * (0.6 + 0.4 * np.sin(2 * np.pi * (3.0 / g.length) * t)) * gain


# ----------------------------------------------------------------------------------------------------------
# the three loops: one arrangement, three levels of intensity
# ----------------------------------------------------------------------------------------------------------

def battle(level):
    """level 1, 2 or 3. Everything in level 1 is also in 2 and 3; each level adds to it."""
    g = Grid(list(LOOPS.values())[level - 1])
    add_drone(g, 0.45, 600 + 250 * level)
    add_wind(g, 0.25 if level == 1 else 0.12)
    add_pads(g, 0.55 + 0.05 * level, (700, 1100, 2500))                               # the roaring choir...
    if level >= 2:
        add_pads(g, 0.35, (800, 1300, 2800), octave=12)                               # ...gets a second, higher choir
    if level >= 3:
        add_pads(g, 0.4, (900, 1500, 3200), octave=19)                                # ...and then screams
    arp_cache = {}
    for bar, (root, chord) in enumerate(PROGRESSION):
        # ---- drums ----
        kicks = {1: (0, 2), 2: (0, 1, 2, 3, 3.5), 3: (0, 0.75, 1, 2, 2.75, 3, 3.5)}[level]
        for beat in kicks:
            g.add(kick(), bar, beat, 0.95 if beat == int(beat) else 0.6)
        for beat, gain in ((0, 1.0), (1.5, 0.7), (2, 0.85), (3, 0.9)):              # war drums under everything
            g.add(taiko(), bar, beat, gain * (0.8 if level == 3 else 1.0))
        for beat in (1, 3):
            g.add(snare(), bar, beat, 0.55 + 0.1 * level)
        if level == 3 and bar in (3, 7):                                             # a snare roll into the next section
            for i in range(8):
                g.add(snare(), bar, 3 + i * 0.125, 0.25 + 0.05 * i)
        steps = 2 if level == 1 else 4                                               # hats: eighths, then sixteenths
        for i in range(4 * steps):
            g.add(hat(i % 4 == 3 and level >= 2), bar, i / steps, 0.22 if i % 2 else 0.3)
        # ---- bass ----
        per_beat = 4 if level == 3 else 2
        for i in range(4 * per_beat):
            midi = root + (12 if i % per_beat == per_beat - 1 and i % 4 == 3 else 0)
            accent = i % per_beat == 0
            note = pluck(s.midi_hz(midi), 0.28 if level < 3 else 0.16)
            g.add(drive(note, 2.5) if level == 3 else note, bar, i / per_beat, 0.8 if accent else 0.5)
        # ---- brass: stabs on the beat, plus a held low chord ----
        stabs = {1: (0, 2.5), 2: (0, 1.5, 2.5, 3.5), 3: (0, 0.75, 1.5, 2.5, 3.5)}[level]
        for beat in stabs:
            g.add(brass(chord, g.beat * (1.4 if beat == 0 else 0.6)), bar, beat, 0.75)
        g.add(brass([m - 12 for m in chord], g.bar * 0.95), bar, 0, 0.35)
        # ---- the racing arpeggio (phase 2 and 3) ----
        if level >= 2:
            for i in range(16):
                note = chord[(i * 2 + (i // 4)) % 3] + 12
                if note not in arp_cache:
                    arp_cache[note] = lp(osc("saw", s.midi_hz(note - 12), 0.14), 1500) * perc(0.14, 0.002, 0.06)
                g.add(arp_cache[note], bar, i * 0.25, 0.3 if level == 2 else 0.4)
    # ---- crashes, the theme, the riser ----
    for bar in range(0, BARS, 4 if level == 1 else 2):
        g.add(crash(), bar, 0, 0.35 + 0.05 * level)
    for bar in (1, 3, 5, 7):                                                         # the theme: slow, heavy brass (no bells)
        for i, midi in enumerate(MOTIF):
            g.add(brass([midi - 12, midi - 24], g.beat * 0.95), bar, i, 0.45 + 0.05 * level)
    for bar in (1, 5) if level >= 2 else ():                                         # the theme again, in brass
        g.add(brass([MOTIF[0], MOTIF[0] - 12], g.beat * 1.5), bar, 0, 0.5)
    if level >= 2:
        rise = hp(noise(g.bar, 21) * swell(g.bar, 0.98, 2.0), 2500) * 0.5
        g.add(rise, 7, 0, 0.5 + 0.1 * level)
    return finish_loop(g.buf, 0.2 - 0.03 * level)


def build_p1():
    return battle(1)


def build_p2():
    return battle(2)


def build_p3():
    return battle(3)


TRACKS = {"lich_p1": build_p1, "lich_p2": build_p2, "lich_p3": build_p3}
