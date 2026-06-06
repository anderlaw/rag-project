from pathlib import Path

from app.core.config import Settings
from app.core.errors import UploadValidationError

BYTES_PER_MEGABYTE = 1024 * 1024


def validate_upload(*, settings: Settings, filename: str, file_bytes: bytes) -> None:
    # 上传限制统一来自 settings；route 层只负责把校验错误转换成 HTTP 响应。
    extension = Path(filename).suffix.lower().lstrip(".")
    if not extension or extension not in settings.allowed_upload_extensions:
        allowed = ", ".join(settings.allowed_upload_extensions)
        raise UploadValidationError(f"file extension '{extension or '<none>'}' is not allowed; allowed: {allowed}")
    if not file_bytes:
        raise UploadValidationError("uploaded file is empty")
    max_bytes = settings.max_upload_size_mb * BYTES_PER_MEGABYTE
    if len(file_bytes) > max_bytes:
        raise UploadValidationError(f"uploaded file exceeds {settings.max_upload_size_mb} MB")
