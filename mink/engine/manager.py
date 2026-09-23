"""On-demand transcription engine lifecycle.

The GPU pod only exists while it's actually being used:

* ``start()`` picks the cheapest RunPod GPU with current capacity, creates a
  pod, and waits (in the background) until the engine's ``/health`` responds.
* Every transcription bumps a last-used timestamp.
* A watcher thread terminates the pod after ``MINK_RUNPOD_IDLE_MINUTES`` of
  inactivity — terminate, not stop, so there is zero residual cost.
* The pod's engine requires a bearer token (``nemo-speech serve --api-key``);
  the token is generated per pod, persisted root-only in the data dir so a
  web restart can re-adopt a live pod, and never logged.

Without ``MINK_RUNPOD_API_KEY`` the manager stays dormant and Mink behaves
exactly as before (static ``MINK_ENGINE_URL``).
"""

from __future__ import annotations

import json
import os
import secrets
import threading
import time
from enum import Enum

import httpx

from mink.cloud.runpod import RunPodClient, RunPodError
from mink.config import settings

POD_NAME = "mink-engine"
ENGINE_PORT = 8000
# Poll cadence / timeouts.
_POD_POLL_S = 10
_HEALTH_POLL_S = 10
_START_TIMEOUT_S = 15 * 60
_IDLE_CHECK_S = 30

# Slim CUDA runtime image: the nemo-speech.cpp prebuilt CUDA archive bundles
# the user-space CUDA libs it needs, so no PyTorch image is required.
ENGINE_IMAGE = "nvidia/cuda:12.4.1-runtime-ubuntu22.04"


class EngineState(str, Enum):
    OFF = "off"
    PROVISIONING = "provisioning"
    READY = "ready"
    ERROR = "error"


def _boot_script() -> str:
    """Bash run as the pod entrypoint: install, pull models, serve."""
    return r"""set -e
export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
apt-get install -y -qq curl ca-certificates
echo "[mink] installing nemo-speech.cpp"
curl -fsSL https://github.com/NVIDIA/NeMo-Speech.cpp/raw/main/scripts/install.sh | sh
export PATH="$HOME/.local/bin:$PATH"
echo "[mink] pulling models"
nemo-speech pull parakeet-tdt
nemo-speech pull sortformer
echo "[mink] starting engine on :8000"
exec nemo-speech serve \
  --asr-model parakeet-tdt \
  --diar-model sortformer \
  --host 0.0.0.0 --port 8000 \
  --no-ui \
  --api-key "$NEMO_API_KEY"
"""


class EngineManager:
    """Owns the on-demand engine pod. Thread-safe; one process-wide instance."""

    def __init__(self) -> None:
        # RLock: status() is called from inside locked regions (e.g. start()).
        self._lock = threading.RLock()
        self._state = EngineState.OFF
        self._pod_id: str | None = None
        self._gpu_id: str | None = None
        self._price_per_hr: float | None = None
        self._api_key: str | None = None
        self._error: str | None = None
        self._started_at: float | None = None
        self._last_used: float | None = None
        self._worker: threading.Thread | None = None
        self._idle_thread: threading.Thread | None = None

    # ------------------------------------------------------------------
    # properties
    # ------------------------------------------------------------------

    @property
    def configured(self) -> bool:
        return bool(settings.runpod_api_key)

    @property
    def state(self) -> EngineState:
        with self._lock:
            return self._state

    @property
    def api_key(self) -> str | None:
        """Bearer token for the current pod's engine, if any."""
        with self._lock:
            return self._api_key if self._state is EngineState.READY else None

    @property
    def engine_url(self) -> str:
        """Pod proxy URL while ready, else the static configured URL."""
        with self._lock:
            if self._state is EngineState.READY and self._pod_id:
                return f"https://{self._pod_id}-{ENGINE_PORT}.proxy.runpod.net"
            return settings.engine_url

    def status(self) -> dict:
        with self._lock:
            now = time.time()
            return {
                "state": self._state.value,
                "configured": self.configured,
                "pod_id": self._pod_id,
                "gpu": self._gpu_id,
                "price_per_hr": self._price_per_hr,
                "engine_url": self.engine_url
                if self._state is EngineState.READY
                else settings.engine_url,
                "uptime_s": round(now - self._started_at) if self._started_at else None,
                "idle_s": round(now - self._last_used)
                if self._last_used and self._state is EngineState.READY
                else None,
                "idle_timeout_s": settings.runpod_idle_minutes * 60,
                "error": self._error,
            }

    # ------------------------------------------------------------------
    # lifecycle
    # ------------------------------------------------------------------

    def _client(self) -> RunPodClient:
        assert settings.runpod_api_key, "RunPod not configured"
        return RunPodClient(settings.runpod_api_key)

    def start(self) -> dict:
        """Begin provisioning; idempotent. Returns the current status."""
        with self._lock:
            if not self.configured:
                raise RunPodError("RunPod is not configured (set MINK_RUNPOD_API_KEY)")
            if self._state is EngineState.READY:
                return self.status()
            if self._state is EngineState.PROVISIONING:
                return self.status()
            self._error = None
            self._state = EngineState.PROVISIONING

        try:
            client = self._client()
            gpu_id, price = client.cheapest_gpu()
            api_key = secrets.token_urlsafe(32)
            body = {
                "name": POD_NAME,
                "cloud": "COMMUNITY",
                "gpu": {"id": gpu_id, "count": 1},
                "image": ENGINE_IMAGE,
                "ports": [f"{ENGINE_PORT}/http"],
                "disk": 20,
                "env": {"NEMO_API_KEY": api_key},
                "entrypoint": ["/bin/bash", "-c", _boot_script()],
            }
            pod = client.create_pod(body)
            pod_id = pod.get("id")
            if not pod_id:
                raise RunPodError(f"Pod creation returned no id: {pod}")
        except Exception as exc:  # noqa: BLE001 — surface as ERROR state
            with self._lock:
                self._state = EngineState.ERROR
                self._error = str(exc)
            return self.status()

        with self._lock:
            self._pod_id = pod_id
            self._gpu_id = gpu_id
            self._price_per_hr = price
            self._api_key = api_key
            self._started_at = time.time()
            self._last_used = time.time()
        self._persist_key()
        self._ensure_worker(self._provision_worker)
        self._ensure_idle_watcher()
        return self.status()

    def stop(self) -> dict:
        """Terminate the pod immediately. Idempotent."""
        with self._lock:
            pod_id = self._pod_id
            self._pod_id = None
            self._gpu_id = None
            self._price_per_hr = None
            self._api_key = None
            self._started_at = None
            self._last_used = None
            self._state = EngineState.OFF
            self._error = None
        self._clear_key()
        if pod_id and self.configured:
            try:
                self._client().terminate_pod(pod_id)
            except RunPodError:
                pass  # already gone; nothing to bill
        return self.status()

    def touch(self) -> None:
        """Mark the engine as used (called on every transcription)."""
        with self._lock:
            if self._state is EngineState.READY:
                self._last_used = time.time()

    def reconcile(self) -> None:
        """Adopt a live pod from a previous process, else start clean.

        Called once at web startup. A previous manager's pod is only adopted
        when its bearer token was persisted; otherwise it is terminated so a
        crashed process can never leave a GPU billing silently.
        """
        if not self.configured:
            return
        try:
            client = self._client()
            pods = [
                p
                for p in client.list_pods()
                if p.get("name") == POD_NAME and p.get("status") == "RUNNING"
            ]
        except RunPodError:
            return
        if not pods:
            return
        saved = self._load_key()
        pod = max(pods, key=lambda p: p.get("uptimeInSeconds", 0) or 0)
        # Terminate strays we cannot authenticate to.
        for p in pods:
            if p.get("id") != pod.get("id"):
                try:
                    client.terminate_pod(p["id"])
                except RunPodError:
                    pass
        if saved and saved.get("pod_id") == pod.get("id"):
            with self._lock:
                self._pod_id = pod["id"]
                self._api_key = saved["api_key"]
                self._gpu_id = (pod.get("gpu") or {}).get("id") or pod.get("machineId")
                self._started_at = time.time() - (pod.get("uptimeInSeconds", 0) or 0)
                self._last_used = time.time()
                self._state = EngineState.PROVISIONING
            self._ensure_worker(self._health_worker)
            self._ensure_idle_watcher()
        else:
            try:
                client.terminate_pod(pod["id"])
            except RunPodError:
                pass

    # ------------------------------------------------------------------
    # background workers
    # ------------------------------------------------------------------

    def _ensure_worker(self, target) -> None:
        with self._lock:
            if self._worker and self._worker.is_alive():
                return
            self._worker = threading.Thread(target=target, daemon=True)
            self._worker.start()

    def _ensure_idle_watcher(self) -> None:
        with self._lock:
            if self._idle_thread and self._idle_thread.is_alive():
                return
            self._idle_thread = threading.Thread(target=self._idle_worker, daemon=True)
            self._idle_thread.start()

    def _provision_worker(self) -> None:
        """Wait for the pod to run, then for the engine to answer /health."""
        deadline = time.time() + _START_TIMEOUT_S
        try:
            client = self._client()
            while time.time() < deadline:
                with self._lock:
                    pod_id = self._pod_id
                    if self._state is not EngineState.PROVISIONING:
                        return
                pod = client.get_pod(pod_id or "")
                if pod.get("status") == "RUNNING":
                    break
                if pod.get("status") in ("TERMINATED", "EXITED", "FAILED"):
                    raise RunPodError(f"Pod entered {pod.get('status')}")
                time.sleep(_POD_POLL_S)
            else:
                raise RunPodError("Timed out waiting for the pod to start")
            self._wait_healthy(deadline)
            with self._lock:
                self._state = EngineState.READY
                self._last_used = time.time()
        except Exception as exc:  # noqa: BLE001 — ERROR state carries the message
            with self._lock:
                if self._state is EngineState.PROVISIONING:
                    self._state = EngineState.ERROR
                    self._error = str(exc)

    def _health_worker(self) -> None:
        """Adopted pod: just verify the engine is healthy."""
        try:
            self._wait_healthy(time.time() + _START_TIMEOUT_S)
            with self._lock:
                self._state = EngineState.READY
                self._last_used = time.time()
        except Exception as exc:  # noqa: BLE001
            with self._lock:
                if self._state is EngineState.PROVISIONING:
                    self._state = EngineState.ERROR
                    self._error = str(exc)

    def _wait_healthy(self, deadline: float) -> None:
        while time.time() < deadline:
            with self._lock:
                pod_id = self._pod_id
                api_key = self._api_key
                if self._state is not EngineState.PROVISIONING:
                    raise RunPodError("Startup cancelled")
            url = f"https://{pod_id}-{ENGINE_PORT}.proxy.runpod.net/health"
            try:
                resp = httpx.get(
                    url,
                    headers={"Authorization": f"Bearer {api_key}"},
                    timeout=10.0,
                    trust_env=False,
                )
                if resp.status_code < 500:
                    return
            except httpx.HTTPError:
                pass
            time.sleep(_HEALTH_POLL_S)
        raise RunPodError("Timed out waiting for the engine to become healthy")

    def _idle_worker(self) -> None:
        """Terminate the pod after the idle timeout. Runs for the process life."""
        while True:
            time.sleep(_IDLE_CHECK_S)
            timeout_s = settings.runpod_idle_minutes * 60
            with self._lock:
                idle = (
                    timeout_s > 0
                    and self._state is EngineState.READY
                    and self._last_used is not None
                    and time.time() - self._last_used > timeout_s
                )
            if idle:
                self.stop()

    # ------------------------------------------------------------------
    # persisted bearer token (re-adopt across web restarts)
    # ------------------------------------------------------------------

    def _key_path(self):
        return settings.data_dir / "engine-key.json"

    def _persist_key(self) -> None:
        try:
            path = self._key_path()
            path.parent.mkdir(parents=True, exist_ok=True)
            with self._lock:
                payload = {"pod_id": self._pod_id, "api_key": self._api_key}
            path.write_text(json.dumps(payload))
            os.chmod(path, 0o600)
        except OSError:
            pass

    def _load_key(self) -> dict | None:
        try:
            return json.loads(self._key_path().read_text())
        except (OSError, ValueError):
            return None

    def _clear_key(self) -> None:
        try:
            self._key_path().unlink(missing_ok=True)
        except OSError:
            pass


engine_manager = EngineManager()
