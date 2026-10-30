"""Step 7: compose the news video (graphics + anchor + voice) with FFmpeg."""
import subprocess
import wave
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

from . import anchor as anchor_mod
from .strings import T, date_text
from .text import Font, wrap
from .tts import read_wav

BG_TOP, BG_BOTTOM = (12, 20, 38), (24, 40, 74)
ACCENT = (230, 57, 70)
GREEN = (42, 157, 143)
AMBER = (244, 162, 97)
WHITE = (240, 243, 248)
MUTED = (150, 165, 190)


class Layout:
    def __init__(self, cfg):
        v = cfg["video"]
        self.W, self.H, self.fps = v["width"], v["height"], v["fps"]
        self.cfg = cfg
        self.t = T(cfg)
        self.sx = self.W / 1280
        self.f = {k: Font(int(s * self.sx), b) for k, (s, b) in {
            "brand": (24, True), "small": (15, True), "label": (17, True), "h1": (36, True),
            "body": (21, False), "tick": (21, True), "list": (24, True), "thumb": (60, True),
            "thumb_tag": (28, True)}.items()}

    def s(self, v):
        return int(v * self.sx)

    def lh(self, key):  # line height; Devanagari needs room above and below
        return int(self.f[key].size * 1.42)

    def text(self, d, xy, txt, key, fill):
        self.f[key].draw(d, xy, txt, fill)

    def tlen(self, d, txt, key):
        return self.f[key].length(d, txt)

    def background(self):
        g = np.linspace(0, 1, self.H)[:, None, None]
        arr = (np.array(BG_TOP) * (1 - g) + np.array(BG_BOTTOM) * g).astype(np.uint8)
        img = Image.fromarray(np.repeat(arr, self.W, axis=1), "RGB").convert("RGBA")
        s = self.s
        # faint grid motif (drawn on its own layer so alpha blends)
        grid = Image.new("RGBA", img.size, (0, 0, 0, 0))
        g = ImageDraw.Draw(grid)
        for x in range(0, self.W, s(64)):
            g.line([(x, s(56)), (x, self.H)], fill=(255, 255, 255, 10))
        for y in range(s(56), self.H, s(64)):
            g.line([(0, y), (self.W, y)], fill=(255, 255, 255, 10))
        img.alpha_composite(grid)
        d = ImageDraw.Draw(img)
        # top bar
        d.rectangle([0, 0, self.W, s(56)], fill=(8, 12, 24))
        d.rectangle([s(24), s(14), s(52), s(42)], fill=ACCENT)
        name = self.cfg["channel"]["name"].upper()
        self.text(d, (s(64), s(11)), name, "brand", WHITE)
        bx = s(64) + self.tlen(d, name, "brand") + s(20)
        self.text(d, (bx, s(17)), "|  " + date_text(self.cfg), "small", MUTED)
        # permanent AI disclosure (YouTube policy + India IT rules)
        label = self.t["ai_label"]
        lw = self.tlen(d, label, "small")
        d.rounded_rectangle([self.W - lw - s(48), s(12), self.W - s(24), s(44)], radius=s(6),
                            outline=AMBER, width=2)
        self.text(d, (self.W - lw - s(36), s(16)), label, "small", AMBER)
        return img

    def desk(self, img):
        d = ImageDraw.Draw(img)
        s = self.s
        top, bottom = s(585), s(668)
        d.rectangle([s(800), top, self.W, bottom], fill=(14, 22, 42))
        d.rectangle([s(800), top, self.W, top + s(4)], fill=ACCENT)
        name = self.cfg["channel"]["name"].upper()
        self.text(d, (s(1040) - self.tlen(d, name, "label") / 2, top + s(26)), name, "label", MUTED)

    def check(self, d, x, y, size, color):
        d.line([(x, y + size * 0.55), (x + size * 0.38, y + size * 0.9), (x + size, y + size * 0.1)],
               fill=color, width=max(2, self.s(3)), joint="curve")

    def story_panel(self, img, seg, idx, total):
        d = ImageDraw.Draw(img)
        s, t = self.s, self.t
        x, y, w = s(48), s(76), s(720)
        tag = t["story_n"].format(i=idx, n=total)
        if seg.get("section") == "world":
            tag += "  |  " + t["world"]
        if seg.get("date_label"):
            tag += "  |  " + seg["date_label"]
        self.text(d, (x, y), tag, "label", ACCENT)
        y += s(32)
        for line in wrap(d, seg["headline"], self.f["h1"], w, 2):
            self.text(d, (x, y), line, "h1", WHITE)
            y += self.lh("h1")
        y += s(6)
        chip = t["reported_by"].format(n=seg["n_outlets"])
        if seg.get("foreign"):
            chip += "  " + t["foreign"]
        cw = self.tlen(d, chip, "label")
        d.rounded_rectangle([x, y, x + cw + s(48), y + s(34)], radius=s(17), fill=(22, 72, 84),
                            outline=GREEN, width=2)
        self.check(d, x + s(13), y + s(10), s(14), WHITE)
        self.text(d, (x + s(36), y + s(4)), chip, "label", WHITE)
        y += s(44)
        outlets = ", ".join(dict.fromkeys(src["outlet"] for src in seg.get("sources", [])))
        for line in wrap(d, t["sources"].format(list=outlets), self.f["small"], w, 1):
            self.text(d, (x, y), line, "small", MUTED)
        y += s(34)

        limit, row = s(645), self.lh("body")
        facts = seg.get("confirmed_facts") or []
        if facts:
            self.text(d, (x, y), t["confirmed"], "label", GREEN)
            y += s(30)
            for fct in facts:
                lines = wrap(d, fct["fact"], self.f["body"], w - s(24), 2)
                if y + len(lines) * row > limit - s(70):
                    break
                d.ellipse([x + s(2), y + s(12), x + s(10), y + s(20)], fill=GREEN)
                for line in lines:
                    self.text(d, (x + s(22), y), line, "body", WHITE)
                    y += row
                y += s(4)
            y += s(8)
        reaction = seg.get("public_reaction")
        if reaction:
            limit -= s(108)  # keep room for the opinion box at the bottom
        disputed = [c for c in seg.get("disputed") or [] if c.get("reported_by")]
        if disputed and y < limit - s(70):
            self.text(d, (x, y), t["unconfirmed"], "label", AMBER)
            y += s(30)
            for c in disputed:
                txt = c["claim"] + t["per"].format(src=", ".join(c["reported_by"]))
                lines = wrap(d, txt, self.f["body"], w - s(24), 2)
                if y + len(lines) * row > limit:
                    break
                d.rectangle([x + s(2), y + s(6), x + s(6), y + len(lines) * row - s(4)], fill=AMBER)
                for line in lines:
                    self.text(d, (x + s(22), y), line, "body", (225, 228, 235))
                    y += row
                y += s(4)
        if reaction:  # opinions get their own, clearly labelled box, never mixed with facts
            top = limit + s(6)
            d.rounded_rectangle([x, top, x + w, top + s(100)], radius=s(8), fill=(30, 36, 60),
                                outline=(124, 77, 255), width=2)
            self.text(d, (x + s(14), top + s(4)), t["reaction_label"], "small", (170, 150, 255))
            ry = top + s(28)
            for line in wrap(d, reaction, self.f["small"], w - s(28), 3):
                self.text(d, (x + s(14), ry), line, "small", (225, 228, 235))
                ry += s(22)

    def list_panel(self, img, title, items, numbered=True):
        d = ImageDraw.Draw(img)
        s = self.s
        x, y, w = s(48), s(84), s(720)
        self.text(d, (x, y), title.upper(), "h1", WHITE)
        y += s(70)
        key = "list" if numbered else "body"
        for i, it in enumerate(items, 1):
            lines = wrap(d, it, self.f[key], w - s(56), 2)
            if numbered:
                d.rounded_rectangle([x, y + s(4), x + s(34), y + s(38)], radius=s(6), fill=ACCENT)
                n = str(i)
                self.text(d, (x + s(17) - self.tlen(d, n, "label") / 2, y + s(7)), n, "label", WHITE)
            else:
                self.check(d, x + s(6), y + s(10), s(18), GREEN)
            for line in lines:
                self.text(d, (x + s(54), y), line, key, WHITE)
                y += self.lh(key)
            y += s(10 if numbered else 14)

    def ticker_strip(self, headlines):
        s = self.s
        h = s(52)
        sep = "     |     "
        text = sep.join(headlines) + sep
        tmp = ImageDraw.Draw(Image.new("RGB", (1, 1)))
        tw = int(self.tlen(tmp, text, "tick"))
        strip = Image.new("RGB", (tw * 2, h), (245, 246, 250))
        d = ImageDraw.Draw(strip)
        for k in (0, tw):
            self.text(d, (k, s(10)), text, "tick", (20, 28, 48))
        return strip, tw


def encode(frame_rgb, n_frames, W, H, fps, audio_path, target):
    """Pipe raw frames into FFmpeg together with the voice track."""
    cmd = ["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24",
           "-s", f"{W}x{H}", "-r", str(fps), "-i", "-", "-i", str(audio_path),
           "-c:v", "libx264", "-preset", "veryfast", "-crf", "21", "-pix_fmt", "yuv420p",
           "-c:a", "aac", "-b:a", "160k", "-shortest", "-movflags", "+faststart", str(target)]
    print(f"Rendering {Path(target).name}: {n_frames} frames ({n_frames / fps:.0f}s)...")
    p = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    for i in range(n_frames):
        p.stdin.write(frame_rgb(i))
    p.stdin.close()
    if p.wait() != 0:
        raise RuntimeError("ffmpeg failed")


def _concat_audio(episode, out_dir):
    parts, sr = [], None
    for seg in episode["segments"]:
        data, sr = read_wav(Path(out_dir) / seg["audio"])
        parts.append(data)
    audio = np.concatenate(parts)
    path = Path(out_dir) / "audio" / "episode.wav"
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes(audio.tobytes())
    return path, audio, sr


def render_episode(episode, cfg, out_dir):
    out_dir = Path(out_dir)
    L = Layout(cfg)
    W, H, fps, s = L.W, L.H, L.fps, L.s
    mode = cfg["anchor"]["mode"]
    audio_path, audio, sr = _concat_audio(episode, out_dir)
    n_frames = int(len(audio) / sr * fps)

    stories = [x for x in episode["segments"] if x["kind"] == "story"]
    base = L.background()

    # one static "card" per segment
    cards = []
    for seg in episode["segments"]:
        img = base.copy()
        if seg["kind"] == "intro":
            L.list_panel(img, seg["headline"], [x["headline"] for x in stories[:6]])
        elif seg["kind"] == "outro":
            k = cfg["editor"]["confirm_threshold"]
            L.list_panel(img, seg["headline"], [p.format(k=k) for p in L.t["how_points"]], numbered=False)
        else:
            L.story_panel(img, seg, stories.index(seg) + 1, len(stories))
        if mode != "puppet":  # puppet: anchor drawn per frame, desk goes on top of it
            L.desk(img)
        cards.append(img)

    # timeline: which segment is on screen at each frame
    seg_of_frame = np.zeros(n_frames, dtype=int)
    t = 0.0
    for i, seg in enumerate(episode["segments"]):
        a, b = int(t * fps), int((t + seg["duration"]) * fps)
        seg_of_frame[a:b] = i
        t += seg["duration"]
    seg_of_frame[int(t * fps):] = len(episode["segments"]) - 1

    mouths = anchor_mod.mouth_track(audio, sr, fps)
    blinks = anchor_mod.blink_track(n_frames, fps)
    sprites = anchor_mod.sprites(s(420), s(520)) if mode == "puppet" else None
    anchor_pos = (s(830), s(92))

    strip, loop_w = L.ticker_strip([x["headline"] for x in stories])
    tick_y, tick_h = H - s(52), s(52)
    tmp = ImageDraw.Draw(Image.new("RGB", (1, 1)))
    label_w = int(L.tlen(tmp, L.t["headlines"], "tick")) + s(40)
    speed = s(110) / fps  # pixels per frame

    cache = {}

    def frame_rgb(i):
        si = seg_of_frame[i]
        key = (si, int(mouths[min(i, len(mouths) - 1)]), bool(blinks[i]))
        if key not in cache:
            img = cards[si].copy()
            if sprites is not None:
                img.alpha_composite(sprites[(key[1], key[2])], anchor_pos)
                L.desk(img)
            d = ImageDraw.Draw(img)
            d.rectangle([0, tick_y, label_w, H], fill=ACCENT)
            L.text(d, (s(20), tick_y + s(10)), L.t["headlines"], "tick", WHITE)
            cache[key] = img.convert("RGB")
        img = cache[key].copy()
        off = int(i * speed) % loop_w
        img.paste(strip.crop((off, 0, off + W - label_w, tick_h)), (label_w, tick_y))
        return img.tobytes()

    silent = out_dir / "video_noanchor.mp4" if mode != "puppet" else None
    final = out_dir / "episode.mp4"
    encode(frame_rgb, n_frames, W, H, fps, audio_path, silent or final)

    if mode == "lipsync":
        _overlay_lipsync(episode, out_dir, silent, final, L)

    save_thumbnail(L, base, stories, sprites, out_dir)
    return final


def _overlay_lipsync(episode, out_dir, bg_video, final, L):
    """Overlay talking-head clips (one per segment, from colab/lipsync.ipynb) on the anchor area."""
    s = L.s
    clips = [out_dir / "anchor" / f"{seg['id']}.mp4" for seg in episode["segments"]]
    missing = [c.name for c in clips if not c.exists()]
    if missing:
        raise FileNotFoundError(f"Missing lip-sync clips in {out_dir / 'anchor'}: {missing}. "
                                f"Run colab/lipsync.ipynb or set anchor.mode: puppet")
    lst = out_dir / "anchor" / "list.txt"
    lst.write_text("".join(f"file '{c.name}'\n" for c in clips))
    box_w, box_h = s(380), s(505)
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(bg_video), "-f", "concat", "-safe", "0",
                    "-i", str(lst), "-filter_complex",
                    f"[1:v]scale={box_w}:{box_h}:force_original_aspect_ratio=increase,crop={box_w}:{box_h},"
                    f"setsar=1[a];[0:v][a]overlay={s(850)}:{s(80)}:shortest=1",
                    "-map", "0:a", "-c:v", "libx264", "-preset", "veryfast", "-crf", "21",
                    "-pix_fmt", "yuv420p", "-c:a", "copy", "-movflags", "+faststart", str(final)], check=True)


def save_thumbnail(L, base, stories, sprites, out_dir):
    s = L.s
    img = base.copy()
    d = ImageDraw.Draw(img)
    y = s(130)
    head = stories[0]["headline"] if stories else L.t["top_stories"]
    for line in wrap(d, head, L.f["thumb"], s(760), 4):
        L.text(d, (s(48), y), line, "thumb", WHITE)
        y += L.lh("thumb")
    tag = L.t["fact_checked"]
    tw = L.tlen(d, tag, "thumb_tag")
    d.rectangle([s(48), y + s(16), s(80) + tw, y + s(72)], fill=ACCENT)
    L.text(d, (s(64), y + s(22)), tag, "thumb_tag", WHITE)
    if sprites:
        img.alpha_composite(sprites[(0, False)], (s(830), s(92)))
        L.desk(img)
    img.convert("RGB").save(out_dir / "thumbnail.jpg", quality=92)
