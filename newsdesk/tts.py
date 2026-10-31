"""Step 5: free offline voice with Piper."""
import wave
from pathlib import Path

import numpy as np
import requests

from .config import ROOT

HF = "https://huggingface.co/rhasspy/piper-voices/resolve/main/"


def ensure_voice(voice):
    models = ROOT / "models"
    models.mkdir(exist_ok=True)
    onnx = models / (Path(voice).name + ".onnx")
    for f, suffix in ((onnx, ".onnx"), (onnx.with_suffix(".onnx.json"), ".onnx.json")):
        if not f.exists():
            print(f"Downloading voice {f.name}...")
            r = requests.get(HF + voice + suffix, timeout=300)
            r.raise_for_status()
            f.write_bytes(r.content)
    return onnx


OUT_SR = 24000  # every voice track is written at this rate, whichever engine made it


def _ffmpeg_audio(audio, sr_in, chain):
    import subprocess
    p = subprocess.run(["ffmpeg", "-loglevel", "error", "-f", "s16le", "-ar", str(sr_in), "-ac", "1", "-i", "-",
                        "-af", chain, "-ar", str(OUT_SR), "-f", "s16le", "-"],
                       input=audio.tobytes(), capture_output=True, check=True)
    return np.frombuffer(p.stdout, dtype=np.int16)


class Speaker:
    """Text to speech. Engines:
      gemini - Gemini speech model with acting directions (natural, expressive; uses GEMINI_API_KEY)
      piper  - offline Piper voice (always available; used as the fallback)
    """

    def __init__(self, cfg):
        from .persona import persona
        self.cfg, self.t = cfg, cfg["tts"]
        self.pz = persona(cfg)
        self.engine = self.pz.get("tts_engine", self.t.get("engine", "piper"))
        self.gemini_off = False
        self._piper_voice = None
        self.last_engine = None
        self.last_spans = []

    # ---------------- Gemini (expressive) ----------------
    def _gemini_models(self):
        import os
        import requests
        if hasattr(self, "_models"):
            return self._models
        wanted = list(self.t.get("gemini_models", []))
        try:  # also discover whatever speech models this key can use
            r = requests.get("https://generativelanguage.googleapis.com/v1beta/models", timeout=30,
                             headers={"x-goog-api-key": os.environ.get("GEMINI_API_KEY", "")},
                             params={"pageSize": 200})
            found = [m["name"].split("/")[-1] for m in r.json().get("models", []) if "tts" in m["name"]]
            wanted += [m for m in found if m not in wanted]
            print(f"   speech models available: {', '.join(found) or 'none'}")
        except Exception:
            pass
        self._models = wanted
        return wanted

    def _gemini(self, text, mood):
        import base64
        import os
        import re
        import time
        import requests
        key = os.environ.get("GEMINI_API_KEY")
        if not key:
            raise RuntimeError("no GEMINI_API_KEY")
        style = self.pz.get("tts_styles", {}).get(mood) or self.pz.get("tts_styles", {}).get("default", "")
        body = {"contents": [{"parts": [{"text": f"{style}:\n{text}" if style else text}]}],
                "generationConfig": {"responseModalities": ["AUDIO"], "speechConfig": {"voiceConfig": {
                    "prebuiltVoiceConfig": {"voiceName": self.pz.get("gemini_voice", "Fenrir")}}}}}
        last = None
        for model in self._gemini_models():
            for attempt in range(3):
                r = requests.post(f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
                                  headers={"x-goog-api-key": key}, json=body, timeout=300)
                if r.ok:
                    cand = (r.json().get("candidates") or [{}])[0]
                    parts = (cand.get("content") or {}).get("parts") or []
                    part = next((p_["inlineData"] for p_ in parts if "inlineData" in p_), None)
                    if part:
                        rate = int((re.search(r"rate=(\d+)", part.get("mimeType", "")) or [0, 24000])[1])
                        pcm = np.frombuffer(base64.b64decode(part["data"]), dtype=np.int16)
                        self.last_engine = f"gemini:{model}"
                        return pcm, rate
                    # empty answer (it happens now and then, or a filter tripped): retry, then the next model
                    last = f"{model}: no audio (finishReason={cand.get('finishReason')})"
                    print(f"   {last}; retrying")
                    if attempt < 2:
                        time.sleep(3)
                        continue
                    break
                last = f"{model}: HTTP {r.status_code} {r.text[:160]}"
                if r.status_code == 429 and "PerDay" not in r.text and attempt < 2:
                    time.sleep(25)  # per-minute limit: wait and retry
                    continue
                break  # retired, not allowed, or out of daily quota: try the next model
        raise RuntimeError(last or "no Gemini speech model available")

    # ---------------- Piper (offline fallback) ----------------
    def _piper(self, text):
        from piper import PiperVoice
        from piper.config import SynthesisConfig
        if self._piper_voice is None:
            self._piper_voice = PiperVoice.load(str(ensure_voice(self.t["voice"])))
        v = self._piper_voice
        syn = SynthesisConfig(length_scale=self.pz.get("length_scale", self.t["length_scale"]))
        sr = v.config.sample_rate
        if not self.pz.get("emphasis"):
            return np.concatenate([c.audio_int16_array for c in v.synthesize(text, syn_config=syn)]), sr
        # same voice throughout; exclamations are only a little louder, with smooth fades (no pitch change)
        import re
        parts = []
        fade = int(sr * 0.03)
        for sent in [x for x in re.split(r"(?<=[!?।.])\s+", text) if x.strip()]:
            a = np.concatenate([c.audio_int16_array for c in v.synthesize(sent, syn_config=syn)]).astype(np.float32)
            if sent.rstrip().endswith("!") and len(a) > 2 * fade:
                gain = np.full(len(a), 1.4, np.float32)
                gain[:fade] = np.linspace(1, 1.4, fade)
                gain[-fade:] = np.linspace(1.4, 1, fade)
                a = a * gain
            parts += [np.clip(a, -32767, 32767).astype(np.int16), np.zeros(int(sr * 0.06), np.int16)]
        self.last_engine = "piper"
        return np.concatenate(parts), sr

    def say(self, text, path, pause=0.0, mood="default"):
        """Write text as speech to a wav file; returns the duration in seconds."""
        audio = None
        if self.engine == "gemini" and not self.gemini_off:
            try:
                pcm, rate = self._gemini(text, mood)
                audio = _ffmpeg_audio(pcm, rate, "highpass=f=70,alimiter=limit=0.97")
            except Exception as e:
                print(f"   Gemini voice unavailable ({str(e)[:160]}); using the offline voice")
                self.gemini_off = True
        if audio is None:
            pcm, rate = self._piper(text)
            pitch = float(self.pz.get("pitch", 1.0))
            chain = [f"asetrate={int(rate * pitch)},aresample={rate},atempo={1 / pitch:.4f}"] if abs(pitch - 1) > 0.01 else []
            chain += [self.pz["voice_fx"]] if self.pz.get("voice_fx") else []
            audio = _ffmpeg_audio(pcm, rate, ",".join(chain) or "anull")
        audio = np.concatenate([audio, np.zeros(int(OUT_SR * pause), dtype=np.int16)])
        with wave.open(str(path), "wb") as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(OUT_SR)
            w.writeframes(audio.tobytes())
        return round(len(audio) / OUT_SR, 3)


def segment_mood(seg):
    if seg.get("kind") == "intro":
        return "intro"
    if seg.get("tragedy"):
        return "serious"  # deaths, disasters, violence: calm and respectful, no jokes
    return "angry" if seg.get("angry") else "calm"


def synthesize_episode(episode, cfg, out_dir):
    speaker = Speaker(cfg)
    audio_dir = Path(out_dir) / "audio"
    audio_dir.mkdir(exist_ok=True)
    for attempt in range(2):
        engines = set()
        for seg in episode["segments"]:
            path = audio_dir / f"{seg['id']}.wav"
            seg["duration"] = speaker.say(seg["script"], path, cfg["tts"]["pause_after_segment"], segment_mood(seg))
            seg["audio"] = str(path.relative_to(out_dir))
            engines.add((speaker.last_engine or "piper").split(":")[0])
            print(f"  {seg['id']:<8} {seg['duration']:6.1f}s  [{speaker.last_engine}]")
        if len(engines) <= 1:
            break
        print("   voices got mixed (Gemini stopped mid-way): redoing the episode in one voice")
        speaker.gemini_off = True
    return episode


def read_wav(path):
    with wave.open(str(path)) as w:
        sr = w.getframerate()
        data = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16)
    return data, sr
