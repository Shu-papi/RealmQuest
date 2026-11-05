"""
manager.py - The AudioManager: loads the sounds and plays them without ever getting in the game's way.

You normally use the functions in audio/__init__.py instead of this class. What it takes care of:

    * NO SOUND CARD?  init() just returns False and every call becomes a silent no-op. The game never crashes.
    * SPAM: a boss that fires twenty bolts a second would turn into a buzz. Each sound has a cooldown, a voice limit
      and a priority (sounds.py); low-priority sounds are dropped first when the mixer is full.
    * VARIANTS: name__v1.wav, name__v2.wav ... one is picked at random (never the same one twice in a row).
    * STEREO: pass x (screen pixels) and the sound pans left / right.
    * DUCKING: roars, blasts and stings briefly turn the music down so they cut through.
    * MUSIC: tracks loop and CROSSFADE (phase 1 -> 2 -> 3 flows instead of cutting).
    * LOOPS: a sound that lasts while something is true (the Soul Ward's hum) fades in and out by itself.
    * VOLUME: follows the player's settings (master x music / sfx).
"""
import os
import random
import re
import time

from . import sounds
from .paths import MUSIC_DIR, SFX_DIR

SFX_CHANNELS = 32              # channels for one-shot sounds
RESERVED = 4                   # 0, 1 = music (two, for crossfades)   2, 3 = looping sounds
SCREEN_WIDTH = 960             # x = 0 is the far left, x = SCREEN_WIDTH the far right
MAX_PAN = 0.75                 # how hard a sound can lean to one side (1 = fully left / right)
BURST_WINDOW = 0.1             # seconds...
BURST_LIMIT = 6                # ...in which this many sounds may START before spam (priority 0) is dropped
DUCK_SPEED = 3.0               # how fast the music dips (per second)
RECOVER_SPEED = 1.5            # ...and how fast it comes back
CUT_FADE_MS = 70               # how long a sound cut short with max_seconds takes to fade out
VARIANT = re.compile(r"^(.+)__v(\d+)$")


def pan_gains(x, width=SCREEN_WIDTH):
    """(left, right) volumes for a sound at screen position x. None = centre."""
    if x is None:
        return 1.0, 1.0
    pan = max(-1.0, min(1.0, (x - width / 2.0) / (width / 2.0))) * MAX_PAN
    return min(1.0, 1.0 - pan), min(1.0, 1.0 + pan)


def clamp01(value):
    return max(0.0, min(1.0, value))


class _Fader:
    """A looping channel whose volume glides to a target (used by music and loops)."""

    def __init__(self, name, index, channel, gain):
        self.name = name
        self.index = index           # which mixer channel (0..3) it owns
        self.channel = channel
        self.gain = gain
        self.level = 0.0
        self.target = 1.0
        self.rate = 1.0              # level change per second
        self.pan = (1.0, 1.0)


class AudioManager:
    def __init__(self, pygame_module, sfx_dir=SFX_DIR, music_dir=MUSIC_DIR, clock=time.monotonic):
        self.pg = pygame_module
        self.sfx_dir = sfx_dir
        self.music_dir = music_dir
        self.clock = clock
        self.ready = False
        self.channel_started = {}
        self.muted = False
        self.sfx_volume = 1.0
        self.music_volume = 1.0
        self.sounds = {}               # name -> [Sound, ...]
        self.music_cache = {}          # track -> Sound
        self.rng = random.Random()
        self.last_variant = {}
        self.last_played = {}
        self.voices = {}               # name -> [Channel, ...]
        self.recent = []               # start times of the latest sounds (the spam limiter)
        self.channels = {}             # index -> mixer Channel (made once: Channel objects are not comparable)
        self.music_faders = {}         # track -> _Fader
        self.loop_faders = {}          # name -> _Fader
        self.duck = 1.0                # current music multiplier (1 = no ducking)
        self.duck_floor = 1.0
        self.duck_until = 0.0
        self.cuts = []                 # [stop time, channel, sound]: sounds to fade out early (max_seconds)
        self.last_tick = clock()
        self.current_music = None
        self.warnings = []

    # ------------------------------------------------------------------
    # start / stop
    # ------------------------------------------------------------------

    def init(self):
        """Open the sound device and load every sound. Returns True if there is sound, False if not."""
        mixer = self.pg.mixer
        try:
            if not mixer.get_init():
                mixer.pre_init(22050, -16, 2, 512)
                mixer.init()
            if not mixer.get_init():
                return False
            mixer.set_num_channels(SFX_CHANNELS + RESERVED)
            mixer.set_reserved(RESERVED)
            self.channels = {i: mixer.Channel(i) for i in range(SFX_CHANNELS + RESERVED)}
        except Exception as error:                                        # noqa: BLE001 (no device, bad driver...)
            self.warnings.append(f"no sound: {error}")
            return False
        self._load_sfx()
        self.ready = True
        return True

    def _load_sfx(self):
        if not os.path.isdir(self.sfx_dir):
            self.warnings.append(f"sound folder missing: {self.sfx_dir}")
            return
        for filename in sorted(os.listdir(self.sfx_dir)):
            if not filename.lower().endswith((".wav", ".ogg")):
                continue
            stem = filename.rsplit(".", 1)[0]
            match = VARIANT.match(stem)
            name = match.group(1) if match else stem
            try:
                self.sounds.setdefault(name, []).append(self.pg.mixer.Sound(os.path.join(self.sfx_dir, filename)))
            except Exception as error:                                    # noqa: BLE001 (a broken file: skip it)
                self.warnings.append(f"could not load {filename}: {error}")

    def shutdown(self):
        self.stop_all(fade=0.0)
        self.ready = False

    def has(self, name):
        return name in self.sounds

    # ------------------------------------------------------------------
    # volume
    # ------------------------------------------------------------------

    def set_volumes(self, sfx=None, music=None):
        """0..1 each (already multiplied by the master volume)."""
        if sfx is not None:
            self.sfx_volume = clamp01(sfx)
        if music is not None:
            self.music_volume = clamp01(music)
        self._apply_fader_volumes()

    def apply_settings(self, settings):
        """Read the player's volume sliders from a ui.settings_data.Settings."""
        self.set_volumes(settings.effective_volume("sfx"), settings.effective_volume("music"))

    def set_muted(self, muted):
        self.muted = bool(muted)
        if self.muted:
            for channel in self._one_shot_channels():
                channel.stop()
            self.voices = {}
        self._apply_fader_volumes()

    # ------------------------------------------------------------------
    # sound effects
    # ------------------------------------------------------------------

    def play(self, name, x=None, volume=1.0, max_seconds=None):
        """
        Play a sound once. Returns True if it started. Safe to call as often as you like.
        max_seconds: fade it out after this long (a charge-up sound that must end exactly when the attack fires).
        """
        if not self.ready or self.muted:
            return False
        variants = self.sounds.get(name)
        if not variants:
            return False
        now = self.clock()
        self.tick(now)
        info = sounds.spec(name)
        if now - self.last_played.get(name, -1e9) < info["cooldown"]:
            return False
        self.recent = [t for t in self.recent if now - t < BURST_WINDOW]
        if info["priority"] <= 0 and len(self.recent) >= BURST_LIMIT:
            return False

        active = [c for c in self.voices.get(name, []) if c.get_busy()]
        self.voices[name] = active
        if len(active) >= info["voices"]:
            if info["priority"] < 2:
                return False
            active.pop(0).stop()                                          # important: replace the oldest copy

        channel = self._free_channel(info["priority"] >= 2, now)
        if channel is None:
            return False
        sound = self._pick(name, variants)
        channel.play(sound)
        left, right = pan_gains(x)
        level = clamp01(info["gain"] * volume * self.sfx_volume)
        channel.set_volume(level * left, level * right)                   # (set AFTER play: play() resets it)
        active.append(channel)
        if max_seconds is not None and max_seconds > 0:
            self.cuts.append([now + max_seconds, channel, sound])
        self.last_played[name] = now
        self.recent.append(now)
        if info["duck"]:
            self._duck(*info["duck"], now)
        return True

    def _free_channel(self, steal, now):
        """A channel for a one-shot. NEVER the music or loop channels (pygame's own find_channel(force=True) can steal
        the longest-running channel, and that is always the music: it made the music cut out in busy fights)."""
        pool = self._one_shot_channels()
        for channel in pool:
            if not channel.get_busy():
                self.channel_started[id(channel)] = now
                return channel
        if not steal or not pool:
            return None
        oldest = min(pool, key=lambda c: self.channel_started.get(id(c), 0.0))
        oldest.stop()
        self.channel_started[id(oldest)] = now
        return oldest

    def _pick(self, name, variants):
        if len(variants) == 1:
            return variants[0]
        choices = [i for i in range(len(variants)) if i != self.last_variant.get(name)]
        index = self.rng.choice(choices)
        self.last_variant[name] = index
        return variants[index]

    def _duck(self, amount, seconds, now):
        self.duck_floor = min(self.duck_floor if now < self.duck_until else 1.0, 1.0 - clamp01(amount))
        self.duck_until = max(self.duck_until, now + seconds)

    # ------------------------------------------------------------------
    # music
    # ------------------------------------------------------------------

    def _music_sound(self, track):
        if track not in self.music_cache:
            path = os.path.join(self.music_dir, track + ".wav")
            try:
                self.music_cache[track] = self.pg.mixer.Sound(path)
            except Exception as error:                                    # noqa: BLE001
                self.warnings.append(f"could not load music {track}: {error}")
                self.music_cache[track] = None
        return self.music_cache[track]

    def play_music(self, track, fade=1.5):
        """Start a looping track, crossfading from whatever is playing. Asking for the same track again does nothing."""
        if not self.ready:
            return False
        now = self.clock()
        self.tick(now)
        if track == self.current_music and track in self.music_faders:
            return True
        sound = self._music_sound(track)
        if sound is None:
            return False
        for other in self.music_faders.values():
            other.target = 0.0
            other.rate = 1.0 / max(fade, 0.05)
        used = {f.index for f in self.music_faders.values()}
        free = [i for i in (0, 1) if i not in used]
        if free:
            index = free[0]
        else:                                                             # both busy: reuse the quieter one
            quietest = min(self.music_faders.values(), key=lambda f: f.level)
            index = quietest.index
            quietest.channel.stop()
            self.music_faders.pop(quietest.name, None)
        channel = self.channels[index]
        fader = _Fader(track, index, channel, sounds.MUSIC.get(track, sounds.DEFAULT_MUSIC_GAIN))
        fader.rate = 1.0 / max(fade, 0.05)
        channel.play(sound, loops=-1)
        channel.set_volume(0.0)
        self.music_faders[track] = fader
        self.current_music = track
        self._apply_fader_volumes()
        return True

    def stop_music(self, fade=1.5):
        self.current_music = None
        for fader in self.music_faders.values():
            fader.target = 0.0
            fader.rate = 1.0 / max(fade, 0.05)
        if fade <= 0:
            for fader in self.music_faders.values():
                fader.level = 0.0
            self.tick()

    # ------------------------------------------------------------------
    # looping sounds
    # ------------------------------------------------------------------

    def loop(self, name, on, x=None, fade=0.4):
        """Keep a looping sound running while `on` is True (call it every frame; it only acts when `on` changes)."""
        if not self.ready:
            return
        self.tick()
        fader = self.loop_faders.get(name)
        if on:
            if fader is not None:
                if fader.target <= 0:                                     # it was fading out: bring it back
                    fader.target = 1.0
                    fader.rate = 1.0 / max(fade, 0.05)
                return
            variants = self.sounds.get(name)
            if not variants:
                return
            used = {f.index for f in self.loop_faders.values()}
            free = [i for i in (2, 3) if i not in used]
            if not free:
                return
            channel = self.channels[free[0]]
            fader = _Fader(name, free[0], channel, sounds.LOOPS.get(name, 0.3))
            fader.rate = 1.0 / max(fade, 0.05)
            fader.pan = pan_gains(x)
            channel.play(variants[0], loops=-1)
            channel.set_volume(0.0)
            self.loop_faders[name] = fader
            self._apply_fader_volumes()
        elif fader is not None and fader.target > 0:
            fader.target = 0.0
            fader.rate = 1.0 / max(fade, 0.05)

    def stop_all(self, fade=0.3):
        """Silence everything (leaving the boss room, restarting). Music and loops fade; one-shots stop."""
        self.stop_music(fade)
        for fader in self.loop_faders.values():
            fader.target = 0.0
            fader.rate = 1.0 / max(fade, 0.05)
        for channel in self._one_shot_channels():
            channel.stop()
        self.voices = {}
        self.cuts = []
        if fade <= 0:
            for fader in list(self.loop_faders.values()):
                fader.level = 0.0
            self.tick()

    # ------------------------------------------------------------------
    # every frame
    # ------------------------------------------------------------------

    def update(self, dt=None):
        """Optional: call once per frame. (Fades also advance whenever a sound is played.)"""
        self.tick()

    def tick(self, now=None):
        if not self.ready:
            return
        now = self.clock() if now is None else now
        dt = max(0.0, min(2.0, now - self.last_tick))
        self.last_tick = now
        for cut in [c for c in self.cuts if now >= c[0]]:                  # charge-ups that must end now
            self.cuts.remove(cut)
            if cut[1].get_busy() and cut[1].get_sound() is cut[2]:
                cut[1].fadeout(CUT_FADE_MS)
        # ducking: dip fast, recover slowly
        want = self.duck_floor if now < self.duck_until else 1.0
        if want < self.duck:
            self.duck = max(want, self.duck - DUCK_SPEED * dt)
        else:
            self.duck = min(want, self.duck + RECOVER_SPEED * dt)
        if now >= self.duck_until and self.duck >= 1.0:
            self.duck_floor = 1.0
        for table in (self.music_faders, self.loop_faders):
            for name in list(table):
                fader = table[name]
                if fader.level < fader.target:
                    fader.level = min(fader.target, fader.level + fader.rate * dt)
                elif fader.level > fader.target:
                    fader.level = max(fader.target, fader.level - fader.rate * dt)
                if fader.level <= 0.0 and fader.target <= 0.0:
                    fader.channel.stop()
                    del table[name]
        self._apply_fader_volumes()

    def _apply_fader_volumes(self):
        silent = 0.0 if self.muted else 1.0
        for fader in self.music_faders.values():
            level = clamp01(fader.gain * fader.level * self.music_volume * self.duck * silent)
            fader.channel.set_volume(level)
        for fader in self.loop_faders.values():
            level = clamp01(fader.gain * fader.level * self.sfx_volume * silent)
            fader.channel.set_volume(level * fader.pan[0], level * fader.pan[1])

    # ------------------------------------------------------------------
    # helpers
    # ------------------------------------------------------------------

    def _one_shot_channels(self):
        return [self.channels[i] for i in range(RESERVED, SFX_CHANNELS + RESERVED) if i in self.channels]
