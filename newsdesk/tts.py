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


class Speaker:
    def __init__(self, cfg):
        from piper import PiperVoice
        from piper.config import SynthesisConfig
        t = cfg["tts"]
        self.voice = PiperVoice.load(str(ensure_voice(t["voice"])))
        self.syn = SynthesisConfig(length_scale=t["length_scale"])
        self.sr = self.voice.config.sample_rate

    def say(self, text, path, pause=0.0):
        """Write text as speech to a wav file; returns the duration in seconds."""
        chunks = [c.audio_int16_array for c in self.voice.synthesize(text, syn_config=self.syn)]
        audio = np.concatenate([*chunks, np.zeros(int(self.sr * pause), dtype=np.int16)])
        with wave.open(str(path), "wb") as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(self.sr)
            w.writeframes(audio.tobytes())
        return round(len(audio) / self.sr, 3)


def synthesize_episode(episode, cfg, out_dir):
    speaker = Speaker(cfg)
    audio_dir = Path(out_dir) / "audio"
    audio_dir.mkdir(exist_ok=True)
    for seg in episode["segments"]:
        path = audio_dir / f"{seg['id']}.wav"
        seg["duration"] = speaker.say(seg["script"], path, cfg["tts"]["pause_after_segment"])
        seg["audio"] = str(path.relative_to(out_dir))
        print(f"  {seg['id']:<8} {seg['duration']:6.1f}s")
    return episode


def read_wav(path):
    with wave.open(str(path)) as w:
        sr = w.getframerate()
        data = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16)
    return data, sr
