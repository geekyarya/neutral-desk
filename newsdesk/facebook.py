"""Publish a Reel to the Facebook Page (Graph API video_reels). The video must be at a public URL.

Uses a Page access token with pages_manage_posts (FB_TOKEN, or IG_TOKEN when it is that same Page token).
"""
import os
import time

import requests

BASE = "https://graph.facebook.com"


def _check(r):
    if not r.ok:
        raise RuntimeError(f"Facebook API {r.status_code}: {r.text[:300]}")
    return r.json()


def publish_fb_reel(video_url, caption, cfg, token=None):
    token = token or os.environ.get("FB_TOKEN") or os.environ.get("IG_TOKEN")
    if not token or not token.startswith("EAA"):
        raise RuntimeError("Set FB_TOKEN (a Facebook Page access token with pages_manage_posts)")
    v = cfg["instagram"]["api_version"]
    page = _check(requests.get(f"{BASE}/{v}/me", params={"fields": "id,name", "access_token": token}, timeout=30))
    pid = page["id"]
    # 1) start an upload session, 2) let Facebook fetch the video from its URL, 3) publish it with the caption
    start = _check(requests.post(f"{BASE}/{v}/{pid}/video_reels", timeout=60,
                                 data={"upload_phase": "start", "access_token": token}))
    vid = start["video_id"]
    _check(requests.post(start.get("upload_url") or f"https://rupload.facebook.com/video-upload/{v}/{vid}",
                         headers={"Authorization": f"OAuth {token}", "file_url": video_url}, timeout=120))
    _check(requests.post(f"{BASE}/{v}/{pid}/video_reels", timeout=60, data={
        "upload_phase": "finish", "video_id": vid, "video_state": "PUBLISHED", "description": caption,
        "access_token": token}))
    for _ in range(30):  # wait until Facebook has processed it (best effort)
        st = requests.get(f"{BASE}/{v}/{vid}", params={"fields": "status", "access_token": token}, timeout=30).json()
        phase = (st.get("status") or {}).get("video_status")
        if phase in ("ready", "published"):
            break
        if phase == "error":
            raise RuntimeError(f"Facebook could not process the video: {st}")
        time.sleep(10)
    print(f"Published Facebook Reel on {page.get('name')}: https://www.facebook.com/reel/{vid}")
    return vid
