"""
paths.py - Where the sound files live.

    assets/audio/sfx/     one short .wav per sound  (name.wav, or name__v1.wav, name__v2.wav ... for variants)
    assets/audio/music/   one looping .wav per track
"""
import os

AUDIO_DIR = os.path.dirname(os.path.abspath(__file__))      # src/audio
SRC_DIR = os.path.dirname(AUDIO_DIR)                        # src
REPO_ROOT = os.path.dirname(SRC_DIR)                        # the repo root
SFX_DIR = os.path.join(REPO_ROOT, "assets", "audio", "sfx")
MUSIC_DIR = os.path.join(REPO_ROOT, "assets", "audio", "music")
