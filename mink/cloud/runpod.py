"""Minimal RunPod REST client for on-demand engine pods.

Only the calls the engine manager needs: GPU catalog (cheapest available),
pod CRUD, status, and logs. Uses the v2 REST API
(``https://docs.runpod.io/api-reference``).
"""

from __future__ import annotations

import contextlib

import httpx

API_BASE = "https://api.runpod.io"

# Cloudflare sits in front of api.runpod.io and 403s requests with a
# non-browser User-Agent (error 1010). Identify as a browser.
_USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0 Safari/537.36"
)


class RunPodError(RuntimeError):
    """A RunPod API call failed."""

    def __init__(self, message: str, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code


def _is_cuda_gpu(gpu: dict) -> bool:
    """True when the catalog entry is an NVIDIA (CUDA-capable) GPU.

    The transcription engine (nemo-speech.cpp on the ggml CUDA backend)
    cannot run on non-NVIDIA hardware. The catalog also lists AMD cards
    (Instinct/Radeon), which are sometimes cheaper and must never be picked.
    Strict on purpose: an unrecognized card is skipped rather than risking a
    dead pod.
    """
    haystack = " ".join(
        str(gpu.get(k) or "") for k in ("id", "name", "displayName")
    ).lower()
    return "nvidia" in haystack


class RunPodClient:
    """Thin wrapper over the RunPod v2 REST API."""

    def __init__(self, api_key: str, timeout: float = 30.0) -> None:
        self._client = httpx.Client(
            base_url=API_BASE,
            timeout=timeout,
            trust_env=False,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
                "User-Agent": _USER_AGENT,
            },
        )

    # ------------------------------------------------------------------
    # low level
    # ------------------------------------------------------------------

    def _request(
        self, method: str, path: str, body: dict | None = None, timeout: float | None = None
    ) -> dict:
        try:
            kwargs: dict = {}
            if timeout is not None:
                kwargs["timeout"] = timeout
            resp = self._client.request(method, path, json=body, **kwargs)
        except httpx.HTTPError as exc:
            raise RunPodError(f"RunPod request failed: {exc}") from exc
        if resp.status_code >= 400:
            detail = resp.text[:300]
            with contextlib.suppress(ValueError):
                parsed = resp.json()
                if isinstance(parsed, dict) and parsed.get("detail"):
                    detail = str(parsed["detail"])
            raise RunPodError(
                f"RunPod {method} {path}: HTTP {resp.status_code}: {detail}",
                status_code=resp.status_code,
            )
        try:
            return resp.json()
        except Exception:  # noqa: BLE001 — some endpoints return empty bodies
            return {}

    # ------------------------------------------------------------------
    # GPU catalog
    # ------------------------------------------------------------------

    def list_gpus(self) -> list[dict]:
        """All catalog GPUs with community pricing and availability."""
        data = self._request("GET", "/v2/catalog/gpus?include=AVAILABILITY&product=POD")
        return data.get("gpus", [])

    def ranked_gpus(self) -> list[tuple[str, float]]:
        """Return [(gpu_id, $/hr), ...] sorted cheapest-first.

        Only NVIDIA (CUDA-capable) GPUs are considered — the engine cannot
        run on anything else. GPUs the catalog flags as having capacity come
        first; GPUs flagged NONE (or unflagged) follow as a fallback, because
        catalog capacity is often stale and placement is the real test.
        Raises RunPodError when the catalog has no community CUDA GPUs.
        """
        with_capacity: list[tuple[float, str]] = []
        fallback: list[tuple[float, str]] = []
        for gpu in self.list_gpus():
            if not _is_cuda_gpu(gpu):
                continue
            price = (gpu.get("price") or {}).get("community")
            if not isinstance(price, (int, float)):
                continue
            gid = gpu.get("id") or gpu.get("name")
            if not gid:
                continue
            bucket = (
                with_capacity
                if gpu.get("availability") not in (None, "NONE")
                else fallback
            )
            bucket.append((float(price), gid))
        with_capacity.sort()
        fallback.sort()
        ranked = with_capacity + fallback
        if not ranked:
            raise RunPodError("No CUDA GPUs with capacity in the RunPod catalog right now")
        return [(gid, price) for price, gid in ranked]

    def cheapest_gpu(self) -> tuple[str, float]:
        """Return (gpu_id, $/hr) of the cheapest GPU with current capacity.

        Raises RunPodError when nothing is available.
        """
        gid, price = self.ranked_gpus()[0]
        return gid, price

    # ------------------------------------------------------------------
    # Pods
    # ------------------------------------------------------------------

    def list_pods(self) -> list[dict]:
        data = self._request("GET", "/v2/pods")
        return data.get("pods", [])

    def get_pod(self, pod_id: str) -> dict:
        return self._request("GET", f"/v2/pods/{pod_id}")

    def create_pod(self, body: dict) -> dict:
        return self._request("POST", "/v2/pods", body)

    def terminate_pod(self, pod_id: str) -> None:
        self._request("DELETE", f"/v2/pods/{pod_id}")

    def pod_logs(self, pod_id: str, timeout: float | None = None) -> str:
        data = self._request("GET", f"/v2/pods/{pod_id}/logs", timeout=timeout)
        logs = data.get("logs") or data.get("data") or ""
        if isinstance(logs, list):
            return "\n".join(str(x) for x in logs)
        return logs if isinstance(logs, str) else str(logs)
