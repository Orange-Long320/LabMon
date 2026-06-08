from pathlib import Path

from labmon.logs import discover_logs, parse_progress_line, read_indexed_log, stable_log_id


def test_parse_progress_line():
    metrics = parse_progress_line("epoch=3 step=1250 loss=0.942 reward=1.8 lr=2.8e-4 eta=01:44:50")

    assert metrics["epoch"] == "3"
    assert metrics["step"] == "1250"
    assert metrics["loss"] == "0.942"
    assert metrics["reward"] == "1.8"
    assert metrics["lr"] == "2.8e-4"
    assert metrics["eta"] == "01:44:50"


def test_discover_logs_extracts_latest_progress(tmp_path):
    log_path = tmp_path / "train.log"
    log_path.write_text(
        "step=10 loss=2.0 reward=-1\nstep=20 loss=1.5 reward=4 eta=10m\n",
        encoding="utf-8",
    )

    logs, warnings = discover_logs([str(tmp_path)])

    assert warnings == []
    assert len(logs) == 1
    assert logs[0]["id"] == stable_log_id(log_path)
    assert logs[0]["progress"]["step"] == "20"
    assert logs[0]["progress"]["loss"] == "1.5"
    assert logs[0]["last_line"] == "step=20 loss=1.5 reward=4 eta=10m"


def test_read_indexed_log_uses_whitelist(tmp_path):
    allowed = tmp_path / "train.log"
    allowed.write_text("step=1 loss=1\n", encoding="utf-8")
    secret = tmp_path.parent / "secret.log"
    secret.write_text("step=999 loss=0\n", encoding="utf-8")

    result, _warnings = read_indexed_log([str(tmp_path)], stable_log_id(allowed), lines=20)
    rejected, _warnings = read_indexed_log([str(tmp_path)], stable_log_id(secret), lines=20)
    traversal, _warnings = read_indexed_log([str(tmp_path)], "../secret.log", lines=20)

    assert result["lines"] == ["step=1 loss=1"]
    assert rejected is None
    assert traversal is None
