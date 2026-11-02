"""Cricket Reels: current India cricket news, and player stat comparisons from Wikipedia's cricketer infoboxes."""
import re

import feedparser
import requests

from .editor import _music_and_meme, complete_json
from .persona import persona

WIKI = "https://en.wikipedia.org/w/api.php"
UA = {"User-Agent": "ZeroMasalaBot/1.0 (https://geekyarya.github.io/neutral-desk/)"}
FEEDS = [("ESPNcricinfo", "https://www.espncricinfo.com/rss/content/story/feeds/0.xml")]
FORMATS = ("Test", "ODI", "T20I")
CRICKET_STYLE = (
    "Voice: an energetic, funny cricket-fan commentator talking to Gen Z friends. NOT a news-channel anchor: never "
    "open with 'breaking', never say 'janta jawab maang rahi hai', never use outrage, debate-show shouting, "
    "slogans or 'sources say' drama. Start straight with the actual cricket news or the hook question. Light "
    "Hinglish fan slang is fine (e.g. 'क्या खेला भाई!', 'मैच पलट दिया!'). No anger, no taunting; praise and "
    "banter only. Never mock players, never run a player down.")
CRICKET_QUERIES = ["cricket match stadium", "India cricket team"]


def _prompts():
    from .reels import COMMON_RULES, extra_keys
    news = """You write 20-30 second cricket news Reels for a fact-first channel called Zero Masala.
Below are recent cricket headlines from different outlets. Pick the ONE story that matters most to Indian fans
right now (an ongoing or just-finished India match, series or tournament first; otherwise a major India player or
team story). Use all items about that same story. State scores, results and numbers ONLY if they appear in the
items; attribute anything reported by a single outlet ("according to ..."); never invent a score, player quote or
prediction. If nothing is about cricket involving India, return {{"index": []}}.
""" + COMMON_RULES + extra_keys + """- "index": list of the numbers of the items about the chosen story.

{style}
- "image_queries" for cricket: 2-3 short English phrases for photos, always including "cricket" plus the match, series, stadium or player name.

ITEMS:
{items}
"""
    stats = """You write 20-30 second cricket "stats face-off" Reels for a fact-first channel called Zero Masala.
Compare {a} and {b} using ONLY the numbers below (from Wikipedia, as of {date}). Hook with a question
fans argue about, give 3-4 striking head-to-head numbers, then a fair verdict (who leads in what; both have strengths).
Do not invent any number, rank or record that is not in the data. Say the stats are as per Wikipedia.
""" + COMMON_RULES + extra_keys + """
{data}

{style}
"""
    celeb = """You write 20-30 second celebrity news Reels for a fact-first channel called Zero Masala.
Below are recent headlines about Indian film, TV, music and sports celebrities. Pick the ONE most talked-about
item about their PUBLIC work or public statements (film or show releases, box office, trailers, awards, public
appearances, announcements, interviews). Use all items about that same story. Attribute everything to the outlet
("according to ..."), state only what the items say, never add rumours, quotes or details.
SKIP (return {{"index": []}}) anything about: deaths, illness or health, affairs, breakups or divorce, children,
leaked photos or videos, arrests or unproven legal allegations, body-shaming, or gossip without a named outlet.
Keep it light, playful and respectful; tease the news, never the person's private life.
""" + COMMON_RULES + extra_keys + """- "index": list of the numbers of the items about the chosen story.

{style}
- "image_queries" for cricket: 2-3 short English phrases for photos, always including "cricket" plus the match, series, stadium or player name.

ITEMS:
{items}
"""
    return news, stats, celeb


def _google_items(query):
    items = []
    try:
        r = requests.get("https://news.google.com/rss/search", timeout=30,
                         params={"q": query, "hl": "en-IN", "gl": "IN", "ceid": "IN:en"})
        for e in feedparser.parse(r.content).entries[:25]:
            src = (e.get("source") or {}).get("title") or e.title.rsplit(" - ", 1)[-1]
            items.append((e.title.rsplit(" - ", 1)[0], src, e.link))
    except requests.RequestException as e:
        print(f"   news search error: {e}")
    return items


def _story_from_items(cfg, items, prompt, kind, out_dir, music="upbeat", style=None):
    """Ask the LLM to pick and write one story from (title, outlet, url) items; None if nothing suitable."""
    from .reels import _finish, _lang, _media_for
    if not items:
        return None
    text = "\n".join(f"[{n}] ({src}) {title}" for n, (title, src, _) in enumerate(items))
    res = complete_json(cfg, prompt.format(items=text, style=style or persona(cfg)["style"], **_lang(cfg)))
    idx = [i for i in (res.get("index") or []) if isinstance(i, int) and 0 <= i < len(items)]
    if not idx:
        return None
    res = _finish(res, cfg)
    if not res["script"]:
        return None
    res.update(_music_and_meme(res))
    if kind == "cricket":
        res["angry"] = False
        res["image_queries"] = (res.get("image_queries") or [])[:3] + CRICKET_QUERIES
    if res.get("music") in (None, "", "chill"):
        res["music"] = "none" if res.get("tragedy") else music
    chosen = [items[i] for i in idx]
    res.update(type=kind, urls=[c[2] for c in chosen], sources=list(dict.fromkeys(c[1] for c in chosen)),
               source_items=[{"outlet": c[1], "title": c[0], "url": c[2]} for c in chosen],
               image=None, credit=None, chip=None, media=_media_for(res, out_dir, kind))
    if kind == "cricket":
        res["media"] = _with_photos(res["media"], res.get("visuals") or [], out_dir)
    return res


def cricket_news(cfg, used_urls, out_dir):
    items = _google_items(cfg["reels"].get("cricket_query", "cricket India when:2d"))
    for name, url in FEEDS:
        try:
            for e in feedparser.parse(requests.get(url, headers=UA, timeout=30).content).entries[:10]:
                items.append((e.title, name, e.link))
        except requests.RequestException:
            pass
    return _story_from_items(cfg, [i for i in items if i[2] not in used_urls], _prompts()[0], "cricket", out_dir, style=CRICKET_STYLE)


def celeb_news(cfg, used_urls, out_dir):
    items = _google_items(cfg["reels"].get("celeb_query", "Bollywood celebrity India when:1d"))
    return _story_from_items(cfg, [i for i in items if i[2] not in used_urls], _prompts()[2], "celeb", out_dir)


def _infobox(title):
    r = requests.get(WIKI, headers=UA, timeout=30, params={
        "action": "query", "format": "json", "redirects": 1, "titles": title, "prop": "revisions",
        "rvprop": "content", "rvslots": "main", "rvsection": 0})
    r.raise_for_status()
    page = next(iter(r.json()["query"]["pages"].values()))
    return page["revisions"][0]["slots"]["main"]["*"], page["title"]


def player_stats(title):
    """{'name', 'date', 'lines': [...]} from the cricketer infobox, or None."""
    text, name = _infobox(title)
    f = {k.strip(): v.strip() for k, v in re.findall(r"^\|\s*([^=|]+?)\s*=\s*(.*)$", text, re.M)}
    lines, rows = [], {}
    for i in (1, 2, 3, 4):
        fmt = re.sub(r"\[\[(?:[^|\]]*\|)?([^\]]*)\]\]", r"\1", f.get(f"column{i}", ""))
        if fmt not in FORMATS or not f.get(f"matches{i}"):
            continue
        parts = [f"{fmt}: {f[f'matches{i}']} matches"]
        if f.get(f"runs{i}"):
            parts.append(f"{f[f'runs{i}']} runs, average {f.get(f'bat avg{i}', '-')}, "
                         f"100s/50s {f.get(f'100s/50s{i}', '-')}, highest {f.get(f'top score{i}', '-')}")
        if f.get(f"wickets{i}") not in (None, "", "0", "–"):
            parts.append(f"{f[f'wickets{i}']} wickets, bowling average {f.get(f'bowl avg{i}', '-')}, "
                         f"best {f.get(f'best bowling{i}', '-')}")
        lines.append("; ".join(parts))
        rows[fmt] = {"Matches": f[f"matches{i}"], "Runs": f.get(f"runs{i}"), "Average": f.get(f"bat avg{i}"),
                     "100s / 50s": f.get(f"100s/50s{i}"), "Wickets": f.get(f"wickets{i}"),
                     "Bowling avg": f.get(f"bowl avg{i}")}
    if not lines:
        return None
    date = re.sub(r"\{\{[^}]*\}\}|<[^>]+>", "", f.get("date", "")).strip() or "recently"
    return {"name": name, "date": date, "lines": lines, "rows": rows}


def cricket_stats(cfg, out_dir):
    from .reels import _finish, _lang, _media_for, ist_now
    pairs = cfg["reels"].get("cricket_pairs") or []
    if not pairs:
        return None
    start = ist_now().date().toordinal() % len(pairs)
    for i in range(len(pairs)):
        a, b = pairs[(start + i) % len(pairs)]
        try:
            sa, sb = player_stats(a), player_stats(b)
        except (requests.RequestException, KeyError, ValueError) as e:
            print(f"   cricket stats error for {a} vs {b}: {e}")
            continue
        if not sa or not sb:
            continue
        data = "\n".join(f"{s['name']}:\n  " + "\n  ".join(s["lines"]) for s in (sa, sb))
        res = complete_json(cfg, _prompts()[1].format(a=sa["name"], b=sb["name"], date=sa["date"], data=data,
                                                     style=CRICKET_STYLE, **_lang(cfg)))
        res = _finish(res, cfg)
        if not res["script"]:
            continue
        res.update(_music_and_meme(res))
        res.update(music="upbeat", tragedy=False, angry=False)
        res["visuals"] = [sa["name"], sb["name"]]
        res["image_queries"] = (res.get("image_queries") or [])[:2] + CRICKET_QUERIES
        cards = stats_cards(sa, sb, out_dir)
        res.update(type="cricket", sources=["Wikipedia (player statistics)"], image=None, credit=None, chip=None,
                   urls=["https://en.wikipedia.org/wiki/" + s["name"].replace(" ", "_") for s in (sa, sb)],
                   media=cards + _with_photos(_media_for(res, out_dir, "cricket"), [sa["name"], sb["name"]], out_dir))
        return res
    return None


def make_cricket(cfg, used_urls, out_dir):
    """News on one day, stats face-off the next; whichever fails falls back to the other."""
    from .reels import ist_now
    order = [lambda: cricket_news(cfg, used_urls, out_dir), lambda: cricket_stats(cfg, out_dir)]
    if ist_now().date().toordinal() % 2:
        order.reverse()
    for make in order:
        content = make()
        if content:
            return content
    return None


def build_extras(cfg, used_urls=()):
    """Rapid-round bulletin segments (cricket, celeb, strange news) written like story segments.
    They are single-pass, attributed reports, not cross-checked facts, and are labelled that way on screen."""
    from .reels import make_supernatural
    from .strings import T
    t, out = T(cfg), []
    makers = {"cricket": lambda: cricket_news(cfg, set(used_urls), None_dir()),
              "celeb": lambda: celeb_news(cfg, set(used_urls), None_dir()),
              "supernatural": lambda: make_supernatural(cfg, set(used_urls), None_dir())}
    for kind in cfg.get("bulletin_extras") or []:
        print(f"Extras: {kind}")
        try:
            c = makers[kind]()
        except Exception as e:  # an extra must never kill the bulletin
            print(f"   skipped: {e}")
            continue
        if not c:
            print("   nothing suitable today")
            continue
        items = c.get("source_items") or [{"outlet": o, "title": c["title"], "url": u}
                                          for o, u in zip(c["sources"], c["urls"])]
        out.append({"id": f"extra-{kind}", "kind": "story", "section": "extra", "extra": kind,
                    "headline": c["title"], "script": c["script"], "short_script": c["script"],
                    "public_reaction": "", "why_it_matters": "", "mood": "neutral",
                    "music": c.get("music") or "upbeat", "meme_line": c.get("meme_line", ""),
                    "meme_at": c.get("meme_at", 0.5), "tragedy": bool(c.get("tragedy")),
                    "angry": bool(c.get("angry")) and not c.get("tragedy"),
                    "image_queries": c.get("image_queries") or [], "visuals": c.get("visuals") or [],
                    "confirmed_facts": [], "disputed": [], "n_outlets": len(items), "countries": ["India"],
                    "foreign": False,
                    "chip": t["extra_chip"].format(tag=t["extra_tags"][kind], n=len(items)),
                    "sources": [{"outlet": i["outlet"], "owner": i["outlet"], "country": "India",
                                 "title": i["title"], "url": i["url"]} for i in items]})
    return out


def None_dir():
    import tempfile
    from pathlib import Path
    return Path(tempfile.mkdtemp())


def _num(v):
    try:
        return float(re.sub(r"[^0-9.]", "", str(v).split("/")[0]))
    except ValueError:
        return None


def stats_cards(sa, sb, out_dir, max_cards=2):
    """Head-to-head stat cards (PIL images) for formats both players have; the better number is highlighted."""
    from pathlib import Path

    from PIL import Image, ImageDraw

    from .text import Font
    W, H = 1080, 1920
    big, mid, small = Font(64, True), Font(46, True), Font(34, True)
    cards = []
    for fmt in FORMATS:
        ra, rb = sa["rows"].get(fmt), sb["rows"].get(fmt)
        if not ra or not rb or len(cards) >= max_cards:
            continue
        keys = ["Matches"]
        if ra.get("Runs") and rb.get("Runs"):
            keys += ["Runs", "Average", "100s / 50s"]
        if all((_num(r.get("Wickets")) or 0) >= 20 for r in (ra, rb)):
            keys += ["Wickets", "Bowling avg"]
        if len(keys) < 3:
            continue
        if "Wickets" in keys and len(keys) > 4:
            keys = ["Matches", "Runs", "Wickets", "Bowling avg"]
        keys = keys[:4]
        img = Image.new("RGB", (W, H), (10, 18, 40))
        d = ImageDraw.Draw(img)
        y0 = 590
        d.rounded_rectangle([40, y0 - 20, W - 40, y0 + 130 + 82 * len(keys) + 10], radius=30, fill=(18, 28, 56),
                            outline=(30, 150, 80), width=4)
        x1, x2 = 250, 830
        for x, st in ((x1, sa), (x2, sb)):
            last = st["name"].split()[-1].upper()
            big.draw(d, (x - big.length(d, last) / 2, y0), last, (255, 255, 255))
        small.draw(d, ((W - small.length(d, fmt)) / 2, y0 + 12), fmt, (130, 210, 160))
        y = y0 + 125
        for k in keys:
            va, vb = ra.get(k) or "-", rb.get(k) or "-"
            na, nb = _num(va), _num(vb)
            better = None
            if na is not None and nb is not None and na != nb and k not in ("Matches", "100s / 50s"):
                better = (na > nb) != (k == "Bowling avg")
            for x, v, win in ((x1, va, better is True), (x2, vb, better is False)):
                mid.draw(d, (x - mid.length(d, v) / 2, y), v, (255, 214, 64) if win else (235, 235, 235))
            lab = Font(28, True)
            lab.draw(d, ((W - lab.length(d, k)) / 2, y + 10), k, (150, 165, 200))
            y += 82
        path = Path(out_dir) / f"statcard-{len(cards)}.png"
        img.save(path)
        cards.append({"type": "img", "path": str(path), "credit": None})
    return cards


def commons_photos(query, out_dir, prefix, limit=1):
    """Freely licensed Commons photos found by a file search (e.g. a player's name); credit included."""
    from pathlib import Path

    from .media import free_image
    out_dir, found = Path(out_dir), []
    try:
        r = requests.get("https://commons.wikimedia.org/w/api.php", headers=UA, timeout=30, params={
            "action": "query", "format": "json", "list": "search", "srnamespace": 6,
            "srsearch": f"{query} filetype:bitmap", "srlimit": 8})
        hits = [h["title"][5:] for h in r.json().get("query", {}).get("search", [])]
    except (requests.RequestException, ValueError, KeyError) as e:
        print(f"   (commons search failed for {query}: {e})")
        return found
    for i, name in enumerate(hits):
        if len(found) >= limit:
            break
        if not name.lower().endswith((".jpg", ".jpeg", ".png")):
            continue
        try:
            path, credit = free_image(name, out_dir / f"{prefix}-{i}")
        except (requests.RequestException, ValueError, KeyError):
            continue
        if path:
            found.append({"type": "img", "path": path, "credit": credit})
    return found


def _with_photos(media, names, out_dir, want=3):
    """Top up cricket visuals with Commons photos of the named players/teams until there are `want` pictures."""
    have = [m for m in media if m["type"] == "img" and m.get("credit")]
    for n, name in enumerate(names):
        if len(have) >= want:
            break
        got = commons_photos(f"{name} cricket", out_dir, f"cp{n}")
        media, have = media + got, have + got
    print(f"   cricket visuals: {len(media)} items")
    return media
