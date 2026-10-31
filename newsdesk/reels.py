"""Instagram Reels (20-30 s): a rotating mix of news, real mysteries and "strange claim" news.

Every Reel follows the channel rule: facts are only what sources support; legends and claims are
always attributed ("according to...", "legend says..."), never presented as true.
"""
import datetime as dt
import html
import json
import os
import re

import feedparser
import requests
from pathlib import Path

from .cluster import cluster_stories
from .editor import _clean, _fix_spelling, _music_and_meme, _reports_text, _stray, wrong_language
from .fetch import fetch_all, fetch_full_text
from .llm import complete_json
from .persona import persona
from .strings import T
from .trends import reactions_text, reddit_reactions

WIKI_UA = {"User-Agent": "ZeroMasalaBot/1.0 (https://geekyarya.github.io/neutral-desk/)"}
IST = dt.timezone(dt.timedelta(hours=5, minutes=30))

COMMON_RULES = """Return JSON with these keys:
- "title": on-screen hook, max 45 characters, in {language_short}.
- "script": what the narrator says, {words} words, in {language}
  Start with a strong hook sentence. No greeting, no sign-off.
- "caption": Instagram caption, 2-3 short sentences in {language_short}, no hashtags.
"""

extra_keys = """- "angry": true only if the reports describe clear wrongdoing, negligence that hurt people, corruption or
  injustice; false for ordinary politics, weather, science, sport and achievements.
- "tragedy": true if it involves deaths, injuries, disasters, violence, crimes against people or children, or war
  casualties (told seriously: no jokes, no memes, no music).
- "music": "tense" (wrongdoing, attacks, anger), "upbeat" (good news), "chill" (ordinary news), "suspense"
  (mysterious things) or "none" (tragedies).
- "meme_line": only if tragedy is false: a funny Gen Z meme-style sticker line (max 6 words, exactly as it appears
  as its own sentence in the middle of "script"), e.g. "सीन बन गया भाई!". "" for tragedies.
- "visuals": 2-3 English Wikipedia article titles that illustrate it (places, institutions, landmarks, public figures).
- "image_queries": 2-3 short English photo-search phrases for it (places, events, objects; never private people).
"""

NEWS_PROMPT = """You write 20-30 second news Reels for a strictly neutral channel. Below are {n} reports of the
SAME event from independently owned outlets. State as fact only what at least {k} outlets report; attribute
anything else ("according to NDTV..."). No opinions, no emotional words, no speculation.
""" + COMMON_RULES + extra_keys + """- "about_india": true if the event is in India or directly involves India/Indians.
If PUBLIC REACTION posts are given, end the script with ONE sentence on the range of opinions, clearly framed as
opinion ("सोशल मीडिया पर कुछ लोगों का कहना है ..., तो कुछ ..."), no usernames, nothing hateful.

{style}

REPORTS:
{reports}
{reactions}"""

MYSTERY_PROMPT = """You write 20-30 second "mystery" Reels for a fact-first channel called Zero Masala.
Topic: {topic}. Use ONLY the Wikipedia text below. Structure: a hook question, what is documented, then the
legend or popular theory clearly labelled as such ("कहा जाता है" / "legend says"), and what experts or science
say if the text mentions it. Never claim anything supernatural is real. No fear-mongering.
""" + COMMON_RULES + """
WIKIPEDIA TEXT:
{text}
"""

SUPERNATURAL_PROMPT = """You write 20-30 second "strange news" Reels for a fact-first channel called Zero Masala.
Below are recent news headlines. Pick the ONE item that is a genuine news report about a strange, unexplained
or supernatural CLAIM in India (e.g. villagers report a ghost, a UFO sighting, an arrest for black magic).
Ignore ads, products, films, Halloween events, metaphors like "ghost employees", and anything violent toward a
person or child. If none qualifies, return {{"index": -1}}.
Otherwise also write the Reel: attribute every claim to the outlet ("according to ..."), say clearly that the
claim is not verified, and mention any rational explanation or official response given in the report. Never
present the supernatural as real and never encourage superstition or "remedies".
""" + COMMON_RULES + extra_keys + """- "index": the number of the chosen item.

HEADLINES:
{items}
"""


def ist_now():
    return dt.datetime.now(IST)


def pick_slot(cfg, slot=None, now=None):
    slots = cfg["reels"]["slots"]
    if slot is not None:
        return slots[slot]
    hour = (now or ist_now()).hour
    return min(slots, key=lambda s: abs(s["hour"] - hour))


def _lang(cfg):
    t = T(cfg)
    short = "Hindi (Devanagari)" if cfg["channel"]["language"] == "hi" else "English"
    return {"language": t["llm_language"], "language_short": short, "words": cfg["reels"]["words"]}


def _finish(res, cfg):
    """Spelling fixes + strip stray foreign-script characters; empty script if in the wrong language."""
    lang = cfg["channel"]["language"]
    if wrong_language(res, lang, ("title", "script")):
        return {**res, "title": "", "script": "", "caption": ""}
    res = _fix_spelling(res, cfg["editor"].get("spelling_fixes") or {})
    for key in ("title", "script", "caption"):
        res[key] = str(res.get(key) or "").strip()
    if _stray(" ".join(res[k] for k in ("title", "script", "caption")), lang):
        res["headline"] = res["title"]
        res = _clean(res, lang)
        res["title"] = res.pop("headline")
    return res


# ---------------- news ----------------

def _media_for(res, out_dir, prefix):
    """News photos (Wikipedia + Openverse) and, if one exists, a free video clip, for a Reel."""
    from .media import commons_video, openverse_images, topic_images
    folder = Path(out_dir)
    imgs = topic_images(res.get("visuals") or [], folder, prefix, limit=2)
    for q in res.get("image_queries") or []:
        if len(imgs) >= 4:
            break
        imgs += openverse_images(q, folder, f"{prefix}-{len(imgs)}")
    video = None
    for q in (res.get("image_queries") or [])[:2]:
        video = commons_video(q, folder, prefix, seconds=8)
        if video:
            break
    media = [{"type": "video", "path": video["path"], "credit": video["credit"]}] if video else []
    media += [{"type": "img", "path": m["path"], "credit": m["credit"]} for m in imgs]
    print(f"   visuals: {len(imgs)} photos, {1 if video else 0} video")
    return media


def make_news(cfg, used_urls, out_dir=None):
    india, world = cluster_stories(fetch_all(cfg), cfg)
    k = cfg["editor"]["confirm_threshold"]
    for story in india + world:
        urls = {a["url"] for a in story["articles"]}
        if urls & used_urls:
            continue  # already posted today
        for a in story["articles"]:
            a["text"] = fetch_full_text(a["url"])
        threads = reddit_reactions(story, cfg["trends"]["reddit_subs"]) if cfg.get("trends", {}).get("reddit") else []
        reactions = ("\nPUBLIC REACTION (Reddit, opinions NOT facts):\n" + reactions_text(threads)) if threads else ""
        res = complete_json(cfg, NEWS_PROMPT.format(n=len(story["articles"]), k=min(k, story["n_outlets"]),
                                                    reports=_reports_text(story), reactions=reactions,
                                                    style=persona(cfg)["style"],
                                                    **_lang(cfg)))
        if story["section"] == "india" and not res.get("about_india", True):
            continue
        res = _finish(res, cfg)
        if not res["script"]:
            continue
        res.update(_music_and_meme(res))
        outlets = list(dict.fromkeys(a["outlet"] for a in story["articles"]))
        res.update(type="news", urls=sorted(urls), sources=outlets, image=None, credit=None,
                   chip=T(cfg)["reported_by"].format(n=story["n_outlets"]),
                   media=_media_for(res, out_dir, "news") if out_dir else [])
        return res
    return None


# ---------------- mystery ----------------

def _wiki(title):
    r = requests.get("https://en.wikipedia.org/w/api.php", headers=WIKI_UA, timeout=30, params={
        "action": "query", "format": "json", "redirects": 1, "titles": title,
        "prop": "extracts|pageimages", "explaintext": 1, "exsectionformat": "plain", "exchars": 6000,
        "piprop": "name|original"})
    r.raise_for_status()
    page = next(iter(r.json()["query"]["pages"].values()))
    if "missing" in page or not page.get("extract"):
        return None
    return page


def _free_image(filename, out_dir):
    """Download the article's lead image only if it is freely licensed on Wikimedia Commons."""
    r = requests.get("https://commons.wikimedia.org/w/api.php", headers=WIKI_UA, timeout=30, params={
        "action": "query", "format": "json", "titles": f"File:{filename}", "prop": "imageinfo",
        "iiprop": "url|extmetadata", "iiurlwidth": 1600})
    page = next(iter(r.json()["query"]["pages"].values()))
    info = (page.get("imageinfo") or [None])[0]
    if not info:
        return None, None  # not on Commons -> usually a non-free local file: don't use it
    meta = info.get("extmetadata", {})
    lic = meta.get("LicenseShortName", {}).get("value", "")
    if not re.search(r"CC|Public domain|PD", lic, re.I):
        return None, None
    artist = re.sub(r"<[^>]+>", "", html.unescape(meta.get("Artist", {}).get("value", ""))).strip()
    img = requests.get(info.get("thumburl") or info["url"], headers=WIKI_UA, timeout=60)
    img.raise_for_status()
    path = out_dir / ("bg" + os.path.splitext(filename)[1].lower())
    path.write_bytes(img.content)
    return str(path), f"Image: {artist or 'Wikimedia Commons'}, {lic}"


def make_mystery(cfg, out_dir, slot_no):
    topics = cfg["reels"]["mystery_topics"]
    mystery_slots = [i for i, s in enumerate(cfg["reels"]["slots"]) if s["type"] == "mystery"]
    per_day = max(1, len(mystery_slots))
    order = mystery_slots.index(slot_no) if slot_no in mystery_slots else 0
    start = (ist_now().date().toordinal() * per_day + order) % len(topics)
    for i in range(len(topics)):  # skip topics Wikipedia can't serve right now
        topic = topics[(start + i) % len(topics)]
        try:
            page = _wiki(topic)
        except requests.RequestException as e:
            print(f"   Wikipedia error for {topic}: {e}")
            continue
        if not page:
            continue
        res = _finish(complete_json(cfg, MYSTERY_PROMPT.format(topic=page["title"], text=page["extract"],
                                                               **_lang(cfg))), cfg)
        if not res["script"]:
            continue
        image, credit = (None, None)
        if page.get("pageimage"):
            try:
                image, credit = _free_image(page["pageimage"], out_dir)
            except requests.RequestException:
                pass
        url = "https://en.wikipedia.org/wiki/" + page["title"].replace(" ", "_")
        res.update(music="suspense", meme_line="", tragedy=False)
        res.update(type="mystery", urls=[url], sources=["Wikipedia"], image=image, credit=credit, chip=None,
                   media=[{"type": "img", "path": image, "credit": credit}] if image else [])
        return res
    return None


# ---------------- strange-claim news ----------------

def make_supernatural(cfg, used_urls, out_dir=None):
    r = requests.get("https://news.google.com/rss/search", timeout=30, params={
        "q": cfg["reels"]["supernatural_query"], "hl": "en-IN", "gl": "IN", "ceid": "IN:en"})
    entries = [e for e in feedparser.parse(r.content).entries if e.link not in used_urls][:20]
    if not entries:
        return None
    items = "\n".join(f"[{i}] {e.title} — {re.sub(r'<[^>]+>', ' ', e.get('summary', ''))[:200]}"
                      for i, e in enumerate(entries))
    res = complete_json(cfg, SUPERNATURAL_PROMPT.format(items=items, **_lang(cfg)))
    idx = res.get("index", -1)
    if not isinstance(idx, int) or not 0 <= idx < len(entries):
        return None
    res = _finish(res, cfg)
    if not res["script"]:
        return None
    res.update(music="suspense", meme_line="", tragedy=False)
    e = entries[idx]
    source = (e.get("source") or {}).get("title") or e.title.rsplit(" - ", 1)[-1]
    res.update(type="supernatural", urls=[e.link], sources=[source], image=None, credit=None, chip=None,
               media=_media_for(res, out_dir, "strange") if out_dir else [])
    return res


def make_reel_content(cfg, slot_no, out_dir, used_urls):
    kind = cfg["reels"]["slots"][slot_no]["type"]
    makers = {"news": lambda: make_news(cfg, used_urls, out_dir),
              "mystery": lambda: make_mystery(cfg, out_dir, slot_no),
              "supernatural": lambda: make_supernatural(cfg, used_urls, out_dir)}
    content = makers[kind]()
    if content is None and kind != "mystery":  # nothing suitable -> a mystery instead
        print(f"   no suitable {kind} item; making a mystery Reel instead")
        content = make_mystery(cfg, out_dir, slot_no)
    if content is None:
        raise SystemExit("Could not make any Reel content right now.")
    return content


def caption_text(content, cfg):
    t = T(cfg)
    lines = [content["title"], "", content["caption"], ""]
    if content["type"] == "mystery":
        lines.append(f"{t['reel_source']}: Wikipedia ({content['urls'][0]})")
        if content.get("credit"):
            lines.append(content["credit"])
    else:
        lines.append(f"{t['reel_source']}: {', '.join(content['sources'])}")
        credits = [m["credit"] for m in content.get("media") or [] if m.get("credit")]
        if credits:
            lines.append("Photos/video: " + "; ".join(credits[:4]))
    lines += ["", t["reel_disclosure"], "", " ".join(cfg["reels"]["hashtags"][content["type"]])]
    return "\n".join(lines)[:2100]


def used_urls_from_github(hours=30):
    """URLs used by Reels posted in the last day (stored in the GitHub release notes)."""
    repo, token = os.environ.get("GITHUB_REPOSITORY"), os.environ.get("GITHUB_TOKEN")
    if not (repo and token):
        return set()
    r = requests.get(f"https://api.github.com/repos/{repo}/releases", params={"per_page": 50}, timeout=30,
                     headers={"Authorization": f"Bearer {token}"})
    if not r.ok:
        return set()
    cutoff = dt.datetime.now(dt.timezone.utc) - dt.timedelta(hours=hours)
    used = set()
    for rel in r.json():
        if not rel["tag_name"].startswith("reel-"):
            continue
        if dt.datetime.fromisoformat(rel["created_at"].replace("Z", "+00:00")) < cutoff:
            continue
        m = re.search(r"<!--urls:(.*?)-->", rel.get("body") or "", re.S)
        if m:
            used |= set(json.loads(m.group(1)))
    return used


def reel_already_posted(reel_id):
    """True if a Reel for this slot (release tag reel-<id>-...) was already made today."""
    repo, token = os.environ.get("GITHUB_REPOSITORY"), os.environ.get("GITHUB_TOKEN")
    if not (repo and token):
        return False
    r = requests.get(f"https://api.github.com/repos/{repo}/releases", params={"per_page": 50}, timeout=30,
                     headers={"Authorization": f"Bearer {token}"})
    return r.ok and any(rel["tag_name"].startswith(f"reel-{reel_id}-") for rel in r.json())
