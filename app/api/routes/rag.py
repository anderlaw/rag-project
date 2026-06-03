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
    QueryLogDetailResponse,
)
from app.services.rag_debug_service import (
    create_eval_case_from_query_log,
    create_failure_case_from_query_log,
    get_query_log_detail,
    run_debug_query,
)

router = APIRouter(prefix="/rag", tags=["rag"])


@router.post("/debug-query", response_model=DebugQueryResponse)
def debug_query(request: DebugQueryRequest, db: Session = Depends(get_db)) -> DebugQueryResponse:
    return run_debug_query(db, request)


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
