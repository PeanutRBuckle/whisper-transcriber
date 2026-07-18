#!/usr/bin/env python3
"""
Local Whisper transcription server.

Serves a single page at http://127.0.0.1:8756 that accepts audio files,
converts them with ffmpeg, transcribes them with whisper.cpp, and returns
the text. Everything runs on this machine. Nothing is uploaded anywhere.

Standard library only -- no pip install required.
"""

import http.server
import json
import os
import re
import shutil
import socketserver
import subprocess
import sys
import tempfile
import threading
import time
import uuid
import webbrowser
from pathlib import Path
from urllib.parse import urlparse, parse_qs

PORT = int(os.environ.get("PORT", "8756"))
HERE = Path(__file__).resolve().parent
MODEL_DIR = Path(os.environ.get("WHISPER_MODEL_DIR", Path.home() / ".cache" / "whisper-models"))
MODEL_NAME = os.environ.get("WHISPER_MODEL", "ggml-large-v3-turbo.bin")

# Audio containers ffmpeg will happily decode. Anything else we still try --
# this list only drives the file picker's filter.
AUDIO_EXTS = [".mp3", ".m4a", ".wav", ".aac", ".flac", ".ogg", ".opus",
              ".mp4", ".mov", ".m4v", ".webm", ".aiff", ".aif", ".wma"]

JOBS = {}
JOBS_LOCK = threading.Lock()


def find_whisper():
    """whisper.cpp has renamed its CLI over time; accept any of the names."""
    for name in ("whisper-cli", "whisper-cpp", "whisper"):
        path = shutil.which(name)
        if path:
            return path
    return None


def model_path():
    return MODEL_DIR / MODEL_NAME


def preflight():
    """Fail loudly at startup rather than mysteriously on the first upload."""
    problems = []
    if not shutil.which("ffmpeg"):
        problems.append(
            "ffmpeg is not installed.\n"
            "    Fix: brew install ffmpeg"
        )
    if not find_whisper():
        problems.append(
            "whisper.cpp is not installed.\n"
            "    Fix: brew install whisper-cpp"
        )
    if not model_path().exists():
        problems.append(
            "The Whisper model file is missing:\n"
            "      {}\n"
            "    Fix: ./setup.sh   (downloads it once, ~1.6GB)".format(model_path())
        )
    return problems


def already_ours():
    """True if the thing holding our port is another copy of this app."""
    try:
        import urllib.request
        with urllib.request.urlopen(
            "http://127.0.0.1:{}/config".format(PORT), timeout=1.5
        ) as response:
            return "accept" in json.loads(response.read())
    except Exception:  # noqa: BLE001 - any failure just means "not us"
        return False


def set_job(job_id, **fields):
    with JOBS_LOCK:
        JOBS.setdefault(job_id, {}).update(fields)


def get_job(job_id):
    with JOBS_LOCK:
        return dict(JOBS.get(job_id, {}))


def audio_duration(path):
    """Seconds of audio, or None if ffprobe can't tell us."""
    if not shutil.which("ffprobe"):
        return None
    try:
        out = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "default=noprint_wrappers=1:nokey=1", str(path)],
            capture_output=True, text=True, timeout=60,
        )
        return float(out.stdout.strip())
    except (ValueError, subprocess.SubprocessError):
        return None


def transcribe_job(job_id, src_path, workdir):
    """Convert -> transcribe. Runs on a worker thread; updates JOBS as it goes."""
    try:
        duration = audio_duration(src_path)
        set_job(job_id, duration=duration)

        # whisper.cpp requires 16kHz mono 16-bit PCM. ffmpeg gets us there from
        # essentially any container.
        set_job(job_id, state="converting", progress=0)
        wav_path = workdir / "audio.wav"
        conv = subprocess.run(
            ["ffmpeg", "-nostdin", "-y", "-i", str(src_path),
             "-ar", "16000", "-ac", "1", "-c:a", "pcm_s16le", str(wav_path)],
            capture_output=True, text=True,
        )
        if conv.returncode != 0 or not wav_path.exists():
            tail = "\n".join(conv.stderr.strip().splitlines()[-4:])
            set_job(job_id, state="error",
                    error="ffmpeg could not read this file.\n" + tail)
            return

        set_job(job_id, state="transcribing", progress=0)
        cmd = [
            find_whisper(),
            "-m", str(model_path()),
            "-f", str(wav_path),
            "--no-timestamps",
            "--print-progress",
            "--language", "auto",
        ]
        proc = subprocess.Popen(
            cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True, bufsize=1,
        )

        # whisper.cpp writes transcript to stdout and progress to stderr.
        progress_re = re.compile(r"progress\s*=\s*(\d+)%")
        stderr_tail = []

        def watch_stderr():
            for line in proc.stderr:
                match = progress_re.search(line)
                if match:
                    set_job(job_id, progress=int(match.group(1)))
                else:
                    stderr_tail.append(line.rstrip())
                    del stderr_tail[:-12]

        watcher = threading.Thread(target=watch_stderr, daemon=True)
        watcher.start()

        text = proc.stdout.read()
        proc.wait()
        watcher.join(timeout=5)

        if proc.returncode != 0:
            set_job(job_id, state="error",
                    error="whisper.cpp failed.\n" + "\n".join(stderr_tail[-6:]))
            return

        set_job(job_id, state="done", progress=100, text=text.strip())

    except Exception as exc:  # noqa: BLE001 - surface anything to the browser
        set_job(job_id, state="error", error="{}: {}".format(type(exc).__name__, exc))
    finally:
        shutil.rmtree(workdir, ignore_errors=True)


class Handler(http.server.BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, fmt, *args):
        # Default logging is noisy with status polling; stay quiet.
        pass

    def _send(self, code, body, content_type="application/json"):
        if isinstance(body, str):
            body = body.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_json(self, code, obj):
        self._send(code, json.dumps(obj))

    def do_GET(self):
        parsed = urlparse(self.path)

        if parsed.path == "/":
            html = (HERE / "index.html").read_bytes()
            self._send(200, html, "text/html; charset=utf-8")
            return

        if parsed.path == "/config":
            self._send_json(200, {"accept": AUDIO_EXTS})
            return

        if parsed.path == "/status":
            job_id = parse_qs(parsed.query).get("job", [""])[0]
            job = get_job(job_id)
            if not job:
                self._send_json(404, {"error": "unknown job"})
                return
            self._send_json(200, job)
            return

        self._send_json(404, {"error": "not found"})

    def do_POST(self):
        if urlparse(self.path).path != "/upload":
            self._send_json(404, {"error": "not found"})
            return

        filename = self.headers.get("X-Filename", "audio")
        length = int(self.headers.get("Content-Length", "0"))
        if length <= 0:
            self._send_json(400, {"error": "empty upload"})
            return

        # Stream the body to disk in chunks -- these files can be very large and
        # we never want the whole thing resident in memory.
        workdir = Path(tempfile.mkdtemp(prefix="whisper-"))
        suffix = Path(filename).suffix or ".bin"
        src_path = workdir / ("input" + suffix)
        remaining = length
        with open(src_path, "wb") as handle:
            while remaining > 0:
                chunk = self.rfile.read(min(1024 * 1024, remaining))
                if not chunk:
                    break
                handle.write(chunk)
                remaining -= len(chunk)

        job_id = uuid.uuid4().hex
        set_job(job_id, state="queued", progress=0, filename=filename,
                started=time.time())
        threading.Thread(
            target=transcribe_job, args=(job_id, src_path, workdir), daemon=True
        ).start()

        self._send_json(200, {"job": job_id})


class Server(socketserver.ThreadingTCPServer):
    allow_reuse_address = True
    daemon_threads = True


def main():
    problems = preflight()
    if problems:
        print("\n  Setup is incomplete:\n")
        for problem in problems:
            print("  -  " + problem + "\n")
        sys.exit(1)

    # Bind before printing the banner -- otherwise a failed start still tells
    # the user to "Open: http://..." at an address that isn't listening.
    try:
        server = Server(("127.0.0.1", PORT), Handler)
    except OSError as exc:
        print("\n  Port {} is already in use.\n".format(PORT))
        if already_ours():
            print("  It looks like Whisper Transcriber is already running.")
            print("  Just open:  http://127.0.0.1:{}\n".format(PORT))
        else:
            print("  ({})".format(exc))
            print("  Another program has it. Start on a different port with:\n")
            print("      PORT=8757 {}\n".format(HERE / "run.sh"))
        sys.exit(1)

    url = "http://127.0.0.1:{}".format(PORT)
    print("\n  Whisper Transcriber")
    print("  Model:  {}".format(model_path().name))
    print("  Open:   {}".format(url))
    print("\n  Everything runs locally. Press Ctrl+C to stop.\n")

    threading.Timer(0.6, lambda: webbrowser.open(url)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n  Stopped.\n")


if __name__ == "__main__":
    main()
