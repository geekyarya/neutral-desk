"""Render a 1080x1920 Reel: hook title, big spoken captions, and either a slowly zooming photo or the anchor."""
import re
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageOps

from . import anchor as anchor_mod
from .persona import persona
from .render import ACCENT, AMBER, BG_BOTTOM, BG_TOP, GREEN, WHITE, encode
from .strings import T
from .text import Font, wrap
from .tts import Speaker, read_wav

W, H, FPS = 1080, 1920, 25
TAG_COLORS = {"news": ACCENT, "mystery": (124, 77, 255), "supernatural": (230, 126, 34)}


def caption_chunks(text, max_words=4):
    """Split narration into short on-screen phrases, breaking at punctuation where possible."""
    chunks = []
    for part in re.split(r"(?<=[।.!?,;:])\s+", text.strip()):
        words = part.split()
        for i in range(0, len(words), max_words):
            chunks.append(" ".join(words[i:i + max_words]))
    return [c for c in chunks if c]


def _timeline(chunks, speech_seconds, n_frames):
    """Frame index -> chunk index, with each phrase on screen in proportion to its length."""
    weights = np.array([len(c) + 3 for c in chunks], dtype=float)
    ends = np.cumsum(weights) / weights.sum() * speech_seconds * FPS
    return np.minimum(np.searchsorted(ends, np.arange(n_frames), side="right"), len(chunks) - 1)


def _gradient():
    g = np.linspace(0, 1, H)[:, None, None]
    arr = (np.array(BG_TOP) * (1 - g) + np.array(BG_BOTTOM) * g).astype(np.uint8)
    return Image.fromarray(np.repeat(arr, W, axis=1), "RGB").convert("RGBA")


def _shade():
    """Dark top and bottom so white text stays readable over any photo."""
    y = np.linspace(0, 1, H)
    alpha = np.clip(np.maximum(0.85 - y * 2.2, (y - 0.45) * 1.6) * 255, 70, 235).astype(np.uint8)
    a = np.repeat(alpha[:, None], W, axis=1)
    return Image.fromarray(np.dstack([np.zeros((H, W, 3), np.uint8), a]), "RGBA")


def _overlay(cfg, content, f):
    """Everything static on top of the background: brand bar, AI label, type tag, hook title."""
    t = T(cfg)
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rectangle([44, 70, 84, 110], fill=ACCENT)
    f["brand"].draw(d, (100, 62), cfg["channel"]["name"].upper(), WHITE, 3, (0, 0, 0))
    label = t["ai_label"]
    lw = f["small"].length(d, label)
    d.rounded_rectangle([W - lw - 76, 70, W - 44, 114], radius=10, fill=(0, 0, 0, 140), outline=AMBER, width=3)
    f["small"].draw(d, (W - lw - 60, 76), label, AMBER)

    tag = t["reel_tags"][content["type"]]
    tw = f["tag"].length(d, tag)
    d.rounded_rectangle([44, 170, 44 + tw + 48, 234], radius=14, fill=TAG_COLORS[content["type"]])
    f["tag"].draw(d, (68, 176), tag, WHITE)
    if content.get("chip"):
        f["small"].draw(d, (44 + tw + 72, 186), content["chip"], (190, 235, 225), 2, (0, 0, 0))

    y = 270
    for line in wrap(d, content["title"], f["title"], W - 88, 3):
        f["title"].draw(d, (44, y), line, WHITE, 4, (0, 0, 0))
        y += 100
    if content.get("credit"):
        f["credit"].draw(d, (44, H - 70), content["credit"][:90], (200, 200, 200), 2, (0, 0, 0))
    return img


def render_reel(content, cfg, out_dir):
    out_dir = Path(out_dir)
    t = T(cfg)
    f = {k: Font(sz, b) for k, (sz, b) in {"brand": (40, True), "small": (26, True), "tag": (34, True),
                                           "title": (70, True), "cap": (64, True), "credit": (22, False)}.items()}
    name = cfg["channel"].get("spoken_name") or cfg["channel"]["name"]
    outro = t["reel_outro"].format(name=name)
    wav = out_dir / "voice.wav"
    speaker = Speaker(cfg)
    speaker.say(f"{content['script']} {outro}", wav, 0.5)
    audio, sr = read_wav(wav)
    n = int(len(audio) / sr * FPS)
    chunks = caption_chunks(f"{content['script']} {outro}")
    which = _timeline(chunks, len(audio) / sr - 0.5, n)

    overlay = _overlay(cfg, content, f)
    photo = content.get("image")
    if photo:
        src = ImageOps.fit(Image.open(photo).convert("RGB"), (int(W * 1.18), int(H * 1.18)), Image.LANCZOS)
        shade = _shade()
        cap_y = 1180
    else:
        base = _gradient()
        ah = 820
        aw = int(ah * 420 / 520)
        sprites = anchor_mod.sprites(aw, ah, persona(cfg)["character"])
        pos = ((W - aw) // 2, H - ah - 60)
        mouths = anchor_mod.mouth_track(audio, sr, FPS)
        blinks = anchor_mod.blink_track(n, FPS)
        cap_y = 640

    cap_cache = {}

    def caption_layer(ci):
        if ci not in cap_cache:
            layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
            d = ImageDraw.Draw(layer)
            lines = wrap(d, chunks[ci], f["cap"], W - 120, 2)
            y = cap_y
            for line in lines:
                x = (W - f["cap"].length(d, line)) / 2
                f["cap"].draw(d, (x, y), line, (255, 236, 120), 7, (0, 0, 0))
                y += 92
            cap_cache[ci] = layer
        return cap_cache[ci]

    frame_cache = {}

    def frame_rgb(i):
        ci = int(which[i])
        if photo:  # slow zoom-in with a gentle drift (Ken Burns)
            p = i / max(1, n - 1)
            z = 1.0 + 0.12 * p
            cw, ch = int(src.width / z), int(src.height / z)
            x0 = int((src.width - cw) * (0.5 + 0.2 * (p - 0.5)))
            y0 = int((src.height - ch) * 0.5)
            img = src.crop((x0, y0, x0 + cw, y0 + ch)).resize((W, H), Image.BILINEAR).convert("RGBA")
            img.alpha_composite(shade)
            img.alpha_composite(overlay)
            img.alpha_composite(caption_layer(ci))
        else:
            key = (int(mouths[min(i, len(mouths) - 1)]), bool(blinks[i]), ci)
            if key not in frame_cache:
                img = base.copy()
                img.alpha_composite(sprites[key[:2]], pos)
                ImageDraw.Draw(img).rectangle([0, H - 190, W, H], fill=(14, 22, 42))
                ImageDraw.Draw(img).rectangle([0, H - 190, W, H - 184], fill=ACCENT)
                img.alpha_composite(overlay)
                img.alpha_composite(caption_layer(ci))
                frame_cache[key] = img
            img = frame_cache[key].copy()
        img = img.convert("RGB")
        ImageDraw.Draw(img).rectangle([0, H - 12, int(W * (i + 1) / n), H], fill=GREEN)
        return img.tobytes()

    out = out_dir / "reel.mp4"
    encode(frame_rgb, n, W, H, FPS, wav, out)
    wav.unlink()
    return out
