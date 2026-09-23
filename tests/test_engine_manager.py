"""Tests for the on-demand engine manager and RunPod client (all network mocked)."""

import threading
import time

import pytest

import mink.engine.manager as manager_mod
from mink.cloud.runpod import RunPodClient, RunPodError
from mink.config import settings
from mink.engine.manager import EngineManager, EngineState, _boot_script


@pytest.fixture()
def manager(monkeypatch, tmp_path):
    monkeypatch.setattr(settings, "runpod_api_key", "test-key")
    monkeypatch.setattr(settings, "runpod_idle_minutes", 0)  # disable auto-stop
    monkeypatch.setattr(settings, "data_dir", tmp_path)
    monkeypatch.setattr(manager_mod, "_POD_POLL_S", 0.01)
    monkeypatch.setattr(manager_mod, "_HEALTH_POLL_S", 0.01)
    m = EngineManager()
    yield m
    # Leave no threads behind mutating shared state.
    m._state = EngineState.OFF


class FakeRunPod:
    """Stand-in for RunPodClient."""

    def __init__(self, fail_create: bool = False, fail_gpu_ids: tuple = ()):
        self.fail_create = fail_create
        self.fail_gpu_ids = set(fail_gpu_ids)
        self.terminated: list[str] = []
        self.created: list[dict] = []
        self.attempted_gpu_ids: list[str] = []

    def ranked_gpus(self):
        return [("NVIDIA RTX A5000", 0.16), ("NVIDIA RTX 3090", 0.22)]

    def cheapest_gpu(self):
        return self.ranked_gpus()[0]

    def create_pod(self, body):
        self.created.append(body)
        gid = (body.get("gpu") or {}).get("id")
        self.attempted_gpu_ids.append(gid)
        if self.fail_create or gid in self.fail_gpu_ids:
            # Placement failure, as RunPod reports it.
            raise RunPodError("no capacity", status_code=400)
        return {"id": "pod123"}

    def get_pod(self, pod_id):
        return {"id": pod_id, "status": "RUNNING"}

    def list_pods(self):
        return []

    def terminate_pod(self, pod_id):
        self.terminated.append(pod_id)


class FakeHealthResp:
    status_code = 200


def _healthy(monkeypatch):
    monkeypatch.setattr(
        manager_mod.httpx, "post", lambda *a, **k: FakeHealthResp()
    )


def _wait_for(manager, state, timeout=5.0):
    deadline = time.time() + timeout
    while time.time() < deadline:
        if manager.state is state:
            return True
        time.sleep(0.02)
    return False


# ---------------------------------------------------------------------------
# manager state machine
# ---------------------------------------------------------------------------


def test_starts_off_unconfigured(monkeypatch):
    monkeypatch.setattr(settings, "runpod_api_key", None)
    m = EngineManager()
    assert not m.configured
    assert m.state is EngineState.OFF
    assert m.api_key is None
    assert m.engine_url == settings.engine_url
    with pytest.raises(RunPodError):
        m.start()


def test_start_provisions_and_becomes_ready(manager, monkeypatch):
    fake = FakeRunPod()
    monkeypatch.setattr(manager, "_client", lambda: fake)
    _healthy(monkeypatch)

    status = manager.start()
    assert status["state"] == EngineState.PROVISIONING.value
    assert fake.created, "pod should have been created"
    body = fake.created[0]
    assert body["gpu"] == {"id": "NVIDIA RTX A5000", "count": 1}
    assert body["cloud"] == "COMMUNITY"
    assert "NEMO_API_KEY" in body["env"]
    assert body["ports"] == ["8000/http"]

    assert _wait_for(manager, EngineState.READY), "worker should reach READY"
    assert manager.api_key is not None
    assert manager.engine_url == "https://pod123-8000.proxy.runpod.net"
    # Bearer token persisted for re-adoption across restarts.
    assert manager._load_key()["pod_id"] == "pod123"


def test_start_failure_surfaces_error_state(manager, monkeypatch):
    fake = FakeRunPod(fail_create=True)
    monkeypatch.setattr(manager, "_client", lambda: fake)
    status = manager.start()
    assert status["state"] == EngineState.ERROR.value
    assert "no capacity" in status["error"]


def test_start_falls_back_to_next_gpu(manager, monkeypatch):
    fake = FakeRunPod(fail_gpu_ids=("NVIDIA RTX A5000",))
    monkeypatch.setattr(manager, "_client", lambda: fake)
    _healthy(monkeypatch)

    status = manager.start()
    assert status["state"] in (
        EngineState.PROVISIONING.value,
        EngineState.READY.value,
    )
    assert fake.attempted_gpu_ids == ["NVIDIA RTX A5000", "NVIDIA RTX 3090"]
    body = fake.created[-1]
    assert body["gpu"] == {"id": "NVIDIA RTX 3090", "count": 1}
    assert _wait_for(manager, EngineState.READY), "worker should reach READY"
    assert manager.engine_url == "https://pod123-8000.proxy.runpod.net"


def test_start_idempotent_while_provisioning(manager, monkeypatch):
    fake = FakeRunPod()
    monkeypatch.setattr(manager, "_client", lambda: fake)

    class NeverHealthy:
        status_code = 503

    monkeypatch.setattr(manager_mod.httpx, "post", lambda *a, **k: NeverHealthy())
    manager.start()
    n_created = len(fake.created)
    manager.start()
    assert len(fake.created) == n_created, "second start must not create another pod"


def test_stop_terminates_and_resets(manager, monkeypatch):
    fake = FakeRunPod()
    monkeypatch.setattr(manager, "_client", lambda: fake)
    _healthy(monkeypatch)
    manager.start()
    assert _wait_for(manager, EngineState.READY)

    status = manager.stop()
    assert status["state"] == EngineState.OFF.value
    assert fake.terminated == ["pod123"]
    assert manager.api_key is None
    assert manager.engine_url == settings.engine_url
    # Second stop is a no-op.
    manager.stop()


def test_touch_only_counts_when_ready(manager):
    manager.touch()  # OFF: no-op, must not raise
    assert manager.status()["idle_s"] is None


def test_boot_script_uses_current_cli_flags():
    script = _boot_script()
    assert "--asr-model parakeet-tdt" in script
    assert "--diar-model sortformer" in script
    assert "--host 0.0.0.0 --port 8000" in script
    assert '--api-key "$NEMO_API_KEY"' in script
    assert "--model " not in script.replace("--asr-model", "").replace("--diar-model", "")


# ---------------------------------------------------------------------------
# RunPod client: cheapest-GPU selection
# ---------------------------------------------------------------------------


def test_cheapest_gpu_picks_lowest_available(monkeypatch):
    client = RunPodClient("key")
    catalog = {
        "gpus": [
            {"id": "A", "availability": "NONE", "price": {"community": 0.05}},
            {"id": "B", "availability": "LOW", "price": {"community": 0.22}},
            {"id": "C", "availability": "HIGH", "price": {"community": 0.16}},
            {"id": "D", "availability": "LOW", "price": {"community": None}},
        ]
    }
    monkeypatch.setattr(client, "_request", lambda *a, **k: catalog)
    assert client.cheapest_gpu() == ("C", 0.16)


def test_ranked_gpus_puts_unavailable_last(monkeypatch):
    from mink.cloud.runpod import RunPodClient

    client = RunPodClient("key")
    catalog = {
        "gpus": [
            {"id": "A", "availability": "NONE", "price": {"community": 0.05}},
            {"id": "B", "availability": "LOW", "price": {"community": 0.22}},
            {"id": "C", "availability": "HIGH", "price": {"community": 0.16}},
            {"id": "D", "availability": "LOW", "price": {"community": None}},
        ]
    }
    monkeypatch.setattr(client, "_request", lambda *a, **k: catalog)
    # C and B have catalog capacity (cheapest first); A is a stale-catalog
    # fallback; D has no community price and is dropped.
    assert client.ranked_gpus() == [("C", 0.16), ("B", 0.22), ("A", 0.05)]


def test_start_stops_on_non_placement_error(manager, monkeypatch):
    """A 402 (no funds) must not be retried across the whole GPU list."""

    class BrokeRunPod(FakeRunPod):
        def ranked_gpus(self):
            return [("GPU1", 0.1), ("GPU2", 0.2)]

        def create_pod(self, body):
            raise RunPodError("balance too low", status_code=402)

    fake = BrokeRunPod()
    monkeypatch.setattr(manager, "_client", lambda: fake)
    status = manager.start()
    assert status["state"] == EngineState.ERROR.value
    assert "balance too low" in status["error"]


def test_cheapest_gpu_raises_when_empty(monkeypatch):
    client = RunPodClient("key")
    monkeypatch.setattr(client, "_request", lambda *a, **k: {"gpus": []})
    with pytest.raises(RunPodError):
        client.cheapest_gpu()


# ---------------------------------------------------------------------------
# EngineClient: bearer auth + manager URL
# ---------------------------------------------------------------------------


def test_client_sends_bearer_and_manager_url(monkeypatch):
    import mink.engine.client as client_mod

    calls = {}

    class FakeResp:
        status_code = 200

        def json(self):
            return {"text": "hi", "segments": []}

        def raise_for_status(self):
            pass

    class FakeClient:
        def __init__(self, **kwargs):
            calls["init"] = kwargs

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def post(self, url, data=None, files=None, headers=None):
            calls["url"] = url
            calls["headers"] = headers
            return FakeResp()

    monkeypatch.setattr(client_mod.httpx, "Client", FakeClient)

    class StubManager:
        engine_url = "https://pod123-8000.proxy.runpod.net"
        api_key = "secret-token"

        def touch(self):
            calls["touched"] = True

    monkeypatch.setattr(client_mod, "engine_manager", StubManager())

    from mink.engine.client import EngineClient

    client = EngineClient()
    assert client.base_url == "https://pod123-8000.proxy.runpod.net"

    import tempfile
    from pathlib import Path

    with tempfile.NamedTemporaryFile(suffix=".wav") as tmp:
        client.transcribe(Path(tmp.name))
    assert calls["headers"] == {"Authorization": "Bearer secret-token"}
    assert calls["url"].endswith("/v1/audio/transcriptions")
    assert calls["touched"]


def test_client_no_auth_header_without_key(monkeypatch):
    import mink.engine.client as client_mod

    class StubManager:
        engine_url = "http://127.0.0.1:8000"
        api_key = None

        def touch(self):
            pass

    monkeypatch.setattr(client_mod, "engine_manager", StubManager())

    from mink.engine.client import EngineClient

    assert EngineClient()._headers() == {}
    assert EngineClient(api_key="k")._headers() == {"Authorization": "Bearer k"}


def test_idle_worker_thread_count_stays_bounded(manager, monkeypatch):
    """Repeated starts must not leak idle-watcher threads."""
    fake = FakeRunPod()
    monkeypatch.setattr(manager, "_client", lambda: fake)
    _healthy(monkeypatch)
    before = threading.active_count()
    manager.start()
    assert _wait_for(manager, EngineState.READY)
    manager.stop()
    manager.start()
    assert _wait_for(manager, EngineState.READY)
    manager.stop()
    # At most the provision worker + idle watcher beyond baseline.
    assert threading.active_count() <= before + 2
