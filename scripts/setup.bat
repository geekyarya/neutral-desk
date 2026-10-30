@echo off
REM One-time setup for Windows. Needs Python 3.10+ and FFmpeg (winget install ffmpeg).
cd /d "%~dp0.."

where ffmpeg >nul 2>nul || (echo Install FFmpeg first:  winget install Gyan.FFmpeg & exit /b 1)

python -m venv .venv
.venv\Scripts\python -m pip install --upgrade pip
.venv\Scripts\pip install -r requirements.txt
.venv\Scripts\python -c "from newsdesk.config import load_config; from newsdesk.tts import ensure_voice; ensure_voice(load_config()['tts']['voice'])"

where ollama >nul 2>nul && (ollama pull gemma3:12b) || (echo Install Ollama from https://ollama.com/download then run: ollama pull gemma3:12b)

echo.
echo Setup done. Make your first episode:
echo   .venv\Scripts\activate ^&^& python run.py script ^&^& python run.py video
