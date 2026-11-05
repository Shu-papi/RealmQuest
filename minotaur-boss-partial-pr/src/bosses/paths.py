"""STAND-IN (rebuilt so the partial PR runs on its own): where a boss keeps its art and sounds.
If your real repo already has bosses/paths.py, keep yours and delete this one."""
import os

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def asset_dir(name):
    """assets/bosses/<name>/ at the repo root."""
    return os.path.join(ROOT, "assets", "bosses", name)
