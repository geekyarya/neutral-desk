#!/usr/bin/env bash
# One-time setup for Linux / macOS. Windows: scripts\setup.bat
set -e
cd "$(dirname "$0")/.."

command -v ffmpeg >/dev/null || { echo "Install FFmpeg first: sudo apt install ffmpeg  (mac: brew install ffmpeg)"; exit 1; }

python3 -m venv .venv
.venv/bin/pip install --upgrade pip
.venv/bin/pip install -r requirements.txt

# download the free voice now so the first run is fast
.venv/bin/python -c "from newsdesk.config import load_config; from newsdesk.tts import ensure_voice; ensure_voice(load_config()['tts']['voice'])"

if command -v ollama >/dev/null; then
  ollama pull "$(.venv/bin/python -c "from newsdesk.config import load_config; print(load_config()['llm']['ollama_model'])")"
else
  echo
  echo "Ollama not found. Install it from https://ollama.com/download, then run:  ollama pull gemma3:12b"
  echo "(or set llm.provider: gemini in config.yaml and export GEMINI_API_KEY)"
fi

echo
echo "Setup done. Make your first episode:"
echo "  source .venv/bin/activate && python run.py script && python run.py video"
