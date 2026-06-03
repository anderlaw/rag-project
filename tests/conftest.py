import os
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient


@pytest.fixture()
def client(tmp_path, monkeypatch) -> Iterator[TestClient]:
    db_path = tmp_path / "rag-test.db"
    storage_dir = tmp_path / "uploads"

    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv("DATABASE_URL", f"sqlite+pysqlite:///{db_path}")
    monkeypatch.setenv("STORAGE_PROVIDER", "local")
    monkeypatch.setenv("LOCAL_STORAGE_DIR", str(storage_dir))
    monkeypatch.setenv("EMBEDDING_PROVIDER", "fake")
    monkeypatch.setenv("EMBEDDING_DIMENSION", "8")
    monkeypatch.setenv("ALLOWED_UPLOAD_EXTENSIONS", "txt,md,pdf")

    from app.core.config import reset_settings_cache
    from app.core.database import Base, configure_database, get_engine
    from app.main import create_app

    reset_settings_cache()
    configure_database(os.environ["DATABASE_URL"])
    Base.metadata.create_all(bind=get_engine())

    app = create_app()
    with TestClient(app) as test_client:
        yield test_client

    Base.metadata.drop_all(bind=get_engine())
