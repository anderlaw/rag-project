import { describe, expect, it, vi } from "vitest";

import { baseURL } from "../../lib/http";
import {
  createEvalCaseFromQueryLog,
  createFailureCaseFromQueryLog,
  createSynonymGroup,
  getQueryLogDetail,
  listSynonymGroups,
  normalizeQuery,
  runDebugQuery,
  searchDocuments,
  submitSearchFeedback
} from "./api";

const API_BASE = `${baseURL.replace(/\/+$/, "")}/api/v1`;

describe("rag api", () => {
  it("posts debug query requests to the backend", async () => {
    const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      expect(String(input)).toBe(`${API_BASE}/rag/debug-query`);
      expect(init?.method).toBe("POST");
      expect(init?.body).toBe(JSON.stringify({ question: "报销材料", use_llm: true, final_top_k: 5 }));
      return jsonResponse({ question: "报销材料", candidates: [], selected_chunks: [], prompt: null });
    });
    vi.stubGlobal("fetch", fetchMock);

    await expect(runDebugQuery({ question: "报销材料", use_llm: true, final_top_k: 5 })).resolves.toMatchObject({
      question: "报销材料"
    });
  });

  it("gets query log detail from the backend", async () => {
    const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
      expect(String(input)).toBe(`${API_BASE}/rag/query-logs/1001`);
      return jsonResponse({ id: 1001, question: "报销材料", candidates: [], selected_chunks: [] });
    });
    vi.stubGlobal("fetch", fetchMock);

    await expect(getQueryLogDetail(1001)).resolves.toMatchObject({
      id: 1001,
      question: "报销材料"
    });
  });

  it("posts user document search requests to the backend", async () => {
    const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      expect(String(input)).toBe(`${API_BASE}/rag/search`);
      expect(init?.method).toBe("POST");
      expect(init?.credentials).toBe("include");
      expect(init?.body).toBe(JSON.stringify({ question: "报销材料", use_llm: true }));
      return jsonResponse({ query_log_id: 1, question: "报销材料", status: "COMPLETED", results: [], warnings: [] });
    });
    vi.stubGlobal("fetch", fetchMock);

    await expect(searchDocuments({ question: "报销材料", use_llm: true })).resolves.toMatchObject({
      query_log_id: 1,
      status: "COMPLETED"
    });
  });

  it("submits search feedback to the backend", async () => {
    const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      expect(String(input)).toBe(`${API_BASE}/rag/search/1001/feedback`);
      expect(init?.method).toBe("POST");
      expect(init?.body).toBe(
        JSON.stringify({
          rating: "NOT_HELPFUL",
          comment: "没找到答案"
        })
      );
      return jsonResponse({ id: 77, query_log_id: 1001, rating: "NOT_HELPFUL" });
    });
    vi.stubGlobal("fetch", fetchMock);

    await expect(submitSearchFeedback(1001, { rating: "NOT_HELPFUL", comment: "没找到答案" })).resolves.toMatchObject({
      id: 77
    });
  });

  it("saves a query log as a failure case", async () => {
    const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      expect(String(input)).toBe(`${API_BASE}/rag/query-logs/1001/failure-cases`);
      expect(init?.method).toBe("POST");
      expect(init?.body).toBe(
        JSON.stringify({
          primary_failure_type: "RETRIEVAL_LOW_RANK",
          status: "OPEN",
          priority: 2,
          analysis_note: "正确 chunk 排名过低"
        })
      );
      return jsonResponse({ id: 7, query_log_id: 1001, status: "OPEN" });
    });
    vi.stubGlobal("fetch", fetchMock);

    await expect(
      createFailureCaseFromQueryLog(1001, {
        primary_failure_type: "RETRIEVAL_LOW_RANK",
        status: "OPEN",
        priority: 2,
        analysis_note: "正确 chunk 排名过低"
      })
    ).resolves.toMatchObject({ id: 7 });
  });

  it("saves a query log as an eval case", async () => {
    const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      expect(String(input)).toBe(`${API_BASE}/rag/query-logs/1001/eval-cases`);
      expect(init?.method).toBe("POST");
      expect(init?.body).toBe(
        JSON.stringify({
          question: "报销材料是什么？",
          expected_answer: "需要发票。",
          case_type: "FAILURE_REGRESSION",
          status: "DRAFT",
          priority: 2
        })
      );
      return jsonResponse({ id: 8, question: "报销材料是什么？", status: "DRAFT" });
    });
    vi.stubGlobal("fetch", fetchMock);

    await expect(
      createEvalCaseFromQueryLog(1001, {
        question: "报销材料是什么？",
        expected_answer: "需要发票。",
        case_type: "FAILURE_REGRESSION",
        status: "DRAFT",
        priority: 2
      })
    ).resolves.toMatchObject({ id: 8 });
  });

  it("lists synonym groups", async () => {
    const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
      expect(String(input)).toBe(`${API_BASE}/rag/synonyms`);
      return jsonResponse({ items: [{ id: 1, name: "技术栈", terms: [] }] });
    });
    vi.stubGlobal("fetch", fetchMock);

    await expect(listSynonymGroups()).resolves.toMatchObject({
      items: [{ id: 1, name: "技术栈" }]
    });
  });

  it("creates synonym groups with seed terms", async () => {
    const request = {
      name: "客户画像",
      terms: [
        { term: "客户画像", term_type: "CANONICAL" as const, language: "zh" },
        { term: "ICP", term_type: "SYNONYM" as const, language: "en" }
      ]
    };
    const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      expect(String(input)).toBe(`${API_BASE}/rag/synonyms`);
      expect(init?.method).toBe("POST");
      expect(init?.body).toBe(JSON.stringify(request));
      return jsonResponse({ id: 2, name: "客户画像", terms: [] });
    });
    vi.stubGlobal("fetch", fetchMock);

    await expect(createSynonymGroup(request)).resolves.toMatchObject({ id: 2, name: "客户画像" });
  });

  it("normalizes queries through the backend", async () => {
    const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      expect(String(input)).toBe(`${API_BASE}/rag/normalize-query`);
      expect(init?.method).toBe("POST");
      expect(init?.body).toBe(JSON.stringify({ question: "告诉我ICP是啥" }));
      return jsonResponse({
        original_text: "告诉我ICP是啥",
        normalized_text: "ICP",
        expanded_text: "ICP 客户画像",
        applied_synonym_groups: ["客户画像"]
      });
    });
    vi.stubGlobal("fetch", fetchMock);

    await expect(normalizeQuery("告诉我ICP是啥")).resolves.toMatchObject({
      normalized_text: "ICP",
      applied_synonym_groups: ["客户画像"]
    });
  });
});

function jsonResponse(body: unknown): Response {
  return new Response(JSON.stringify(body), {
    status: 200,
    headers: { "Content-Type": "application/json" }
  });
}
