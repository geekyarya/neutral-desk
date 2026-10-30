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


def synthesize_episode(episode, cfg, out_dir):
    from piper import PiperVoice
    from piper.config import SynthesisConfig

    t = cfg["tts"]
    voice = PiperVoice.load(str(ensure_voice(t["voice"])))
    syn = SynthesisConfig(length_scale=t["length_scale"])
    audio_dir = Path(out_dir) / "audio"
    audio_dir.mkdir(exist_ok=True)

    for seg in episode["segments"]:
        path = audio_dir / f"{seg['id']}.wav"
        chunks = [c.audio_int16_array for c in voice.synthesize(seg["script"], syn_config=syn)]
        sr = voice.config.sample_rate
        pause = np.zeros(int(sr * t["pause_after_segment"]), dtype=np.int16)
        audio = np.concatenate([*chunks, pause])
        with wave.open(str(path), "wb") as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(sr)
            w.writeframes(audio.tobytes())
        seg["audio"] = str(path.relative_to(out_dir))
        seg["duration"] = round(len(audio) / sr, 3)
        print(f"  {seg['id']:<8} {seg['duration']:6.1f}s")
    return episode


def read_wav(path):
    with wave.open(str(path)) as w:
        sr = w.getframerate()
        data = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16)
    return data, sr
