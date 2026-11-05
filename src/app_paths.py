"""
app_paths.py - where the game keeps things, in development and in the built .exe.

    frozen()      True inside the PyInstaller build (RealmQuest.exe)
    game_dir()    the repo root in development; the folder holding RealmQuest.exe when built
                  (assets/, audio/, config/ sit there in both cases)
    user_dir()    where saves and the crash log go: the repo root in development,
                  %APPDATA%/RealmQuest when built (always writable, survives reinstalling the game)

The built game's modules live in RealmQuest/_internal/<package>/..., so every module that finds the repo
root as "two folders above me" already lands on the .exe's folder: build_exe.bat copies the data there.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

APP_NAME = "RealmQuest"


def frozen() -> bool:
    return bool(getattr(sys, "frozen", False))


def game_dir() -> Path:
    if frozen():
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parents[1]


def user_dir() -> Path:
    if not frozen():
        return game_dir()
    base = os.environ.get("APPDATA") or os.path.join(os.path.expanduser("~"), "AppData", "Roaming")
    path = Path(base) / APP_NAME
    try:
        path.mkdir(parents=True, exist_ok=True)
    except OSError:
        path = game_dir()
    return path
