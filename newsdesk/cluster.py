"""Step 2: group articles that cover the same event, rank by breadth of independent coverage."""
import numpy as np
from sklearn.cluster import AgglomerativeClustering
from sklearn.feature_extraction.text import TfidfVectorizer

from .trends import google_stories, reddit_hot_titles, trend_hits, trending_terms

MERGE_SIMILARITY = 0.2  # same-event clusters measured ~0.33, unrelated ones < 0.08


def cluster_stories(articles, cfg):
    ed = cfg["editor"]
    if len(articles) < 2:
        return []
    texts = [f"{a['title']} {a['title']} {a['summary']}" for a in articles]
    X = TfidfVectorizer(stop_words="english", sublinear_tf=True, min_df=1, max_df=0.3,
                        ngram_range=(1, 2)).fit_transform(texts).toarray()
    labels = AgglomerativeClustering(n_clusters=None, metric="cosine", linkage="average",
                                     distance_threshold=ed["cluster_distance"]).fit_predict(X)

    # second pass: merge clusters that are the same event told differently (e.g. two crash-update clusters)
    ids = sorted(set(labels))
    cent = np.array([X[labels == l].mean(0) for l in ids])
    cent /= np.linalg.norm(cent, axis=1, keepdims=True) + 1e-9
    sim = cent @ cent.T
    parent = {l: l for l in ids}

    def root(l):
        while parent[l] != l:
            l = parent[l]
        return l

    for i, j in zip(*np.where(np.triu(sim, 1) > MERGE_SIMILARITY)):
        parent[root(ids[j])] = root(ids[i])

    groups = {}
    for a, lab in zip(articles, labels):
        groups.setdefault(root(lab), []).append(a)

    raw = [{"items": items, "prominence": 0.0} for items in groups.values()]
    tcfg = cfg.get("trends", {})
    if tcfg.get("google_news"):
        _merge_google(raw, google_stories(cfg), cfg)
    hot = reddit_hot_titles(tcfg.get("reddit_subs", [])) if tcfg.get("reddit") else []
    terms = trending_terms() if tcfg.get("google_trends") else []

    india, world = [], []
    for g in raw:
        items = g["items"]
        by_owner = {}
        for a in items:  # one article per media group = independent voices; feed articles (full text) first
            by_owner.setdefault(a["owner"], a)
        picked = list(by_owner.values())
        countries = {a["country"] for a in picked}
        n_india = sum(a["section"] == "india" for a in items)
        section = "india" if n_india * 2 >= len(items) else "world"
        if len(picked) < ed["min_outlets"]:
            continue
        if section == "world" and len(countries) < ed["world_min_countries"] and not g["prominence"]:
            continue
        story = {"articles": picked[: ed["max_articles_per_story"]], "section": section,
                 "n_outlets": len(picked), "n_articles": len(items), "countries": sorted(countries),
                 "foreign": any(a["country"] != "India" for a in picked), "prominence": g["prominence"]}
        (india if section == "india" else world).append(story)

    # trending first: independent coverage + article volume + Google News prominence
    # + match with today's top Google searches + buzz on Indian Reddit
    for s in india + world:
        s["trend_hits"] = trend_hits(s, terms)
        s["reddit_hits"] = _buzz(s, hot)
        s["hot_hits"] = _hot(s, ed.get("hot_topics") or [])
        s["score"] = (min(s["n_outlets"], 15) + 0.3 * (s["n_articles"] - s["n_outlets"]) + s["prominence"]
                      + 3 * min(s["trend_hits"], 2) + 1.5 * min(s["reddit_hits"], 2)
                      + ed.get("hot_weight", 0) * min(s["hot_hits"], 2))
    india.sort(key=lambda s: (s["score"], s["foreign"]), reverse=True)
    world.sort(key=lambda s: (s["score"], len(s["countries"])), reverse=True)
    india, world = _drop_repeats(india), _drop_repeats(world)
    # extra India candidates: the editor drops ones that turn out not to be about India
    return india[: ed["india_stories"] + 4], world[: ed["world_stories"] + 1]


def _drop_repeats(stories, threshold=0.3):
    """Two angles on the same event (e.g. 'rally on Nov 1' and 'demand to postpone the rally'): keep the top one."""
    if len(stories) < 2:
        return stories
    texts = [_story_text(s["articles"]) for s in stories]
    X = TfidfVectorizer(stop_words="english", sublinear_tf=True).fit_transform(texts)
    sim = (X @ X.T).toarray()
    kept = []
    for i in range(len(stories)):
        if all(sim[i, j] < threshold for j in kept):
            kept.append(i)
    return [stories[i] for i in kept]


def _hot(story, words):
    """How many 'hot' keywords (war, protest, controversy...) appear in the story's headlines."""
    import re
    text = " ".join(a["title"] for a in story["articles"][:15]).lower()
    return sum(bool(re.search(rf"\b{re.escape(w.lower())}", text)) for w in words)


def _story_text(items):
    return " ".join(a["title"] for a in items[:12])


def _merge_google(raw, gstories, cfg):
    """Fold Google News coverage into matching feed stories, or add it as a new story."""
    if not gstories:
        return
    texts = [_story_text(g["items"]) for g in raw] + [_story_text(g["articles"]) for g in gstories]
    X = TfidfVectorizer(stop_words="english", sublinear_tf=True).fit_transform(texts)
    feed_X, g_X = X[: len(raw)], X[len(raw):]
    sims = (g_X @ feed_X.T).toarray() if len(raw) else np.zeros((len(gstories), 0))
    for gi, g in enumerate(gstories):
        best = int(sims[gi].argmax()) if sims.shape[1] else -1
        if best >= 0 and sims[gi, best] > 0.25:
            raw[best]["items"] = raw[best]["items"] + g["articles"]  # feed articles stay first
            raw[best]["prominence"] = max(raw[best]["prominence"], g["prominence"])
        else:
            raw.append({"items": g["articles"], "prominence": g["prominence"]})


def _buzz(story, hot_titles):
    """How many of Indian Reddit's hot posts are about this story."""
    if not hot_titles:
        return 0
    titles = [a["title"] for a in story["articles"][:12]]
    X = TfidfVectorizer(stop_words="english").fit_transform(titles + hot_titles)
    sims = (X[len(titles):] @ X[: len(titles)].T).toarray()  # each hot post vs each headline
    return int((sims.max(axis=1) > 0.3).sum())
