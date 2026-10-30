"""Step 6: the AI anchor.

"puppet" mode draws an original illustrated anchor whose mouth follows the voice
loudness and who blinks naturally. Runs on any CPU, no downloads.
For a photoreal face use "lipsync" mode (colab/lipsync.ipynb).
"""
import random

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

SKIN = (178, 120, 86)
SKIN_SHADE = (150, 96, 66)
HAIR = (28, 22, 20)
SUIT = (30, 42, 68)
SUIT_LIGHT = (44, 60, 94)
SHIRT = (238, 240, 245)
TIE = (178, 34, 52)
LIP = (120, 52, 46)
MOUTH_IN = (60, 18, 22)

S = 2  # supersampling factor for smooth edges


def _e(d, cx, cy, rx, ry, fill):
    d.ellipse([(cx - rx) * S, (cy - ry) * S, (cx + rx) * S, (cy + ry) * S], fill=fill)


def _poly(d, pts, fill):
    d.polygon([(x * S, y * S) for x, y in pts], fill=fill)


def _line(d, pts, fill, w):
    d.line([(x * S, y * S) for x, y in pts], fill=fill, width=w * S, joint="curve")


def draw_anchor(mouth=0, blink=False, w=420, h=520):
    """mouth: 0 closed, 1 half open, 2 open."""
    img = Image.new("RGBA", (w * S, h * S), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    cx = w // 2

    # shoulders + suit
    d.rounded_rectangle([(cx - 185) * S, 378 * S, (cx + 185) * S, (h + 80) * S], radius=80 * S, fill=SUIT)
    # neck
    d.rectangle([(cx - 34) * S, 300 * S, (cx + 34) * S, 390 * S], fill=SKIN_SHADE)
    # shirt + tie
    _poly(d, [(cx - 52, 372), (cx + 52, 372), (cx, 470)], SHIRT)
    _poly(d, [(cx - 13, 384), (cx + 13, 384), (cx + 9, 400), (cx - 9, 400)], TIE)
    _poly(d, [(cx - 9, 400), (cx + 9, 400), (cx + 16, 460), (cx, 478), (cx - 16, 460)], TIE)
    # lapels
    _poly(d, [(cx - 52, 372), (cx - 95, 380), (cx - 62, 520), (cx - 8, 480)], SUIT_LIGHT)
    _poly(d, [(cx + 52, 372), (cx + 95, 380), (cx + 62, 520), (cx + 8, 480)], SUIT_LIGHT)
    _poly(d, [(cx - 52, 372), (cx - 26, 372), (cx - 8, 420), (cx - 30, 400)], SHIRT)
    _poly(d, [(cx + 52, 372), (cx + 26, 372), (cx + 8, 420), (cx + 30, 400)], SHIRT)

    # hair (back), ears, head
    _e(d, cx, 175, 112, 118, HAIR)
    _e(d, cx - 98, 215, 16, 26, SKIN_SHADE)
    _e(d, cx + 98, 215, 16, 26, SKIN_SHADE)
    _e(d, cx, 210, 98, 125, SKIN)
    # jaw shading
    d.chord([(cx - 98) * S, 90 * S, (cx + 98) * S, 335 * S], 30, 150, fill=SKIN_SHADE)
    _e(d, cx, 205, 96, 122, SKIN)
    # fringe
    d.chord([(cx - 104) * S, 70 * S, (cx + 110) * S, 250 * S], 180, 355, fill=HAIR)
    _poly(d, [(cx - 104, 160), (cx - 90, 160), (cx - 92, 215), (cx - 102, 205)], HAIR)
    _poly(d, [(cx + 110, 160), (cx + 92, 160), (cx + 94, 215), (cx + 106, 205)], HAIR)
    _e(d, cx + 30, 128, 70, 30, HAIR)

    # eyebrows
    _line(d, [(cx - 64, 168), (cx - 42, 162), (cx - 20, 166)], HAIR, 7)
    _line(d, [(cx + 20, 166), (cx + 42, 162), (cx + 64, 168)], HAIR, 7)
    # eyes
    for ex in (cx - 42, cx + 42):
        if blink:
            _line(d, [(ex - 16, 192), (ex, 196), (ex + 16, 192)], HAIR, 4)
        else:
            _e(d, ex, 192, 17, 11, (250, 250, 250))
            _e(d, ex, 192, 9, 9, (58, 38, 26))
            _e(d, ex, 192, 4, 4, (10, 10, 10))
            _e(d, ex + 3, 189, 2, 2, (255, 255, 255))
            _line(d, [(ex - 18, 189), (ex - 6, 182), (ex + 8, 182), (ex + 18, 188)], HAIR, 3)
    # nose
    _line(d, [(cx - 4, 205), (cx - 10, 238), (cx, 244), (cx + 8, 240)], SKIN_SHADE, 4)

    # mouth
    my = 272
    if mouth == 0:
        _line(d, [(cx - 26, my), (cx, my + 4), (cx + 26, my)], LIP, 5)
    else:
        oh = 9 if mouth == 1 else 18
        _e(d, cx, my + oh / 2, 24 if mouth == 1 else 27, oh, LIP)
        _e(d, cx, my + oh / 2, 19 if mouth == 1 else 22, oh - 4, MOUTH_IN)
        d.rectangle([(cx - 15) * S, (my - oh / 2 + 3) * S, (cx + 15) * S, (my - oh / 2 + 7) * S], fill=(245, 245, 245))
        if mouth == 2:
            _e(d, cx, my + oh - 4, 12, 5, (170, 70, 76))

    img = img.resize((w, h), Image.LANCZOS)
    # soft drop shadow so the anchor sits in the scene
    shadow = Image.new("RGBA", img.size, (0, 0, 0, 0))
    shadow.putalpha(img.getchannel("A").point(lambda a: a * 0.35).filter(ImageFilter.GaussianBlur(10)))
    out = Image.new("RGBA", img.size, (0, 0, 0, 0))
    out.alpha_composite(shadow, (6, 6))
    out.alpha_composite(img)
    return out


def sprites(w=420, h=520):
    return {(m, b): draw_anchor(m, b, w, h) for m in (0, 1, 2) for b in (False, True)}


def mouth_track(samples, sr, fps):
    """Loudness per video frame -> mouth state 0/1/2."""
    hop = sr / fps
    n = int(len(samples) / hop)
    x = samples.astype(np.float32)
    rms = np.array([np.sqrt(np.mean(x[int(i * hop):int((i + 1) * hop)] ** 2) + 1e-9) for i in range(n)])
    ref = np.percentile(rms[rms > 50], 90) if np.any(rms > 50) else 1.0
    level = rms / ref
    states = np.where(level > 0.55, 2, np.where(level > 0.18, 1, 0))
    # avoid jitter: a mouth shape holds for at least 2 frames
    for i in range(1, n - 1):
        if states[i] != states[i - 1] and states[i] != states[i + 1]:
            states[i] = states[i - 1]
    return states


def blink_track(n, fps, seed=7):
    rnd = random.Random(seed)
    out = np.zeros(n, dtype=bool)
    t = int(fps * rnd.uniform(1.5, 3))
    while t < n:
        out[t:t + 3] = True
        t += int(fps * rnd.uniform(2.5, 5.5))
    return out
