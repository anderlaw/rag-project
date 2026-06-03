def test_synonym_group_can_be_created_listed_and_used_for_normalization(client):
    response = client.post(
        "/api/v1/rag/synonyms",
        json={
            "name": "客户画像",
            "description": "获客领域词",
            "terms": [
                {"term": "客户画像", "term_type": "CANONICAL", "language": "zh", "weight": 1.0},
                {"term": "ICP", "term_type": "SYNONYM", "language": "en", "weight": 1.0},
            ],
        },
    )

    assert response.status_code == 200
    created = response.json()
    assert created["name"] == "客户画像"
    assert [term["term"] for term in created["terms"]] == ["客户画像", "ICP"]

    list_response = client.get("/api/v1/rag/synonyms")
    assert list_response.status_code == 200
    assert list_response.json()["items"][0]["name"] == "客户画像"

    normalize_response = client.post(
        "/api/v1/rag/normalize-query",
        json={"question": "告诉我ICP是啥"},
    )

    assert normalize_response.status_code == 200
    normalized = normalize_response.json()
    assert normalized["normalized_text"] == "ICP"
    assert "ICP" in normalized["expanded_text"]
    assert "客户画像" in normalized["expanded_text"]


def test_debug_query_uses_database_synonyms(client):
    from app.core.database import get_session
    from app.models.document import RagChunk, RagDocument, RagDocumentVersion

    create_synonym = client.post(
        "/api/v1/rag/synonyms",
        json={
            "name": "客户画像",
            "terms": [
                {"term": "客户画像", "term_type": "CANONICAL"},
                {"term": "ICP", "term_type": "SYNONYM", "language": "en"},
            ],
        },
    )
    assert create_synonym.status_code == 200

    with get_session() as db:
        document = RagDocument(name="获客方法.md", file_type="md", file_size=100, status="ACTIVE")
        db.add(document)
        db.flush()
        version = RagDocumentVersion(
            document_id=document.id,
            version_no=1,
            file_hash="hash",
            original_filename=document.name,
            status="COMPLETED",
            chunk_count=1,
        )
        db.add(version)
        db.flush()
        document.current_version_id = version.id
        db.add(
            RagChunk(
                document_id=document.id,
                document_version_id=version.id,
                chunk_type="CHILD",
                chunk_index=0,
                child_index=0,
                section_title="客户画像",
                heading_path="获客方法 / 客户画像",
                content="客户画像用于定义目标客户行业、规模、职位和需求。",
                search_text="获客方法 / 客户画像\n\n客户画像用于定义目标客户行业、规模、职位和需求。",
            )
        )
        db.commit()

    response = client.post(
        "/api/v1/rag/debug-query",
        json={
            "question": "告诉我ICP是啥",
            "use_llm": True,
            "vector_top_k": 0,
            "keyword_top_k": 5,
            "trgm_top_k": 0,
            "final_top_k": 1,
            "min_final_score": 0,
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["selected_chunks"][0]["section_title"] == "客户画像"
    assert "客户画像用于定义目标客户" in body["prompt"]["text"]
