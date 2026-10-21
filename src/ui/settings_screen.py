"""
settings_screen.py - The Settings window (Audio, Video, Controls tabs).

    from ui.settings_data import Settings
    from ui.settings_screen import SettingsScreen

    settings = Settings.load()
    screen_ui = SettingsScreen(settings)

    # every frame, while it's open:
    for event in pygame.event.get():
        result = screen_ui.handle_event(event)
        if result == "back":           close it (settings are already saved)
        if result == "video_changed":  call settings.apply_display(...) (fullscreen changed)
    screen_ui.update(dt)
    menu.draw(screen)                  # whatever is behind it (it gets dimmed)
    screen_ui.draw(screen)

CONTROLS
    Tab / Shift+Tab      next / previous tab        (or click a tab)
    Up / Down            choose a row
    Left / Right         change a volume, or pick On / Off
    Enter                change a key (then press the new key), or toggle
    Esc                  close (or cancel while changing a key)
    Mouse                drag sliders, click On/Off, click a key box to change it

PICTURES: panel.png, title_plate.png, button.png, button_selected.png,
          icon_sound.png, icon_video.png, icon_controls.png  (all optional)
"""
import math

import pygame

from . import theme
from .assets import get_image, get_font, nine_slice
from .settings_data import KEY_ACTIONS, VOLUMES
from .text import draw_text

BACK = "back"
VIDEO_CHANGED = "video_changed"

#        label        tab id      icon
TABS = [
    ("AUDIO",    "audio",    "icon_sound.png"),
    ("VIDEO",    "video",    "icon_video.png"),
    ("CONTROLS", "controls", "icon_controls.png"),
]
VOLUME_LABELS = {"master_volume": "Master Volume", "music_volume": "Music Volume",
                 "sfx_volume": "SFX Volume"}
VIDEO_ROWS = [("fullscreen", "Fullscreen"), ("screen_shake", "Screen Shake")]
RESET_ROW = "reset_keys"
VOLUME_STEP = 5

# layout (screen is 960 x 640)
PANEL = (150, 100, 660, 450)          # x, y, w, h
PANEL_BORDER = 28                     # frame thickness inside panel.png
PLATE_CENTER = (480, 100)
CLOSE = (782, 84, 40, 40)            # sits on the top-right corner of the panel
TAB_X, TAB_Y, TAB_W, TAB_H, TAB_GAP = 182, 150, 176, 52, 12
CONTENT_X, CONTENT_Y, CONTENT_W = 384, 150, 380
ROW_H = {"audio": 70, "video": 70, "controls": 32}
HINT_Y = 512


class SettingsScreen:
    def __init__(self, settings, save_path=None):
        self.settings = settings
        self.save_path = save_path            # None = the default place
        self.tab = 0
        self.row = 0
        self.rebinding = False                 # waiting for the player to press a new key
        self.dragging = None                   # which volume slider is being dragged
        self.time = 0.0
        self._cache = {}

    # ---------- what's on the current tab ----------

    @property
    def tab_id(self):
        return TABS[self.tab][1]

    def rows(self):
        if self.tab_id == "audio":
            return list(VOLUMES)
        if self.tab_id == "video":
            return [name for name, _ in VIDEO_ROWS]
        return [action for action, _, _ in KEY_ACTIONS] + [RESET_ROW]

    # ---------- logic (no drawing, easy to test) ----------

    def switch_tab(self, step=None, index=None):
        self.tab = index if index is not None else (self.tab + step) % len(TABS)
        self.row = 0
        self.rebinding = False

    def move(self, step):
        self.row = (self.row + step) % len(self.rows())

    def adjust(self, direction):
        """Left (-1) / Right (+1) on the selected row. Returns VIDEO_CHANGED if needed."""
        name = self.rows()[self.row]
        if self.tab_id == "audio":
            self.settings.set_volume(name, getattr(self.settings, name) + direction * VOLUME_STEP)
            self.settings.apply_audio()
        elif self.tab_id == "video":
            return self._set_toggle(name, direction < 0)      # left = On, right = Off
        return None

    def activate(self):
        """Enter on the selected row."""
        name = self.rows()[self.row]
        if self.tab_id == "video":
            return self._set_toggle(name, not getattr(self.settings, name))
        if self.tab_id == "controls":
            if name == RESET_ROW:
                self.settings.reset_keys()
            else:
                self.rebinding = True
        return None

    def press_key_while_rebinding(self, key_name):
        """The next key pressed after Enter becomes the new key. Esc cancels."""
        if key_name != "escape":
            self.settings.rebind(self.rows()[self.row], key_name)
        self.rebinding = False

    def close(self):
        if self.save_path:
            self.settings.save(self.save_path)
        else:
            self.settings.save()
        return BACK

    def _set_toggle(self, name, value):
        if getattr(self.settings, name) == value:
            return None
        setattr(self.settings, name, value)
        return VIDEO_CHANGED if name == "fullscreen" else None

    def _set_volume_from_x(self, index, x):
        tx, _, tw, _ = self.slider_track(index)
        name = VOLUMES[index]
        self.settings.set_volume(name, (x - tx) / tw * 100)
        self.settings.apply_audio()

    # ---------- where things are on screen ----------

    def tab_rects(self):
        return [(TAB_X, TAB_Y + i * (TAB_H + TAB_GAP), TAB_W, TAB_H) for i in range(len(TABS))]

    def row_rect(self, index):
        h = ROW_H[self.tab_id]
        return (CONTENT_X, CONTENT_Y + index * h, CONTENT_W, h)

    def slider_track(self, index):
        x, y, w, h = self.row_rect(index)
        return (x + 168, y + h // 2 - 7, 150, 14)

    def toggle_rects(self, index):
        x, y, w, h = self.row_rect(index)
        return (x + 180, y + 14, 84, h - 28), (x + 272, y + 14, 84, h - 28)

    def key_box(self, index):
        x, y, w, h = self.row_rect(index)
        return (x + 220, y + 3, 140, h - 6)

    # ---------- input ----------

    def handle_event(self, event):
        if event.type == pygame.KEYDOWN:
            if self.rebinding:
                self.press_key_while_rebinding(pygame.key.name(event.key))
                return None
            if event.key == pygame.K_ESCAPE:
                return self.close()
            if event.key == pygame.K_TAB:
                self.switch_tab(-1 if event.mod & pygame.KMOD_SHIFT else +1)
            elif event.key in (pygame.K_UP, pygame.K_w):
                self.move(-1)
            elif event.key in (pygame.K_DOWN, pygame.K_s):
                self.move(+1)
            elif event.key in (pygame.K_LEFT, pygame.K_a):
                return self.adjust(-1)
            elif event.key in (pygame.K_RIGHT, pygame.K_d):
                return self.adjust(+1)
            elif event.key in (pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_SPACE):
                return self.activate()

        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            return self._click(event.pos)
        elif event.type == pygame.MOUSEBUTTONUP and event.button == 1:
            self.dragging = None
        elif event.type == pygame.MOUSEMOTION:
            if self.dragging is not None:
                self._set_volume_from_x(self.dragging, event.pos[0])
            elif not self.rebinding:
                for i in range(len(self.rows())):
                    if _inside(event.pos, self.row_rect(i)):
                        self.row = i
        return None

    def _click(self, pos):
        if self.rebinding:
            self.rebinding = False             # clicking anywhere cancels
            return None
        if _inside(pos, CLOSE):
            return self.close()
        for i, rect in enumerate(self.tab_rects()):
            if _inside(pos, rect):
                self.switch_tab(index=i)
                return None
        for i, name in enumerate(self.rows()):
            if self.tab_id == "audio":
                tx, ty, tw, th = self.slider_track(i)
                if _inside(pos, (tx - 10, ty - 14, tw + 20, th + 28)):
                    self.row, self.dragging = i, i
                    self._set_volume_from_x(i, pos[0])
                    return None
            elif self.tab_id == "video":
                on_rect, off_rect = self.toggle_rects(i)
                if _inside(pos, on_rect) or _inside(pos, off_rect):
                    self.row = i
                    return self._set_toggle(name, _inside(pos, on_rect))
            elif _inside(pos, self.row_rect(i)):
                self.row = i
                return self.activate()
        return None

    def update(self, dt):
        self.time += dt

    # ---------- drawing ----------

    def draw(self, surface):
        shade = pygame.Surface((surface.get_width(), surface.get_height()), pygame.SRCALPHA)
        shade.fill((0, 0, 0, 150))                         # dim whatever is behind
        surface.blit(shade, (0, 0))
        self._draw_panel(surface)
        self._draw_plate(surface)
        self._draw_close(surface)
        self._draw_tabs(surface)
        {"audio": self._draw_audio, "video": self._draw_video,
         "controls": self._draw_controls}[self.tab_id](surface)
        hint = "PRESS A KEY  -  ESC TO CANCEL" if self.rebinding else \
            "TAB: SWITCH TAB   ARROWS: CHANGE   ESC: BACK"
        draw_text(surface, hint, get_font(theme.FONT_SMALL), theme.TEXT_DIM,
                  (PANEL[0] + PANEL[2] // 2, HINT_Y), outline=1, center=True)

    def _stretched(self, name, w, h, border):
        """nine_slice a picture once and keep it."""
        key = (name, w, h)
        if key not in self._cache:
            image = get_image(name)
            self._cache[key] = nine_slice(image, w, h, border) if image is not None else None
        return self._cache[key]

    def _draw_panel(self, surface):
        x, y, w, h = PANEL
        panel = self._stretched("panel.png", w, h, PANEL_BORDER)
        if panel is not None:
            surface.blit(panel, (x, y))
        else:
            pygame.draw.rect(surface, theme.OUTLINE, (x - 3, y - 3, w + 6, h + 6))
            pygame.draw.rect(surface, theme.STONE, (x, y, w, h))
            pygame.draw.rect(surface, theme.WOOD, (x + 14, y + 14, w - 28, h - 28))
            pygame.draw.rect(surface, theme.PANEL, (x + 20, y + 20, w - 40, h - 40))

    def _draw_plate(self, surface):
        cx, cy = PLATE_CENTER
        plate = get_image("title_plate.png")
        if plate is not None:
            surface.blit(plate, (cx - plate.get_width() // 2, cy - plate.get_height() // 2))
        else:
            pygame.draw.rect(surface, theme.OUTLINE, (cx - 132, cy - 26, 264, 52))
            pygame.draw.rect(surface, theme.WOOD, (cx - 128, cy - 22, 256, 44))
        draw_text(surface, "SETTINGS", get_font(theme.FONT_BUTTON), theme.TITLE, (cx, cy),
                  outline=2, outline_color=theme.TITLE_SHADOW, center=True)

    def _draw_close(self, surface):
        x, y, w, h = CLOSE
        pygame.draw.rect(surface, theme.OUTLINE, (x - 2, y - 2, w + 4, h + 4))
        pygame.draw.rect(surface, theme.BRASS, (x, y, w, h))
        pygame.draw.rect(surface, theme.STONE_DARK, (x + 3, y + 3, w - 6, h - 6))
        draw_text(surface, "X", get_font(theme.FONT_LABEL), theme.TEXT,
                  (x + w // 2, y + h // 2), outline=1, shadow=False, center=True)

    def _draw_tabs(self, surface):
        for i, (label, _, icon) in enumerate(TABS):
            x, y, w, h = self.tab_rects()[i]
            selected = i == self.tab
            image = self._stretched("button_selected.png" if selected else "button.png", w, h, 14)
            if image is not None:
                surface.blit(image, (x, y))
            else:
                pygame.draw.rect(surface, theme.BRASS if selected else theme.WOOD, (x, y, w, h))
                pygame.draw.rect(surface, theme.TORCH if selected else theme.STONE,
                                 (x + 4, y + 4, w - 8, h - 8))
            icon_image = get_image(icon)
            if icon_image is not None:
                surface.blit(icon_image, (x + 14, y + (h - icon_image.get_height()) // 2))
            draw_text(surface, label, get_font(theme.FONT_LABEL),
                      theme.TEXT if selected else theme.TEXT_DIM, (x + 54, y + h // 2),
                      outline=2, middle=True)

    def _draw_row_highlight(self, surface, index):
        x, y, w, h = self.row_rect(index)
        pygame.draw.rect(surface, theme.STONE, (x - 10, y + 2, w + 14, h - 4))
        pygame.draw.rect(surface, theme.BRASS, (x - 10, y + 2, 4, h - 4))

    def _draw_audio(self, surface):
        font = get_font(theme.FONT_LABEL)
        for i, name in enumerate(VOLUMES):
            if i == self.row:
                self._draw_row_highlight(surface, i)
            x, y, w, h = self.row_rect(i)
            draw_text(surface, VOLUME_LABELS[name], font, theme.TEXT, (x, y + h // 2),
                      outline=2, middle=True)
            value = getattr(self.settings, name)
            tx, ty, tw, th = self.slider_track(i)
            pygame.draw.rect(surface, theme.OUTLINE, (tx - 2, ty - 2, tw + 4, th + 4))
            pygame.draw.rect(surface, theme.STONE, (tx, ty, tw, th))
            pygame.draw.rect(surface, theme.TORCH, (tx, ty, int(tw * value / 100), th))
            pygame.draw.rect(surface, theme.TORCH_LIGHT, (tx, ty, int(tw * value / 100), 3))
            knob_x = tx + int(tw * value / 100) - 7
            pygame.draw.rect(surface, theme.OUTLINE, (knob_x - 2, ty - 8, 18, th + 16))
            pygame.draw.rect(surface, theme.BRASS, (knob_x, ty - 6, 14, th + 12))
            draw_text(surface, f"{value}%", font, theme.TEXT, (tx + tw + 14, y + h // 2),
                      outline=2, middle=True)

    def _draw_video(self, surface):
        font = get_font(theme.FONT_LABEL)
        for i, (name, label) in enumerate(VIDEO_ROWS):
            if i == self.row:
                self._draw_row_highlight(surface, i)
            x, y, w, h = self.row_rect(i)
            draw_text(surface, label, font, theme.TEXT, (x, y + h // 2), outline=2, middle=True)
            value = getattr(self.settings, name)
            for rect, text, is_on in zip(self.toggle_rects(i), ("ON", "OFF"), (True, False)):
                active = value == is_on
                rx, ry, rw, rh = rect
                pygame.draw.rect(surface, theme.OUTLINE, (rx - 2, ry - 2, rw + 4, rh + 4))
                pygame.draw.rect(surface, theme.BRASS if active else theme.WOOD_DARK, (rx, ry, rw, rh))
                pygame.draw.rect(surface, theme.TORCH if active else theme.STONE,
                                 (rx + 3, ry + 3, rw - 6, rh - 6))
                draw_text(surface, text, font, theme.TEXT if active else theme.TEXT_DIM,
                          (rx + rw // 2, ry + rh // 2), outline=2, center=True)

    def _draw_controls(self, surface):
        font = get_font(theme.FONT_LABEL)
        blink = math.sin(self.time * 8) > 0
        for i, (action, label, _) in enumerate(KEY_ACTIONS):
            if i == self.row:
                self._draw_row_highlight(surface, i)
            x, y, w, h = self.row_rect(i)
            draw_text(surface, label, font, theme.TEXT, (x, y + h // 2), outline=2, middle=True)
            bx, by, bw, bh = self.key_box(i)
            waiting = self.rebinding and i == self.row
            pygame.draw.rect(surface, theme.OUTLINE, (bx - 2, by - 2, bw + 4, bh + 4))
            pygame.draw.rect(surface, theme.TORCH if waiting else theme.WOOD_DARK, (bx, by, bw, bh))
            pygame.draw.rect(surface, theme.STONE_DARK if not waiting else theme.TORCH,
                             (bx + 2, by + 2, bw - 4, bh - 4))
            key_text = ("..." if blink else "") if waiting else self.settings.key_for(action).upper()
            draw_text(surface, key_text, font, theme.TEXT, (bx + bw // 2, by + bh // 2),
                      outline=2, center=True)
        i = len(KEY_ACTIONS)
        if i == self.row:
            self._draw_row_highlight(surface, i)
        x, y, w, h = self.row_rect(i)
        draw_text(surface, "Reset to default keys", font, theme.TITLE, (x, y + h // 2 + 4),
                  outline=2, middle=True)


def _inside(pos, rect):
    x, y, w, h = rect
    return x <= pos[0] < x + w and y <= pos[1] < y + h
