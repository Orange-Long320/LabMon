from fastapi.testclient import TestClient

from labmon.app import app
from labmon.auth import hash_password, write_users


def configure_auth(monkeypatch, tmp_path):
    users_file = tmp_path / "users.json"
    write_users(users_file, {"alice": hash_password("secret")})
    monkeypatch.setenv("LABMON_AUTH", "1")
    monkeypatch.setenv("LABMON_AUTH_SECRET", "test-secret")
    monkeypatch.setenv("LABMON_USERS_FILE", str(users_file))
    monkeypatch.setenv("LABMON_DEMO", "1")


def test_auth_redirects_pages_and_denies_api(monkeypatch, tmp_path):
    configure_auth(monkeypatch, tmp_path)
    client = TestClient(app)

    page = client.get("/", follow_redirects=False)
    api = client.get("/api/snapshot")
    static_asset = client.get("/static/app.js", follow_redirects=False)

    assert page.status_code == 303
    assert page.headers["location"].startswith("/login")
    assert api.status_code == 401
    assert api.json()["message"] == "需要登录"
    assert static_asset.status_code == 303
    assert static_asset.headers["location"].startswith("/login")


def test_login_allows_snapshot_and_logout_blocks_again(monkeypatch, tmp_path):
    configure_auth(monkeypatch, tmp_path)
    client = TestClient(app)

    bad = client.post("/api/login", json={"username": "alice", "password": "wrong"})
    ok = client.post("/api/login", json={"username": "alice", "password": "secret"})
    me = client.get("/api/me")
    snapshot = client.get("/api/snapshot")
    logout = client.post("/api/logout")
    blocked = client.get("/api/snapshot")

    assert bad.status_code == 401
    assert ok.status_code == 200
    assert "labmon_session" in ok.headers["set-cookie"]
    assert me.json() == {"auth_enabled": True, "username": "alice"}
    assert snapshot.status_code == 200
    assert snapshot.json()["host"]["mode"] == "demo"
    assert logout.status_code == 200
    assert blocked.status_code == 401


def test_auth_disabled_reports_anonymous_session(monkeypatch):
    monkeypatch.delenv("LABMON_AUTH", raising=False)
    client = TestClient(app)

    response = client.get("/api/me")

    assert response.status_code == 200
    assert response.json() == {"auth_enabled": False, "username": None}


def test_missing_auth_secret_returns_clear_error(monkeypatch, tmp_path):
    users_file = tmp_path / "users.json"
    write_users(users_file, {"alice": hash_password("secret")})
    monkeypatch.setenv("LABMON_AUTH", "1")
    monkeypatch.setenv("LABMON_USERS_FILE", str(users_file))
    monkeypatch.delenv("LABMON_AUTH_SECRET", raising=False)
    monkeypatch.delenv("LABMON_DEMO", raising=False)
    client = TestClient(app)

    response = client.post("/api/login", json={"username": "alice", "password": "secret"})

    assert response.status_code == 500
    assert "LABMON_AUTH_SECRET" in response.json()["message"]
