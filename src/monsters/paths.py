"""
paths.py - One place that knows where monster files are in the repo.

    src/monsters/paths.py          <- this file
    assets/monsters/<name>/        <- each monster's artwork (frames.png + sprite.json)
"""
import os

MONSTERS_DIR = os.path.dirname(os.path.abspath(__file__))    # src/monsters
SRC_DIR = os.path.dirname(MONSTERS_DIR)                      # src
REPO_ROOT = os.path.dirname(SRC_DIR)                         # the repo root


def asset_dir(monster_name):
    """Folder holding a monster's artwork, e.g. asset_dir("skeleton_warrior")."""
    return os.path.join(REPO_ROOT, "assets", "monsters", monster_name)
