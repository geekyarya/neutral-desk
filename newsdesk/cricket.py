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
    return news, stats


def cricket_news(cfg, used_urls, out_dir):
    from .reels import _finish, _lang, _media_for
    q = cfg["reels"].get("cricket_query", "cricket India when:2d")
    items = []
    try:
        r = requests.get("https://news.google.com/rss/search", timeout=30,
                         params={"q": q, "hl": "en-IN", "gl": "IN", "ceid": "IN:en"})
        for e in feedparser.parse(r.content).entries[:25]:
            src = (e.get("source") or {}).get("title") or e.title.rsplit(" - ", 1)[-1]
            items.append((e.title.rsplit(" - ", 1)[0], src, e.link))
    except requests.RequestException as e:
        print(f"   cricket news error: {e}")
    for name, url in FEEDS:
        try:
            for e in feedparser.parse(requests.get(url, headers=UA, timeout=30).content).entries[:10]:
                items.append((e.title, name, e.link))
        except requests.RequestException:
            pass
    items = [i for i in items if i[2] not in used_urls]
    if not items:
        return None
    text = "\n".join(f"[{n}] ({src}) {title}" for n, (title, src, _) in enumerate(items))
    res = complete_json(cfg, _prompts()[0].format(items=text, style=persona(cfg)["style"], **_lang(cfg)))
    idx = [i for i in (res.get("index") or []) if isinstance(i, int) and 0 <= i < len(items)]
    if not idx:
        return None
    res = _finish(res, cfg)
    if not res["script"]:
        return None
    res.update(_music_and_meme(res))
    if res.get("music") in (None, "", "chill"):
        res["music"] = "none" if res.get("tragedy") else "upbeat"
    chosen = [items[i] for i in idx]
    res.update(type="cricket", urls=[c[2] for c in chosen], sources=list(dict.fromkeys(c[1] for c in chosen)),
               image=None, credit=None, chip=None, media=_media_for(res, out_dir, "cricket"))
    return res


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
    lines = []
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
    if not lines:
        return None
    date = re.sub(r"\{\{[^}]*\}\}|<[^>]+>", "", f.get("date", "")).strip() or "recently"
    return {"name": name, "date": date, "lines": lines}


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
                                                     style=persona(cfg)["style"], **_lang(cfg)))
        res = _finish(res, cfg)
        if not res["script"]:
            continue
        res.update(_music_and_meme(res))
        res.update(music="upbeat", tragedy=False, angry=False)
        res["visuals"] = [sa["name"], sb["name"]]
        res.update(type="cricket", sources=["Wikipedia (player statistics)"], image=None, credit=None, chip=None,
                   urls=["https://en.wikipedia.org/wiki/" + s["name"].replace(" ", "_") for s in (sa, sb)],
                   media=_media_for(res, out_dir, "cricket"))
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
