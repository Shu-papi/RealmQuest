"""
sprite_animation - Idle / Walk / Run / Quick-Attack / Charge-Attack animation system.

Layers (each usable on its own):

    config      AnimationSpec + the five animation definitions   (pure Python)
    player      AnimationPlayer: frame timing, looping, events    (pure Python)
    controller  AnimationController: input -> which animation     (pure Python)
    assets      AnimationLibrary: PNG loading, anchors, mirroring (pygame)
    character   AnimatedCharacter: movement + animation + draw    (pygame)

The pure-Python layers import without pygame, so they can be unit-tested headlessly.
The pygame classes are imported lazily on first access.
"""
from .config import (ANIMATIONS, ATTACKS, CHARGE_ATTACK, IDLE, LOCOMOTION, QUICK_ATTACK, RUN, WALK,
                     AnimationSpec, discover_frame_counts)
from .controller import AnimationController, ControllerSettings
from .player import AnimationPlayer

__all__ = [
    "ANIMATIONS", "ATTACKS", "CHARGE_ATTACK", "IDLE", "LOCOMOTION", "QUICK_ATTACK", "RUN", "WALK",
    "AnimationSpec", "discover_frame_counts", "AnimationController", "ControllerSettings",
    "AnimationPlayer", "AnimationLibrary", "AnimatedCharacter",
]


def __getattr__(name):                      # lazy: only needs pygame when actually used
    if name == "AnimationLibrary":
        from .assets import AnimationLibrary
        return AnimationLibrary
    if name == "AnimatedCharacter":
        from .character import AnimatedCharacter
        return AnimatedCharacter
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
