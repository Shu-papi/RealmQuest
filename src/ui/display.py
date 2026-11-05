"""
display.py - The game window, and the fixed-size canvas the game draws on.

    display = Display((1152, 648))
    screen = display.open(settings)        # canvas to draw on (the same Surface every time)
    ...draw the frame on `screen`...
    display.present()                      # canvas -> window, scaled to fill it, then flip
    event = display.map_event(event)       # mouse positions in canvas coordinates
    display.mouse_pos()                    # pygame.mouse.get_pos(), in canvas coordinates

The game always draws at one size. present() scales that picture to the window (Settings:
display mode + resolution), keeping its shape: it fills a 16:9 screen completely and adds
thin black bars on other shapes. Whole-number zooms stay pixel-sharp; others are smoothed.
"""
import pygame

MOUSE_EVENTS = (pygame.MOUSEMOTION, pygame.MOUSEBUTTONDOWN, pygame.MOUSEBUTTONUP)


class Display:
    def __init__(self, size):
        self.size = tuple(size)
        self.canvas = None
        self.window = None
        self.view = pygame.Rect(0, 0, *self.size)    # where the canvas lands in the window
        self._scaled = None
        self._win_size = None

    def open(self, settings):
        """(Re)make the window from the settings. Returns the canvas to draw on."""
        self.window = settings.open_window(self.size)
        if self.canvas is None:
            self.canvas = pygame.Surface(self.size).convert()
        self._layout()
        return self.canvas

    def _layout(self):
        ww, wh = self._win_size = self.window.get_size()
        cw, ch = self.size
        k = min(ww / cw, wh / ch)
        if abs(k - round(k)) < 0.01:                  # a whole-number zoom: crisp pixels
            k = round(k)
        w, h = max(1, int(cw * k)), max(1, int(ch * k))
        self.view = pygame.Rect((ww - w) // 2, (wh - h) // 2, w, h)
        self._scaled = None if (w, h) == self.size else pygame.Surface((w, h)).convert()

    def present(self):
        """Show the canvas in the window and flip."""
        win = pygame.display.get_surface()
        if win is None:
            return
        if win.get_size() != self._win_size:
            self.window = win                         # the window changed under us: lay out again
            self._layout()
        if self._scaled is None:
            win.blit(self.canvas, self.view)
        else:
            if self.view.w % self.size[0] == 0 and self.view.h % self.size[1] == 0:
                pygame.transform.scale(self.canvas, self.view.size, self._scaled)
            else:
                pygame.transform.smoothscale(self.canvas, self.view.size, self._scaled)
            win.blit(self._scaled, self.view)
        if self.view.size != win.get_size():          # black bars around a different-shaped screen
            for r in self._bars(win.get_size()):
                win.fill((0, 0, 0), r)
        pygame.display.flip()

    def _bars(self, size):
        ww, wh = size
        v = self.view
        return [pygame.Rect(0, 0, ww, v.y), pygame.Rect(0, v.bottom, ww, wh - v.bottom),
                pygame.Rect(0, v.y, v.x, v.h), pygame.Rect(v.right, v.y, ww - v.right, v.h)]

    # ---- mouse ---------------------------------------------------------------------
    def to_canvas(self, pos):
        """A window position -> the canvas position under it (clamped to the canvas)."""
        v = self.view
        x = (pos[0] - v.x) * self.size[0] / max(1, v.w)
        y = (pos[1] - v.y) * self.size[1] / max(1, v.h)
        return (int(max(0, min(self.size[0] - 1, x))), int(max(0, min(self.size[1] - 1, y))))

    def map_event(self, event):
        if event.type not in MOUSE_EVENTS or "pos" not in event.dict:
            return event
        data = dict(event.dict)
        data["pos"] = self.to_canvas(event.pos)
        if "rel" in data:
            kx, ky = self.size[0] / max(1, self.view.w), self.size[1] / max(1, self.view.h)
            data["rel"] = (int(data["rel"][0] * kx), int(data["rel"][1] * ky))
        return pygame.event.Event(event.type, data)

    def mouse_pos(self):
        return self.to_canvas(pygame.mouse.get_pos())
