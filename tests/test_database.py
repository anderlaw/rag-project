def test_postgresql_engine_uses_pre_ping_to_recover_stale_connections(monkeypatch):
    from app.core import database

    captured: dict = {}

    def fake_create_engine(url, **kwargs):
        captured["url"] = url
        captured["kwargs"] = kwargs
        return object()

    def fake_sessionmaker(**kwargs):
        captured["sessionmaker"] = kwargs
        return object()

    monkeypatch.setattr(database, "create_engine", fake_create_engine)
    monkeypatch.setattr(database, "sessionmaker", fake_sessionmaker)

    database.configure_database("postgresql+psycopg://user:pass@example/db")

    assert captured["kwargs"]["pool_pre_ping"] is True
    assert captured["kwargs"]["pool_recycle"] == 1800
    assert captured["kwargs"]["connect_args"] == {}


def test_sqlite_engine_keeps_thread_connect_args_without_pool_recycle(monkeypatch):
    from app.core import database

    captured: dict = {}

    def fake_create_engine(url, **kwargs):
        captured["url"] = url
        captured["kwargs"] = kwargs
        return object()

    def fake_sessionmaker(**kwargs):
        captured["sessionmaker"] = kwargs
        return object()

    monkeypatch.setattr(database, "create_engine", fake_create_engine)
    monkeypatch.setattr(database, "sessionmaker", fake_sessionmaker)

    database.configure_database("sqlite+pysqlite:///:memory:")

    assert captured["kwargs"]["connect_args"] == {"check_same_thread": False}
    assert "pool_pre_ping" not in captured["kwargs"]
    assert "pool_recycle" not in captured["kwargs"]
