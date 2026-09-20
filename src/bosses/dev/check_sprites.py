"""
check_sprites.py - Checks a boss's sprite files for mistakes.

    python src/bosses/dev/check_sprites.py               checks lich_king
    python src/bosses/dev/check_sprites.py lich_king     same, by name
    python src/bosses/dev/check_sprites.py lich_king some/other/folder

Run this after saving new art. It tells you in plain words what is wrong
(wrong size, blurry pixels, marker colours that are slightly off, ...).

Every boss with PNG art has  src/bosses/<name>/art.py  that provides
ASSET_DIR and check_assets(folder)  (see lich_king/art.py).
"""
import importlib
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")

import pygame


def main():
    boss = sys.argv[1] if len(sys.argv) > 1 else "lich_king"
    try:
        art = importlib.import_module(f"bosses.{boss}.art")
    except ModuleNotFoundError:
        print(f"Could not find src/bosses/{boss}/art.py. Check the boss name.")
        return 1

    folder = sys.argv[2] if len(sys.argv) > 2 else art.ASSET_DIR
    pygame.init()
    print(f"Checking {boss} sprites in {folder}\n")

    names = list(getattr(art, "BODY_FILES", {}).values())
    if hasattr(art, "STAFF_FILE"):
        names.append(art.STAFF_FILE)
    for name in names:
        path = os.path.join(folder, name)
        if os.path.exists(path):
            w, h = pygame.image.load(path).get_size()
            print(f"  found    {name:22s} {w}x{h}")
        else:
            print(f"  missing  {name:22s} (optional: the game reuses another frame)")

    errors, warnings = art.check_assets(folder)
    print()
    for message in errors:
        print(f"  [PROBLEM] {message}")
    for message in warnings:
        print(f"  [warning] {message}")
    if not errors and not warnings:
        print(f"  All good! Look at him with:  python src/bosses/{boss}/preview.py --live")
    elif not errors:
        print("\n  No problems, just warnings. The game will run.")
    else:
        print(f"\n  {len(errors)} problem(s) to fix.")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
