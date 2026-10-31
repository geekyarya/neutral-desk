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
    """Babbar Bhai: a sleek cartoon lion anchor in a suit.
    cool=True: calm, aviator sunglasses.  cool=False: angry, red face, furious almond eyes, vein and steam."""
    import math
    img = Image.new("RGBA", (w * S, h * S), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    cx, hy = w // 2, 196
    line = (55, 25, 12)
    angry = not cool
    face = (226, 96, 64) if angry else (236, 170, 74)
    face_lt = (246, 160, 130) if angry else (250, 220, 165)
    mane_dark = (120, 38, 22) if angry else (122, 62, 24)
    mane = (160, 58, 30) if angry else (168, 92, 34)

    def P(pts):
        return [(x * S, y * S) for x, y in pts]

    def shape(t_steps, fn):
        return [fn(2 * math.pi * k / t_steps) for k in range(t_steps)]

    def head_pt(t, scale=1.0):
        low = max(0.0, math.sin(t))  # 0 on top half, up to 1 at the chin
        rx = 98 * (1 - 0.5 * low ** 1.4) * scale
        ry = (98 + 42 * low) * scale
        return cx + rx * math.cos(t), hy + ry * math.sin(t)

    # suit, shirt, lapels, tie
    _poly(d, [(cx - 182, h), (cx - 168, 404), (cx - 92, 362), (cx + 92, 362), (cx + 168, 404), (cx + 182, h)],
          (34, 38, 54))
    _poly(d, [(cx - 46, 362), (cx + 46, 362), (cx, 452)], (242, 242, 248))
    _poly(d, [(cx - 46, 362), (cx - 96, 372), (cx - 58, 505), (cx - 8, 452)], (50, 56, 76))
    _poly(d, [(cx + 46, 362), (cx + 96, 372), (cx + 58, 505), (cx + 8, 452)], (50, 56, 76))
    _poly(d, [(cx - 12, 370), (cx + 12, 370), (cx + 16, 444), (cx, 466), (cx - 16, 444)], (200, 24, 34))
    # flowing mane: pointed locks swept back, longer on top and sides, framing a narrow chin
    for col, sc, n, twist in ((mane_dark, 1.62, 24, 0.10), (mane, 1.42, 22, 0.16)):
        pts = []
        for k in range(n):
            t = 2 * math.pi * k / n
            tt = t + twist
            for frac, r in ((0.0, 1.0), (0.5, 1.22)):  # valley, then tip
                ang = tt + frac * 2 * math.pi / n
                short = 1 - 0.22 * max(0.0, math.sin(ang)) ** 2  # shorter under the chin so the tie shows
                bx, by = head_pt(ang, sc * (r if frac else 1.0) * short)
                pts.append((bx, by + 10))
        _poly(d, pts, col)
    # ears
    for side in (-1, 1):
        ex = cx + side * 74
        _poly(d, [(ex - 26, hy - 64), (ex + side * 6, hy - 118), (ex + 26, hy - 70)], face)
        _poly(d, [(ex - 12, hy - 72), (ex + side * 4, hy - 102), (ex + 12, hy - 76)], face_lt)
    # tapered face with an outline, lighter snout and nose bridge
    d.polygon(P(shape(72, lambda t: head_pt(t, 1.04))), fill=line)
    d.polygon(P(shape(72, head_pt)), fill=face)
    d.polygon(P([(cx - 16, hy - 70), (cx + 16, hy - 70), (cx + 30, hy + 40), (cx - 30, hy + 40)]), fill=face_lt)
    d.ellipse([(cx - 58) * S, (hy + 30) * S, (cx + 58) * S, (hy + 124) * S], fill=face_lt)
    for k in (-1, 1):  # whisker dots
        for j in range(3):
            r = 3
            x, y = cx + k * (26 + j * 11), hy + 78 + (j % 2) * 9
            d.ellipse([(x - r) * S, (y - r) * S, (x + r) * S, (y + r) * S], fill=(110, 60, 40))
    # eyes: aviator sunglasses when calm, furious almond eyes when angry
    if cool:
        frame, lens = (14, 14, 18), (34, 40, 58)
        for side in (-1, 1):
            ex = cx + side * 44
            _line(d, [(ex + side * 34, hy - 22), (ex + side * 70, hy - 30)], frame, 7)  # arm to the ear
            outer = [(ex - side * 34, hy - 30), (ex + side * 40, hy - 32), (ex + side * 38, hy - 4),
                     (ex + side * 26, hy + 14), (ex - side * 22, hy + 14), (ex - side * 34, hy)]
            inner = [(ex - side * 28, hy - 24), (ex + side * 34, hy - 26), (ex + side * 32, hy - 5),
                     (ex + side * 22, hy + 8), (ex - side * 19, hy + 8), (ex - side * 28, hy - 2)]
            d.polygon(P(outer), fill=frame)
            d.polygon(P(inner), fill=lens)
            d.polygon(P([(ex - side * 22, hy - 22), (ex - side * 10, hy - 22), (ex - side * 22, hy + 4),
                         (ex - side * 28, hy + 2)]), fill=(120, 135, 165))  # glare streak
            d.polygon(P([(ex + side * 2, hy - 23), (ex + side * 8, hy - 23), (ex - side * 6, hy + 6),
                         (ex - side * 12, hy + 6)]), fill=(80, 92, 118))
            _line(d, [(ex - side * 30, hy - 48), (ex + side * 36, hy - 46)], (95, 45, 18), 9)  # relaxed brows
        _line(d, [(cx - 12, hy - 22), (cx, hy - 26), (cx + 12, hy - 22)], frame, 7)  # bridge
    else:
        for side in (-1, 1):
            ex = cx + side * 42
            if blink:
                _line(d, [(ex - 20, hy - 6), (ex + 20, hy - 6)], line, 6)
            else:
                d.polygon(P([(ex - side * 22, hy - 4), (ex, hy - 18), (ex + side * 24, hy - 12), (ex + side * 18, hy + 4),
                             (ex - side * 2, hy + 8)]), fill=(255, 245, 200))
                d.ellipse([(ex - 7) * S, (hy - 11) * S, (ex + 7) * S, (hy + 3) * S], fill=(20, 15, 10))
            _line(d, [(ex + side * 34, hy - 46), (ex - side * 24, hy - 18)], (80, 20, 8), 12)  # furious brows
        vx, vy = cx + 64, hy - 70  # anger vein
        for dx, dy in ((-1, -1), (1, -1), (-1, 1), (1, 1)):
            _line(d, [(vx + dx * 5, vy + dy * 5), (vx + dx * 15, vy + dy * 5), (vx + dx * 15, vy + dy * 15)],
                  (255, 230, 60), 5)
        for sx, sy in ((cx - 112, hy - 112), (cx + 112, hy - 112)):  # steam from the ears
            for ox, oy, r in ((0, 0, 15), (-11 if sx < cx else 11, -21, 12), (0, -40, 9)):
                x, y = sx + ox, sy + oy
                d.ellipse([(x - r) * S, (y - r) * S, (x + r) * S, (y + r) * S], fill=(245, 245, 250))
    # nose + mouth
    d.polygon(P([(cx - 22, hy + 40), (cx + 22, hy + 40), (cx + 8, hy + 60), (cx - 8, hy + 60)]), fill=(80, 35, 28))
    gap = (5, 20, 34)[mouth]
    if mouth == 0:
        if cool:  # smirk
            _line(d, [(cx - 30, hy + 84), (cx - 4, hy + 90), (cx + 30, hy + 78)], line, 5)
        else:  # clenched snarl
            _line(d, [(cx - 30, hy + 84), (cx, hy + 80), (cx + 30, hy + 84)], line, 6)
            for tx in (cx - 22, cx + 14):
                _poly(d, [(tx, hy + 82), (tx + 9, hy + 82), (tx + 4, hy + 92)], (255, 255, 255))
    else:
        d.chord([(cx - 44) * S, (hy + 70) * S, (cx + 44) * S, (hy + 78 + gap * 1.5) * S], 0, 180,
                fill=(120, 20, 25), outline=line, width=4 * S)
        for tx in (cx - 28, cx + 18):  # fangs
            _poly(d, [(tx, hy + 76), (tx + 11, hy + 76), (tx + 5, hy + 76 + 9 + gap / 4)], (255, 255, 255))
        d.ellipse([(cx - 20) * S, (hy + 76 + gap * 0.8) * S, (cx + 20) * S, (hy + 88 + gap) * S],
                  fill=(230, 90, 100))
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
