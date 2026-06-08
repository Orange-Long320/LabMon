from fastapi.testclient import TestClient

from labmon.app import app


def test_demo_snapshot_returns_four_mock_gpus(monkeypatch):
    monkeypatch.setenv("LABMON_DEMO", "1")

    client = TestClient(app)
    response = client.get("/api/snapshot")

    assert response.status_code == 200
    payload = response.json()
    assert payload["host"]["mode"] == "demo"
    assert len(payload["gpus"]) == 4
    assert payload["gpus"][0]["name"] == "NVIDIA GeForce RTX 3090"


def test_log_endpoint_reads_only_indexed_logs(monkeypatch):
    monkeypatch.setenv("LABMON_DEMO", "1")

    client = TestClient(app)
    snapshot = client.get("/api/snapshot").json()
    log_id = snapshot["logs"][0]["id"]

    ok = client.get(f"/api/logs/{log_id}?lines=5")
    missing = client.get("/api/logs/not-a-real-log-id")

    assert ok.status_code == 200
    assert len(ok.json()["lines"]) <= 5
    assert missing.status_code == 404


def test_history_endpoint_returns_server_side_samples(monkeypatch):
    monkeypatch.setenv("LABMON_DEMO", "1")

    from labmon.history import recorder

    recorder.stop()
    with recorder._lock:
        recorder._samples.clear()

    client = TestClient(app)
    response = client.get("/api/history?seconds=120")

    assert response.status_code == 200
    payload = response.json()
    assert payload["window_seconds"] == 120
    assert payload["samples"]
    assert len(payload["samples"][-1]["gpus"]) == 4
    assert "cpu_percent" in payload["samples"][-1]["host"]
