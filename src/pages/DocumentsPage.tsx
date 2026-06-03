import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Search } from "lucide-react";
import { useMemo, useState } from "react";

import { EmptyState } from "../components/common/EmptyState";
import { ErrorState } from "../components/common/ErrorState";
import { LoadingState } from "../components/common/LoadingState";
import { PageHeader } from "../components/common/PageHeader";
import { deleteDocument, listDocuments, uploadDocument, uploadDocumentVersion } from "../features/documents/api";
import { DocumentTable } from "../features/documents/components/DocumentTable";
import { DocumentUploadCard } from "../features/documents/components/DocumentUploadCard";
import type { DocumentSummary } from "../features/documents/types";

export function DocumentsPage() {
  const queryClient = useQueryClient();
  const [keyword, setKeyword] = useState("");
  const [typeFilter, setTypeFilter] = useState("all");
  const documentsQuery = useQuery({ queryKey: ["documents"], queryFn: listDocuments });

  const uploadMutation = useMutation({
    mutationFn: uploadDocument,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["documents"] })
  });
  const uploadVersionMutation = useMutation({
    mutationFn: ({ document, file }: { document: DocumentSummary; file: File }) => uploadDocumentVersion(document.id, file),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["documents"] })
  });
  const deleteMutation = useMutation({
    mutationFn: deleteDocument,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["documents"] })
  });

  const documents = documentsQuery.data?.items ?? [];
  const fileTypes = useMemo(() => Array.from(new Set(documents.map((item) => item.file_type).filter(Boolean))), [documents]);
  const filteredDocuments = documents.filter((document) => {
    const matchesKeyword = document.name.toLowerCase().includes(keyword.trim().toLowerCase());
    const matchesType = typeFilter === "all" || document.file_type === typeFilter;
    return matchesKeyword && matchesType;
  });

  return (
    <div className="page-stack">
      <PageHeader title="文档管理" description="上传文档、查看版本和 chunk 入库状态。" />

      <DocumentUploadCard pending={uploadMutation.isPending} onUpload={(file) => uploadMutation.mutate(file)} />

      {uploadMutation.error ? <ErrorState title="上传失败" error={uploadMutation.error} /> : null}
      {uploadVersionMutation.error ? <ErrorState title="版本上传失败" error={uploadVersionMutation.error} /> : null}
      {deleteMutation.error ? <ErrorState title="删除失败" error={deleteMutation.error} /> : null}

      <section className="toolbar">
        <label className="search-field">
          <Search size={16} />
          <input
            type="search"
            placeholder="搜索文档名"
            value={keyword}
            onChange={(event) => setKeyword(event.currentTarget.value)}
          />
        </label>
        <select value={typeFilter} onChange={(event) => setTypeFilter(event.currentTarget.value)} aria-label="文件类型筛选">
          <option value="all">全部类型</option>
          {fileTypes.map((type) => (
            <option key={type} value={type ?? ""}>
              {type}
            </option>
          ))}
        </select>
      </section>

      {documentsQuery.isLoading ? <LoadingState label="加载文档" /> : null}
      {documentsQuery.error ? <ErrorState error={documentsQuery.error} onRetry={() => documentsQuery.refetch()} /> : null}
      {!documentsQuery.isLoading && !documentsQuery.error && filteredDocuments.length === 0 ? (
        <EmptyState title="暂无文档" description="上传文档后会出现在这里。" />
      ) : null}
      {filteredDocuments.length > 0 ? (
        <DocumentTable
          documents={filteredDocuments}
          deletingId={deleteMutation.variables ?? null}
          updatingId={uploadVersionMutation.variables?.document.id ?? null}
          onDelete={(document) => {
            if (window.confirm(`删除 ${document.name}？`)) {
              deleteMutation.mutate(document.id);
            }
          }}
          onUploadVersion={(document, file) => uploadVersionMutation.mutate({ document, file })}
        />
      ) : null}
    </div>
  );
}
