import { requestJson } from "../../lib/http";
import type {
  CreateEvalCaseRequest,
  CreateFailureCaseRequest,
  DebugQueryRequest,
  DebugQueryResponse,
  EvalCase,
  FailureCase,
  QueryLogDetail
} from "./types";

const RAG_BASE = "/api/v1/rag";

export function runDebugQuery(request: DebugQueryRequest): Promise<DebugQueryResponse> {
  return requestJson<DebugQueryResponse>(`${RAG_BASE}/debug-query`, {
    method: "POST",
    body: JSON.stringify(request)
  });
}

export function getQueryLogDetail(queryLogId: number): Promise<QueryLogDetail> {
  return requestJson<QueryLogDetail>(`${RAG_BASE}/query-logs/${queryLogId}`);
}

export function createFailureCaseFromQueryLog(
  queryLogId: number,
  request: CreateFailureCaseRequest
): Promise<FailureCase> {
  return requestJson<FailureCase>(`${RAG_BASE}/query-logs/${queryLogId}/failure-cases`, {
    method: "POST",
    body: JSON.stringify(request)
  });
}

export function createEvalCaseFromQueryLog(queryLogId: number, request: CreateEvalCaseRequest): Promise<EvalCase> {
  return requestJson<EvalCase>(`${RAG_BASE}/query-logs/${queryLogId}/eval-cases`, {
    method: "POST",
    body: JSON.stringify(request)
  });
}
