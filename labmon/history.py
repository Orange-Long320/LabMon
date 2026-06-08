import threading
import time
from collections import deque

from .collectors import collect_gpus, collect_host
from .config import get_settings


def _gpu_history_row(gpu):
    total = float(gpu.get("memory_total_mib") or 0)
    used = float(gpu.get("memory_used_mib") or 0)
    memory_percent = (used / total) * 100 if total else 0
    return {
        "index": gpu.get("index"),
        "utilization_gpu": gpu.get("utilization_gpu") or 0,
        "memory_used_mib": used,
        "memory_total_mib": total,
        "memory_percent": memory_percent,
    }


def collect_history_sample(settings=None):
    settings = settings or get_settings()
    warnings = []
    host, host_warnings = collect_host(settings)
    gpus, gpu_warnings = collect_gpus(settings)
    warnings.extend(host_warnings)
    warnings.extend(gpu_warnings)
    return {
        "generated_at": time.time(),
        "host": {
            "cpu_percent": host.get("cpu_percent") or 0,
            "memory_percent": (host.get("memory") or {}).get("percent") or 0,
        },
        "gpus": [_gpu_history_row(gpu) for gpu in gpus],
        "warnings": warnings,
    }


class HistoryRecorder:
    def __init__(self):
        self._lock = threading.Lock()
        self._samples = deque()
        self._thread = None
        self._stop_event = threading.Event()
        self._retention_seconds = 3600
        self._interval_seconds = 1

    def start(self, settings=None):
        settings = settings or get_settings()
        with self._lock:
            self._retention_seconds = float(settings.history_seconds)
            self._interval_seconds = float(settings.history_interval_seconds)
            if self._thread and self._thread.is_alive():
                return
            self._stop_event.clear()
            self._thread = threading.Thread(target=self._run, name="labmon-history", daemon=True)
            self._thread.start()

    def stop(self):
        thread = None
        with self._lock:
            thread = self._thread
            self._thread = None
            self._stop_event.set()
        if thread and thread.is_alive():
            thread.join(timeout=2)

    def record_once(self, settings=None):
        settings = settings or get_settings()
        self._retention_seconds = float(settings.history_seconds)
        sample = collect_history_sample(settings)
        with self._lock:
            self._samples.append(sample)
            self._trim_locked(sample["generated_at"])
        return sample

    def read(self, settings=None, seconds=None):
        settings = settings or get_settings()
        seconds = float(seconds or settings.history_seconds)
        with self._lock:
            empty = not self._samples
        if empty:
            self.record_once(settings)
        now = time.time()
        since = now - seconds
        with self._lock:
            samples = [sample for sample in self._samples if sample["generated_at"] >= since]
            retention = self._retention_seconds
            interval = self._interval_seconds
        return {
            "generated_at": now,
            "window_seconds": seconds,
            "retention_seconds": retention,
            "interval_seconds": interval,
            "samples": samples,
        }

    def _run(self):
        while not self._stop_event.is_set():
            settings = get_settings()
            started = time.monotonic()
            try:
                self.record_once(settings)
            except Exception:
                pass
            elapsed = time.monotonic() - started
            wait_seconds = max(0.1, float(settings.history_interval_seconds) - elapsed)
            self._stop_event.wait(wait_seconds)

    def _trim_locked(self, now):
        cutoff = now - self._retention_seconds
        while self._samples and self._samples[0]["generated_at"] < cutoff:
            self._samples.popleft()


recorder = HistoryRecorder()


def start_history_recorder(settings=None):
    recorder.start(settings)


def stop_history_recorder():
    recorder.stop()


def read_history(settings=None, seconds=None):
    return recorder.read(settings, seconds=seconds)
