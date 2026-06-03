import numpy as np


def test_query_normalization_removes_colloquial_noise_and_expands_stack_synonyms():
    from app.services.rag_debug_service import QuerySynonymGroup, _normalize_query

    normalized = _normalize_query(
        "告诉我我的rag技术栈是啥 React Vite TanStack",
        synonym_groups=[
            QuerySynonymGroup(name="技术栈", terms=("技术栈", "技术选型", "技术方案", "技术框架"))
        ],
    )

    assert "告诉我" not in normalized.normalized_text
    assert "我的" not in normalized.normalized_text
    assert "是啥" not in normalized.normalized_text
    assert "rag" in normalized.normalized_text
    assert "React" in normalized.normalized_text
    assert "Vite" in normalized.normalized_text
    assert "TanStack" in normalized.normalized_text
    assert "技术选型" in normalized.expanded_text
    assert "技术方案" in normalized.expanded_text
    assert "技术框架" in normalized.expanded_text


def test_keyword_score_uses_normalized_query_synonyms():
    from app.services.rag_debug_service import QuerySynonymGroup, _keyword_score, _normalize_query

    normalized_query = _normalize_query(
        "告诉我我的rag技术栈是啥",
        synonym_groups=[
            QuerySynonymGroup(name="技术栈", terms=("技术栈", "技术选型", "技术方案", "技术框架"))
        ],
    )

    score = _keyword_score(
        "告诉我我的rag技术栈是啥",
        "RAG 知识库问答系统前端架构设计.md / 3. 技术选型\n\n"
        "```txt\n框架：React\n构建工具：Vite\n状态管理：TanStack Query + React local state\n```",
        normalized_query=normalized_query,
    )

    assert score >= 0.6


def test_vector_scoring_accepts_pgvector_array_embeddings():
    from app.services.rag_debug_service import _has_embedding, _vector_score

    embedding = np.array([0.2, 0.4, 0.6])

    assert _has_embedding(embedding) is True
    assert _vector_score([0.2, 0.4, 0.6], embedding) == 1
