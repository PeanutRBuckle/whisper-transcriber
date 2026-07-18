# Instructions for Claude

This repo is a local audio transcription app. A user has likely just cloned it
and asked you to set it up and run it. Here is everything you need.

## What this is

A Python server (standard library only) that serves a single HTML page. The page
accepts audio files; the server converts them with `ffmpeg` and transcribes them
with `whisper.cpp` running locally on the user's hardware. No API keys, no
network calls, no cloud services. Do not add any.

## Setting it up

Run `./setup.sh`. It is idempotent — safe to run again if you are unsure of the
state. It installs `ffmpeg` and `whisper-cpp` via the system package manager and
downloads the model (~1.6GB) to `~/.cache/whisper-models/`.

Before running it, tell the user about the 1.6GB download and get a yes. It is a
large file and they may be tethered or metered.

If `setup.sh` fails, these are the pieces it is trying to put in place:

1. **ffmpeg** on `PATH` — `brew install ffmpeg`, `apt-get install ffmpeg`
2. **whisper.cpp** on `PATH` as `whisper-cli` — `brew install whisper-cpp` on
   macOS. On Linux there is no package; build from source:
   ```bash
   git clone https://github.com/ggerganov/whisper.cpp
   cd whisper.cpp && cmake -B build && cmake --build build -j --config Release
   ```
   then put the resulting `whisper-cli` binary on `PATH`.
3. **The model** at `~/.cache/whisper-models/ggml-large-v3-turbo.bin`, from
   `https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-large-v3-turbo.bin`

`python3` must exist but needs no packages — 3.8 or newer is fine.

## Running it

```bash
./run.sh
```

This is a **foreground, long-running server**. Start it in the background rather
than blocking your session on it, then tell the user to open
<http://127.0.0.1:8756> (it also tries to open their browser automatically).

`server.py` runs a preflight check at startup and prints a specific fix for
anything missing, so if it exits immediately, read its output — the answer is
there.

## Verifying it works

Don't just check that the port is listening. Transcribe something:

```bash
say -o /tmp/probe.aiff "The quick brown fox jumps over the lazy dog"   # macOS
curl -s -X POST --data-binary @/tmp/probe.aiff \
     -H "X-Filename: probe.aiff" http://127.0.0.1:8756/upload
# -> {"job": "<id>"}; then poll:
curl -s "http://127.0.0.1:8756/status?job=<id>"
```

Poll until `state` is `done` and confirm `text` contains the sentence.

## Hardware expectations

Roughly 1 minute of processing per 10–15 minutes of audio on Apple Silicon;
slower on Intel or CPU-only Linux. If the user has a weak machine or wants speed
over accuracy, suggest `WHISPER_MODEL=ggml-base.en.bin ./setup.sh` — 140MB and
several times faster, at some cost in accuracy.

## If you are asked to modify this

Keep the constraints that define the project:

- **Standard library only.** No pip installs, no `requirements.txt`, no venv.
  The zero-dependency setup is the whole point.
- **Fully local.** Nothing may call out to a network service at transcription
  time.
- **Serif typography, green and blue palette.** The owner's stated preference.
- **Bare bones.** Resist adding features that weren't asked for.

## Layout

| File | Role |
|---|---|
| `server.py` | HTTP server, job queue, ffmpeg + whisper.cpp orchestration |
| `index.html` | The entire UI — one file, no build step, no framework |
| `setup.sh` | Idempotent dependency + model installer |
| `run.sh` | Runs setup if needed, then starts the server |
| `Transcribe.command` | macOS double-click launcher |

### Endpoints

- `GET /` — the page
- `GET /config` — accepted file extensions
- `POST /upload` — raw audio body, filename in the `X-Filename` header, returns `{"job": id}`
- `GET /status?job=<id>` — `{state, progress, text, error}` where `state` is
  `queued` | `converting` | `transcribing` | `done` | `error`
