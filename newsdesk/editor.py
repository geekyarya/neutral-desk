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
from .persona import persona
from .strings import T, date_text
from .trends import reactions_text, reddit_reactions

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
- "script": what the TV anchor says, {words} words, written to be LISTENED to and to keep viewers watching:
  1) open with a hook: the single most striking confirmed fact, or a short question the story answers;
  2) what happened, in short spoken sentences (max ~15 words each), with concrete numbers, places and names;
  3) why it matters to ordinary people ("इसका असर..."), only as far as the reports support it;
  4) what happens next, if the reports say.
  Conversational and lively, like a good TV anchor talking to one viewer. Use only confirmed facts as statements.
  Mention disputed claims only with attribution ("According to Dawn, ..." / "This could not be independently
  confirmed"). No opinions, no sensational words (e.g. "shocking", "slams", "massive"), no speculation.
  Do not greet or sign off.
- "mood": "good" (achievements, relief, progress), "bad" (war, attacks, deaths, scams, failures, crises) or
  "neutral".
- "angry": true ONLY if the reports describe clear wrongdoing that would make ordinary viewers angry: corruption,
  scams, negligence that hurt people, broken promises, injustice, attacks on the country. false for ordinary
  politics and speeches, weather, disasters without negligence, science, sport, business and achievements.
- "tragedy": true if the story involves deaths, injuries, disasters, violence, crimes against people or children,
  or war casualties. Those are always told seriously: no jokes, no memes.
- "music": the background-music mood that fits this story: "tense" (corruption, scams, attacks, war, anger),
  "upbeat" (achievements, wins, good news), "chill" (ordinary politics, business, weather, science),
  "suspense" (unexplained or mysterious things), or "none" (any tragedy: silence is more respectful).
- "meme_line": ONLY if tragedy is false: a short, funny meme-style sticker line (max 6 words, written exactly as it
  appears in your script) in internet / Gen Z Hinglish, e.g. "सीन बन गया भाई!", "ये क्या हो रहा है भाई!", "L टेक है ये".
  Put that same line as its own sentence in the MIDDLE of "script". Use "" for tragedies.
- "image_queries": 2 or 3 short English photo-search phrases for this story (e.g. "Ramlila Maidan rally",
  "Arunachal Pradesh border", "GSLV rocket launch"). Places, events, objects; never private individuals.
- "why_it_matters": one line, max 15 words, the practical significance of the story, only as far as the reports
  support it. "" if unclear.
- "visuals": 2 to 4 English Wikipedia article titles that illustrate the story with photos: the specific
  places, institutions, landmarks, vehicles/objects or public figures involved (e.g. "Indian Space Research
  Organisation", "Sriharikota", "Joshimath"). Never private individuals, victims or children.
- "short_script": a {short_words}-word version of "script" for a 30-40 second vertical Short. Open with the single
  most important confirmed fact as a hook. Same rules: no opinions, attribute anything unconfirmed. No sign-off.

- "public_reaction": {reaction_rule}

{style}

LANGUAGE: write "headline", "fact", "claim", "script", "why_it_matters", "meme_line" and "public_reaction" in {language}
"visuals" stay in English (they are Wikipedia titles).
Outlet names in "outlets" and "reported_by" must be copied exactly (in English) from the brackets below.

REPORTS:
{reports}
{reactions}"""

REACTION_RULE = (
    "1-2 sentences (25-40 words) summarising the RANGE of opinions in the PUBLIC REACTION posts below, clearly "
    "framed as opinion (e.g. \"सोशल मीडिया पर लोगों की राय बंटी हुई है: कुछ का कहना है ..., जबकि कुछ ...\"). "
    "Never present an opinion as fact, no usernames, no insults or hateful generalisations about any group, and "
    "include opposing views if they exist. Use \"\" if the posts are off-topic or there are none.")
NO_REACTIONS = "Always \"\" (no public reaction available)."


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


def wrong_language(res, lang, keys=("headline", "script")):
    """True if Hindi output is mostly not in Devanagari (small models often slip into English)."""
    if lang != "hi":
        return False
    for key in keys:
        letters = [c for c in str(res.get(key) or "") if c.isalpha()]
        deva = sum("\u0900" <= c <= "\u097F" for c in letters)
        if letters and deva / len(letters) < 0.6:
            return True
    return False


def _all_text(res):
    parts = [res.get("headline", ""), res.get("script", ""), str(res.get("short_script") or ""),
             str(res.get("public_reaction") or ""), str(res.get("why_it_matters") or ""),
             str(res.get("meme_line") or "")]
    parts += [f.get("fact", "") for f in res.get("confirmed_facts") or []]
    parts += [d.get("claim", "") for d in res.get("disputed") or []]
    return " ".join(str(p) for p in parts)


def _clean(res, lang):
    bad = f"[^{ALLOWED.get(lang, ALLOWED['hi'])}]"
    fix = lambda t: re.sub(bad, "", t)
    res["headline"], res["script"] = fix(res["headline"]), fix(res["script"])
    res["short_script"] = fix(str(res.get("short_script") or ""))
    res["public_reaction"] = fix(str(res.get("public_reaction") or ""))
    res["why_it_matters"] = fix(str(res.get("why_it_matters") or ""))
    res["meme_line"] = fix(str(res.get("meme_line") or ""))
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


def _fix_spelling(res, fixes):
    def fix(text):
        for wrong, right in fixes.items():
            text = text.replace(wrong, right)
        return text
    for key in ("headline", "script", "short_script", "public_reaction", "why_it_matters", "meme_line"):
        if res.get(key):
            res[key] = fix(str(res[key]))
    for f in res.get("confirmed_facts") or []:
        f["fact"] = fix(f.get("fact", ""))
    for d in res.get("disputed") or []:
        d["claim"] = fix(d.get("claim", ""))
    return res


def _music_and_meme(res):
    """Pick the music mood (silence for tragedies) and keep the meme sticker line only where it is allowed."""
    from .sound import MUSIC_STYLES
    tragedy = bool(res.get("tragedy")) or (res.get("mood") == "bad" and not res.get("angry"))
    music = res.get("music") if res.get("music") in MUSIC_STYLES else None
    if music is None:  # LLM gave nothing usable: derive it from the mood
        music = ("tense" if res.get("angry") else "upbeat" if res.get("mood") == "good" else "chill")
    if tragedy:
        music = "none"
    meme = "" if tragedy else str(res.get("meme_line") or "").strip()
    script = str(res.get("script") or "")
    pos = script.find(meme) / max(len(script), 1) if meme and meme in script else 0.5
    if len(meme.split()) > 8:
        meme = ""
    return {"tragedy": tragedy, "music": music, "meme_line": meme, "meme_at": round(min(max(pos, 0.2), 0.8), 2)}


def _package(res, story, k, fixes=None):
    res = _fix_spelling(res, fixes or {})
    confirmed, disputed = _verify(res, story, k)
    reaction = str(res.get("public_reaction") or "").strip()
    return {"headline": res["headline"].strip(),
            "script": f"{res['script'].strip()} {reaction}".strip(),  # facts first, then labelled opinion
            "public_reaction": reaction,
            "short_script": str(res.get("short_script") or "").strip(),
            "why_it_matters": str(res.get("why_it_matters") or "").strip(),
            "mood": res.get("mood") if res.get("mood") in ("good", "bad", "neutral") else "neutral",
            "angry": bool(res.get("angry", False)),
            **_music_and_meme(res),
            "image_queries": [str(q) for q in (res.get("image_queries") or [])][:3],
            "visuals": [str(v) for v in (res.get("visuals") or [])][:4],
            "about_india": bool(res.get("about_india", True)),
            "confirmed_facts": confirmed, "disputed": disputed}


def _edit_with_llm(story, cfg):
    k = min(cfg["editor"]["confirm_threshold"], story["n_outlets"])
    reactions = story.get("reactions") or []
    prompt = PROMPT.format(n=len(story["articles"]), k=k, words="90 to 130", short_words="60 to 80",
                           style=persona(cfg)["style"],
                           language=T(cfg)["llm_language"], reports=_reports_text(story),
                           reaction_rule=REACTION_RULE if reactions else NO_REACTIONS,
                           reactions=("\nPUBLIC REACTION (Reddit posts and comments: opinions, NOT facts):\n"
                                      + reactions_text(reactions)) if reactions else "")
    lang = cfg["channel"]["language"]
    fixes = cfg["editor"].get("spelling_fixes") or {}
    last, messy = None, None
    for _ in range(2):
        try:
            res = complete_json(cfg, prompt)
        except Exception as e:
            last = e
            continue
        if not (res.get("script") and res.get("headline")):
            continue
        facts = " ".join(str(f.get("fact", "")) for f in res.get("confirmed_facts") or [])
        if wrong_language({**res, "facts": facts}, lang, ("headline", "script", "facts")):
            last = "answer was not in the episode's language"
            continue  # never fall back to a wrong-language answer
        stray = _stray(_all_text(res), lang)
        if not stray:
            return _package(res, story, k, fixes)
        messy, last = res, f"stray characters {''.join(sorted(set(stray)))}"  # ask again; usually clean
    if messy:  # still messy after the retry: strip the junk characters
        print(f"   ↳ removed {last}")
        return _package(_clean(messy, lang), story, k, fixes)
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
            if use_llm and cfg.get("trends", {}).get("reddit"):
                s["reactions"] = reddit_reactions(s, cfg["trends"]["reddit_subs"])
                print(f"   people's reaction: {len(s['reactions'])} Reddit threads")
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
            "reaction_links": [{"sub": t["sub"], "url": t["url"]} for t in s.get("reactions") or []]
                              if out.get("public_reaction") else [],
        })

    t, name = T(cfg), cfg["channel"].get("spoken_name") or cfg["channel"]["name"]
    n_outlets = len({src["outlet"] for seg in segments for src in seg["sources"]})
    lang, pz = cfg["channel"]["language"], persona(cfg)
    intro_t = pz.get("intro", {}).get(lang, t["intro"])
    outro_t = pz.get("outro", {}).get(lang, t["outro"])
    intro = {"id": "intro", "kind": "intro", "headline": t["top_stories"],
             "script": intro_t.format(name=name, date=date_text(cfg), n_outlets=n_outlets)}
    outro = {"id": "outro", "kind": "outro", "headline": t["how_title"],
             "script": outro_t.format(name=name, k=ed["confirm_threshold"])}
    return {"date": dt.date.today().isoformat(), "channel": cfg["channel"]["name"],
            "language": cfg["channel"]["language"], "segments": [intro, *segments, outro]}
