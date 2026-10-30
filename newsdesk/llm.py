"""Free LLM backends: local Ollama or Google Gemini free tier."""
import json
import os
import re

import requests


def complete_json(cfg, prompt):
    c = cfg["llm"]
    if c["provider"] == "ollama":
        r = requests.post(f"{c['ollama_host']}/api/generate", timeout=900, json={
            "model": c["ollama_model"], "prompt": prompt, "stream": False, "format": "json",
            "options": {"temperature": c["temperature"], "num_ctx": 8192}})
        r.raise_for_status()
        text = r.json()["response"]
    elif c["provider"] == "gemini":
        key = os.environ.get("GEMINI_API_KEY")
        if not key:
            raise RuntimeError("Set GEMINI_API_KEY (free at https://aistudio.google.com/apikey)")
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{c['gemini_model']}:generateContent"
        r = requests.post(url, params={"key": key}, timeout=300, json={
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"temperature": c["temperature"],
                                 "responseMimeType": "application/json"}})
        r.raise_for_status()
        text = r.json()["candidates"][0]["content"]["parts"][0]["text"]
    else:
        raise RuntimeError(f"Unknown llm provider {c['provider']}")
    return _parse_json(text)


def _parse_json(text):
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        m = re.search(r"\{.*\}", text, re.S)
        if not m:
            raise
        return json.loads(m.group(0))
