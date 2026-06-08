import csv
import subprocess
from io import StringIO


GPU_QUERY = [
    "index",
    "name",
    "uuid",
    "utilization.gpu",
    "memory.total",
    "memory.used",
    "temperature.gpu",
    "power.draw",
    "power.limit",
]

PROCESS_QUERY = [
    "pid",
    "gpu_uuid",
    "used_memory",
]


def _clean_value(value):
    value = value.strip()
    for suffix in (" MiB", " W", " %"):
        if value.endswith(suffix):
            value = value[: -len(suffix)]
    if value in {"[Not Supported]", "N/A", ""}:
        return None
    return value


def _to_int(value):
    cleaned = _clean_value(value)
    if cleaned is None:
        return None
    try:
        return int(float(cleaned))
    except ValueError:
        return None


def _to_float(value):
    cleaned = _clean_value(value)
    if cleaned is None:
        return None
    try:
        return float(cleaned)
    except ValueError:
        return None


def parse_csv_rows(output):
    reader = csv.reader(StringIO(output.strip()))
    return [[cell.strip() for cell in row] for row in reader if row]


def parse_gpu_query(output):
    gpus = []
    for row in parse_csv_rows(output):
        if len(row) < len(GPU_QUERY):
            continue
        gpus.append(
            {
                "index": _to_int(row[0]),
                "name": row[1],
                "uuid": row[2],
                "utilization_gpu": _to_int(row[3]) or 0,
                "memory_total_mib": _to_int(row[4]) or 0,
                "memory_used_mib": _to_int(row[5]) or 0,
                "temperature_c": _to_int(row[6]),
                "power_draw_w": _to_float(row[7]),
                "power_limit_w": _to_float(row[8]),
                "processes": [],
            }
        )
    return gpus


def parse_process_query(output):
    processes = []
    for row in parse_csv_rows(output):
        if len(row) < len(PROCESS_QUERY):
            continue
        pid = _to_int(row[0])
        if pid is None:
            continue
        processes.append(
            {
                "pid": pid,
                "gpu_uuid": row[1],
                "gpu_memory_mib": _to_int(row[2]) or 0,
            }
        )
    return processes


def _run_query(query_type, fields):
    args = [
        "nvidia-smi",
        "--query-{}={}".format(query_type, ",".join(fields)),
        "--format=csv,noheader,nounits",
    ]
    return subprocess.check_output(args, text=True, stderr=subprocess.STDOUT, timeout=4)


def read_nvidia_smi():
    warnings = []
    try:
        gpu_output = _run_query("gpu", GPU_QUERY)
        gpus = parse_gpu_query(gpu_output)
    except FileNotFoundError:
        return [], ["未找到 nvidia-smi，当前环境可能没有 NVIDIA 驱动"]
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
        return [], ["nvidia-smi GPU 查询失败: {}".format(exc)]

    try:
        process_output = _run_query("compute-apps", PROCESS_QUERY)
        processes = parse_process_query(process_output)
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
        warnings.append("nvidia-smi 进程查询失败: {}".format(exc))
        processes = []

    by_uuid = {gpu["uuid"]: gpu for gpu in gpus}
    for process in processes:
        gpu = by_uuid.get(process["gpu_uuid"])
        if gpu:
            gpu["processes"].append(process)
    return gpus, warnings
