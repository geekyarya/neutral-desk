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


def draw_parrot(mouth=0, blink=False, w=420, h=520):
    """Mitthu Bhai: a green parrot anchor with round glasses and a red bow tie. mouth: 0 closed .. 2 open."""
    img = Image.new("RGBA", (w * S, h * S), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    cx = w // 2
    line = (25, 60, 35)
    green, dark, belly = (70, 180, 90), (40, 135, 70), (170, 225, 120)

    def oval(x, y, rx, ry, fill, outline=line, width=4):
        d.ellipse([(x - rx) * S, (y - ry) * S, (x + rx) * S, (y + ry) * S], fill=fill,
                  outline=outline, width=width * S if outline else 0)

    # body, wings, belly
    oval(cx, 420, 135, 150, green)
    oval(cx - 118, 410, 48, 105, dark)
    oval(cx + 118, 410, 48, 105, dark)
    oval(cx, 440, 82, 110, belly, outline=None)
    # bow tie
    _poly(d, [(cx - 52, 300), (cx - 6, 318), (cx - 52, 338)], (220, 40, 55))
    _poly(d, [(cx + 52, 300), (cx + 6, 318), (cx + 52, 338)], (220, 40, 55))
    oval(cx, 318, 13, 13, (190, 25, 45), outline=None)
    # head + crest feathers
    for fx, fy, r in ((-28, 72, 26), (6, 58, 30), (40, 72, 24)):
        oval(cx + fx, fy, r * 0.7, r * 1.3, dark)
    oval(cx, 185, 128, 122, green)
    oval(cx - 92, 215, 30, 22, (255, 120, 120), outline=None)  # rosy cheeks
    oval(cx + 92, 215, 30, 22, (255, 120, 120), outline=None)
    # eyes behind round glasses
    for ex in (cx - 52, cx + 52):
        oval(ex, 160, 40, 40, (255, 255, 255))
        if blink:
            _line(d, [(ex - 26, 162), (ex, 168), (ex + 26, 162)], line, 6)
        else:
            oval(ex + 6, 162, 17, 19, (20, 20, 25), outline=None)
            oval(ex + 12, 154, 6, 6, (255, 255, 255), outline=None)
        d.ellipse([(ex - 46) * S, (160 - 46) * S, (ex + 46) * S, (160 + 46) * S], outline=(30, 30, 35), width=7 * S)
    _line(d, [(cx - 8, 158), (cx + 8, 158)], (30, 30, 35), 6)  # glasses bridge
    # beak: the lower half drops open with the voice
    gap = (0, 12, 24)[mouth]
    if mouth:
        oval(cx, 252 + gap / 2, 24, 6 + gap / 2, (150, 30, 40))  # inside of the beak
        oval(cx, 256 + gap * 0.7, 13, 3 + gap / 4, (240, 110, 120), outline=None)  # tongue
    _poly(d, [(cx - 24, 250 + gap), (cx + 24, 250 + gap), (cx + 9, 274 + gap), (cx - 9, 274 + gap)], (245, 170, 40))
    _line(d, [(cx - 24, 250 + gap), (cx - 9, 274 + gap), (cx + 9, 274 + gap), (cx + 24, 250 + gap)], line, 4)
    _poly(d, [(cx - 40, 205), (cx + 40, 205), (cx + 36, 230), (cx + 6, 262), (cx - 6, 262), (cx - 36, 230)],
          (255, 200, 60))
    _line(d, [(cx - 40, 205), (cx - 36, 230), (cx - 6, 262), (cx + 6, 262), (cx + 36, 230), (cx + 40, 205)], line, 4)

    img = img.resize((w, h), Image.LANCZOS)
    shadow = Image.new("RGBA", img.size, (0, 0, 0, 0))
    shadow.putalpha(img.getchannel("A").point(lambda a: a * 0.35).filter(ImageFilter.GaussianBlur(10)))
    out = Image.new("RGBA", img.size, (0, 0, 0, 0))
    out.alpha_composite(shadow, (6, 6))
    out.alpha_composite(img)
    return out


def draw_lion(mouth=0, blink=False, w=420, h=520, cool=False):
    """Babbar Bhai, a cartoon lion anchor in a suit.
    cool=True: calm, sunglasses on.  cool=False: shouting, face red with anger, furious brows, vein and steam."""
    import math
    img = Image.new("RGBA", (w * S, h * S), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    cx, hy = w // 2, 200
    line = (60, 30, 15)
    angry = not cool
    face = (232, 92, 62) if angry else (240, 175, 70)
    ear = (215, 80, 55) if angry else (230, 160, 60)
    mane_out = (140, 45, 25) if angry else (150, 75, 28)
    mane_in = (165, 60, 30) if angry else (180, 95, 38)
    muzzle = (250, 175, 150) if angry else (252, 225, 178)

    def oval(x, y, rx, ry, fill, outline=line, width=4):
        d.ellipse([(x - rx) * S, (y - ry) * S, (x + rx) * S, (y + ry) * S], fill=fill,
                  outline=outline, width=width * S if outline else 0)

    # suit, shirt, tie, lapels
    _poly(d, [(cx - 182, h), (cx - 168, 400), (cx - 92, 356), (cx + 92, 356), (cx + 168, 400), (cx + 182, h)],
          (38, 42, 58))
    _poly(d, [(cx - 50, 356), (cx + 50, 356), (cx, 452)], (242, 242, 248))
    _poly(d, [(cx - 50, 356), (cx - 98, 366), (cx - 60, 500), (cx - 10, 452)], (52, 58, 78))
    _poly(d, [(cx + 50, 356), (cx + 98, 366), (cx + 60, 500), (cx + 10, 452)], (52, 58, 78))
    _poly(d, [(cx - 13, 364), (cx + 13, 364), (cx + 17, 440), (cx, 464), (cx - 17, 440)], (200, 24, 34))
    # fluffy mane: two rings of rounded tufts
    for r, n, col, sz in ((168, 22, mane_out, 40), (140, 18, mane_in, 36)):
        for k in range(n):
            a = 2 * math.pi * (k + 0.5 * (r == 140)) / n
            oval(cx + r * math.cos(a), hy + 12 + r * 0.95 * math.sin(a), sz, sz, col, outline=None)
    oval(cx, hy + 12, 140, 134, mane_in, outline=None)
    # ears + face with soft cheek shading
    for ex in (cx - 92, cx + 92):
        oval(ex, hy - 92, 32, 32, ear)
        oval(ex, hy - 90, 16, 16, (250, 200, 160), outline=None)
    oval(cx, hy + 15, 114, 114, face)
    oval(cx - 70, hy + 45, 30, 20, (255, 120, 110) if not angry else (200, 40, 30), outline=None)
    oval(cx + 70, hy + 45, 30, 20, (255, 120, 110) if not angry else (200, 40, 30), outline=None)
    oval(cx, hy + 72, 72, 50, muzzle, outline=None)
    for k in (-1, 1):  # whisker dots
        for j in range(3):
            oval(cx + k * (34 + j * 12), hy + 72 + (j % 2) * 10, 3, 3, (110, 60, 40), outline=None)
    # eyes / sunglasses / brows
    if cool:
        for side in (-1, 1):
            ex = cx + side * 46
            d.rounded_rectangle([(ex - 40) * S, (hy - 26) * S, (ex + 40) * S, (hy + 14) * S], radius=16 * S,
                                fill=(18, 18, 24), outline=(70, 70, 80), width=3 * S)
            _poly(d, [(ex - 28, hy - 18), (ex - 8, hy - 18), (ex - 24, hy + 2)], (95, 115, 150))  # shine
            _line(d, [(ex - 30, hy - 44), (ex + 30, hy - 46)], (100, 50, 20), 10)  # relaxed brows
        _line(d, [(cx - 6, hy - 10), (cx + 6, hy - 10)], (18, 18, 24), 7)
    else:
        for side in (-1, 1):
            ex = cx + side * 45
            if blink:
                _line(d, [(ex - 20, hy - 5), (ex + 20, hy - 5)], line, 6)
            else:
                oval(ex, hy - 5, 21, 17, (255, 255, 255))
                oval(ex - side * 4, hy - 1, 8, 8, (20, 15, 10), outline=None)
                _line(d, [(ex - 14, hy - 12), (ex - 4, hy - 4)], (230, 60, 60), 2)  # bloodshot
            _line(d, [(ex + side * 36, hy - 54), (ex - side * 24, hy - 20)], (90, 25, 10), 14)  # furious brows
        vx, vy = cx + 72, hy - 72  # anger vein
        for dx, dy in ((-1, -1), (1, -1), (-1, 1), (1, 1)):
            _line(d, [(vx + dx * 6, vy + dy * 6), (vx + dx * 18, vy + dy * 6), (vx + dx * 18, vy + dy * 18)],
                  (255, 230, 60), 6)
        for sx, sy in ((cx - 128, hy - 128), (cx + 128, hy - 128)):  # steam puffs from the ears
            for j, (ox, oy, r) in enumerate(((0, 0, 16), (-12 if sx < cx else 12, -22, 13), (0, -42, 10))):
                oval(sx + ox, sy + oy, r, r, (245, 245, 250), outline=None)
    # nose + mouth (smirk when calm and closed, roaring when open)
    _poly(d, [(cx - 22, hy + 42), (cx + 22, hy + 42), (cx, hy + 64)], (95, 45, 35))
    gap = (6, 22, 36)[mouth]
    if mouth == 0 and cool:
        _line(d, [(cx - 34, hy + 84), (cx, hy + 92), (cx + 34, hy + 80)], line, 5)
    else:
        d.chord([(cx - 50) * S, (hy + 66) * S, (cx + 50) * S, (hy + 74 + gap * 1.5) * S], 0, 180,
                fill=(120, 20, 25), outline=line, width=4 * S)
        if mouth:
            for tx in (cx - 30, cx + 18):  # fangs
                _poly(d, [(tx, hy + 72), (tx + 12, hy + 72), (tx + 6, hy + 72 + 10 + gap / 4)], (255, 255, 255))
            oval(cx, hy + 78 + gap * 0.9, 22, 6 + gap / 6, (230, 90, 100), outline=None)
    img = img.resize((w, h), Image.LANCZOS)
    shadow = Image.new("RGBA", img.size, (0, 0, 0, 0))
    shadow.putalpha(img.getchannel("A").point(lambda a: a * 0.35).filter(ImageFilter.GaussianBlur(10)))
    out = Image.new("RGBA", img.size, (0, 0, 0, 0))
    out.alpha_composite(shadow, (6, 6))
    out.alpha_composite(img)
    return out


CHARACTERS = {"anchor": draw_anchor, "parrot": draw_parrot, "lion": draw_lion}


def sprites(w=420, h=520, character="anchor", cool=False):
    draw = CHARACTERS.get(character, draw_anchor)
    if character == "lion":
        return {(m, b): draw_lion(m, b, w, h, cool) for m in (0, 1, 2) for b in (False, True)}
    return {(m, b): draw(m, b, w, h) for m in (0, 1, 2) for b in (False, True)}


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
