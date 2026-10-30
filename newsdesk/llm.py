"""Free LLM backends: local Ollama or Google Gemini free tier, with automatic fallback."""
import json
import os
import re
import time

import requests

RETRY_STATUS = {429, 500, 502, 503, 504}  # rate limit / overloaded: worth waiting and retrying
_last_call = [0.0]
_exhausted = set()  # Gemini models whose free DAILY quota is used up: skip them for the rest of the run


def complete_json(cfg, prompt):
    c = cfg["llm"]
    try:
        text = _call(c, c["provider"], prompt)
    except RuntimeError as e:
        fb = c.get("fallback_provider")
        if not fb or fb == c["provider"]:
            raise
        print(f"   {c['provider']} failed ({str(e)[:120]}); using {fb}")
        text = _call(c, fb, prompt, fallback=True)
    return _parse_json(text)


def _call(c, provider, prompt, fallback=False):
    if provider == "ollama":
        return _ollama(c, prompt, c.get("fallback_ollama_model") if fallback else None)
    if provider == "gemini":
        return _gemini(c, prompt)
    raise RuntimeError(f"Unknown llm provider {provider}")


def _ollama(c, prompt, model=None):
    try:
        r = requests.post(f"{c['ollama_host']}/api/generate", timeout=1800, json={
            "model": model or c["ollama_model"], "prompt": prompt, "stream": False, "format": "json",
            "options": {"temperature": c["temperature"], "num_ctx": 8192}})
        r.raise_for_status()
    except requests.RequestException as e:
        raise RuntimeError(f"ollama: {e}") from e
    return r.json()["response"]


def _gemini(c, prompt):
    key = os.environ.get("GEMINI_API_KEY")
    if not key:
        raise RuntimeError("Set GEMINI_API_KEY (free at https://aistudio.google.com/apikey)")
    models = [m for m in [c["gemini_model"], *c.get("gemini_fallback_models", [])] if m not in _exhausted]
    body = {"contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"temperature": c["temperature"], "responseMimeType": "application/json"}}
    last = "all Gemini models are out of daily quota"
    for model in models:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
        for attempt in range(3):
            # free tier allows only a few requests per minute: keep calls spaced out
            wait = c.get("gemini_min_interval", 6) - (time.time() - _last_call[0])
            if wait > 0:
                time.sleep(wait)
            _last_call[0] = time.time()
            try:
                # key goes in a header, not the URL, so it never shows up in logs
                r = requests.post(url, headers={"x-goog-api-key": key}, json=body, timeout=300)
            except requests.RequestException as e:
                last = e
            else:
                if r.ok:
                    return r.json()["candidates"][0]["content"]["parts"][0]["text"]
                last = f"{model}: HTTP {r.status_code}"
                if r.status_code == 429 and "PerDay" in r.text:
                    _exhausted.add(model)  # daily quota gone: retrying today is pointless
                    print(f"   {model}: free daily quota used up")
                    break
                if r.status_code not in RETRY_STATUS:
                    break  # e.g. 404 model retired -> try the next model
            delay = 10 * 2 ** attempt
            print(f"   Gemini busy ({last}); retrying in {delay}s")
            time.sleep(delay)
    raise RuntimeError(f"Gemini failed: {last}")


def _parse_json(text):
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        m = re.search(r"\{.*\}", text, re.S)
        if not m:
            raise
        return json.loads(m.group(0))
