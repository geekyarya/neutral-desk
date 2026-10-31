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
BRIGHT = [(261.63, 329.63, 392.00), (293.66, 369.99, 440.00), (220.00, 277.18, 329.63), (196.00, 246.94, 293.66)]
DARK = [(110.00, 130.81, 164.81), (98.00, 116.54, 146.83), (103.83, 123.47, 155.56), (92.50, 110.00, 138.59)]

# every music mood: chords, tempo, and which layers play
STYLES = {
    "chill":    dict(chords=CHORDS, bpm=80, pad=0.10, arp=0.04, hat=0.0, kick=0.0, tick=0.0),   # lo-fi, relaxed
    "tense":    dict(chords=TENSE, bpm=118, pad=0.12, arp=0.05, hat=0.0, kick=0.35, tick=0.0),  # pounding, angry
    "upbeat":   dict(chords=BRIGHT, bpm=122, pad=0.09, arp=0.07, hat=0.10, kick=0.18, tick=0.0),  # good news, bouncy
    "suspense": dict(chords=DARK, bpm=72, pad=0.14, arp=0.0, hat=0.0, kick=0.0, tick=0.22),    # mystery, ticking clock
}
MUSIC_STYLES = tuple(STYLES) + ("none",)


def music_bed(seconds, sr, bpm=None, style="chill"):
    st = STYLES.get(style, STYLES["chill"])
    chords, bpm = st["chords"], bpm or st["bpm"]
    beat = 60 / bpm
    bar = 4 * beat
    out = np.zeros(int(sr * (seconds + bar * 2)), np.float32)
    t_chord = bar * 2
    n = int(sr * t_chord)
    tt = np.arange(n) / sr
    rng = np.random.default_rng(4)
    k = 0
    while k * t_chord < seconds + t_chord:
        root = chords[k % len(chords)]
        start = int(k * t_chord * sr)
        m = min(n, len(out) - start)
        if m <= 0:
            break
        # soft pad: triad + sub, slightly detuned for warmth
        pad = sum(np.sin(2 * np.pi * f * tt) + 0.6 * np.sin(2 * np.pi * f * 1.003 * tt) for f in root)
        pad += 0.5 * np.sin(2 * np.pi * root[0] / 2 * tt)
        out[start:start + m] += (st["pad"] * pad * _env(n, sr, 0.8, 0.8))[:m]
        if st["arp"]:  # plucked arpeggio on eighth notes
            notes = [root[0] * 2, root[1] * 2, root[2] * 2, root[1] * 2]
            step = beat / 2
            for j in range(int(t_chord / step)):
                f = notes[j % len(notes)]
                mm = int(sr * 0.5)
                pt = np.arange(mm) / sr
                pluck = np.sin(2 * np.pi * f * pt) * np.exp(-pt * 9) * np.minimum(pt / 0.004, 1)
                i0 = start + int(j * step * sr)
                if i0 < len(out):
                    out[i0:i0 + mm] += st["arp"] * pluck[: len(out) - i0]
        if st["kick"]:  # pounding kick on every beat
            kn = int(sr * 0.25)
            kt = np.arange(kn) / sr
            kick = np.sin(2 * np.pi * (45 + 80 * np.exp(-kt * 30)) * kt) * np.exp(-kt * 12)
            for j in range(int(t_chord / beat)):
                i0 = start + int(j * beat * sr)
                if i0 < len(out):
                    out[i0:i0 + kn] += st["kick"] * kick[: len(out) - i0]
        if st["hat"]:  # bouncy hi-hats on the off-beats
            hn = int(sr * 0.05)
            hat = rng.standard_normal(hn).astype(np.float32) * np.exp(-np.arange(hn) / sr * 90)
            for j in range(int(t_chord / beat * 2)):
                if j % 2 == 1:
                    i0 = start + int(j * beat / 2 * sr)
                    if i0 < len(out):
                        out[i0:i0 + hn] += st["hat"] * hat[: len(out) - i0]
        if st["tick"]:  # a ticking clock under a low drone
            tn = int(sr * 0.08)
            ct = np.arange(tn) / sr
            tick = np.sin(2 * np.pi * 1800 * ct) * np.exp(-ct * 70)
            for j in range(int(t_chord / beat)):
                i0 = start + int(j * beat * sr)
                if i0 < len(out):
                    out[i0:i0 + tn] += st["tick"] * tick[: len(out) - i0]
        k += 1
    return out[: int(sr * seconds)]


def music_track(spans, total, sr):
    """One continuous music track made of per-segment moods. spans: [(start_s, end_s, style)];
    style 'none'/None leaves silence. Each piece fades in and out so changes between moods are smooth."""
    out = np.zeros(int(total * sr) + sr, np.float32)
    for a, b, style in spans:
        if not style or style == "none" or b - a < 1.0:
            continue
        piece = music_bed(b - a + 0.8, sr, style=style)
        piece = piece / (np.abs(piece).max() or 1)
        fade = int(sr * 0.7)
        piece[:fade] *= np.linspace(0, 1, fade)
        piece[-fade:] *= np.linspace(1, 0, fade)
        i0 = int((a - 0.4) * sr) if a > 0.4 else 0
        j = min(len(out) - i0, len(piece))
        out[i0:i0 + j] += piece[:j]
    return out[: int(total * sr)]


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


def meme_pop(sr):
    """A short comedic 'bloop' with a low thud, played when a meme sticker pops up."""
    t = np.arange(int(sr * 0.45)) / sr
    bloop = np.sin(2 * np.pi * (700 * np.exp(-t * 7) + 120) * t) * np.exp(-t * 6)
    thud = np.sin(2 * np.pi * 55 * t) * np.exp(-t * 14)
    return ((bloop * 0.5 + thud * 0.7) * 0.8).astype(np.float32)


def mix(voice, sr, cues, volume=0.12, style="chill", hits=(), spans=None, memes=()):
    """voice: int16 array. cues: seconds for a transition whoosh; hits: seconds for a 'dhan!'; memes: seconds for
    a meme-sticker pop. Music: either one style for the whole piece, or per-segment `spans` [(start, end, style)]
    so each story gets the mood that fits it (and some get none). It ducks under speech."""
    v = voice.astype(np.float32) / 32768
    total = len(v) / sr
    if spans is None:
        spans = [(0.0, total, style)]
    music = music_track(spans, total, sr)
    music = np.pad(music, (0, max(0, len(v) - len(music))))[: len(v)]  # exactly as long as the voice
    # duck: quieter while someone is speaking (smoothed loudness of the voice)
    win = max(1, min(int(sr * 0.3), len(v)))
    loud = np.convolve(np.abs(v), np.ones(win) / win, mode="same")
    duck = 1 - 0.6 * np.clip(loud / (np.percentile(loud, 90) or 1), 0, 1)
    out = v + music * volume * duck
    def add(snd, t, gain=1.0):  # drop a sound effect at second t, clipped to the clip's length
        i = int(t * sr)
        if 0 <= i < len(out):
            n = min(len(snd), len(out) - i)
            out[i:i + n] += snd[:n] * gain

    w, hh, mp = whoosh(sr), hit(sr), meme_pop(sr)
    for c in cues:
        add(w, c, 0.6)
    for c in hits:
        add(hh, c)
    for c in memes:
        add(mp, c)
    out = np.tanh(out * 1.1) / np.tanh(1.1)  # soft limiter
    return (np.clip(out, -1, 1) * 32767).astype(np.int16)
