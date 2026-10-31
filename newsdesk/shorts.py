"""Vertical 1080x1920 Shorts: one per story, made from the same cross-checked facts as the bulletin."""
import re
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

from . import anchor as anchor_mod
from .persona import persona
from .render import ACCENT, AMBER, BG_BOTTOM, BG_TOP, GREEN, MUTED, WHITE, encode
from .strings import T, date_text
from .text import Font, wrap
from .tts import Speaker, read_wav

W, H, FPS = 1080, 1920, 25


def short_text(seg):
    """The LLM's short version, or (for older scripts) the first three sentences of the full one."""
    if seg.get("short_script"):
        return seg["short_script"]
    sentences = re.split(r"(?<=[।.!?])\s+", seg["script"])
    return " ".join(sentences[:3])


def _base(cfg, seg):
    t = T(cfg)
    f = {k: Font(sz, b) for k, (sz, b) in {"brand": (40, True), "small": (26, True), "chip": (30, True),
                                           "h1": (60, True), "body": (36, False), "label": (30, True),
                                           "foot": (30, True)}.items()}
    g = np.linspace(0, 1, H)[:, None, None]
    arr = (np.array(BG_TOP) * (1 - g) + np.array(BG_BOTTOM) * g).astype(np.uint8)
    img = Image.fromarray(np.repeat(arr, W, axis=1), "RGB").convert("RGBA")
    d = ImageDraw.Draw(img)

    d.rectangle([0, 0, W, 120], fill=(8, 12, 24))
    d.rectangle([44, 38, 88, 82], fill=ACCENT)
    name = cfg["channel"]["name"].upper()
    f["brand"].draw(d, (106, 30), name, WHITE)
    date = date_text(cfg)
    f["small"].draw(d, (W - 44 - f["small"].length(d, date), 42), date, MUTED)

    label = t["ai_label"]
    lw = f["small"].length(d, label)
    d.rounded_rectangle([44, 146, 44 + lw + 32, 194], radius=10, outline=AMBER, width=3)
    f["small"].draw(d, (60, 152), label, AMBER)

    y = 230
    chip = t["reported_by"].format(n=seg["n_outlets"])
    cw = f["chip"].length(d, chip)
    d.rounded_rectangle([44, y, 44 + cw + 76, y + 56], radius=28, fill=(22, 72, 84), outline=GREEN, width=3)
    d.line([(66, y + 30), (76, y + 40), (94, y + 18)], fill=WHITE, width=5, joint="curve")
    f["chip"].draw(d, (108, y + 8), chip, WHITE)

    y += 84
    for line in wrap(d, seg["headline"], f["h1"], W - 88, 3):
        f["h1"].draw(d, (44, y), line, WHITE)
        y += 86
    y += 16
    facts = seg.get("confirmed_facts") or []
    if facts:
        f["label"].draw(d, (44, y), t["confirmed"], GREEN)
        y += 48
        for fct in facts[:2]:
            lines = wrap(d, fct["fact"], f["body"], W - 120, 2)
            d.ellipse([50, y + 20, 64, y + 34], fill=GREEN)
            for line in lines:
                f["body"].draw(d, (84, y), line, WHITE)
                y += 52
            y += 10
    return img, f, y


def _desk(img, f, cfg):
    d = ImageDraw.Draw(img)
    top = 1590
    d.rectangle([0, top, W, 1760], fill=(14, 22, 42))
    d.rectangle([0, top, W, top + 6], fill=ACCENT)
    name = cfg["channel"]["name"].upper()
    f["brand"].draw(d, ((W - f["brand"].length(d, name)) / 2, top + 50), name, MUTED)


def render_short(seg, cfg, speaker, out_dir):
    t = T(cfg)
    shorts_dir = Path(out_dir) / "shorts"
    shorts_dir.mkdir(exist_ok=True)
    name = cfg["channel"].get("spoken_name") or cfg["channel"]["name"]
    wav = shorts_dir / f"{seg['id']}.wav"
    duration = speaker.say(f"{short_text(seg)} {t['short_outro'].format(name=name)}", wav, 0.4,
                           "angry" if seg.get("angry") else "calm")
    audio, sr = read_wav(wav)
    n = int(len(audio) / sr * FPS)

    base, f, text_bottom = _base(cfg, seg)
    # anchor fills the space between the facts and the desk
    ah = max(560, 1640 - max(text_bottom, 860))
    aw = int(ah * 420 / 520)
    sprites = anchor_mod.sprites(aw, ah, persona(cfg)["character"])
    pos = ((W - aw) // 2, 1640 - ah)
    d = ImageDraw.Draw(base)
    d.rectangle([0, 1760, W, H], fill=(8, 12, 24))
    foot = t["short_footer"]
    f["foot"].draw(d, ((W - f["foot"].length(d, foot)) / 2, 1800), foot, WHITE)

    mouths = anchor_mod.mouth_track(audio, sr, FPS)
    blinks = anchor_mod.blink_track(n, FPS, seed=hash(seg["id"]) % 1000)
    cache = {}

    def frame_rgb(i):
        key = (int(mouths[min(i, len(mouths) - 1)]), bool(blinks[i]))
        if key not in cache:
            img = base.copy()
            img.alpha_composite(sprites[key], pos)
            _desk(img, f, cfg)
            cache[key] = img.convert("RGB")
        img = cache[key].copy()
        ImageDraw.Draw(img).rectangle([0, 1754, int(W * (i + 1) / n), 1760], fill=WHITE)  # progress bar
        return img.tobytes()

    out = shorts_dir / f"{seg['id']}.mp4"
    encode(frame_rgb, n, W, H, FPS, wav, out)
    wav.unlink()
    return {"file": str(out.relative_to(out_dir)), "duration": duration}


def render_shorts(episode, cfg, out_dir):
    count = cfg.get("shorts", {}).get("count", 5)
    speaker = Speaker(cfg)
    stories = [s for s in episode["segments"] if s["kind"] == "story"][:count]
    for seg in stories:
        seg["short"] = render_short(seg, cfg, speaker, out_dir)
    return episode
