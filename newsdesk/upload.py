"""Step 8: upload to YouTube with the free YouTube Data API."""
import datetime as dt
import os
from pathlib import Path

from .config import ROOT
from .strings import T, date_text

SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]
SECRET = ROOT / "client_secret.json"
TOKEN = ROOT / "token.json"


def credentials(interactive=True):
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow

    creds = Credentials.from_authorized_user_file(str(TOKEN), SCOPES) if TOKEN.exists() else None
    if creds and not creds.valid and creds.refresh_token:  # also covers a token.json with only a refresh token
        creds.refresh(Request())
    if not creds or not creds.valid:
        if not interactive:
            raise RuntimeError("No valid token.json. Run: python run.py auth")
        if not SECRET.exists():
            raise FileNotFoundError(f"Put your OAuth client file at {SECRET} (see README, step 'YouTube')")
        creds = InstalledAppFlow.from_client_secrets_file(str(SECRET), SCOPES).run_local_server(port=0)
    TOKEN.write_text(creds.to_json())
    return creds


def build_metadata(episode, cfg):
    t = T(cfg)
    name = cfg["channel"]["name"]
    stories = [s for s in episode["segments"] if s["kind"] == "story"]
    date_str = date_text(cfg, dt.date.fromisoformat(episode["date"]), short=True)
    top = stories[0]["headline"] if stories else ""
    title = t["title"].format(headline=top, date=date_str)
    if len(title) > 100:
        title = t["title_short"].format(date=date_str, name=name)

    lines = [f"{name} – {cfg['channel']['tagline']}",
             t["desc_checked"].format(n=len({x['outlet'] for s in stories for x in s['sources']})),
             "", t["desc_stories"]]
    for i, s in enumerate(stories, 1):
        lines.append(f"{i}. {s['headline']}")
    lines += ["", t["desc_sources"]]
    for s in stories:
        lines.append(f"\n▶ {s['headline']}")
        for src in s["sources"]:
            lines.append(f"• {src['outlet']}: {src['url']}")
    lines += ["", t["desc_how"], t["desc_how_text"].format(k=cfg["editor"]["confirm_threshold"]),
              "", t["desc_disclosure"], t["desc_disclosure_text"], "", t["hashtags"]]
    desc = "\n".join(lines)
    return {"title": title, "description": desc[:4900]}


def upload(episode, cfg, out_dir, interactive=True):
    from googleapiclient.discovery import build
    from googleapiclient.http import MediaFileUpload

    out_dir = Path(out_dir)
    meta = build_metadata(episode, cfg)
    yt = build("youtube", "v3", credentials=credentials(interactive))
    body = {
        "snippet": {"title": meta["title"], "description": meta["description"],
                    "tags": cfg["youtube"]["tags"], "categoryId": cfg["youtube"]["category_id"],
                    "defaultLanguage": cfg["channel"]["language"],
                    "defaultAudioLanguage": cfg["channel"]["language"]},
        "status": {"privacyStatus": os.environ.get("YT_PRIVACY", cfg["youtube"]["privacy"]),
                   "selfDeclaredMadeForKids": False,
                   "containsSyntheticMedia": True},  # YouTube's "altered or synthetic content" flag
    }
    media = MediaFileUpload(str(out_dir / "episode.mp4"), chunksize=8 * 1024 * 1024, resumable=True)
    req = yt.videos().insert(part="snippet,status", body=body, media_body=media)
    resp = None
    while resp is None:
        status, resp = req.next_chunk()
        if status:
            print(f"  uploaded {int(status.progress() * 100)}%")
    vid = resp["id"]
    print(f"Uploaded: https://youtu.be/{vid} ({body['status']['privacyStatus']})")
    thumb = out_dir / "thumbnail.jpg"
    if thumb.exists():
        try:
            yt.thumbnails().set(videoId=vid, media_body=MediaFileUpload(str(thumb))).execute()
        except Exception as e:  # custom thumbnails need a phone-verified channel
            print(f"  (thumbnail skipped: {e})")
    return vid
