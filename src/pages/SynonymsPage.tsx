import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { CheckCircle2, Plus, Save, SearchCheck } from "lucide-react";
import { useState } from "react";
import { Link } from "react-router-dom";

import { ButtonSpinner } from "../components/common/ButtonSpinner";
import { ErrorState } from "../components/common/ErrorState";
import { LoadingState } from "../components/common/LoadingState";
import { PageHeader } from "../components/common/PageHeader";
import {
  addSynonymTerm,
  createSynonymGroup,
  listSynonymGroups,
  normalizeQuery,
  updateSynonymGroup,
  updateSynonymTerm
} from "../features/rag/api";
import type {
  SynonymGroup,
  SynonymGroupStatus,
  SynonymTerm,
  SynonymTermStatus,
  SynonymTermType
} from "../features/rag/types";

const GROUP_STATUS_LABELS: Record<SynonymGroupStatus, string> = {
  ACTIVE: "启用",
  INACTIVE: "停用"
};
const TERM_STATUS_LABELS: Record<SynonymTermStatus, string> = {
  ACTIVE: "启用",
  INACTIVE: "停用"
};
const TERM_TYPE_LABELS: Record<SynonymTermType, string> = {
  CANONICAL: "标准词",
  SYNONYM: "同义词"
};
const GROUP_STATUS_OPTIONS: SynonymGroupStatus[] = ["ACTIVE", "INACTIVE"];
const TERM_STATUS_OPTIONS: SynonymTermStatus[] = ["ACTIVE", "INACTIVE"];
const TERM_TYPE_OPTIONS: SynonymTermType[] = ["CANONICAL", "SYNONYM"];

export function SynonymsPage() {
  const queryClient = useQueryClient();
  const [groupName, setGroupName] = useState("");
  const [description, setDescription] = useState("");
  const [canonicalTerm, setCanonicalTerm] = useState("");
  const [synonymsText, setSynonymsText] = useState("");
  const [testQuestion, setTestQuestion] = useState("告诉我技术栈是啥");

  const synonymsQuery = useQuery({
    queryKey: ["rag-synonyms"],
    queryFn: listSynonymGroups
  });

  const createMutation = useMutation({
    mutationFn: createSynonymGroup,
    onSuccess: () => {
      setGroupName("");
      setDescription("");
      setCanonicalTerm("");
      setSynonymsText("");
      queryClient.invalidateQueries({ queryKey: ["rag-synonyms"] });
    }
  });

  const updateGroupMutation = useMutation({
    mutationFn: ({ groupId, status }: { groupId: number; status: SynonymGroupStatus }) =>
      updateSynonymGroup(groupId, { status }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["rag-synonyms"] })
  });

  const addTermMutation = useMutation({
    mutationFn: ({ groupId, term, termType }: { groupId: number; term: string; termType: SynonymTermType }) =>
      addSynonymTerm(groupId, { term, term_type: termType, language: detectLanguage(term), status: "ACTIVE" }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["rag-synonyms"] })
  });

  const updateTermMutation = useMutation({
    mutationFn: ({ termId, status }: { termId: number; status: SynonymTermStatus }) => updateSynonymTerm(termId, { status }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["rag-synonyms"] })
  });

  const normalizeMutation = useMutation({
    mutationFn: normalizeQuery
  });

  const canCreate = Boolean(groupName.trim() && (canonicalTerm.trim() || synonymsText.trim()));

  return (
    <div className="page-stack">
      <PageHeader
        title="检索词典"
        description="维护 query normalization 使用的标准词和同义词，保存后立即参与检索调试。"
        actions={
          <Link className="button button-secondary" to="/rag/debug">
            <SearchCheck size={16} />
            打开检索调试
          </Link>
        }
      />

      <section className="synonym-workbench">
        <form
          className="panel synonym-form"
          onSubmit={(event) => {
            event.preventDefault();
            const terms = buildTermRequests(canonicalTerm, synonymsText);
            if (terms.length === 0) {
              return;
            }
            createMutation.mutate({
              name: groupName.trim(),
              description: optionalText(description),
              status: "ACTIVE",
              terms
            });
          }}
        >
          <div className="panel-title-row">
            <h2>新增词组</h2>
            <Plus size={16} />
          </div>
          <label>
            <span>词组名称</span>
            <input
              className="plain-input"
              value={groupName}
              onChange={(event) => setGroupName(event.currentTarget.value)}
              placeholder="例如：客户画像"
            />
          </label>
          <label>
            <span>描述</span>
            <input
              className="plain-input"
              value={description}
              onChange={(event) => setDescription(event.currentTarget.value)}
              placeholder="例如：获客领域词"
            />
          </label>
          <label>
            <span>标准词</span>
            <input
              className="plain-input"
              value={canonicalTerm}
              onChange={(event) => setCanonicalTerm(event.currentTarget.value)}
              placeholder="例如：客户画像"
            />
          </label>
          <label>
            <span>同义词</span>
            <textarea
              value={synonymsText}
              onChange={(event) => setSynonymsText(event.currentTarget.value)}
              rows={5}
              placeholder="每行一个，或用逗号分隔：ICP、目标客户画像"
            />
          </label>
          <button className="button button-primary" type="submit" disabled={!canCreate || createMutation.isPending}>
            {createMutation.isPending ? <ButtonSpinner label="保存词组中" /> : <Save size={16} />}
            {createMutation.isPending ? "保存中" : "保存词组"}
          </button>
          {createMutation.data ? (
            <p className="success-text">
              <CheckCircle2 size={16} />
              词组 #{createMutation.data.id} 已保存
            </p>
          ) : null}
          {createMutation.error ? <p className="error-text">{formatError(createMutation.error)}</p> : null}
        </form>

        <section className="panel synonym-form">
          <div className="panel-title-row">
            <h2>测试 Query Normalization</h2>
            <SearchCheck size={16} />
          </div>
          <label>
            <span>问题</span>
            <textarea
              value={testQuestion}
              onChange={(event) => setTestQuestion(event.currentTarget.value)}
              rows={4}
              placeholder="输入要试算的用户问题"
            />
          </label>
          <button
            className="button button-primary"
            type="button"
            disabled={!testQuestion.trim() || normalizeMutation.isPending}
            onClick={() => normalizeMutation.mutate(testQuestion)}
          >
            {normalizeMutation.isPending ? <ButtonSpinner label="试算中" /> : <SearchCheck size={16} />}
            {normalizeMutation.isPending ? "试算中" : "试算"}
          </button>
          {normalizeMutation.data ? (
            <dl className="normalization-result">
              <div>
                <dt>清洗后 query</dt>
                <dd>{normalizeMutation.data.normalized_text}</dd>
              </div>
              <div>
                <dt>扩展后 query</dt>
                <dd>{normalizeMutation.data.expanded_text}</dd>
              </div>
              <div>
                <dt>命中词组</dt>
                <dd>{normalizeMutation.data.applied_synonym_groups.join("、") || "-"}</dd>
              </div>
            </dl>
          ) : null}
          {normalizeMutation.error ? <p className="error-text">{formatError(normalizeMutation.error)}</p> : null}
        </section>
      </section>

      {synonymsQuery.isLoading ? <LoadingState label="加载检索词典" /> : null}
      {synonymsQuery.error ? <ErrorState title="加载检索词典失败" error={synonymsQuery.error} onRetry={() => synonymsQuery.refetch()} /> : null}
      {synonymsQuery.data ? (
        <SynonymGroupsPanel
          groups={synonymsQuery.data.items}
          pendingGroupId={updateGroupMutation.variables?.groupId ?? null}
          pendingTermId={updateTermMutation.variables?.termId ?? null}
          addingGroupId={addTermMutation.variables?.groupId ?? null}
          onUpdateGroupStatus={(groupId, status) => updateGroupMutation.mutate({ groupId, status })}
          onUpdateTermStatus={(termId, status) => updateTermMutation.mutate({ termId, status })}
          onAddTerm={(groupId, term, termType) => addTermMutation.mutate({ groupId, term, termType })}
        />
      ) : null}
    </div>
  );
}

function SynonymGroupsPanel({
  groups,
  pendingGroupId,
  pendingTermId,
  addingGroupId,
  onUpdateGroupStatus,
  onUpdateTermStatus,
  onAddTerm
}: {
  groups: SynonymGroup[];
  pendingGroupId: number | null;
  pendingTermId: number | null;
  addingGroupId: number | null;
  onUpdateGroupStatus: (groupId: number, status: SynonymGroupStatus) => void;
  onUpdateTermStatus: (termId: number, status: SynonymTermStatus) => void;
  onAddTerm: (groupId: number, term: string, termType: SynonymTermType) => void;
}) {
  return (
    <section className="panel synonym-list-panel">
      <div className="panel-title-row">
        <h2>词组列表</h2>
        <span className="runtime-pill">{groups.length} groups</span>
      </div>
      {groups.length === 0 ? (
        <div className="empty-state">
          <div>
            <h3>暂无词组</h3>
            <p>先新增一个标准词和同义词，保存后用于 query 扩展。</p>
          </div>
        </div>
      ) : (
        <div className="synonym-group-list">
          {groups.map((group) => (
            <SynonymGroupItem
              group={group}
              key={group.id}
              pendingGroupId={pendingGroupId}
              pendingTermId={pendingTermId}
              addingGroupId={addingGroupId}
              onUpdateGroupStatus={onUpdateGroupStatus}
              onUpdateTermStatus={onUpdateTermStatus}
              onAddTerm={onAddTerm}
            />
          ))}
        </div>
      )}
    </section>
  );
}

function SynonymGroupItem({
  group,
  pendingGroupId,
  pendingTermId,
  addingGroupId,
  onUpdateGroupStatus,
  onUpdateTermStatus,
  onAddTerm
}: {
  group: SynonymGroup;
  pendingGroupId: number | null;
  pendingTermId: number | null;
  addingGroupId: number | null;
  onUpdateGroupStatus: (groupId: number, status: SynonymGroupStatus) => void;
  onUpdateTermStatus: (termId: number, status: SynonymTermStatus) => void;
  onAddTerm: (groupId: number, term: string, termType: SynonymTermType) => void;
}) {
  const [newTerm, setNewTerm] = useState("");
  const [newTermType, setNewTermType] = useState<SynonymTermType>("SYNONYM");
  const isAdding = addingGroupId === group.id;
  const canonicalTerms = group.terms.filter((term) => term.term_type === "CANONICAL");
  const synonymTerms = group.terms.filter((term) => term.term_type === "SYNONYM");

  return (
    <article className="synonym-group-item">
      <div className="synonym-group-header">
        <div>
          <h3>{group.name}</h3>
          <p>{group.description || "未填写描述"}</p>
        </div>
        <label>
          <span>词组状态</span>
          <select
            value={group.status}
            disabled={pendingGroupId === group.id}
            onChange={(event) => onUpdateGroupStatus(group.id, event.currentTarget.value as SynonymGroupStatus)}
          >
            {GROUP_STATUS_OPTIONS.map((status) => (
              <option key={status} value={status}>
                {GROUP_STATUS_LABELS[status]}
              </option>
            ))}
          </select>
        </label>
      </div>

      <TermBucket title="标准词" terms={canonicalTerms} pendingTermId={pendingTermId} onUpdateTermStatus={onUpdateTermStatus} />
      <TermBucket title="同义词" terms={synonymTerms} pendingTermId={pendingTermId} onUpdateTermStatus={onUpdateTermStatus} />

      <form
        className="synonym-add-term"
        onSubmit={(event) => {
          event.preventDefault();
          if (!newTerm.trim()) {
            return;
          }
          onAddTerm(group.id, newTerm.trim(), newTermType);
          setNewTerm("");
        }}
      >
        <label>
          <span>新增词条</span>
          <input
            className="plain-input"
            value={newTerm}
            onChange={(event) => setNewTerm(event.currentTarget.value)}
            placeholder="例如：ICP"
          />
        </label>
        <label>
          <span>词条类型</span>
          <select value={newTermType} onChange={(event) => setNewTermType(event.currentTarget.value as SynonymTermType)}>
            {TERM_TYPE_OPTIONS.map((type) => (
              <option key={type} value={type}>
                {TERM_TYPE_LABELS[type]}
              </option>
            ))}
          </select>
        </label>
        <button className="button button-secondary" type="submit" disabled={!newTerm.trim() || isAdding}>
          {isAdding ? <ButtonSpinner label="新增词条中" /> : <Plus size={16} />}
          {isAdding ? "新增中" : "新增词条"}
        </button>
      </form>
    </article>
  );
}

function TermBucket({
  title,
  terms,
  pendingTermId,
  onUpdateTermStatus
}: {
  title: string;
  terms: SynonymTerm[];
  pendingTermId: number | null;
  onUpdateTermStatus: (termId: number, status: SynonymTermStatus) => void;
}) {
  return (
    <div className="synonym-term-bucket">
      <span>{title}</span>
      {terms.length === 0 ? (
        <p className="muted">暂无{title}</p>
      ) : (
        <div className="synonym-term-list">
          {terms.map((term) => (
            <div className="synonym-term-chip" key={term.id}>
              <strong>{term.term}</strong>
              <small>{TERM_TYPE_LABELS[term.term_type]}</small>
              <select
                value={term.status}
                disabled={pendingTermId === term.id}
                aria-label={`${term.term} 状态`}
                onChange={(event) => onUpdateTermStatus(term.id, event.currentTarget.value as SynonymTermStatus)}
              >
                {TERM_STATUS_OPTIONS.map((status) => (
                  <option key={status} value={status}>
                    {TERM_STATUS_LABELS[status]}
                  </option>
                ))}
              </select>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function buildTermRequests(canonicalTerm: string, synonymsText: string) {
  const canonical = splitTerms(canonicalTerm);
  const synonyms = splitTerms(synonymsText);
  return [
    ...canonical.map((term) => ({
      term,
      term_type: "CANONICAL" as const,
      language: detectLanguage(term),
      weight: 1,
      status: "ACTIVE" as const
    })),
    ...synonyms.map((term) => ({
      term,
      term_type: "SYNONYM" as const,
      language: detectLanguage(term),
      weight: 1,
      status: "ACTIVE" as const
    }))
  ];
}

function splitTerms(value: string) {
  const seen = new Set<string>();
  return value
    .split(/[\n,，;；]+/)
    .map((term) => term.trim())
    .filter((term) => {
      const key = term.toLowerCase();
      if (!term || seen.has(key)) {
        return false;
      }
      seen.add(key);
      return true;
    });
}

function detectLanguage(value: string) {
  if (/[\u4e00-\u9fff]/.test(value)) {
    return "zh";
  }
  if (/[a-z]/i.test(value)) {
    return "en";
  }
  return "mixed";
}

function optionalText(value: string) {
  const trimmed = value.trim();
  return trimmed ? trimmed : null;
}

function formatError(error: unknown) {
  return error instanceof Error ? error.message : "请求失败";
}
