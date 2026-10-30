"""Step 3+4: cross-check each story across outlets and write a neutral anchor script.

Rule of the channel: a fact is spoken as fact only if >= confirm_threshold
independent media groups report it. Everything else is attributed
("according to X") or labelled as not independently confirmed.
"""
import datetime as dt
import re
from concurrent.futures import ThreadPoolExecutor

from .fetch import fetch_full_text
from .llm import complete_json
from .strings import T, date_text

PROMPT = """You are the editor of a strictly neutral news channel. Below are {n} reports of the SAME event
from different, independently owned outlets. Outlets may be biased; your job is to separate fact from spin.

Return JSON with exactly these keys:
- "about_india": true if the event happened in India or directly involves India / Indians / the Indian
  government; false otherwise.
- "headline": neutral headline, max 70 characters, no adjectives, no clickbait.
- "confirmed_facts": list of objects {{"fact": str, "outlets": [outlet names]}}. Include a fact ONLY if at least
  {k} different outlets below state it. Plain, neutral wording, max 20 words each. Max 4 facts, most important first.
- "disputed": list of objects {{"claim": str, "reported_by": [outlet names]}} for important claims that only
  one or two outlets make, or where outlets contradict each other. Max 20 words each. Max 3.
- "script": what the TV anchor says, {words} words. Use only confirmed facts as statements.
  Mention disputed claims only with attribution ("According to Dawn, ..." / "This could not be independently
  confirmed"). No opinions, no emotional words (e.g. "shocking", "slams", "massive"), no speculation.
  Do not greet or sign off.

LANGUAGE: write "headline", "fact", "claim" and "script" in {language}
Outlet names in "outlets" and "reported_by" must be copied exactly (in English) from the brackets below.

REPORTS:
{reports}
"""


def _reports_text(story):
    parts = []
    for a in story["articles"]:
        text = a.get("text") or ""
        body = text if len(text) > 300 else a["summary"]  # paywalled/blocked pages give junk
        parts.append(f"[{a['outlet']}] ({a['country']}) {a['title']}\n{body}")
    return "\n\n".join(parts)


# characters allowed in LLM text: Latin/punctuation/₹ for every language, plus Devanagari for Hindi
ALLOWED = {"en": r"\u0000-\u024F\u2000-\u206F\u20B9", "hi": r"\u0000-\u024F\u2000-\u206F\u20B9\u0900-\u097F"}


def _stray(text, lang):
    """Characters from unexpected scripts, e.g. Japanese kana that an LLM slipped into a Hindi word."""
    return re.findall(f"[^{ALLOWED.get(lang, ALLOWED['hi'])}]", text)


def _all_text(res):
    parts = [res.get("headline", ""), res.get("script", "")]
    parts += [f.get("fact", "") for f in res.get("confirmed_facts") or []]
    parts += [d.get("claim", "") for d in res.get("disputed") or []]
    return " ".join(str(p) for p in parts)


def _clean(res, lang):
    bad = f"[^{ALLOWED.get(lang, ALLOWED['hi'])}]"
    fix = lambda t: re.sub(bad, "", t)
    res["headline"], res["script"] = fix(res["headline"]), fix(res["script"])
    for f in res.get("confirmed_facts") or []:
        f["fact"] = fix(f.get("fact", ""))
    for d in res.get("disputed") or []:
        d["claim"] = fix(d.get("claim", ""))
    return res


def _verify(result, story, k):
    """Don't trust the LLM blindly: re-check that each 'confirmed' fact cites >= k real outlets."""
    real = {a["outlet"] for a in story["articles"]}
    confirmed, disputed = [], list(result.get("disputed") or [])
    for f in result.get("confirmed_facts") or []:
        outlets = sorted(set(f.get("outlets") or []) & real)
        if len(outlets) >= k:
            confirmed.append({"fact": f["fact"], "outlets": outlets})
        elif outlets:
            disputed.append({"claim": f["fact"], "reported_by": outlets})
    disputed = [{"claim": d["claim"], "reported_by": sorted(set(d.get("reported_by") or []) & real)}
                for d in disputed if d.get("claim")]
    return confirmed, disputed[:3]


def _package(res, story, k):
    confirmed, disputed = _verify(res, story, k)
    return {"headline": res["headline"].strip(), "script": res["script"].strip(),
            "about_india": bool(res.get("about_india", True)),
            "confirmed_facts": confirmed, "disputed": disputed}


def _edit_with_llm(story, cfg):
    k = min(cfg["editor"]["confirm_threshold"], story["n_outlets"])
    prompt = PROMPT.format(n=len(story["articles"]), k=k, words="90 to 130",
                           language=T(cfg)["llm_language"], reports=_reports_text(story))
    lang = cfg["channel"]["language"]
    last, messy = None, None
    for _ in range(2):
        try:
            res = complete_json(cfg, prompt)
        except Exception as e:
            last = e
            continue
        if not (res.get("script") and res.get("headline")):
            continue
        stray = _stray(_all_text(res), lang)
        if not stray:
            return _package(res, story, k)
        messy, last = res, f"stray characters {''.join(sorted(set(stray)))}"  # ask again; usually clean
    if messy:  # still messy after the retry: strip the junk characters
        print(f"   ↳ removed {last}")
        return _package(_clean(messy, lang), story, k)
    raise RuntimeError(f"LLM failed for story '{story['articles'][0]['title']}': {last}")


def _edit_without_llm(story):
    """No-AI fallback (English only): read out what each outlet reports, always attributed."""
    arts = story["articles"]
    lead = arts[0]
    lines = [f"{lead['title']}. This story was reported by {story['n_outlets']} independent outlets."]
    for a in arts[:3]:
        if a["summary"]:
            first = a["summary"].split(". ")[0].rstrip(".")
            lines.append(f"According to {a['outlet']}, {first[0].lower() + first[1:]}.")
    return {"headline": lead["title"][:90], "script": " ".join(lines), "about_india": True,
            "confirmed_facts": [],
            "disputed": [{"claim": a["title"], "reported_by": [a["outlet"]]} for a in arts[1:3]]}


def build_episode(candidates, cfg):
    india_c, world_c = candidates
    ed = cfg["editor"]
    use_llm = cfg["llm"]["provider"] != "none"
    if not use_llm and cfg["channel"]["language"] != "en":
        raise SystemExit("A non-English episode needs an LLM: set llm.provider to ollama or gemini.")

    if ed["fetch_full_text"] and use_llm:
        jobs = [a for s in india_c + world_c for a in s["articles"]]
        print(f"Fetching full text for {len(jobs)} articles...")
        with ThreadPoolExecutor(max_workers=8) as pool:
            for a, text in zip(jobs, pool.map(lambda a: fetch_full_text(a["url"]), jobs)):
                a["text"] = text

    picked = []
    for pool_, want in ((india_c, ed["india_stories"]), (world_c, ed["world_stories"])):
        got = 0
        for s in pool_:
            if got >= want:
                break
            print(f"Editing [{s['section']}]: {s['articles'][0]['title'][:70]}")
            try:
                out = _edit_with_llm(s, cfg) if use_llm else _edit_without_llm(s)
            except RuntimeError as e:  # one failed story shouldn't kill the whole episode
                print(f"   ↳ skipped: {e}")
                continue
            if s["section"] == "india" and not out.pop("about_india"):
                print("   ↳ skipped: not about India")
                continue
            out.pop("about_india", None)
            picked.append((s, out))
            got += 1

    if not picked:
        raise SystemExit("No story could be written (LLM unavailable). Try again later.")
    segments = []
    for i, (s, out) in enumerate(picked, 1):
        segments.append({
            "id": f"story{i:02d}", "kind": "story", "section": s["section"], **out,
            "n_outlets": s["n_outlets"], "countries": s["countries"], "foreign": s["foreign"],
            "sources": [{"outlet": a["outlet"], "owner": a["owner"], "country": a["country"],
                         "title": a["title"], "url": a["url"]} for a in s["articles"]],
        })

    t, name = T(cfg), cfg["channel"].get("spoken_name") or cfg["channel"]["name"]
    n_outlets = len({src["outlet"] for seg in segments for src in seg["sources"]})
    intro = {"id": "intro", "kind": "intro", "headline": t["top_stories"],
             "script": t["intro"].format(name=name, date=date_text(cfg), n_outlets=n_outlets)}
    outro = {"id": "outro", "kind": "outro", "headline": t["how_title"],
             "script": t["outro"].format(name=name, k=ed["confirm_threshold"])}
    return {"date": dt.date.today().isoformat(), "channel": cfg["channel"]["name"],
            "language": cfg["channel"]["language"], "segments": [intro, *segments, outro]}
