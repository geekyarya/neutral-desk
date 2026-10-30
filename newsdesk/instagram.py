"""Publish a Reel with the Instagram API (Instagram Login). The video must be at a public URL."""
import os
import time

import requests

BASE = "https://graph.instagram.com"


def _check(r):
    if not r.ok:
        raise RuntimeError(f"Instagram API {r.status_code}: {r.text[:300]}")
    return r.json()


def publish_reel(video_url, caption, cfg, token=None):
    token = token or os.environ.get("IG_TOKEN")
    if not token:
        raise RuntimeError("Set IG_TOKEN (Instagram access token)")
    v = cfg["instagram"]["api_version"]
    me = _check(requests.get(f"{BASE}/{v}/me", params={"fields": "user_id,username", "access_token": token},
                             timeout=30))
    uid = me["user_id"]
    container = _check(requests.post(f"{BASE}/{v}/{uid}/media", timeout=60, data={
        "media_type": "REELS", "video_url": video_url, "caption": caption, "share_to_feed": "true",
        "access_token": token}))["id"]
    # Instagram downloads and processes the video; wait until it's ready
    for _ in range(60):
        status = _check(requests.get(f"{BASE}/{v}/{container}", timeout=30,
                                     params={"fields": "status_code,status", "access_token": token}))
        if status.get("status_code") == "FINISHED":
            break
        if status.get("status_code") in ("ERROR", "EXPIRED"):
            raise RuntimeError(f"Instagram could not process the video: {status}")
        time.sleep(10)
    else:
        raise RuntimeError("Instagram took too long to process the video")
    media = _check(requests.post(f"{BASE}/{v}/{uid}/media_publish", timeout=60,
                                 data={"creation_id": container, "access_token": token}))["id"]
    link = requests.get(f"{BASE}/{v}/{media}", params={"fields": "permalink", "access_token": token},
                        timeout=30).json().get("permalink", "")
    print(f"Published Reel on @{me.get('username')}: {link or media}")
    return media


def refresh_token(token):
    """Long-lived tokens last 60 days; refreshing (allowed once a day) gives a fresh 60 days."""
    r = requests.get(f"{BASE}/refresh_access_token", timeout=30,
                     params={"grant_type": "ig_refresh_token", "access_token": token})
    return r.json().get("access_token") if r.ok else None
