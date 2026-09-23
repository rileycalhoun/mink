# Mink architecture

Mink is an open-source alternative to Otter.ai for classrooms: record a
lecture, get a speaker-labeled, timestamped, searchable transcript — plus
AI summaries. Runs fully local: audio never leaves the machine (LLM calls
go to whatever provider you configure, local by default).

## Components

```
┌─────────────┐     ┌──────────────────┐     ┌─────────────────────┐
│ capture /   │────▶│ nemo-speech.cpp  │────▶│ pipeline            │
│ browser mic │     │ (Parakeet ASR +  │     │ (sessions, search,  │
│ (16k PCM)   │     │  Sortformer      │     │  export)            │
└─────────────┘     │  diarization)    │     └─────────┬───────────┘
                    └──────────────────┘               │
┌─────────────┐                                       ▼
│ mink/llm    │◀────────────────────────────┌─────────────────────┐
│ (Ollama /   │   summaries, future LLM     │ web (FastAPI + WS)  │
│  OpenAI)    │   features                  │ SvelteKit UI        │
└─────────────┘                             └─────────────────────┘
```

### 1. Capture (`mink/capture`) and browser mic

- CLI: records 16 kHz mono WAV via `sounddevice`.
- Web live view: the browser captures mic audio with an AudioWorklet,
  downsamples to 16 kHz mono Int16 PCM, and streams binary frames over
  the WebSocket. No ffmpeg needed in the browser path.

### 2. Transcription engine (external: `nemo-speech.cpp`)

Mink does **not** bundle ML inference. It talks to a local
`nemo-speech.cpp` server over its OpenAI-compatible
`POST /v1/audio/transcriptions` endpoint (`mink/engine/client.py`).

Model roles (`mink/engine/models.py`):

| Role | Model | Notes |
|---|---|---|
| File transcription (default) | `parakeet-tdt-0.6b-v3` | 0.6B TDT, self-punctuating, word timestamps, 25 languages |
| Live windows | `parakeet-ctc-1.1b` | fast CTC; final pass re-runs with the default model |
| Live (alt) | `nemotron-speech-streaming-en-0.6b` | cache-aware streaming RNNT |
| Diarization | `sortformer-v2` | up to 4 speakers, applied on the final pass |

### 3. Live transcription (`mink/pipeline/live.py`, `WS /api/live/ws`)

Chunked design over the engine's stateless HTTP API:

- Browser sends PCM frames; backend accumulates into 12 s windows with
  3 s overlap (`MINK_LIVE_WINDOW_SECONDS` / `MINK_LIVE_OVERLAP_SECONDS`).
- Silent windows (RMS < `MINK_LIVE_SILENCE_RMS`) skip the engine call.
- Overlap deduplication: segments starting inside the overlapped head are
  dropped (except window 0), so repeated audio isn't shown twice.
- On `stop`: the full recording is saved as WAV and a final diarized
  pass with the default model produces the canonical transcript.

WebSocket protocol:

```
C → S {"type": "start", "title"?, "course"?, "model"?}
S → C {"type": "started", "session_id"}
C → S <binary PCM16 16kHz mono>
S → C {"type": "partial", "segments": [{start, end, text}], "text", "duration"}
C → S {"type": "stop"}
S → C {"type": "finalizing"}
S → C {"type": "done", "session_id"} | {"type": "error", "message"}
```

### 4. LLM layer (`mink/llm/`)

The single seam for all language-model use. `LLMProvider` is a Protocol
with `complete()` / `available()`; implementations speak plain HTTP —
no vendor SDKs.

- `ollama` — local via Ollama `/api/chat` (default; fully offline)
- `openai` — any OpenAI-compatible `/chat/completions` endpoint
  (OpenAI, vLLM, LM Studio, …)
- `none` — LLM features disabled with a clear error

Settings: `MINK_LLM_PROVIDER`, `MINK_LLM_MODEL` (default `llama3.1`),
`MINK_LLM_BASE_URL`, `MINK_LLM_API_KEY`. `provider_status()` feeds
`/api/health` so the UI can show LLM availability.

Current LLM feature: **summaries** (`mink/llm/summarize.py`) — TL;DR,
timestamped chapters, key points, action items, glossary. Stored as JSON
on the session; `mink summarize <id>` or `POST /api/sessions/{id}/summary`.

### 5. Pipeline (`mink/pipeline`)

`LectureSession` is the unit of work: audio + transcript + optional
summary, persisted as JSON under `~/.local/share/mink/sessions/`.
`SessionStore` lists and full-text searches. `export.py` renders
Markdown / TXT / SRT / VTT.

### 6. Interfaces

- **CLI** (`mink`): `record`, `transcribe`, `sessions`, `search`, `show`,
  `summarize`, `export`, `serve`, `devices`, `models`, `engine-status`.
- **Web API** (`mink serve`): REST under `/api/*` + live WebSocket.
- **Web UI**: SvelteKit app in `mink/web/ui/`, statically built to
  `mink/web/static/` and served by FastAPI with SPA fallback.
  Build: `cd mink/web/ui && npm install && npm run build`.

## Roadmap

- [x] HTML UI (library, transcript view, search)
- [x] Live transcription view (WebSocket + chunked engine calls)
- [x] Summaries via local LLM
- [ ] Q&A over a lecture ("ask this lecture") via `mink/llm`
- [ ] Flashcards / quiz generation
- [ ] Slide/whiteboard capture alongside audio
- [ ] Multi-device: phone as remote mic

## Licensing notes

- Mink's code: Apache-2.0.
- NVIDIA model weights (Parakeet, Nemotron, Sortformer): CC-BY-4.0.
  They are downloaded at setup time and never redistributed here;
  attribution to NVIDIA is required when distributing them.
