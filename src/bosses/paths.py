"""
paths.py - One place that knows where things are in the repo.

    src/bosses/paths.py         <- this file
    assets/bosses/<boss_name>/  <- each boss's artwork
"""
import os

BOSSES_DIR = os.path.dirname(os.path.abspath(__file__))     # src/bosses
SRC_DIR = os.path.dirname(BOSSES_DIR)                       # src
REPO_ROOT = os.path.dirname(SRC_DIR)                        # the repo root


def asset_dir(boss_name):
    """Folder holding a boss's artwork, e.g. asset_dir("lich_king")."""
    return os.path.join(REPO_ROOT, "assets", "bosses", boss_name)
