import { useMutation } from "@tanstack/react-query";
import { Copy, FileSearch, Play, Search } from "lucide-react";
import { useMemo, useState } from "react";
import { Link } from "react-router-dom";

import { ButtonSpinner } from "../components/common/ButtonSpinner";
import { ErrorState } from "../components/common/ErrorState";
import { PageHeader } from "../components/common/PageHeader";
import { runDebugQuery } from "../features/rag/api";
import { ChunkDetailModal, cleanDisplayText } from "../features/rag/components/ChunkDetailModal";
import { DocumentDiagnostics } from "../features/rag/components/DocumentDiagnostics";
import type { DebugCandidate, DebugQueryResponse } from "../features/rag/types";

const DEFAULT_QUESTION = "差旅报销需要什么材料？";

export function DebugPage() {
  const [question, setQuestion] = useState(DEFAULT_QUESTION);
  const [useLlm, setUseLlm] = useState(true);
  const [finalTopK, setFinalTopK] = useState(5);
  const [minScore, setMinScore] = useState(0.55);
  const [selectedCandidate, setSelectedCandidate] = useState<DebugCandidate | null>(null);
  const [detailCandidate, setDetailCandidate] = useState<DebugCandidate | null>(null);

  const debugMutation = useMutation({
    mutationFn: runDebugQuery,
    onSuccess: (result) => {
      setSelectedCandidate(result.candidates[0] ?? null);
    }
  });

  const result = debugMutation.data;
  const activeCandidate = useMemo(() => {
    if (!result) {
      return null;
    }
    return selectedCandidate && result.candidates.some((candidate) => candidate.chunk_id === selectedCandidate.chunk_id)
      ? selectedCandidate
      : (result.candidates[0] ?? null);
  }, [result, selectedCandidate]);

  return (
    <div className="page-stack">
      <PageHeader title="检索调试" description="分析 query -> retrieval -> prompt -> answer 全链路。" />

      <form
        className="debug-form panel"
        onSubmit={(event) => {
          event.preventDefault();
          debugMutation.mutate({
            question,
            use_llm: useLlm,
            final_top_k: finalTopK,
            min_final_score: minScore
          });
        }}
      >
        <label className="debug-question-field">
          <span>问题</span>
          <textarea
            value={question}
            onChange={(event) => setQuestion(event.currentTarget.value)}
            rows={3}
            placeholder="输入要调试的知识库问题"
          />
        </label>

        <div className="debug-controls">
          <label className="toggle-field">
            <input type="checkbox" checked={useLlm} onChange={(event) => setUseLlm(event.currentTarget.checked)} />
            use_llm
          </label>
          <label>
            <span>final_top_k</span>
            <input
              className="number-input"
              type="number"
              min={0}
              max={50}
              value={finalTopK}
              onChange={(event) => setFinalTopK(Number(event.currentTarget.value))}
            />
          </label>
          <label>
            <span>min_final_score</span>
            <input
              className="number-input"
              type="number"
              min={0}
              max={1}
              step={0.01}
              value={minScore}
              onChange={(event) => setMinScore(Number(event.currentTarget.value))}
            />
          </label>
          <button className="button button-primary" type="submit" disabled={debugMutation.isPending || !question.trim()}>
            {debugMutation.isPending ? <ButtonSpinner label="调试运行中" /> : <Play size={16} />}
            {debugMutation.isPending ? "运行中" : "运行调试"}
          </button>
        </div>
      </form>

      {debugMutation.error ? <ErrorState title="调试查询失败" error={debugMutation.error} /> : null}

      {result?.query_log_id ? (
        <section className="panel query-log-callout">
          <div>
            <span className="runtime-pill">query log #{result.query_log_id}</span>
            <h2>本次调试已保存</h2>
            <p className="muted">可查看完整候选、Prompt 和 LLM 状态快照。</p>
          </div>
          <Link className="button button-secondary" to={`/rag/query-logs/${result.query_log_id}`}>
            <FileSearch size={16} />
            打开查询详情
          </Link>
        </section>
      ) : null}

      <DebugSummary result={result} />
      <DocumentDiagnostics diagnostics={result?.diagnostics} />

      <section className="debug-grid">
        <div className="panel">
          <div className="panel-title-row">
            <h2>检索候选 chunks</h2>
            <span className="runtime-pill">{result ? `${result.candidates.length} candidates` : "未运行"}</span>
          </div>
          <CandidateTable
            candidates={result?.candidates ?? []}
            selectedChunkId={activeCandidate?.chunk_id ?? null}
            onSelect={setSelectedCandidate}
            onOpenDetail={setDetailCandidate}
          />
        </div>

        <SelectedChunkPanel candidates={result?.selected_chunks ?? []} onOpenDetail={setDetailCandidate} />
      </section>

      <section className="debug-grid">
        <PromptViewer prompt={result?.prompt?.text ?? null} version={result?.prompt?.version ?? null} />
        <LlmResultPanel result={result} />
      </section>

      <ChunkDetailModal candidate={detailCandidate} onClose={() => setDetailCandidate(null)} />
    </div>
  );
}

function DebugSummary({ result }: { result?: DebugQueryResponse }) {
  if (!result) {
    return (
      <section className="summary-grid">
        <div className="metric">
          <span>搜索配置</span>
          <strong>默认混合检索</strong>
        </div>
        <div className="metric">
          <span>权重</span>
          <strong>.65/.25/.10</strong>
        </div>
        <div className="metric">
          <span>候选</span>
          <strong>-</strong>
        </div>
        <div className="metric">
          <span>Prompt</span>
          <strong>-</strong>
        </div>
      </section>
    );
  }

  return (
    <section className="summary-grid">
      <div className="metric">
        <span>搜索配置</span>
        <strong>{result.search_profile.name}</strong>
      </div>
      <div className="metric">
        <span>权重</span>
        <strong>
          {result.search_profile.vector_weight}/{result.search_profile.keyword_weight}/
          {result.search_profile.trgm_weight}
        </strong>
      </div>
      <div className="metric">
        <span>候选</span>
        <strong>{result.candidates.length}</strong>
      </div>
      <div className="metric">
        <span>进入 Prompt</span>
        <strong>{result.selected_chunks.length}</strong>
      </div>
    </section>
  );
}

function CandidateTable({
  candidates,
  selectedChunkId,
  onSelect,
  onOpenDetail
}: {
  candidates: DebugCandidate[];
  selectedChunkId: number | null;
  onSelect: (candidate: DebugCandidate) => void;
  onOpenDetail: (candidate: DebugCandidate) => void;
}) {
  if (candidates.length === 0) {
    return (
      <div className="empty-state">
        <div>
          <h3>暂无候选</h3>
          <p>输入问题后运行调试。</p>
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
            <tr
              className={candidate.chunk_id === selectedChunkId ? "selected-row" : ""}
              key={candidate.chunk_id}
              onClick={() => onSelect(candidate)}
            >
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
                <button
                  className="button button-secondary"
                  type="button"
                  onClick={(event) => {
                    event.stopPropagation();
                    onOpenDetail(candidate);
                  }}
                >
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

function SelectedChunkPanel({
  candidates,
  onOpenDetail
}: {
  candidates: DebugCandidate[];
  onOpenDetail: (candidate: DebugCandidate) => void;
}) {
  return (
    <section className="panel">
      <div className="panel-title-row">
        <h2>最终送入 Prompt 的 chunks</h2>
        <Search size={16} />
      </div>
      {candidates.length === 0 ? (
        <p className="muted">没有 chunk 达到阈值。</p>
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

function PromptViewer({ prompt, version }: { prompt: string | null; version: string | null }) {
  return (
    <section className="panel">
      <div className="panel-title-row">
        <h2>Prompt 预览</h2>
        <button
          className="icon-button"
          type="button"
          disabled={!prompt}
          aria-label="复制 Prompt"
          onClick={() => prompt && navigator.clipboard?.writeText(prompt)}
        >
          <Copy size={16} />
        </button>
      </div>
      <span className="runtime-pill">{version ?? "未构建"}</span>
      {prompt ? <pre className="debug-code">{prompt}</pre> : <p className="muted">未构建 prompt。</p>}
    </section>
  );
}

function LlmResultPanel({ result }: { result?: DebugQueryResponse }) {
  const llm = result?.llm;
  return (
    <section className="panel">
      <h2>LLM 回答</h2>
      {!llm ? (
        <p className="muted">运行调试后展示回答状态。</p>
      ) : (
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
            <dd>{llm.latency_ms != null ? `${llm.latency_ms}ms` : "-"}</dd>
          </div>
          <div>
            <dt>error</dt>
            <dd>{llm.error ?? "-"}</dd>
          </div>
        </dl>
      )}
      {llm?.answer ? <pre className="debug-code">{llm.answer}</pre> : null}
    </section>
  );
}

function formatScore(value: number) {
  return value.toFixed(2);
}

function summarizeContent(value: string) {
  const cleaned = cleanDisplayText(value).replace(/\s+/g, " ");
  return cleaned.length > 96 ? `${cleaned.slice(0, 96)}...` : cleaned;
}
