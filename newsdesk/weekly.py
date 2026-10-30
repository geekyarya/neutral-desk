"""Sunday "week in review": the biggest stories of the last 7 days, reusing the daily scripts (no AI calls).

Daily scripts are kept as GitHub Actions artifacts named script-YYYY-MM-DD; locally, output/<date>/script.json.
"""
import datetime as dt
import io
import json
import os
import zipfile

import requests
from sklearn.cluster import AgglomerativeClustering
from sklearn.feature_extraction.text import TfidfVectorizer

from .config import ROOT
from .strings import T, date_text


def _from_github(day):
    repo, token = os.environ.get("GITHUB_REPOSITORY"), os.environ.get("GITHUB_TOKEN")
    if not (repo and token):
        return None
    h = {"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json"}
    r = requests.get(f"https://api.github.com/repos/{repo}/actions/artifacts",
                     params={"name": f"script-{day}", "per_page": 1}, headers=h, timeout=30)
    arts = r.json().get("artifacts") if r.ok else None
    if not arts:
        return None
    z = requests.get(arts[0]["archive_download_url"], headers=h, timeout=60)
    if not z.ok:
        return None
    with zipfile.ZipFile(io.BytesIO(z.content)) as zf:
        name = next(n for n in zf.namelist() if n.endswith("script.json"))
        return json.loads(zf.read(name))


def _load_day(day):
    local = ROOT / "output" / day / "script.json"
    if local.exists():
        return json.loads(local.read_text(encoding="utf-8"))
    return _from_github(day)


def collect_week(end=None):
    end = end or dt.date.today()
    days = [(end - dt.timedelta(days=i)).isoformat() for i in range(6, -1, -1)]
    stories = []
    for day in days:
        ep = _load_day(day)
        print(f"  {day}: {'found' if ep else 'missing'}")
        for seg in (ep or {}).get("segments", []):
            if seg["kind"] == "story":
                stories.append({**seg, "date": day})
    return stories, days[0], days[-1]


def _dedupe(stories):
    """The same event often runs for several days: keep its best-covered, latest version."""
    if len(stories) < 2:
        return stories
    # cluster on the English source headlines (Hindi script text tokenises poorly)
    texts = [" ".join(src["title"] for src in s["sources"]) for s in stories]
    X = TfidfVectorizer(stop_words="english", sublinear_tf=True).fit_transform(texts).toarray()
    labels = AgglomerativeClustering(n_clusters=None, metric="cosine", linkage="average",
                                     distance_threshold=0.75).fit_predict(X)
    best = {}
    for s, lab in zip(stories, labels):
        b = best.get(lab)
        if b is None or (s["n_outlets"], s["date"]) > (b["n_outlets"], b["date"]):
            best[lab] = s
    return list(best.values())


def build_weekly(cfg, end=None):
    t = T(cfg)
    stories, start, stop = collect_week(end)
    if not stories:
        raise SystemExit("No daily scripts found for the last 7 days.")
    picked = sorted(_dedupe(stories), key=lambda s: s["n_outlets"], reverse=True)[: cfg["weekly"]["max_stories"]]
    picked.sort(key=lambda s: s["date"])  # tell the week in order

    segments = []
    for i, s in enumerate(picked, 1):
        d = dt.date.fromisoformat(s["date"])
        seg = {k: v for k, v in s.items() if k not in ("audio", "duration", "short", "date")}
        seg["id"] = f"story{i:02d}"
        seg["date_label"] = f"{t['weekdays'][d.weekday()]}, {date_text(cfg, d)}"
        segments.append(seg)

    name = cfg["channel"].get("spoken_name") or cfg["channel"]["name"]
    s_txt = date_text(cfg, dt.date.fromisoformat(start))
    e_txt = date_text(cfg, dt.date.fromisoformat(stop))
    intro = {"id": "intro", "kind": "intro", "headline": t["weekly_title"],
             "script": t["weekly_intro"].format(name=name, start=s_txt, end=e_txt)}
    outro = {"id": "outro", "kind": "outro", "headline": t["how_title"],
             "script": t["weekly_outro"].format(name=name, k=cfg["editor"]["confirm_threshold"])}
    print(f"Week {start} – {stop}: {len(stories)} stories, {len(picked)} after merging repeats")
    return {"date": stop, "week_start": start, "weekly": True, "channel": cfg["channel"]["name"],
            "language": cfg["channel"]["language"], "segments": [intro, *segments, outro]}
