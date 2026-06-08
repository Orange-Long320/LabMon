import getpass
import math
import os
import platform
import random
import socket
import time

from .config import get_settings
from .logs import discover_logs
from .nvidia import read_nvidia_smi

try:
    import psutil
except ImportError:  # pragma: no cover - exercised only before dependencies are installed
    psutil = None


def _safe_percent(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _bytes_to_gib(value):
    return round(float(value) / (1024 ** 3), 1)


def collect_host(settings=None):
    settings = settings or get_settings()
    warnings = []
    hostname = settings.host_label or socket.gethostname()
    host = {
        "hostname": hostname,
        "platform": platform.platform(),
        "mode": "demo" if settings.demo else "server",
        "refresh_seconds": settings.refresh_seconds,
        "cpu_percent": 0,
        "load_average": None,
        "memory": {"percent": 0, "used_gib": 0, "total_gib": 0},
        "disk": {"percent": 0, "used_gib": 0, "total_gib": 0},
    }
    if psutil is None:
        warnings.append("psutil 未安装，无法读取主机资源")
        return host, warnings

    try:
        host["cpu_percent"] = _safe_percent(psutil.cpu_percent(interval=0.05))
    except Exception as exc:
        warnings.append("CPU 读取失败: {}".format(exc))
    try:
        if hasattr(os, "getloadavg"):
            host["load_average"] = [round(value, 2) for value in os.getloadavg()]
    except OSError:
        pass
    try:
        memory = psutil.virtual_memory()
        host["memory"] = {
            "percent": _safe_percent(memory.percent),
            "used_gib": _bytes_to_gib(memory.used),
            "total_gib": _bytes_to_gib(memory.total),
        }
    except Exception as exc:
        warnings.append("内存读取失败: {}".format(exc))
    try:
        disk = psutil.disk_usage("/")
        host["disk"] = {
            "percent": _safe_percent(disk.percent),
            "used_gib": _bytes_to_gib(disk.used),
            "total_gib": _bytes_to_gib(disk.total),
        }
    except Exception as exc:
        warnings.append("磁盘读取失败: {}".format(exc))
    return host, warnings


def _process_details(pid):
    details = {
        "pid": pid,
        "username": "unknown",
        "command": "unknown",
        "started_at": None,
        "runtime_seconds": None,
        "cpu_percent": None,
        "memory_rss_mib": None,
    }
    if psutil is None:
        return details, "psutil 未安装，无法关联 PID {}".format(pid)
    try:
        process = psutil.Process(pid)
        with process.oneshot():
            details["username"] = process.username()
            cmdline = process.cmdline()
            details["command"] = " ".join(cmdline) if cmdline else process.name()
            details["started_at"] = process.create_time()
            details["runtime_seconds"] = max(0, int(time.time() - process.create_time()))
            details["cpu_percent"] = process.cpu_percent(interval=None)
            details["memory_rss_mib"] = round(process.memory_info().rss / (1024 ** 2), 1)
    except psutil.AccessDenied:
        return details, "PID {} 权限不足，只显示 nvidia-smi 信息".format(pid)
    except psutil.NoSuchProcess:
        return details, "PID {} 已结束".format(pid)
    except Exception as exc:
        return details, "PID {} 读取失败: {}".format(pid, exc)
    return details, None


def attach_process_details(gpus):
    warnings = []
    for gpu in gpus:
        detailed = []
        for process in gpu.get("processes", []):
            details, warning = _process_details(process["pid"])
            merged = dict(process)
            merged.update(details)
            detailed.append(merged)
            if warning:
                warnings.append(warning)
        gpu["processes"] = detailed
    return warnings


def _demo_process(pid, username, command, gpu_memory_mib, runtime_seconds):
    now = time.time()
    return {
        "pid": pid,
        "gpu_uuid": None,
        "gpu_memory_mib": gpu_memory_mib,
        "username": username,
        "command": command,
        "started_at": now - runtime_seconds,
        "runtime_seconds": runtime_seconds,
        "cpu_percent": round(random.uniform(8, 95), 1),
        "memory_rss_mib": round(random.uniform(1800, 24000), 1),
    }


def _demo_wave(base, amplitude, phase, offset, minimum=0, maximum=None):
    value = base + math.sin(phase + offset) * amplitude
    if maximum is not None:
        value = min(maximum, value)
    return max(minimum, int(round(value)))


def demo_gpus():
    users = [getpass.getuser(), "li", "wang", "chen"]
    commands = [
        "python train_rl.py --env FrankaPick --gpu 0 --seed 7",
        "python scripts/pretrain.py --config configs/vla.yaml",
        "python eval_policy.py --checkpoint runs/rl_3090/latest.pt",
        "python launch.py --model diffusion_policy --batch-size 64",
    ]
    phase = time.time() / 5
    profiles = [
        (
            0,
            _demo_wave(78, 6, phase, 0.0, maximum=98),
            _demo_wave(18940, 520, phase, 0.8, maximum=24576),
            _demo_wave(64, 3, phase, 1.6, maximum=80),
            _demo_wave(312, 14, phase, 2.4, maximum=350),
            [_demo_process(12841, users[0], commands[0], 11620, 7320)],
        ),
        (
            1,
            _demo_wave(6, 4, phase, 1.1, maximum=16),
            _demo_wave(2440, 180, phase, 2.2, maximum=24576),
            _demo_wave(43, 2, phase, 3.3, maximum=60),
            _demo_wave(86, 10, phase, 4.4, maximum=160),
            [],
        ),
        (
            2,
            _demo_wave(96, 3, phase, 2.0, maximum=100),
            _demo_wave(23170, 420, phase, 2.9, maximum=24576),
            _demo_wave(72, 3, phase, 3.8, maximum=83),
            _demo_wave(337, 9, phase, 4.7, maximum=350),
            [_demo_process(22110, users[1], commands[1], 18120, 18540), _demo_process(22187, users[2], commands[2], 3280, 8800)],
        ),
        (
            3,
            _demo_wave(42, 7, phase, 3.0, maximum=75),
            _demo_wave(10920, 640, phase, 3.7, maximum=24576),
            _demo_wave(58, 3, phase, 4.4, maximum=78),
            _demo_wave(214, 18, phase, 5.1, maximum=320),
            [_demo_process(30218, users[3], commands[3], 8750, 4210)],
        ),
    ]
    gpus = []
    for index, util, used, temp, power, processes in profiles:
        for process in processes:
            process["gpu_uuid"] = "GPU-DEMO-{}".format(index)
        gpus.append(
            {
                "index": index,
                "name": "NVIDIA GeForce RTX 3090",
                "uuid": "GPU-DEMO-{}".format(index),
                "utilization_gpu": util,
                "memory_total_mib": 24576,
                "memory_used_mib": used,
                "temperature_c": temp,
                "power_draw_w": power,
                "power_limit_w": 350,
                "processes": processes,
            }
        )
    return gpus


def collect_gpus(settings=None):
    settings = settings or get_settings()
    if settings.demo:
        return demo_gpus(), []
    gpus, warnings = read_nvidia_smi()
    warnings.extend(attach_process_details(gpus))
    return gpus, warnings


def collect_snapshot(settings=None):
    settings = settings or get_settings()
    warnings = []
    host, host_warnings = collect_host(settings)
    gpus, gpu_warnings = collect_gpus(settings)
    logs, log_warnings = discover_logs(settings.log_roots)
    warnings.extend(host_warnings)
    warnings.extend(gpu_warnings)
    warnings.extend(log_warnings)
    return {
        "generated_at": time.time(),
        "host": host,
        "gpus": gpus,
        "logs": logs,
        "warnings": warnings,
    }
