# Mink

Open-source lecture recording and transcription — an open alternative to
Otter.ai, built for classrooms.

Record a lecture, get a speaker-labeled, timestamped, searchable transcript.
Runs fully local: your audio never leaves your machine.

## How it works

Mink pairs a small Python app (capture, sessions, search, API) with
NVIDIA's speech models for transcription:

- **ASR**: [Parakeet](https://huggingface.co/nvidia/parakeet-tdt-0.6b-v3)
  (`parakeet-tdt-0.6b-v3`) — fast, accurate, self-punctuating transcription
  with word-level timestamps, served locally by
  [nemo-speech.cpp](https://github.com/nvidia/nemo-speech.cpp).
- **Live mode**: `nemotron-speech-streaming-en-0.6b` for real-time lecture
  transcription.
- **Diarization**: Sortformer v2 — speaker labels for instructor vs.
  student questions.

See [docs/architecture.md](docs/architecture.md) for the full design.

## Quickstart

```bash
# 1. Install Mink
pip install -e '.[capture]'

# 2. Set up the transcription engine (downloads models, starts server)
scripts/setup-engine.sh

# 3. Record a lecture (Ctrl-C to stop)
mink record --course "CS 101" --title "Lecture 1: Intro"

# ...or transcribe an existing file
mink transcribe lecture.wav --course "CS 101"

# 4. Read it back
mink sessions
mink show <session-id>
mink search "recursion"

# 5. Web API
mink serve  # http://127.0.0.1:8473
```

Check the engine first if anything fails:

```bash
mink engine-status
mink models
```

## Configuration

All settings are environment variables prefixed with `MINK_`:

| Variable | Default | Purpose |
|---|---|---|
| `MINK_ENGINE_URL` | `http://127.0.0.1:8000` | nemo-speech.cpp server |
| `MINK_DEFAULT_MODEL` | `parakeet-tdt-0.6b-v3` | transcription model |
| `MINK_DATA_DIR` | `~/.local/share/mink` | sessions + audio |
| `MINK_WEB_PORT` | `8473` | `mink serve` port |

## Project layout

```
mink/
├── mink/
│   ├── cli.py            # `mink` command line
│   ├── config.py         # settings (env-overridable)
│   ├── engine/           # client for nemo-speech.cpp + model catalog
│   ├── capture/          # microphone recording
│   ├── pipeline/         # lecture sessions, transcript store + search
│   └── web/              # FastAPI service
├── scripts/setup-engine.sh
├── docs/architecture.md
└── tests/
```

## License

Apache-2.0 — see [LICENSE](LICENSE).

Note: the NVIDIA model weights downloaded by `setup-engine.sh`
(Parakeet, Nemotron, Sortformer) are published by NVIDIA under
**CC-BY-4.0**. They are fetched at setup time, never redistributed with
this repository.
