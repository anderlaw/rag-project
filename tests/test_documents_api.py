def test_upload_list_detail_chunks_update_and_delete_document(client):
    upload = client.post(
        "/api/v1/documents/upload",
        files={"file": ("policy.txt", b"Alpha policy paragraph.\n\nBeta policy paragraph.", "text/plain")},
    )

    assert upload.status_code == 200
    uploaded = upload.json()
    assert uploaded["document_id"] == 1
    assert uploaded["version_id"] == 1
    assert uploaded["status"] == "COMPLETED"
    assert uploaded["chunk_count"] >= 2
    assert uploaded["current_version_id"] == 1

    listed = client.get("/api/v1/documents")
    assert listed.status_code == 200
    assert [item["name"] for item in listed.json()["items"]] == ["policy.txt"]

    detail = client.get("/api/v1/documents/1")
    assert detail.status_code == 200
    assert detail.json()["current_version_id"] == 1
    version_detail = detail.json()["versions"][0]
    assert version_detail["status"] == "COMPLETED"
    assert version_detail["parser_version"] == "document-parser-v1"
    assert version_detail["chunk_strategy_name"] == "parent_child_v1"
    assert version_detail["parser_config_snapshot"]["split_paragraphs"] is True
    assert version_detail["chunk_config_snapshot"]["child_chunk_size"] == 500

    chunks = client.get("/api/v1/documents/1/chunks?version=current&chunk_type=CHILD")
    assert chunks.status_code == 200
    child_chunks = chunks.json()["items"]
    assert child_chunks
    assert any("Alpha policy" in chunk["content"] for chunk in child_chunks)
    assert child_chunks[0]["content_with_context"]
    assert child_chunks[0]["search_text"]
    assert child_chunks[0]["start_char"] is not None
    assert child_chunks[0]["end_char"] is not None

    update = client.post(
        "/api/v1/documents/1/versions/upload",
        files={"file": ("policy.txt", b"Gamma updated policy.", "text/plain")},
    )
    assert update.status_code == 200
    assert update.json()["version_id"] == 2
    assert update.json()["current_version_id"] == 2

    updated_detail = client.get("/api/v1/documents/1").json()
    assert updated_detail["current_version_id"] == 2
    assert [version["version_no"] for version in updated_detail["versions"]] == [1, 2]

    delete = client.delete("/api/v1/documents/1")
    assert delete.status_code == 200
    assert delete.json() == {"success": True}

    listed_after_delete = client.get("/api/v1/documents").json()
    assert listed_after_delete["items"] == []
