"""Special long-form episodes that replace the news bulletin on some days:
business case study, scam story (real, documented), and an original horror story (fiction, clearly labelled)."""
import datetime as dt
import os
import re

import requests

from .editor import _fix_spelling, complete_json, wrong_language
from .strings import date_text

WIKI = "https://en.wikipedia.org/w/api.php"
UA = {"User-Agent": "ZeroMasalaBot/1.0 (https://geekyarya.github.io/neutral-desk/)"}
SPECIAL = ("business", "scam", "horror")
LABEL = {"business": "केस स्टडी", "scam": "घोटाले की कहानी", "horror": "काल्पनिक डरावनी कहानी"}
SFX = ["wind", "creak", "heartbeat", "whisper", "knock", "footsteps", "bell", "silence"]
SCENES = ["house", "forest", "corridor", "road", "well", "station", "room", "village"]

SCENE_KEYS = """- "title": a punchy Hinglish YouTube title (max 70 characters) with a hook, in the style of
  "Ather लो या Vida, पैसा तो Hero का ही बनेगा!" (Devanagari Hindi mixed with English brand names).
- "hook": 2 short spoken sentences in Hindi that open the video with a curious question or surprising claim taken from
  the text (no greeting, no channel name).
- "summary": 2 sentences in Hindi for the video description.
- "thumb_text": 3 to 5 punchy Hinglish words for the thumbnail banner (e.g. "Hero का Double Game!").
- "thumb_image": an English prompt for the thumbnail illustration: one dramatic, symbolic scene with generic
  fictional characters.
- "chapters": exactly 6 chapters, each {{"title": short Hindi chapter title (max 35 characters),
  "music": "tense" | "upbeat" | "chill",
  "visuals": 2-3 English Wikipedia article titles of the SPECIFIC companies, products or places in this chapter,
  "scenes": exactly 5 scenes, each {{"line": 1-2 spoken sentences in Hindi (Devanagari), 25 to 35 words, in a warm,
  conversational storyteller voice,
  "image": an English prompt describing what to illustrate for this line: setting, action, mood, with GENERIC
  FICTIONAL characters (e.g. "a middle-aged businessman in a navy suit"); never a real named person's face, no text,
  "text": a punchy on-screen phrase of at most 4 words in Hinglish for key moments, otherwise "",
  "hl": 1 to 3 words copied exactly from "line" to highlight on screen (numbers, key terms)}}}}."""

BUSINESS_PROMPT = """You write a Hindi YouTube long-form BUSINESS CASE STUDY for the fact-first channel Zero Masala.
Topic: {topic}. Use ONLY the Wikipedia text below. First decide whether it is safe: if it mainly concerns a death,
a crime against a person, a child, or a communal incident, return only {{"skip": true}}.
Chapters in order: 1 an intriguing hook and the company today, 2 how it started, 3 the big idea that made it grow,
4 the turning point or crisis, 5 what happened next (state numbers and dates only if they are in the text), 6 three
clear lessons for viewers. Neutral tone, no investment advice, no claims beyond the text. {style}
Return JSON with:
""" + SCENE_KEYS + """

WIKIPEDIA TEXT:
{text}
"""

SCAM_PROMPT = """You write a Hindi YouTube long-form SCAM STORY for the fact-first channel Zero Masala.
Topic: {topic}. Use ONLY the Wikipedia text below. First decide whether it is safe: if it mainly concerns violence,
a child, a communal incident, or an accusation against someone that the text does not present as established
(convicted, found liable, or officially concluded), return only {{"skip": true}}.
Chapters in order: 1 hook, 2 how the scheme worked and why people trusted it, 3 how it grew, 4 how it collapsed or
was caught, 5 what the courts and authorities concluded (use "alleged" for anything not established), 6 three warning
signs viewers can use to protect themselves. Never explain how to commit fraud. Name only people the text names.
{style}
Return JSON with:
""" + SCENE_KEYS + """

WIKIPEDIA TEXT:
{text}
"""

HORROR_PROMPT = """You write a Hindi YouTube HORROR STORY for the channel Zero Masala. It is ENTIRELY FICTION, original,
told by the narrator in first person. Seed idea: {theme}.
Rules: no real people, real named places, brands, religions or communities as villains; no gore, no sexual
content, no harm to children, no suicide, no real crimes. Scare with atmosphere, suspense and small details, build slowly
and end with an unsettling twist. {style}
Return JSON with:
- "title": a short Hindi title (max 60 characters).
- "summary": 2 sentences in Hindi for the description (say it is a fictional story).
- "chapters": a list of exactly 7 chapters, each {{"title": short Hindi title (max 30 characters),
  "script": narration of {words} words in Hindi (Devanagari), simple spoken Hindi, short tense sentences,
  "scene": one of {scenes}, "sfx": a list of 1-3 sound cues from {sfx} that fit the chapter,
  "intensity": 1 (calm), 2 (uneasy) or 3 (terrifying)}}.
"""


def pick_format(cfg, today=None):
    forced = os.environ.get("EPISODE_FORMAT", "").strip()
    if forced in SPECIAL or forced == "news":
        return forced
    seq = cfg.get("daily_formats") or ["news"]
    today = today or dt.datetime.now(dt.timezone(dt.timedelta(hours=5, minutes=30))).date()
    return seq[today.weekday() % len(seq)]


def _wiki_text(title):
    for _ in range(3):
        r = requests.get(WIKI, headers=UA, timeout=30, params={
            "action": "query", "format": "json", "redirects": 1, "titles": title, "prop": "extracts",
            "explaintext": 1, "exsectionformat": "plain", "exchars": 14000})
        if r.status_code == 200:
            page = next(iter(r.json()["query"]["pages"].values()))
            if "missing" not in page and page.get("extract"):
                return page["title"], page["extract"]
            return None
    return None


def _clean_chapters(res, cfg, keys=("title", "script")):
    lang = cfg["channel"]["language"]
    fixes = cfg["editor"].get("spelling_fixes") or {}
    out = []
    for c in res.get("chapters") or []:
        if not isinstance(c, dict) or not str(c.get("script") or "").strip():
            continue
        if wrong_language(c, lang, keys):
            continue
        out.append(_fix_spelling({**c, "title": str(c.get("title") or "").strip(),
                                  "script": str(c["script"]).strip()}, fixes))
    return out


def _clean_scene_chapters(res, cfg):
    lang = cfg["channel"]["language"]
    fixes = cfg["editor"].get("spelling_fixes") or {}
    out = []
    for c in res.get("chapters") or []:
        scenes = []
        for sc in (c.get("scenes") or []) if isinstance(c, dict) else []:
            if not isinstance(sc, dict) or not str(sc.get("line") or "").strip():
                continue
            if wrong_language(sc, lang, ("line",)):
                continue
            sc = _fix_spelling({**sc, "line": str(sc["line"]).strip()}, fixes)
            line = sc["line"]
            scenes.append({"line": line, "image": str(sc.get("image") or "")[:500],
                           "text": str(sc.get("text") or "").strip()[:30],
                           "hl": [w for w in (sc.get("hl") or []) if isinstance(w, str) and w in line][:3]})
        if len(scenes) >= 3:
            out.append({"title": str(c.get("title") or "").strip(), "scenes": scenes,
                        "script": " ".join(x["line"] for x in scenes),
                        "music": c.get("music"), "visuals": c.get("visuals") or []})
    return out


def _episode(cfg, fmt, res, chapters, sources, today):
    name = cfg["channel"].get("spoken_name") or cfg["channel"]["name"]
    title = str(res.get("title") or "").strip()
    intro_txt = {
        "business": f"नमस्कार दोस्तों, मैं हूं बब्बर भाई, और ये है {name}! आज की केस स्टडी है: {title}। "
                    "आखिर तक देखिएगा, क्योंकि आखिर में काम की सीख मिलेगी!",
        "scam": f"नमस्कार दोस्तों, मैं हूं बब्बर भाई, और ये है {name}! आज की कहानी है एक घोटाले की: {title}। "
                "ताकि आप खुद ऐसे जाल में न फंसें, पूरी कहानी ध्यान से सुनिए।",
        "horror": f"नमस्कार दोस्तों, मैं हूं बब्बर भाई, और ये है {name}। ये एक काल्पनिक डरावनी कहानी है, "
                  "सच्ची घटना नहीं। लाइट बंद कीजिए, हेडफोन लगाइए, और सुनिए: " + title,
    }[fmt]
    outro_txt = {
        "business": f"तो दोस्तों, ये थी आज की केस स्टडी। वीडियो पसंद आया हो तो लाइक कीजिए, शेयर कीजिए और {name} को फॉलो कीजिए। "
                    "कल फिर मिलेंगे!",
        "scam": f"तो दोस्तों, ये थी पूरी कहानी। सावधान रहिए, सतर्क रहिए, और ये वीडियो उनको भी भेजिए जिन्हें इसकी ज़रूरत है। "
                f"फॉलो कीजिए {name}।",
        "horror": f"तो दोस्तों, ये थी आज की काल्पनिक डरावनी कहानी। कैसी लगी, कमेंट में बताइए, और {name} को फॉलो कीजिए। "
                  "अब नींद आएगी या नहीं, ये आप जानिए!",
    }[fmt]
    scene_fmt = fmt in ("business", "scam")
    if scene_fmt:
        hook = str(res.get("hook") or "").strip()
        intro_txt = hook or intro_txt
        outro_txt = {"business": f"तो ये थी आज की कहानी। पसंद आई हो तो वीडियो को लाइक और शेयर कीजिए, और {name} को फॉलो कीजिए।",
                     "scam": f"तो ये थी पूरी कहानी। सतर्क रहिए, और ये वीडियो उन्हें भी भेजिए जिन्हें इसकी ज़रूरत है। "
                             f"{name} को फॉलो कीजिए।"}[fmt]
    segs = [{"id": "intro", "kind": "intro", "headline": title, "script": intro_txt}]
    for i, c in enumerate(chapters, 1):
        seg = {"id": f"ch{i:02d}", "kind": "story", "section": fmt, "headline": c["title"], "script": c["script"],
               "short_script": "", "mood": "neutral", "music": c.get("music") if c.get("music") in
               ("tense", "upbeat", "chill") else "chill", "meme_line": "", "angry": False,
               "tragedy": fmt == "horror",  # horror is narrated in the serious, hushed voice
               "visuals": [str(v) for v in (c.get("visuals") or [])][:4],
               "image_queries": [str(q) for q in (c.get("image_queries") or [])][:3],
               "confirmed_facts": [], "disputed": [], "n_outlets": 1, "countries": [], "foreign": False,
               "sources": sources}
        if scene_fmt:
            seg.update(scenes=c["scenes"], voice="story", visuals=[str(v) for v in (c.get("visuals") or [])][:3])
        if fmt == "horror":
            sc = c.get("scene") if c.get("scene") in SCENES else SCENES[i % len(SCENES)]
            seg.update(scene=sc, sfx=[x for x in c.get("sfx") or [] if x in SFX][:3] or ["wind"],
                       intensity=c.get("intensity") if c.get("intensity") in (1, 2, 3) else 2,
                       visuals=[], image_queries=[f"{'abandoned house' if sc in ('house', 'room') else sc} "
                                                  f"night fog"][:1])
        segs.append(seg)
    segs.append({"id": "outro", "kind": "outro", "headline": name, "script": outro_txt})
    tag = LABEL[fmt]
    yt_title = f"{title} | {'Case Study' if fmt == 'business' else 'Scam Story' if fmt == 'scam' else tag}" \
        if scene_fmt else f"{title} | {tag}"
    if len(yt_title) > 100:
        yt_title = title[:90]
    lines = [str(res.get("summary") or "").strip(), "", "अध्याय:"]
    lines += [f"{i}. {c['title']}" for i, c in enumerate(chapters, 1)]
    if fmt == "horror":
        lines += ["", "यह पूरी तरह काल्पनिक कहानी है। इसके सभी पात्र, स्थान और घटनाएँ काल्पनिक हैं।"]
    else:
        lines += ["", "स्रोत:"] + [f"• {s['outlet']}: {s['url']}" for s in sources]
        lines += ["", "सारी जानकारी सार्वजनिक स्रोतों पर आधारित है; जहाँ बात साबित नहीं हुई, वहाँ उसे आरोप कहा गया है।"]
    tags = {"business": "#casestudy #business #hindi #zeromasala", "scam": "#scam #fraud #hindi #zeromasala",
            "horror": "#horrorstory #darawanikahani #hindi #zeromasala"}[fmt]
    lines += ["", tags]
    return {"date": today.isoformat(), "channel": cfg["channel"]["name"], "language": cfg["channel"]["language"],
            "format": fmt, "thumb_text": str(res.get("thumb_text") or "").strip(),
            "thumb_image": str(res.get("thumb_image") or "").strip()[:500], "title": yt_title, "description": "\n".join(lines)[:4900], "tag": tag,
            "segments": segs}


def build_special(cfg, fmt, today=None):
    """Write a long-form episode (dict like the news episode). Returns None if nothing suitable could be written."""
    from .persona import persona
    today = today or dt.datetime.now(dt.timezone(dt.timedelta(hours=5, minutes=30))).date()
    sp = cfg.get("special") or {}
    words = sp.get("words", "110 to 130")
    style = "Tone: " + ("a gripping, hushed storyteller" if fmt == "horror" else
                        "a warm, witty finance-YouTuber storyteller talking to a friend in simple Hinglish-flavoured "
                        "Hindi, with rhetorical questions, vivid comparisons and light humour; no shouting, no taunts")
    lang = "Hindi"
    if fmt == "horror":
        themes = sp.get("horror_themes") or ["एक सुनसान रेलवे स्टेशन की आखिरी ट्रेन"]
        theme = themes[(today.toordinal() // 7) % len(themes)]
        res = complete_json(cfg, HORROR_PROMPT.format(theme=theme, words=words, style=style, scenes=SCENES,
                                                      sfx=SFX))
        chapters = _clean_chapters(res, cfg)
        if len(chapters) < 4:
            return None
        for c, raw in zip(chapters, res.get("chapters") or []):
            c.update(scene=raw.get("scene"), sfx=raw.get("sfx"), intensity=raw.get("intensity"))
        return _episode(cfg, fmt, res, chapters, [], today)
    pool = sp.get(f"{fmt}_topics") or []
    if not pool:
        return None
    start = (today.toordinal() // 7) % len(pool)
    for i in range(len(pool)):
        topic = pool[(start + i) % len(pool)]
        try:
            page = _wiki_text(topic)
        except requests.RequestException as e:
            print(f"   Wikipedia error for {topic}: {e}")
            continue
        if not page:
            continue
        title, text = page
        prompt = (BUSINESS_PROMPT if fmt == "business" else SCAM_PROMPT).format(
            topic=title, text=text, words=words, style=style)
        res = complete_json(cfg, prompt)
        if res.get("skip"):
            print(f"   skipping sensitive topic: {title}")
            continue
        chapters = _clean_scene_chapters(res, cfg)
        if len(chapters) < 4:
            print(f"   not enough usable chapters for {title}")
            continue
        src = [{"outlet": "Wikipedia", "owner": "Wikipedia", "country": "", "title": title,
                "url": "https://en.wikipedia.org/wiki/" + title.replace(" ", "_")}]
        return _episode(cfg, fmt, res, chapters, src, today)
    return None
