"""What's trending (Google Trends India) and what people are saying (Reddit, public RSS, no account needed)."""
import html
import re
import time

import feedparser
import requests

UA = {"User-Agent": "ZeroMasalaBot/1.0 (news research; https://geekyarya.github.io/neutral-desk/)"}
STOP = set("""a an the of in on at to for from with by and or is are was were be been has have had will would after
before over under into about as amid says said new news latest live updates update india indian""".split())


def trending_terms(geo="IN"):
    """Today's top Google searches, e.g. ['india china border', 'janhvi kapoor', ...]."""
    try:
        r = requests.get("https://trends.google.com/trending/rss", params={"geo": geo}, headers=UA, timeout=20)
        return [e.title.lower() for e in feedparser.parse(r.content).entries]
    except requests.RequestException:
        return []


def trend_hits(story, terms):
    """How many trending searches this story matches (all words of the search appear in its headlines)."""
    text = " ".join(f"{a['title']} {a['summary']}" for a in story["articles"]).lower()
    hits = 0
    for term in terms:
        words = [w for w in re.findall(r"\w+", term) if w not in STOP and len(w) > 2]
        if words and all(re.search(rf"\b{re.escape(w)}", text) for w in words):
            hits += 1
    return hits


def _keywords(title, n=4):
    """A short Reddit search query from an English headline: names and long words first."""
    words = [w for w in re.findall(r"[A-Za-z][A-Za-z'-]+", title) if w.lower() not in STOP]
    words.sort(key=lambda w: (not w[0].isupper(), -len(w)))
    return " ".join(dict.fromkeys(words[:n]))


def _clean(text):
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", html.unescape(text or ""))).strip()


def story_keywords(story, n=4):
    """The words most of the story's headlines share, names first (e.g. 'Arunachal China border')."""
    counts = {}
    for a in story["articles"][:15]:
        words = {re.sub(r"'s$", "", w) for w in re.findall(r"[A-Za-z][A-Za-z'-]+", a["title"])}
        for w in words:
            if w.lower() not in STOP and len(w) > 2:
                key = w.lower()
                cap, c = counts.get(key, (w, 0))
                counts[key] = (w if w[0].isupper() else cap, c + 1)
    ranked = sorted(counts.values(), key=lambda wc: (-wc[1], not wc[0][0].isupper(), -len(wc[0])))
    return [w for w, c in ranked[:n]]


def _reddit_search(subs, query):
    try:
        r = requests.get(f"https://www.reddit.com/r/{'+'.join(subs)}/search.rss", headers=UA, timeout=20,
                         params={"q": query, "restrict_sr": "on", "sort": "relevance", "t": "week"})
        return feedparser.parse(r.content).entries if r.ok else []
    except requests.RequestException:
        return []


def reddit_reactions(story, subs, max_threads=3, max_comments=6):
    """Top posts about this story across a balanced set of subreddits, with their top comments."""
    words = story_keywords(story)
    posts = []
    for n in (4, 3, 2):  # broaden the search until something comes back
        if len(words) >= n:
            posts = _reddit_search(subs, " ".join(words[:n]))
            if posts:
                break
            time.sleep(1)
    threads, seen_subs = [], set()
    for p in posts:
        sub = (p.get("tags") or [{}])[0].get("term", "")
        if sub in seen_subs:  # one thread per community keeps the mix balanced
            continue
        time.sleep(2)  # be polite to Reddit
        try:
            c = requests.get(p.link.rstrip("/") + "/.rss", params={"sort": "top", "limit": 15}, headers=UA,
                             timeout=20)
        except requests.RequestException:
            continue
        comments = []
        for e in feedparser.parse(c.content).entries[1:]:  # entry 0 is the post itself
            author = (e.get("author") or "").lower()
            text = re.sub(r"https?://\S+", "", _clean((e.get("content") or [{}])[0].get("value", ""))).strip()
            if "automoderator" in author or len(text) < 25 or text.startswith(("[deleted]", "[removed]")):
                continue
            comments.append(text[:220])
            if len(comments) >= max_comments:
                break
        if comments:
            threads.append({"sub": f"r/{sub}", "title": _clean(p.title), "url": p.link, "comments": comments})
            seen_subs.add(sub)
        if len(threads) >= max_threads:
            break
    return threads


def reactions_text(threads):
    parts = []
    for t in threads:
        parts.append(f"{t['sub']} thread: {t['title']}\n" + "\n".join(f"- {c}" for c in t["comments"]))
    return "\n\n".join(parts)


# ---------------- trending stories from Google News + Reddit buzz ----------------

GN = "https://news.google.com/rss"
GN_PARAMS = {"hl": "en-IN", "gl": "IN", "ceid": "IN:en"}


def _gn(path="", **params):
    try:
        r = requests.get(GN + path, params={**GN_PARAMS, **params}, headers=UA, timeout=20)
        return feedparser.parse(r.content).entries if r.ok else []
    except requests.RequestException:
        return []


def owner_of(outlet, cfg):
    """Media group behind an outlet name, so outlets with the same owner count once."""
    low = outlet.lower()
    for alias, owner in (cfg.get("trends", {}).get("owner_aliases") or {}).items():
        if alias.lower() in low:
            return owner
    for f in cfg["feeds"]:
        if f["name"].lower() == low:
            return f.get("owner", f["name"])
    return outlet


def google_stories(cfg, top_n=12):
    """Today's most prominent stories on Google News India, each expanded with coverage from many outlets."""
    sections = [("india", "/headlines/section/topic/NATION"), ("world", "/headlines/section/topic/WORLD"),
                ("india", "")]
    heads, seen = [], set()

    def add(section, prominence, head):
        q = _keywords(head, 4)
        if q and q.lower() not in seen:
            seen.add(q.lower())
            heads.append((section, prominence, head, q))

    tcfg = cfg.get("trends", {})
    for topic in tcfg.get("watch_topics") or []:  # topics you always want checked
        add("india", 2, topic)
    for section, path in sections:  # what Google News ranks highest right now
        for rank, e in enumerate(_gn(path)[:top_n]):
            add(section, 3 if rank < 5 else 1.5, e.title.rsplit(" - ", 1)[0])
    if tcfg.get("reddit"):  # what Indians are discussing today; needs real coverage to survive
        for title in reddit_titles(tcfg.get("reddit_subs", []), "top", t="day")[:15]:
            add("india", 2, title)
    stories = []
    for section, prominence, head, q in heads:
        time.sleep(1)
        entries = _gn("/search", q=f"{q} when:2d")
        arts = []
        for e in entries[:30]:
            outlet = (e.get("source") or {}).get("title") or e.title.rsplit(" - ", 1)[-1]
            arts.append({"outlet": outlet, "owner": owner_of(outlet, cfg), "country": "India", "section": section,
                         "title": e.title.rsplit(" - ", 1)[0], "summary": "", "url": e.link,
                         "published": e.get("published")})
        if arts:
            stories.append({"head": head, "section": section, "prominence": prominence, "articles": arts})
    return stories


def reddit_titles(subs, listing="hot", **params):
    try:
        r = requests.get(f"https://www.reddit.com/r/{'+'.join(subs)}/{listing}.rss",
                         params={"limit": 50, **params}, headers=UA, timeout=20)
        return [_clean(e.title) for e in feedparser.parse(r.content).entries] if r.ok else []
    except requests.RequestException:
        return []


def reddit_hot_titles(subs):
    return reddit_titles(subs, "hot")
