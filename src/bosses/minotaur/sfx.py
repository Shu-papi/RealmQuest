"""
minotaur/sfx.py - Sound effects for the Minotaur fight.

The sounds are plain WAV files in  assets/bosses/minotaur/sfx/  (made by tools/build_minotaur_sfx.py, and
you can swap any of them for your own recording: keep the file name, or use name_1.wav, name_2.wav...
for a sound with variants; .ogg works too). Nothing here is required:

    * no pygame mixer (no sound card, a test run, a stubbed pygame) -> every call quietly does nothing
    * a missing or broken file                                      -> that one sound is skipped
    * boss.sfx = None, or boss.sfx = SoundBoard(enabled=False)      -> the boss is silent

so the game never crashes because of audio.

USE
    board = get_soundboard()              # one shared board (the Minotaur and the arena both use it)
    board.play("slam")                    # volume 1.0, centred
    board.play("step", volume=0.5, x=200) # quieter, panned to where x=200 is on a 960-wide screen
    board.toggle_mute()                   # M key in the arena

The names in SOUND_NAMES are the ones the fight uses. VOLUMES balances them against each other
(a footstep should not be as loud as a slam), and `board.volume` is the master volume.
"""
import os
import random

import pygame

from ..paths import asset_dir

SFX_DIR = os.path.join(asset_dir("minotaur"), "sfx")

SOUND_NAMES = (
    # the player
    "swing", "roll", "hit", "hit_heavy", "block", "hurt", "player_down", "victory", "defeat",
    # the Minotaur's body
    "step", "stomp", "snort", "roar", "roar_big", "death", "thud",
    # his skills
    "charge_windup", "charge", "crash", "stun",
    "slam_windup", "slam", "cast_windup", "fireball",
    "rain_windup", "rock", "leap_windup", "leap",
)

# Loudness of each sound relative to the others (1.0 = as recorded). Tune the mix here.
VOLUMES = {
    "swing": 0.55, "roll": 0.5, "hit": 0.8, "hit_heavy": 0.95, "block": 0.65, "hurt": 0.9,
    "player_down": 0.9, "victory": 0.7, "defeat": 0.7,
    "step": 0.45, "stomp": 0.75, "snort": 0.55, "roar": 0.85, "roar_big": 1.0, "death": 0.95, "thud": 0.9,
    "charge_windup": 0.7, "charge": 0.8, "crash": 1.0, "stun": 0.7,
    "slam_windup": 0.7, "slam": 1.0, "cast_windup": 0.6, "fireball": 0.8,
    "rain_windup": 0.65, "rock": 0.6, "leap_windup": 0.65, "leap": 0.7,
}

SCREEN_WIDTH = 960          # the arena window; x positions are panned across this
PAN_WIDTH = 0.5             # 0 = everything centred, 1 = a sound at the screen edge is only in one ear
CHANNELS = 24               # pygame mixes 8 sounds by default; a rock volley plus a roar needs more
EXTENSIONS = (".wav", ".ogg")


class SoundBoard:
    """Loads the Minotaur's sounds once and plays them. Safe to use with no audio at all."""

    def __init__(self, enabled=True, volume=0.8, directory=None, seed=None):
        self.enabled = enabled
        self.volume = volume                  # master volume, 0..1
        self.muted = False
        self.directory = directory or SFX_DIR
        self.sounds = {}                      # name -> [pygame.mixer.Sound, ...] (several = variants)
        self._last_variant = {}
        self._loaded = False
        self._rng = random.Random(seed)       # its own random, so sounds never change the fight

    # -- the mixer ------------------------------------------------------------------

    @staticmethod
    def _mixer_ready():
        mixer = getattr(pygame, "mixer", None)
        try:
            return mixer is not None and mixer.get_init() is not None
        except Exception:                      # a stubbed or half-working pygame
            return False

    @property
    def available(self):
        """True when sounds can really play (enabled, mixer running, at least one file loaded)."""
        return bool(self.enabled and self._mixer_ready() and self.sounds)

    def _files_for(self, name):
        """name.wav, or name_1.wav, name_2.wav, ... (and the same with .ogg), in the order found."""
        found = []
        for ext in EXTENSIONS:
            single = os.path.join(self.directory, name + ext)
            if os.path.isfile(single):
                found.append(single)
        for i in range(1, 10):
            for ext in EXTENSIONS:
                numbered = os.path.join(self.directory, f"{name}_{i}{ext}")
                if os.path.isfile(numbered):
                    found.append(numbered)
        return found

    def load(self):
        """Reads every sound file. Safe to call again (it only loads once), or before the mixer exists
        (it then tries again at the next call)."""
        if self._loaded or not self.enabled or not self._mixer_ready():
            return self
        try:
            if pygame.mixer.get_num_channels() < CHANNELS:
                pygame.mixer.set_num_channels(CHANNELS)
        except Exception:
            pass
        for name in SOUND_NAMES:
            loaded = []
            for path in self._files_for(name):
                try:
                    loaded.append(pygame.mixer.Sound(path))
                except Exception:              # pygame.error or an unreadable file: skip just this one
                    continue
            if loaded:
                self.sounds[name] = loaded
        self._loaded = True
        return self

    # -- playing ------------------------------------------------------------------

    def play(self, name, volume=1.0, x=None):
        """
        Plays one sound. `volume` multiplies the sound's own loudness; `x` (screen pixels) pans it
        left or right. Returns the pygame Channel, or None when nothing was played.
        """
        if not self.enabled or self.muted or not self._mixer_ready():
            return None
        if not self._loaded:
            self.load()
        variants = self.sounds.get(name)
        if not variants:
            return None
        index = self._rng.randrange(len(variants))
        if len(variants) > 1 and index == self._last_variant.get(name):
            index = (index + 1 + self._rng.randrange(len(variants) - 1)) % len(variants)   # never the same twice
        self._last_variant[name] = index

        level = max(0.0, min(1.0, self.volume * VOLUMES.get(name, 1.0) * volume))
        left = right = level
        if x is not None:
            pan = max(-1.0, min(1.0, (x - SCREEN_WIDTH / 2) / (SCREEN_WIDTH / 2))) * PAN_WIDTH
            left = level * (1.0 - max(0.0, pan))
            right = level * (1.0 - max(0.0, -pan))
        try:
            channel = variants[index].play()
            if channel is not None:
                channel.set_volume(left, right)
            return channel
        except Exception:
            return None

    # -- controls -----------------------------------------------------------------

    def toggle_mute(self):
        """Mutes or unmutes. Returns True when the sound is now muted."""
        self.muted = not self.muted
        if self.muted:
            self.stop_all()
        return self.muted

    def set_paused(self, paused):
        """Freezes (or resumes) every sound that is playing: used by the arena's P key."""
        try:
            if self._mixer_ready():
                (pygame.mixer.pause if paused else pygame.mixer.unpause)()
        except Exception:
            pass

    def stop_all(self):
        try:
            if self._mixer_ready():
                pygame.mixer.stop()
        except Exception:
            pass


_shared = None


def get_soundboard():
    """The one board shared by the Minotaur and the arena, so the files are only loaded once."""
    global _shared
    if _shared is None:
        _shared = SoundBoard()
    return _shared
