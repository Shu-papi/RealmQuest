"""
settings_data.py - The player's settings (volumes, video options, key bindings),
plus saving/loading them so they're remembered next time.

    from ui.settings_data import Settings

    settings = Settings.load()              # reads the saved file, or uses defaults
    settings.music_volume = 50
    settings.save()

    # other teams can ask:
    settings.key_for("attack")              # -> "j"
    settings.effective_volume("sfx")        # -> 0.0 .. 1.0 (master x sfx)

No drawing here: this is plain data, so it's easy to test.
The settings screen (settings_screen.py) is what shows and changes it.
"""
import json
import os

# saved in the player's home folder, NOT in the repo, so each person keeps their own
DEFAULT_PATH = os.path.join(os.path.expanduser("~"), ".realmquest_settings.json")

VOLUMES = ("master_volume", "music_volume", "sfx_volume")
TOGGLES = ("vsync", "show_fps", "screen_shake")

# ---- video ------------------------------------------------------------------------------
# The game always draws at 1152 x 648; pygame.SCALED stretches it to the window (and keeps
# the mouse in game coordinates), so any resolution / mode works without changing the game.
DISPLAY_MODES = ("windowed", "borderless", "borderless_fullscreen", "fullscreen")
DISPLAY_MODE_NAMES = {"windowed": "Windowed", "borderless": "Borderless Window",
                      "borderless_fullscreen": "Borderless Fullscreen", "fullscreen": "Fullscreen"}
RESOLUTIONS = ((960, 540), (1152, 648), (1280, 720), (1366, 768), (1600, 900), (1920, 1080), (2560, 1440))
DEFAULT_RESOLUTION = (1152, 648)
FPS_CAPS = (30, 60, 120, 144, 0)          # 0 = no limit

# The actions the player can rebind, in the order shown on screen.
# These are suggestions: agree on them with the Characters & Skills team.
#               action            label shown          default key (pygame key name)
KEY_ACTIONS = [
    ("move_up",       "Move Up",       "w"),
    ("move_down",     "Move Down",     "s"),
    ("move_left",     "Move Left",     "a"),
    ("move_right",    "Move Right",    "d"),
    ("attack",        "Attack",        "j"),
    ("skill",         "Skill 1",       "k"),
    ("skill_2",       "Skill 2",       "u"),
    ("special",       "Special",       "f"),
    ("dash",          "Dash",          "left shift"),
    ("switch_weapon", "Switch Weapon", "q"),
    ("interact",      "Interact",      "e"),
]


class Settings:
    def __init__(self):
        self.master_volume = 80          # 0 - 100
        self.music_volume = 70
        self.sfx_volume = 70
        self.display_mode = "windowed"
        self.resolution = DEFAULT_RESOLUTION
        self.vsync = False
        self.fps_cap = 60
        self.show_fps = False
        self.screen_shake = True
        self.key_bindings = {action: key for action, _, key in KEY_ACTIONS}

    # ---------- video ----------

    @property
    def fullscreen(self):
        """True for both fullscreen modes (older code and settings files only knew this)."""
        return self.display_mode in ("fullscreen", "borderless_fullscreen")

    @fullscreen.setter
    def fullscreen(self, value):
        self.display_mode = "fullscreen" if value else "windowed"

    def cycle(self, name, step):
        """Left / Right on a list setting: display_mode, resolution or fps_cap."""
        options = {"display_mode": DISPLAY_MODES, "resolution": RESOLUTIONS, "fps_cap": FPS_CAPS}[name]
        cur = getattr(self, name)
        i = options.index(cur) if cur in options else 0
        setattr(self, name, options[(i + step) % len(options)])

    def choice_text(self, name):
        if name == "display_mode":
            return DISPLAY_MODE_NAMES[self.display_mode]
        if name == "resolution":
            return "%d x %d" % self.resolution
        if name == "fps_cap":
            return "Unlimited" if not self.fps_cap else "%d FPS" % self.fps_cap
        return str(getattr(self, name))

    # ---------- volumes ----------

    def set_volume(self, name, value):
        if name not in VOLUMES:
            raise KeyError(name)
        setattr(self, name, max(0, min(100, int(round(value)))))

    def effective_volume(self, kind):
        """'music' or 'sfx' as 0.0 - 1.0, already multiplied by the master volume."""
        own = getattr(self, f"{kind}_volume")
        return (self.master_volume / 100) * (own / 100)

    # ---------- keys ----------

    def key_for(self, action):
        return self.key_bindings[action]

    def rebind(self, action, key_name):
        """
        Give 'action' a new key. If another action already used that key,
        the two simply swap, so no key ever does two things.
        """
        if action not in self.key_bindings:
            raise KeyError(action)
        old_key = self.key_bindings[action]
        for other, key in self.key_bindings.items():
            if key == key_name and other != action:
                self.key_bindings[other] = old_key
        self.key_bindings[action] = key_name

    def reset_keys(self):
        self.key_bindings = {action: key for action, _, key in KEY_ACTIONS}

    # ---------- saving ----------

    def to_dict(self):
        data = {name: getattr(self, name) for name in VOLUMES + TOGGLES}
        data.update(display_mode=self.display_mode, resolution=list(self.resolution), fps_cap=self.fps_cap)
        data["key_bindings"] = dict(self.key_bindings)
        return data

    def save(self, path=DEFAULT_PATH):
        try:
            with open(path, "w", encoding="utf-8") as file:
                json.dump(self.to_dict(), file, indent=2)
            return True
        except OSError:
            return False                 # can't save? the game still works

    @classmethod
    def load(cls, path=DEFAULT_PATH):
        """Read saved settings. Missing or broken file -> defaults (never crashes)."""
        settings = cls()
        try:
            with open(path, encoding="utf-8") as file:
                data = json.load(file)
        except (OSError, ValueError):
            return settings
        if not isinstance(data, dict):
            return settings
        for name in VOLUMES:
            if isinstance(data.get(name), (int, float)):
                settings.set_volume(name, data[name])
        for name in TOGGLES:
            if isinstance(data.get(name), bool):
                setattr(settings, name, data[name])
        if isinstance(data.get("fullscreen"), bool):                 # files from before display modes
            settings.fullscreen = data["fullscreen"]
        if data.get("display_mode") in DISPLAY_MODES:
            settings.display_mode = data["display_mode"]
        res = data.get("resolution")
        if isinstance(res, list) and tuple(res) in RESOLUTIONS:
            settings.resolution = tuple(res)
        if data.get("fps_cap") in FPS_CAPS:
            settings.fps_cap = data["fps_cap"]
        keys = data.get("key_bindings")
        if isinstance(keys, dict):
            old_file = "special" not in keys          # saved before the skill keys existed
            for action in settings.key_bindings:
                if isinstance(keys.get(action), str):
                    settings.key_bindings[action] = keys[action]
            if old_file and keys.get("dash") == "space":
                # the old placeholder default; Space is the game's attack key, dash is Shift now
                settings.key_bindings["dash"] = dict((a, k) for a, _l, k in KEY_ACTIONS)["dash"]
            settings._resolve_clashes()
        return settings

    def _resolve_clashes(self):
        """After loading an older file, a new action may share a key: give it back its default
        (or leave it unbound as '?' if that is taken too), so no key does two things."""
        defaults = {action: key for action, _l, key in KEY_ACTIONS}
        seen = {}
        for action, _l, _k in KEY_ACTIONS:
            key = self.key_bindings[action]
            if key in seen:
                free = defaults[action] if defaults[action] not in self.key_bindings.values() else "?"
                self.key_bindings[action] = free
            seen[self.key_bindings[action]] = action

    # ---------- applying to pygame ----------

    def apply_audio(self):
        """Tell pygame and the audio package (src/audio) the new volumes."""
        try:
            import pygame
            if pygame.mixer.get_init():
                pygame.mixer.music.set_volume(self.effective_volume("music"))
        except Exception:
            pass                         # no sound device: ignore
        try:
            try:
                import audio             # src/ is on sys.path
            except ImportError:
                from src import audio
            audio.apply_settings(self)   # sound effects, music and loops follow the sliders too
        except Exception:
            pass

    def copy(self):
        """An independent copy (the settings screen edits one until Apply)."""
        other = Settings()
        other.copy_from(self)
        return other

    def copy_from(self, other):
        for name, value in vars(other).items():
            setattr(self, name, dict(value) if isinstance(value, dict) else value)

    def same_as(self, other):
        return self.to_dict() == other.to_dict()

    # ---------- the window ----------

    def window_size(self, desktop, frame=False):
        """The window size for this resolution, never larger than the desktop
        (`frame`: leave room for the title bar and taskbar of a normal window)."""
        w, h = self.resolution
        dw, dh = desktop[0], desktop[1] - (80 if frame else 0)
        if w > dw or h > dh:
            k = min(dw / w, dh / h)
            w, h = int(w * k), int(h * k)
        return w, h

    def window_plan(self, desktop, fullscreen_modes=()):
        """(size, mode) of the window to open: what each display mode means.
            windowed               a normal window of the chosen resolution
            borderless             the same without a title bar
            borderless_fullscreen  a frameless window covering the whole desktop
            fullscreen             the screen switches to the chosen resolution"""
        mode = self.display_mode
        if mode == "fullscreen":
            ok = not fullscreen_modes or tuple(self.resolution) in fullscreen_modes
            return (tuple(self.resolution) if ok else tuple(desktop)), mode
        if mode == "borderless_fullscreen":
            return tuple(desktop), mode
        return self.window_size(desktop, frame=mode == "windowed"), mode

    def open_window(self, size=None):
        """Open / re-make the game window. The game draws on its own canvas and
        ui.display.Display scales it to this window. Returns the window Surface."""
        import pygame
        desktop = pygame.display.get_desktop_sizes()[0]
        try:
            modes = pygame.display.list_modes()
            modes = set(modes) if modes not in (-1, None) else set()
        except pygame.error:
            modes = set()
        wsize, mode = self.window_plan(desktop, modes)
        flags = {"fullscreen": pygame.FULLSCREEN, "borderless": pygame.NOFRAME,
                 "borderless_fullscreen": pygame.NOFRAME}.get(mode, 0)
        try:
            window = pygame.display.set_mode(wsize, flags, vsync=1 if self.vsync else 0)
        except pygame.error:                         # no VSync here: open without it
            window = pygame.display.set_mode(wsize, flags)
            self.vsync_failed = True
        try:
            win = pygame.Window.from_display_module()
            if mode == "borderless_fullscreen":
                win.position = (0, 0)
            elif mode != "fullscreen":
                win.position = pygame.WINDOWPOS_CENTERED
        except (pygame.error, AttributeError):       # older pygame: wherever SDL put it
            pass
        return window

    def frame_cap(self):
        """FPS for clock.tick(): the FPS limit, or the monitor's rate when VSync couldn't be
        switched on (so VSync still stops the game from running flat out)."""
        if self.vsync and getattr(self, "vsync_failed", False):
            try:
                import pygame
                rate = pygame.display.get_current_refresh_rate()
                if rate:
                    return min(rate, self.fps_cap) if self.fps_cap else rate
            except Exception:
                pass
        return self.fps_cap

    def apply_display(self, size):
        """Older name for open_window (kept so other tools keep working)."""
        return self.open_window(size)
