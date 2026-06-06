import re

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.document import RagSynonymGroup, RagSynonymTerm
from app.services.rag_debug.scoring_rules import MIN_ASCII_MATCH_TERM_LENGTH
from app.services.rag_debug.types import NormalizedQuery, QuerySynonymGroup

CJK_STOP_CHARS = set("的是了嘛吗呢啊呀么什请问和与或及在对从为")
COLLOQUIAL_QUERY_NOISE = ("告诉我", "我的", "是什么", "是啥")


def normalize_query_text(value: str, synonym_groups: list[QuerySynonymGroup] | None = None) -> NormalizedQuery:
    # 把用户输入的问题做“标准化 + 同义词扩展”，返回原始文本、清洗文本和扩展文本。
    normalized = value.strip()
    for noise in COLLOQUIAL_QUERY_NOISE:
        normalized = normalized.replace(noise, "")
    normalized = re.sub(r"\s+", " ", normalized).strip()

    expanded_terms: list[str] = []
    applied_groups: list[str] = []
    applied_terms: list[str] = []
    for group in synonym_groups or []:
        if not query_matches_synonym_group(normalized, group):
            continue
        applied_groups.append(group.name)
        applied_terms.extend(group.terms)
        expanded_terms.extend(term for term in group.terms if not contains_term(normalized, term))

    expanded = " ".join(dedupe_terms([part for part in [normalized, *expanded_terms] if part])).strip()
    return NormalizedQuery(
        original_text=value,
        normalized_text=normalized,
        expanded_text=expanded,
        applied_synonym_groups=tuple(dedupe_terms(applied_groups)),
        applied_synonym_terms=tuple(dedupe_terms(applied_terms)),
    )


def load_active_synonym_groups(db: Session) -> list[QuerySynonymGroup]:
    # 只加载 ACTIVE 词组和 ACTIVE 词项，避免禁用词项继续影响查询扩展。
    rows = db.execute(
        select(RagSynonymGroup.name, RagSynonymTerm.term)
        .join(RagSynonymTerm, RagSynonymTerm.group_id == RagSynonymGroup.id)
        .where(RagSynonymGroup.status == "ACTIVE", RagSynonymTerm.status == "ACTIVE")
        .order_by(RagSynonymGroup.id.asc(), RagSynonymTerm.term_type.asc(), RagSynonymTerm.id.asc())
    )
    terms_by_group: dict[str, list[str]] = {}
    for group_name, term in rows:
        terms_by_group.setdefault(group_name, []).append(term)
    return [
        QuerySynonymGroup(name=group_name, terms=tuple(dedupe_terms(terms)))
        for group_name, terms in terms_by_group.items()
        if terms
    ]


def query_matches_synonym_group(query: str, group: QuerySynonymGroup) -> bool:
    # 判断用户 query 是否命中同义词组中的任一词项。
    return any(contains_term(query, term) for term in group.terms)


def contains_term(value: str, term: str) -> bool:
    if not term:
        return False
    return term.lower() in value.lower()


def dedupe_terms(values: list[str] | tuple[str, ...]) -> list[str]:
    # 对一组字符串去重：忽略空白内容，并按小写形式判断重复。
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        normalized_value = value.strip()
        key = normalized_value.lower()
        if not normalized_value or key in seen:
            continue
        seen.add(key)
        result.append(normalized_value)
    return result


def query_terms(value: str) -> list[str]:
    # ASCII 词组和中文单字分开抽取，再合并成 keyword 覆盖率使用的 term 列表。
    ascii_terms = ascii_match_terms(value)
    cjk_terms = [
        char
        for char in re.findall(r"[\u4e00-\u9fff]", value)
        if char not in CJK_STOP_CHARS
    ]
    return ascii_terms + cjk_terms


def is_ascii_term(value: str) -> bool:
    return bool(re.fullmatch(r"[a-z0-9][a-z0-9.+#_-]*", value.lower()))


def ascii_match_terms(value: str) -> list[str]:
    # 匹配 ASCII 词，并把 node.js、RAG-system 这类复合词拆出可匹配的小词。
    terms: list[str] = []
    for raw_term in re.findall(r"[a-z0-9][a-z0-9.+#_-]*", value.lower()):
        terms.append(raw_term)
        # 只保留长度达到阈值的小词，避免 ai 这类短词造成误命中。
        terms.extend(
            part
            for part in re.split(r"[.+#_-]+", raw_term)
            if len(part) >= MIN_ASCII_MATCH_TERM_LENGTH
        )
    return dedupe_terms(terms)


def ascii_match_token_set(value: str) -> set[str]:
    return set(ascii_match_terms(value))


def query_exact_match_score(query: str, haystack: str, haystack_ascii_tokens: set[str]) -> float:
    # 计算 query 是否精确命中；ASCII 词使用 token 集合避免子串误命中。
    if not query:
        return 0
    if re.fullmatch(r"[a-z0-9][a-z0-9.+#_-]*", query):
        return 1 if query in haystack_ascii_tokens else 0
    return 1 if query in haystack else 0
