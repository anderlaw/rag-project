import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowLeft, FileUp, Search } from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";
import { Link, useParams } from "react-router-dom";

import { EmptyState } from "../components/common/EmptyState";
import { ErrorState } from "../components/common/ErrorState";
import { LoadingState } from "../components/common/LoadingState";
import { PageHeader } from "../components/common/PageHeader";
import { formatBytes } from "../lib/format";
import { getDocument, listDocumentChunks, uploadDocumentVersion } from "../features/documents/api";
import { ChunkPreview } from "../features/documents/components/ChunkPreview";
import { ChunkTable } from "../features/documents/components/ChunkTable";
import { DocumentStatusBadge } from "../features/documents/components/DocumentStatusBadge";
import { DocumentVersionEvalDraftButton } from "../features/documents/components/DocumentVersionEvalDraftButton";
import { VersionTimeline } from "../features/documents/components/VersionTimeline";
import type { ChunkType, DocumentChunk, DocumentVersion, JsonObject } from "../features/documents/types";

export function DocumentDetailPage() {
  const { documentId } = useParams();
  const id = Number(documentId);
  const queryClient = useQueryClient();
  const fileInputRef = useRef<HTMLInputElement | null>(null);
  const [selectedVersionId, setSelectedVersionId] = useState<number | null>(null);
  const [chunkType, setChunkType] = useState<ChunkType>("CHILD");
  const [sectionFilter, setSectionFilter] = useState("all");
  const [chunkKeyword, setChunkKeyword] = useState("");
  const [selectedChunk, setSelectedChunk] = useState<DocumentChunk | null>(null);

  const documentQuery = useQuery({
    queryKey: ["documents", id],
    queryFn: () => getDocument(id),
    enabled: Number.isFinite(id) && id > 0
  });

  const uploadVersionMutation = useMutation({
    mutationFn: (file: File) => uploadDocumentVersion(id, file),
    onSuccess: (result) => {
      queryClient.invalidateQueries({ queryKey: ["documents"] });
      queryClient.invalidateQueries({ queryKey: ["documents", id] });
      queryClient.invalidateQueries({ queryKey: ["documents", id, "chunks"] });
      setSelectedVersionId(result.version_id);
      setSectionFilter("all");
      setSelectedChunk(null);
    }
  });

  const document = documentQuery.data;
  const selectedVersion = useMemo(
    () => resolveSelectedVersion(document?.versions ?? [], document?.current_version_id ?? null, selectedVersionId),
    [document?.current_version_id, document?.versions, selectedVersionId]
  );

  useEffect(() => {
    if (!document || selectedVersionId !== null) {
      return;
    }
    const nextVersion = resolveSelectedVersion(document.versions, document.current_version_id, null);
    if (nextVersion) {
      setSelectedVersionId(nextVersion.id);
    }
  }, [document, selectedVersionId]);

  const chunksQuery = useQuery({
    queryKey: ["documents", id, "chunks", selectedVersion?.id ?? "none", chunkType],
    queryFn: () => listDocumentChunks(id, selectedVersion?.id ?? "current", chunkType),
    enabled: Number.isFinite(id) && Boolean(selectedVersion)
  });

  const chunks = chunksQuery.data?.items ?? [];
  const sectionOptions = useMemo(() => {
    const values = new Set<string>();
    for (const chunk of chunks) {
      values.add(chunkSectionValue(chunk));
    }
    return Array.from(values).sort((a, b) => a.localeCompare(b, "zh-CN"));
  }, [chunks]);

  const filteredChunks = useMemo(() => {
    const keyword = chunkKeyword.trim().toLowerCase();
    return chunks.filter((chunk) => {
      const text = `${chunk.content}\n${chunk.content_with_context ?? ""}`.toLowerCase();
      const matchesKeyword = !keyword || text.includes(keyword);
      const matchesSection = sectionFilter === "all" || chunkSectionValue(chunk) === sectionFilter;
      return matchesKeyword && matchesSection;
    });
  }, [chunks, chunkKeyword, sectionFilter]);

  const previewChunk =
    selectedChunk && filteredChunks.some((chunk) => chunk.id === selectedChunk.id) ? selectedChunk : filteredChunks[0];

  if (documentQuery.isLoading) {
    return <LoadingState label="加载文档详情" />;
  }
  if (documentQuery.error || !document) {
    return <ErrorState error={documentQuery.error ?? new Error("文档不存在")} onRetry={() => documentQuery.refetch()} />;
  }

  return (
    <div className="page-stack">
      <PageHeader
        title={`文档详情：${document.name}`}
        description={`类型：${document.file_type ?? "-"} · 当前版本：${
          selectedVersion ? `v${selectedVersion.version_no}` : "-"
        } · 状态：${document.status} · Chunk：${selectedVersion?.chunk_count ?? 0}`}
        actions={
          <>
            <Link className="button button-secondary" to="/documents">
              <ArrowLeft size={16} />
              返回
            </Link>
            <button
              className="button button-primary"
              type="button"
              disabled={uploadVersionMutation.isPending}
              onClick={() => fileInputRef.current?.click()}
            >
              <FileUp size={16} />
              {uploadVersionMutation.isPending ? "处理中" : "上传新版本"}
            </button>
            <input
              ref={fileInputRef}
              className="visually-hidden"
              type="file"
              accept=".txt,.md,.pdf,.docx"
              onChange={(event) => {
                const file = event.currentTarget.files?.[0];
                if (file) {
                  uploadVersionMutation.mutate(file);
                }
                event.currentTarget.value = "";
              }}
            />
          </>
        }
      />

      {uploadVersionMutation.error ? <ErrorState title="版本上传失败" error={uploadVersionMutation.error} /> : null}

      <section className="summary-grid">
        <div className="metric">
          <span>类型</span>
          <strong>{document.file_type ?? "-"}</strong>
        </div>
        <div className="metric">
          <span>大小</span>
          <strong>{formatBytes(document.file_size)}</strong>
        </div>
        <div className="metric">
          <span>当前版本</span>
          <strong>{selectedVersion ? `v${selectedVersion.version_no}` : "-"}</strong>
        </div>
        <div className="metric">
          <span>Chunk</span>
          <strong>{selectedVersion?.chunk_count ?? 0}</strong>
        </div>
      </section>

      <section className="detail-grid">
        <div className="panel">
          <h2>版本列表</h2>
          <VersionTimeline
            versions={document.versions}
            currentVersionId={document.current_version_id}
            selectedVersionId={selectedVersion?.id ?? null}
            onSelect={(version) => {
              setSelectedVersionId(version.id);
              setSectionFilter("all");
              setSelectedChunk(null);
            }}
          />
        </div>
        <div className="panel">
          <h2>当前版本信息</h2>
          {selectedVersion ? (
            <VersionInspector version={selectedVersion} />
          ) : (
            <EmptyState title="没有可用版本" />
          )}
        </div>
      </section>

      <section className="toolbar chunk-toolbar" aria-label="Chunk 筛选">
        <label>
          <span>类型</span>
          <select
            aria-label="Chunk 类型筛选"
            value={chunkType}
            onChange={(event) => {
              setChunkType(event.currentTarget.value as ChunkType);
              setSectionFilter("all");
              setSelectedChunk(null);
            }}
          >
            <option value="CHILD">CHILD</option>
            <option value="PARENT">PARENT</option>
          </select>
        </label>
        <label>
          <span>章节</span>
          <select
            aria-label="章节筛选"
            value={sectionFilter}
            onChange={(event) => {
              setSectionFilter(event.currentTarget.value);
              setSelectedChunk(null);
            }}
          >
            <option value="all">全部章节</option>
            {sectionOptions.map((section) => (
              <option key={section} value={section}>
                {section}
              </option>
            ))}
          </select>
        </label>
        <label className="search-field">
          <Search size={16} />
          <input
            type="search"
            placeholder="搜索 chunk 内容"
            value={chunkKeyword}
            onChange={(event) => setChunkKeyword(event.currentTarget.value)}
          />
        </label>
      </section>

      {chunksQuery.isLoading ? <LoadingState label="加载 chunks" /> : null}
      {chunksQuery.error ? <ErrorState error={chunksQuery.error} onRetry={() => chunksQuery.refetch()} /> : null}

      <section className="chunks-grid">
        <div>
          {filteredChunks.length > 0 ? (
            <ChunkTable
              chunks={filteredChunks}
              selectedId={previewChunk?.id}
              onSelect={(chunk) => setSelectedChunk(chunk)}
            />
          ) : (
            <EmptyState title="暂无 Chunk" />
          )}
        </div>
        <ChunkPreview document={document} chunk={previewChunk} />
      </section>
    </div>
  );
}

function VersionInspector({ version }: { version: DocumentVersion }) {
  return (
    <div className="version-inspector">
      <dl className="meta-grid">
        <div>
          <dt>Version ID</dt>
          <dd>{version.id}</dd>
        </div>
        <div>
          <dt>状态</dt>
          <dd>
            <DocumentStatusBadge status={version.status} />
          </dd>
        </div>
        <div>
          <dt>Chunk</dt>
          <dd>{version.chunk_count}</dd>
        </div>
        <div>
          <dt>文件</dt>
          <dd>{version.original_filename ?? "-"}</dd>
        </div>
        <div>
          <dt>File Hash</dt>
          <dd className="mono truncate">{version.file_hash ?? "-"}</dd>
        </div>
        <div>
          <dt>Storage Key</dt>
          <dd className="mono truncate">{version.storage_key ?? "-"}</dd>
        </div>
        <div>
          <dt>Parser Version</dt>
          <dd className="mono truncate">{version.parser_version ?? "-"}</dd>
        </div>
        <div>
          <dt>Chunk Strategy</dt>
          <dd className="mono truncate">{version.chunk_strategy_name ?? "-"}</dd>
        </div>
      </dl>

      <div className="inspector-actions">
        <DocumentVersionEvalDraftButton versionId={version.id} />
      </div>

      <ConfigSnapshot title="解析配置" value={version.parser_config_snapshot} />
      <ConfigSnapshot title="切片配置" value={version.chunk_config_snapshot} />
    </div>
  );
}

function ConfigSnapshot({ title, value }: { title: string; value: JsonObject | null }) {
  return (
    <section className="config-snapshot">
      <h3>{title}</h3>
      <pre className="config-code">{formatJson(value)}</pre>
    </section>
  );
}

function resolveSelectedVersion(
  versions: DocumentVersion[],
  currentVersionId: number | null,
  selectedVersionId: number | null
) {
  if (selectedVersionId != null) {
    const selected = versions.find((version) => version.id === selectedVersionId);
    if (selected) {
      return selected;
    }
  }
  if (currentVersionId != null) {
    const current = versions.find((version) => version.id === currentVersionId);
    if (current) {
      return current;
    }
  }
  return versions.at(-1) ?? null;
}

function chunkSectionValue(chunk: DocumentChunk) {
  return chunk.heading_path ?? chunk.section_title ?? "未分章节";
}

function formatJson(value: JsonObject | null) {
  return JSON.stringify(value ?? {}, null, 2);
}
