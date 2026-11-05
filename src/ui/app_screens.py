"""
app_screens.py - The front end of the game: Home (main menu) -> Name your hero ->
Choose your class -> straight into the world. Settings opens from the menu.

    front = FrontEnd(settings, save_info="Aria  -  Mage  -  Lv 4", portraits={...})
    result = front.handle_event(event)
        ("new", name, character_class)   start a new game as this hero
        ("continue",)                     load the saved game
        ("quit",)                         close the game
        ("video",)                        Apply changed the display (re-create the window)
        ("applied",)                      Apply changed other settings (keys, volume...)
    front.update(dt)
    front.draw(window)                    # any window size: the 960x640 screens are centred

The screens are the team's (menu.py, name_entry.py, class_select.py, settings_screen.py);
this file only switches between them, so the game loop stays simple.
"""
import pygame

from . import theme
from .class_select import ClassSelect, START, BACK as CLASS_BACK
from .menu import MainMenu, CONTINUE, NEW_GAME, SETTINGS, EXIT
from .name_entry import NameEntry, NEXT, BACK as NAME_BACK
from .settings_screen import SettingsScreen, BACK as SETTINGS_BACK, VIDEO_CHANGED, APPLIED

SIZE = (theme.SCREEN_W, theme.SCREEN_H)


class FrontEnd:
    def __init__(self, settings, save_info=None, portraits=None, hero_name="", skill_keys=None,
                 heroes=None, sprites=None, play=None):
        self.heroes = heroes or []          # animated hero(es) for the home screen
        self.sprites = sprites if sprites is not None else {}   # {class: HeroSprite} for the class cards
        self.play = play or (lambda name: None)
        self.settings = settings
        self.portraits = portraits or {}
        self.skill_keys = skill_keys or {}
        self.canvas = pygame.Surface(SIZE)
        self.offset = (0, 0)
        self.hero_name = hero_name
        self.set_save(save_info)
        self.name_screen = None
        self.class_screen = None
        self.settings_screen = None
        self.screen = "menu"

    def set_save(self, save_info):
        """save_info: one-line summary of the saved game, or None when there is nothing to continue."""
        self.save_info = save_info
        buttons = []
        if save_info:
            buttons.append(("CONTINUE", CONTINUE, "icon_play.png"))
        buttons += [("NEW GAME", NEW_GAME, "icon_shield.png" if save_info else "icon_play.png"),
                    ("SETTINGS", SETTINGS, "icon_gear.png"),
                    ("EXIT", EXIT, "icon_exit.png")]
        self.menu = MainMenu(buttons=buttons, info=save_info, heroes=self.heroes)

    def open(self, screen="menu"):
        self.screen = screen
        if screen == "name":
            self.name_screen = NameEntry(self.hero_name)
        elif screen == "class":
            self.class_screen = ClassSelect(hero_name=self.hero_name, portraits=self.portraits,
                                            skill_keys=self.skill_keys, sprites=self.sprites)
            self._flourish(self.class_screen.chosen)
        elif screen == "settings":
            self.settings_screen = SettingsScreen(self.settings, play=self.play)

    def _flourish(self, cls):
        """The picked hero on the class cards shows off their attack once."""
        sprite = self.sprites.get(cls)
        if sprite is not None:
            sprite.act("attack")

    # ---------- input ----------
    def _local(self, event):
        """The same event with its mouse position moved into the 960x640 screen."""
        if hasattr(event, "pos") and event.type in (pygame.MOUSEMOTION, pygame.MOUSEBUTTONDOWN,
                                                    pygame.MOUSEBUTTONUP):
            x, y = event.pos
            data = dict(event.dict)
            data["pos"] = (x - self.offset[0], y - self.offset[1])
            return pygame.event.Event(event.type, data)
        return event

    def handle_event(self, event):
        """Input for the current screen, with menu sounds (move / select / back)."""
        screen = self.screen
        before = self._focus()
        result = self._handle(self._local(event))
        if screen == "settings":
            return result                        # the settings screen plays its own sounds
        if result is not None or self.screen != screen:
            backwards = self.screen == "menu" and screen != "menu" or \
                (screen == "class" and self.screen == "name")
            self.play("ui_back" if backwards else "ui_select")
        elif self._focus() != before:
            self.play("ui_move")
            if screen == "class":
                self._flourish(self.class_screen.chosen)
        return result

    def _focus(self):
        """What is highlighted right now (to hear when it changes)."""
        if self.screen == "menu":
            return self.menu.selected
        if self.screen == "class" and self.class_screen is not None:
            return self.class_screen.selected
        return None

    def _handle(self, event):
        if self.screen == "menu":
            action = self.menu.handle_event(event)
            if action == CONTINUE:
                return ("continue",)
            if action == NEW_GAME:
                self.open("name")
            elif action == SETTINGS:
                self.open("settings")
            elif action == EXIT:
                return ("quit",)
            elif event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                return ("quit",)
        elif self.screen == "name":
            result = self.name_screen.handle_event(event)
            if result == NEXT:
                self.hero_name = self.name_screen.name
                self.open("class")
            elif result == NAME_BACK:
                self.open("menu")
        elif self.screen == "class":
            result = self.class_screen.handle_event(event)
            if result == START:
                return ("new", self.hero_name, self.class_screen.chosen)
            if result == CLASS_BACK:
                self.open("name")
        elif self.screen == "settings":
            result = self.settings_screen.handle_event(event)
            if result == SETTINGS_BACK:
                self.open("menu")
            elif result == VIDEO_CHANGED:
                return ("video",)
            elif result == APPLIED:
                return ("applied",)
        return None

    def update(self, dt):
        self.menu.update(dt)
        for scr in (self.name_screen, self.class_screen, self.settings_screen):
            if scr is not None and hasattr(scr, "update"):
                scr.update(dt)

    # ---------- drawing ----------
    def draw(self, window):
        c = self.canvas
        if self.screen == "settings":
            self.menu.draw(c)
            self.settings_screen.draw(c)
        elif self.screen == "name":
            self.name_screen.draw(c)
        elif self.screen == "class":
            self.class_screen.draw(c)
        else:
            self.menu.draw(c)
        draw_centered(window, c, self)


def draw_centered(window, canvas, holder=None):
    """Blit the 960x640 canvas in the middle of the window, with stone bands around it."""
    W, H = window.get_size()
    w, h = canvas.get_size()
    if (W, H) == (w, h):
        window.blit(canvas, (0, 0))
        if holder is not None:
            holder.offset = (0, 0)
        return
    ox, oy = (W - w) // 2, (H - h) // 2
    window.fill(theme.STONE_DARK)
    for x in range(0, W, 48):                     # a simple stone-block pattern in the bands
        for y in range(0, H, 32):
            sx = x + (24 if (y // 32) % 2 else 0)
            pygame.draw.rect(window, theme.STONE, (sx + 2, y + 2, 44, 28), 1)
    window.blit(canvas, (ox, oy))
    pygame.draw.rect(window, theme.BRASS, (ox - 3, oy - 3, w + 6, h + 6), 2)
    if holder is not None:
        holder.offset = (ox, oy)
