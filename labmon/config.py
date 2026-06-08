import os
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEMO_LOG_ROOT = PROJECT_ROOT / "sample_logs"


def env_bool(name, default=False):
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def split_roots(value):
    return [item.strip() for item in value.split(",") if item.strip()]


def env_float(name, default, minimum=None):
    raw_value = os.getenv(name)
    if raw_value is None:
        value = float(default)
    else:
        value = float(raw_value)
    if minimum is not None:
        return max(float(minimum), value)
    return value


class Settings:
    def __init__(self):
        self.demo = env_bool("LABMON_DEMO", default=False)
        self.host_label = os.getenv("LABMON_HOST_LABEL") or None
        self.refresh_seconds = env_float("LABMON_REFRESH_SECONDS", default=1, minimum=0.25)
        self.history_seconds = env_float("LABMON_HISTORY_SECONDS", default=3600, minimum=60)
        self.history_interval_seconds = env_float("LABMON_HISTORY_INTERVAL_SECONDS", default=1, minimum=0.5)
        self.auth_enabled = env_bool("LABMON_AUTH", default=False)
        self.auth_users_file = os.getenv("LABMON_USERS_FILE") or str(PROJECT_ROOT / "labmon-users.json")
        self.auth_secret = os.getenv("LABMON_AUTH_SECRET") or ("labmon-demo-secret-change-me" if self.demo else "")
        self.auth_session_hours = env_float("LABMON_AUTH_SESSION_HOURS", default=168, minimum=1)
        self.auth_cookie_secure = env_bool("LABMON_AUTH_COOKIE_SECURE", default=False)
        roots = os.getenv("LABMON_LOG_ROOTS")
        if roots:
            self.log_roots = split_roots(roots)
        elif self.demo:
            self.log_roots = [str(DEMO_LOG_ROOT)]
        else:
            self.log_roots = [
                "/home/*/runs",
                "/home/*/logs",
                "/data/runs",
                "/data/logs",
            ]


def get_settings():
    return Settings()
