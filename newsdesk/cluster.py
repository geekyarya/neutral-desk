"""Step 2: group articles that cover the same event, rank by breadth of independent coverage."""
import numpy as np
from sklearn.cluster import AgglomerativeClustering
from sklearn.feature_extraction.text import TfidfVectorizer

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

    india, world = [], []
    for items in groups.values():
        by_owner = {}
        for a in items:                       # one article per media group = independent voices
            by_owner.setdefault(a["owner"], a)
        picked = list(by_owner.values())
        countries = {a["country"] for a in picked}
        n_india = sum(a["section"] == "india" for a in items)
        section = "india" if n_india * 2 >= len(items) else "world"
        if len(picked) < ed["min_outlets"]:
            continue
        if section == "world" and len(countries) < ed["world_min_countries"]:
            continue
        story = {"articles": picked[: ed["max_articles_per_story"]], "section": section,
                 "n_outlets": len(picked), "countries": sorted(countries),
                 "foreign": any(a["country"] != "India" for a in picked)}
        (india if section == "india" else world).append(story)

    india.sort(key=lambda s: (s["n_outlets"], s["foreign"]), reverse=True)
    world.sort(key=lambda s: (len(s["countries"]), s["n_outlets"]), reverse=True)
    # extra India candidates: the editor drops ones that turn out not to be about India
    return india[: ed["india_stories"] + 4], world[: ed["world_stories"] + 1]
