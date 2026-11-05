"""
synth.py - A tiny sound-building toolkit (DEV TOOL ONLY: the game itself never imports this).

The game plays ordinary .wav files from assets/audio/. These helpers are how those files were made, so the
sounds can be re-made or tweaked in code (see recipes.py and make_sounds.py). Needs numpy (dev machines only).

Everything is mono, 22050 Hz, and works on plain numpy arrays of floats between -1 and 1.
"""
import wave

import numpy as np

SR = 22050


# ----------------------------------------------------------------------------------------------------------
# basics
# ----------------------------------------------------------------------------------------------------------

def n_samples(seconds):
    return max(1, int(round(seconds * SR)))


def times(seconds):
    return np.arange(n_samples(seconds)) / SR


def rng(seed=0):
    return np.random.default_rng(int(seed))


def midi_hz(note):
    return 440.0 * 2.0 ** ((note - 69) / 12.0)


def noise(seconds, seed=0, color="white"):
    """White noise (std 0.5). 'pink' has more lows, 'brown' even more."""
    x = rng(seed).standard_normal(n_samples(seconds))
    if color != "white":
        spectrum = np.fft.rfft(x)
        f = np.arange(len(spectrum), dtype=float)
        f[0] = 1.0
        spectrum /= np.sqrt(f) if color == "pink" else f
        x = np.fft.irfft(spectrum, len(x))
    return x / (np.std(x) + 1e-12) * 0.5


def glide(f0, f1, seconds, curve="exp"):
    """A frequency curve from f0 to f1 (use it as the `freq` of osc())."""
    t = np.linspace(0.0, 1.0, n_samples(seconds))
    if curve == "exp":
        return f0 * (f1 / f0) ** t
    return f0 + (f1 - f0) * t


def _phase(freq, seconds=None, phase0=0.0):
    if np.isscalar(freq):
        freq = np.full(n_samples(seconds), float(freq))
    return phase0 + 2 * np.pi * np.cumsum(freq) / SR, np.asarray(freq)


def osc(kind, freq, seconds=None, phase0=0.0):
    """
    A tone. kind: sine | saw | square | tri. freq: a number (needs `seconds`) or an array from glide().
    The saw / square / tri are band-limited (no harsh aliasing).
    """
    phase, f = _phase(freq, seconds, phase0)
    if kind == "sine":
        return np.sin(phase)
    top = max(1, int(min(60, (SR * 0.45) / max(float(np.max(f)), 1.0))))
    out = np.zeros_like(phase)
    if kind == "saw":
        for k in range(1, top + 1):
            out += np.sin(k * phase) / k
        return out * (2 / np.pi)
    if kind == "square":
        for k in range(1, top + 1, 2):
            out += np.sin(k * phase) / k
        return out * (4 / np.pi) * 0.5
    if kind == "tri":
        for i, k in enumerate(range(1, top + 1, 2)):
            out += (-1) ** i * np.sin(k * phase) / k ** 2
        return out * (8 / np.pi ** 2)
    raise ValueError(kind)


# ----------------------------------------------------------------------------------------------------------
# envelopes
# ----------------------------------------------------------------------------------------------------------

def perc(seconds, attack=0.003, decay=0.1):
    """Quick attack then an exponential fade: the shape of anything struck."""
    t = times(seconds)
    return np.minimum(t / max(attack, 1e-4), 1.0) * np.exp(-t / max(decay, 1e-4))


def swell(seconds, peak=0.6, power=1.5):
    """Fades in to `peak` (0..1 of the length), then out."""
    u = np.linspace(0.0, 1.0, n_samples(seconds))
    up = np.clip(u / max(peak, 1e-4), 0, 1) ** power
    down = np.clip((1 - u) / max(1 - peak, 1e-4), 0, 1) ** power
    return np.minimum(up, down)


def ramp(seconds, a=0.0, b=1.0, power=1.0):
    return a + (b - a) * np.linspace(0.0, 1.0, n_samples(seconds)) ** power


def adsr(seconds, a=0.01, d=0.1, s=0.7, r=0.2):
    t = times(seconds)
    env = np.where(t < a, t / max(a, 1e-4), 1.0)
    env = np.where((t >= a) & (t < a + d), 1.0 - (1.0 - s) * (t - a) / max(d, 1e-4), env)
    env = np.where(t >= a + d, s, env)
    release = np.clip((seconds - t) / max(r, 1e-4), 0, 1)
    return env * release


def lfo(rate, seconds, depth=1.0, centre=0.0, phase0=0.0):
    return centre + depth * np.sin(2 * np.pi * rate * times(seconds) + phase0)


# ----------------------------------------------------------------------------------------------------------
# filters  (zero-phase FFT filters: smooth, no clicks)
# ----------------------------------------------------------------------------------------------------------

def _shape(x, response, pad=4096, cyclic=False):
    """Filter in the frequency domain. cyclic=True treats the sound as a LOOP (no padding), so it stays seamless."""
    padded = x if cyclic else np.concatenate([x, np.zeros(pad)])
    spectrum = np.fft.rfft(padded)
    freq = np.fft.rfftfreq(len(padded), 1.0 / SR)
    out = np.fft.irfft(spectrum * response(freq), len(padded))
    return out[:len(x)]


def lp(x, cutoff, order=2, cyclic=False):
    return _shape(x, lambda f: 1.0 / np.sqrt(1.0 + (f / cutoff) ** (2 * order)), cyclic=cyclic)


def hp(x, cutoff, order=2, cyclic=False):
    return _shape(x, lambda f: ((f / cutoff) ** order) / np.sqrt(1.0 + (f / cutoff) ** (2 * order)), cyclic=cyclic)


def bp(x, low, high, order=2, cyclic=False):
    return hp(lp(x, high, order, cyclic), low, order, cyclic)


def formant(x, centre, q=6.0, cyclic=False):
    """A narrow resonance at `centre` Hz: how a vowel ('aah') is carved out of a buzz."""
    def response(f):
        f = np.maximum(f, 1e-3)
        return 1.0 / (1.0 + (q * (f / centre - centre / f)) ** 2)
    return _shape(x, response, cyclic=cyclic)


def sweep_lp(x, cutoff):
    """A low-pass whose cutoff moves over time (`cutoff` is an array, one value per sample). Two poles."""
    a = 1.0 - np.exp(-2 * np.pi * np.clip(cutoff, 20, SR * 0.45) / SR)
    out = np.empty(len(x))
    y1 = y2 = 0.0
    for i in range(len(x)):
        y1 += a[i] * (x[i] - y1)
        y2 += a[i] * (y1 - y2)
        out[i] = y2
    return out


def sweep_bp(x, centre, width=0.6):
    """A band-pass that follows `centre` (array) - the classic whoosh. width: bandwidth in octaves."""
    low = sweep_lp(x, centre * 2 ** (width / 2))
    return low - sweep_lp(low, np.maximum(centre * 2 ** (-width / 2), 20))


def drive(x, amount=3.0):
    """Soft distortion: turns a clean tone into a snarl."""
    return np.tanh(x * amount) / np.tanh(amount)


# ----------------------------------------------------------------------------------------------------------
# space
# ----------------------------------------------------------------------------------------------------------

def impulse_response(seconds, damp=4000.0, seed=1):
    ir = noise(seconds, seed) * np.exp(-6.9 * times(seconds) / seconds)        # -60 dB at the end
    ir = lp(ir, damp, 1)
    ir[0] = 0.0
    return ir


def reverb(x, seconds=1.6, wet=0.3, damp=3500.0, seed=1, cyclic=False):
    """A stone-crypt echo. cyclic=True wraps the tail round to the start, so a music loop stays seamless."""
    ir = impulse_response(seconds, damp, seed)
    ir = ir / (np.sqrt(np.sum(ir ** 2)) + 1e-9) * 0.6
    if cyclic:
        padded = np.zeros(len(x))
        usable = min(len(ir), len(x))
        padded[:usable] = ir[:usable]
        wet_signal = np.fft.irfft(np.fft.rfft(x) * np.fft.rfft(padded), len(x))
        return x * (1.0 - wet * 0.5) + wet_signal * wet
    size = len(x) + len(ir)
    wet_signal = np.fft.irfft(np.fft.rfft(x, size) * np.fft.rfft(ir, size), size)
    out = np.concatenate([x, np.zeros(len(ir))]) * (1.0 - wet * 0.5)
    return out + wet_signal * wet


def echo(x, delay=0.18, feedback=0.4, repeats=4):
    out = np.concatenate([x, np.zeros(int(delay * SR * repeats) + 1)])
    for k in range(1, repeats + 1):
        shift = int(delay * SR * k)
        out[shift:shift + len(x)] += x * feedback ** k
    return out


# ----------------------------------------------------------------------------------------------------------
# putting sounds together
# ----------------------------------------------------------------------------------------------------------

def pad_to(x, seconds):
    size = n_samples(seconds)
    if len(x) >= size:
        return x[:size]
    return np.concatenate([x, np.zeros(size - len(x))])


def layer(seconds, parts):
    """Mix [(sound, start_seconds, gain), ...] into one buffer `seconds` long (anything longer is cut off)."""
    out = np.zeros(n_samples(seconds))
    for sound, start, gain in parts:
        i = int(round(start * SR))
        if i >= len(out) or i + len(sound) <= 0:
            continue
        a, b = max(0, -i), min(len(sound), len(out) - i)
        out[i + a:i + b] += sound[a:b] * gain
    return out


def add_wrapped(buffer, sound, start_seconds, gain=1.0):
    """Mix into a LOOP: whatever runs past the end wraps round to the beginning."""
    size = len(buffer)
    start = int(round(start_seconds * SR)) % size
    sound = sound[:size] * gain
    first = min(len(sound), size - start)
    buffer[start:start + first] += sound[:first]
    if first < len(sound):
        buffer[:len(sound) - first] += sound[first:]


def fade(x, fade_in=0.004, fade_out=0.012):
    x = x.copy()
    a, b = min(len(x), int(fade_in * SR)), min(len(x), int(fade_out * SR))
    if a > 0:
        x[:a] *= np.linspace(0, 1, a)
    if b > 0:
        x[-b:] *= np.linspace(1, 0, b)
    return x


def finish(x, peak=0.92, fade_in=0.004, fade_out=0.015, trim=True, punch=1.8):
    """Last step of every sound: no DC offset, trailing silence cut off, no clicks at the edges, loudest point = `peak`."""
    x = np.asarray(x, dtype=float)
    x = x - np.mean(x)
    if trim and fade_out > 0:                    # (loops use fade_out=0 and are never trimmed)
        loud = np.nonzero(np.abs(x) > 0.004 * (np.max(np.abs(x)) + 1e-9))[0]
        if len(loud):
            x = x[:min(len(x), int(loud[-1]) + int(0.03 * SR))]
    x = fade(x, fade_in, fade_out)
    top = float(np.max(np.abs(x))) + 1e-9
    if punch:                                    # gentle saturation: the same peak but a much louder, fuller sound
        x = np.tanh(x / top * punch) / np.tanh(punch)
        top = float(np.max(np.abs(x))) + 1e-9
    return x / top * peak


def write_wav(path, x):
    data = np.clip(np.asarray(x), -1.0, 1.0)
    pcm = (data * 32767.0).astype("<i2")
    with wave.open(path, "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(SR)
        handle.writeframes(pcm.tobytes())


def read_wav(path):
    with wave.open(path, "rb") as handle:
        frames = handle.readframes(handle.getnframes())
        rate = handle.getframerate()
    return np.frombuffer(frames, dtype="<i2").astype(float) / 32768.0, rate
