"""
testing.py - Helpers for tests: listen to what the game WOULD play without any sound device.

    from audio.testing import Recorder
    rec = Recorder()
    audio.set_manager(rec)
    ... run the fight ...
    assert "ward_break" in rec.names()
    audio.set_manager(None)
"""


class Recorder:
    """Looks like an AudioManager but only writes down what it was asked to do."""
    ready = True
    muted = False

    def __init__(self):
        self.events = []             # ("play", name, x, max_seconds) / ("music", track) / ("stop_music",) / ("loop", name, on) ...
        self.loops = {}

    def play(self, name, x=None, volume=1.0, max_seconds=None):
        self.events.append(("play", name, x, max_seconds))
        return True

    def play_music(self, track, fade=1.5):
        self.events.append(("music", track))
        return True

    def stop_music(self, fade=1.5):
        self.events.append(("stop_music",))

    def loop(self, name, on, x=None, fade=0.4):
        if self.loops.get(name) != bool(on):
            self.events.append(("loop", name, bool(on)))
        self.loops[name] = bool(on)

    def stop_all(self, fade=0.3):
        self.events.append(("stop_all",))
        self.loops = {}

    def update(self, dt=None):
        pass

    def apply_settings(self, settings):
        pass

    def set_muted(self, muted):
        self.muted = bool(muted)

    def shutdown(self):
        pass

    # ---- questions for tests ----

    def names(self):
        """Every sound effect played so far, in order."""
        return [e[1] for e in self.events if e[0] == "play"]

    def count(self, name):
        return self.names().count(name)

    def tracks(self):
        return [e[1] for e in self.events if e[0] == "music"]

    def clear(self):
        self.events = []
