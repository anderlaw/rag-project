import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";

import App from "./App";

describe("document management app", () => {
  it("loads documents and opens detail chunks", async () => {
    vi.stubGlobal("fetch", mockFetch());
    const queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false }, mutations: { retry: false } }
    });

    render(
      <QueryClientProvider client={queryClient}>
        <MemoryRouter initialEntries={["/documents"]}>
          <App />
        </MemoryRouter>
      </QueryClientProvider>
    );

    expect(await screen.findByRole("heading", { name: "文档管理" })).toBeInTheDocument();
    expect(await screen.findByText("policy.txt")).toBeInTheDocument();

    await userEvent.click(screen.getByRole("link", { name: "查看详情" }));

    expect(await screen.findByRole("heading", { name: "文档详情：policy.txt" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "生成测试用例草稿" })).toBeDisabled();
    expect(screen.getByText("解析配置")).toBeInTheDocument();
    expect(screen.getByText("切片配置")).toBeInTheDocument();
    expect(screen.getAllByText("parent_child_v1").length).toBeGreaterThan(0);

    expect(await screen.findAllByText("policy paragraph content")).toHaveLength(2);
    expect(screen.getByLabelText("章节筛选")).toBeInTheDocument();
    expect(screen.getAllByText("正文 / 报销制度").length).toBeGreaterThan(0);
    expect(screen.getByText("Context 内容")).toBeInTheDocument();
    expect(screen.getByText(/正文 \/ 报销制度 context/)).toBeInTheDocument();
  });

  it("runs retrieval debugging and shows candidate scores", async () => {
    vi.stubGlobal("fetch", mockDebugFetch());
    const queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false }, mutations: { retry: false } }
    });

    render(
      <QueryClientProvider client={queryClient}>
        <MemoryRouter initialEntries={["/rag/debug"]}>
          <App />
        </MemoryRouter>
      </QueryClientProvider>
    );

    expect(await screen.findByRole("heading", { name: "检索调试" })).toBeInTheDocument();

    await userEvent.clear(screen.getByLabelText("问题"));
    await userEvent.type(screen.getByLabelText("问题"), "差旅报销需要什么材料");
    await userEvent.click(screen.getByRole("button", { name: "运行调试" }));

    expect(await screen.findByText("公司报销制度.pdf")).toBeInTheDocument();
    expect(screen.getByText("差旅报销")).toBeInTheDocument();
    expect(screen.getByText("0.86")).toBeInTheDocument();
    expect(screen.getByText("0.70")).toBeInTheDocument();
    expect(screen.getByText("0.73")).toBeInTheDocument();
    expect(screen.getByText("是")).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "文档状态诊断" })).toBeInTheDocument();
    expect(screen.getByText("1 active documents")).toBeInTheDocument();
    expect(screen.getByText("AI获客数据权限相关.md")).toBeInTheDocument();
    expect(screen.getByText("DELETED")).toBeInTheDocument();
    expect(screen.queryByText("报销制度 / 差旅报销\n\n差旅报销需要提供发票、行程单、审批记录。")).not.toBeInTheDocument();

    await userEvent.click(screen.getAllByRole("button", { name: "查看 chunk #10 详情" })[0]);

    const debugDialog = await screen.findByRole("dialog", { name: "Chunk 详情 #10" });
    expect(within(debugDialog).getByText("父 chunk #3")).toBeInTheDocument();
    expect(within(debugDialog).getByText("子 chunk #0")).toBeInTheDocument();
    expect(within(debugDialog).getByText("字符 12-38")).toBeInTheDocument();
    expect(within(debugDialog).getByText("差旅报销需要提供发票、行程单、审批记录。")).toBeInTheDocument();
    expect(screen.getByText("Prompt 预览")).toBeInTheDocument();
    expect(screen.getByText(/你是一个知识库问答助手/)).toBeInTheDocument();
  });

  it("loads query log detail", async () => {
    vi.stubGlobal("fetch", mockQueryLogFetch());
    const queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false }, mutations: { retry: false } }
    });

    render(
      <QueryClientProvider client={queryClient}>
        <MemoryRouter initialEntries={["/rag/query-logs/1001"]}>
          <App />
        </MemoryRouter>
      </QueryClientProvider>
    );

    expect(await screen.findByRole("heading", { name: "查询详情 #1001" })).toBeInTheDocument();
    expect(screen.getByText("AI智能获客技术栈是什么")).toBeInTheDocument();
    expect(screen.getAllByText("AI获客数据权限相关.md").length).toBeGreaterThan(0);
    expect(screen.getByText("1.2 技术栈")).toBeInTheDocument();
    expect(screen.getAllByText("0.75").length).toBeGreaterThan(0);
    expect(screen.getByRole("heading", { name: "文档状态诊断" })).toBeInTheDocument();
    expect(screen.getByText("340 chunks")).toBeInTheDocument();

    await userEvent.click(screen.getAllByRole("button", { name: "查看 chunk #2072 详情" })[0]);

    const logDialog = await screen.findByRole("dialog", { name: "Chunk 详情 #2072" });
    expect(within(logDialog).getByText("字符 120-220")).toBeInTheDocument();
    expect(within(logDialog).getByText("AI获客数据权限相关 / 一、项目概览 / 1.2 技术栈")).toBeInTheDocument();
    expect(screen.getByText("Prompt 快照")).toBeInTheDocument();
    expect(screen.getByText(/DashScope embedding failed/)).toBeInTheDocument();
  });

  it("saves query log detail as failure and eval cases with enum selects", async () => {
    vi.stubGlobal("fetch", mockQueryLogSaveFetch());
    const queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false }, mutations: { retry: false } }
    });

    render(
      <QueryClientProvider client={queryClient}>
        <MemoryRouter initialEntries={["/rag/query-logs/1001"]}>
          <App />
        </MemoryRouter>
      </QueryClientProvider>
    );

    expect(await screen.findByRole("heading", { name: "查询详情 #1001" })).toBeInTheDocument();
    expect(screen.getByRole("option", { name: "召回到了但排名过低" })).toBeInTheDocument();
    expect(screen.getByRole("option", { name: "分析中" })).toBeInTheDocument();
    expect(screen.getAllByRole("option", { name: "P2 高" }).length).toBeGreaterThan(0);
    expect(screen.getByRole("option", { name: "失败回归" })).toBeInTheDocument();
    expect(screen.getByRole("option", { name: "草稿" })).toBeInTheDocument();

    await userEvent.selectOptions(screen.getByLabelText("失败类型"), "RETRIEVAL_LOW_RANK");
    await userEvent.selectOptions(screen.getByLabelText("失败状态"), "ANALYZING");
    await userEvent.selectOptions(screen.getByLabelText("失败优先级"), "2");
    await userEvent.type(screen.getByLabelText("失败分析备注"), "正确 chunk 排名太低");
    await userEvent.click(screen.getByRole("button", { name: "保存失败案例" }));

    expect(await screen.findByText("失败案例 #7 已保存")).toBeInTheDocument();

    await userEvent.selectOptions(screen.getByLabelText("用例类型"), "FAILURE_REGRESSION");
    await userEvent.selectOptions(screen.getByLabelText("用例状态"), "DRAFT");
    await userEvent.selectOptions(screen.getByLabelText("用例优先级"), "2");
    await userEvent.type(screen.getByLabelText("期望答案"), "后端使用 FastAPI + PostgreSQL。");
    await userEvent.click(screen.getByRole("button", { name: "保存评测用例" }));

    expect(await screen.findByText("评测用例 #8 已保存")).toBeInTheDocument();
  });
});

function mockFetch() {
  return vi.fn(async (input: RequestInfo | URL) => {
    const url = String(input);
    if (url === "/api/v1/documents") {
      return jsonResponse({
        items: [
          {
            id: 1,
            name: "policy.txt",
            file_type: "txt",
            file_size: 128,
            current_version_id: 1,
            status: "ACTIVE",
            created_at: "2026-06-02T10:00:00",
            updated_at: "2026-06-02T10:05:00"
          }
        ]
      });
    }
    if (url === "/api/v1/documents/1") {
      return jsonResponse({
        id: 1,
        name: "policy.txt",
        file_type: "txt",
        file_size: 128,
        current_version_id: 1,
        status: "ACTIVE",
        created_at: "2026-06-02T10:00:00",
        updated_at: "2026-06-02T10:05:00",
        versions: [
          {
            id: 1,
            version_no: 1,
            file_hash: "abc",
            original_filename: "policy.txt",
            storage_key: "documents/1/versions/1/policy.txt",
            parser_version: "document-parser-v1",
            parser_config_snapshot: {
              parser: "pypdf/python-docx/plaintext",
              version: "document-parser-v1",
              split_paragraphs: true
            },
            chunk_strategy_name: "parent_child_v1",
            chunk_config_snapshot: {
              strategy: "parent_child_v1",
              parent_chunk_size: 1800,
              parent_chunk_overlap: 200,
              child_chunk_size: 500,
              child_chunk_overlap: 100
            },
            status: "COMPLETED",
            chunk_count: 2,
            error_message: null,
            created_at: "2026-06-02T10:00:00",
            processed_at: "2026-06-02T10:01:00"
          }
        ]
      });
    }
    if (url === "/api/v1/documents/1/chunks?version=1&chunk_type=CHILD") {
      return jsonResponse({
        items: [
          {
            id: 2,
            chunk_type: "CHILD",
            parent_chunk_id: 1,
            chunk_index: 0,
            child_index: 0,
            heading_path: "正文 / 报销制度",
            section_title: "报销制度",
            start_char: 0,
            end_char: 24,
            content: "policy paragraph content",
            content_with_context: "正文 / 报销制度 context\n\npolicy paragraph content",
            search_text: "正文 / 报销制度 context\n\npolicy paragraph content"
          }
        ]
      });
    }
    throw new Error(`unexpected request ${url}`);
  });
}

function mockDebugFetch() {
  return vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = String(input);
    if (url === "/api/v1/rag/debug-query" && init?.method === "POST") {
      return jsonResponse({
        query_log_id: 1001,
        question: "差旅报销需要什么材料",
        search_profile: {
          id: null,
          name: "默认混合检索",
          mode: "HYBRID",
          vector_top_k: 20,
          keyword_top_k: 20,
          trgm_top_k: 20,
          final_top_k: 5,
          vector_weight: 0.65,
          keyword_weight: 0.25,
          trgm_weight: 0.1,
          min_final_score: 0.55
        },
        candidates: [
          {
            rank: 1,
            chunk_id: 10,
            document_id: 1,
            document_version_id: 2,
            document_name: "公司报销制度.pdf",
            section_title: "差旅报销",
            heading_path: "报销制度 / 差旅报销",
            parent_chunk_id: 3,
            chunk_index: 0,
            child_index: 0,
            start_char: 12,
            end_char: 38,
            page_number: null,
            vector_score: 0.86,
            keyword_score: 0.7,
            trgm_score: 0,
            final_score: 0.734,
            selected_for_prompt: true,
            content_preview: "差旅报销需要提供发票、行程单、审批记录。",
            content: "差旅报销需要提供发票、行程单、审批记录。",
            content_with_context: "报销制度 / 差旅报销\n\n差旅报销需要提供发票、行程单、审批记录。"
          }
        ],
        selected_chunks: [
          {
            rank: 1,
            chunk_id: 10,
            document_id: 1,
            document_version_id: 2,
            document_name: "公司报销制度.pdf",
            section_title: "差旅报销",
            heading_path: "报销制度 / 差旅报销",
            parent_chunk_id: 3,
            chunk_index: 0,
            child_index: 0,
            start_char: 12,
            end_char: 38,
            page_number: null,
            vector_score: 0.86,
            keyword_score: 0.7,
            trgm_score: 0,
            final_score: 0.734,
            selected_for_prompt: true,
            content_preview: "差旅报销需要提供发票、行程单、审批记录。",
            content: "差旅报销需要提供发票、行程单、审批记录。",
            content_with_context: "报销制度 / 差旅报销\n\n差旅报销需要提供发票、行程单、审批记录。"
          }
        ],
        prompt: {
          version: "rag_qa_v1",
          text: "你是一个知识库问答助手。请只根据给定资料回答问题。"
        },
        diagnostics: {
          active_document_count: 1,
          searchable_child_chunk_count: 10,
          inactive_related_documents: [
            {
              document_id: 9,
              name: "AI获客数据权限相关.md",
              status: "DELETED",
              current_version_id: 9,
              version_status: "COMPLETED",
              chunk_count: 340,
              match_reason: "文档名/标题/内容与问题关键词匹配"
            }
          ],
          warnings: ["发现 1 个相关文档未参与检索，可能是状态非 ACTIVE 或当前版本不可检索。"]
        },
        llm: {
          used: false,
          model: null,
          latency_ms: null,
          answer: null,
          error: "LLM provider is not configured"
        }
      });
    }
    throw new Error(`unexpected request ${url}`);
  });
}

function mockQueryLogFetch() {
  return vi.fn(async (input: RequestInfo | URL) => {
    const url = String(input);
    if (url === "/api/v1/rag/query-logs/1001") {
      return jsonResponse({
        id: 1001,
        question: "AI智能获客技术栈是什么",
        search_mode: "HYBRID",
        use_llm: true,
        created_at: "2026-06-02T10:10:00",
        search_profile: {
          id: null,
          name: "默认混合检索",
          mode: "HYBRID",
          vector_top_k: 20,
          keyword_top_k: 20,
          trgm_top_k: 20,
          final_top_k: 5,
          vector_weight: 0.65,
          keyword_weight: 0.25,
          trgm_weight: 0.1,
          min_final_score: 0.55
        },
        model_config_snapshot: {
          embedding: { provider: "dashscope", model: "text-embedding-v4", dimension: 1536 },
          llm: { provider: "zhipu", model: "glm-5.1" }
        },
        search_latency_ms: 120,
        llm_latency_ms: null,
        total_latency_ms: 120,
        candidates: [
          {
            rank: 1,
            chunk_id: 2072,
            document_id: 9,
            document_version_id: 9,
            document_name: "AI获客数据权限相关.md",
            section_title: "1.2 技术栈",
            heading_path: "AI获客数据权限相关 / 一、项目概览 / 1.2 技术栈",
            parent_chunk_id: 2071,
            chunk_index: 1,
            child_index: 0,
            start_char: 120,
            end_char: 220,
            page_number: null,
            vector_score: 0.72,
            keyword_score: 0.75,
            trgm_score: 0,
            final_score: 0.75,
            selected_for_prompt: true,
            content_preview: "|层级|技术| 后端 FastAPI + PostgreSQL",
            content: "|层级|技术|\n|后端|FastAPI + PostgreSQL|",
            content_with_context: "AI获客数据权限相关 / 一、项目概览 / 1.2 技术栈\n\n|层级|技术|"
          }
        ],
        selected_chunks: [
          {
            rank: 1,
            chunk_id: 2072,
            document_id: 9,
            document_version_id: 9,
            document_name: "AI获客数据权限相关.md",
            section_title: "1.2 技术栈",
            heading_path: "AI获客数据权限相关 / 一、项目概览 / 1.2 技术栈",
            parent_chunk_id: 2071,
            chunk_index: 1,
            child_index: 0,
            start_char: 120,
            end_char: 220,
            page_number: null,
            vector_score: 0.72,
            keyword_score: 0.75,
            trgm_score: 0,
            final_score: 0.75,
            selected_for_prompt: true,
            content_preview: "|层级|技术| 后端 FastAPI + PostgreSQL",
            content: "|层级|技术|\n|后端|FastAPI + PostgreSQL|",
            content_with_context: "AI获客数据权限相关 / 一、项目概览 / 1.2 技术栈\n\n|层级|技术|"
          }
        ],
        prompt: {
          version: "rag_qa_v1",
          text: "你是一个知识库问答助手。问题：AI智能获客技术栈是什么"
        },
        diagnostics: {
          active_document_count: 2,
          searchable_child_chunk_count: 29,
          inactive_related_documents: [
            {
              document_id: 9,
              name: "AI获客数据权限相关.md",
              status: "DELETED",
              current_version_id: 9,
              version_status: "COMPLETED",
              chunk_count: 340,
              match_reason: "文档名/标题/内容与问题关键词匹配"
            }
          ],
          warnings: ["发现 1 个相关文档未参与检索，可能是状态非 ACTIVE 或当前版本不可检索。"]
        },
        llm: {
          used: false,
          model: "glm-5.1",
          latency_ms: null,
          answer: null,
          error: "DashScope embedding failed"
        }
      });
    }
    throw new Error(`unexpected request ${url}`);
  });
}

function mockQueryLogSaveFetch() {
  const baseFetch = mockQueryLogFetch();
  return vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = String(input);
    if (url === "/api/v1/rag/query-logs/1001/failure-cases" && init?.method === "POST") {
      expect(JSON.parse(String(init.body))).toMatchObject({
        primary_failure_type: "RETRIEVAL_LOW_RANK",
        status: "ANALYZING",
        priority: 2,
        analysis_note: "正确 chunk 排名太低"
      });
      return jsonResponse({
        id: 7,
        query_log_id: 1001,
        source_type: "MANUAL_DEBUG",
        primary_failure_type: "RETRIEVAL_LOW_RANK",
        status: "ANALYZING",
        priority: 2
      });
    }
    if (url === "/api/v1/rag/query-logs/1001/eval-cases" && init?.method === "POST") {
      expect(JSON.parse(String(init.body))).toMatchObject({
        question: "AI智能获客技术栈是什么",
        expected_answer: "后端使用 FastAPI + PostgreSQL。",
        case_type: "FAILURE_REGRESSION",
        status: "DRAFT",
        priority: 2
      });
      return jsonResponse({
        id: 8,
        question: "AI智能获客技术栈是什么",
        case_type: "FAILURE_REGRESSION",
        status: "DRAFT",
        priority: 2,
        created_from: "QUERY_LOG",
        source_ref_id: 1001
      });
    }
    return baseFetch(input);
  });
}

function jsonResponse(body: unknown): Response {
  return new Response(JSON.stringify(body), {
    status: 200,
    headers: { "Content-Type": "application/json" }
  });
}
