import pytest

from labmon.config import get_settings


def test_default_refresh_seconds_is_live(monkeypatch):
    monkeypatch.delenv("LABMON_REFRESH_SECONDS", raising=False)

    settings = get_settings()

    assert settings.refresh_seconds == 1


def test_refresh_seconds_accepts_fractional_values(monkeypatch):
    monkeypatch.setenv("LABMON_REFRESH_SECONDS", "0.5")

    settings = get_settings()

    assert settings.refresh_seconds == pytest.approx(0.5)


def test_refresh_seconds_has_lower_bound(monkeypatch):
    monkeypatch.setenv("LABMON_REFRESH_SECONDS", "0.05")

    settings = get_settings()

    assert settings.refresh_seconds == pytest.approx(0.25)
