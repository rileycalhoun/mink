#!/usr/bin/env bash
# Set up the Mink transcription engine: nemo-speech.cpp + NVIDIA ASR models.
#
# Pulls the default transcription model and the Sortformer diarization
# companion, then starts the OpenAI-compatible server Mink talks to.
# (Install nemo-speech.cpp first: https://github.com/NVIDIA/NeMo-Speech.cpp —
# prebuilt binaries or build from source; needs no Python ML stack.)
#
# Usage:
#   scripts/setup-engine.sh              # default models, serve on :8000
#   scripts/setup-engine.sh --pull-only  # just download models, don't serve
set -euo pipefail

MODEL="${MINK_MODEL:-parakeet-tdt}"
DIAR="${MINK_DIAR_MODEL:-sortformer}"
PORT="${MINK_ENGINE_PORT:-8000}"

PULL_ONLY=0
for arg in "$@"; do
  case "$arg" in
    --pull-only) PULL_ONLY=1 ;;
    *) echo "Unknown arg: $arg" >&2; exit 1 ;;
  esac
done

if ! command -v nemo-speech >/dev/null 2>&1; then
  echo "nemo-speech not found."
  echo "Install it first: https://github.com/NVIDIA/NeMo-Speech.cpp"
  exit 1
fi

echo "==> Pulling transcription model: $MODEL"
nemo-speech pull "$MODEL"

echo "==> Pulling diarization companion: $DIAR"
nemo-speech pull "$DIAR"

if [[ "$PULL_ONLY" -eq 1 ]]; then
  echo "Models ready (see: nemo-speech model list)"
  exit 0
fi

echo "==> Starting engine server on 127.0.0.1:$PORT"
exec nemo-speech serve \
  --asr-model "$MODEL" \
  --diar-model "$DIAR" \
  --host 127.0.0.1 --port "$PORT" \
  --no-ui
