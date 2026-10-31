"""Step 7: compose the news video (graphics + anchor + voice) with FFmpeg."""
import subprocess
import wave
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageOps

from . import anchor as anchor_mod
from .persona import persona
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

    def story_panel(self, img, seg, idx, total, n_facts=None, rest=True, w=None):
        """n_facts: how many confirmed facts to show (None = all); rest: also show disputed/why/opinion boxes."""
        d = ImageDraw.Draw(img)
        s, t = self.s, self.t
        x, y, w = s(48), s(76), w or s(720)
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
        why = seg.get("why_it_matters") if rest else ""
        if why:
            limit -= s(80)  # keep room for the "why it matters" box at the bottom
        facts = seg.get("confirmed_facts") or []
        shown = facts if n_facts is None else facts[:n_facts]
        if facts:
            self.text(d, (x, y), t["confirmed"], "label", GREEN)
            y += s(30)
            for fct in shown:
                lines = wrap(d, fct["fact"], self.f["body"], w - s(24), 2)
                if y + len(lines) * row > limit - s(70):
                    break
                d.ellipse([x + s(2), y + s(12), x + s(10), y + s(20)], fill=GREEN)
                for line in lines:
                    self.text(d, (x + s(22), y), line, "body", WHITE)
                    y += row
                y += s(4)
            y += s(8)
        if not rest:
            return
        reaction = seg.get("public_reaction")
        if reaction:
            limit -= s(108)  # keep room for the opinion box at the bottom
        disputed = [c for c in seg.get("disputed") or [] if c.get("reported_by")]
        first = wrap(d, disputed[0]["claim"], self.f["body"], w - s(24), 2) if disputed else []
        if disputed and y + s(30) + len(first) * row <= limit:  # heading only if at least one claim fits
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
        if why:
            top = s(645) - s(74)
            d.rounded_rectangle([x, top, x + w, top + s(66)], radius=s(8), fill=(60, 44, 20), outline=AMBER, width=2)
            self.text(d, (x + s(14), top + s(4)), t["why_label"], "label", AMBER)
            for line in wrap(d, why, self.f["small"], w - s(28), 1):
                self.text(d, (x + s(14), top + s(32)), line, "small", WHITE)
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


TRANSITION = 0.45  # seconds of the "खबर 2" wipe at the start of each story


def _ease(x):
    x = min(max(x, 0.0), 1.0)
    return x * x * (3 - 2 * x)


def _reveal_stage(seg, t, dur):
    """How much of a story card is visible at local time t: facts appear one by one as they are spoken."""
    n = len(seg.get("confirmed_facts") or [])
    shown = sum(t >= dur * (0.12 + 0.6 * j / max(n, 1)) for j in range(n))
    return shown, t >= dur * 0.72


def _cover(img, w, h):
    return ImageOps.fit(img.convert("RGB"), (w, h), Image.LANCZOS)


def _kenburns(src, p, W, H, flip):
    """Slow zoom (1.0 -> 1.1) with a gentle sideways drift."""
    z = 1.0 + 0.1 * p
    cw, ch = int(src.width / z), int(src.height / z)
    drift = (p - 0.5) * (0.3 if flip else -0.3)
    x0 = int((src.width - cw) * (0.5 + drift))
    y0 = int((src.height - ch) * 0.45)
    return src.crop((x0, y0, x0 + cw, y0 + ch)).resize((W, H), Image.BILINEAR)


def _pip_sprites(sprites, d):
    """Round picture-in-picture versions of the anchor (head and shoulders) for photo segments."""
    out = {}
    mask = Image.new("L", (d, d), 0)
    ImageDraw.Draw(mask).ellipse([0, 0, d - 1, d - 1], fill=255)
    for key, sp in sprites.items():
        w, h = sp.size
        crop = sp.crop((int(w * 0.08), int(h * 0.04), int(w * 0.92), int(h * 0.04 + w * 0.84)))
        face = Image.new("RGBA", crop.size, (24, 40, 74, 255))
        face.alpha_composite(crop)
        face = face.resize((d, d), Image.LANCZOS)
        ring = Image.new("RGBA", (d + 12, d + 12), (0, 0, 0, 0))
        ImageDraw.Draw(ring).ellipse([0, 0, d + 11, d + 11], fill=ACCENT)
        ImageDraw.Draw(ring).ellipse([3, 3, d + 8, d + 8], fill=WHITE)
        ring.paste(face, (6, 6), mask)
        out[key] = ring
    return out


def render_episode(episode, cfg, out_dir):
    out_dir = Path(out_dir)
    L = Layout(cfg)
    W, H, fps, s = L.W, L.H, L.fps, L.s
    mode = cfg["anchor"]["mode"]
    audio_path, audio, sr = _concat_audio(episode, out_dir)
    n_frames = int(len(audio) / sr * fps)
    segs = episode["segments"]

    # timeline
    starts, t = [], 0.0
    for seg in segs:
        starts.append(t)
        t += seg["duration"]
    seg_of_frame = np.zeros(n_frames, dtype=int)
    for i, st in enumerate(starts):
        seg_of_frame[int(st * fps):] = i

    # music bed + whoosh on every story transition (generated, no copyright)
    vcfg = cfg.get("video", {})
    if vcfg.get("music", True):
        from .sound import mix
        mixed = mix(audio, sr, [st for st, sg in zip(starts, segs) if sg["kind"] == "story"],
                    vcfg.get("music_volume", 0.12), persona(cfg).get("music", "calm"))
        audio_path = out_dir / "audio" / "episode_mix.wav"
        with wave.open(str(audio_path), "wb") as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(sr)
            w.writeframes(mixed.tobytes())

    stories = [x for x in segs if x["kind"] == "story"]
    base = L.background()
    topbar = base.crop((0, 0, W, s(56)))

    mouths = anchor_mod.mouth_track(audio, sr, fps)
    blinks = anchor_mod.blink_track(n_frames, fps)
    pz = persona(cfg)
    sprites = anchor_mod.sprites(s(420), s(520), pz["character"]) if mode == "puppet" else None
    pips = _pip_sprites(sprites, s(190)) if sprites else None
    # mood effects: fire for bad news, ice (+ sunglasses on the photo lion) for good news
    fx = None
    if pz.get("mood_effects") and sprites is not None:
        from .effects import Particles, fire_ring, ice_ring, vignette
        ring_d = s(190) + 12
        cool = anchor_mod.sprites(s(420), s(520), pz["character"], cool=True)
        fx = {"fire": fire_ring(ring_d, s(70)), "ice": ice_ring(ring_d, s(46)), "ring_d": ring_d,
              "pad": {"bad": s(70), "good": s(46)},
              "vig": {"bad": vignette(W, H, (200, 30, 0), 120), "good": vignette(W, H, (60, 160, 255), 110)},
              "parts": {"bad": Particles(W, H, "embers"), "good": Particles(W, H, "snow")},
              "cool": cool, "cool_pips": _pip_sprites(cool, s(190))}
    shake = pz.get("shake", False)
    anchor_pos = (s(830), s(92))
    pip_pos = (W - s(232), H - s(52) - s(222))

    # photos for each story (fetched earlier by media.add_story_images)
    photos = {}
    for seg in stories:
        imgs = []
        for im in seg.get("images") or []:
            try:
                imgs.append((_cover(Image.open(out_dir / im["path"]), int(W * 1.12), int(H * 1.12)), im["credit"]))
            except OSError:
                pass
        if imgs and sprites is not None:
            photos[seg["id"]] = imgs

    # dark fade on the left of photos so the text stays readable
    xs = np.linspace(0, 1, W)
    alpha = np.clip(1.05 - xs * 1.25, 0, 0.92) * 255
    fade = Image.fromarray(np.dstack([np.full((H, W, 3), (8, 12, 24), np.uint8),
                                      np.repeat(alpha[None, :], H, axis=0).astype(np.uint8)]), "RGBA")

    strip, loop_w = L.ticker_strip([x["headline"] for x in stories])
    tick_y, tick_h = H - s(52), s(52)
    tmp = ImageDraw.Draw(Image.new("RGB", (1, 1)))
    label_w = int(L.tlen(tmp, L.t["headlines"], "tick")) + s(40)
    speed = s(110) / fps  # pixels per frame
    small = Font(s(13))

    cache = {"seg": None}
    breaking = persona(cfg).get("breaking", False)

    def card(si, stage):
        """Static layer for a segment at a reveal stage (cached per segment)."""
        key = ("card", stage)
        if key in cache:
            return cache[key]
        seg = segs[si]
        if seg["kind"] == "story" and seg["id"] in photos:
            layer = fade.copy()
            layer.paste(topbar, (0, 0))
            L.story_panel(layer, seg, stories.index(seg) + 1, len(stories), n_facts=stage[0], rest=stage[1],
                          w=s(640))
        else:
            layer = base.copy()
            if seg["kind"] == "intro":
                L.list_panel(layer, seg["headline"], [x["headline"] for x in stories[:6]][: stage[0]])
            elif seg["kind"] == "outro":
                k = cfg["editor"]["confirm_threshold"]
                L.list_panel(layer, seg["headline"], [p.format(k=k) for p in L.t["how_points"]][: stage[0]],
                             numbered=False)
            else:
                L.story_panel(layer, seg, stories.index(seg) + 1, len(stories), n_facts=stage[0], rest=stage[1])
            if mode != "puppet":
                L.desk(layer)
            if pz["character"] == "lion_photo":
                dd = ImageDraw.Draw(layer)
                small.draw(dd, (W - small.length(dd, anchor_mod.LION_PHOTO_CREDIT) - s(14), s(64)),
                           anchor_mod.LION_PHOTO_CREDIT, (220, 220, 220), stroke=2, stroke_fill=(0, 0, 0))
        cache[key] = layer
        return layer

    def frame_rgb(i):
        si = int(seg_of_frame[i])
        seg = segs[si]
        if cache["seg"] != si:  # keep memory small: only the current segment's layers are cached
            cache.clear()
            cache["seg"] = si
        tl = i / fps - starts[si]
        dur = seg["duration"]
        if seg["kind"] == "story":
            stage = _reveal_stage(seg, tl, dur)
        else:  # intro/outro lists build up line by line
            n_items = 6 if seg["kind"] == "intro" else len(L.t["how_points"])
            stage = (sum(tl >= dur * (0.15 + 0.6 * j / n_items) for j in range(n_items)), True)
        mouth, blink = int(mouths[min(i, len(mouths) - 1)]), bool(blinks[i])

        if seg["kind"] == "story" and seg["id"] in photos:
            imgs = photos[seg["id"]]
            slot = dur / len(imgs)
            k = min(int(tl / slot), len(imgs) - 1)
            p = (tl - k * slot) / slot
            img = _kenburns(imgs[k][0], p, W, H, k % 2 == 1)
            if p > 0.92 and k + 1 < len(imgs):  # crossfade into the next photo
                nxt = _kenburns(imgs[k + 1][0], 0.0, W, H, (k + 1) % 2 == 1)
                img = Image.blend(img, nxt, (p - 0.92) / 0.08)
            img = img.convert("RGBA")
            img.alpha_composite(card(si, stage))
            credit = "Photo: " + imgs[k][1] + (f"  |  {anchor_mod.LION_PHOTO_CREDIT}" if pz["character"] == "lion_photo"
                                               else "")
            dd = ImageDraw.Draw(img)
            cw = small.length(dd, credit)
            small.draw(dd, (W - cw - s(14), s(64)), credit, (230, 230, 230), stroke=2, stroke_fill=(0, 0, 0))
            mood = seg.get("mood") if fx else None
            pip = (fx["cool_pips"] if mood == "good" else pips)[(mouth, blink)]
            jx, jy = ((i * 7) % 9 - 4, (i * 5) % 7 - 3) if shake and mouth == 2 else (0, 0)
            pos = (pip_pos[0] + s(jx), pip_pos[1] + s(jy))
            if mood in ("bad", "good"):
                img.alpha_composite(fx["vig"][mood])
                pad = fx["pad"][mood]
                ring = fx["fire"][i % len(fx["fire"])] if mood == "bad" else fx["ice"]
                img.alpha_composite(ring, (pos[0] - pad, pos[1] - pad))
                fx["parts"][mood].draw(img, tl)
            img.alpha_composite(pip, pos)
        else:
            mood = seg.get("mood") if fx and seg["kind"] == "story" else None
            key = ("frame", stage, mouth, blink)
            if key not in cache:
                img = card(si, stage).copy()
                if sprites is not None:
                    sp = (fx["cool"] if mood == "good" else sprites)[(mouth, blink)]
                    img.alpha_composite(sp, anchor_pos)
                    L.desk(img)
                if mood in ("bad", "good"):
                    img.alpha_composite(fx["vig"][mood])
                cache[key] = img
            img = cache[key].copy()
            if mood in ("bad", "good"):
                fx["parts"][mood].draw(img, tl)

        if seg["kind"] == "story" and tl < TRANSITION:  # branded wipe: panel sweeps in, then out
            x = tl / TRANSITION
            left = 0 if x < 0.5 else int(W * _ease((x - 0.5) * 2))
            right = int(W * _ease(x * 2)) if x < 0.5 else W
            dd = ImageDraw.Draw(img)
            dd.rectangle([left, 0, right, H], fill=ACCENT)
            label = f"{L.t['story_word']} {stories.index(seg) + 1}"
            lw = L.tlen(dd, label, "thumb")
            if right - left > lw:
                L.text(dd, ((left + right - lw) / 2, H / 2 - s(40)), label, "thumb", WHITE)

        if breaking and seg["kind"] == "story" and int(tl * 2) % 2 == 0:  # flashing "BREAKING" pill
            dd = ImageDraw.Draw(img)
            bx = W // 2 - s(70)
            dd.rounded_rectangle([bx, s(12), bx + s(140), s(44)], radius=s(6), fill=(220, 20, 30))
            L.text(dd, (bx + (s(140) - L.tlen(dd, L.t["breaking"], "label")) / 2, s(15)), L.t["breaking"], "label",
                   WHITE)

        img = img.convert("RGB")
        dd = ImageDraw.Draw(img)
        dd.rectangle([0, tick_y, label_w, H], fill=ACCENT)
        L.text(dd, (s(20), tick_y + s(10)), L.t["headlines"], "tick", WHITE)
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
    lead = (stories[0].get("images") or [None])[0] if stories else None
    if lead:
        try:
            photo = _cover(Image.open(Path(out_dir) / lead["path"]), L.W, L.H).convert("RGBA")
            xs = np.linspace(0, 1, L.W)
            a = (np.clip(1.1 - xs * 1.1, 0.15, 0.9) * 255).astype(np.uint8)
            shade = Image.fromarray(np.dstack([np.full((L.H, L.W, 3), (8, 12, 24), np.uint8),
                                               np.repeat(a[None, :], L.H, axis=0)]), "RGBA")
            photo.alpha_composite(shade)
            photo.paste(base.crop((0, 0, L.W, s(56))), (0, 0))
            img, sprites = photo, None
        except OSError:
            pass
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
