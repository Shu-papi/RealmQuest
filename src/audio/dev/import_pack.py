"""
import_pack.py - Turns the "Classic Monster Sounds" pack (by Coucassi) into game sounds. DEV TOOL (needs numpy).

    python src/audio/dev/import_pack.py "path/to/Monster Sounds"            # build every sound in USED below
    python src/audio/dev/import_pack.py "path/to/Monster Sounds" roar_phase2 # just one
    python src/audio/dev/import_pack.py "path/to/Monster Sounds" --library   # ALSO convert every creature sound
                                                                             # (bat_attack.wav, orc_death.wav ...)
                                                                             # so any area or monster can use it

TERMS OF USE of the pack: free for commercial and non-commercial use, you may edit the sounds, credit Coucassi, and
DO NOT POST THE SOUNDS ANYWHERE WITHOUT THE AUTHOR'S PERMISSION. So do not commit the converted files (or the pack)
to a PUBLIC repository without asking. See assets/audio/CREDITS.md.

HOW TO CHANGE WHICH SOUND IS USED WHERE: edit USED. Each entry is
    "game sound name": {"parts": [(source, gain, start_seconds), ...], "max": seconds, "variants": [...]}
A source is a pack file ("Dragon/Dragon_Attack") or "synth:name" (the code-made sound from recipes.py, so a
real roar can be LAYERED on top of the synthesized rumble). "max" cuts the result off (with a fade).
Give "variants": [parts, parts, ...] to make name__v1, name__v2 ... instead.
"""
import os
import sys
import wave

SRC_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)

import numpy as np                                            # noqa: E402

from audio.dev import synth                                   # noqa: E402
from audio.dev.recipes import SFX                             # noqa: E402

ROOT = os.path.dirname(SRC_DIR)
SFX_DIR = os.path.join(ROOT, "assets", "audio", "sfx")

# -----------------------------------------------------------------------------------------------------------
# WHAT GOES WHERE  (the pack's names say what the author meant; here they are borrowed for other jobs)
# -----------------------------------------------------------------------------------------------------------
USED = {
    # the roars: a real dragon for phase 2, then a dragon AND a behemoth together for the enrage
    "roar_phase2": {"parts": [("Dragon/Dragon_Attack", 1.0, 0.0)], "max": 3.2},
    "roar_phase3": {"parts": [("Behemoth/Behemoth_Attack", 1.0, 0.0), ("Dragon/Dragon_Damage", 0.8, 0.15),
                              ("synth:roar_phase3", 0.35, 0.0)], "max": 4.4},
    # he rises: a behemoth clawing out of the earth under the synthesized bells and bones
    "lich_intro": {"parts": [("Behemoth/Behemoth_Emerge", 1.0, 0.0), ("synth:lich_intro", 0.8, 0.0)], "max": 4.2},
    # he dies: a dying dragon's cry under the rising souls
    "lich_death": {"parts": [("Dragon/Dragon_Death", 1.0, 0.0), ("synth:lich_death", 0.7, 0.0)], "max": 5.0},
    # the Soul Ward shatters: glass, a boom and a cry of pain (a dragon's "damage" sound)
    "ward_break": {"parts": [("synth:ward_break", 1.0, 0.0), ("Dragon/Dragon_Damage", 0.7, 0.2)], "max": 2.6},
    # his army: ghost wails for the chant and for the dead rising
    "summon_windup": {"parts": [("Ghost/Ghost_Attack", 1.0, 0.0), ("synth:summon_windup", 0.5, 0.0)], "max": 2.0},
    "summon_rise": {"parts": [("Ghost/Ghost_Emerge", 1.0, 0.0), ("synth:summon_rise", 0.7, 0.0)], "max": 2.4},
    # the skeleton brute: a behemoth's growl and grunts (no orc sounds: they sounded like pig squeals)
    "brute_windup": {"parts": [("Behemoth/Behemoth_Attack", 0.8, 0.0)], "max": 0.9},
    "brute_hit": {"variants": [[("Behemoth/Behemtoh_Damage", 1.0, 0.0)], [("Behemoth/Behemtoh_Damage", 1.0, 0.1), ("synth:brute_hit", 0.5, 0.0)]], "max": 0.55},
    "brute_shatter": {"variants": [[("Behemoth/Behemoth_Death", 0.8, 0.0), ("synth:brute_shatter", 1.0, 0.0)],], "max": 1.8},
}


# -----------------------------------------------------------------------------------------------------------

def read_pack_wav(path):
    """Any pack .wav (16 or 24 bit, mono or stereo) -> mono floats at the game's 22050 Hz."""
    with wave.open(path, "rb") as handle:
        frames, rate, channels, width = handle.getnframes(), handle.getframerate(), handle.getnchannels(), handle.getsampwidth()
        raw = handle.readframes(frames)
    if width == 2:
        x = np.frombuffer(raw, "<i2").astype(float) / 32768.0
    elif width == 3:
        b = np.frombuffer(raw, np.uint8).reshape(-1, 3).astype(np.int32)
        x = (((b[:, 0] | (b[:, 1] << 8) | (b[:, 2] << 16)) << 8) >> 8) / 8388608.0
    else:
        x = np.frombuffer(raw, "<i4").astype(float) / 2147483648.0
    if channels > 1:
        x = x.reshape(-1, channels).mean(axis=1)
    return resample(x, rate)


def resample(x, rate, target=synth.SR):
    if rate == target:
        return x
    try:
        from math import gcd
        from scipy.signal import resample_poly
        g = gcd(int(rate), target)
        return resample_poly(x, target // g, int(rate) // g)
    except ImportError:                                       # no scipy: filter crudely, then interpolate
        spectrum = np.fft.rfft(x)
        cutoff = int(len(spectrum) * (target / 2.0) / (rate / 2.0))
        spectrum[cutoff:] = 0
        x = np.fft.irfft(spectrum, len(x))
        n = int(len(x) * target / rate)
        return np.interp(np.linspace(0, len(x) - 1, n), np.arange(len(x)), x)


def tidy(x, peak=0.92):
    """Cut the silence at the start, then make the loudest point `peak` (some pack files are very quiet)."""
    loud = np.nonzero(np.abs(x) > 0.02 * (np.max(np.abs(x)) + 1e-9))[0]
    if len(loud):
        x = x[max(0, loud[0] - int(0.005 * synth.SR)):]
    return x / (np.max(np.abs(x)) + 1e-9) * peak


def load_source(pack, source):
    if source.startswith("synth:"):
        return SFX[source[6:]][0](seed=1)
    return tidy(read_pack_wav(os.path.join(pack, source + ".wav")))


def build(pack, parts, longest):
    layers = [(load_source(pack, source), start, gain) for source, gain, start in parts]
    mix = synth.layer(max(len(s) / synth.SR + st for s, st, _ in layers), layers)
    if longest:
        mix = mix[:int(longest * synth.SR)]
    return synth.finish(mix, 0.92, 0.003, 0.08)


def sfx_files_for(name):
    return [f for f in os.listdir(SFX_DIR) if f == name + ".wav" or (f.startswith(name + "__v") and f.endswith(".wav"))]


def make_used(pack, only=None):
    for name, spec in USED.items():
        if only and name not in only:
            continue
        for old in sfx_files_for(name):                       # replace the code-made version (and any old variants)
            os.remove(os.path.join(SFX_DIR, old))
        variants = spec.get("variants") or [spec["parts"]]
        for i, parts in enumerate(variants):
            filename = f"{name}.wav" if len(variants) == 1 else f"{name}__v{i + 1}.wav"
            sound = build(pack, parts, spec.get("max"))
            synth.write_wav(os.path.join(SFX_DIR, filename), sound)
            print(f"  {filename:<26} {len(sound) / synth.SR:5.2f}s  <- " + " + ".join(s for s, _, _ in parts))


def make_library(pack):
    """Every creature sound as  creature_kind.wav  (orc_death.wav, bat_emerge.wav ...), for other areas to use."""
    for folder in sorted(os.listdir(pack)):
        path = os.path.join(pack, folder)
        if not os.path.isdir(path):
            continue
        for filename in sorted(os.listdir(path)):
            if not filename.lower().endswith(".wav"):
                continue
            stem = filename[:-4].replace("Bonus_", "").replace("Behemtoh", "Behemoth").lower()
            name = stem if stem.startswith(folder.lower()) else f"{folder.lower()}_{stem}"
            sound = synth.finish(tidy(read_pack_wav(os.path.join(path, filename))), 0.92, 0.003, 0.05)
            synth.write_wav(os.path.join(SFX_DIR, name + ".wav"), sound)
            print(f"  {name + '.wav':<30} {len(sound) / synth.SR:5.2f}s")


def main():
    args = sys.argv[1:]
    if not args or not os.path.isdir(args[0]):
        print(__doc__)
        return
    pack, rest = args[0], args[1:]
    names = [a for a in rest if not a.startswith("-")]
    unknown = [n for n in names if n not in USED]
    if unknown:
        print("Not in USED:", ", ".join(unknown))
        return
    make_used(pack, names)
    if "--library" in rest:
        print("Library:")
        make_library(pack)


if __name__ == "__main__":
    main()
