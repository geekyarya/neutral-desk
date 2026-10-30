"""Neutral Desk - free AI news channel pipeline.

  python run.py script            fetch news, cross-check, write script  -> output/<date>/script.json
  (review / edit script.json)
  python run.py audio             AI voice for each segment
  python run.py video             voice (if needed) + anchor + graphics -> output/<date>/episode.mp4
  python run.py upload            upload to YouTube (private by default)
  python run.py all [--upload]    everything in one go
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
    out = render_episode(ep, cfg, d)
    meta = build_metadata(ep, cfg)
    (d / "youtube_title.txt").write_text(meta["title"], encoding="utf-8")
    (d / "youtube_description.txt").write_text(meta["description"], encoding="utf-8")
    print(f"\nVideo ready: {out}")
    return ep


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
    ap.add_argument("stage", choices=["script", "audio", "video", "upload", "all", "auth", "pack"])
    ap.add_argument("--date", help="episode date folder (default today)")
    ap.add_argument("--upload", action="store_true", help="with 'all': also upload")
    ap.add_argument("--config")
    a = ap.parse_args()
    cfg = load_config(a.config)
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
    elif a.stage == "upload":
        from newsdesk.upload import upload
        upload(load(d), cfg, d, interactive=sys.stdin.isatty())
    elif a.stage == "pack":
        stage_pack(cfg, d, load(d))
    elif a.stage == "all":
        ep = stage_script(cfg, d)
        ep = stage_video(cfg, d, ep)
        if a.upload:
            from newsdesk.upload import upload
            upload(ep, cfg, d, interactive=False)


if __name__ == "__main__":
    main()
