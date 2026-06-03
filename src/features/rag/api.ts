import { requestJson } from "../../lib/http";
import type {
  CreateEvalCaseRequest,
  CreateFailureCaseRequest,
  CreateSynonymGroupRequest,
  CreateSynonymTermRequest,
  DebugQueryRequest,
  DebugQueryResponse,
  EvalCase,
  FailureCase,
  NormalizeQueryResponse,
  QueryLogDetail,
  SynonymGroup,
  SynonymGroupListResponse,
  SynonymTerm,
  UpdateSynonymGroupRequest,
  UpdateSynonymTermRequest
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

export function listSynonymGroups(): Promise<SynonymGroupListResponse> {
  return requestJson<SynonymGroupListResponse>(`${RAG_BASE}/synonyms`);
}

export function createSynonymGroup(request: CreateSynonymGroupRequest): Promise<SynonymGroup> {
  return requestJson<SynonymGroup>(`${RAG_BASE}/synonyms`, {
    method: "POST",
    body: JSON.stringify(request)
  });
}

export function updateSynonymGroup(groupId: number, request: UpdateSynonymGroupRequest): Promise<SynonymGroup> {
  return requestJson<SynonymGroup>(`${RAG_BASE}/synonyms/${groupId}`, {
    method: "PATCH",
    body: JSON.stringify(request)
  });
}

export function addSynonymTerm(groupId: number, request: CreateSynonymTermRequest): Promise<SynonymTerm> {
  return requestJson<SynonymTerm>(`${RAG_BASE}/synonyms/${groupId}/terms`, {
    method: "POST",
    body: JSON.stringify(request)
  });
}

export function updateSynonymTerm(termId: number, request: UpdateSynonymTermRequest): Promise<SynonymTerm> {
  return requestJson<SynonymTerm>(`${RAG_BASE}/synonyms/terms/${termId}`, {
    method: "PATCH",
    body: JSON.stringify(request)
  });
}

export function normalizeQuery(question: string): Promise<NormalizeQueryResponse> {
  return requestJson<NormalizeQueryResponse>(`${RAG_BASE}/normalize-query`, {
    method: "POST",
    body: JSON.stringify({ question })
  });
}
