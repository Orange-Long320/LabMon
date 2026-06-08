from labmon import collectors


class _AccessDeniedPsutil:
    class AccessDenied(Exception):
        pass

    class NoSuchProcess(Exception):
        pass

    @staticmethod
    def Process(_pid):
        raise _AccessDeniedPsutil.AccessDenied()


def test_process_details_handles_access_denied(monkeypatch):
    monkeypatch.setattr(collectors, "psutil", _AccessDeniedPsutil)

    details, warning = collectors._process_details(1234)

    assert details["pid"] == 1234
    assert details["username"] == "unknown"
    assert "权限不足" in warning
