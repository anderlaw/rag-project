import re
from abc import ABC, abstractmethod
from pathlib import Path

import boto3

from app.core.config import Settings


class StorageService(ABC):
    @abstractmethod
    def save(
        self,
        *,
        file_bytes: bytes,
        filename: str,
        content_type: str,
        document_id: int,
        version_id: int,
    ) -> str:
        raise NotImplementedError


class LocalStorageService(StorageService):
    def __init__(self, *, base_dir: str | Path, key_prefix: str = "") -> None:
        self.base_dir = Path(base_dir)
        self.key_prefix = key_prefix

    def save(
        self,
        *,
        file_bytes: bytes,
        filename: str,
        content_type: str,
        document_id: int,
        version_id: int,
    ) -> str:
        storage_key = build_storage_key(
            document_id=document_id,
            version_id=version_id,
            filename=filename,
            key_prefix=self.key_prefix,
        )
        target = self.base_dir / storage_key
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(file_bytes)
        return storage_key


class R2StorageService(StorageService):
    def __init__(self, *, bucket: str, client, key_prefix: str = "") -> None:
        self.bucket = bucket
        self.client = client
        self.key_prefix = key_prefix

    def save(
        self,
        *,
        file_bytes: bytes,
        filename: str,
        content_type: str,
        document_id: int,
        version_id: int,
    ) -> str:
        storage_key = build_storage_key(
            document_id=document_id,
            version_id=version_id,
            filename=filename,
            key_prefix=self.key_prefix,
        )
        self.client.put_object(
            Bucket=self.bucket,
            Key=storage_key,
            Body=file_bytes,
            ContentType=content_type,
        )
        return storage_key


def create_storage_service(settings: Settings) -> StorageService:
    key_prefix = settings.storage_key_prefix or settings.app_env
    if settings.storage_provider == "local":
        return LocalStorageService(base_dir=settings.local_storage_dir, key_prefix=key_prefix)

    endpoint_url = settings.r2_endpoint_url
    if endpoint_url is None and settings.r2_account_id:
        endpoint_url = f"https://{settings.r2_account_id}.r2.cloudflarestorage.com"

    client = boto3.client(
        "s3",
        endpoint_url=endpoint_url,
        aws_access_key_id=settings.r2_access_key_id,
        aws_secret_access_key=settings.r2_secret_access_key,
        region_name="auto",
    )
    assert settings.r2_bucket is not None
    return R2StorageService(bucket=settings.r2_bucket, client=client, key_prefix=key_prefix)


def build_storage_key(*, document_id: int, version_id: int, filename: str, key_prefix: str = "") -> str:
    parts = [sanitize_key_prefix(key_prefix), "documents", str(document_id), "versions", str(version_id), sanitize_filename(filename)]
    return "/".join(part for part in parts if part)


def sanitize_filename(filename: str) -> str:
    # 存储 key 保留原扩展名，但统一规范文件名主体，保证本地和对象存储路径格式一致。
    stem = Path(filename).stem.lower()
    suffix = Path(filename).suffix.lower()
    safe_stem = re.sub(r"[^a-z0-9]+", "-", stem).strip("-")
    safe_stem = re.sub(r"-+", "-", safe_stem) or "upload"
    safe_suffix = re.sub(r"[^a-z0-9.]", "", suffix)
    return f"{safe_stem}{safe_suffix}"


def sanitize_key_prefix(prefix: str) -> str:
    safe_prefix = re.sub(r"[^a-z0-9]+", "-", prefix.lower()).strip("-")
    return re.sub(r"-+", "-", safe_prefix)
