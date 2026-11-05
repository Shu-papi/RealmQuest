"""
music.py - Background music that fits where the hero is (files in audio/music/).

    music = Music()
    music.set_volume(0.56)                 # 0.0 - 1.0 (Settings: master x music)
    music.play(pick_place(...))            # every frame; only changes when the place changes
    music.update(dt)                       # finishes cross-fades

Change which track plays where in TRACKS. A missing file or no sound device is ignored.
"""
from __future__ import annotations

from pathlib import Path

import pygame

MUSIC_DIR = Path(__file__).resolve().parents[2] / "audio" / "music"

TRACKS = {
    "menu":      "Fantasy Menu Theme.mp3",                    # home, name, class select, victory
    "village":   "medieval.mp3",                              # Oakwood by day
    "shop":      "RPG For Wenches, Ale, and LOOT!!mp3.mp3",   # haggling with Torvin and Wren
    "wilds":     "in_search_of_the_philosophers_stone.mp3",   # exploring the vale by day
    "night":     "mysterious_calm.mp3",                       # the vale after dark
    "battle":    "battleThemeA.mp3",                          # night raids, champions, caravans
    "goblin":    "mysterious_calm.mp3",                       # Goblin Dungeon + goblin caves
    "berserker": "Ruins Of Empire.mp3",                       # Berserker ruins + ruin caves
    "lich":      "BGM_Snow_Theme_Loop.mp3",                   # Lich King's barrows + bone caves
    "boss":      "battleThemeA.mp3",                          # any boss fight
}
FAMILY_PLACE = {1: "goblin", 2: "berserker", 3: "lich"}
FADE_OUT = 0.6
FADE_IN_MS = 900


def pick_place(*, state="playing", mode="village", victory=False, shop=False, raid=False,
               event_near=False, night=0.0, in_village=True, family=1, boss=False):
    """Which entry of TRACKS fits the moment. Plain values in, so it is easy to test."""
    if state != "playing" or victory:
        return "menu"
    if mode == "village":
        if shop:
            return "shop"
        if raid or event_near:
            return "battle"
        if night >= 0.55:
            return "night"
        return "village" if in_village else "wilds"
    if boss:
        return "boss"
    return FAMILY_PLACE.get(family, "goblin")


class Music:
    def __init__(self, tracks=None, folder=MUSIC_DIR):
        self.tracks = dict(TRACKS if tracks is None else tracks)
        self.folder = Path(folder)
        self.place = None              # what was asked for last
        self.file = None               # what is playing (two places can share a file)
        self.pending = None            # file waiting for the fade-out to finish
        self.wait = 0.0
        self.volume = 0.7
        try:
            if not pygame.mixer.get_init():
                pygame.mixer.init()
            self.ok = bool(pygame.mixer.get_init())
        except Exception:
            self.ok = False

    def set_volume(self, volume):
        self.volume = max(0.0, min(1.0, float(volume)))
        if self.ok:
            try:
                pygame.mixer.music.set_volume(self.volume)
            except Exception:
                pass

    def play(self, place):
        if place == self.place:
            return
        self.place = place
        name = self.tracks.get(place)
        path = self.folder / name if name else None
        if path is not None and not path.is_file():
            path = None
        target = str(path) if path else None
        if target == self.file and self.pending is None:
            return                     # same song for the new place: keep it going
        self.pending, self.wait = (target or ""), FADE_OUT
        if self.ok and self.file:
            try:
                pygame.mixer.music.fadeout(int(FADE_OUT * 1000))
            except Exception:
                pass
        else:
            self.wait = 0.0

    def update(self, dt):
        if self.pending is None:
            return
        self.wait -= dt
        if self.wait > 0:
            return
        target, self.pending = self.pending, None
        self.file = target or None
        if not self.ok:
            return
        try:
            if not target:
                pygame.mixer.music.stop()
                return
            pygame.mixer.music.load(target)
            pygame.mixer.music.set_volume(self.volume)
            pygame.mixer.music.play(loops=-1, fade_ms=FADE_IN_MS)
        except Exception:
            self.file = None

    def stop(self):
        self.place = None
        self.pending = None
        self.file = None
        if self.ok:
            try:
                pygame.mixer.music.stop()
            except Exception:
                pass
