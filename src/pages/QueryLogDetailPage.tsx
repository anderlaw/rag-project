import { useMutation, useQuery } from "@tanstack/react-query";
import { ArrowLeft, Bug, CheckCircle2, Copy, FileCheck2, Search } from "lucide-react";
import { useState } from "react";
import { Link, useParams } from "react-router-dom";

import { ButtonSpinner } from "../components/common/ButtonSpinner";
import { ErrorState } from "../components/common/ErrorState";
import { LoadingState } from "../components/common/LoadingState";
import { PageHeader } from "../components/common/PageHeader";
import { createEvalCaseFromQueryLog, createFailureCaseFromQueryLog, getQueryLogDetail } from "../features/rag/api";
import { ChunkDetailModal, cleanDisplayText } from "../features/rag/components/ChunkDetailModal";
import { DocumentDiagnostics } from "../features/rag/components/DocumentDiagnostics";
import type {
  DebugCandidate,
  DebugLlm,
  DebugPrompt,
  EvalCaseStatus,
  EvalCaseType,
  FailureStatus,
  FailureType,
  QueryLogDetail
} from "../features/rag/types";
import { formatDateTime } from "../lib/format";

const FAILURE_TYPE_OPTIONS: FailureType[] = [
  "RETRIEVAL_NO_RECALL",
  "RETRIEVAL_LOW_RANK",
  "CHUNK_INCOMPLETE",
  "CONTEXT_MISSING",
  "PROMPT_SELECTION_WRONG",
  "GENERATION_WRONG",
  "HALLUCINATION",
  "OUTDATED_DOCUMENT",
  "AMBIGUOUS_QUESTION",
  "UX_BAD_FORMAT",
  "LOW_CONFIDENCE_RETRIEVAL",
  "LLM_ERROR"
];
const FAILURE_STATUS_OPTIONS: FailureStatus[] = ["OPEN", "ANALYZING", "FIXED", "WONT_FIX"];
const EVAL_CASE_TYPE_OPTIONS: EvalCaseType[] = ["CORE_RULE", "FREQUENT_QUERY", "EDGE_CASE", "FAILURE_REGRESSION"];
const EVAL_CASE_STATUS_OPTIONS: EvalCaseStatus[] = ["DRAFT", "ACTIVE", "INACTIVE", "REJECTED"];
const PRIORITY_OPTIONS = [1, 2, 3, 4, 5];
const FAILURE_TYPE_LABELS: Record<FailureType, string> = {
  RETRIEVAL_NO_RECALL: "没有召回正确内容",
  RETRIEVAL_LOW_RANK: "召回到了但排名过低",
  CHUNK_INCOMPLETE: "切片内容不完整",
  CONTEXT_MISSING: "上下文缺失",
  PROMPT_SELECTION_WRONG: "Prompt 选择了错误片段",
  GENERATION_WRONG: "回答生成错误",
  HALLUCINATION: "模型幻觉",
  OUTDATED_DOCUMENT: "文档内容过期",
  AMBIGUOUS_QUESTION: "问题表述不清",
  UX_BAD_FORMAT: "回答格式体验差",
  LOW_CONFIDENCE_RETRIEVAL: "检索置信度低",
  LLM_ERROR: "LLM 调用错误"
};
const FAILURE_STATUS_LABELS: Record<FailureStatus, string> = {
  OPEN: "待处理",
  ANALYZING: "分析中",
  FIXED: "已修复",
  WONT_FIX: "不修复"
};
const EVAL_CASE_TYPE_LABELS: Record<EvalCaseType, string> = {
  CORE_RULE: "核心规则",
  FREQUENT_QUERY: "高频问题",
  EDGE_CASE: "边界用例",
  FAILURE_REGRESSION: "失败回归"
};
const EVAL_CASE_STATUS_LABELS: Record<EvalCaseStatus, string> = {
  DRAFT: "草稿",
  ACTIVE: "启用",
  INACTIVE: "停用",
  REJECTED: "拒绝"
};
const PRIORITY_LABELS: Record<number, string> = {
  1: "P1 最高",
  2: "P2 高",
  3: "P3 中",
  4: "P4 低",
  5: "P5 最低"
};

export function QueryLogDetailPage() {
  const { queryLogId } = useParams();
  const parsedQueryLogId = Number(queryLogId);
  const isValidQueryLogId = Number.isInteger(parsedQueryLogId) && parsedQueryLogId > 0;
  const [detailCandidate, setDetailCandidate] = useState<DebugCandidate | null>(null);

  const queryLogQuery = useQuery({
    queryKey: ["rag-query-log", parsedQueryLogId],
    queryFn: () => getQueryLogDetail(parsedQueryLogId),
    enabled: isValidQueryLogId
  });

  if (!isValidQueryLogId) {
    return <ErrorState title="查询日志 ID 无效" error={new Error("URL 中的查询日志 ID 必须是正整数。")} />;
  }

  if (queryLogQuery.isLoading) {
    return <LoadingState label="加载查询详情" />;
  }

  if (queryLogQuery.error || !queryLogQuery.data) {
    return <ErrorState error={queryLogQuery.error ?? new Error("查询日志不存在")} onRetry={() => queryLogQuery.refetch()} />;
  }

  const detail = queryLogQuery.data;

  return (
    <div className="page-stack">
      <PageHeader
        title={`查询详情 #${detail.id}`}
        description={`${formatDateTime(detail.created_at)} · ${detail.search_mode}`}
        actions={
          <>
            <Link className="button button-secondary" to="/rag/debug">
              <ArrowLeft size={16} />
              返回调试
            </Link>
            <Link className="button button-secondary" to="/documents">
              文档列表
            </Link>
          </>
        }
      />

      <QueryQuestionPanel detail={detail} />
      <QueryLogMetrics detail={detail} />
      <DocumentDiagnostics diagnostics={detail.diagnostics} />

      <section className="debug-grid">
        <FailureCaseSavePanel queryLogId={detail.id} />
        <EvalCaseSavePanel detail={detail} />
      </section>

      <section className="debug-grid">
        <div className="panel">
          <div className="panel-title-row">
            <h2>检索候选 chunks</h2>
            <span className="runtime-pill">{detail.candidates.length} candidates</span>
          </div>
          <QueryCandidateTable candidates={detail.candidates} onOpenDetail={setDetailCandidate} />
        </div>

        <SelectedChunksPanel candidates={detail.selected_chunks} onOpenDetail={setDetailCandidate} />
      </section>

      <section className="debug-grid">
        <PromptSnapshot prompt={detail.prompt} />
        <LlmSnapshot llm={detail.llm} />
      </section>

      <section className="debug-grid">
        <SnapshotPanel title="搜索配置快照" value={detail.search_profile} />
        <SnapshotPanel title="模型配置快照" value={detail.model_config_snapshot} />
      </section>

      <ChunkDetailModal candidate={detailCandidate} onClose={() => setDetailCandidate(null)} />
    </div>
  );
}

function FailureCaseSavePanel({ queryLogId }: { queryLogId: number }) {
  const [failureType, setFailureType] = useState<FailureType>("RETRIEVAL_LOW_RANK");
  const [status, setStatus] = useState<FailureStatus>("OPEN");
  const [priority, setPriority] = useState(3);
  const [analysisNote, setAnalysisNote] = useState("");
  const [fixPlan, setFixPlan] = useState("");

  const mutation = useMutation({
    mutationFn: () =>
      createFailureCaseFromQueryLog(queryLogId, {
        primary_failure_type: failureType,
        status,
        priority,
        analysis_note: optionalText(analysisNote),
        fix_plan: optionalText(fixPlan)
      })
  });

  return (
    <section className="panel case-save-panel">
      <div className="panel-title-row">
        <h2>保存失败案例</h2>
        <Bug size={16} />
      </div>
      <div className="case-save-grid">
        <label>
          <span>失败类型</span>
          <select value={failureType} onChange={(event) => setFailureType(event.currentTarget.value as FailureType)}>
            {FAILURE_TYPE_OPTIONS.map((option) => (
              <option key={option} value={option}>
                {FAILURE_TYPE_LABELS[option]}
              </option>
            ))}
          </select>
        </label>
        <label>
          <span>失败状态</span>
          <select value={status} onChange={(event) => setStatus(event.currentTarget.value as FailureStatus)}>
            {FAILURE_STATUS_OPTIONS.map((option) => (
              <option key={option} value={option}>
                {FAILURE_STATUS_LABELS[option]}
              </option>
            ))}
          </select>
        </label>
        <label>
          <span>失败优先级</span>
          <select value={priority} onChange={(event) => setPriority(Number(event.currentTarget.value))}>
            {PRIORITY_OPTIONS.map((option) => (
              <option key={option} value={option}>
                {PRIORITY_LABELS[option]}
              </option>
            ))}
          </select>
        </label>
        <label className="case-save-wide">
          <span>失败分析备注</span>
          <textarea value={analysisNote} onChange={(event) => setAnalysisNote(event.currentTarget.value)} rows={3} />
        </label>
        <label className="case-save-wide">
          <span>修复计划</span>
          <textarea value={fixPlan} onChange={(event) => setFixPlan(event.currentTarget.value)} rows={2} />
        </label>
      </div>
      <button className="button button-primary" type="button" disabled={mutation.isPending} onClick={() => mutation.mutate()}>
        {mutation.isPending ? <ButtonSpinner label="保存失败案例中" /> : <FileCheck2 size={16} />}
        {mutation.isPending ? "保存中" : "保存失败案例"}
      </button>
      {mutation.data ? (
        <p className="success-text">
          <CheckCircle2 size={16} />
          失败案例 #{mutation.data.id} 已保存
        </p>
      ) : null}
      {mutation.error ? <p className="error-text">{mutation.error instanceof Error ? mutation.error.message : "保存失败"}</p> : null}
    </section>
  );
}

function EvalCaseSavePanel({ detail }: { detail: QueryLogDetail }) {
  const [question, setQuestion] = useState(detail.question);
  const [expectedAnswer, setExpectedAnswer] = useState("");
  const [caseType, setCaseType] = useState<EvalCaseType>("FAILURE_REGRESSION");
  const [status, setStatus] = useState<EvalCaseStatus>("DRAFT");
  const [priority, setPriority] = useState(3);

  const mutation = useMutation({
    mutationFn: () =>
      createEvalCaseFromQueryLog(detail.id, {
        question: optionalText(question),
        expected_answer: optionalText(expectedAnswer),
        case_type: caseType,
        status,
        priority
      })
  });

  return (
    <section className="panel case-save-panel">
      <div className="panel-title-row">
        <h2>保存评测用例</h2>
        <FileCheck2 size={16} />
      </div>
      <div className="case-save-grid">
        <label className="case-save-wide">
          <span>评测问题</span>
          <input className="plain-input" value={question} onChange={(event) => setQuestion(event.currentTarget.value)} />
        </label>
        <label>
          <span>用例类型</span>
          <select value={caseType} onChange={(event) => setCaseType(event.currentTarget.value as EvalCaseType)}>
            {EVAL_CASE_TYPE_OPTIONS.map((option) => (
              <option key={option} value={option}>
                {EVAL_CASE_TYPE_LABELS[option]}
              </option>
            ))}
          </select>
        </label>
        <label>
          <span>用例状态</span>
          <select value={status} onChange={(event) => setStatus(event.currentTarget.value as EvalCaseStatus)}>
            {EVAL_CASE_STATUS_OPTIONS.map((option) => (
              <option key={option} value={option}>
                {EVAL_CASE_STATUS_LABELS[option]}
              </option>
            ))}
          </select>
        </label>
        <label>
          <span>用例优先级</span>
          <select value={priority} onChange={(event) => setPriority(Number(event.currentTarget.value))}>
            {PRIORITY_OPTIONS.map((option) => (
              <option key={option} value={option}>
                {PRIORITY_LABELS[option]}
              </option>
            ))}
          </select>
        </label>
        <label className="case-save-wide">
          <span>期望答案</span>
          <textarea value={expectedAnswer} onChange={(event) => setExpectedAnswer(event.currentTarget.value)} rows={4} />
        </label>
      </div>
      <button className="button button-primary" type="button" disabled={mutation.isPending} onClick={() => mutation.mutate()}>
        {mutation.isPending ? <ButtonSpinner label="保存评测用例中" /> : <FileCheck2 size={16} />}
        {mutation.isPending ? "保存中" : "保存评测用例"}
      </button>
      {mutation.data ? (
        <p className="success-text">
          <CheckCircle2 size={16} />
          评测用例 #{mutation.data.id} 已保存
        </p>
      ) : null}
      {mutation.error ? <p className="error-text">{mutation.error instanceof Error ? mutation.error.message : "保存失败"}</p> : null}
    </section>
  );
}

function QueryQuestionPanel({ detail }: { detail: QueryLogDetail }) {
  return (
    <section className="panel query-question-panel">
      <div>
        <span className="runtime-pill">{detail.use_llm ? "LLM enabled" : "retrieval only"}</span>
        <h2>{detail.question}</h2>
      </div>
      <dl className="query-log-inline-meta">
        <div>
          <dt>profile</dt>
          <dd>{detail.search_profile.name}</dd>
        </div>
        <div>
          <dt>mode</dt>
          <dd>{detail.search_profile.mode}</dd>
        </div>
        <div>
          <dt>min score</dt>
          <dd>{formatScore(detail.search_profile.min_final_score)}</dd>
        </div>
      </dl>
    </section>
  );
}

function QueryLogMetrics({ detail }: { detail: QueryLogDetail }) {
  return (
    <section className="summary-grid">
      <div className="metric">
        <span>候选 chunks</span>
        <strong>{detail.candidates.length}</strong>
      </div>
      <div className="metric">
        <span>进入 Prompt</span>
        <strong>{detail.selected_chunks.length}</strong>
      </div>
      <div className="metric">
        <span>检索耗时</span>
        <strong>{formatLatency(detail.search_latency_ms)}</strong>
      </div>
      <div className="metric">
        <span>总耗时</span>
        <strong>{formatLatency(detail.total_latency_ms)}</strong>
      </div>
    </section>
  );
}

function QueryCandidateTable({
  candidates,
  onOpenDetail
}: {
  candidates: DebugCandidate[];
  onOpenDetail: (candidate: DebugCandidate) => void;
}) {
  if (candidates.length === 0) {
    return (
      <div className="empty-state">
        <div>
          <h3>暂无候选</h3>
          <p>这次查询没有检索到候选 chunk。</p>
        </div>
      </div>
    );
  }

  return (
    <div className="table-shell">
      <table className="data-table debug-table">
        <thead>
          <tr>
            <th>Rank</th>
            <th>文档</th>
            <th>章节</th>
            <th>V分</th>
            <th>K分</th>
            <th>T分</th>
            <th>总分</th>
            <th>选中</th>
            <th>内容摘要</th>
            <th>详情</th>
          </tr>
        </thead>
        <tbody>
          {candidates.map((candidate) => (
            <tr className={candidate.selected_for_prompt ? "selected-row" : ""} key={candidate.chunk_id}>
              <td>{candidate.rank}</td>
              <td className="document-name">{candidate.document_name}</td>
              <td>{candidate.section_title ?? candidate.heading_path ?? "-"}</td>
              <td>{formatScore(candidate.vector_score)}</td>
              <td>{formatScore(candidate.keyword_score)}</td>
              <td>{formatScore(candidate.trgm_score)}</td>
              <td>{formatScore(candidate.final_score)}</td>
              <td>{candidate.selected_for_prompt ? "是" : "否"}</td>
              <td>{summarizeContent(candidate.content_preview)}</td>
              <td>
                <button className="button button-secondary" type="button" onClick={() => onOpenDetail(candidate)}>
                  查看 chunk #{candidate.chunk_id} 详情
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function SelectedChunksPanel({
  candidates,
  onOpenDetail
}: {
  candidates: DebugCandidate[];
  onOpenDetail: (candidate: DebugCandidate) => void;
}) {
  return (
    <section className="panel">
      <div className="panel-title-row">
        <h2>送入 Prompt 的 chunks</h2>
        <Search size={16} />
      </div>
      {candidates.length === 0 ? (
        <p className="muted">没有 chunk 被选入 prompt。</p>
      ) : (
        <div className="selected-list">
          {candidates.map((candidate) => (
            <article className="selected-chunk" key={candidate.chunk_id}>
              <strong>
                #{candidate.rank} {candidate.document_name}
              </strong>
              <span>{cleanDisplayText(candidate.heading_path ?? candidate.section_title ?? "未分章节")}</span>
              <p>{summarizeContent(candidate.content_preview)}</p>
              <button className="button button-secondary" type="button" onClick={() => onOpenDetail(candidate)}>
                查看 chunk #{candidate.chunk_id} 详情
              </button>
            </article>
          ))}
        </div>
      )}
    </section>
  );
}

function PromptSnapshot({ prompt }: { prompt: DebugPrompt | null }) {
  return (
    <section className="panel">
      <div className="panel-title-row">
        <h2>Prompt 快照</h2>
        <button
          className="icon-button"
          type="button"
          disabled={!prompt?.text}
          aria-label="复制 Prompt 快照"
          onClick={() => prompt?.text && navigator.clipboard?.writeText(prompt.text)}
        >
          <Copy size={16} />
        </button>
      </div>
      <span className="runtime-pill">{prompt?.version ?? "未构建"}</span>
      {prompt?.text ? <pre className="debug-code">{prompt.text}</pre> : <p className="muted">这次查询没有构建 prompt。</p>}
    </section>
  );
}

function LlmSnapshot({ llm }: { llm: DebugLlm }) {
  return (
    <section className="panel">
      <h2>LLM 状态</h2>
      <dl className="meta-grid">
        <div>
          <dt>used</dt>
          <dd>{String(llm.used)}</dd>
        </div>
        <div>
          <dt>model</dt>
          <dd>{llm.model ?? "-"}</dd>
        </div>
        <div>
          <dt>latency</dt>
          <dd>{formatLatency(llm.latency_ms)}</dd>
        </div>
        <div>
          <dt>error</dt>
          <dd className={llm.error ? "error-text" : undefined}>{llm.error ?? "-"}</dd>
        </div>
      </dl>
      {llm.answer ? <pre className="debug-code">{llm.answer}</pre> : null}
    </section>
  );
}

function SnapshotPanel({ title, value }: { title: string; value: unknown }) {
  return (
    <section className="panel config-snapshot">
      <h2>{title}</h2>
      <pre className="config-code">{formatJson(value)}</pre>
    </section>
  );
}

function formatScore(value: number) {
  return value.toFixed(2);
}

function formatLatency(value?: number | null) {
  return value == null ? "-" : `${value}ms`;
}

function formatJson(value: unknown) {
  if (value == null) {
    return "-";
  }
  return JSON.stringify(value, null, 2);
}

function optionalText(value: string) {
  const trimmed = value.trim();
  return trimmed ? trimmed : null;
}

function summarizeContent(value: string) {
  const cleaned = cleanDisplayText(value).replace(/\s+/g, " ");
  return cleaned.length > 96 ? `${cleaned.slice(0, 96)}...` : cleaned;
}
