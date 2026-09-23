# Mink architecture

Mink is an open-source alternative to Otter.ai for classrooms: record a
lecture, get a speaker-labeled, timestamped, searchable transcript.

## Components

```
┌─────────────┐     ┌──────────────────┐     ┌─────────────────────┐
│ mink capture│────▶│ nemo-speech.cpp  │────▶│ mink pipeline/store │
│ (mic → WAV) │     │ (Parakeet ASR +  │     │ (sessions, search)  │
└─────────────┘     │  Sortformer      │     └─────────┬───────────┘
                    │  diarization)    │               │
                    └──────────────────┘               ▼
                                              ┌───────────────┐
                                              │ mink web (API)│
                                              │ mink cli      │
                                              └───────────────┘
```

### 1. Capture (`mink/capture`)

Records 16 kHz mono WAV from the default input device via `sounddevice`.
Chunking is unnecessary — the engine transcribes long files in one pass
(Parakeet handles tens of minutes per segment; the server streams).

Future: system-audio loopback (for recorded Zoom/Meet lectures) and a
browser-based recorder.

### 2. Transcription engine (external: `nemo-speech.cpp`)

Mink does **not** bundle ML inference. It talks to a local
`nemo-speech.cpp` server over its OpenAI-compatible
`POST /v1/audio/transcriptions` endpoint. The server runs NVIDIA's
Parakeet / Nemotron ASR models as GGUFs — no PyTorch, no NeMo install.

Model roles:

| Role | Model | Notes |
|---|---|---|
| File transcription (default) | `parakeet-tdt-0.6b-v3` | 0.6B TDT, self-punctuating, word timestamps, 25 languages |
| File transcription (EN, streaming-capable) | `parakeet-ctc-1.1b` | 1.1B CTC, needs PnC companion for punctuation |
| Live lecture | `nemotron-speech-streaming-en-0.6b` | cache-aware streaming RNNT |
| Multilingual live | `nemotron-3.5` | 40+ locales, prompt-conditioned |
| Speaker diarization | `sortformer-v2` | up to 4 speakers, streaming-capable |

Diarization is a companion GGUF loaded alongside the ASR model; segments
come back with speaker tags (`SPEAKER_00`, …). The CLI later maps these to
"Instructor" / "Student" heuristics.

### 3. Pipeline (`mink/pipeline`)

`LectureSession` is the unit of work: one audio file + one transcript,
persisted as JSON under `~/.local/share/mink/sessions/`. `SessionStore`
provides listing and full-text search over transcripts.

### 4. Interfaces

- **CLI** (`mink`): `record`, `transcribe`, `sessions`, `search`, `show`,
  `serve`, `devices`, `models`, `engine-status`.
- **Web API** (`mink serve`): FastAPI JSON API for sessions, search, and
  audio upload. An HTML UI is a future milestone.

## Roadmap

1. HTML UI (session list, transcript view with speaker colors, search).
2. Live transcription view (streaming model → websocket).
3. Summaries & chapter detection (local LLM pass over the transcript).
4. Export: Markdown, PDF, SRT/VTT captions.
5. Slide/whiteboard capture alongside audio.
6. Multi-device: phone as remote mic.

## Licensing notes

- Mink's code: Apache-2.0.
- NVIDIA model weights (Parakeet, Nemotron, Sortformer): CC-BY-4.0.
  They are downloaded at setup time and never redistributed here;
  attribution to NVIDIA is required when distributing them.
