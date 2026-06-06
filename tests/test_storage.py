from pathlib import Path


def test_local_storage_saves_under_document_version_path(tmp_path):
    from app.services.storage import LocalStorageService

    service = LocalStorageService(base_dir=tmp_path, key_prefix="dev")

    storage_key = service.save(
        file_bytes=b"hello",
        filename="Policy V1.txt",
        content_type="text/plain",
        document_id=7,
        version_id=3,
    )

    assert storage_key == "dev/documents/7/versions/3/policy-v1.txt"
    assert (tmp_path / Path(storage_key)).read_bytes() == b"hello"


def test_r2_storage_puts_object_with_stable_key():
    from app.services.storage import R2StorageService

    calls = []

    class FakeS3Client:
        def put_object(self, **kwargs):
            calls.append(kwargs)

    service = R2StorageService(bucket="rag-docs", client=FakeS3Client(), key_prefix="prod")

    storage_key = service.save(
        file_bytes=b"hello",
        filename="Policy V1.txt",
        content_type="text/plain",
        document_id=7,
        version_id=3,
    )

    assert storage_key == "prod/documents/7/versions/3/policy-v1.txt"
    assert calls == [
        {
            "Bucket": "rag-docs",
            "Key": storage_key,
            "Body": b"hello",
            "ContentType": "text/plain",
        }
    ]


def test_storage_key_prefix_is_sanitized():
    from app.services.storage import build_storage_key

    storage_key = build_storage_key(document_id=7, version_id=3, filename="Policy V1.txt", key_prefix="Dev Env/")

    assert storage_key == "dev-env/documents/7/versions/3/policy-v1.txt"
