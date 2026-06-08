from labmon.nvidia import parse_gpu_query, parse_process_query


def test_parse_gpu_query():
    output = """0, NVIDIA GeForce RTX 3090, GPU-aaa, 78, 24576, 18940, 64, 312.45, 350.00
1, NVIDIA GeForce RTX 3090, GPU-bbb, 0, 24576, 12, 34, 20.11, 350.00
"""

    gpus = parse_gpu_query(output)

    assert len(gpus) == 2
    assert gpus[0]["index"] == 0
    assert gpus[0]["utilization_gpu"] == 78
    assert gpus[0]["memory_total_mib"] == 24576
    assert gpus[0]["power_draw_w"] == 312.45
    assert gpus[1]["uuid"] == "GPU-bbb"


def test_parse_process_query():
    output = """12841, GPU-aaa, 11620
22110, GPU-bbb, 18120
"""

    processes = parse_process_query(output)

    assert processes == [
        {"pid": 12841, "gpu_uuid": "GPU-aaa", "gpu_memory_mib": 11620},
        {"pid": 22110, "gpu_uuid": "GPU-bbb", "gpu_memory_mib": 18120},
    ]


def test_parse_ignores_malformed_process_rows():
    processes = parse_process_query("not-a-pid, GPU-aaa, N/A\n")

    assert processes == []
