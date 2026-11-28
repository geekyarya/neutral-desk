"""Render long-form special episodes (case study, scam story, horror) with photos or generated scenes,
spoken captions, optional anchor window and, for horror, creepy grading, fog, flicker and synthesized sound effects."""
import math
import random
import wave
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageEnhance, ImageFilter

from . import anchor as anchor_mod
from .persona import persona
from .reel_render import caption_chunks
from .render import ACCENT, AMBER, WHITE, Layout, _concat_audio, _cover, _kenburns, _pip_sprites, encode
from .text import Font, wrap

FOG_SPEED = 0.35


# ---------------- sound effects (all synthesized, no copyright) ----------------

def _env(n, attack, decay, sr):
    t = np.arange(n) / sr
    return np.minimum(t / max(attack, 1e-3), 1) * np.exp(-t / max(decay, 1e-3))


def _noise(n, rng, lp=1):
    x = rng.standard_normal(n).astype(np.float32)
    if lp > 1:
        x = np.convolve(x, np.ones(lp, np.float32) / lp, mode="same")
    return x


def sfx_sound(kind, sr, rng):
    if kind == "creak":
        n = int(sr * 1.3)
        t = np.arange(n) / sr
        f = 140 + 90 * np.sin(2 * np.pi * 0.9 * t) + 60 * t
        w = np.sign(np.sin(2 * np.pi * np.cumsum(f) / sr)) * 0.5 + _noise(n, rng, 6) * 0.4
        return w * _env(n, 0.05, 0.6, sr) * 0.5
    if kind == "knock":
        out = np.zeros(int(sr * 1.4), np.float32)
        for k, at in enumerate((0.0, 0.32, 0.62)):
            n = int(sr * 0.18)
            thud = (_noise(n, rng, 30) * 3 + np.sin(2 * np.pi * 95 * np.arange(n) / sr)) * _env(n, 0.002, 0.05, sr)
            i = int(at * sr)
            out[i:i + n] += thud[: len(out) - i] * 0.7
        return out
    if kind == "footsteps":
        out = np.zeros(int(sr * 3.2), np.float32)
        for k in range(5):
            n = int(sr * 0.25)
            step = _noise(n, rng, 40) * 2.5 * _env(n, 0.004, 0.06, sr)
            i = int(k * 0.62 * sr)
            out[i:i + n] += step[: len(out) - i] * (0.45 + 0.05 * k)
        return out
    if kind == "whisper":
        n = int(sr * 2.6)
        w = _noise(n, rng) - _noise(n, rng, 10) * 1.0  # high-passed breathy noise
        slow = 0.5 + 0.5 * np.sin(2 * np.pi * 0.7 * np.arange(n) / sr)
        return w * slow * _env(n, 0.5, 1.4, sr) * 0.12
    if kind == "bell":
        n = int(sr * 4)
        t = np.arange(n) / sr
        w = sum(np.sin(2 * np.pi * f * t) * a for f, a in ((220, 1), (554, 0.5), (871, 0.35), (1318, 0.2)))
        return w * np.exp(-t / 1.4) * 0.18
    if kind == "heartbeat":
        n = int(sr * 0.9)
        t = np.arange(n) / sr
        beat = np.zeros(n, np.float32)
        for at, g in ((0.0, 1.0), (0.28, 0.7)):
            i = int(at * sr)
            m = n - i
            beat[i:] += np.sin(2 * np.pi * 58 * t[:m]) * np.exp(-t[:m] / 0.07) * g
        return beat * 0.9
    if kind == "sting":
        n = int(sr * 1.6)
        t = np.arange(n) / sr
        boom = np.sin(2 * np.pi * (70 - 25 * t) * t) * np.exp(-t / 0.5)
        return (boom + _noise(n, rng, 3) * np.exp(-t / 0.08) * 0.8) * 0.9
    return np.zeros(1, np.float32)


def horror_bed(total, sr, segs, starts, seed=3):
    """Continuous drone + wind (louder with intensity) plus each chapter's sound cues. Returns float32 array and a
    list of (time, strength) for visual jolts."""
    rng = np.random.default_rng(seed)
    n = int(total * sr)
    t = np.arange(n) / sr
    drone = (np.sin(2 * np.pi * 55 * t) + 0.7 * np.sin(2 * np.pi * 55.9 * t) + 0.3 * np.sin(2 * np.pi * 82.4 * t))
    drone *= 0.5 + 0.5 * np.sin(2 * np.pi * 0.08 * t)
    wind = np.convolve(rng.standard_normal(n).astype(np.float32), np.ones(220, np.float32) / 220, mode="same")
    wind *= 3.5 * (0.5 + 0.5 * np.sin(2 * np.pi * 0.11 * t + 1.0))
    inten = np.ones(n, np.float32) * 0.6
    for st, sg in zip(starts, segs):
        if sg["kind"] == "story":
            inten[int(st * sr):int((st + sg["duration"]) * sr)] = 0.5 + 0.25 * sg.get("intensity", 2)
    bed = (drone * 0.10 + wind * 0.10) * inten
    jolts = []

    def add(snd, at, gain=1.0):
        i = int(at * sr)
        if 0 <= i < n:
            m = min(len(snd), n - i)
            bed[i:i + m] += snd[:m] * gain

    for st, sg in zip(starts, segs):
        if sg["kind"] == "intro":
            add(sfx_sound("bell", sr, rng), st + 0.5)
        if sg["kind"] != "story":
            continue
        dur = sg["duration"]
        add(sfx_sound("sting", sr, rng), st + 0.05, 0.25 + 0.15 * sg.get("intensity", 2))
        for k, cue in enumerate(sg.get("sfx") or []):
            at = st + dur * (0.2 + 0.3 * k + rng.random() * 0.1)
            if cue == "heartbeat":
                for b in range(int(dur * 0.5 / 0.9)):
                    add(sfx_sound("heartbeat", sr, rng), at + b * 0.9, 0.5 + 0.12 * sg.get("intensity", 2))
            elif cue != "silence":
                add(sfx_sound(cue, sr, rng), at, 0.8)
                if cue in ("knock", "creak"):
                    jolts.append((at, 1.0 if cue == "knock" else 0.5))
        if sg.get("intensity") == 3:
            jolts.append((st + dur * 0.8, 1.0))
            add(sfx_sound("sting", sr, rng), st + dur * 0.8, 0.5)
    return bed, jolts


def write_mix(voice, sr, bed, volume, path):
    v = voice.astype(np.float32) / 32768
    bed = np.pad(bed, (0, max(0, len(v) - len(bed))))[: len(v)]
    win = max(1, min(int(sr * 0.3), len(v)))
    loud = np.convolve(np.abs(v), np.ones(win) / win, mode="same")
    duck = 1 - 0.55 * np.clip(loud / (np.percentile(loud, 90) or 1), 0, 1)
    out = np.tanh((v + bed * volume * duck) * 1.1) / np.tanh(1.1)
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes((np.clip(out, -1, 1) * 32767).astype(np.int16).tobytes())


# ---------------- visuals ----------------

def horror_scene(seed, kind, W, H):
    """A generated creepy night scene (used when no suitable photo exists, and as a base for variety)."""
    rnd = random.Random(seed)
    w, h = int(W * 1.12), int(H * 1.12)
    y = np.linspace(0, 1, h)[:, None, None]
    top, bot = np.array((4, 8, 20)), np.array((26, 36, 52))
    img = Image.fromarray(np.repeat((top * (1 - y) + bot * y).astype(np.uint8), w, axis=1), "RGB")
    d = ImageDraw.Draw(img, "RGBA")
    mx, my = rnd.randint(int(w * 0.15), int(w * 0.85)), rnd.randint(int(h * 0.12), int(h * 0.3))
    glow = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    ImageDraw.Draw(glow).ellipse([mx - 110, my - 110, mx + 110, my + 110], fill=(150, 170, 200, 60))
    img = Image.alpha_composite(img.convert("RGBA"), glow.filter(ImageFilter.GaussianBlur(40)))
    d = ImageDraw.Draw(img, "RGBA")
    d.ellipse([mx - 48, my - 48, mx + 48, my + 48], fill=(215, 220, 205, 255))
    hor = int(h * 0.72)
    d.rectangle([0, hor, w, h], fill=(6, 8, 12, 255))
    if kind in ("road", "station", "corridor"):
        d.polygon([(w * 0.46, hor), (w * 0.54, hor), (w * 0.95, h), (w * 0.05, h)], fill=(18, 20, 26, 255))
        for k in range(6):
            yy = hor + (h - hor) * (k / 6) ** 1.6
            ww = 4 + 22 * (k / 6)
            d.rectangle([w / 2 - ww / 2, yy, w / 2 + ww / 2, yy + 10 + 14 * k / 6], fill=(150, 150, 120, 150))
    for _ in range(rnd.randint(7, 11) if kind in ("forest", "village", "well", "road") else rnd.randint(2, 4)):
        x = rnd.randint(0, w)
        th = rnd.randint(int(h * 0.3), int(h * 0.6))
        d.rectangle([x - 8, hor - th, x + 8, hor + 20], fill=(3, 4, 7, 255))
        for _b in range(rnd.randint(3, 6)):
            by = hor - rnd.randint(int(th * 0.3), th)
            bx = x + rnd.choice((-1, 1)) * rnd.randint(40, 130)
            d.line([(x, by), (bx, by - rnd.randint(20, 70))], fill=(3, 4, 7, 255), width=5)
    if kind in ("house", "room", "village"):
        hx = rnd.randint(int(w * 0.25), int(w * 0.6))
        hw, hh = int(w * 0.28), int(h * 0.24)
        d.rectangle([hx, hor - hh, hx + hw, hor + 10], fill=(2, 3, 6, 255))
        d.polygon([(hx - 20, hor - hh), (hx + hw / 2, hor - hh - int(h * 0.12)), (hx + hw + 20, hor - hh)],
                  fill=(2, 3, 6, 255))
        for k in range(rnd.randint(1, 3)):
            wx = hx + 30 + k * int(hw / 3)
            lit = (255, 190, 90, 230) if rnd.random() < 0.5 else (20, 24, 30, 255)
            d.rectangle([wx, hor - hh + 30, wx + 38, hor - hh + 78], fill=lit)
    if kind == "well":
        d.ellipse([w * 0.42, hor - 30, w * 0.58, hor + 50], fill=(8, 10, 14, 255), outline=(40, 44, 50, 255), width=8)
    for _ in range(rnd.randint(1, 3)):  # watching eyes in the dark
        ex, ey = rnd.randint(int(w * 0.1), int(w * 0.9)), rnd.randint(int(h * 0.55), int(h * 0.7))
        for dx in (-14, 14):
            d.ellipse([ex + dx - 4, ey - 3, ex + dx + 4, ey + 3], fill=(255, 60, 40, 235))
    return img.convert("RGB")


def graded(img, W, H):
    """Dark, desaturated, cold-tinted photo for the horror look."""
    img = _cover(img.convert("RGB"), int(W * 1.12), int(H * 1.12))
    img = ImageEnhance.Color(img).enhance(0.35)
    img = ImageEnhance.Brightness(img).enhance(0.55)
    tint = Image.new("RGB", img.size, (70, 95, 130))
    return Image.blend(img, tint, 0.16)


def _vignette(W, H):
    yy, xx = np.mgrid[0:H, 0:W]
    r = np.sqrt(((xx - W / 2) / (W / 2)) ** 2 + ((yy - H / 2) / (H / 2)) ** 2)
    a = np.clip((r - 0.45) * 0.9, 0, 0.85) * 255
    return Image.fromarray(np.dstack([np.zeros((H, W, 3), np.uint8), a.astype(np.uint8)]), "RGBA")


def _fog(W, H, seed=5):
    rng = np.random.default_rng(seed)
    small = rng.random((H // 40 + 2, (W * 2) // 40 + 2)).astype(np.float32)
    big = np.array(Image.fromarray((small * 255).astype(np.uint8)).resize((W * 2, H), Image.BICUBIC), np.float32)
    big = np.array(Image.fromarray(big.astype(np.uint8)).filter(ImageFilter.GaussianBlur(25)), np.float32) / 255
    a = np.clip((big - 0.35) * 0.55, 0, 0.4) * 255
    rgba = np.dstack([np.full((H, W * 2, 3), (170, 185, 200), np.uint8), a.astype(np.uint8)])
    return Image.fromarray(rgba, "RGBA")


# ---------------- render ----------------

def render_special(ep, cfg, out_dir):
    out_dir = Path(out_dir)
    L = Layout(cfg)
    W, H, fps, s = L.W, L.H, L.fps, L.s
    fmt = ep["format"]
    horror = fmt == "horror"
    segs = ep["segments"]
    audio_path, audio, sr = _concat_audio(ep, out_dir)
    n = int(len(audio) / sr * fps)
    starts, t = [], 0.0
    for sg in segs:
        starts.append(t)
        t += sg["duration"]
    seg_of = np.zeros(n, dtype=int)
    for i, st in enumerate(starts):
        seg_of[int(st * fps):] = i
    total = len(audio) / sr

    jolts = []
    mixed = out_dir / "audio" / "episode_mix.wav"
    if horror:
        bed, jolts = horror_bed(total, sr, segs, starts)
        write_mix(audio, sr, bed, 1.0, mixed)
    else:
        from .sound import mix
        spans = [(st, st + sg["duration"], {"intro": "upbeat", "outro": "chill"}.get(sg["kind"])
                  or sg.get("music") or "chill") for st, sg in zip(starts, segs)]
        data = mix(audio, sr, [st for st, sg in zip(starts, segs) if sg["kind"] == "story"],
                   cfg.get("video", {}).get("music_volume", 0.12), spans=spans)
        with wave.open(str(mixed), "wb") as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(sr)
            w.writeframes(data.tobytes())

    plain = Image.new("RGB", (int(W * 1.12), int(H * 1.12)), (14, 26, 52))

    def title_card(text):
        img = plain.copy()
        d = ImageDraw.Draw(img)
        big = Font(s(64), True)
        lines = wrap(d, text, big, img.width - s(240), 3)
        y = (img.height - len(lines) * s(84)) // 2 - s(60)
        for line in lines:
            big.draw(d, ((img.width - big.length(d, line)) / 2, y), line, WHITE, 4, (0, 0, 0))
            y += s(84)
        return img

    # visuals per segment: list of (image) already cropped for Ken Burns
    visual, bounds, hl_words = {}, {}, {}
    thumb_src = None
    if ep.get("thumb_path") and (out_dir / ep["thumb_path"]).exists():
        try:
            thumb_src = _cover(Image.open(out_dir / ep["thumb_path"]).convert("RGB"), int(W * 1.12), int(H * 1.12))
        except OSError:
            pass
    for k, sg in enumerate(segs):
        if sg.get("scenes") and not horror:  # illustrated case study: one picture per scene, timed by words spoken
            words = [max(1, len(sc["line"].split())) for sc in sg["scenes"]]
            bounds[k] = np.concatenate([[0], np.cumsum(words)]) / sum(words)
            hl_words[k] = {w.strip(".,!?।\"'").lower() for sc in sg["scenes"] for h in sc.get("hl") or [] for w in h.split()}
            photos = []
            for im in sg.get("images") or []:
                try:
                    photos.append(_cover(Image.open(out_dir / im["path"]).convert("RGB"), int(W * 1.12), int(H * 1.12)))
                except OSError:
                    pass
            imgs = []
            for j, sc in enumerate(sg["scenes"]):
                img = None
                if sc.get("path") and (out_dir / sc["path"]).exists():
                    try:
                        img = _cover(Image.open(out_dir / sc["path"]).convert("RGB"), int(W * 1.12), int(H * 1.12))
                    except OSError:
                        img = None
                if img is None:
                    img = photos[j % len(photos)] if photos else title_card(sc.get("text") or sg["headline"])
                imgs.append((img, None))
            visual[k] = imgs
            continue
        if thumb_src is not None and sg["kind"] == "intro" and not horror:
            visual[k] = [(thumb_src, None)]
            continue
        imgs = []
        for im in sg.get("images") or []:
            try:
                src = Image.open(out_dir / im["path"])
                imgs.append((graded(src, W, H) if horror else _cover(src.convert("RGB"), int(W * 1.12), int(H * 1.12)),
                             im.get("credit")))
            except OSError:
                pass
        if horror and sg["kind"] != "story":
            imgs = [(horror_scene(100 + k, "house", W, H), None)]
        elif horror and len(imgs) < 2:
            imgs.append((horror_scene(200 + k, sg.get("scene", "forest"), W, H), None))
        elif not imgs:  # no free photo found: a clean title card with the chapter name
            imgs = [(title_card(sg["headline"]), None)]
        visual[k] = imgs
    f = {"brand": Font(s(24), True), "tag": Font(s(20), True), "chap": Font(s(30), True), "cap": Font(s(36), True),
         "small": Font(s(15), True), "credit": Font(s(13), False)}
    vig = _vignette(W, H) if horror else None
    fog = _fog(W, H) if horror else None
    shade = Image.fromarray(np.dstack([np.zeros((H, W, 3), np.uint8),
                                       (np.clip((np.linspace(0, 1, H) - 0.45) * 2.2, 0, 0.8) * 255).astype(np.uint8)
                                       [:, None].repeat(W, 1)]), "RGBA")
    pz = persona(cfg)
    pip = None
    sprites = None
    if not horror and cfg["video"].get("anchor", True):
        sprites = anchor_mod.sprites(s(420), s(520), pz["character"], cool=True)
        pip_d = s(190)
        pip = _pip_sprites(sprites, pip_d, 0.52 if pz["character"] == "lion" else None)
        pip_pos = (W - pip_d - s(36), H - pip_d - s(40))
    mouths = anchor_mod.mouth_track(audio, sr, fps)
    blinks = anchor_mod.blink_track(n, fps)
    chunks = {k: caption_chunks(sg["script"], 7) for k, sg in enumerate(segs)}
    rng = random.Random(9)
    flick = [rng.random() for _ in range(n // 3 + 2)]
    story_ids = [k for k, sg in enumerate(segs) if sg["kind"] == "story"]
    cap_cache, top_cache = {}, {}

    def top_layer(k):
        if k not in top_cache:
            layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
            d = ImageDraw.Draw(layer)
            d.rectangle([0, 0, W, s(56)], fill=(8, 12, 24, 200))
            f["brand"].draw(d, (s(24), s(12)), cfg["channel"]["name"].upper(), WHITE)
            tag = ep["tag"]
            tw = f["tag"].length(d, tag)
            col = ACCENT if horror else (30, 150, 80)
            d.rounded_rectangle([W - tw - s(56), s(11), W - s(24), s(45)], radius=s(8), fill=col)
            f["tag"].draw(d, (W - tw - s(40), s(14)), tag, WHITE)
            sg = segs[k]
            if sg["kind"] == "story":
                label = f"{story_ids.index(k) + 1}/{len(story_ids)}  {sg['headline']}"
                f["small"].draw(d, (s(24) + f["brand"].length(d, cfg["channel"]["name"].upper()) + s(30), s(18)),
                                label, AMBER, 2, (0, 0, 0))
            top_cache[k] = layer
        return top_cache[k]

    def cap_layer(k, ci):
        key = (k, ci)
        if key not in cap_cache:
            layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
            d = ImageDraw.Draw(layer)
            y = H - s(150)
            hl = hl_words.get(k) or set()
            for line in wrap(d, chunks[k][ci], f["cap"], W - s(300), 2):
                x = (W - f["cap"].length(d, line)) / 2 - (s(80) if pip else 0)
                if not hl:
                    f["cap"].draw(d, (x, y), line, (255, 236, 120) if not horror else (235, 235, 235), 5, (0, 0, 0))
                else:  # key words and numbers sit on a yellow tag, like the reference videos
                    space = f["cap"].length(d, " ")
                    for w in line.split():
                        wl = f["cap"].length(d, w)
                        bare = w.strip(".,!?।\"'").lower()
                        if bare in hl or any(c.isdigit() or c in "₹%" for c in w):
                            d.rounded_rectangle([x - s(8), y - s(4), x + wl + s(8), y + s(46)], radius=s(8),
                                                fill=(255, 214, 40))
                            f["cap"].draw(d, (x, y), w, (20, 20, 20))
                        else:
                            f["cap"].draw(d, (x, y), w, WHITE, 5, (0, 0, 0))
                        x += wl + space
                y += s(50)
            cap_cache[key] = layer
        return cap_cache[key]

    punch_cache = {}

    def punch_layer(k, j):
        if (k, j) not in punch_cache:
            layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
            d = ImageDraw.Draw(layer)
            big = Font(s(70), True)
            text = segs[k]["scenes"][j]["text"]
            tw = big.length(d, text)
            d.rounded_rectangle([(W - tw) / 2 - s(30), H * 0.36 - s(14), (W + tw) / 2 + s(30), H * 0.36 + s(92)],
                                radius=s(14), fill=(0, 0, 0, 140))
            big.draw(d, ((W - tw) / 2, H * 0.36), text, (255, 255, 255), 6, (0, 0, 0))
            punch_cache[(k, j)] = layer
        return punch_cache[(k, j)]

    def frame_rgb(i):
        k = int(seg_of[i])
        sg = segs[k]
        tl = i / fps - starts[k]
        dur = sg["duration"]
        imgs = visual[k] or [(plain, None)]
        bd = bounds.get(k)
        if bd is not None:
            x = min(tl / dur, 0.9999)
            j = min(int(np.searchsorted(bd, x, side="right")) - 1, len(imgs) - 1)
            p = (x - bd[j]) / max(bd[j + 1] - bd[j], 1e-6)
        else:
            slot = dur / len(imgs)
            j = min(int(tl / slot), len(imgs) - 1)
            p = (tl - j * slot) / slot
        base = _kenburns(imgs[j][0], p, W, H, j % 2 == 1).convert("RGBA")
        if sg["kind"] != "story" and not horror:  # intro/outro: darker title card look
            base = Image.blend(base, Image.new("RGBA", (W, H), (8, 14, 30, 255)), 0.55)
        base.alpha_composite(shade)
        if horror:
            off = int((i * FOG_SPEED) % W)
            base.alpha_composite(fog.crop((off, 0, off + W, H)))
            base.alpha_composite(vig)
            fl = flick[i // 3]
            dark = int(40 + 70 * fl) if fl > 0.86 else int(20 * (1 - sg.get("intensity", 2) * 0.0))
            for jt, strength in jolts:  # a jolt: quick dark flash then red tint
                dt_ = i / fps - jt
                if 0 <= dt_ < 0.25:
                    base.alpha_composite(Image.new("RGBA", (W, H), (150, 0, 0, int(110 * strength * (1 - dt_ / 0.25)))))
            if dark:
                base.alpha_composite(Image.new("RGBA", (W, H), (0, 0, 0, dark)))
        base.alpha_composite(top_layer(k))
        if bd is not None and segs[k]["scenes"][j].get("text") and (tl - bd[j] * dur) < 2.4:
            base.alpha_composite(punch_layer(k, j))
        chs = chunks[k]
        if chs:
            ci = min(int(tl / dur * len(chs)), len(chs) - 1)
            base.alpha_composite(cap_layer(k, ci))
        if pip:
            mouth, blink = int(mouths[min(i, len(mouths) - 1)]), bool(blinks[i])
            base.alpha_composite(pip[(mouth, blink)], (pip_pos[0], pip_pos[1] + int(5 * math.sin(i / 7))))
        credit = imgs[j][1]
        img = base.convert("RGB")
        d = ImageDraw.Draw(img)
        if credit and sg["kind"] == "story":
            f["credit"].draw(d, (s(24), H - s(26)), ("Photo: " + credit)[:90], (200, 200, 200), 2, (0, 0, 0))
        d.rectangle([0, H - s(6), int(W * (i + 1) / n), H], fill=ACCENT if horror else (30, 150, 80))
        return img.tobytes()

    final = out_dir / "episode.mp4"
    encode(frame_rgb, n, W, H, fps, mixed, final)
    save_special_thumbnail(ep, visual, cfg, out_dir, L, horror)
    return final


def save_special_thumbnail(ep, visual, cfg, out_dir, L, horror):
    W, H, s = L.W, L.H, L.s
    base = None
    if ep.get("thumb_path") and (Path(out_dir) / ep["thumb_path"]).exists():
        try:
            base = Image.open(Path(out_dir) / ep["thumb_path"]).convert("RGB")
        except OSError:
            base = None
    if base is None:
        k = next((k for k, sg in enumerate(ep["segments"]) if sg["kind"] == "story" and visual.get(k)), None)
        base = visual[k][0][0] if k is not None else Image.new("RGB", (W, H), (14, 26, 52))
    img = _cover(base, W, H).convert("RGBA")
    d = ImageDraw.Draw(img)
    text = ep.get("thumb_text") or ep["segments"][0]["headline"]
    if ep.get("thumb_text") and not horror:  # bold banner across the top, like the reference
        big = Font(s(78), True)
        lines = wrap(d, text, big, W - s(140), 2)
        bh = s(30) + len(lines) * s(96)
        d.rectangle([0, s(18), W, s(18) + bh], fill=(255, 214, 40))
        d.rectangle([0, s(18), s(26), s(18) + bh], fill=ACCENT)
        d.rectangle([W - s(26), s(18), W, s(18) + bh], fill=ACCENT)
        y = s(30)
        for line in lines:
            big.draw(d, ((W - big.length(d, line)) / 2, y), line, (15, 15, 15))
            y += s(96)
    else:
        img.alpha_composite(Image.fromarray(np.dstack([np.zeros((H, W, 3), np.uint8),
                                                       np.full((H, W), 120, np.uint8)]), "RGBA"))
        d = ImageDraw.Draw(img)
        big = Font(s(64), True)
        y = s(150)
        for line in wrap(d, ep["segments"][0]["headline"], big, W - s(120), 4):
            big.draw(d, (s(60), y), line, WHITE, 6, (0, 0, 0))
            y += s(80)
        tag = ep["tag"]
        tf = Font(s(34), True)
        tw = tf.length(d, tag)
        d.rectangle([s(60), y + s(20), s(100) + tw, y + s(80)], fill=ACCENT if horror else (30, 150, 80))
        tf.draw(d, (s(80), y + s(26)), tag, WHITE)
    img.convert("RGB").save(Path(out_dir) / "thumbnail.jpg", quality=92)
