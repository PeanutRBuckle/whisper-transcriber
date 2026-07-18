#!/usr/bin/env bash
# Starts the transcriber. Runs setup automatically the first time.
set -euo pipefail

cd "$(dirname "$0")"

MODEL_DIR="${WHISPER_MODEL_DIR:-$HOME/.cache/whisper-models}"
MODEL_NAME="${WHISPER_MODEL:-ggml-large-v3-turbo.bin}"

if [ ! -f "$MODEL_DIR/$MODEL_NAME" ]; then
  printf "\n  First run -- setting things up.\n"
  ./setup.sh
fi

exec python3 server.py
