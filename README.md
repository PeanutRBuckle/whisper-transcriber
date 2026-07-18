# Whisper Transcriber

A bare-bones local app for transcribing audio. Drop in files, get text back.

- **Free.** No API keys, no accounts, no per-minute billing.
- **Private.** Audio never leaves your machine — there is no network call anywhere in the transcription path.
- **Uncapped.** No file size limit, no length limit. Three-hour recordings are fine.
- **Offline.** After setup, it works with the Wi-Fi off.

Transcripts appear in the browser with copy, `.md`, and `.txt` export.

---

## Quick start

```bash
git clone https://github.com/PeanutRBuckle/whisper-transcriber.git
cd whisper-transcriber
./setup.sh     # one time, ~1.6GB model download
./run.sh       # opens your browser
```

On a Mac you can also just double-click **`Transcribe.command`** in Finder — it runs setup on first launch and starts the app every time after.

To stop it, press `Ctrl+C` in the terminal (or close the window).

## Handing this to Claude instead

If you'd rather not touch a terminal, clone the repo and tell Claude Code:

> Set up and run the whisper-transcriber repo in this folder.

The included [`CLAUDE.md`](CLAUDE.md) tells it exactly what to install and how to launch the app.

---

## What gets installed

| Thing | What it does | Size |
|---|---|---|
| [`ffmpeg`](https://ffmpeg.org) | Converts your audio into the format Whisper needs | ~80MB |
| [`whisper.cpp`](https://github.com/ggerganov/whisper.cpp) | Runs the model on your GPU | ~5MB |
| `ggml-large-v3-turbo.bin` | The Whisper model itself | ~1.6GB |

The model lands in `~/.cache/whisper-models/` — outside the repo, so it survives deleting and re-cloning.

Nothing is installed into your system Python. The server is standard library only.

## Supported audio

Anything ffmpeg can read: `mp3`, `m4a`, `wav`, `aac`, `flac`, `ogg`, `opus`, `wma`, `aiff`, plus video containers like `mp4`, `mov`, and `webm` (the audio track is pulled out automatically). Voice Memos and Zoom recordings work as-is.

## Speed

On Apple Silicon, expect roughly **1 minute of processing per 10–15 minutes of audio** — a two-hour recording takes about ten minutes. The page shows live progress and a running estimate. Files are transcribed one at a time so each gets the whole machine.

Older Intel Macs and CPU-only Linux boxes will be meaningfully slower.

## Configuration

Set these as environment variables if the defaults don't suit you:

| Variable | Default | Notes |
|---|---|---|
| `PORT` | `8756` | `PORT=8757 ./run.sh` if something else owns the port |
| `WHISPER_MODEL` | `ggml-large-v3-turbo.bin` | See [other models](https://huggingface.co/ggerganov/whisper.cpp/tree/main) |
| `WHISPER_MODEL_DIR` | `~/.cache/whisper-models` | Where the model lives |

Want it faster and don't mind slightly rougher output? `ggml-base.en.bin` is 140MB and several times quicker — run `WHISPER_MODEL=ggml-base.en.bin ./setup.sh` to fetch it.

## Troubleshooting

**"Setup is incomplete"** — run `./setup.sh`; it prints exactly what's missing.

**Interrupted model download** — re-run `./setup.sh`. It resumes where it left off.

**Port already in use** — `PORT=8757 ./run.sh`.

**macOS won't open `Transcribe.command`** — right-click it, choose *Open*, then confirm once. macOS blocks double-clicked scripts until you approve them.

**Transcript is empty** — usually a file with no speech, or a language the model guessed wrong. Force it with `-l` by editing the `--language` flag in `server.py`.

## License

MIT
