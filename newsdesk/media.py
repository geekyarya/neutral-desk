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


def add_story_images(episode, out_dir):
    """Fetch pictures for each story from the Wikipedia topics the editor suggested."""
    for seg in episode["segments"]:
        if seg["kind"] == "story" and "images" not in seg:
            imgs = topic_images(seg.get("visuals") or [], Path(out_dir) / "images", seg["id"])
            seg["images"] = [{**im, "path": os.path.relpath(im["path"], out_dir)} for im in imgs]
            print(f"   {seg['id']}: {len(imgs)} pictures ({', '.join(im['title'] for im in imgs) or 'none'})")
    return episode
