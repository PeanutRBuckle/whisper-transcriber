#!/usr/bin/env bash
#
# One-time setup: installs ffmpeg + whisper.cpp and downloads the model.
# Safe to re-run -- it skips anything already in place.

set -euo pipefail

MODEL_DIR="${WHISPER_MODEL_DIR:-$HOME/.cache/whisper-models}"
MODEL_NAME="${WHISPER_MODEL:-ggml-large-v3-turbo.bin}"
MODEL_URL="https://huggingface.co/ggerganov/whisper.cpp/resolve/main/${MODEL_NAME}"

say() { printf "\n  %s\n" "$1"; }

say "Whisper Transcriber setup"

# ---- ffmpeg + whisper.cpp -------------------------------------------------

need_ffmpeg=false
need_whisper=false

command -v ffmpeg >/dev/null 2>&1 || need_ffmpeg=true
if ! command -v whisper-cli >/dev/null 2>&1 \
   && ! command -v whisper-cpp >/dev/null 2>&1; then
  need_whisper=true
fi

if [ "$need_ffmpeg" = true ] || [ "$need_whisper" = true ]; then
  if command -v brew >/dev/null 2>&1; then
    [ "$need_ffmpeg" = true ]  && { say "Installing ffmpeg..."; brew install ffmpeg; }
    [ "$need_whisper" = true ] && { say "Installing whisper.cpp..."; brew install whisper-cpp; }
  elif command -v apt-get >/dev/null 2>&1; then
    say "Installing ffmpeg via apt (whisper.cpp must be built from source on Linux)..."
    sudo apt-get update && sudo apt-get install -y ffmpeg
    [ "$need_whisper" = true ] && {
      say "Build whisper.cpp yourself, then put 'whisper-cli' on your PATH:"
      echo "     git clone https://github.com/ggerganov/whisper.cpp"
      echo "     cd whisper.cpp && cmake -B build && cmake --build build -j --config Release"
      exit 1
    }
  else
    say "No package manager found. Install these two yourself, then re-run:"
    echo "     - ffmpeg        https://ffmpeg.org/download.html"
    echo "     - whisper.cpp   https://github.com/ggerganov/whisper.cpp"
    exit 1
  fi
else
  say "ffmpeg and whisper.cpp are already installed."
fi

# ---- model ----------------------------------------------------------------

mkdir -p "$MODEL_DIR"
MODEL_PATH="$MODEL_DIR/$MODEL_NAME"

if [ -f "$MODEL_PATH" ] && [ "$(wc -c < "$MODEL_PATH")" -gt 100000000 ]; then
  say "Model already downloaded: $MODEL_PATH"
else
  say "Downloading $MODEL_NAME (~1.6GB, one time only)..."
  # -C - resumes a partial download if this was interrupted before.
  curl -L -C - --fail --progress-bar -o "$MODEL_PATH" "$MODEL_URL"
fi

say "Setup complete. Start the app with:  ./run.sh"
echo
