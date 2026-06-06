import pytest
from pydantic import ValidationError


def set_auth_env(monkeypatch) -> None:
    monkeypatch.setenv("AUTH_SESSION_SECRET", "test-secret")
    monkeypatch.setenv("SUPER_ADMIN_USERNAME", "admin")
    monkeypatch.setenv("SUPER_ADMIN_PASSWORD", "admin-pass")
    monkeypatch.setenv("NORMAL_USER_USERNAME", "user")
    monkeypatch.setenv("NORMAL_USER_PASSWORD", "user-pass")


def test_local_storage_settings_accept_default_local_provider(monkeypatch, tmp_path):
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv("DATABASE_URL", "sqlite+pysqlite:///:memory:")
    monkeypatch.setenv("STORAGE_PROVIDER", "local")
    monkeypatch.setenv("LOCAL_STORAGE_DIR", str(tmp_path / "uploads"))
    monkeypatch.setenv("EMBEDDING_PROVIDER", "fake")
    set_auth_env(monkeypatch)

    from app.core.config import Settings

    settings = Settings(_env_file=None)

    assert settings.storage_provider == "local"
    assert settings.local_storage_dir == tmp_path / "uploads"
    assert settings.embedding_provider == "fake"


def test_r2_storage_requires_bucket_and_credentials(monkeypatch):
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://user:pass@example/db")
    monkeypatch.setenv("STORAGE_PROVIDER", "r2")
    monkeypatch.delenv("R2_BUCKET", raising=False)
    monkeypatch.delenv("R2_ACCESS_KEY_ID", raising=False)
    monkeypatch.delenv("R2_SECRET_ACCESS_KEY", raising=False)
    set_auth_env(monkeypatch)

    from app.core.config import Settings

    with pytest.raises(ValidationError):
        Settings(_env_file=None)


def test_dashscope_embedding_requires_api_key(monkeypatch, tmp_path):
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://user:pass@example/db")
    monkeypatch.setenv("STORAGE_PROVIDER", "local")
    monkeypatch.setenv("LOCAL_STORAGE_DIR", str(tmp_path / "uploads"))
    monkeypatch.setenv("EMBEDDING_PROVIDER", "dashscope")
    monkeypatch.delenv("DASHSCOPE_API_KEY", raising=False)
    set_auth_env(monkeypatch)

    from app.core.config import Settings

    with pytest.raises(ValidationError):
        Settings(_env_file=None)


def test_zhipu_llm_requires_api_key(monkeypatch, tmp_path):
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://user:pass@example/db")
    monkeypatch.setenv("STORAGE_PROVIDER", "local")
    monkeypatch.setenv("LOCAL_STORAGE_DIR", str(tmp_path / "uploads"))
    monkeypatch.setenv("EMBEDDING_PROVIDER", "fake")
    monkeypatch.setenv("LLM_PROVIDER", "zhipu")
    monkeypatch.delenv("ZHIPUAI_API_KEY", raising=False)
    set_auth_env(monkeypatch)

    from app.core.config import Settings

    with pytest.raises(ValidationError):
        Settings(_env_file=None)


def test_minimax_llm_requires_api_key(monkeypatch, tmp_path):
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://user:pass@example/db")
    monkeypatch.setenv("STORAGE_PROVIDER", "local")
    monkeypatch.setenv("LOCAL_STORAGE_DIR", str(tmp_path / "uploads"))
    monkeypatch.setenv("EMBEDDING_PROVIDER", "fake")
    monkeypatch.setenv("LLM_PROVIDER", "minimax")
    monkeypatch.delenv("MINIMAX_API_KEY", raising=False)
    set_auth_env(monkeypatch)

    from app.core.config import Settings

    with pytest.raises(ValidationError) as exc_info:
        Settings(_env_file=None)

    assert "MINIMAX_API_KEY" in str(exc_info.value)


def test_minimax_llm_settings(monkeypatch, tmp_path):
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv("DATABASE_URL", "sqlite+pysqlite:///:memory:")
    monkeypatch.setenv("STORAGE_PROVIDER", "local")
    monkeypatch.setenv("LOCAL_STORAGE_DIR", str(tmp_path / "uploads"))
    monkeypatch.setenv("EMBEDDING_PROVIDER", "fake")
    monkeypatch.setenv("LLM_PROVIDER", "minimax")
    monkeypatch.setenv("MINIMAX_API_KEY", "test-key")
    monkeypatch.setenv("MINIMAX_API_BASE_URL", "https://api.minimax.io/v1")
    monkeypatch.setenv("LLM_MODEL", "MiniMax-M2.7")
    set_auth_env(monkeypatch)

    from app.core.config import Settings

    settings = Settings(_env_file=None)

    assert settings.llm_provider == "minimax"
    assert settings.minimax_api_key == "test-key"
    assert settings.minimax_api_base_url == "https://api.minimax.io/v1"
    assert settings.llm_model == "MiniMax-M2.7"


def test_dashscope_embedding_and_zhipu_llm_settings_are_separate(monkeypatch, tmp_path):
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv("DATABASE_URL", "sqlite+pysqlite:///:memory:")
    monkeypatch.setenv("STORAGE_PROVIDER", "local")
    monkeypatch.setenv("LOCAL_STORAGE_DIR", str(tmp_path / "uploads"))
    monkeypatch.setenv("EMBEDDING_PROVIDER", "dashscope")
    monkeypatch.setenv("DASHSCOPE_API_KEY", "dashscope-key")
    monkeypatch.setenv("EMBEDDING_MODEL", "text-embedding-v4")
    monkeypatch.setenv("LLM_PROVIDER", "zhipu")
    monkeypatch.setenv("ZHIPUAI_API_KEY", "test-key")
    monkeypatch.setenv("LLM_MODEL", "glm-5.1")
    set_auth_env(monkeypatch)

    from app.core.config import Settings

    settings = Settings(_env_file=None)

    assert settings.embedding_provider == "dashscope"
    assert settings.dashscope_api_key == "dashscope-key"
    assert settings.embedding_model == "text-embedding-v4"
    assert settings.llm_provider == "zhipu"
    assert settings.zhipuai_api_key == "test-key"
    assert settings.llm_model == "glm-5.1"


def test_plain_postgresql_url_is_normalized_to_psycopg_driver(monkeypatch, tmp_path):
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv("DATABASE_URL", "postgresql://user:pass@example/db")
    monkeypatch.setenv("STORAGE_PROVIDER", "local")
    monkeypatch.setenv("LOCAL_STORAGE_DIR", str(tmp_path / "uploads"))
    monkeypatch.setenv("EMBEDDING_PROVIDER", "fake")
    set_auth_env(monkeypatch)

    from app.core.config import Settings

    settings = Settings(_env_file=None)

    assert settings.database_url == "postgresql+psycopg://user:pass@example/db"


def test_dashscope_text_ingestion_rejects_vision_embedding_model(monkeypatch, tmp_path):
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv("DATABASE_URL", "sqlite+pysqlite:///:memory:")
    monkeypatch.setenv("STORAGE_PROVIDER", "local")
    monkeypatch.setenv("LOCAL_STORAGE_DIR", str(tmp_path / "uploads"))
    monkeypatch.setenv("EMBEDDING_PROVIDER", "dashscope")
    monkeypatch.setenv("DASHSCOPE_API_KEY", "test-key")
    monkeypatch.setenv("EMBEDDING_MODEL", "tongyi-embedding-vision-plus-2026-03-06")
    set_auth_env(monkeypatch)

    from app.core.config import Settings

    with pytest.raises(ValidationError):
        Settings(_env_file=None)


def test_auth_settings_are_required_by_default(monkeypatch, tmp_path):
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv("DATABASE_URL", "sqlite+pysqlite:///:memory:")
    monkeypatch.setenv("STORAGE_PROVIDER", "local")
    monkeypatch.setenv("LOCAL_STORAGE_DIR", str(tmp_path / "uploads"))
    monkeypatch.setenv("EMBEDDING_PROVIDER", "fake")
    monkeypatch.delenv("AUTH_SESSION_SECRET", raising=False)
    monkeypatch.delenv("SUPER_ADMIN_USERNAME", raising=False)
    monkeypatch.delenv("SUPER_ADMIN_PASSWORD", raising=False)
    monkeypatch.delenv("NORMAL_USER_USERNAME", raising=False)
    monkeypatch.delenv("NORMAL_USER_PASSWORD", raising=False)

    from app.core.config import Settings

    with pytest.raises(ValidationError) as exc_info:
        Settings(_env_file=None)

    assert "AUTH_SESSION_SECRET" in str(exc_info.value)
