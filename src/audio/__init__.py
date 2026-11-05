"""
RealmQuest audio package (Pygame): sound effects, looping sounds and music for the whole game.

    import audio                                   # or: from src import audio

    audio.init(settings)          ONCE at start-up. settings = ui.settings_data.Settings (optional: sets the volumes).
                                  Returns False if there is no sound device. That is fine: everything below then
                                  silently does nothing, so you never have to check.

    audio.play("bone_hit", x=monster.x)            one sound effect (x = screen pixels: pans left / right; optional;
                                                   max_seconds=0.5 fades it out early, e.g. a charge-up)
    audio.music("lich_p2")                         start / crossfade to a music loop
    audio.stop_music(fade=2.0)
    audio.loop("ward_hum", True)                   a sound that lasts while something is true (call every frame)
    audio.stop_all()                               leaving the area / restarting: everything fades out
    audio.update()                                 optional, once per frame (fades also advance on every play())
    audio.apply_settings(settings)                 the player moved a volume slider (Settings.apply_audio does this)
    audio.set_muted(True)

THE BOSSES AND MONSTERS ALREADY CALL audio.play(...) at the right moments, so the only thing the game has to do
is call audio.init() once. Until then every call is a no-op (so tests, tools and previews stay silent).

Files:   assets/audio/sfx/*.wav   assets/audio/music/*.wav      (made by src/audio/dev/make_sounds.py)
Mixing:  src/audio/sounds.py      (how loud each sound is, how often it may repeat, what it ducks)
See src/audio/README.md.
"""
from .manager import AudioManager
from .sounds import LOOPS, MUSIC, SOUNDS

_manager = None


def init(settings=None, pygame_module=None):
    """Open the sound device and load the sounds. Returns True if sound is available."""
    global _manager
    if _manager is not None and getattr(_manager, "ready", False):
        if settings is not None:
            _manager.apply_settings(settings)
        return True
    if pygame_module is None:
        try:
            import pygame as pygame_module                          # noqa: PLC0415
        except ImportError:
            return False
    manager = AudioManager(pygame_module)
    if not manager.init():
        return False
    _manager = manager
    if settings is not None:
        manager.apply_settings(settings)
    return True


def set_manager(manager):
    """Swap in a different manager (tests use audio.testing.Recorder). None goes back to silence."""
    global _manager
    _manager = manager


def get_manager():
    return _manager


def is_ready():
    return _manager is not None and getattr(_manager, "ready", False)


def play(name, x=None, volume=1.0, max_seconds=None):
    if _manager is not None:
        return _manager.play(name, x, volume, max_seconds)
    return False


def music(track, fade=1.5):
    if _manager is not None:
        return _manager.play_music(track, fade)
    return False


def stop_music(fade=1.5):
    if _manager is not None:
        _manager.stop_music(fade)


def loop(name, on, x=None, fade=0.4):
    if _manager is not None:
        _manager.loop(name, on, x, fade)


def stop_all(fade=0.3):
    if _manager is not None:
        _manager.stop_all(fade)


def update(dt=None):
    if _manager is not None:
        _manager.update(dt)


def apply_settings(settings):
    if _manager is not None:
        _manager.apply_settings(settings)


def set_muted(muted):
    if _manager is not None:
        _manager.set_muted(muted)


def toggle_muted():
    """Flip mute. Returns the new state (False when there is no sound at all)."""
    if _manager is None:
        return False
    _manager.set_muted(not _manager.muted)
    return _manager.muted


def shutdown():
    global _manager
    if _manager is not None:
        _manager.shutdown()
    _manager = None
