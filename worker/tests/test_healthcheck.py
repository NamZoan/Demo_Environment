import app.healthcheck as healthcheck


class _FakeCursor:
    def __init__(self):
        self.statements = []

    def __enter__(self):
        return self

    def __exit__(self, _exc_type, _exc_value, _traceback):
        return False

    def execute(self, statement):
        self.statements.append(statement)


class _FakeConnection:
    def __init__(self):
        self.cursor_obj = _FakeCursor()

    def __enter__(self):
        return self

    def __exit__(self, _exc_type, _exc_value, _traceback):
        return False

    def cursor(self):
        return self.cursor_obj


def test_check_database_executes_select_one():
    connection = _FakeConnection()

    healthcheck.check_database("postgresql://monitor:secret@db/environment", connect=lambda _url, **_kwargs: connection)

    assert connection.cursor_obj.statements == ["SELECT 1"]


def test_main_returns_failure_without_leaking_database_url(monkeypatch, capsys):
    monkeypatch.setenv("DATABASE_URL", "postgresql://monitor:secret@db/environment")
    monkeypatch.setattr(healthcheck.psycopg, "connect", lambda *_args, **_kwargs: (_ for _ in ()).throw(TimeoutError("secret")))

    assert healthcheck.main() == 1
    output = capsys.readouterr().out
    assert "Worker database healthcheck failed" in output
    assert "secret" not in output
    assert "postgresql://" not in output
