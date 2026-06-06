import { useMutation } from "@tanstack/react-query";
import { ChevronDown, ChevronUp, FileText, Search, Send } from "lucide-react";
import { FormEvent, useState } from "react";
import { Link } from "react-router-dom";

import { ButtonSpinner } from "../components/common/ButtonSpinner";
import { EmptyState } from "../components/common/EmptyState";
import { ErrorState } from "../components/common/ErrorState";
import { PageHeader } from "../components/common/PageHeader";
import { searchDocuments, submitSearchFeedback } from "../features/rag/api";
import type { SearchFeedbackRating, SearchResult, SearchResponse } from "../features/rag/types";

const DEFAULT_QUESTION = "";

const RATING_OPTIONS: Array<{ value: SearchFeedbackRating; label: string }> = [
  { value: "HELPFUL", label: "有帮助" },
  { value: "PARTIALLY_HELPFUL", label: "部分有帮助" },
  { value: "NOT_HELPFUL", label: "无帮助" }
];

export function SearchPage() {
  const [question, setQuestion] = useState(DEFAULT_QUESTION);
  const [expandedIds, setExpandedIds] = useState<Set<number>>(new Set());
  const [rating, setRating] = useState<SearchFeedbackRating>("HELPFUL");
  const [comment, setComment] = useState("");
  const [expectedAnswer, setExpectedAnswer] = useState("");

  const searchMutation = useMutation({
    mutationFn: searchDocuments,
    onSuccess: () => {
      setExpandedIds(new Set());
      setRating("HELPFUL");
      setComment("");
      setExpectedAnswer("");
    }
  });

  const feedbackMutation = useMutation({
    mutationFn: ({ queryLogId }: { queryLogId: number }) =>
      submitSearchFeedback(queryLogId, {
        rating,
        comment: optionalText(comment),
        expected_answer: optionalText(expectedAnswer)
      })
  });

  const result = searchMutation.data;

  function handleSearch(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const trimmed = question.trim();
    if (!trimmed) {
      return;
    }
    searchMutation.mutate({ question: trimmed, use_llm: true });
  }

  function toggleContext(resultId: number) {
    setExpandedIds((current) => {
      const next = new Set(current);
      if (next.has(resultId)) {
        next.delete(resultId);
      } else {
        next.add(resultId);
      }
      return next;
    });
  }

  return (
    <div className="page-stack">
      <PageHeader title="文档检索" description="输入问题，从知识库中检索相关片段并生成每条结果的回答。" />

      <form className="search-panel panel" onSubmit={handleSearch}>
        <label className="debug-question-field">
          <span>问题</span>
          <textarea
            value={question}
            onChange={(event) => setQuestion(event.currentTarget.value)}
            rows={3}
            placeholder="输入要检索的问题"
          />
        </label>
        <div className="search-actions">
          <button className="button button-primary" type="submit" disabled={searchMutation.isPending || !question.trim()}>
            {searchMutation.isPending ? <ButtonSpinner label="检索中" /> : <Search size={16} />}
            {searchMutation.isPending ? "检索中" : "检索文档"}
          </button>
        </div>
      </form>

      {searchMutation.error ? <ErrorState title="检索失败" error={searchMutation.error} /> : null}

      {!result && !searchMutation.isPending ? (
        <EmptyState title="输入一个问题开始检索知识库" description="检索结果会展示对应回答、命中内容和上下文。" />
      ) : null}

      {result ? (
        <section className="search-result-layout">
          <div className="search-results-stack">
            <SearchResultSummary result={result} />
            {result.results.length > 0 ? (
              result.results.map((item) => (
                <SearchResultCard
                  key={item.query_candidate_id}
                  result={item}
                  expanded={expandedIds.has(item.query_candidate_id)}
                  onToggle={() => toggleContext(item.query_candidate_id)}
                />
              ))
            ) : (
              <EmptyState title="没有找到相关文档" description="可以调整问题描述，或提交反馈方便后续补充知识库。" />
            )}
          </div>

          <FeedbackPanel
            result={result}
            rating={rating}
            comment={comment}
            expectedAnswer={expectedAnswer}
            pending={feedbackMutation.isPending}
            savedId={feedbackMutation.data?.id ?? null}
            error={feedbackMutation.error}
            onRatingChange={setRating}
            onCommentChange={setComment}
            onExpectedAnswerChange={setExpectedAnswer}
            onSubmit={() => feedbackMutation.mutate({ queryLogId: result.query_log_id })}
          />
        </section>
      ) : null}
    </div>
  );
}

function SearchResultSummary({ result }: { result: SearchResponse }) {
  return (
    <section className="panel search-summary">
      <div>
        <span className="runtime-pill">query log #{result.query_log_id}</span>
        <h2>{statusText(result.status)}</h2>
        <p className="muted">检索结果 · {result.results.length} 条</p>
      </div>
      {result.warnings.length > 0 ? (
        <div className="search-warnings">
          {result.warnings.map((warning) => (
            <span className="status-badge status-warning" key={warning}>
              {warning}
            </span>
          ))}
        </div>
      ) : null}
    </section>
  );
}

function SearchResultCard({
  result,
  expanded,
  onToggle
}: {
  result: SearchResult;
  expanded: boolean;
  onToggle: () => void;
}) {
  const section = result.heading_path ?? result.section_title ?? "未分章节";
  return (
    <article className="panel search-result-card">
      <div className="search-result-heading">
        <div>
          <span className="runtime-pill">#{result.rank}</span>
          <h2>{result.document_name}</h2>
          <p>{section}</p>
        </div>
        <Link className="button button-secondary" to={`/documents/${result.document_id}`}>
          <FileText size={16} />
          查看文档
        </Link>
      </div>

      <div className="search-answer">
        <h3>回答</h3>
        <p>{answerText(result)}</p>
      </div>

      <div className="search-hit">
        <h3>命中内容</h3>
        <p>{result.hit_content}</p>
      </div>

      <button className="button button-secondary search-context-toggle" type="button" onClick={onToggle}>
        {expanded ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
        {expanded ? "收起上下文" : "展开上下文"}
      </button>

      {expanded ? (
        <div className="search-context-grid">
          <ContextBlock title="前文" content={result.before_context} />
          <ContextBlock title="后文" content={result.after_context} />
        </div>
      ) : null}
    </article>
  );
}

function ContextBlock({ title, content }: { title: string; content: string }) {
  return (
    <section className="context-block">
      <h3>{title}</h3>
      <p>{content || "无"}</p>
    </section>
  );
}

function FeedbackPanel({
  result,
  rating,
  comment,
  expectedAnswer,
  pending,
  savedId,
  error,
  onRatingChange,
  onCommentChange,
  onExpectedAnswerChange,
  onSubmit
}: {
  result: SearchResponse;
  rating: SearchFeedbackRating;
  comment: string;
  expectedAnswer: string;
  pending: boolean;
  savedId: number | null;
  error: unknown;
  onRatingChange: (value: SearchFeedbackRating) => void;
  onCommentChange: (value: string) => void;
  onExpectedAnswerChange: (value: string) => void;
  onSubmit: () => void;
}) {
  return (
    <aside className="panel feedback-panel">
      <h2>反馈结果</h2>
      <p className="muted">反馈会关联本次 query #{result.query_log_id}。</p>

      <div className="feedback-options" role="radiogroup" aria-label="反馈评分">
        {RATING_OPTIONS.map((option) => (
          <label key={option.value}>
            <input
              type="radio"
              name="search-feedback-rating"
              value={option.value}
              checked={rating === option.value}
              onChange={() => onRatingChange(option.value)}
            />
            {option.label}
          </label>
        ))}
      </div>

      <label className="form-field">
        <span>备注</span>
        <textarea value={comment} onChange={(event) => onCommentChange(event.currentTarget.value)} rows={4} />
      </label>

      <label className="form-field">
        <span>期望答案</span>
        <textarea
          value={expectedAnswer}
          onChange={(event) => onExpectedAnswerChange(event.currentTarget.value)}
          rows={4}
        />
      </label>

      <button className="button button-primary" type="button" disabled={pending} onClick={onSubmit}>
        {pending ? <ButtonSpinner label="提交中" /> : <Send size={16} />}
        {pending ? "提交中" : "提交反馈"}
      </button>

      {savedId ? <p className="success-text">反馈 #{savedId} 已保存</p> : null}
      {error ? <ErrorState title="反馈提交失败" error={error} /> : null}
    </aside>
  );
}

function statusText(status: SearchResponse["status"]) {
  switch (status) {
    case "COMPLETED":
      return "检索完成";
    case "NO_RECALL":
      return "没有找到相关文档";
    case "LLM_DISABLED":
      return "已返回相关资料，未生成答案";
    case "LLM_ERROR":
      return "生成答案失败，已返回相关资料";
  }
}

function answerText(result: SearchResult) {
  if (result.answer_status === "ANSWERED" && result.answer) {
    return result.answer;
  }
  if (result.answer_status === "NO_ANSWER") {
    return "该片段不足以回答这个问题。";
  }
  if (result.answer_status === "LLM_ERROR") {
    return "答案生成失败，请查看命中内容。";
  }
  return "未生成答案，请查看命中内容。";
}

function optionalText(value: string) {
  const trimmed = value.trim();
  return trimmed ? trimmed : null;
}
