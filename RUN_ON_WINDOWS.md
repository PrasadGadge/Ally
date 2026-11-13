# Run Vivie on Windows — Step by Step

## What you need

- Windows 10 or 11
- Python 3.10 or 3.11 (3.14 works if already installed)
- Microphone + speakers or headset
- Internet connection
- **ffmpeg** on PATH (for fast TTS): https://www.gyan.dev/ffmpeg/builds/ — unzip and add `bin` to System PATH

---

## Step 1 — Open the project folder

1. Press `Win + E` (File Explorer)
2. Go to:
   `C:\Users\dell\OneDrive\Desktop\queen`
3. Click the address bar, type `cmd`, press Enter  
   (opens Command Prompt in that folder)

Or in Cursor: **Terminal → New Terminal** (already in project folder).

---

## Step 2 — Create virtual environment (recommended)

```bat
python -m venv venv
venv\Scripts\activate
```

You should see `(venv)` at the start of the line.

---

## Step 3 — Install dependencies

**Full install (recommended first time):**

```bat
python setup.py --full
```

**Or minimal (voice + brain only):**

```bat
python setup.py
```

Wait until pip finishes (can take 5–20 minutes with `--full`).

---

## Step 4 — API keys (.env)

1. Copy the template:
   ```bat
   copy .env.example .env
   ```
2. Open `.env` in Notepad and set at least:
   ```
   GROQ_API_KEY=your_key_here
   ```
   Get a free key: https://console.groq.com/

3. Optional but useful:
   ```
   OPENAI_API_KEY=...          # or OPENROUTER_API_KEY
   GOOGLE_API_KEY=...          # Gemini
   MEM0_API_KEY=...            # long-term cloud memory
   TAVILY_API_KEY=...          # web search
   ```

Save `.env`. **Never share or commit this file.**

---

## Step 5 — Validate install

```bat
python validate_deps.py
python validate_deps.py --health
```

You want:
- `[OK]` on critical packages
- Health report from the `--health` command (STT, TTS, memory, automation)

Fix any `[FAIL]` lines with `pip install <package>`.

---

## Step 6 — Run tests (optional, 1 minute)

```bat
python -m pytest tests/ -q
```

Expect the full suite to pass. Current baseline: **50+ tests passed, 1 skipped**.

---

## Step 7 — Start Vivie

```bat
python Vivie.py
```

What should happen:
1. Online greeting (voice + notification)
2. Console shows **Health** report
3. Browser opens **ui.html** (Vivie panel)
4. Console says STT ready / WebSocket started
5. Status in UI: listening → you speak → she replies

**Stop:** press `Ctrl + C` in the terminal.

---

## Step 8 — Talk to Vivie

1. Allow **microphone** if Windows asks.
2. Wait until UI shows listening / agent ready.
3. Say clearly: **"Hey Vivie, what time is it?"** or **"Hey Vivie, how are you?"**
4. Wait for her reply (voice + text in UI).

**Try these:**
- "What's the weather?"
- "Check my internet speed"
- "Open Chrome" (needs optional automation packages)
- "Vivie stop" — goes silent
- "Vivie wake up" — listens again

---

## Troubleshooting

| Problem | Fix |
|--------|-----|
| No mic / STT silent | Install `sounddevice`, check Windows Privacy → Microphone |
| No voice | Install `edge-tts`, `ffmpeg`, `pygame-ce` |
| API errors in console | Check `.env` keys; Groq for STT |
| UI blank | Refresh browser; check terminal for WebSocket errors |
| Slow first start | Normal — Chroma/embeddings load once |

---

## Quick re-run (after first setup)

```bat
cd C:\Users\dell\OneDrive\Desktop\queen
venv\Scripts\activate
python Vivie.py
```

---

When you've tried it, note: did she hear you, reply by voice, and show text in the UI? That feedback helps tune the next fixes.
