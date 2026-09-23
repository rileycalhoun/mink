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

# 5. Web UI (Svelte)
mink serve  # http://127.0.0.1:8473
```

The UI is a SvelteKit app in `mink/web/ui/`. Build it once:

```bash
cd mink/web/ui && npm install && npm run build
```

`mink serve` then serves the app itself from `/` (API stays under `/api/*`).
Pages: library with search, live transcription view, session detail with
audio-synced transcript, summaries, and export (Markdown / TXT / SRT / VTT).

## Live transcription

Open the web UI and hit **Live record**, or stream 16 kHz mono Int16 PCM
over `ws://127.0.0.1:8473/api/live/ws`:

```
→ {"type": "start", "title": "Lecture 1", "course": "CS 101"}
← {"type": "started", "session_id": "…"}
→ <binary PCM frames>
← {"type": "partial", "segments": [{"start": 0.0, "end": 3.2, "text": "…"}], …}
→ {"type": "stop"}
← {"type": "finalizing"}
← {"type": "done", "session_id": "…"}
```

Live windows are transcribed in 12 s overlapping chunks; stopping runs a
full diarized pass with the default model to produce the final transcript.

## Summaries (LLM)

Summaries run through `mink/llm`, a provider abstraction so future LLM
features (Q&A, flashcards) plug into one seam — no vendor SDKs in app code.

| `MINK_LLM_PROVIDER` | Backend |
|---|---|
| `ollama` (default) | Local Ollama at `http://127.0.0.1:11434` |
| `openai` | Any OpenAI-compatible `/chat/completions` endpoint |
| `none` | LLM features disabled |

```bash
export MINK_LLM_MODEL=llama3.1        # default
export MINK_LLM_BASE_URL=…            # override per provider
export MINK_LLM_API_KEY=…             # for hosted endpoints

mink summarize <session-id>           # CLI
```

Or hit **Generate summary** in the UI. `/api/health` reports LLM
reachability so the UI can reflect it.

## Summary verification (Jev)

After a summary is generated, Mink can ask [Jev](https://typesafe.ai)
(TypeSafe SystemOne) typed questions about it *against the source
transcript* — one fast parallel pass, no generated prose. This is a
separate seam from the generative LLM in `mink/llm`: the LLM writes
summaries, Jev verifies them. The gate asks:

- **faithfulness** (Choice) — every claim grounded in the transcript?
- **quality** (Score 0–4) — how good a study aid is the summary?
- **action_items** (Noul) — do the action items correspond to real
  assignments mentioned in the transcript?

The verdict (`faithful` / `minor_drift` / `unfaithful`, confidence, quality
score) is stored under `summary["verdict"]` and shown as a badge in the UI.
If any check looks bad, the verdict recommends a human review.

Opt-in: the gate stays off until you set a TypeSafe key — Mink is fully
local by default.

```bash
export MINK_JEV_API_KEY=<your TypeSafe API key>

mink verdict <session-id>            # verify an existing summary
```

`mink summarize <session-id>` and `POST /api/sessions/{id}/summary` also
run the gate automatically when a key is configured. `/api/health` reports
decision-provider reachability under `decision`.

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
| `MINK_RUNPOD_API_KEY` | _(unset)_ | enables the on-demand cloud engine |
| `MINK_RUNPOD_IDLE_MINUTES` | `20` | terminate the GPU pod after N idle minutes (`0` = never) |

## On-demand cloud engine

No local GPU? Set `MINK_RUNPOD_API_KEY` and the engine pill in the web UI
becomes a start/stop control: it spins up the cheapest RunPod GPU with
current capacity, waits for the engine to become healthy, and terminates the
pod after `MINK_RUNPOD_IDLE_MINUTES` of inactivity — so you only pay for the
minutes you transcribe. The pod's engine requires a per-pod bearer token,
generated at start time and never stored in the repo.

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
