"""Freely licensed pictures from Wikipedia / Wikimedia Commons (credited), for story visuals."""
import html
import os
import re
from pathlib import Path

import requests

WIKI_UA = {"User-Agent": "ZeroMasalaBot/1.0 (https://geekyarya.github.io/neutral-desk/)"}


def wiki_page(title, chars=6000):
    r = requests.get("https://en.wikipedia.org/w/api.php", headers=WIKI_UA, timeout=30, params={
        "action": "query", "format": "json", "redirects": 1, "titles": title,
        "prop": "extracts|pageimages", "explaintext": 1, "exsectionformat": "plain", "exchars": chars,
        "piprop": "name|original"})
    r.raise_for_status()
    page = next(iter(r.json()["query"]["pages"].values()))
    if "missing" in page or not page.get("extract"):
        return None
    return page


def free_image(filename, out_path):
    """Download a Commons image only if it is freely licensed; returns (path, credit) or (None, None)."""
    r = requests.get("https://commons.wikimedia.org/w/api.php", headers=WIKI_UA, timeout=30, params={
        "action": "query", "format": "json", "titles": f"File:{filename}", "prop": "imageinfo",
        "iiprop": "url|extmetadata|mime", "iiurlwidth": 1600})
    page = next(iter(r.json()["query"]["pages"].values()))
    info = (page.get("imageinfo") or [None])[0]
    if not info:
        return None, None  # not on Commons -> usually a non-free local file: don't use it
    if not str(info.get("mime", "image/jpeg")).startswith(("image/jpeg", "image/png", "image/webp")):
        return None, None  # skip SVG maps/logos and other formats that render badly as photos
    meta = info.get("extmetadata", {})
    lic = meta.get("LicenseShortName", {}).get("value", "")
    if not re.search(r"CC|Public domain|PD", lic, re.I):
        return None, None
    artist = re.sub(r"<[^>]+>", "", html.unescape(meta.get("Artist", {}).get("value", ""))).strip()
    img = requests.get(info.get("thumburl") or info["url"], headers=WIKI_UA, timeout=60)
    img.raise_for_status()
    out_path = Path(out_path).with_suffix(os.path.splitext(filename)[1].lower() or ".jpg")
    out_path.write_bytes(img.content)
    return str(out_path), f"{artist[:40] or 'Wikimedia Commons'}, {lic}"


def topic_images(titles, out_dir, prefix, limit=3):
    """Lead photos of the given Wikipedia articles, e.g. ['ISRO', 'Sriharikota'] -> [{path, credit, title}]."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    found = []
    for i, title in enumerate(titles):
        if len(found) >= limit:
            break
        try:
            page = wiki_page(title, chars=200)
            if not page or not page.get("pageimage"):
                continue
            path, credit = free_image(page["pageimage"], out_dir / f"{prefix}-{i}")
        except (requests.RequestException, ValueError, KeyError) as e:
            print(f"   (no picture for {title}: {e})")
            continue
        if path:
            found.append({"path": path, "credit": credit, "title": page["title"]})
    return found


def openverse_images(query, out_dir, prefix, limit=1):
    """Creative Commons photos (Flickr and more) from Openverse that allow commercial use and adaptation."""
    out_dir = Path(out_dir)
    found = []
    try:
        r = requests.get("https://api.openverse.org/v1/images/", headers=WIKI_UA, timeout=25, params={
            "q": query, "page_size": 10, "license_type": "commercial,modification", "mature": "false"})
        results = r.json().get("results", []) if r.ok else []
    except (requests.RequestException, ValueError):
        return found
    for i, res in enumerate(results):
        if len(found) >= limit:
            break
        if (res.get("width") or 0) < 800:
            continue
        try:
            img = requests.get(res["url"], headers=WIKI_UA, timeout=30)
            img.raise_for_status()
            from PIL import Image
            from io import BytesIO
            Image.open(BytesIO(img.content)).verify()
        except Exception:
            continue
        path = out_dir / f"{prefix}-ov{i}.jpg"
        path.write_bytes(img.content)
        lic = f"CC {res.get('license', '').upper()} {res.get('license_version', '')}".replace("CC CC0", "CC0")
        if res.get("license") == "pdm":
            lic = "Public domain"
        found.append({"path": str(path), "credit": f"{(res.get('creator') or 'unknown')[:40]}, {lic.strip()}",
                      "title": res.get("title") or query})
    return found


def commons_video(query, out_dir, prefix, seconds=10):
    """A freely licensed video clip from Wikimedia Commons, trimmed and resized for the bulletin (no audio)."""
    import subprocess
    try:
        r = requests.get("https://commons.wikimedia.org/w/api.php", headers=WIKI_UA, timeout=30, params={
            "action": "query", "format": "json", "list": "search", "srnamespace": 6, "srlimit": 5,
            "srsearch": f"{query} filetype:video"})
        titles = [x["title"] for x in r.json()["query"]["search"]]
    except (requests.RequestException, ValueError, KeyError):
        return None
    for title in titles:
        try:
            r = requests.get("https://commons.wikimedia.org/w/api.php", headers=WIKI_UA, timeout=30, params={
                "action": "query", "format": "json", "titles": title, "prop": "imageinfo",
                "iiprop": "url|extmetadata|size"})
            info = next(iter(r.json()["query"]["pages"].values()))["imageinfo"][0]
        except (requests.RequestException, ValueError, KeyError, StopIteration):
            continue
        meta = info.get("extmetadata", {})
        lic = meta.get("LicenseShortName", {}).get("value", "")
        if not re.search(r"CC|Public domain|PD", lic, re.I) or info.get("size", 0) > 60_000_000:
            continue
        out = Path(out_dir) / f"{prefix}-video.mp4"
        try:  # FFmpeg reads straight from the URL; keep the first seconds, 1280x720, no sound
            subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-user_agent", WIKI_UA["User-Agent"],
                            "-i", info["url"], "-t", str(seconds), "-an", "-vf",
                            "scale=1280:720:force_original_aspect_ratio=increase,crop=1280:720,fps=25",
                            "-c:v", "libx264", "-preset", "veryfast", "-crf", "23", str(out)],
                           check=True, timeout=180)
        except (subprocess.SubprocessError, OSError):
            continue
        artist = re.sub(r"<[^>]+>", "", html.unescape(meta.get("Artist", {}).get("value", ""))).strip()
        return {"path": str(out), "credit": f"{artist[:40] or 'Wikimedia Commons'}, {lic}", "title": title}
    return None


def add_story_images(episode, out_dir, max_photos=4):
    """Pictures (Wikipedia topics + Openverse searches) and, when one exists, a free video clip per story."""
    for seg in episode["segments"]:
        if seg["kind"] != "story" or "images" in seg:
            continue
        folder = Path(out_dir) / "images"
        folder.mkdir(parents=True, exist_ok=True)
        imgs = topic_images(seg.get("visuals") or [], folder, seg["id"], limit=2)
        for q in seg.get("image_queries") or []:
            if len(imgs) >= max_photos:
                break
            imgs += openverse_images(q, folder, f"{seg['id']}-{len(imgs)}")
        video = None
        for q in (seg.get("image_queries") or [])[:2] + (seg.get("visuals") or [])[:1]:
            video = commons_video(q, folder, seg["id"])
            if video:
                break
        rel = lambda m: {**m, "path": os.path.relpath(m["path"], out_dir)}
        seg["images"] = [rel(im) for im in imgs]
        seg["videos"] = [rel(video)] if video else []
        print(f"   {seg['id']}: {len(imgs)} pictures, {len(seg['videos'])} video "
              f"({', '.join(m['title'][:30] for m in imgs + seg['videos']) or 'none'})")
    return episode
