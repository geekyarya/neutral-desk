"""Original background music bed + transition whooshes, mixed under the voice (generated, so no copyright)."""
import numpy as np

# a calm, hopeful news-bed progression: C - G - Am - F (two bars each)
CHORDS = [(261.63, 329.63, 392.00), (196.00, 246.94, 293.66), (220.00, 261.63, 329.63), (174.61, 220.00, 261.63)]


def _env(n, sr, attack, release):
    e = np.ones(n, np.float32)
    a, r = int(sr * attack), int(sr * release)
    e[:a] = np.linspace(0, 1, a)
    e[-r:] = np.linspace(1, 0, r)
    return e


TENSE = [(220.00, 261.63, 329.63), (174.61, 220.00, 261.63), (146.83, 174.61, 220.00), (164.81, 207.65, 246.94)]


def music_bed(seconds, sr, bpm=92, style="calm"):
    chords = TENSE if style == "tense" else CHORDS
    beat = 60 / bpm
    bar = 4 * beat
    out = np.zeros(int(sr * (seconds + bar * 2)), np.float32)
    t_chord = bar * 2
    n = int(sr * t_chord)
    tt = np.arange(n) / sr
    k = 0
    while k * t_chord < seconds + t_chord:
        root = chords[k % len(chords)]
        start = int(k * t_chord * sr)
        # soft pad: triad + octave, slightly detuned for warmth
        pad = sum(np.sin(2 * np.pi * f * tt) + 0.6 * np.sin(2 * np.pi * f * 1.003 * tt) for f in root)
        pad += 0.5 * np.sin(2 * np.pi * root[0] / 2 * tt)
        m = min(n, len(out) - start)
        if m <= 0:
            break
        out[start:start + m] += (0.12 * pad * _env(n, sr, 0.8, 0.8))[:m]
        # gentle plucked arpeggio on eighth notes
        notes = [root[0] * 2, root[1] * 2, root[2] * 2, root[1] * 2]
        step = beat / 2
        for j in range(int(t_chord / step)):
            f = notes[j % len(notes)]
            m = int(sr * 0.5)
            pt = np.arange(m) / sr
            pluck = np.sin(2 * np.pi * f * pt) * np.exp(-pt * 9) * np.minimum(pt / 0.004, 1)
            i0 = start + int(j * step * sr)
            if i0 < len(out):
                out[i0:i0 + m] += 0.05 * pluck[: len(out) - i0]
        if style == "tense":  # pounding kick on every beat
            kn = int(sr * 0.25)
            kt = np.arange(kn) / sr
            kick = np.sin(2 * np.pi * (45 + 80 * np.exp(-kt * 30)) * kt) * np.exp(-kt * 12)
            for j in range(int(t_chord / beat)):
                i0 = start + int(j * beat * sr)
                if i0 < len(out):
                    out[i0:i0 + kn] += 0.35 * kick[: len(out) - i0]
        k += 1
    return out[: int(sr * seconds)]


def whoosh(sr, dur=0.5):
    n = int(sr * dur)
    noise = np.random.default_rng(3).standard_normal(n).astype(np.float32)
    # sweep a simple low-pass upward, with a swell-and-fade envelope
    out, y = np.zeros(n, np.float32), 0.0
    for i in range(n):
        a = 0.02 + 0.5 * (i / n)
        y += a * (noise[i] - y)
        out[i] = y
    env = np.sin(np.linspace(0, np.pi, n)) ** 2
    return out * env * 0.5


def hit(sr, dur=1.2):
    """A dramatic TV 'dhan!': deep boom + noise burst + a falling tone."""
    t = np.arange(int(sr * dur)) / sr
    boom = np.sin(2 * np.pi * (40 + 90 * np.exp(-t * 18)) * t) * np.exp(-t * 3.5)
    burst = np.random.default_rng(9).standard_normal(len(t)) * np.exp(-t * 25) * 0.5
    fall = np.sin(2 * np.pi * (520 * np.exp(-t * 2.5)) * t) * np.exp(-t * 4) * 0.25
    return (boom + burst + fall).astype(np.float32) * 0.9


def mix(voice, sr, cues, volume=0.12, style="calm", hits=()):
    """voice: int16 array. cues: seconds where a transition whoosh plays; hits: seconds for a 'dhan!'.
    Music ducks under speech."""
    v = voice.astype(np.float32) / 32768
    music = music_bed(len(v) / sr, sr, bpm=118 if style == "tense" else 92, style=style)
    music = music / (np.abs(music).max() or 1)
    # duck: quieter while someone is speaking (smoothed loudness of the voice)
    win = int(sr * 0.3)
    loud = np.convolve(np.abs(v), np.ones(win) / win, mode="same")
    duck = 1 - 0.6 * np.clip(loud / (np.percentile(loud, 90) or 1), 0, 1)
    out = v + music * volume * duck
    w = whoosh(sr)
    for c in cues:
        i = int(c * sr)
        out[i:i + len(w)] += w[: len(out) - i] * 0.6
    hh = hit(sr)
    for c in hits:
        i = int(c * sr)
        out[i:i + len(hh)] += hh[: len(out) - i]
    out = np.tanh(out * 1.1) / np.tanh(1.1)  # soft limiter
    return (np.clip(out, -1, 1) * 32767).astype(np.int16)
