from collections import defaultdict
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.document import RagSynonymGroup, RagSynonymTerm
from app.schemas.rag import (
    NormalizeQueryRequest,
    NormalizeQueryResponse,
    SynonymGroupCreate,
    SynonymGroupListResponse,
    SynonymGroupResponse,
    SynonymGroupUpdate,
    SynonymTermCreate,
    SynonymTermResponse,
    SynonymTermUpdate,
)
from app.services.rag_debug.query_normalization import load_active_synonym_groups, normalize_query_text


def list_synonym_groups(db: Session) -> SynonymGroupListResponse:
    groups = list(db.scalars(select(RagSynonymGroup).order_by(RagSynonymGroup.updated_at.desc(), RagSynonymGroup.id.desc())))
    terms_by_group = _terms_by_group(db, [group.id for group in groups])
    return SynonymGroupListResponse(items=[_group_response(group, terms_by_group[group.id]) for group in groups])


def create_synonym_group(db: Session, request: SynonymGroupCreate) -> SynonymGroupResponse:
    now = datetime.utcnow()
    group = RagSynonymGroup(
        name=request.name.strip(),
        description=request.description.strip() if request.description else None,
        status=request.status,
        created_at=now,
        updated_at=now,
    )
    db.add(group)
    db.flush()

    for term_request in request.terms:
        db.add(_new_term(group.id, term_request, now))

    db.commit()
    db.refresh(group)
    return _group_response(group, _terms_by_group(db, [group.id])[group.id])


def update_synonym_group(db: Session, group_id: int, request: SynonymGroupUpdate) -> SynonymGroupResponse | None:
    group = db.get(RagSynonymGroup, group_id)
    if group is None:
        return None
    if request.name is not None:
        group.name = request.name.strip()
    if request.description is not None:
        group.description = request.description.strip() or None
    if request.status is not None:
        group.status = request.status
    group.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(group)
    return _group_response(group, _terms_by_group(db, [group.id])[group.id])


def add_synonym_term(db: Session, group_id: int, request: SynonymTermCreate) -> SynonymTermResponse | None:
    group = db.get(RagSynonymGroup, group_id)
    if group is None:
        return None
    now = datetime.utcnow()
    term = _new_term(group.id, request, now)
    group.updated_at = now
    db.add(term)
    db.commit()
    db.refresh(term)
    return SynonymTermResponse.model_validate(term)


def update_synonym_term(db: Session, term_id: int, request: SynonymTermUpdate) -> SynonymTermResponse | None:
    term = db.get(RagSynonymTerm, term_id)
    if term is None:
        return None
    if request.term is not None:
        term.term = request.term.strip()
    if request.term_type is not None:
        term.term_type = request.term_type
    if request.language is not None:
        term.language = request.language.strip() or "mixed"
    if request.weight is not None:
        term.weight = request.weight
    if request.status is not None:
        term.status = request.status
    term.updated_at = datetime.utcnow()
    group = db.get(RagSynonymGroup, term.group_id)
    if group is not None:
        group.updated_at = term.updated_at
    db.commit()
    db.refresh(term)
    return SynonymTermResponse.model_validate(term)


def normalize_query(db: Session, request: NormalizeQueryRequest) -> NormalizeQueryResponse:
    normalized = normalize_query_text(request.question, synonym_groups=load_active_synonym_groups(db))
    return NormalizeQueryResponse(
        original_text=normalized.original_text,
        normalized_text=normalized.normalized_text,
        expanded_text=normalized.expanded_text,
        applied_synonym_groups=list(normalized.applied_synonym_groups),
    )


def _new_term(group_id: int, request: SynonymTermCreate, now: datetime) -> RagSynonymTerm:
    # 权重（weight）先持久化供后续排序/调参使用；当前查询扩展只按 ACTIVE 状态决定是否纳入。
    return RagSynonymTerm(
        group_id=group_id,
        term=request.term.strip(),
        term_type=request.term_type,
        language=request.language.strip() or "mixed",
        weight=request.weight,
        status=request.status,
        created_at=now,
        updated_at=now,
    )


def _terms_by_group(db: Session, group_ids: list[int]) -> dict[int, list[RagSynonymTerm]]:
    terms_by_group: dict[int, list[RagSynonymTerm]] = defaultdict(list)
    if not group_ids:
        return terms_by_group
    rows = db.scalars(
        select(RagSynonymTerm)
        .where(RagSynonymTerm.group_id.in_(group_ids))
        .order_by(RagSynonymTerm.group_id.asc(), RagSynonymTerm.term_type.asc(), RagSynonymTerm.id.asc())
    )
    for term in rows:
        terms_by_group[term.group_id].append(term)
    return terms_by_group


def _group_response(group: RagSynonymGroup, terms: list[RagSynonymTerm]) -> SynonymGroupResponse:
    return SynonymGroupResponse(
        id=group.id,
        name=group.name,
        description=group.description,
        status=group.status,
        terms=[SynonymTermResponse.model_validate(term) for term in terms],
        created_at=group.created_at,
        updated_at=group.updated_at,
    )
