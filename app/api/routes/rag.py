from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_db
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
from app.services.synonym_service import (
    add_synonym_term,
    create_synonym_group,
    list_synonym_groups,
    normalize_query,
    update_synonym_group,
    update_synonym_term,
)
# 定义RAG模块的APIRouter实例，设置前缀和标签
router = APIRouter(prefix="/rag", tags=["rag"])

# 调试查询接口
@router.post("/debug-query", response_model=DebugQueryResponse)
def debug_query(request: DebugQueryRequest, db: Session = Depends(get_db)) -> DebugQueryResponse:
    return run_debug_query(db, request)

# 查询规范化接口，把用户输入的查询进行规范化处理，返回规范化后的文本和相关信息
@router.post("/normalize-query", response_model=NormalizeQueryResponse)
def normalize_query_endpoint(request: NormalizeQueryRequest, db: Session = Depends(get_db)) -> NormalizeQueryResponse:
    return normalize_query(db, request)


@router.get("/query-logs/{query_log_id}", response_model=QueryLogDetailResponse)
def query_log_detail(query_log_id: int, db: Session = Depends(get_db)) -> QueryLogDetailResponse:
    detail = get_query_log_detail(db, query_log_id)
    if detail is None:
        raise HTTPException(status_code=404, detail="query log not found")
    return detail


@router.post("/query-logs/{query_log_id}/failure-cases", response_model=FailureCaseResponse)
def save_query_log_as_failure_case(
    query_log_id: int,
    request: CreateFailureCaseFromQueryLogRequest,
    db: Session = Depends(get_db),
) -> FailureCaseResponse:
    failure_case = create_failure_case_from_query_log(db, query_log_id, request)
    if failure_case is None:
        raise HTTPException(status_code=404, detail="query log not found")
    return failure_case


@router.post("/query-logs/{query_log_id}/eval-cases", response_model=EvalCaseResponse)
def save_query_log_as_eval_case(
    query_log_id: int,
    request: CreateEvalCaseFromQueryLogRequest,
    db: Session = Depends(get_db),
) -> EvalCaseResponse:
    eval_case = create_eval_case_from_query_log(db, query_log_id, request)
    if eval_case is None:
        raise HTTPException(status_code=404, detail="query log not found")
    return eval_case


# 列出“同义词组”
@router.get("/synonyms", response_model=SynonymGroupListResponse)
def list_synonyms(db: Session = Depends(get_db)) -> SynonymGroupListResponse:
    return list_synonym_groups(db)

# 增加同义词组
@router.post("/synonyms", response_model=SynonymGroupResponse)
def create_synonym(request: SynonymGroupCreate, db: Session = Depends(get_db)) -> SynonymGroupResponse:
    return create_synonym_group(db, request)

# 更新同义词组
@router.patch("/synonyms/{group_id}", response_model=SynonymGroupResponse)
def update_synonym(group_id: int, request: SynonymGroupUpdate, db: Session = Depends(get_db)) -> SynonymGroupResponse:
    group = update_synonym_group(db, group_id, request)
    if group is None:
        raise HTTPException(status_code=404, detail="synonym group not found")
    return group

# 增加同义词项
@router.post("/synonyms/{group_id}/terms", response_model=SynonymTermResponse)
def create_synonym_term(group_id: int, request: SynonymTermCreate, db: Session = Depends(get_db)) -> SynonymTermResponse:
    term = add_synonym_term(db, group_id, request)
    if term is None:
        raise HTTPException(status_code=404, detail="synonym group not found")
    return term

# 更新同义词项
@router.patch("/synonyms/terms/{term_id}", response_model=SynonymTermResponse)
def update_synonym_term_endpoint(
    term_id: int,
    request: SynonymTermUpdate,
    db: Session = Depends(get_db),
) -> SynonymTermResponse:
    term = update_synonym_term(db, term_id, request)
    if term is None:
        raise HTTPException(status_code=404, detail="synonym term not found")
    return term