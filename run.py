"""Neutral Desk - free AI news channel pipeline.

  python run.py script            fetch news, cross-check, write script  -> output/<date>/script.json
  (review / edit script.json)
  python run.py audio             AI voice for each segment
  python run.py video             voice (if needed) + anchor + graphics -> output/<date>/episode.mp4
  python run.py shorts            vertical Shorts, one per story      -> output/<date>/shorts/
  python run.py upload            upload bulletin + Shorts to YouTube
  python run.py all [--upload]    script + video + shorts in one go
  python run.py weekly            Sunday week-in-review from the last 7 days' scripts -> output/week-<date>/
  python run.py reel [--slot N]   one 20-30 s Instagram Reel for the current (or given) slot -> output/reels/<id>/
  python run.py reel-publish --video-url URL [--reel ID] [--to facebook]   post that Reel (Instagram default)
  python run.py auth              one-time YouTube login
  python run.py pack              zip face + voice files for colab/lipsync.ipynb (realistic anchor)
"""
import argparse
import json
import sys

from newsdesk.config import episode_dir, load_config


def save(ep, d):
    (d / "script.json").write_text(json.dumps(ep, indent=2, ensure_ascii=False), encoding="utf-8")


def load(d):
    p = d / "script.json"
    if not p.exists():
        sys.exit(f"No {p}. Run: python run.py script")
    return json.loads(p.read_text(encoding="utf-8"))


def stage_script(cfg, d):
    from newsdesk.cluster import cluster_stories
    from newsdesk.editor import build_episode
    from newsdesk.fetch import fetch_all

    print("1/3 Fetching news...")
    articles = fetch_all(cfg)
    (d / "articles.json").write_text(json.dumps(articles, indent=1, ensure_ascii=False), encoding="utf-8")
    print(f"    {len(articles)} articles")
    print("2/3 Grouping into stories...")
    india, world = cluster_stories(articles, cfg)
    if not india and not world:
        sys.exit("No story met the coverage rules. Lower editor.min_outlets or raise hours_back.")
    for s in india + world:
        print(f"    [{s['section']}, {s['n_outlets']} groups] {s['articles'][0]['title'][:80]}")
    print(f"3/3 Cross-checking with LLM ({cfg['llm']['provider']})...")
    ep = build_episode((india, world), cfg)
    save(ep, d)
    print(f"\nScript ready: {d / 'script.json'}\nReview/edit it, then: python run.py video")
    return ep


def stage_audio(cfg, d, ep):
    from newsdesk.tts import synthesize_episode
    print("Generating voice...")
    ep = synthesize_episode(ep, cfg, d)
    save(ep, d)
    return ep


def stage_video(cfg, d, ep):
    from newsdesk.render import render_episode
    from newsdesk.upload import build_metadata
    if any("duration" not in s for s in ep["segments"]):
        ep = stage_audio(cfg, d, ep)
    if cfg.get("video", {}).get("photos", True):
        from newsdesk.media import add_story_images
        print("Finding free photos for each story...")
        ep = add_story_images(ep, d)
        save(ep, d)
    out = render_episode(ep, cfg, d)
    meta = build_metadata(ep, cfg)
    (d / "youtube_title.txt").write_text(meta["title"], encoding="utf-8")
    (d / "youtube_description.txt").write_text(meta["description"], encoding="utf-8")
    print(f"\nVideo ready: {out}")
    return ep


def stage_shorts(cfg, d, ep):
    from newsdesk.shorts import render_shorts
    print("Making Shorts...")
    ep = render_shorts(ep, cfg, d)
    save(ep, d)
    return ep


def stage_weekly(cfg, a):
    import datetime as dt
    from newsdesk.weekly import build_weekly
    end = dt.date.fromisoformat(a.date) if a.date else None
    ep = build_weekly(cfg, end)
    d = episode_dir(f"week-{ep['date']}")
    save(ep, d)
    return stage_video(cfg, d, ep)


def stage_reel(cfg, a):
    import os
    from newsdesk.config import ROOT
    from newsdesk.reel_render import render_reel
    from newsdesk.reels import (caption_text, ist_now, make_reel_content, pick_slot, reel_already_posted,
                                used_urls_from_github)
    slot = pick_slot(cfg, a.slot)
    slot_no = cfg["reels"]["slots"].index(slot)
    reel_id = ist_now().strftime("%Y-%m-%d-") + f"{slot['hour']:02d}"
    d = ROOT / "output" / "reels" / reel_id
    d.mkdir(parents=True, exist_ok=True)
    print(f"Reel {reel_id}: {slot['type']}")
    if os.environ.get("SKIP_IF_DONE") == "true" and reel_already_posted(reel_id):
        print("This slot was already posted today; skipping.")
        return
    used = used_urls_from_github()
    for m in (ROOT / "output" / "reels").glob("*/meta.json"):  # local runs
        used |= set(json.loads(m.read_text(encoding="utf-8")).get("urls", []))
    content = make_reel_content(cfg, slot_no, d, used)
    print(f"   {content['type']}: {content['title']}")
    render_reel(content, cfg, d)
    (d / "meta.json").write_text(json.dumps(content, indent=2, ensure_ascii=False), encoding="utf-8")
    (d / "caption.txt").write_text(caption_text(content, cfg), encoding="utf-8")
    if os.environ.get("GITHUB_ENV"):
        with open(os.environ["GITHUB_ENV"], "a") as env:
            env.write(f"REEL_ID={reel_id}\n")
    print(f"Reel ready: {d / 'reel.mp4'}")


def stage_reel_publish(cfg, a):
    from newsdesk.config import ROOT
    d = ROOT / "output" / "reels" / a.reel
    caption = (d / "caption.txt").read_text(encoding="utf-8")
    if a.to == "facebook":
        from newsdesk.facebook import publish_fb_reel
        publish_fb_reel(a.video_url, caption, cfg)
    else:
        from newsdesk.instagram import publish_reel
        publish_reel(a.video_url, caption, cfg)


def stage_pack(cfg, d, ep):
    import zipfile
    from newsdesk.config import ROOT
    if any("duration" not in s for s in ep["segments"]):
        ep = stage_audio(cfg, d, ep)
    face = ROOT / cfg["anchor"]["face_image"]
    if not face.exists():
        sys.exit(f"Put your anchor face image at {face}")
    out = d / "lipsync_input.zip"
    with zipfile.ZipFile(out, "w") as z:
        z.write(face, "face" + face.suffix)
        for s in ep["segments"]:
            z.write(d / s["audio"], f"audio/{s['id']}.wav")
    print(f"Upload {out} to colab/lipsync.ipynb, then unzip the result into {d / 'anchor'}/ "
          f"and run: python run.py video --date {d.name}")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("stage", choices=["script", "audio", "video", "shorts", "upload", "all", "auth", "pack", "weekly",
                                       "reel", "reel-publish"])
    ap.add_argument("--date", help="episode date folder (default today)")
    ap.add_argument("--upload", action="store_true", help="with 'all': also upload")
    ap.add_argument("--config")
    ap.add_argument("--slot", type=int, help="reel: slot number from config (default: nearest to now)")
    ap.add_argument("--reel", help="reel-publish: reel id (output/reels/<id>)")
    ap.add_argument("--video-url", help="reel-publish: public URL of the reel video")
    ap.add_argument("--to", choices=["instagram", "facebook"], default="instagram", help="reel-publish: where")
    a = ap.parse_args()
    cfg = load_config(a.config)
    if a.stage == "weekly":
        return stage_weekly(cfg, a)
    if a.stage == "reel":
        return stage_reel(cfg, a)
    if a.stage == "reel-publish":
        return stage_reel_publish(cfg, a)
    d = episode_dir(a.date)

    if a.stage == "auth":
        from newsdesk.upload import credentials
        credentials()
        print("YouTube login saved to token.json")
    elif a.stage == "script":
        stage_script(cfg, d)
    elif a.stage == "audio":
        stage_audio(cfg, d, load(d))
    elif a.stage == "video":
        stage_video(cfg, d, load(d))
    elif a.stage == "shorts":
        stage_shorts(cfg, d, load(d))
    elif a.stage == "upload":
        from newsdesk.upload import upload
        save(upload(load(d), cfg, d, interactive=sys.stdin.isatty()), d)
    elif a.stage == "pack":
        stage_pack(cfg, d, load(d))
    elif a.stage == "all":
        ep = stage_script(cfg, d)
        ep = stage_video(cfg, d, ep)
        if cfg.get("shorts", {}).get("count", 0):
            ep = stage_shorts(cfg, d, ep)
        if a.upload:
            from newsdesk.upload import upload
            save(upload(ep, cfg, d, interactive=False), d)


if __name__ == "__main__":
    main()
