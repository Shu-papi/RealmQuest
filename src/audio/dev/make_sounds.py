"""
make_sounds.py - (Re)makes every sound file in assets/audio/ from the recipes. DEV TOOL (needs numpy).

    python src/audio/dev/make_sounds.py                 remake everything
    python src/audio/dev/make_sounds.py boss_hit        remake one sound (all its variants)
    python src/audio/dev/make_sounds.py --music         remake only the music
    python src/audio/dev/make_sounds.py --list          list the names
    python src/audio/dev/make_sounds.py --synth-only    remake even the sounds that are real recordings (import_pack.py)
    python src/audio/dev/make_sounds.py --report        check every file in assets/audio (length, loudness, clipping)

You do NOT need this to play the game: the finished .wav files are in assets/audio/ already.
Sounds with variants are saved as  name__v1.wav, name__v2.wav ...  and the game picks one at random.
"""
import os
import sys
import time

SRC_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)

import numpy as np                                            # noqa: E402

from audio.dev import synth                                   # noqa: E402
from audio.dev.import_pack import USED                        # noqa: E402
from audio.dev.music import TRACKS                            # noqa: E402
from audio.dev.recipes import SFX                             # noqa: E402

ROOT = os.path.dirname(SRC_DIR)
SFX_DIR = os.path.join(ROOT, "assets", "audio", "sfx")
MUSIC_DIR = os.path.join(ROOT, "assets", "audio", "music")


def sfx_filenames(name, variants):
    if variants == 1:
        return [f"{name}.wav"]
    return [f"{name}__v{i + 1}.wav" for i in range(variants)]


def make_sfx(only=None, synth_only=False):
    """Code-made sounds. Sounds that are real recordings (import_pack.USED) are left alone unless synth_only."""
    os.makedirs(SFX_DIR, exist_ok=True)
    for name, (recipe, variants) in SFX.items():
        if only and name not in only:
            continue
        if name in USED and not synth_only:
            print(f"  {name:<28} (real recording from the monster pack: skipped, use --synth-only to replace it)")
            continue
        for i, filename in enumerate(sfx_filenames(name, variants)):
            started = time.time()
            sound = recipe(seed=i * 17 + 1)
            synth.write_wav(os.path.join(SFX_DIR, filename), sound)
            print(f"  {filename:<28} {len(sound) / synth.SR:5.2f}s   ({time.time() - started:4.1f}s to make)")


def make_music():
    os.makedirs(MUSIC_DIR, exist_ok=True)
    for name, build in TRACKS.items():
        started = time.time()
        track = build()
        synth.write_wav(os.path.join(MUSIC_DIR, name + ".wav"), track)
        print(f"  {name + '.wav':<28} {len(track) / synth.SR:5.2f}s   ({time.time() - started:4.1f}s to make)")


def report():
    """One line per file: how long, how loud, whether it clips, and (for loops) whether the seam is smooth."""
    rows = 0
    for folder in (SFX_DIR, MUSIC_DIR):
        for filename in sorted(os.listdir(folder)):
            if not filename.endswith(".wav"):
                continue
            x, rate = synth.read_wav(os.path.join(folder, filename))
            peak = float(np.max(np.abs(x)))
            rms = float(np.sqrt(np.mean(x ** 2)))
            seam = abs(float(x[0]) - float(x[-1]))
            flag = "  CLIPS!" if peak >= 0.999 else ""
            print(f"{os.path.basename(folder)}/{filename:<28} {len(x) / rate:6.2f}s  peak {peak:.2f}  rms {rms:.3f}  "
                  f"edge jump {seam:.3f}{flag}")
            rows += 1
    print(f"{rows} files")


def main():
    args = sys.argv[1:]
    if "--list" in args:
        print("SFX:  ", ", ".join(SFX))
        print("MUSIC:", ", ".join(TRACKS))
        return
    if "--report" in args:
        report()
        return
    if "--music" in args:
        make_music()
        return
    synth_only = "--synth-only" in args
    names = [a for a in args if not a.startswith("-")]
    unknown = [n for n in names if n not in SFX and n not in TRACKS]
    if unknown:
        print("Unknown sound(s):", ", ".join(unknown), "(try --list)")
        return
    if names:
        make_sfx([n for n in names if n in SFX], synth_only)
        if any(n in TRACKS for n in names):
            os.makedirs(MUSIC_DIR, exist_ok=True)
            for n in names:
                if n in TRACKS:
                    synth.write_wav(os.path.join(MUSIC_DIR, n + ".wav"), TRACKS[n]())
        return
    print("Sound effects:")
    make_sfx(synth_only=synth_only)
    print("Music:")
    make_music()
    print("Done. Run with --report to check the files.")


if __name__ == "__main__":
    main()
