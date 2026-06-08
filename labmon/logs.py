import glob
import hashlib
import os
import re
from collections import deque
from pathlib import Path


LOG_SUFFIXES = {".log", ".txt", ".out", ".err"}
MAX_LOG_FILES = 80
MAX_SCAN_BYTES = 128 * 1024 * 1024

METRIC_PATTERNS = {
    "epoch": re.compile(r"\bepoch\s*[:=/ ]\s*(\d+(?:\.\d+)?)", re.I),
    "step": re.compile(r"\b(?:global_)?step\s*[:=/ ]\s*(\d+)", re.I),
    "episode": re.compile(r"\b(?:episode|ep)\s*[:=/ ]\s*(\d+)", re.I),
    "loss": re.compile(r"\b(?:loss|train_loss|policy_loss)\s*[:=/ ]\s*(-?\d+(?:\.\d+)?)", re.I),
    "reward": re.compile(r"\b(?:reward|return|episode_reward|mean_reward)\s*[:=/ ]\s*(-?\d+(?:\.\d+)?)", re.I),
    "lr": re.compile(r"\blr\s*[:=/ ]\s*(\d+(?:\.\d+)?(?:e-?\d+)?)", re.I),
    "eta": re.compile(r"\b(?:eta|remaining)\s*[:=/ ]\s*([0-9]+(?::[0-9]{2}){1,2}|[0-9.]+\s*[smhd])", re.I),
}


def stable_log_id(path):
    return hashlib.sha1(str(Path(path).resolve()).encode("utf-8")).hexdigest()[:16]


def parse_progress_line(line):
    metrics = {}
    for key, pattern in METRIC_PATTERNS.items():
        match = pattern.search(line)
        if match:
            metrics[key] = match.group(1)
    return metrics


def merge_progress(lines):
    merged = {}
    for line in lines:
        merged.update(parse_progress_line(line))
    return merged


def tail_lines(path, lines=200):
    line_count = max(1, min(int(lines), 1000))
    with open(path, "r", encoding="utf-8", errors="replace") as handle:
        return list(deque(handle, maxlen=line_count))


def _candidate_files(root_pattern):
    matches = glob.glob(os.path.expanduser(root_pattern))
    for matched in matches:
        path = Path(matched)
        if path.is_file():
            yield path
        elif path.is_dir():
            for child in path.rglob("*"):
                if child.is_file():
                    yield child


def _looks_like_log(path):
    if path.name.startswith("."):
        return False
    if path.suffix.lower() in LOG_SUFFIXES:
        return True
    return path.suffix == "" and any(part in path.name.lower() for part in ("log", "stdout", "train"))


def discover_logs(root_patterns):
    warnings = []
    seen = set()
    files = []
    for root in root_patterns:
        matched_any = False
        for path in _candidate_files(root):
            matched_any = True
            try:
                resolved = path.resolve()
                stat = resolved.stat()
            except (OSError, RuntimeError) as exc:
                warnings.append("日志文件不可读: {} ({})".format(path, exc))
                continue
            if resolved in seen or not _looks_like_log(resolved):
                continue
            if stat.st_size > MAX_SCAN_BYTES:
                continue
            seen.add(resolved)
            files.append((resolved, stat))
        if not matched_any:
            warnings.append("日志目录未匹配: {}".format(root))

    files.sort(key=lambda item: item[1].st_mtime, reverse=True)
    logs = []
    for path, stat in files[:MAX_LOG_FILES]:
        try:
            tail = tail_lines(path, lines=20)
            last_line = tail[-1].strip() if tail else ""
            progress = merge_progress(tail)
        except OSError as exc:
            warnings.append("读取日志失败: {} ({})".format(path, exc))
            continue
        logs.append(
            {
                "id": stable_log_id(path),
                "name": path.name,
                "path": str(path),
                "modified_at": stat.st_mtime,
                "size_bytes": stat.st_size,
                "last_line": last_line,
                "progress": progress,
            }
        )
    if not logs and root_patterns:
        warnings.append("没有发现可展示的日志文件")
    return logs, warnings


def log_index(root_patterns):
    logs, warnings = discover_logs(root_patterns)
    return {item["id"]: item for item in logs}, warnings


def read_indexed_log(root_patterns, log_id, lines=200):
    index, warnings = log_index(root_patterns)
    entry = index.get(log_id)
    if entry is None:
        return None, warnings
    content = tail_lines(entry["path"], lines=lines)
    return {"entry": entry, "lines": [line.rstrip("\n") for line in content]}, warnings
