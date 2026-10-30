# Neutral Desk: free AI news channel

This pipeline makes a daily **Hindi** YouTube news episode about **India** (5 Indian stories and 1 world story). It reads 32 news feeds, from 20 Indian outlets across the editorial spectrum plus foreign media, and **states something as fact only when 3 or more independent media groups report it**. Outlets with the same owner count as one source, so TOI and Economic Times (both Times Group) count once. Everything else is attributed to its source or labelled "स्वतंत्र रूप से पुष्टि नहीं" (not independently confirmed). An AI anchor with a Hindi AI voice presents the episode.

Every part is free: no paid APIs and no subscriptions.

```
RSS feeds ─► group same story ─► LLM cross-check ─► script.json ─► Piper voice ─► anchor + graphics ─► episode.mp4 ─► YouTube
 (32 feeds)    (TF-IDF clusters)   (Ollama/Gemini)    (you review)    (offline TTS)   (FFmpeg)                          (private)
```

| Step | Tool | Cost |
|---|---|---|
| News | RSS feeds from 32 feeds, editable in `config.yaml` | free |
| Story grouping | scikit-learn | free, CPU |
| Fact cross-check and script | **Ollama** (local, unlimited) or **Gemini free tier** | free |
| Hindi voice | **Piper** `hi_IN-rohan` (offline neural TTS) | free, CPU |
| Anchor | built-in animated anchor (CPU), or a realistic face through free Colab GPU | free |
| Video | FFmpeg | free |
| Upload | YouTube Data API | free |

---

## 1. Setup (one time, about 10 minutes)

You need **Python 3.10+** and **FFmpeg**.

**Windows**
```
winget install Gyan.FFmpeg
scripts\setup.bat
```
**Linux / macOS**
```
sudo apt install ffmpeg        # mac: brew install ffmpeg
bash scripts/setup.sh
```

**LLM (choose one):**
- **Gemini (best Hindi, no strong PC needed):** get a free key at https://aistudio.google.com/apikey, set `llm.provider: gemini` in `config.yaml`, and run `set GEMINI_API_KEY=...` on Windows or `export GEMINI_API_KEY=...` on Linux/macOS.
- **Ollama (unlimited, private, offline):** install from https://ollama.com/download, then run `ollama pull gemma3:12b`. This needs about 16 GB of RAM. On a weaker PC, use `gemma3:4b`, which writes weaker Hindi. Gemma models write much better Hindi than Qwen or Llama models of the same size.

## 2. Make an episode

```
python run.py script      # fetch news → cross-check → output/<date>/script.json
```
**Review `script.json`.** Fix anything wrong and delete any story you don't want. This human check matters for news.
```
python run.py video       # voice + anchor + graphics → output/<date>/episode.mp4
python run.py shorts      # one vertical Short per story → output/<date>/shorts/
python run.py weekly      # week in review from the last 7 days → output/week-<date>/
```
The same folder also gets `thumbnail.jpg`, `youtube_title.txt` and `youtube_description.txt`. The description includes every source link and the AI disclosure.

A 4–6 minute episode renders in about 1 minute on a normal laptop CPU.

## 3. YouTube upload

**Easiest:** upload `episode.mp4` in YouTube Studio and paste in the title and description files. While uploading, tick **"Altered or synthetic content: Yes"**.

**Automatic (YouTube Data API, free):**
1. Go to https://console.cloud.google.com, create a project, then open **APIs & Services → Library** and enable **YouTube Data API v3**.
2. Under **OAuth consent screen**, choose External, add yourself as a test user, and then click **Publish app**. If you don't publish it, your login expires every 7 days.
3. Under **Credentials → Create credentials → OAuth client ID → Desktop app**, download the file and save it as `client_secret.json` in this folder.
4. Run `python run.py auth` once to log in with the channel's Google account.
5. Run `python run.py upload`. This uploads the video as **private** with the synthetic-content flag set. Review it in YouTube Studio and then publish.

> ⚠️ YouTube rule: videos uploaded through a new, unaudited API project stay **locked to private**. To publish API uploads publicly, apply for the free API compliance audit (search "YouTube API Services audit and quota extension form"). Until the audit is approved, use the manual Studio upload. It takes about 1 minute because the title and description are generated for you.

## 4. Fully automatic daily run (optional, free)

Push this folder to a GitHub repo. `.github/workflows/daily-episode.yml` builds an episode every day at 07:07 IST on GitHub's free runners, using Gemini and the built-in anchor. Add these repo secrets:
- `GEMINI_API_KEY`
- `YT_TOKEN` (optional): your YouTube login, created as described below.

The video uploads as **private**, and you approve it from the YouTube Studio phone app. The video files are also saved as a workflow artifact for 7 days.

**Creating `YT_TOKEN` in the browser (no Python needed):**
1. Do steps 1 and 2 from section 3 above.
2. Under **Credentials → Create credentials → OAuth client ID**, choose **Web application** and add the authorized redirect URI `https://developers.google.com/oauthplayground`. Copy the Client ID and Client secret.
3. Open https://developers.google.com/oauthplayground. Click ⚙️ (top right), tick **Use your own OAuth credentials**, and paste in the Client ID and Client secret.
4. In the box on the left, type `https://www.googleapis.com/auth/youtube.upload`, click **Authorize APIs**, and log in with the account that owns the channel. If you have several channels, pick the right one. Google may warn that the app isn't verified; click **Advanced → Go to ...**, since it's your own app.
5. Click **Exchange authorization code for tokens** and copy the **Refresh token**.
6. In GitHub, create a repo secret named `YT_TOKEN` with this value:
   ```json
   {"client_id": "YOUR_CLIENT_ID", "client_secret": "YOUR_CLIENT_SECRET", "refresh_token": "YOUR_REFRESH_TOKEN", "token_uri": "https://oauth2.googleapis.com/token"}
   ```

## 4b. What runs automatically

| When | Workflow | What it makes |
|---|---|---|
| Every day, 07:07 IST | `daily-episode` | The main bulletin (5–6 min) plus one vertical **Short** per story (30–40 s, up to 5). Everything is uploaded, and each Short links to the bulletin. |
| Every Sunday, 10:07 IST | `weekly-review` | A long **week in review** from the week's best-covered stories. It's saved under the run's *Artifacts* for you to upload manually. |

- **AI backup:** Gemini writes the scripts. If it is down or out of free quota, a small Ollama model (`gemma3:4b`) on the GitHub runner takes over. It is slower and writes weaker Hindi, but the episode still goes out.
- **YouTube limits:** the free API quota allows 6 uploads a day (1 bulletin + 5 Shorts). If the quota runs out, the remaining uploads are skipped and logged.
- **Test runs:** under Actions → daily-episode → Run workflow, untick "Upload to YouTube" to test without posting.

## 5. Realistic AI anchor (optional)

The built-in anchor is an illustrated character, so it works anywhere. For a photoreal talking face:
1. Create a **fictional** face with Stable Diffusion or Fooocus (free) and save it as `assets/anchor_face.png`. Never use a real person.
2. Run `python run.py pack`. This creates `output/<date>/lipsync_input.zip`.
3. Open `colab/lipsync.ipynb` in Google Colab on a free T4 GPU, upload the zip, and download `anchor_clips.zip`.
4. Unzip it into `output/<date>/anchor/`, set `anchor.mode: lipsync`, and run `python run.py video`.

## 6. Customising (`config.yaml`)
- `feeds`: add or remove outlets. Keep the mix balanced across countries and political lines. The editor groups articles by story and counts **each outlet only once**.
- `editor.min_outlets`, `min_countries`, `confirm_threshold`: how strict verification is.
- `channel.language`: `hi` (Hindi) or `en` (English). All on-screen, spoken and YouTube text is in `newsdesk/strings.py`, which you can edit.
- `channel.name` / `spoken_name`: the name shown on screen, and how the anchor pronounces it (written in Devanagari).
- `editor.india_stories` / `world_stories`: how many stories of each kind per episode. India-desk stories are double-checked by the AI, and a story that isn't actually about India (for example, a foreign event Indian papers covered) is skipped.
- `tts.voice`: the Hindi voices are `hi_IN-rohan-medium` (male), `hi_IN-pratham-medium` (male) and `hi_IN-priyamvada-medium` (female).
- `feeds`: each feed has an `owner`, which is its media group. Same owner means the feeds are not independent. Add regional outlets the same way.

## How the bias filter works
1. A story qualifies only when at least 3 **different media owners** cover it, so a story pushed by one media house never makes the episode. World stories also need coverage from at least 2 countries. Indian stories that foreign media also covered are marked "+ विदेशी मीडिया".
2. The LLM gets every outlet's version side by side. It separates **confirmed facts** (stated by 3 or more outlets) from **disputed or single-source claims**, and writes the script without loaded words.
3. **The code re-checks the LLM's output.** A "confirmed" fact must cite 3 or more outlets that really are in the input. If not, the fact is moved to "not independently confirmed". This guards against LLM hallucination.
4. The screen shows पुष्टि हुई (confirmed) facts and स्वतंत्र रूप से पुष्टि नहीं (not independently confirmed) claims separately, along with how many independent groups reported the story and which outlets they were.

## Rules to keep the channel safe
- The on-screen "AI द्वारा बनाए गए एंकर और आवाज़" label and the description disclosure are always on. YouTube and India's IT Rules both require AI-generated content to be labelled.
- Review every script before publishing. An AI mistake in news can be defamatory.
- Use only the generated graphics. Never use other channels' footage or photos, because that leads to copyright strikes.
- Use a fictional anchor face and voice only.

## Files
```
run.py                 CLI: script / audio / video / upload / all / auth / pack
config.yaml            all settings and feeds
newsdesk/fetch.py      RSS + full-text extraction
newsdesk/cluster.py    group articles into stories, rank by coverage breadth
newsdesk/editor.py     cross-check prompt + verification + intro/outro
newsdesk/llm.py        Ollama / Gemini
newsdesk/tts.py        Piper voice
newsdesk/anchor.py     animated anchor (mouth follows voice, natural blinks)
newsdesk/render.py     broadcast graphics, ticker, FFmpeg encode, thumbnail
newsdesk/strings.py    all Hindi / English text
newsdesk/text.py       Hindi + English mixed-font text drawing
assets/fonts/          Noto Sans + Noto Sans Devanagari (free, OFL licence)
newsdesk/upload.py     YouTube upload + description with sources
colab/lipsync.ipynb    realistic face (SadTalker, free GPU)
```
