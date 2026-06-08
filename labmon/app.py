from pathlib import Path

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .collectors import collect_snapshot
from .config import PROJECT_ROOT, get_settings
from .logs import read_indexed_log


STATIC_DIR = PROJECT_ROOT / "static"

app = FastAPI(title="LabMon", version="0.1.0")
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


@app.get("/")
def index():
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/api/snapshot")
def snapshot():
    return collect_snapshot(get_settings())


@app.get("/api/logs/{log_id}")
def read_log(log_id, lines: int = Query(default=200, ge=1, le=1000)):
    settings = get_settings()
    result, warnings = read_indexed_log(settings.log_roots, log_id, lines=lines)
    if result is None:
        raise HTTPException(
            status_code=404,
            detail={"message": "日志不存在或不在允许的扫描目录中", "warnings": warnings},
        )
    result["warnings"] = warnings
    return result
