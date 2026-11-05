"""sfx.py - tiny procedural sound effects.

No audio files are needed: every sound is generated from simple waves when the
game starts. If the computer has no sound device, everything here quietly does
nothing and the game runs without audio. Background music is in music.py
(the tracks in audio/music/).
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
        self.muted = False
        self.volume = 1.0
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
            # hero skills
            "whirlwind": self._seq(T(500, 900, 0.12, 0.26, noise=0.8, decay=1.0),
                                   T(900, 400, 0.18, 0.26, noise=0.8, decay=2.5)),
            "shield_bash": self._seq(T(160, 80, 0.12, 0.45, "square", noise=0.4, decay=4.0)),
            "earthsplitter": T(70, 30, 0.9, 0.55, "saw", noise=0.45, decay=1.8, attack=0.02),
            "fireball": T(300, 160, 0.30, 0.32, "saw", noise=0.55, decay=2.0, attack=0.02),
            "frost_nova": self._seq(T(1300, 1700, 0.08, 0.20, decay=1.5), T(1700, 900, 0.30, 0.22, noise=0.3,
                                                                              decay=2.5)),
            "meteor": T(900, 120, 0.8, 0.35, "sine", noise=0.5, decay=0.8, attack=0.05),
            "boom": T(110, 40, 0.45, 0.55, "square", noise=0.6, decay=3.0),
            "arrow_volley": T(2200, 900, 0.10, 0.22, noise=0.7, decay=4.0),
            "piercing_shot": self._seq(T(700, 1400, 0.10, 0.22, decay=1.0), T(2400, 900, 0.14, 0.26, noise=0.6,
                                                                               decay=3.0)),
            "rain_of_arrows": T(2600, 1200, 0.5, 0.20, noise=0.85, decay=1.5),
            "no_mana": T(200, 160, 0.10, 0.18, "square", decay=3.0),
        }
        for name, samples in defs.items():
            self.sounds[name] = self._make(samples)

    # ---- public ------------------------------------------------------------
    def play(self, name: str):
        if not self.ok or self.muted:
            return
        snd = self.sounds.get(name)
        if snd is not None:
            snd.set_volume(self.volume)
            snd.play()

    def set_volume(self, volume):
        """0.0 - 1.0 for every sound effect (Settings: master x sfx)."""
        self.volume = max(0.0, min(1.0, float(volume)))
