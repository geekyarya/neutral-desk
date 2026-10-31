"""Render a 1080x1920 Reel: hook title, big spoken captions, and either a slowly zooming photo or the anchor."""
import math
import re
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageOps

from . import anchor as anchor_mod
from .persona import persona
from .render import ACCENT, AMBER, BG_BOTTOM, BG_TOP, GREEN, WHITE, _cover, _kenburns, _pip_sprites, _VideoReader, encode
from .sound import mix
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
    angry = bool(content.get("angry"))
    speaker.say(f"{content['script']} {outro}", wav, 0.5, "angry" if angry else "calm")
    audio, sr = read_wav(wav)
    n = int(len(audio) / sr * FPS)
    chunks = caption_chunks(f"{content['script']} {outro}")
    which = _timeline(chunks, len(audio) / sr - 0.5, n)
    mixed = out_dir / "voice_music.wav"  # light music under the voice
    _write_wav(mixed, mix(audio, sr, [], 0.10, "calm"), sr)

    overlay = _overlay(cfg, content, f)
    pz = persona(cfg)
    media = content.get("media") or []
    items = []
    for m in media:
        try:
            if m["type"] == "video":
                items.append(("video", m["path"], m.get("credit")))
            else:
                items.append(("img", _cover(Image.open(m["path"]), int(W * 1.15), int(H * 1.15)), m.get("credit")))
        except OSError:
            pass
    mouths = anchor_mod.mouth_track(audio, sr, FPS)
    blinks = anchor_mod.blink_track(n, FPS)
    if items:
        shade = _shade()
        cap_y = 1080
        pip = None
        if content["type"] != "mystery":  # Babbar Bhai in a round corner window over the news visuals
            face_y = 0.52 if pz["character"] == "lion" else None
            sp = anchor_mod.sprites(420, 520, pz["character"], cool=not angry)
            pip = _pip_sprites(sp, 330, face_y)
            pip_pos = (W - 342 - 36, H - 342 - 70)
    else:
        base = _gradient()
        ah = 820
        aw = int(ah * 420 / 520)
        sprites = anchor_mod.sprites(aw, ah, pz["character"], cool=not angry)
        pos = ((W - aw) // 2, H - ah - 60)
        cap_y = 640
    readers = {}

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
        mouth, blink = int(mouths[min(i, len(mouths) - 1)]), bool(blinks[i])
        if items:  # news photos (slow zoom) and video clips fill the screen, one after another
            slot = n / len(items)
            k = min(int(i / slot), len(items) - 1)
            p = (i - k * slot) / slot
            kind, src, credit = items[k]
            if kind == "video":
                if k not in readers:
                    for rd in readers.values():
                        rd.close()
                    readers.clear()
                    readers[k] = _VideoReader(src, W, H, FPS)
                img = readers[k].read()
            else:
                img = _kenburns(src, p, W, H, k % 2 == 1)
            img = img.convert("RGBA")
            img.alpha_composite(shade)
            img.alpha_composite(overlay)
            img.alpha_composite(caption_layer(ci))
            if credit:
                d = ImageDraw.Draw(img)
                f["credit"].draw(d, (44, H - 52), (("Video: " if kind == "video" else "Photo: ") + credit)[:80],
                                 (220, 220, 220), 2, (0, 0, 0))
            if pip:
                img.alpha_composite(pip[(mouth, blink)], (pip_pos[0], pip_pos[1] + int(6 * math.sin(i / 7))))
        else:
            key = (mouth, blink, ci)
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
    encode(frame_rgb, n, W, H, FPS, mixed, out)
    for rd in readers.values():
        rd.close()
    wav.unlink()
    mixed.unlink()
    return out


def _write_wav(path, audio, sr):
    import wave
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes(audio.tobytes())
