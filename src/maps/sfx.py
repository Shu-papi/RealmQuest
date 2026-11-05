"""sfx.py - tiny procedural sound effects.

No audio files are needed: every sound is generated from simple waves the first time the
game runs and cached (in the system temp folder), so later launches start instantly. If the
computer has no sound device, everything here quietly does nothing and the game runs
without audio. Background music is in music.py (the tracks in audio/music/).

    sfx = Sfx()
    sfx.play("hit")              # frequent sounds have a few pitch variants, picked at random
    sfx.play("step", vol=0.4)    # per-call volume on top of the Settings volume

A limiter keeps a burst of the same sound (a volley, Blade Ward cutting a crowd) from
stacking into a loud buzz: at most MAX_SAME copies at once, and not closer than MIN_GAP.
"""
from __future__ import annotations

import array
import hashlib
import math
import os
import random
import tempfile

import pygame

MAX_SAME = 3            # copies of one sound playing at the same time
MIN_GAP = 0.03          # s between two starts of the same sound
VARIANTS = 3            # pitch variants of frequent sounds
CACHE_VERSION = 2       # bump when the recipes change (the cache rebuilds itself)


def T(f0, f1, dur, vol=0.4, wave="sine", noise=0.0, decay=3.0, attack=0.004):
    """One tone: frequency glide f0 -> f1 over `dur` seconds."""
    return ("tone", f0, f1, dur, vol, wave, noise, decay, attack)


def SEQ(*parts):
    return ("seq",) + parts


def MIX(*parts):
    """Several tones at once (chords, a thump under a chime)."""
    return ("mix",) + parts


def ECHO(part, delay=0.07, gain=0.35, repeats=2):
    """A short room echo: fuller impacts."""
    return ("echo", part, delay, gain, repeats)


# name: (recipe, has pitch variants)
RECIPES = {
    "swing": (T(900, 300, 0.12, 0.30, "sine", noise=0.85, decay=4.0), True),
    "hit": (ECHO(T(220, 90, 0.10, 0.45, "square", noise=0.35, decay=5.0), 0.05, 0.25, 1), True),
    "crit": (ECHO(MIX(T(260, 80, 0.16, 0.45, "square", noise=0.4, decay=4.0),
                      T(1400, 700, 0.12, 0.20, decay=5.0)), 0.06, 0.3, 1), False),
    "hurt": (T(340, 110, 0.22, 0.40, "saw", decay=3.5), True),
    "shield_hit": (MIX(T(1300, 1100, 0.18, 0.22, decay=4.0), T(1950, 1650, 0.14, 0.12, decay=5.0)), True),
    "enemy_die": (ECHO(SEQ(T(420, 160, 0.10, 0.30, "square", noise=0.5, decay=3.0),
                           T(160, 60, 0.16, 0.30, noise=0.7, decay=3.5)), 0.06, 0.25, 1), True),
    "step": (T(140, 90, 0.05, 0.16, noise=0.85, decay=7.0), True),
    "potion": (SEQ(T(440, 520, 0.08, 0.30, decay=1.5), T(560, 660, 0.08, 0.30, decay=1.5),
                   T(760, 900, 0.14, 0.30, decay=2.5)), False),
    "pickup": (SEQ(T(660, 660, 0.06, 0.28, decay=2.0), T(990, 990, 0.10, 0.28, decay=3.0)), False),
    "dash": (T(1400, 400, 0.18, 0.28, "sine", noise=0.9, decay=3.0), False),
    "roar": (T(95, 55, 0.80, 0.50, "saw", noise=0.30, decay=1.6, attack=0.05), False),
    "clear": (SEQ(T(523, 523, 0.09, 0.30, decay=2.0), T(659, 659, 0.09, 0.30, decay=2.0),
                  T(784, 784, 0.20, 0.30, decay=3.0)), False),
    "victory": (SEQ(T(523, 523, 0.14, 0.32, decay=2.0), T(659, 659, 0.14, 0.32, decay=2.0),
                    T(784, 784, 0.14, 0.32, decay=2.0), T(1047, 1047, 0.50, 0.32, decay=2.5)), False),
    "level_up": (ECHO(SEQ(T(523, 523, 0.07, 0.28, decay=2.0), T(659, 659, 0.07, 0.28, decay=2.0),
                          T(784, 784, 0.07, 0.28, decay=2.0),
                          MIX(T(1047, 1047, 0.45, 0.26, decay=2.2), T(1319, 1319, 0.45, 0.16, decay=2.6))),
                     0.09, 0.3, 2), False),
    "death": (T(260, 50, 0.70, 0.45, "saw", decay=2.5), False),
    "blip": (T(520, 520, 0.035, 0.18, decay=2.0), False),
    # loot and gear
    "drop_rare": (MIX(T(1175, 1175, 0.30, 0.20, decay=3.0), T(1568, 1568, 0.30, 0.12, decay=3.5)), False),
    "drop_epic": (ECHO(SEQ(T(988, 988, 0.08, 0.22, decay=2.0),
                           MIX(T(1319, 1319, 0.40, 0.22, decay=2.5), T(1976, 1976, 0.40, 0.12, decay=3.0))),
                       0.1, 0.3, 2), False),
    "drop_legendary": (ECHO(SEQ(T(784, 784, 0.09, 0.24, decay=1.5), T(988, 988, 0.09, 0.24, decay=1.5),
                                T(1175, 1175, 0.09, 0.24, decay=1.5),
                                MIX(T(1568, 1568, 0.70, 0.24, decay=1.8), T(2093, 2093, 0.70, 0.14, decay=2.2),
                                    T(784, 784, 0.70, 0.16, decay=2.0))), 0.12, 0.35, 3), False),
    "equip": (SEQ(T(300, 220, 0.06, 0.30, "square", noise=0.5, decay=5.0),
                  T(1200, 1000, 0.10, 0.18, decay=4.0)), False),
    "sell": (SEQ(T(1319, 1319, 0.05, 0.22, decay=3.0), T(1760, 1760, 0.05, 0.22, decay=3.0),
                 T(2093, 2093, 0.12, 0.20, decay=3.0)), False),
    # menus
    "ui_move": (T(700, 760, 0.03, 0.14, decay=3.0), False),
    "ui_select": (SEQ(T(660, 660, 0.04, 0.20, decay=2.5), T(990, 990, 0.08, 0.20, decay=3.0)), False),
    "ui_back": (SEQ(T(660, 660, 0.04, 0.18, decay=2.5), T(440, 440, 0.08, 0.18, decay=3.0)), False),
    # hero skills
    "shield_bash": (ECHO(T(160, 80, 0.12, 0.45, "square", noise=0.4, decay=4.0), 0.06, 0.3, 1), False),
    "earthsplitter": (ECHO(T(70, 30, 0.9, 0.55, "saw", noise=0.45, decay=1.8, attack=0.02), 0.11, 0.35, 2), False),
    "fireball": (T(300, 160, 0.30, 0.32, "saw", noise=0.55, decay=2.0, attack=0.02), False),
    "meteor": (T(900, 120, 0.8, 0.35, "sine", noise=0.5, decay=0.8, attack=0.05), False),
    "boom": (ECHO(T(110, 40, 0.45, 0.55, "square", noise=0.6, decay=3.0), 0.1, 0.35, 2), False),
    "arrow_volley": (T(2200, 900, 0.10, 0.22, noise=0.7, decay=4.0), False),
    "piercing_shot": (SEQ(T(700, 1400, 0.10, 0.22, decay=1.0), T(2400, 900, 0.14, 0.26, noise=0.6, decay=3.0)),
                      False),
    "rain_of_arrows": (T(2600, 1200, 0.5, 0.20, noise=0.85, decay=1.5), False),
    "bolt": (T(620, 1250, 0.16, 0.24, "sine", noise=0.25, decay=3.0), True),
    "bow": (T(1900, 650, 0.09, 0.24, noise=0.6, decay=5.0), True),
    "blade_ward": (SEQ(T(500, 900, 0.12, 0.26, noise=0.8, decay=1.0), T(900, 1300, 0.16, 0.20, noise=0.5, decay=1.5)),
                   False),
    "arcane_barrier": (SEQ(T(500, 1000, 0.14, 0.22, decay=1.2), T(1000, 1500, 0.24, 0.18, decay=1.5)), False),
    "barrier_break": (T(1600, 300, 0.25, 0.25, noise=0.5, decay=3.0), False),
    "no_mana": (T(200, 160, 0.10, 0.18, "square", decay=3.0), False),
}

SFX_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
                       "assets", "sfx")
# Recorded sounds (assets/sfx/): name -> (file, gain). They replace a generated sound of the
# same name; a missing file just leaves the generated one.
FILE_SOUNDS = {
    "swing": ("knight_basic_attack.mp3", 1.0),
    "bow": ("archer_basic_attack.mp3", 0.6),
    "earthsplitter": ("knight_special_skill.mp3", 0.7),
    "meteor": ("meteor_special_attack_mage.mp3", 0.7),
    "fireball": ("fire ball.mp3", 0.6),
    "shaman_fireball": ("fire ball.mp3", 0.4),
    "shaman_barrier": ("cast barrier.mp3", 0.5),
    "boar_attack": ("boar_attack.mp3", 0.6),
    "slime_attack": ("slime_attack.mp3", 0.6),
    "slime_walk": ("slime_walk.mp3", 0.3),
    "king_swing": ("goblin_king_swing_axe.mp3", 0.7),
    "king_slam": ("goblin_king_axe_hit_ground.mp3", 0.8),
    "goblin_ambience": ("goblin_sound.mp3", 0.45),
}
LOOPED = {"goblin_ambience"}      # long beds: not trimmed, played with Sfx.ambience
TRIM_LEVEL = 0.03                 # quieter than this (of the peak) at the ends counts as silence
FADE_IN = 0.02                    # s kept before the sound starts
FADE_OUT = 0.04                   # s of fade at the cut end
AMBIENCE_FADE = 800               # ms


class Sfx:
    def __init__(self, cache_dir=None):
        self.ok = False
        self.sounds: dict[str, list] = {}       # name -> [Sound, ...] (variants)
        self.muted = False
        self.volume = 1.0
        self.last: dict[str, int] = {}           # name -> ticks of the last start (limiter)
        self.gain: dict[str, float] = {}         # recorded sounds: per-file loudness
        self.cache_dir = cache_dir or tempfile.gettempdir()
        self.bed = None                          # name of the ambience playing (or fading in)
        self.bed_channel = None
        try:
            if not pygame.mixer.get_init():
                pygame.mixer.init()
            fmt = pygame.mixer.get_init()
            if not fmt:
                return
            self.rate, size, self.channels = fmt
            if size != -16:                      # only plain signed 16-bit is supported
                return
            self._build()
            self._load_files()
            if pygame.mixer.get_num_channels() < 16:
                pygame.mixer.set_num_channels(16)
            pygame.mixer.set_reserved(1)         # channel 0: ambience, never stolen by effects
            self.bed_channel = pygame.mixer.Channel(0)
            self.ok = True
        except Exception:
            self.ok = False

    # ---- recorded sounds -------------------------------------------------------
    def _load_files(self):
        for name, (filename, gain) in FILE_SOUNDS.items():
            try:
                snd = pygame.mixer.Sound(os.path.join(SFX_DIR, filename))
                if name not in LOOPED:
                    snd = self._trim(snd)
            except Exception:
                continue                          # keep the generated sound
            self.sounds[name] = [snd]
            self.gain[name] = gain

    def _trim(self, snd):
        """Cut the silence at both ends (some files carry seconds of it) and fade the cut."""
        ch = self.channels
        a = array.array("h", snd.get_raw())
        frames = len(a) // ch
        if frames == 0:
            return snd
        peak = max(abs(v) for v in a)
        thr = max(1, int(peak * TRIM_LEVEL))
        first = next(i for i in range(len(a)) if abs(a[i]) > thr) // ch
        last = next(i for i in range(len(a) - 1, -1, -1) if abs(a[i]) > thr) // ch
        start = max(0, first - int(self.rate * FADE_IN))
        fade = int(self.rate * FADE_OUT)
        end = min(frames, last + fade)
        out = a[start * ch:end * ch]
        n = end - start
        for f in range(max(0, n - fade), n):
            k = (n - f) / fade
            for c in range(ch):
                out[f * ch + c] = int(out[f * ch + c] * k)
        return pygame.mixer.Sound(buffer=out.tobytes())

    # ---- synthesis -----------------------------------------------------------
    # Sounds are computed at half the mixer rate (plenty for these retro tones) and every
    # sample is written twice: half the work of the old generator.
    def _render(self, recipe, pitch, rnd):
        kind = recipe[0]
        if kind == "tone":
            return self._tone(recipe, pitch, rnd)
        if kind == "seq":
            out = []
            for part in recipe[1:]:
                out.extend(self._render(part, pitch, rnd))
            return out
        if kind == "mix":
            parts = [self._render(p, pitch, rnd) for p in recipe[1:]]
            out = [0.0] * max(len(p) for p in parts)
            for p in parts:
                for i, s in enumerate(p):
                    out[i] += s
            return out
        if kind == "echo":
            _k, part, delay, gain, repeats = recipe
            dry = self._render(part, pitch, rnd)
            step = int(self.gen_rate * delay)
            out = dry + [0.0] * (step * repeats)
            g = gain
            for r in range(1, repeats + 1):
                off = step * r
                for i, s in enumerate(dry):
                    out[off + i] += s * g
                g *= gain
            return out
        raise ValueError(kind)

    def _tone(self, recipe, pitch, rnd):
        _k, f0, f1, dur, vol, wave, noise, decay, attack = recipe
        rate = self.gen_rate
        n = max(1, int(rate * dur))
        out, phase = [], 0.0
        tau = 2 * math.pi
        sin, exp, uniform = math.sin, math.exp, rnd.uniform
        for i in range(n):
            t = i / n
            phase += tau * (f0 + (f1 - f0) * t) * pitch / rate
            if wave == "square":
                s = 1.0 if sin(phase) >= 0 else -1.0
            elif wave == "saw":
                s = 2.0 * ((phase / tau) % 1.0) - 1.0
            else:
                s = sin(phase)
            if noise:
                s = s * (1.0 - noise) + uniform(-1, 1) * noise
            env = min(1.0, (i / rate) / attack) * exp(-decay * t)
            out.append(s * env * vol)
        return out

    def _pack(self, samples):
        """Soft-clip, then 16-bit PCM bytes at the mixer rate (each sample twice) for every channel."""
        tanh = math.tanh
        reps = self.channels * 2
        vals = array.array("h")
        for s in samples:
            v = int(tanh(s * 1.1) * 30000)
            vals.extend((v,) * reps)
        return vals.tobytes()

    # ---- building (with a disk cache) -----------------------------------------
    def _cache_path(self):
        key = hashlib.md5(repr((CACHE_VERSION, sorted(RECIPES.items()), self.rate, self.channels,
                                VARIANTS)).encode()).hexdigest()[:16]
        return os.path.join(self.cache_dir, "realmquest_sfx_%s.bin" % key)

    def _build(self):
        self.gen_rate = self.rate // 2
        path = self._cache_path()
        data = self._read_cache(path)
        if data is None:
            data = {}
            for name, (recipe, varied) in RECIPES.items():
                pitches = (1.0, 0.94, 1.06)[:VARIANTS] if varied else (1.0,)
                data[name] = [self._pack(self._render(recipe, p, random.Random(11 + k)))
                              for k, p in enumerate(pitches)]
            self._write_cache(path, data)
        for name, variants in data.items():
            self.sounds[name] = [pygame.mixer.Sound(buffer=b) for b in variants]

    @staticmethod
    def _read_cache(path):
        try:
            with open(path, "rb") as f:
                blob = f.read()
        except OSError:
            return None
        data, pos = {}, 0
        try:
            while pos < len(blob):
                nlen = blob[pos]
                name = blob[pos + 1:pos + 1 + nlen].decode()
                pos += 1 + nlen
                count = blob[pos]
                pos += 1
                variants = []
                for _ in range(count):
                    size = int.from_bytes(blob[pos:pos + 4], "little")
                    variants.append(blob[pos + 4:pos + 4 + size])
                    pos += 4 + size
                data[name] = variants
        except (IndexError, UnicodeDecodeError):
            return None
        return data if set(data) == set(RECIPES) else None

    @staticmethod
    def _write_cache(path, data):
        out = bytearray()
        for name, variants in data.items():
            b = name.encode()
            out += bytes([len(b)]) + b + bytes([len(variants)])
            for v in variants:
                out += len(v).to_bytes(4, "little") + v
        try:
            tmp = path + ".tmp"
            with open(tmp, "wb") as f:
                f.write(out)
            os.replace(tmp, path)
        except OSError:
            pass                                      # no cache: next launch just builds again

    # ---- public ------------------------------------------------------------
    def play(self, name: str, vol: float = 1.0):
        if not self.ok or self.muted:
            return
        variants = self.sounds.get(name)
        if not variants:
            return
        now = pygame.time.get_ticks()
        if now - self.last.get(name, -10_000) < MIN_GAP * 1000:
            return
        if sum(v.get_num_channels() for v in variants) >= MAX_SAME:
            return
        self.last[name] = now
        snd = random.choice(variants)
        snd.set_volume(max(0.0, min(1.0, self.volume * vol * self.gain.get(name, 1.0))))
        snd.play()

    def ambience(self, name, on=True):
        """Loop a background sound (goblin chatter) quietly under the music; on=False fades it out.
        Call it every frame - it only acts when the wanted state changes."""
        if not self.ok:
            return
        want = name if on and not self.muted and name in self.sounds else None
        if want == self.bed:
            return
        if self.bed is not None:
            self.bed_channel.fadeout(AMBIENCE_FADE)
        self.bed = want
        if want is not None:
            self.bed_channel.play(self.sounds[want][0], loops=-1, fade_ms=AMBIENCE_FADE)
            self._bed_volume()

    def _bed_volume(self):
        if self.bed is not None:
            self.bed_channel.set_volume(max(0.0, min(1.0, self.volume * self.gain.get(self.bed, 1.0))))

    def set_volume(self, volume):
        """0.0 - 1.0 for every sound effect (Settings: master x sfx)."""
        self.volume = max(0.0, min(1.0, float(volume)))
        if self.ok:
            self._bed_volume()
