def test_failed_new_version_does_not_replace_current_version(client, monkeypatch):
    created = client.post(
        "/api/v1/documents/upload",
        files={"file": ("policy.txt", b"Stable policy.", "text/plain")},
    )
    assert created.status_code == 200
    assert created.json()["current_version_id"] == 1

    from app.services import ingest_service as ingest_module

    original_create_embedding_service = ingest_module.create_embedding_service

    class FailingEmbeddingService:
        def embed(self, texts):
            raise RuntimeError("embedding unavailable")

    monkeypatch.setattr(
        ingest_module,
        "create_embedding_service",
        lambda settings: FailingEmbeddingService(),
    )

    failed = client.post(
        "/api/v1/documents/1/versions/upload",
        files={"file": ("broken-v2.txt", b"Broken update.", "text/plain")},
    )

    monkeypatch.setattr(
        ingest_module,
        "create_embedding_service",
        original_create_embedding_service,
    )

    assert failed.status_code == 500
    detail = client.get("/api/v1/documents/1").json()
    assert detail["name"] == "policy.txt"
    assert detail["current_version_id"] == 1
    assert detail["versions"][-1]["version_no"] == 2
    assert detail["versions"][-1]["status"] == "FAILED"
    assert detail["versions"][-1]["error_message"] == "embedding unavailable"


def test_upload_rejects_disallowed_extensions_without_version(client):
    rejected = client.post(
        "/api/v1/documents/upload",
        files={"file": ("malware.exe", b"nope", "application/octet-stream")},
    )

    assert rejected.status_code == 400
    assert "not allowed" in rejected.json()["detail"]

    listed = client.get("/api/v1/documents").json()
    assert listed["items"] == []
