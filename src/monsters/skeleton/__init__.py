"""The skeleton family: warrior, archer, brute and acolyte. All reuse the Monster base class."""
from .acolyte import SkeletonAcolyte
from .archer import SkeletonArcher
from .brute import SkeletonBrute
from .warrior import SkeletonWarrior

__all__ = ["SkeletonWarrior", "SkeletonArcher", "SkeletonBrute", "SkeletonAcolyte"]
