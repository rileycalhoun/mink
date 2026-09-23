#!/usr/bin/env bash
# Set up the Mink transcription engine: nemo-speech.cpp + NVIDIA ASR models.
#
# Installs nemo-speech.cpp (if needed), pulls the default transcription model
# and the Sortformer diarization companion, then starts the OpenAI-compatible
# server Mink talks to.
#
# Usage:
#   scripts/setup-engine.sh            # default models, serve on :8000
#   scripts/setup-engine.sh --pull-only # just download models, don't serve
set -euo pipefail

MODEL="${MINK_MODEL:-parakeet-tdt-0.6b-v3}"
DIAR="${MINK_DIAR_MODEL:-sortformer-v2}"
PORT="${MINK_ENGINE_PORT:-8000}"
MODELS_DIR="${MINK_MODELS_DIR:-$HOME/.local/share/mink/models}"

PULL_ONLY=0
for arg in "$@"; do
  case "$arg" in
    --pull-only) PULL_ONLY=1 ;;
    *) echo "Unknown arg: $arg" >&2; exit 1 ;;
  esac
done

if ! command -v nemo-speech >/dev/null 2>&1; then
  echo "nemo-speech not found."
  echo "Install nemo-speech.cpp first: https://github.com/nvidia/nemo-speech.cpp"
  echo "(prebuilt binaries or build from source; needs no Python ML stack)"
  exit 1
fi

mkdir -p "$MODELS_DIR"

echo "==> Pulling transcription model: $MODEL"
nemo-speech pull "$MODEL" --out-dir "$MODELS_DIR"

echo "==> Pulling diarization companion: $DIAR"
# Sortformer v2 GGUF; converted once and reused across ASR models.
python3 "$(dirname "$(command -v nemo-speech)")/../share/nemo-speech/convert_model.py" \
  nvidia/diar_streaming_sortformer_4spk-v2 \
  --outfile "$MODELS_DIR/sortformer-v2-f32.gguf" || true

if [[ "$PULL_ONLY" -eq 1 ]]; then
  echo "Models ready in $MODELS_DIR"
  exit 0
fi

echo "==> Starting engine server on 127.0.0.1:$PORT"
exec nemo-speech serve \
  --model "$MODELS_DIR/$MODEL.gguf" \
  --diar-model "$MODELS_DIR/sortformer-v2-f32.gguf" \
  --host 127.0.0.1 --port "$PORT"
