"""Free AI illustrations for the case-study videos (Pollinations: no key, no cost). Never depicts real people:
the prompts ask for generic fictional characters. Failures just fall back to photos or a title card."""
import base64
import os
import time
import urllib.parse
from concurrent.futures import ThreadPoolExecutor
from io import BytesIO
from pathlib import Path

import requests
from PIL import Image

STYLE = ("Vibrant 2D digital comic-book illustration in a modern Indian graphic-novel style, bright saturated colours, "
         "bold clean outlines, warm dramatic lighting, expressive cartoon faces, not photorealistic, not dark, "
         "widescreen 16:9, no text, no letters, no logos, no watermark. Scene: ")


GEMINI_IMAGE_MODELS = ["gemini-2.5-flash-image", "gemini-2.0-flash-preview-image-generation"]
_gemini_off = set()   # models whose free quota ran out (or that this key can't use) in this run


def gemini_image(prompt, path):
    """Try Gemini's image models (better quality). Returns the path, or None if unavailable/out of quota."""
    key = os.environ.get("GEMINI_API_KEY")
    if not key:
        return None
    for model in GEMINI_IMAGE_MODELS:
        if model in _gemini_off:
            continue
        try:
            r = requests.post(f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
                              params={"key": key}, timeout=120, json={
                                  "contents": [{"parts": [{"text": STYLE + prompt[:600]}]}],
                                  "generationConfig": {"responseModalities": ["IMAGE", "TEXT"],
                                                       "imageConfig": {"aspectRatio": "16:9"}}})
        except requests.RequestException:
            continue
        if r.status_code in (400, 403, 404, 429):
            print(f"   (image model {model}: HTTP {r.status_code} {r.text[:120].strip()!r}; not using it today)")
            _gemini_off.add(model)
            continue
        if not r.ok:
            continue
        for part in ((r.json().get("candidates") or [{}])[0].get("content") or {}).get("parts") or []:
            data = (part.get("inlineData") or part.get("inline_data") or {}).get("data")
            if data:
                try:
                    Image.open(BytesIO(base64.b64decode(data))).convert("RGB").save(path, quality=92)
                    return str(path)
                except OSError:
                    pass
    return None


def generate(prompt, path, seed=1, tries=5):
    """One 16:9 illustration at `path` (jpg): Gemini image model first, then the free Pollinations service."""
    got = gemini_image(prompt, path)
    if got:
        return got
    url = ("https://image.pollinations.ai/prompt/" + urllib.parse.quote(STYLE + prompt[:600]) +
           f"?width=1280&height=720&nologo=true&enhance=false&model=flux&seed={seed}")
    for attempt in range(tries):
        try:
            r = requests.get(url, timeout=120)
            if r.ok and r.headers.get("content-type", "").startswith("image"):
                img = Image.open(BytesIO(r.content)).convert("RGB")
                w, h = img.size
                img = img.crop((0, 0, w, int(h * 0.93)))  # the service stamps a small credit along the bottom edge
                img.save(path, quality=92)
                return str(path)
        except (requests.RequestException, OSError):
            pass
        time.sleep(8 * (attempt + 1))
    return None


def generate_scenes(ep, out_dir, workers=1):
    """Illustrate every scene of a case-study episode; stores scene['path'] (relative) when it worked."""
    out_dir = Path(out_dir)
    folder = out_dir / "scenes"
    folder.mkdir(exist_ok=True)
    jobs = []
    for seg in ep["segments"]:
        for j, sc in enumerate(seg.get("scenes") or []):
            if sc.get("image"):
                jobs.append((sc, folder / f"{seg['id']}-{j:02d}.jpg", len(jobs) + 11))
    if ep.get("thumb_image"):
        jobs.append((ep, folder / "thumb.jpg", 3))

    def run(job):
        target, path, seed = job
        prompt = target.get("image") or target.get("thumb_image")
        got = generate(prompt, path, seed)
        return target, got

    def keep(target, got):
        key = "path" if "image" in target else "thumb_path"
        target[key] = str(Path(got).relative_to(out_dir))

    done, missing = 0, []
    with ThreadPoolExecutor(max_workers=workers) as pool:
        for job, (target, got) in zip(jobs, pool.map(run, jobs)):
            if got:
                keep(target, got)
                done += 1
            else:
                missing.append(job)
            time.sleep(3)  # the free service throttles bursts
    for target, path, seed in missing:  # second pass, different seeds, after a pause
        time.sleep(20)
        got = generate(target.get("image") or target.get("thumb_image"), path, seed + 100)
        if got:
            keep(target, got)
            done += 1
    print(f"   illustrations: {done}/{len(jobs)} generated")
    return ep
