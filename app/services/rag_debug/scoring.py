import math
import re
from difflib import SequenceMatcher

from app.models.document import RagChunk
from app.services.chunker import clean_structural_text, is_meaningful_document_name, normalize_file_stem
from app.services.rag_debug.query_normalization import (
    CJK_STOP_CHARS,
    COLLOQUIAL_QUERY_NOISE,
    ascii_match_terms,
    ascii_match_token_set,
    dedupe_terms,
    is_ascii_term,
    normalize_query_text,
    query_exact_match_score,
    query_terms,
)
from app.services.rag_debug.scoring_rules import (
    DIRECTORY_LIKE_CHUNK_SCORE_MULTIPLIER,
    DIRECTORY_LIST_LIKE_LINE_RATIO,
    DIRECTORY_PROSE_LINE_MIN_CHARS,
    DIRECTORY_SHORT_LINE_MAX_CHARS,
    DIRECTORY_SHORT_LINE_RATIO,
    DIRECTORY_SINGLE_LINE_MAX_CHARS,
    DIRECTORY_SINGLE_LINE_MIN_MARKER_COUNT,
    INTENT_GATE_MIN_SCORE,
    KEYWORD_CONTENT_MIX_WEIGHT,
    KEYWORD_DOCUMENT_NAME_MIX_WEIGHT,
    KEYWORD_DOCUMENT_NAME_MULTIPLIER,
    KEYWORD_HEADING_BOOST,
    KEYWORD_HEADING_MIX_WEIGHT,
    KEYWORD_HEADING_SCORE_CAP,
    KEYWORD_SECTION_BOOST,
    KEYWORD_SECTION_MIX_WEIGHT,
    MIN_ASCII_MATCH_TERM_LENGTH,
    SCORE_DECIMAL_PLACES,
    TOPIC_GATE_MIN_SCORE,
    TOPICLESS_SYNONYM_SCORE_CAP,
    TRGM_DOCUMENT_NAME_MULTIPLIER,
    TRGM_HEADING_BOOST,
    TRGM_HEADING_SCORE_CAP,
    TRGM_SECTION_BOOST,
)
from app.services.rag_debug.types import CandidateDraft, NormalizedQuery, SearchProfile


def has_embedding(value) -> bool:
    return value is not None and len(value) > 0


def vector_score(query_embedding: list[float] | None, chunk_embedding) -> float:
    # 计算向量余弦相似度，返回一个 0 到 1 之间的分数。
    if not query_embedding or not has_embedding(chunk_embedding):
        return 0
    chunk_embedding = list(chunk_embedding)
    length = min(len(query_embedding), len(chunk_embedding))
    if length == 0:
        return 0
    # 两个向量可能长度不一样，为了能计算，取较短的长度。
    query = query_embedding[:length]
    chunk = chunk_embedding[:length]
    # 点积除以两个向量模长的乘积，即余弦相似度。
    dot = sum(left * right for left, right in zip(query, chunk, strict=True))
    query_norm = math.sqrt(sum(value * value for value in query))
    chunk_norm = math.sqrt(sum(value * value for value in chunk))

    if query_norm == 0 or chunk_norm == 0:
        return 0
    cosine_similarity = dot / (query_norm * chunk_norm)
    return round_score(_clamp(cosine_similarity))


def field_aware_keyword_score(
    question: str,
    chunk: RagChunk,
    document_name: str,
    *,
    normalized_query: NormalizedQuery | None = None,
) -> float:
    # 字段感知关键词得分：标题、章节、正文、有效文档名分别计分后再合并。
    normalized_query = normalized_query or normalize_query_text(question)
    query_variants = _query_variants(normalized_query)
    if not query_variants:
        return 0

    document_name_score = 0.0
    if is_meaningful_document_name(document_name):
        document_name_score = _max_keyword_score(query_variants, normalize_file_stem(document_name))

    heading_score = _max_keyword_score(query_variants, clean_structural_text(chunk.heading_path or ""))
    section_score = _max_keyword_score(query_variants, clean_structural_text(chunk.section_title or ""))
    content_score = _max_keyword_score(query_variants, chunk.content or "")

    # 权重混合得分保留多字段同时命中时的稳定收益。
    weighted_mix = (
        section_score * KEYWORD_SECTION_MIX_WEIGHT
        + heading_score * KEYWORD_HEADING_MIX_WEIGHT
        + content_score * KEYWORD_CONTENT_MIX_WEIGHT
        + document_name_score * KEYWORD_DOCUMENT_NAME_MIX_WEIGHT
    )
    raw_score = max(
        section_score * KEYWORD_SECTION_BOOST,
        min(heading_score * KEYWORD_HEADING_BOOST, KEYWORD_HEADING_SCORE_CAP),
        content_score,
        document_name_score * KEYWORD_DOCUMENT_NAME_MULTIPLIER,
        weighted_mix,
    )
    return round_score(
        apply_topic_gate(
            raw_score,
            normalized_query=normalized_query,
            document_name=document_name,
            chunk=chunk,
        )
    )


def field_aware_trgm_score(
    question: str,
    chunk: RagChunk,
    document_name: str,
    *,
    normalized_query: NormalizedQuery | None = None,
) -> float:
    normalized_query = normalized_query or normalize_query_text(question)
    query_variants = _query_variants(normalized_query)
    if not query_variants:
        return 0

    document_name_score = 0.0
    if is_meaningful_document_name(document_name):
        document_name_score = _max_trgm_score(query_variants, normalize_file_stem(document_name))

    heading_score = _max_trgm_score(query_variants, clean_structural_text(chunk.heading_path or ""))
    section_score = _max_trgm_score(query_variants, clean_structural_text(chunk.section_title or ""))
    content_score = _max_trgm_score(query_variants, chunk.content or "")

    raw_score = max(
        section_score * TRGM_SECTION_BOOST,
        min(heading_score * TRGM_HEADING_BOOST, TRGM_HEADING_SCORE_CAP),
        content_score,
        document_name_score * TRGM_DOCUMENT_NAME_MULTIPLIER,
    )
    return round_score(
        apply_topic_gate(
            raw_score,
            normalized_query=normalized_query,
            document_name=document_name,
            chunk=chunk,
        )
    )


def field_aware_heading_score(
    question: str,
    chunk: RagChunk,
    document_name: str,
    *,
    normalized_query: NormalizedQuery | None = None,
) -> float:
    # heading_score 只使用 heading_path 和 section_title，不看正文内容，专门表达结构化位置命中。
    normalized_query = normalized_query or normalize_query_text(question)
    query_variants = _query_variants(normalized_query)
    if not query_variants:
        return 0

    heading_score = _max_keyword_score(query_variants, clean_structural_text(chunk.heading_path or ""))
    section_score = _max_keyword_score(query_variants, clean_structural_text(chunk.section_title or ""))
    raw_score = max(
        section_score * KEYWORD_SECTION_BOOST,
        min(heading_score * KEYWORD_HEADING_BOOST, KEYWORD_HEADING_SCORE_CAP),
    )

    # 仍然经过 topic gate，避免“技术栈”等泛化同义词把主题不相关的标题误判为强命中。
    return round_score(
        apply_topic_gate(
            raw_score,
            normalized_query=normalized_query,
            document_name=document_name,
            chunk=chunk,
        )
    )


def apply_topic_gate(
    score: float,
    *,
    normalized_query: NormalizedQuery,
    document_name: str,
    chunk: RagChunk,
) -> float:
    if score <= TOPICLESS_SYNONYM_SCORE_CAP or not normalized_query.applied_synonym_groups:
        return score

    topic_text = _topic_query_text(normalized_query)
    topic_haystack = _topic_haystack(document_name=document_name, chunk=chunk)

    intent_score = _synonym_intent_score(normalized_query, topic_haystack)
    if intent_score < INTENT_GATE_MIN_SCORE:
        return min(score, TOPICLESS_SYNONYM_SCORE_CAP)

    if not topic_text:
        return score

    topic_score = _keyword_score_for_query(topic_text, topic_haystack.lower())
    if topic_score < TOPIC_GATE_MIN_SCORE:
        return min(score, TOPICLESS_SYNONYM_SCORE_CAP)
    return score


def _synonym_intent_score(normalized_query: NormalizedQuery, text: str) -> float:
    haystack = text.lower()
    return max(
        (_keyword_score_for_query(term, haystack) for term in normalized_query.applied_synonym_terms),
        default=0,
    )


def _topic_query_text(normalized_query: NormalizedQuery) -> str:
    topic = normalized_query.normalized_text
    removable_terms = sorted(
        dedupe_terms([*normalized_query.applied_synonym_terms, *normalized_query.applied_synonym_groups]),
        key=len,
        reverse=True,
    )
    for term in removable_terms:
        topic = re.sub(re.escape(term), "", topic, flags=re.IGNORECASE)
    for noise in (*COLLOQUIAL_QUERY_NOISE, "什么", "？", "?", "吗"):
        topic = topic.replace(noise, "")
    topic = re.sub(r"\s+", " ", topic).strip()
    return topic.strip(" ，,。.：:；;")


def _topic_haystack(*, document_name: str, chunk: RagChunk) -> str:
    parts: list[str] = []
    if is_meaningful_document_name(document_name):
        parts.append(normalize_file_stem(document_name))
    parts.extend(
        part
        for part in [
            clean_structural_text(chunk.heading_path or ""),
            clean_structural_text(chunk.section_title or ""),
            chunk.content or "",
        ]
        if part
    )
    return "\n".join(parts)


def _query_variants(normalized_query: NormalizedQuery) -> list[str]:
    return dedupe_terms([normalized_query.normalized_text, normalized_query.expanded_text])


def _max_keyword_score(queries: list[str], text: str) -> float:
    haystack = text.lower()
    if not haystack:
        return 0
    return max((_keyword_score_for_query(query, haystack) for query in queries if query.strip()), default=0)


def _max_trgm_score(queries: list[str], text: str) -> float:
    haystack = text.lower()
    if not haystack:
        return 0
    return max((_trgm_score_for_query(query, haystack) for query in queries if query.strip()), default=0)


def keyword_score(question: str, text: str, *, normalized_query: NormalizedQuery | None = None) -> float:
    normalized_query = normalized_query or normalize_query_text(question)
    haystack = text.lower()
    if not normalized_query.normalized_text or not haystack:
        return 0
    return max(
        _keyword_score_for_query(normalized_query.normalized_text, haystack),
        _keyword_score_for_query(normalized_query.expanded_text, haystack),
    )


def _keyword_score_for_query(query: str, haystack: str) -> float:
    query = query.strip().lower()
    if not query:
        return 0
    terms = query_terms(query)
    if not terms:
        return 0
    haystack_ascii_tokens = ascii_match_token_set(haystack)
    matched = sum(
        1
        for term in terms
        if (
            is_ascii_term(term)
            and term in haystack_ascii_tokens
        )
        or (
            not is_ascii_term(term)
            and term in haystack
        )
    )
    coverage = matched / len(terms)
    if query_exact_match_score(query, haystack, haystack_ascii_tokens) > 0:
        coverage = 1
    return round_score(
        max(
            _clamp(coverage),
            _character_coverage_score_for_query(query, haystack),
            _phrase_match_score(query, haystack),
        )
    )


def _phrase_match_score(query: str, haystack: str) -> float:
    phrases = _query_phrases(query)
    if not phrases:
        return 0
    haystack_ascii_tokens = ascii_match_token_set(haystack)
    if any(
        len(phrase) >= MIN_ASCII_MATCH_TERM_LENGTH and phrase in haystack_ascii_tokens
        if is_ascii_term(phrase)
        else phrase in haystack
        for phrase in phrases
    ):
        return 1
    return 0


def _query_phrases(query: str) -> list[str]:
    phrases: list[str] = []
    for part in re.split(r"\s+", query.lower()):
        phrases.extend(re.findall(r"[a-z0-9][a-z0-9.+#_-]{1,}", part))
        phrases.extend(
            phrase
            for phrase in re.findall(r"[\u4e00-\u9fff]{2,}", part)
            if not all(char in CJK_STOP_CHARS for char in phrase)
        )
    return dedupe_terms(phrases)


def trgm_score(question: str, text: str, *, normalized_query: NormalizedQuery | None = None) -> float:
    normalized_query = normalized_query or normalize_query_text(question)
    haystack = text.lower()
    if not normalized_query.normalized_text or not haystack:
        return 0
    return max(
        _trgm_score_for_query(normalized_query.normalized_text, haystack),
        _trgm_score_for_query(normalized_query.expanded_text, haystack),
    )


def _trgm_score_for_query(query: str, haystack: str) -> float:
    query = query.strip().lower()
    if not query:
        return 0
    if query in haystack:
        return 1
    return round_score(_clamp(SequenceMatcher(None, query, haystack).ratio()))


def character_coverage_score(question: str, text: str) -> float:
    normalized_query = normalize_query_text(question)
    return max(
        _character_coverage_score_for_query(normalized_query.normalized_text, text),
        _character_coverage_score_for_query(normalized_query.expanded_text, text),
    )


def _character_coverage_score_for_query(query: str, text: str) -> float:
    ascii_terms = ascii_match_terms(query)
    cjk_chars = {
        char
        for char in re.findall(r"[\u4e00-\u9fff]", query)
        if char not in CJK_STOP_CHARS
    }
    total_units = len(ascii_terms) + len(cjk_chars)
    if total_units == 0:
        return 0

    text_ascii_tokens = ascii_match_token_set(text)
    matched_ascii = sum(1 for term in ascii_terms if term in text_ascii_tokens)
    matched_cjk = sum(1 for char in cjk_chars if char in text)
    return round_score((matched_ascii + matched_cjk) / total_units)


def candidate_final_score(candidate: CandidateDraft, profile: SearchProfile) -> float:
    weighted_scores = (
        (profile.vector_weight, candidate.vector_score),
        (profile.keyword_weight, candidate.keyword_score),
        (profile.trgm_weight, candidate.trgm_score),
    )
    active_scores = [(weight, score) for weight, score in weighted_scores if weight > 0 and score > 0]
    active_weight = sum(weight for weight, _ in active_scores)
    if active_weight == 0:
        return 0
    raw_score = sum(weight * score for weight, score in active_scores) / active_weight
    return round_score(raw_score * quality_multiplier(candidate.chunk))


def quality_multiplier(chunk: RagChunk) -> float:
    if is_low_information_chunk(chunk):
        return 0
    if _is_directory_like_chunk(chunk):
        return DIRECTORY_LIKE_CHUNK_SCORE_MULTIPLIER
    return 1


def is_low_information_chunk(chunk: RagChunk) -> bool:
    # 判断 chunk 是否是低信息量，用于候选阶段过滤和最终质量系数兜底。
    content = (chunk.content or "").strip().replace("\\", "")
    if not content:
        return True
    # 过滤只由 Markdown 分隔符、表格竖线、代码围栏符号组成的片段，例如 --- 或 ```。
    if re.fullmatch(r"[\s`\-_*|:]+", content):
        return True
    # 转成小写后判断常见代码围栏开头，避免它们进入候选和 Prompt。
    return content.lower() in {"```", "```txt", "```text", "```plain text", "```python", "```json"}


def _is_directory_like_chunk(chunk: RagChunk) -> bool:
    content = (chunk.content or "").strip()
    if not content:
        return False
    if _looks_like_markdown_table(content):
        return False

    single_line_markers = re.findall(r"(?:^|[/\n]\s*)\d+[\.\、)]\s*", content)
    if (
        len(single_line_markers) >= DIRECTORY_SINGLE_LINE_MIN_MARKER_COUNT
        and len(content) <= DIRECTORY_SINGLE_LINE_MAX_CHARS
        and not re.search(r"[。！？；;]", content)
    ):
        return True

    lines = [line.strip() for line in content.splitlines() if line.strip()]
    if len(lines) < DIRECTORY_SINGLE_LINE_MIN_MARKER_COUNT:
        return False

    list_like_count = sum(1 for line in lines if _is_list_like_line(line))
    short_line_count = sum(1 for line in lines if len(line) <= DIRECTORY_SHORT_LINE_MAX_CHARS)
    prose_line_count = sum(
        1
        for line in lines
        if re.search(r"[。！？；;]", line) and len(line) > DIRECTORY_PROSE_LINE_MIN_CHARS
    )

    return (
        list_like_count / len(lines) >= DIRECTORY_LIST_LIKE_LINE_RATIO
        and short_line_count / len(lines) >= DIRECTORY_SHORT_LINE_RATIO
        and prose_line_count == 0
    )


def _looks_like_markdown_table(content: str) -> bool:
    lines = [line.strip() for line in content.splitlines() if line.strip()]
    if len(lines) < 2:
        return False
    return any("|" in line for line in lines) and any(
        re.fullmatch(r"\|?\s*:?-{3,}:?\s*(\|\s*:?-{3,}:?\s*)+\|?", line)
        for line in lines
    )


def _is_list_like_line(line: str) -> bool:
    cleaned = line.strip()
    return bool(
        re.match(r"^(\d+[\.\、)]|[一二三四五六七八九十]+[、.]|[-*•]|#{1,6}\s+)", cleaned)
    )


def _clamp(value: float) -> float:
    return max(0, min(1, value))


def round_score(value: float) -> float:
    # 保留固定小数位，减少前端展示和测试断言中的浮点噪声。
    return round(_clamp(value), SCORE_DECIMAL_PLACES)
