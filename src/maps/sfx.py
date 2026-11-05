"""sfx.py - tiny procedural sound effects and ambient music.

No audio files are needed: every sound is generated from simple waves when the
game starts. If the computer has no sound device, everything here quietly does
nothing and the game runs without audio.
"""
from __future__ import annotations

import array
import math
import random

import pygame


class Sfx:
    def __init__(self):
        self.ok = False
        self.sounds: dict[str, pygame.mixer.Sound] = {}
        self.music_cache: dict[int, pygame.mixer.Sound] = {}
        self.music_chan = None
        self.muted = False
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
            self.ok = True
        except Exception:
            self.ok = False

    # ---- wave helpers ------------------------------------------------------
    def _tone(self, f0, f1, dur, vol=0.4, wave="sine", noise=0.0, decay=3.0, attack=0.004):
        n = max(1, int(self.rate * dur))
        rnd = random.Random(11)
        out, phase = [], 0.0
        for i in range(n):
            t = i / n
            phase += 2 * math.pi * (f0 + (f1 - f0) * t) / self.rate
            if wave == "square":
                s = 1.0 if math.sin(phase) >= 0 else -1.0
            elif wave == "saw":
                s = 2.0 * ((phase / (2 * math.pi)) % 1.0) - 1.0
            else:
                s = math.sin(phase)
            if noise:
                s = s * (1.0 - noise) + rnd.uniform(-1, 1) * noise
            env = min(1.0, (i / self.rate) / attack) * math.exp(-decay * t)
            out.append(s * env * vol)
        return out

    def _seq(self, *parts):
        out = []
        for p in parts:
            out.extend(p)
        return out

    def _make(self, samples):
        buf = array.array("h")
        for s in samples:
            v = int(max(-1.0, min(1.0, s)) * 32767)
            for _ in range(self.channels):
                buf.append(v)
        return pygame.mixer.Sound(buffer=buf.tobytes())

    def _build(self):
        T = self._tone
        defs = {
            "swing": T(900, 300, 0.12, 0.30, "sine", noise=0.85, decay=4.0),
            "hit": T(220, 90, 0.10, 0.45, "square", noise=0.35, decay=5.0),
            "hurt": T(340, 110, 0.22, 0.40, "saw", decay=3.5),
            "potion": self._seq(T(440, 520, 0.08, 0.30, decay=1.5),
                                T(560, 660, 0.08, 0.30, decay=1.5),
                                T(760, 900, 0.14, 0.30, decay=2.5)),
            "pickup": self._seq(T(660, 660, 0.06, 0.28, decay=2.0),
                                T(990, 990, 0.10, 0.28, decay=3.0)),
            "dash": T(1400, 400, 0.18, 0.28, "sine", noise=0.9, decay=3.0),
            "roar": T(95, 55, 0.80, 0.50, "saw", noise=0.30, decay=1.6, attack=0.05),
            "clear": self._seq(T(523, 523, 0.09, 0.30, decay=2.0),
                               T(659, 659, 0.09, 0.30, decay=2.0),
                               T(784, 784, 0.20, 0.30, decay=3.0)),
            "victory": self._seq(T(523, 523, 0.14, 0.32, decay=2.0),
                                 T(659, 659, 0.14, 0.32, decay=2.0),
                                 T(784, 784, 0.14, 0.32, decay=2.0),
                                 T(1047, 1047, 0.50, 0.32, decay=2.5)),
            "death": T(260, 50, 0.70, 0.45, "saw", decay=2.5),
            "blip": T(520, 520, 0.035, 0.18, decay=2.0),
        }
        for name, samples in defs.items():
            self.sounds[name] = self._make(samples)

    # ---- public ------------------------------------------------------------
    def play(self, name: str):
        if not self.ok or self.muted:
            return
        snd = self.sounds.get(name)
        if snd is not None:
            snd.play()

    def _drone(self, f1, f2, dur=4.0):
        n = int(self.rate * dur)
        out = []
        for i in range(n):
            t = i / self.rate
            trem = 0.75 + 0.25 * math.sin(2 * math.pi * 0.5 * t)        # whole cycles = loops cleanly
            s = (0.50 * math.sin(2 * math.pi * f1 * t)
                 + 0.35 * math.sin(2 * math.pi * f2 * t)
                 + 0.15 * math.sin(2 * math.pi * f1 * 2 * t))
            out.append(s * trem * 0.5)
        return out

    def music(self, dungeon: int | None):
        """Looping ambient drone, a different pitch for each dungeon (None stops it)."""
        if not self.ok:
            return
        try:
            if self.music_chan is not None:
                self.music_chan.stop()
                self.music_chan = None
            if dungeon is None or self.muted:
                return
            snd = self.music_cache.get(dungeon)
            if snd is None:
                f1, f2 = {1: (110.0, 165.0), 2: (82.5, 123.75), 3: (65.0, 97.5)}.get(dungeon, (110.0, 165.0))
                snd = self._make(self._drone(f1, f2))
                snd.set_volume(0.22)
                self.music_cache[dungeon] = snd
            self.music_chan = snd.play(loops=-1)
        except Exception:
            pass
