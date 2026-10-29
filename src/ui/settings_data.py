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
TOGGLES = ("fullscreen", "screen_shake")

# The actions the player can rebind, in the order shown on screen.
# These are suggestions: agree on them with the Characters & Skills team.
#               action            label shown          default key (pygame key name)
KEY_ACTIONS = [
    ("move_up",       "Move Up",       "w"),
    ("move_down",     "Move Down",     "s"),
    ("move_left",     "Move Left",     "a"),
    ("move_right",    "Move Right",    "d"),
    ("attack",        "Attack",        "j"),
    ("skill",         "Skill",         "k"),
    ("dash",          "Dash",          "space"),
    ("switch_weapon", "Switch Weapon", "q"),
    ("interact",      "Interact",      "e"),
]


class Settings:
    def __init__(self):
        self.master_volume = 80          # 0 - 100
        self.music_volume = 70
        self.sfx_volume = 70
        self.fullscreen = False
        self.screen_shake = True
        self.key_bindings = {action: key for action, _, key in KEY_ACTIONS}

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
        keys = data.get("key_bindings")
        if isinstance(keys, dict):
            for action in settings.key_bindings:
                if isinstance(keys.get(action), str):
                    settings.key_bindings[action] = keys[action]
        return settings

    # ---------- applying to pygame ----------

    def apply_audio(self):
        """Set the music volume in pygame (sound effects read effective_volume('sfx'))."""
        try:
            import pygame
            if pygame.mixer.get_init():
                pygame.mixer.music.set_volume(self.effective_volume("music"))
        except Exception:
            pass                         # no sound device: ignore

    def apply_display(self, size):
        """Make the window fullscreen or not. Returns the new screen Surface."""
        import pygame
        flags = pygame.SCALED | (pygame.FULLSCREEN if self.fullscreen else 0)
        return pygame.display.set_mode(size, flags)
