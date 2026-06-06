import os
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient


@pytest.fixture()
def auth_client(tmp_path, monkeypatch) -> Iterator[TestClient]:
    db_path = tmp_path / "rag-auth-test.db"
    storage_dir = tmp_path / "uploads"

    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv("DATABASE_URL", f"sqlite+pysqlite:///{db_path}")
    monkeypatch.setenv("STORAGE_PROVIDER", "local")
    monkeypatch.setenv("LOCAL_STORAGE_DIR", str(storage_dir))
    monkeypatch.setenv("EMBEDDING_PROVIDER", "fake")
    monkeypatch.setenv("EMBEDDING_DIMENSION", "8")
    monkeypatch.setenv("ALLOWED_UPLOAD_EXTENSIONS", "txt,md,pdf")
    monkeypatch.setenv("LLM_PROVIDER", "zhipu")
    monkeypatch.setenv("ZHIPUAI_API_KEY", "test-key")
    monkeypatch.setenv("AUTH_SESSION_SECRET", "test-secret")
    monkeypatch.setenv("SUPER_ADMIN_USERNAME", "admin")
    monkeypatch.setenv("SUPER_ADMIN_PASSWORD", "admin-pass")
    monkeypatch.setenv("NORMAL_USER_USERNAME", "user")
    monkeypatch.setenv("NORMAL_USER_PASSWORD", "user-pass")

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


def test_login_me_and_logout(auth_client):
    response = auth_client.post("/api/v1/auth/login", json={"username": "admin", "password": "admin-pass"})
    assert response.status_code == 200
    assert response.json() == {"username": "admin", "role": "SUPER_ADMIN"}
    assert "rag_session" in response.headers["set-cookie"]

    me_response = auth_client.get("/api/v1/auth/me")
    assert me_response.status_code == 200
    assert me_response.json() == {"username": "admin", "role": "SUPER_ADMIN"}

    logout_response = auth_client.post("/api/v1/auth/logout")
    assert logout_response.status_code == 200
    assert auth_client.get("/api/v1/auth/me").status_code == 401


def test_invalid_login_is_rejected(auth_client):
    response = auth_client.post("/api/v1/auth/login", json={"username": "admin", "password": "wrong"})

    assert response.status_code == 401


def test_me_requires_login(auth_client):
    response = auth_client.get("/api/v1/auth/me")

    assert response.status_code == 401


def test_normal_user_cannot_access_super_admin_rag_tools(auth_client):
    login_as(auth_client, "user", "user-pass")

    response = auth_client.post("/api/v1/rag/debug-query", json={"question": "报销材料", "use_llm": False})

    assert response.status_code == 403


def test_super_admin_can_access_debug_query(auth_client):
    login_as(auth_client, "admin", "admin-pass")

    response = auth_client.post("/api/v1/rag/debug-query", json={"question": "报销材料", "use_llm": False})

    assert response.status_code == 200
    assert response.json()["question"] == "报销材料"


def test_user_search_returns_per_chunk_answers_and_context(auth_client, monkeypatch):
    from app.core.database import get_session
    from app.models.document import RagChunk, RagDocument, RagDocumentVersion, RagQueryFeedback
    from app.schemas.rag import SearchResultAnswerStatus
    from app.services.rag_search_service import AnswerBatch

    def fake_generate_result_answers(settings, prompt):
        assert "每条 answer 只能根据该条结果" in prompt
        assert "员工出差前需要完成审批。" in prompt
        assert "住宿费用还需要酒店水单。" in prompt
        return AnswerBatch(
            answers_by_rank={1: (SearchResultAnswerStatus.ANSWERED, "差旅报销需要提供发票、行程单、审批记录。")},
            latency_ms=12,
            raw_text='{"results":[]}',
        )

    monkeypatch.setattr("app.services.rag_search_service.generate_result_answers", fake_generate_result_answers)
    seed_reimbursement_document()
    login_as(auth_client, "user", "user-pass")

    response = auth_client.post(
        "/api/v1/rag/search",
        json={"question": "差旅报销需要什么材料", "use_llm": True},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "COMPLETED"
    assert 1 <= len(body["results"]) <= 5
    first = body["results"][0]
    assert first["answer_status"] == "ANSWERED"
    assert first["answer"] == "差旅报销需要提供发票、行程单、审批记录。"
    assert first["hit_content"] == "差旅报销需要提供发票、行程单、审批记录。"
    assert first["before_context"] == "员工出差前需要完成审批。"
    assert first["after_context"] == "住宿费用还需要酒店水单。"
    assert first["query_candidate_id"]

    feedback_response = auth_client.post(
        f"/api/v1/rag/search/{body['query_log_id']}/feedback",
        json={
            "rating": "PARTIALLY_HELPFUL",
            "comment": "找到了相关制度",
            "expected_answer": "还需要说明住宿材料",
        },
    )
    assert feedback_response.status_code == 200
    feedback = feedback_response.json()
    assert feedback["username"] == "user"
    assert feedback["role"] == "NORMAL_USER"
    assert feedback["rating"] == "PARTIALLY_HELPFUL"

    with get_session() as db:
        saved = db.get(RagQueryFeedback, feedback["id"])
        assert saved is not None
        assert saved.query_log_id == body["query_log_id"]


def test_user_search_without_recall_has_stable_empty_results(auth_client):
    login_as(auth_client, "user", "user-pass")

    response = auth_client.post("/api/v1/rag/search", json={"question": "不存在的问题", "use_llm": True})

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "NO_RECALL"
    assert body["results"] == []


def seed_reimbursement_document() -> None:
    from app.core.database import get_session
    from app.models.document import RagChunk, RagDocument, RagDocumentVersion

    with get_session() as db:
        document = RagDocument(name="公司报销制度.pdf", file_type="pdf", file_size=100, status="ACTIVE")
        db.add(document)
        db.flush()

        version = RagDocumentVersion(
            document_id=document.id,
            version_no=1,
            file_hash="hash",
            original_filename=document.name,
            status="COMPLETED",
            chunk_count=4,
        )
        db.add(version)
        db.flush()
        document.current_version_id = version.id

        parent = RagChunk(
            document_id=document.id,
            document_version_id=version.id,
            chunk_type="PARENT",
            chunk_index=0,
            child_index=None,
            section_title="差旅报销",
            heading_path="报销制度 / 差旅报销",
            content="员工出差前需要完成审批。\n差旅报销需要提供发票、行程单、审批记录。\n住宿费用还需要酒店水单。",
            content_with_context=(
                "报销制度 / 差旅报销\n\n"
                "员工出差前需要完成审批。\n差旅报销需要提供发票、行程单、审批记录。\n住宿费用还需要酒店水单。"
            ),
            search_text=(
                "[heading_path] 报销制度 / 差旅报销\n[section_title] 差旅报销\n[content]\n"
                "员工出差前需要完成审批。\n差旅报销需要提供发票、行程单、审批记录。\n住宿费用还需要酒店水单。"
            ),
        )
        db.add(parent)
        db.flush()

        for index, content in enumerate(
            [
                "员工出差前需要完成审批。",
                "差旅报销需要提供发票、行程单、审批记录。",
                "住宿费用还需要酒店水单。",
            ]
        ):
            db.add(
                RagChunk(
                    document_id=document.id,
                    document_version_id=version.id,
                    chunk_type="CHILD",
                    parent_chunk_id=parent.id,
                    chunk_index=0,
                    child_index=index,
                    section_title="差旅报销",
                    heading_path="报销制度 / 差旅报销",
                    content=content,
                    content_with_context=f"报销制度 / 差旅报销\n\n{content}",
                    search_text=f"[heading_path] 报销制度 / 差旅报销\n[section_title] 差旅报销\n[content]\n{content}",
                )
            )
        db.commit()


def login_as(client: TestClient, username: str, password: str) -> None:
    response = client.post("/api/v1/auth/login", json={"username": username, "password": password})
    assert response.status_code == 200
