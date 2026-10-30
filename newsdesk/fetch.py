"""Step 1: collect articles from RSS feeds."""
import calendar
import datetime as dt
import html
import re
from concurrent.futures import ThreadPoolExecutor

import feedparser
import requests

UA = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) NeutralDesk/1.0"}


def _clean(text):
    text = re.sub(r"<[^>]+>", " ", text or "")
    return re.sub(r"\s+", " ", html.unescape(text)).strip()


def _fetch_feed(feed, cutoff):
    try:
        r = requests.get(feed["url"], headers=UA, timeout=20)
        r.raise_for_status()
    except Exception as e:
        print(f"  ! {feed['name']}: {e}")
        return []
    parsed = feedparser.parse(r.content)
    out = []
    for e in parsed.entries:
        t = e.get("published_parsed") or e.get("updated_parsed")
        published = dt.datetime.fromtimestamp(calendar.timegm(t), dt.timezone.utc) if t else None
        if published and published < cutoff:
            continue
        title = _clean(e.get("title"))
        if not title or not e.get("link"):
            continue
        out.append({
            "outlet": feed["name"],
            "owner": feed.get("owner", feed["name"]),
            "country": feed["country"],
            "section": feed.get("section", "world"),
            "title": title,
            "summary": _clean(e.get("summary"))[:600],
            "url": e.get("link"),
            "published": published.isoformat() if published else None,
        })
    print(f"  {feed['name']:<18} {len(out):>3} articles")
    return out


def fetch_all(cfg):
    cutoff = dt.datetime.now(dt.timezone.utc) - dt.timedelta(hours=cfg["editor"]["hours_back"])
    with ThreadPoolExecutor(max_workers=10) as pool:
        results = pool.map(lambda f: _fetch_feed(f, cutoff), cfg["feeds"])
    seen, articles = set(), []
    for batch in results:
        for a in batch:
            if a["url"] not in seen:
                seen.add(a["url"])
                articles.append(a)
    return articles


def fetch_full_text(url, limit=2500):
    """Best-effort article body extraction. Falls back to '' on paywalls/blocks."""
    import trafilatura
    try:
        r = requests.get(url, headers=UA, timeout=20)
        text = trafilatura.extract(r.text, include_comments=False, include_tables=False) or ""
    except Exception:
        return ""
    return re.sub(r"\s+", " ", text)[:limit]
