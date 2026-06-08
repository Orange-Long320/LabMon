from contextlib import asynccontextmanager
from pathlib import Path
from urllib.parse import quote

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from .auth import (
    COOKIE_NAME,
    AuthConfigError,
    authenticate_user,
    cookie_max_age,
    create_session_token,
    read_session_user,
)
from .collectors import collect_snapshot
from .config import PROJECT_ROOT, get_settings
from .history import read_history, start_history_recorder, stop_history_recorder
from .logs import read_indexed_log


STATIC_DIR = PROJECT_ROOT / "static"


@asynccontextmanager
async def lifespan(_app):
    start_history_recorder(get_settings())
    try:
        yield
    finally:
        stop_history_recorder()


app = FastAPI(title="LabMon", version="0.1.0", lifespan=lifespan)
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


class LoginPayload(BaseModel):
    username: str
    password: str


def _login_url(request):
    next_path = request.url.path
    if request.url.query:
        next_path = "{}?{}".format(next_path, request.url.query)
    return "/login?next={}".format(quote(next_path, safe=""))


def _is_public_path(path):
    return path in {"/login", "/api/login", "/api/logout"}


def _wants_json(request):
    return request.url.path.startswith("/api/") or "application/json" in request.headers.get("accept", "")


@app.middleware("http")
async def require_login(request: Request, call_next):
    settings = get_settings()
    if not settings.auth_enabled or _is_public_path(request.url.path):
        return await call_next(request)
    try:
        username = read_session_user(settings, request.cookies.get(COOKIE_NAME))
    except AuthConfigError as exc:
        return JSONResponse({"message": str(exc)}, status_code=500)
    if not username:
        if _wants_json(request):
            return JSONResponse({"message": "需要登录"}, status_code=401)
        return RedirectResponse(_login_url(request), status_code=303)
    request.state.user = username
    return await call_next(request)


@app.get("/")
def index():
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/login")
def login_page(request: Request):
    settings = get_settings()
    if not settings.auth_enabled:
        return RedirectResponse("/", status_code=303)
    try:
        username = read_session_user(settings, request.cookies.get(COOKIE_NAME))
    except AuthConfigError as exc:
        return JSONResponse({"message": str(exc)}, status_code=500)
    if username:
        return RedirectResponse("/", status_code=303)
    return FileResponse(STATIC_DIR / "login.html")


@app.post("/api/login")
def login(payload: LoginPayload):
    settings = get_settings()
    if not settings.auth_enabled:
        return {"auth_enabled": False, "username": None}
    username = authenticate_user(settings, payload.username, payload.password)
    if not username:
        raise HTTPException(status_code=401, detail={"message": "用户名或密码不正确"})
    try:
        token = create_session_token(settings, username)
    except AuthConfigError as exc:
        return JSONResponse({"message": str(exc)}, status_code=500)
    response = JSONResponse({"auth_enabled": True, "username": username})
    response.set_cookie(
        COOKIE_NAME,
        token,
        max_age=cookie_max_age(settings),
        httponly=True,
        secure=settings.auth_cookie_secure,
        samesite="lax",
        path="/",
    )
    return response


@app.post("/api/logout")
def logout():
    response = JSONResponse({"ok": True})
    response.delete_cookie(COOKIE_NAME, path="/")
    return response


@app.get("/api/me")
def me(request: Request):
    settings = get_settings()
    if not settings.auth_enabled:
        return {"auth_enabled": False, "username": None}
    return {"auth_enabled": True, "username": request.state.user}


@app.get("/api/snapshot")
def snapshot():
    return collect_snapshot(get_settings())


@app.get("/api/history")
def history(seconds: int = Query(default=600, ge=30, le=86400)):
    settings = get_settings()
    return read_history(settings, seconds=seconds)


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
