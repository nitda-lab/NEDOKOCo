from api._shared import check_admin, check_cron


def test_check_cron(monkeypatch):
    monkeypatch.setenv("CRON_SECRET", "s3cr3t")
    assert check_cron({"authorization": "Bearer s3cr3t"}) is True
    assert check_cron({"authorization": "Bearer nope"}) is False
    assert check_cron({}) is False


def test_check_admin_bearer(monkeypatch):
    monkeypatch.setenv("ADMIN_TOKEN", "tok")
    assert check_admin({"authorization": "Bearer tok"}) is True
    assert check_admin({"cookie": "admin_token=tok"}) is True
    assert check_admin({"authorization": "Bearer x"}) is False
