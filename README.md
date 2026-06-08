# LabMon

四卡 RTX 3090 服务器只读监控面板。本机可以先跑 demo，部署到服务器后切到真实 `nvidia-smi` 采集。

## 本机 demo

```bash
uv sync --dev
LABMON_DEMO=1 uv run uvicorn labmon.app:app --reload --host 127.0.0.1 --port 8765
```

打开 <http://127.0.0.1:8765>。

## 测试

```bash
uv run pytest
```

## 服务器运行

```bash
uv sync --no-dev
LABMON_LOG_ROOTS="/home/*/runs,/home/*/logs,/data/runs,/data/logs" \
uv run uvicorn labmon.app:app --host 0.0.0.0 --port 8765
```

服务是只读的，不提供 kill 进程或写入实验目录的能力。如果端口可能暴露到公网，建议绑定 `127.0.0.1`，再通过 SSH tunnel 或 Nginx basic auth 访问。

## 环境变量

- `LABMON_DEMO=1`：启用本机 demo，GPU/进程使用模拟四卡 3090 数据。
- `LABMON_LOG_ROOTS`：逗号分隔的日志目录或 glob。
- `LABMON_HOST_LABEL`：覆盖页面顶部显示的主机名。
- `LABMON_REFRESH_SECONDS`：前端刷新间隔，默认 5 秒。

## systemd 示例

见 `deploy/labmon.service`。部署时需要把 `WorkingDirectory` 改成服务器上的实际路径，并先在该目录执行 `uv sync --no-dev`。
