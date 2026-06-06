from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db, require_authenticated_user, require_super_admin
from app.core.auth import AuthUser
from app.schemas.rag import (
    CreateEvalCaseFromQueryLogRequest,
    CreateFailureCaseFromQueryLogRequest,
    DebugQueryRequest,
    DebugQueryResponse,
    EvalCaseResponse,
    FailureCaseResponse,
    NormalizeQueryRequest,
    NormalizeQueryResponse,
    QueryLogDetailResponse,
    SearchFeedbackRequest,
    SearchFeedbackResponse,
    SearchRequest,
    SearchResponse,
    SynonymGroupCreate,
    SynonymGroupListResponse,
    SynonymGroupResponse,
    SynonymGroupUpdate,
    SynonymTermCreate,
    SynonymTermResponse,
    SynonymTermUpdate,
)
from app.services.rag_debug_service import (
    create_eval_case_from_query_log,
    create_failure_case_from_query_log,
    get_query_log_detail,
    run_debug_query,
)
from app.services.rag_search_service import create_search_feedback, run_search
from app.services.synonym_service import (
    add_synonym_term,
    create_synonym_group,
    list_synonym_groups,
    normalize_query,
    update_synonym_group,
    update_synonym_term,
)

# 检索增强模块（RAG）路由：调试检索、查询日志和同义词管理的 HTTP 入口。
router = APIRouter(prefix="/rag", tags=["rag"])


# 调试查询入口，返回候选、Prompt、诊断信息和 query log 快照。
@router.post("/debug-query", response_model=DebugQueryResponse)
def debug_query(
    request: DebugQueryRequest,
    db: Session = Depends(get_db),
    _: AuthUser = Depends(require_super_admin),
) -> DebugQueryResponse:
    return run_debug_query(db, request)


@router.post("/search", response_model=SearchResponse)
def search_documents(
    request: SearchRequest,
    db: Session = Depends(get_db),
    _: AuthUser = Depends(require_authenticated_user),
) -> SearchResponse:
    return run_search(db, request)


@router.post("/search/{query_log_id}/feedback", response_model=SearchFeedbackResponse)
def submit_search_feedback(
    query_log_id: int,
    request: SearchFeedbackRequest,
    db: Session = Depends(get_db),
    user: AuthUser = Depends(get_current_user),
) -> SearchFeedbackResponse:
    feedback = create_search_feedback(db, query_log_id, request, user)
    if feedback is None:
        raise HTTPException(status_code=404, detail="query log not found")
    return feedback


# 查询规范化入口，用于查看清洗、同义词扩展和最终 expanded query。
@router.post("/normalize-query", response_model=NormalizeQueryResponse)
def normalize_query_endpoint(
    request: NormalizeQueryRequest,
    db: Session = Depends(get_db),
    _: AuthUser = Depends(require_super_admin),
) -> NormalizeQueryResponse:
    return normalize_query(db, request)


# 获取单条调试查询日志详情。
@router.get("/query-logs/{query_log_id}", response_model=QueryLogDetailResponse)
def query_log_detail(
    query_log_id: int,
    db: Session = Depends(get_db),
    _: AuthUser = Depends(require_super_admin),
) -> QueryLogDetailResponse:
    detail = get_query_log_detail(db, query_log_id)
    if detail is None:
        raise HTTPException(status_code=404, detail="query log not found")
    return detail


# 从 query log 生成失败样本，复用当次检索快照作为排查上下文。
@router.post("/query-logs/{query_log_id}/failure-cases", response_model=FailureCaseResponse)
def save_query_log_as_failure_case(
    query_log_id: int,
    request: CreateFailureCaseFromQueryLogRequest,
    db: Session = Depends(get_db),
    _: AuthUser = Depends(require_super_admin),
) -> FailureCaseResponse:
    failure_case = create_failure_case_from_query_log(db, query_log_id, request)
    if failure_case is None:
        raise HTTPException(status_code=404, detail="query log not found")
    return failure_case


# 从 query log 生成评测样本，保留问题和期望答案来源。
@router.post("/query-logs/{query_log_id}/eval-cases", response_model=EvalCaseResponse)
def save_query_log_as_eval_case(
    query_log_id: int,
    request: CreateEvalCaseFromQueryLogRequest,
    db: Session = Depends(get_db),
    _: AuthUser = Depends(require_super_admin),
) -> EvalCaseResponse:
    eval_case = create_eval_case_from_query_log(db, query_log_id, request)
    if eval_case is None:
        raise HTTPException(status_code=404, detail="query log not found")
    return eval_case


# 列出同义词组及组内词项。
@router.get("/synonyms", response_model=SynonymGroupListResponse)
def list_synonyms(
    db: Session = Depends(get_db),
    _: AuthUser = Depends(require_super_admin),
) -> SynonymGroupListResponse:
    return list_synonym_groups(db)


# 创建同义词组，并可同时写入初始词项。
@router.post("/synonyms", response_model=SynonymGroupResponse)
def create_synonym(
    request: SynonymGroupCreate,
    db: Session = Depends(get_db),
    _: AuthUser = Depends(require_super_admin),
) -> SynonymGroupResponse:
    return create_synonym_group(db, request)


# 更新同义词组元数据或启用状态。
@router.patch("/synonyms/{group_id}", response_model=SynonymGroupResponse)
def update_synonym(
    group_id: int,
    request: SynonymGroupUpdate,
    db: Session = Depends(get_db),
    _: AuthUser = Depends(require_super_admin),
) -> SynonymGroupResponse:
    group = update_synonym_group(db, group_id, request)
    if group is None:
        raise HTTPException(status_code=404, detail="synonym group not found")
    return group


# 向指定同义词组增加词项。
@router.post("/synonyms/{group_id}/terms", response_model=SynonymTermResponse)
def create_synonym_term(
    group_id: int,
    request: SynonymTermCreate,
    db: Session = Depends(get_db),
    _: AuthUser = Depends(require_super_admin),
) -> SynonymTermResponse:
    term = add_synonym_term(db, group_id, request)
    if term is None:
        raise HTTPException(status_code=404, detail="synonym group not found")
    return term


# 更新单个同义词词项。
@router.patch("/synonyms/terms/{term_id}", response_model=SynonymTermResponse)
def update_synonym_term_endpoint(
    term_id: int,
    request: SynonymTermUpdate,
    db: Session = Depends(get_db),
    _: AuthUser = Depends(require_super_admin),
) -> SynonymTermResponse:
    term = update_synonym_term(db, term_id, request)
    if term is None:
        raise HTTPException(status_code=404, detail="synonym term not found")
    return term
