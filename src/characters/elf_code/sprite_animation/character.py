"""
AnimatedCharacter - a ready-to-use character: position + movement + animation + drawing.

This is the class most games will use directly. It owns an AnimationController, moves
the character at walk/run speed, and blits the right frame at the right place.
"""
from __future__ import annotations

from typing import List, Optional, Tuple

import pygame

from .assets import AnimationLibrary
from .controller import AnimationController, ControllerSettings
from .player import AnimationPlayer


class AnimatedCharacter:
    """
    Args:
        library:     a loaded :class:`AnimationLibrary` (share one between characters).
        x, y:        world position of the character's FEET (ground contact point).
        walk_speed:  pixels/second while walking (tune to match the walk cycle's stride
                     so the feet don't slide; lower = heavier steps).
        run_speed:   pixels/second while running.
        bounds:      optional ``(min_x, max_x)`` to keep the character inside.
        settings:    optional :class:`ControllerSettings`.
    """

    def __init__(
        self,
        library: AnimationLibrary,
        x: float,
        y: float,
        walk_speed: float = 110.0,
        run_speed: float = 250.0,
        bounds: Optional[Tuple[float, float]] = None,
        settings: Optional[ControllerSettings] = None,
    ):
        self.library = library
        self.x = float(x)
        self.y = float(y)
        # speeds are given for 1x art; scale them with the zoom so motion matches the sprites
        self.walk_speed = walk_speed * library.scale
        self.run_speed = run_speed * library.scale
        self.bounds = bounds
        player = AnimationPlayer(library.specs, library.frame_counts)
        self.controller = AnimationController(player, settings)

    # ----------------------------------------------------------------- actions
    def quick_attack(self) -> None:
        """Fire a quick shot (buffered if another attack is still playing)."""
        self.controller.request_quick_attack()

    def start_charge(self) -> None:
        """Begin drawing a charged shot. Call release_charge() when the button is let go."""
        self.controller.press_charge()

    def release_charge(self) -> None:
        """Release the charged shot (fires if fully drawn, cancels if released early)."""
        self.controller.release_charge()

    # ------------------------------------------------------------------ update
    def update(self, dt: float, move_x: float = 0.0, running: bool = False) -> List[str]:
        """Advance the character by ``dt`` SECONDS.

        ``move_x``  -1..1 horizontal input (keyboard: -1, 0, +1; analog stick: any value).
        ``running`` run modifier (only has an effect while ``move_x`` is non-zero).
        Returns the list of animation events that fired this tick (e.g. ``["fire"]``).
        """
        events = self.controller.update(dt * 1000.0, move_x, running)
        if move_x and self.controller.can_move:
            speed = self.run_speed if running else self.walk_speed
            self.x += max(-1.0, min(1.0, move_x)) * speed * dt
            if self.bounds:
                self.x = max(self.bounds[0], min(self.bounds[1], self.x))
        return events

    # -------------------------------------------------------------------- draw
    @property
    def current_frame(self):
        c = self.controller
        return self.library[c.animation_name].get(c.frame_index, c.facing)

    def draw(self, surface: pygame.Surface, offset: Tuple[int, int] = (0, 0)) -> pygame.Rect:
        """Blit the current frame. Position is rounded to whole pixels (no shimmer).

        ``offset`` is for cameras / scrolling: it is added to the draw position.
        Returns the rectangle that was drawn.
        """
        frame = self.current_frame
        pos = (round(self.x) - frame.anchor[0] + offset[0], round(self.y) - frame.anchor[1] + offset[1])
        return surface.blit(frame.image, pos)
