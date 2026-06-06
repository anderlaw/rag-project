from app.core.config import Settings
from app.models.document import RagQueryCandidate
from app.schemas.rag import SearchResultAnswerStatus
from app.services.rag_search_service import SearchResultDraft, _parse_answer_payload, build_result_prompt, generate_result_answers


def test_build_result_prompt_tells_llm_to_answer_partial_relevant_chunks():
    prompt = build_result_prompt(
        "rag技术栈是啥",
        [
            SearchResultDraft(
                candidate=RagQueryCandidate(
                    rank=1,
                    document_name="架构.md",
                    heading_path="技术选型",
                    content_snapshot="框架：React\n构建工具：Vite",
                ),
                before_context="",
                after_context="",
                answer_status=SearchResultAnswerStatus.LLM_DISABLED,
            )
        ],
    )

    assert "只要该条资料能回答用户问题的全部或一部分" in prompt
    assert "不能因为资料只覆盖部分答案就返回 NO_ANSWER" in prompt


def test_parse_answer_payload_keeps_non_empty_answer_when_status_casing_is_not_exact():
    parsed = _parse_answer_payload(
        '{"results":[{"rank":1,"answer_status":"answered","answer":"框架是 React，构建工具是 Vite。"}]}'
    )

    assert parsed[1] == (SearchResultAnswerStatus.ANSWERED, "框架是 React，构建工具是 Vite。")


def test_generate_result_answers_calls_minimax_openai_compatible_endpoint(monkeypatch):
    captured = {}

    class FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {
                "choices": [
                    {
                        "message": {
                            "content": '{"results":[{"rank":1,"answer_status":"ANSWERED","answer":"命中回答"}]}'
                        }
                    }
                ]
            }

    class FakeClient:
        def __init__(self, *, timeout):
            captured["timeout"] = timeout

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, traceback):
            return None

        def post(self, url, *, headers, json):
            captured["url"] = url
            captured["headers"] = headers
            captured["json"] = json
            return FakeResponse()

    monkeypatch.setattr("app.services.rag_search_service.httpx.Client", FakeClient)
    settings = Settings(
        _env_file=None,
        llm_provider="minimax",
        minimax_api_key="minimax-key",
        minimax_api_base_url="https://api.minimax.io/v1/",
        llm_model="MiniMax-M2.7",
        llm_timeout_seconds=30,
        auth_session_secret="test-secret",
        super_admin_username="admin",
        super_admin_password="admin-pass",
    )

    batch = generate_result_answers(settings, "prompt text")

    assert captured["timeout"] == 30
    assert captured["url"] == "https://api.minimax.io/v1/chat/completions"
    assert captured["headers"]["Authorization"] == "Bearer minimax-key"
    assert captured["json"] == {
        "model": "MiniMax-M2.7",
        "messages": [{"role": "user", "content": "prompt text"}],
        "temperature": settings.llm_temperature,
        "max_tokens": settings.llm_max_tokens,
    }
    assert batch.answers_by_rank[1] == (SearchResultAnswerStatus.ANSWERED, "命中回答")
