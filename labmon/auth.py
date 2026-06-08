import base64
import hashlib
import hmac
import json
import secrets
import time
from pathlib import Path


COOKIE_NAME = "labmon_session"
HASH_ALGORITHM = "pbkdf2_sha256"
HASH_ITERATIONS = 260000


class AuthConfigError(RuntimeError):
    pass


def _b64encode(raw):
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def _b64decode(value):
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode((value + padding).encode("ascii"))


def hash_password(password, salt=None, iterations=HASH_ITERATIONS):
    salt = salt or secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), iterations)
    return "{}${}${}${}".format(HASH_ALGORITHM, iterations, salt, _b64encode(digest))


def verify_password(password, encoded):
    try:
        algorithm, iterations, salt, expected = encoded.split("$", 3)
        if algorithm != HASH_ALGORITHM:
            return False
        candidate = hash_password(password, salt=salt, iterations=int(iterations)).split("$", 3)[3]
    except (TypeError, ValueError):
        return False
    return hmac.compare_digest(candidate, expected)


def load_users(users_file):
    path = Path(users_file)
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, dict):
        return {}
    return payload


def write_users(users_file, users):
    path = Path(users_file)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(users, handle, indent=2, ensure_ascii=False, sort_keys=True)
        handle.write("\n")
    path.chmod(0o600)


def require_auth_secret(settings):
    if settings.auth_secret:
        return settings.auth_secret
    raise AuthConfigError("LABMON_AUTH_SECRET is required when LABMON_AUTH=1")


def authenticate_user(settings, username, password):
    username = (username or "").strip()
    if not username or not password:
        return None
    password_hash = load_users(settings.auth_users_file).get(username)
    if not password_hash:
        return None
    if verify_password(password, password_hash):
        return username
    return None


def create_session_token(settings, username):
    secret = require_auth_secret(settings).encode("utf-8")
    expires_at = int(time.time() + settings.auth_session_hours * 3600)
    payload = _b64encode(json.dumps({"sub": username, "exp": expires_at}, separators=(",", ":")).encode("utf-8"))
    signature = _b64encode(hmac.new(secret, payload.encode("ascii"), hashlib.sha256).digest())
    return "{}.{}".format(payload, signature)


def read_session_user(settings, token):
    if not token:
        return None
    secret = require_auth_secret(settings).encode("utf-8")
    try:
        payload, signature = token.split(".", 1)
        expected = _b64encode(hmac.new(secret, payload.encode("ascii"), hashlib.sha256).digest())
        if not hmac.compare_digest(signature, expected):
            return None
        data = json.loads(_b64decode(payload).decode("utf-8"))
    except (ValueError, json.JSONDecodeError):
        return None
    if int(data.get("exp", 0)) < int(time.time()):
        return None
    username = data.get("sub")
    if not username:
        return None
    if username not in load_users(settings.auth_users_file):
        return None
    return username


def cookie_max_age(settings):
    return int(settings.auth_session_hours * 3600)
