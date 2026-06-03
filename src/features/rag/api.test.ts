import { describe, expect, it, vi } from "vitest";

import { createEvalCaseFromQueryLog, createFailureCaseFromQueryLog, getQueryLogDetail, runDebugQuery } from "./api";

describe("rag api", () => {
  it("posts debug query requests to the backend", async () => {
    const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      expect(String(input)).toBe("/api/v1/rag/debug-query");
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
      expect(String(input)).toBe("/api/v1/rag/query-logs/1001");
      return jsonResponse({ id: 1001, question: "报销材料", candidates: [], selected_chunks: [] });
    });
    vi.stubGlobal("fetch", fetchMock);

    await expect(getQueryLogDetail(1001)).resolves.toMatchObject({
      id: 1001,
      question: "报销材料"
    });
  });

  it("saves a query log as a failure case", async () => {
    const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      expect(String(input)).toBe("/api/v1/rag/query-logs/1001/failure-cases");
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
      expect(String(input)).toBe("/api/v1/rag/query-logs/1001/eval-cases");
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
});

function jsonResponse(body: unknown): Response {
  return new Response(JSON.stringify(body), {
    status: 200,
    headers: { "Content-Type": "application/json" }
  });
}
