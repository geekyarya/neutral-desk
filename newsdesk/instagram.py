"""Publish a Reel with the Instagram API. The video must be at a public URL.

Works with either kind of token in IG_TOKEN:
  - Instagram Login token (starts with "IG"): graph.instagram.com, expires after 60 days (auto-renewable)
  - Facebook Login token (starts with "EAA"): graph.facebook.com via the Facebook Page linked to the
    Instagram account; a Page token made from a long-lived user token never expires
"""
import os
import time

import requests

IG_BASE = "https://graph.instagram.com"
FB_BASE = "https://graph.facebook.com"


def _check(r):
    if not r.ok:
        raise RuntimeError(f"Instagram API {r.status_code}: {r.text[:300]}")
    return r.json()


def _account(token, v):
    """(base url, instagram user id, username, token to use)."""
    if token.startswith("IG"):
        me = _check(requests.get(f"{IG_BASE}/{v}/me", params={"fields": "user_id,username", "access_token": token},
                                 timeout=30))
        return IG_BASE, me["user_id"], me.get("username"), token
    # Facebook Login: a Page token knows its Instagram account directly; a user token lists its Pages
    me = _check(requests.get(f"{FB_BASE}/{v}/me", timeout=30,
                             params={"fields": "instagram_business_account{id,username}", "access_token": token}))
    ig = me.get("instagram_business_account")
    if ig:
        return FB_BASE, ig["id"], ig.get("username"), token
    pages = _check(requests.get(f"{FB_BASE}/{v}/me/accounts", timeout=30, params={
        "fields": "access_token,instagram_business_account{id,username}", "access_token": token}))["data"]
    for page in pages:
        if page.get("instagram_business_account"):
            ig = page["instagram_business_account"]
            return FB_BASE, ig["id"], ig.get("username"), page["access_token"]
    raise RuntimeError("No Instagram professional account is linked to a Facebook Page this token can manage")


def publish_reel(video_url, caption, cfg, token=None):
    token = token or os.environ.get("IG_TOKEN")
    if not token:
        raise RuntimeError("Set IG_TOKEN (Instagram access token)")
    v = cfg["instagram"]["api_version"]
    base, uid, username, token = _account(token, v)
    container = _check(requests.post(f"{base}/{v}/{uid}/media", timeout=60, data={
        "media_type": "REELS", "video_url": video_url, "caption": caption, "share_to_feed": "true",
        "access_token": token}))["id"]
    # Instagram downloads and processes the video; wait until it's ready
    for _ in range(60):
        status = _check(requests.get(f"{base}/{v}/{container}", timeout=30,
                                     params={"fields": "status_code,status", "access_token": token}))
        if status.get("status_code") == "FINISHED":
            break
        if status.get("status_code") in ("ERROR", "EXPIRED"):
            raise RuntimeError(f"Instagram could not process the video: {status}")
        time.sleep(10)
    else:
        raise RuntimeError("Instagram took too long to process the video")
    media = _check(requests.post(f"{base}/{v}/{uid}/media_publish", timeout=60,
                                 data={"creation_id": container, "access_token": token}))["id"]
    link = requests.get(f"{base}/{v}/{media}", params={"fields": "permalink", "access_token": token},
                        timeout=30).json().get("permalink", "")
    print(f"Published Reel on @{username}: {link or media}")
    return media


def refresh_token(token):
    """Instagram Login tokens last 60 days; refreshing (allowed once a day) gives a fresh 60 days.
    Facebook Page tokens don't expire, so there is nothing to refresh."""
    if not token.startswith("IG"):
        return None
    r = requests.get(f"{IG_BASE}/refresh_access_token", timeout=30,
                     params={"grant_type": "ig_refresh_token", "access_token": token})
    return r.json().get("access_token") if r.ok else None
