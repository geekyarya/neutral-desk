"""Free LLM backends: local Ollama or Google Gemini free tier."""
import json
import os
import re
import time

import requests

RETRY_STATUS = {429, 500, 502, 503, 504}  # rate limit / overloaded: worth waiting and retrying
_last_call = [0.0]


def complete_json(cfg, prompt):
    c = cfg["llm"]
    if c["provider"] == "ollama":
        r = requests.post(f"{c['ollama_host']}/api/generate", timeout=900, json={
            "model": c["ollama_model"], "prompt": prompt, "stream": False, "format": "json",
            "options": {"temperature": c["temperature"], "num_ctx": 8192}})
        r.raise_for_status()
        text = r.json()["response"]
    elif c["provider"] == "gemini":
        text = _gemini(c, prompt)
    else:
        raise RuntimeError(f"Unknown llm provider {c['provider']}")
    return _parse_json(text)


def _gemini(c, prompt):
    key = os.environ.get("GEMINI_API_KEY")
    if not key:
        raise RuntimeError("Set GEMINI_API_KEY (free at https://aistudio.google.com/apikey)")
    models = [c["gemini_model"], *c.get("gemini_fallback_models", [])]
    body = {"contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"temperature": c["temperature"], "responseMimeType": "application/json"}}
    last = None
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
                last = RuntimeError(f"{model}: HTTP {r.status_code} {r.text[:200]}")
                if r.status_code not in RETRY_STATUS:
                    break  # e.g. 404 model retired -> try the next model
            delay = 10 * 2 ** attempt
            print(f"   Gemini busy ({last}); retrying in {delay}s")
            time.sleep(delay)
        print(f"   giving up on {model}, trying next model")
    raise RuntimeError(f"All Gemini models failed: {last}")


def _parse_json(text):
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        m = re.search(r"\{.*\}", text, re.S)
        if not m:
            raise
        return json.loads(m.group(0))
