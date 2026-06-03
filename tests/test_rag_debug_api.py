import pytest


def test_debug_query_selects_keyword_match_when_vector_signal_is_missing(client, monkeypatch):
    from app.core.database import get_session
    from app.models.document import RagChunk, RagDocument, RagDocumentVersion

    monkeypatch.setattr("app.services.rag_debug_service._embed_query", lambda _: [1.0, 0.0])

    with get_session() as db:
        document = RagDocument(name="AI获客数据权限相关.md", file_type="md", file_size=100, status="ACTIVE")
        db.add(document)
        db.flush()

        version = RagDocumentVersion(
            document_id=document.id,
            version_no=1,
            file_hash="hash",
            original_filename=document.name,
            status="COMPLETED",
            chunk_count=2,
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
                section_title="8.2 数据隔离不生效",
                heading_path="常见问题排查 / 8.2 数据隔离不生效",
                content="用户登录时权限会缓存到 Redis",
                content_with_context="常见问题排查 / 8.2 数据隔离不生效\n\n用户登录时权限会缓存到 Redis",
                search_text="常见问题排查 / 8.2 数据隔离不生效\n\n用户登录时权限会缓存到 Redis",
                embedding=[0.8, 0.6],
            )
        )
        db.add(
            RagChunk(
                document_id=document.id,
                document_version_id=version.id,
                chunk_type="CHILD",
                chunk_index=1,
                child_index=0,
                section_title="1.2 技术栈",
                heading_path="AI获客数据权限相关 / 一、项目概览 / 1.2 技术栈",
                content="|层级|技术|\n|---|---|\n|后端|FastAPI + TortoiseORM + PostgreSQL + Redis|",
                content_with_context=(
                    "AI获客数据权限相关 / 一、项目概览 / 1.2 技术栈\n\n"
                    "|层级|技术|\n|---|---|\n|后端|FastAPI + TortoiseORM + PostgreSQL + Redis|"
                ),
                search_text=(
                    "AI获客数据权限相关 / 一、项目概览 / 1.2 技术栈\n\n"
                    "|层级|技术|\n|---|---|\n|后端|FastAPI + TortoiseORM + PostgreSQL + Redis|"
                ),
                embedding=[-1.0, 0.0],
            )
        )
        db.commit()

    response = client.post(
        "/api/v1/rag/debug-query",
        json={"question": "AI智能获客技术栈是什么", "use_llm": True},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["selected_chunks"]
    selected = body["selected_chunks"][0]
    assert selected["section_title"] == "1.2 技术栈"
    assert selected["keyword_score"] >= 0.7
    assert selected["final_score"] >= body["search_profile"]["min_final_score"]
    assert "FastAPI" in body["prompt"]["text"]


def test_debug_query_does_not_select_separator_chunks(client):
    from app.core.database import get_session
    from app.models.document import RagChunk, RagDocument, RagDocumentVersion

    with get_session() as db:
        document = RagDocument(name="AI获客数据权限相关.md", file_type="md", file_size=100, status="ACTIVE")
        db.add(document)
        db.flush()

        version = RagDocumentVersion(
            document_id=document.id,
            version_no=1,
            file_hash="hash",
            original_filename=document.name,
            status="COMPLETED",
            chunk_count=2,
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
                section_title="1.2 技术栈",
                heading_path="AI获客数据权限相关 / 一、项目概览 / 1.2 技术栈",
                content="---",
                content_with_context="AI获客数据权限相关 / 一、项目概览 / 1.2 技术栈\n\n---",
                search_text="AI获客数据权限相关 / 一、项目概览 / 1.2 技术栈\n\n---",
            )
        )
        db.add(
            RagChunk(
                document_id=document.id,
                document_version_id=version.id,
                chunk_type="CHILD",
                chunk_index=1,
                child_index=0,
                section_title="1.2 技术栈",
                heading_path="AI获客数据权限相关 / 一、项目概览 / 1.2 技术栈",
                content="|层级|技术|\n|---|---|\n|后端|FastAPI + TortoiseORM + PostgreSQL + Redis|",
                content_with_context=(
                    "AI获客数据权限相关 / 一、项目概览 / 1.2 技术栈\n\n"
                    "|层级|技术|\n|---|---|\n|后端|FastAPI + TortoiseORM + PostgreSQL + Redis|"
                ),
                search_text=(
                    "AI获客数据权限相关 / 一、项目概览 / 1.2 技术栈\n\n"
                    "|层级|技术|\n|---|---|\n|后端|FastAPI + TortoiseORM + PostgreSQL + Redis|"
                ),
            )
        )
        db.commit()

    response = client.post(
        "/api/v1/rag/debug-query",
        json={"question": "AI智能获客技术栈是什么", "use_llm": True, "final_top_k": 2},
    )

    assert response.status_code == 200
    body = response.json()
    assert [chunk["content"] for chunk in body["selected_chunks"]] == [
        "|层级|技术|\n|---|---|\n|后端|FastAPI + TortoiseORM + PostgreSQL + Redis|"
    ]
    assert "---\n\n---" not in body["prompt"]["text"]


def test_debug_query_diagnoses_related_deleted_documents(client):
    from app.core.database import get_session
    from app.models.document import RagChunk, RagDocument, RagDocumentVersion

    with get_session() as db:
        active_document = RagDocument(name="AI 工程师前端面试题解答.pdf", file_type="pdf", file_size=100, status="ACTIVE")
        db.add(active_document)
        db.flush()
        active_version = RagDocumentVersion(
            document_id=active_document.id,
            version_no=1,
            file_hash="active-hash",
            original_filename=active_document.name,
            status="COMPLETED",
            chunk_count=1,
        )
        db.add(active_version)
        db.flush()
        active_document.current_version_id = active_version.id
        db.add(
            RagChunk(
                document_id=active_document.id,
                document_version_id=active_version.id,
                chunk_type="CHILD",
                chunk_index=0,
                child_index=0,
                section_title="权限校验",
                heading_path="面试题 / 权限校验",
                content="用户登录时权限会缓存到 Redis。",
                search_text="用户登录时权限会缓存到 Redis。",
            )
        )

        deleted_document = RagDocument(name="AI获客数据权限相关.md", file_type="md", file_size=100, status="DELETED")
        db.add(deleted_document)
        db.flush()
        deleted_version = RagDocumentVersion(
            document_id=deleted_document.id,
            version_no=1,
            file_hash="deleted-hash",
            original_filename=deleted_document.name,
            status="COMPLETED",
            chunk_count=1,
        )
        db.add(deleted_version)
        db.flush()
        deleted_document.current_version_id = deleted_version.id
        db.add(
            RagChunk(
                document_id=deleted_document.id,
                document_version_id=deleted_version.id,
                chunk_type="CHILD",
                chunk_index=0,
                child_index=0,
                section_title="**1\\.2 技术栈**",
                heading_path="AI获客数据权限相关 / **一、项目概览** / **1\\.2 技术栈**",
                content="后端使用 FastAPI + TortoiseORM + PostgreSQL + Redis。",
                content_with_context="AI获客数据权限相关 / 一、项目概览 / 1.2 技术栈\n\n后端使用 FastAPI。",
                search_text="AI获客数据权限相关 技术栈 FastAPI TortoiseORM PostgreSQL Redis",
            )
        )
        db.commit()

    response = client.post(
        "/api/v1/rag/debug-query",
        json={
            "question": "AI智能获客技术栈是什么",
            "use_llm": False,
            "vector_top_k": 0,
            "keyword_top_k": 20,
            "trgm_top_k": 20,
        },
    )

    assert response.status_code == 200
    body = response.json()
    diagnostics = body["diagnostics"]
    assert diagnostics["active_document_count"] == 1
    assert diagnostics["searchable_child_chunk_count"] == 1
    assert diagnostics["inactive_related_documents"][0]["name"] == "AI获客数据权限相关.md"
    assert diagnostics["inactive_related_documents"][0]["status"] == "DELETED"
    assert diagnostics["inactive_related_documents"][0]["version_status"] == "COMPLETED"
    assert diagnostics["inactive_related_documents"][0]["chunk_count"] == 1
    assert "未参与检索" in diagnostics["warnings"][0]


def test_debug_query_returns_merged_candidates_scores_and_prompt(client):
    upload = client.post(
        "/api/v1/documents/upload",
        files={
            "file": (
                "policy.txt",
                b"Alpha travel reimbursement requires invoices and approvals.\n\n"
                b"Beta cafeteria menu is unrelated to reimbursement.",
                "text/plain",
            )
        },
    )
    assert upload.status_code == 200

    response = client.post(
        "/api/v1/rag/debug-query",
        json={
            "question": "Alpha reimbursement invoices",
            "use_llm": True,
            "vector_top_k": 20,
            "vector_weight": 0.65,
            "min_final_score": 0,
            "final_top_k": 2,
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["query_log_id"] > 0
    assert body["question"] == "Alpha reimbursement invoices"
    assert body["search_profile"]["vector_weight"] == 0.65
    assert body["search_profile"]["keyword_weight"] == 0.25
    assert body["search_profile"]["trgm_weight"] == 0.1

    candidates = body["candidates"]
    assert candidates
    assert len({candidate["chunk_id"] for candidate in candidates}) == len(candidates)

    first = candidates[0]
    assert first["rank"] == 1
    assert first["document_name"] == "policy.txt"
    assert 0 <= first["vector_score"] <= 1
    assert 0 <= first["keyword_score"] <= 1
    assert 0 <= first["trgm_score"] <= 1
    assert first["final_score"] == pytest.approx(
        _expected_final_score(first, body["search_profile"]),
        abs=0.0001,
    )

    selected = body["selected_chunks"]
    assert selected
    assert all(chunk["selected_for_prompt"] for chunk in selected)
    assert body["prompt"] is not None
    assert "Alpha travel reimbursement" in body["prompt"]["text"]
    assert body["llm"]["used"] is False
    assert body["llm"]["error"] == "LLM provider is not configured"

    detail_response = client.get(f"/api/v1/rag/query-logs/{body['query_log_id']}")

    assert detail_response.status_code == 200
    detail = detail_response.json()
    assert detail["id"] == body["query_log_id"]
    assert detail["question"] == "Alpha reimbursement invoices"
    assert detail["search_profile"]["mode"] == "HYBRID"
    assert detail["prompt"]["text"] == body["prompt"]["text"]
    assert detail["llm"]["error"] == "LLM provider is not configured"
    assert detail["candidates"][0]["chunk_id"] == first["chunk_id"]
    assert detail["selected_chunks"][0]["selected_for_prompt"] is True


def test_query_log_detail_returns_404_for_missing_log(client):
    response = client.get("/api/v1/rag/query-logs/999")

    assert response.status_code == 404
    assert response.json()["detail"] == "query log not found"


def test_query_log_can_be_saved_as_failure_case(client):
    upload = client.post(
        "/api/v1/documents/upload",
        files={"file": ("policy.txt", b"Alpha travel reimbursement requires invoices.", "text/plain")},
    )
    assert upload.status_code == 200
    debug = client.post(
        "/api/v1/rag/debug-query",
        json={"question": "Alpha reimbursement invoices", "use_llm": True, "min_final_score": 0, "final_top_k": 1},
    )
    assert debug.status_code == 200
    query_log_id = debug.json()["query_log_id"]

    response = client.post(
        f"/api/v1/rag/query-logs/{query_log_id}/failure-cases",
        json={
            "primary_failure_type": "RETRIEVAL_LOW_RANK",
            "status": "OPEN",
            "priority": 2,
            "analysis_note": "正确 chunk 排名过低",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["id"] > 0
    assert body["query_log_id"] == query_log_id
    assert body["source_type"] == "MANUAL_DEBUG"
    assert body["primary_failure_type"] == "RETRIEVAL_LOW_RANK"
    assert body["status"] == "OPEN"
    assert body["priority"] == 2
    assert body["analysis_note"] == "正确 chunk 排名过低"


def test_query_log_can_be_saved_as_eval_case_draft(client):
    upload = client.post(
        "/api/v1/documents/upload",
        files={"file": ("policy.txt", b"Alpha travel reimbursement requires invoices.", "text/plain")},
    )
    assert upload.status_code == 200
    debug = client.post(
        "/api/v1/rag/debug-query",
        json={"question": "Alpha reimbursement invoices", "use_llm": True, "min_final_score": 0, "final_top_k": 1},
    )
    assert debug.status_code == 200
    query_log_id = debug.json()["query_log_id"]

    response = client.post(
        f"/api/v1/rag/query-logs/{query_log_id}/eval-cases",
        json={
            "question": "Alpha 报销需要什么材料？",
            "expected_answer": "需要发票。",
            "case_type": "FAILURE_REGRESSION",
            "status": "DRAFT",
            "priority": 2,
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["id"] > 0
    assert body["question"] == "Alpha 报销需要什么材料？"
    assert body["expected_answer"] == "需要发票。"
    assert body["case_type"] == "FAILURE_REGRESSION"
    assert body["status"] == "DRAFT"
    assert body["priority"] == 2
    assert body["created_from"] == "QUERY_LOG"
    assert body["source_ref_id"] == query_log_id


def test_debug_query_does_not_build_prompt_when_no_chunks_pass_threshold(client):
    upload = client.post(
        "/api/v1/documents/upload",
        files={"file": ("policy.txt", b"Alpha travel reimbursement requires invoices.", "text/plain")},
    )
    assert upload.status_code == 200

    response = client.post(
        "/api/v1/rag/debug-query",
        json={
            "question": "zzzzzz unrelated",
            "use_llm": True,
            "min_final_score": 0.99,
            "final_top_k": 5,
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["selected_chunks"] == []
    assert body["prompt"] is None
    assert body["llm"] == {
        "used": False,
        "model": None,
        "latency_ms": None,
        "answer": "根据当前资料无法确定。",
        "error": None,
    }


def _expected_final_score(candidate, profile):
    weighted_scores = [
        (profile["vector_weight"], candidate["vector_score"]),
        (profile["keyword_weight"], candidate["keyword_score"]),
        (profile["trgm_weight"], candidate["trgm_score"]),
    ]
    active_scores = [(weight, score) for weight, score in weighted_scores if weight > 0 and score > 0]
    active_weight = sum(weight for weight, _ in active_scores)
    return sum(weight * score for weight, score in active_scores) / active_weight
