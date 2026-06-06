from dataclasses import dataclass, field

from app.models.document import RagChunk


@dataclass
class SearchProfile:
    id: int | None
    name: str
    mode: str
    vector_top_k: int
    keyword_top_k: int
    trgm_top_k: int
    final_top_k: int
    vector_weight: float
    keyword_weight: float
    trgm_weight: float
    min_final_score: float


@dataclass
class CandidateDraft:
    chunk: RagChunk
    document_name: str
    vector_score: float = 0
    keyword_score: float = 0
    trgm_score: float = 0
    # 标题分数是结构化信号，只用于保护召回，不改变 final_score，便于排查排序语义。
    heading_score: float = 0
    final_score: float = 0
    selected_for_prompt: bool = False
    rank: int = 0
    # recall_channels 记录候选来自哪些召回通道，便于调试和前端展示通道来源。
    recall_channels: set[str] = field(default_factory=set)


@dataclass(frozen=True)
class NormalizedQuery:
    original_text: str
    normalized_text: str
    expanded_text: str
    applied_synonym_groups: tuple[str, ...] = ()
    applied_synonym_terms: tuple[str, ...] = ()


@dataclass(frozen=True)
class QuerySynonymGroup:
    name: str
    terms: tuple[str, ...]
