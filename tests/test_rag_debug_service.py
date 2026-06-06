import numpy as np


def test_query_normalization_removes_colloquial_noise_and_expands_stack_synonyms():
    from app.services.rag_debug.query_normalization import normalize_query_text
    from app.services.rag_debug.types import QuerySynonymGroup

    normalized = normalize_query_text(
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
    from app.services.rag_debug.query_normalization import normalize_query_text
    from app.services.rag_debug.scoring import keyword_score
    from app.services.rag_debug.types import QuerySynonymGroup

    normalized_query = normalize_query_text(
        "告诉我我的rag技术栈是啥",
        synonym_groups=[
            QuerySynonymGroup(name="技术栈", terms=("技术栈", "技术选型", "技术方案", "技术框架"))
        ],
    )

    score = keyword_score(
        "告诉我我的rag技术栈是啥",
        "RAG 知识库问答系统前端架构设计.md / 3. 技术选型\n\n"
        "```txt\n框架：React\n构建工具：Vite\n状态管理：TanStack Query + React local state\n```",
        normalized_query=normalized_query,
    )

    assert score >= 0.6


def test_field_aware_keyword_score_boosts_section_heading_over_body_scatter():
    from app.models.document import RagChunk
    from app.services.rag_debug.query_normalization import normalize_query_text
    from app.services.rag_debug.scoring import field_aware_keyword_score
    from app.services.rag_debug.types import QuerySynonymGroup

    normalized_query = normalize_query_text(
        "AI智能获客技术栈是什么",
        synonym_groups=[
            QuerySynonymGroup(name="技术栈", terms=("技术栈", "技术选型", "技术方案", "技术框架"))
        ],
    )
    section_match = RagChunk(
        document_id=1,
        document_version_id=1,
        chunk_type="CHILD",
        chunk_index=0,
        child_index=0,
        section_title="3. 技术选型",
        heading_path="AI智能获客 / 系统设计 / 3. 技术选型",
        content="前端采用 React、Vite 和 TanStack Query。",
    )
    body_scatter = RagChunk(
        document_id=1,
        document_version_id=1,
        chunk_type="CHILD",
        chunk_index=1,
        child_index=0,
        section_title="页面结构",
        heading_path="AI智能获客 / 页面结构",
        content="这里散落提到技术、方案、框架、选择，但没有当前架构清单的真实内容。",
    )

    section_score = field_aware_keyword_score(
        "AI智能获客技术栈是什么",
        section_match,
        document_name="文档.md",
        normalized_query=normalized_query,
    )
    body_score = field_aware_keyword_score(
        "AI智能获客技术栈是什么",
        body_scatter,
        document_name="AI获客数据权限相关.md",
        normalized_query=normalized_query,
    )

    assert section_score >= 0.9
    assert section_score > body_score


def test_keyword_score_does_not_match_short_ascii_query_inside_longer_words():
    from app.models.document import RagChunk
    from app.services.rag_debug.query_normalization import normalize_query_text
    from app.services.rag_debug.scoring import field_aware_keyword_score
    from app.services.rag_debug.types import QuerySynonymGroup

    normalized_query = normalize_query_text(
        "AI智能获客技术栈是什么",
        synonym_groups=[
            QuerySynonymGroup(name="技术栈", terms=("技术栈", "技术选型", "技术方案", "技术框架"))
        ],
    )
    irrelevant_code_chunk = RagChunk(
        document_id=1,
        document_version_id=1,
        chunk_type="CHILD",
        chunk_index=0,
        child_index=0,
        section_title="获取用户有权查看的创建人ID列表",
        heading_path="获取用户有权查看的创建人ID列表",
        content="```Plain Text\nDataIsolationService.get_allowed_creator_ids(user: User) -> List[int]\n```",
    )
    technology_stack_chunk = RagChunk(
        document_id=1,
        document_version_id=1,
        chunk_type="CHILD",
        chunk_index=1,
        child_index=0,
        section_title="1.2 技术栈",
        heading_path="AI获客数据权限相关 / 一、项目概览 / 1.2 技术栈",
        content="|层级|技术|\n|---|---|\n|后端|FastAPI + TortoiseORM + PostgreSQL + Redis|",
    )

    irrelevant_score = field_aware_keyword_score(
        "AI智能获客技术栈是什么",
        irrelevant_code_chunk,
        document_name="AI获客数据权限相关.md",
        normalized_query=normalized_query,
    )
    stack_score = field_aware_keyword_score(
        "AI智能获客技术栈是什么",
        technology_stack_chunk,
        document_name="AI获客数据权限相关.md",
        normalized_query=normalized_query,
    )

    assert irrelevant_score < 0.7
    assert stack_score > irrelevant_score


def test_keyword_score_does_not_let_ai_token_alone_dominate_mixed_query():
    from app.models.document import RagChunk
    from app.services.rag_debug.query_normalization import normalize_query_text
    from app.services.rag_debug.scoring import field_aware_keyword_score
    from app.services.rag_debug.types import QuerySynonymGroup

    normalized_query = normalize_query_text(
        "AI智能获客技术栈是什么",
        synonym_groups=[
            QuerySynonymGroup(name="技术栈", terms=("技术栈", "技术选型", "技术方案", "技术框架"))
        ],
    )
    reference_link_chunk = RagChunk(
        document_id=1,
        document_version_id=1,
        chunk_type="CHILD",
        chunk_index=0,
        child_index=0,
        section_title="9.1 角色权限清单",
        heading_path="九、重要参考文档 / 9.1 角色权限清单",
        content="> 文档位置: `ai-talk/prd/paas/角色权限清单.md`\n>",
    )

    score = field_aware_keyword_score(
        "AI智能获客技术栈是什么",
        reference_link_chunk,
        document_name="AI获客数据权限相关.md",
        normalized_query=normalized_query,
    )

    assert score < 0.7


def test_topicless_synonym_match_does_not_tie_topic_specific_stack_chunk():
    from app.models.document import RagChunk
    from app.services.rag_debug.query_normalization import normalize_query_text
    from app.services.rag_debug.scoring import field_aware_keyword_score
    from app.services.rag_debug.types import QuerySynonymGroup

    normalized_query = normalize_query_text(
        "AI智能获客技术栈是什么",
        synonym_groups=[
            QuerySynonymGroup(name="技术栈", terms=("技术栈", "技术选型", "技术方案", "技术框架"))
        ],
    )
    generic_stack_chunk = RagChunk(
        document_id=1,
        document_version_id=1,
        chunk_type="CHILD",
        chunk_index=0,
        child_index=0,
        section_title="3. 技术选型",
        heading_path="3. 技术选型",
        content="框架：React\n构建工具：Vite\n状态管理：TanStack Query",
    )
    topic_stack_chunk = RagChunk(
        document_id=2,
        document_version_id=2,
        chunk_type="CHILD",
        chunk_index=1,
        child_index=0,
        section_title="1.2 技术栈",
        heading_path="AI获客数据权限相关 / 一、项目概览 / 1.2 技术栈",
        content="|层级|技术|\n|---|---|\n|后端|FastAPI + PostgreSQL|",
    )

    generic_score = field_aware_keyword_score(
        "AI智能获客技术栈是什么",
        generic_stack_chunk,
        document_name="RAG 知识库问答系统前端架构设计.md",
        normalized_query=normalized_query,
    )
    topic_score = field_aware_keyword_score(
        "AI智能获客技术栈是什么",
        topic_stack_chunk,
        document_name="AI获客数据权限相关.md",
        normalized_query=normalized_query,
    )

    assert generic_score < 0.7
    assert topic_score > generic_score


def test_topic_only_match_does_not_tie_synonym_intent_chunk():
    from app.models.document import RagChunk
    from app.services.rag_debug.query_normalization import normalize_query_text
    from app.services.rag_debug.scoring import field_aware_keyword_score
    from app.services.rag_debug.types import QuerySynonymGroup

    normalized_query = normalize_query_text(
        "告诉我我的rag技术栈是啥",
        synonym_groups=[
            QuerySynonymGroup(name="技术栈", terms=("技术栈", "技术选型", "技术方案", "技术框架"))
        ],
    )
    topic_only_chunk = RagChunk(
        document_id=1,
        document_version_id=1,
        chunk_type="CHILD",
        chunk_index=0,
        child_index=0,
        section_title="2. 前端目标",
        heading_path="2. 前端目标",
        content="文档上传和管理\nRAG 问答\n检索调试\n用户反馈",
    )
    intent_chunk = RagChunk(
        document_id=1,
        document_version_id=1,
        chunk_type="CHILD",
        chunk_index=1,
        child_index=0,
        section_title="3. 技术选型",
        heading_path="3. 技术选型",
        content="框架：React\n构建工具：Vite\n状态管理：TanStack Query",
    )

    topic_only_score = field_aware_keyword_score(
        "告诉我我的rag技术栈是啥",
        topic_only_chunk,
        document_name="RAG 知识库问答系统前端架构设计.md",
        normalized_query=normalized_query,
    )
    intent_score = field_aware_keyword_score(
        "告诉我我的rag技术栈是啥",
        intent_chunk,
        document_name="RAG 知识库问答系统前端架构设计.md",
        normalized_query=normalized_query,
    )

    assert topic_only_score < 0.7
    assert intent_score > topic_only_score


def test_select_final_chunks_protects_keyword_and_heading_matches_from_vector_noise():
    from app.models.document import RagChunk
    from app.services.rag_debug.candidate_selection import select_final_chunks
    from app.services.rag_debug.types import CandidateDraft, SearchProfile

    profile = SearchProfile(
        id=None,
        name="默认混合检索",
        mode="HYBRID",
        vector_top_k=20,
        keyword_top_k=20,
        trgm_top_k=20,
        final_top_k=3,
        vector_weight=0.65,
        keyword_weight=0.25,
        trgm_weight=0.10,
        min_final_score=0.55,
    )

    def make_candidate(chunk_id: int, *, final_score: float, vector_score: float = 0, keyword_score: float = 0):
        return CandidateDraft(
            chunk=RagChunk(
                id=chunk_id,
                document_id=1,
                document_version_id=1,
                chunk_type="CHILD",
                parent_chunk_id=chunk_id + 1000,
                chunk_index=chunk_id,
                child_index=0,
                content=f"chunk {chunk_id}",
            ),
            document_name="doc.md",
            vector_score=vector_score,
            keyword_score=keyword_score,
            final_score=final_score,
        )

    # 前四个候选模拟纯 vector 高分噪声；最后两个分别模拟 keyword/heading 强命中。
    candidates = [
        make_candidate(1, final_score=0.99, vector_score=0.99),
        make_candidate(2, final_score=0.98, vector_score=0.98),
        make_candidate(3, final_score=0.97, vector_score=0.97),
        make_candidate(4, final_score=0.96, vector_score=0.96),
        make_candidate(100, final_score=0.70, keyword_score=0.95),
        make_candidate(101, final_score=0.60, keyword_score=0.20),
    ]
    # heading_score 不参与 final_score 加权，只用于结构化标题命中的保护槽。
    candidates[-1].heading_score = 0.95

    selected_ids = {candidate.chunk.id for candidate in select_final_chunks(candidates, profile=profile)}

    assert {100, 101}.issubset(selected_ids)
    assert len(selected_ids) == 3


def test_protected_recall_candidates_are_limited_to_strong_top_three():
    from app.models.document import RagChunk
    from app.services.rag_debug.candidate_selection import top_heading_match_candidates, top_keyword_match_candidates
    from app.services.rag_debug.types import CandidateDraft

    def make_candidate(chunk_id: int, *, keyword_score: float = 0, heading_score: float = 0, final_score: float = 0):
        candidate = CandidateDraft(
            chunk=RagChunk(
                id=chunk_id,
                document_id=1,
                document_version_id=1,
                chunk_type="CHILD",
                parent_chunk_id=chunk_id + 1000,
                chunk_index=chunk_id,
                child_index=0,
                content=f"chunk {chunk_id}",
            ),
            document_name="doc.md",
            keyword_score=keyword_score,
            final_score=final_score,
        )
        candidate.heading_score = heading_score
        return candidate

    candidates = [
        make_candidate(1, keyword_score=0.99, heading_score=0.71, final_score=0.70),
        make_candidate(2, keyword_score=0.98, heading_score=0.99, final_score=0.69),
        make_candidate(3, keyword_score=0.97, heading_score=0.98, final_score=0.68),
        make_candidate(4, keyword_score=0.96, heading_score=0.97, final_score=0.99),
        make_candidate(5, keyword_score=0.69, heading_score=0.69, final_score=1.00),
    ]

    assert [candidate.chunk.id for candidate in top_keyword_match_candidates(candidates)] == [1, 2, 3]
    assert [candidate.chunk.id for candidate in top_heading_match_candidates(candidates)] == [2, 3, 4]


def test_select_final_chunks_applies_threshold_parent_dedupe_and_low_information_filter():
    from app.models.document import RagChunk
    from app.services.rag_debug.candidate_selection import select_final_chunks
    from app.services.rag_debug.types import CandidateDraft, SearchProfile

    profile = SearchProfile(
        id=None,
        name="默认混合检索",
        mode="HYBRID",
        vector_top_k=20,
        keyword_top_k=20,
        trgm_top_k=20,
        final_top_k=3,
        vector_weight=0.65,
        keyword_weight=0.25,
        trgm_weight=0.10,
        min_final_score=0.55,
    )

    def make_candidate(chunk_id: int, *, parent_id: int, content: str, final_score: float):
        return CandidateDraft(
            chunk=RagChunk(
                id=chunk_id,
                document_id=1,
                document_version_id=1,
                chunk_type="CHILD",
                parent_chunk_id=parent_id,
                chunk_index=chunk_id,
                child_index=0,
                content=content,
            ),
            document_name="doc.md",
            vector_score=final_score,
            final_score=final_score,
        )

    candidates = [
        make_candidate(1, parent_id=10, content="valid first chunk", final_score=0.99),
        make_candidate(2, parent_id=10, content="same parent should be skipped", final_score=0.98),
        make_candidate(3, parent_id=30, content="below score threshold", final_score=0.54),
        make_candidate(4, parent_id=40, content="---", final_score=0.96),
        make_candidate(5, parent_id=50, content="valid fallback chunk", final_score=0.80),
    ]

    selected_ids = [candidate.chunk.id for candidate in select_final_chunks(candidates, profile=profile)]

    assert selected_ids == [1, 5]


def test_field_aware_scoring_preserves_current_business_rule_outputs():
    from app.models.document import RagChunk
    from app.services.rag_debug.query_normalization import normalize_query_text
    from app.services.rag_debug.scoring import (
        field_aware_heading_score,
        field_aware_keyword_score,
        field_aware_trgm_score,
    )
    from app.services.rag_debug.types import QuerySynonymGroup

    normalized_query = normalize_query_text(
        "AI智能获客技术栈是什么",
        synonym_groups=[
            QuerySynonymGroup(name="技术栈", terms=("技术栈", "技术选型", "技术方案", "技术框架"))
        ],
    )
    stack_chunk = RagChunk(
        document_id=1,
        document_version_id=1,
        chunk_type="CHILD",
        chunk_index=0,
        child_index=0,
        section_title="1.2 技术栈",
        heading_path="AI获客数据权限相关 / 一、项目概览 / 1.2 技术栈",
        content="|层级|技术|\n|---|---|\n|后端|FastAPI + TortoiseORM + PostgreSQL + Redis|",
    )

    assert (
        field_aware_keyword_score(
            "AI智能获客技术栈是什么",
            stack_chunk,
            document_name="AI获客数据权限相关.md",
            normalized_query=normalized_query,
        )
        == 0.9
    )
    assert (
        field_aware_trgm_score(
            "AI智能获客技术栈是什么",
            stack_chunk,
            document_name="AI获客数据权限相关.md",
            normalized_query=normalized_query,
        )
        == 0.45
    )
    assert (
        field_aware_heading_score(
            "AI智能获客技术栈是什么",
            stack_chunk,
            document_name="AI获客数据权限相关.md",
            normalized_query=normalized_query,
        )
        == 0.9
    )


def test_directory_like_chunks_are_downweighted_but_tables_are_not():
    from app.models.document import RagChunk
    from app.services.rag_debug.scoring import quality_multiplier

    directory_chunk = RagChunk(
        document_id=1,
        document_version_id=1,
        chunk_type="CHILD",
        chunk_index=0,
        child_index=0,
        content="1. 前端技术栈\n2. 页面结构\n3. 状态管理\n4. 接口设计",
    )
    table_chunk = RagChunk(
        document_id=1,
        document_version_id=1,
        chunk_type="CHILD",
        chunk_index=1,
        child_index=0,
        content="|层级|技术|\n|---|---|\n|前端|React + Vite + TanStack Query|\n|后端|FastAPI + PostgreSQL|",
    )

    assert 0 < quality_multiplier(directory_chunk) < 1
    assert quality_multiplier(table_chunk) == 1


def test_vector_scoring_accepts_pgvector_array_embeddings():
    from app.services.rag_debug.scoring import has_embedding, vector_score

    embedding = np.array([0.2, 0.4, 0.6])

    assert has_embedding(embedding) is True
    assert vector_score([0.2, 0.4, 0.6], embedding) == 1


def test_profile_defaults_to_lexical_when_fake_embedding_provider_is_implicit(monkeypatch):
    from app.core.config import reset_settings_cache
    from app.schemas.rag import DebugQueryRequest
    from app.services.rag_debug_service import _profile_from_request

    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv("EMBEDDING_PROVIDER", "fake")
    reset_settings_cache()

    profile = _profile_from_request(DebugQueryRequest(question="Alpha reimbursement invoices"))

    assert profile.mode == "LEXICAL"
    assert profile.name == "本地关键词检索"
    assert profile.vector_top_k == 0
    assert profile.vector_weight == 0
