from functools import lru_cache
from pathlib import Path
from typing import Annotated, Literal

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    app_env: str = "development"
    app_name: str = "RAG 知识库问答系统 API"
    debug: bool = False
    api_v1_prefix: str = "/api/v1"
    database_url: str = "sqlite+pysqlite:///.data/rag.db"
    db_echo: bool = False

    storage_provider: Literal["local", "r2"] = "local"
    local_storage_dir: Path = Path(".data/uploads")
    r2_account_id: str | None = None
    r2_bucket: str | None = None
    r2_access_key_id: str | None = None
    r2_secret_access_key: str | None = None
    r2_endpoint_url: str | None = None
    # 允许最大上传文件大小，单位MB，以及允许的上传文件扩展名列表（上传时后端根据此规则对文件校验，不通过则raise异常）
    max_upload_size_mb: int = 20
    allowed_upload_extensions: Annotated[list[str], NoDecode] = Field(
        default_factory=lambda: ["pdf", "docx", "md", "txt"]
    )

    # chunk相关设置：大小和重叠度
    parent_chunk_size: int = 1800
    parent_chunk_overlap: int = 200
    child_chunk_size: int = 500
    child_chunk_overlap: int = 100

    embedding_provider: Literal["fake", "dashscope"] = "fake"
    embedding_dimension: int = 1536
    embedding_batch_size: int = 16
    embedding_model: str = "text-embedding-v4"
    dashscope_api_key: str | None = None
    dashscope_api_url: str = "https://dashscope.aliyuncs.com/api/v1/services/embeddings/text-embedding/text-embedding"

    llm_provider: Literal["none", "zhipu"] = "none"
    zhipuai_api_key: str | None = None
    llm_model: str = "glm-5.1"
    llm_temperature: float = 0.2
    llm_max_tokens: int = 1200
    llm_timeout_seconds: int = 120

    @field_validator("allowed_upload_extensions", mode="before")
    @classmethod
    def parse_csv_list(cls, value: str | list[str]) -> list[str]:
        if isinstance(value, str):
            return [item.strip().lower().lstrip(".") for item in value.split(",") if item.strip()]
        return [item.lower().lstrip(".") for item in value]

    @field_validator("database_url", mode="before")
    @classmethod
    def normalize_database_url(cls, value: str) -> str:
        if isinstance(value, str) and value.startswith("postgresql://"):
            return value.replace("postgresql://", "postgresql+psycopg://", 1)
        return value

    @model_validator(mode="after")
    def validate_provider_settings(self) -> "Settings":
        if self.storage_provider == "r2":
            missing = [
                name
                for name, value in {
                    "R2_BUCKET": self.r2_bucket,
                    "R2_ACCESS_KEY_ID": self.r2_access_key_id,
                    "R2_SECRET_ACCESS_KEY": self.r2_secret_access_key,
                }.items()
                if not value
            ]
            if not (self.r2_endpoint_url or self.r2_account_id):
                missing.append("R2_ENDPOINT_URL or R2_ACCOUNT_ID")
            if missing:
                raise ValueError(f"missing R2 settings: {', '.join(missing)}")

        if self.embedding_provider == "dashscope" and not self.dashscope_api_key:
            raise ValueError("DASHSCOPE_API_KEY is required when EMBEDDING_PROVIDER=dashscope")

        if self.llm_provider == "zhipu" and not self.zhipuai_api_key:
            raise ValueError("ZHIPUAI_API_KEY is required when LLM_PROVIDER=zhipu")

        if self.embedding_provider == "dashscope" and "vision" in self.embedding_model.lower():
            raise ValueError("text ingestion requires a DashScope text embedding model, for example text-embedding-v4")

        if self.embedding_dimension <= 0:
            raise ValueError("EMBEDDING_DIMENSION must be positive")

        return self


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()


def reset_settings_cache() -> None:
    get_settings.cache_clear()


__all__ = ["Settings", "get_settings", "reset_settings_cache"]
