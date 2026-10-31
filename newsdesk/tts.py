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
        from .persona import persona
        pz = persona(cfg)
        self.syn = SynthesisConfig(length_scale=pz.get("length_scale", t["length_scale"]))
        self.sr = self.voice.config.sample_rate
        self.pitch = float(pz.get("pitch", 1.0))
        self.fx = pz.get("voice_fx", "")
        self.emphasis = pz.get("emphasis", False)
        self.strong_words = pz.get("strong_words", [])
        self.last_spans = []
        self.shout = SynthesisConfig(length_scale=pz.get("length_scale", t["length_scale"]) * 0.9)

    def _pitch(self, audio):
        """Raise the voice's pitch without changing its speed (FFmpeg: resample up, then slow back down)."""
        import subprocess
        p = subprocess.run(["ffmpeg", "-loglevel", "error", "-f", "s16le", "-ar", str(self.sr), "-ac", "1",
                            "-i", "-", "-af", f"asetrate={int(self.sr * self.pitch)},aresample={self.sr},"
                            f"atempo={1 / self.pitch:.4f}" + (f",{self.fx}" if self.fx else ""), "-f", "s16le", "-"],
                           input=audio.tobytes(), capture_output=True, check=True)
        return np.frombuffer(p.stdout, dtype=np.int16)

    def say(self, text, path, pause=0.0):
        """Write text as speech to a wav file; returns the duration in seconds."""
        self.last_spans = []  # (start, end) seconds of shouted lines, used to switch the anchor's look
        if self.emphasis:  # shout the exclamations and strong words: a bit faster and louder than the rest
            import re
            parts, pos = [], 0
            for sent in [x for x in re.split(r"(?<=[!?।.])\s+", text) if x.strip()]:
                loud = sent.rstrip().endswith("!") or any(w in sent for w in self.strong_words)
                audio = np.concatenate([c.audio_int16_array for c in
                                        self.voice.synthesize(sent, syn_config=self.shout if loud else self.syn)])
                if loud:
                    audio = np.clip(audio.astype(np.int32) * 1.35, -32767, 32767).astype(np.int16)
                    self.last_spans.append((round(pos / self.sr, 2), round((pos + len(audio)) / self.sr, 2)))
                parts += [audio, np.zeros(int(self.sr * 0.06), dtype=np.int16)]
                pos += len(audio) + int(self.sr * 0.06)
            speech = np.concatenate(parts)
        else:
            speech = np.concatenate([c.audio_int16_array for c in self.voice.synthesize(text, syn_config=self.syn)])
        if abs(self.pitch - 1.0) > 0.01 or self.fx:
            speech = self._pitch(speech)
        audio = np.concatenate([speech, np.zeros(int(self.sr * pause), dtype=np.int16)])
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
        seg["shout_spans"] = speaker.last_spans
        seg["audio"] = str(path.relative_to(out_dir))
        print(f"  {seg['id']:<8} {seg['duration']:6.1f}s")
    return episode


def read_wav(path):
    with wave.open(str(path)) as w:
        sr = w.getframerate()
        data = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16)
    return data, sr
