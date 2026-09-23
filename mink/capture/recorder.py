"""Lecture audio recorder.

Captures 16 kHz mono WAV — the sample rate the ASR engine expects — from the
default input device. Long lectures are written as a single file; the
transcription engine handles segmentation internally.
"""

from __future__ import annotations

import threading
import wave
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path


@dataclass
class Recording:
    path: Path
    started_at: datetime
    ended_at: datetime | None = None

    @property
    def duration_seconds(self) -> float | None:
        if self.ended_at is None:
            return None
        return (self.ended_at - self.started_at).total_seconds()


class AudioRecorder:
    """Blocking recorder with start/stop semantics for lecture sessions."""

    SAMPLE_RATE = 16_000
    CHANNELS = 1
    SAMPLE_WIDTH = 2  # 16-bit

    def __init__(self, output_dir: Path, device: int | str | None = None) -> None:
        self.output_dir = output_dir
        self.device = device
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._recording: Recording | None = None

    @property
    def is_recording(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def start(self) -> Recording:
        """Begin recording to a timestamped WAV file. Requires the ``capture``
        extra (``pip install mink[capture]``)."""
        try:
            import sounddevice as sd
        except ImportError as exc:
            raise RuntimeError(
                "Audio capture needs the 'capture' extra: pip install 'mink[capture]'"
            ) from exc

        if self.is_recording:
            raise RuntimeError("Already recording")

        self.output_dir.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        path = self.output_dir / f"lecture-{stamp}.wav"
        self._recording = Recording(path=path, started_at=datetime.now(timezone.utc))
        self._stop.clear()

        def _run() -> None:
            assert self._recording is not None
            with wave.open(str(path), "wb") as wf:
                wf.setnchannels(self.CHANNELS)
                wf.setsampwidth(self.SAMPLE_WIDTH)
                wf.setframerate(self.SAMPLE_RATE)

                def _callback(indata, frames, time_info, status):
                    if status:
                        print(f"audio status: {status}")
                    wf.writeframes(indata.tobytes())

                with sd.InputStream(
                    samplerate=self.SAMPLE_RATE,
                    channels=self.CHANNELS,
                    dtype="int16",
                    device=self.device,
                    callback=_callback,
                ):
                    self._stop.wait()

        self._thread = threading.Thread(target=_run, daemon=True)
        self._thread.start()
        return self._recording

    def stop(self) -> Recording:
        """Stop recording and return the finished Recording."""
        if not self.is_recording or self._recording is None:
            raise RuntimeError("Not recording")
        self._stop.set()
        assert self._thread is not None
        self._thread.join()
        self._thread = None
        self._recording.ended_at = datetime.now(timezone.utc)
        recording, self._recording = self._recording, None
        return recording

    @staticmethod
    def list_devices() -> list[dict]:
        """List available input devices (for ``mink devices``)."""
        try:
            import sounddevice as sd
        except ImportError as exc:
            raise RuntimeError(
                "Audio capture needs the 'capture' extra: pip install 'mink[capture]'"
            ) from exc
        return [
            {"index": i, "name": d["name"], "channels": d["max_input_channels"]}
            for i, d in enumerate(sd.query_devices())
            if d["max_input_channels"] > 0
        ]
