import { AlertTriangle } from "lucide-react";

import type { DebugDocumentDiagnostics } from "../types";

type DocumentDiagnosticsProps = {
  diagnostics?: DebugDocumentDiagnostics | null;
};

export function DocumentDiagnostics({ diagnostics }: DocumentDiagnosticsProps) {
  if (!diagnostics) {
    return null;
  }

  return (
    <section className="panel diagnostics-panel">
      <div className="panel-title-row">
        <h2>文档状态诊断</h2>
        <AlertTriangle size={16} />
      </div>
      <div className="diagnostics-metrics">
        <div>
          <span>Active 文档</span>
          <strong>{diagnostics.active_document_count} active documents</strong>
        </div>
        <div>
          <span>可检索子 chunk</span>
          <strong>{diagnostics.searchable_child_chunk_count} searchable chunks</strong>
        </div>
      </div>

      {diagnostics.warnings.length > 0 ? (
        <ul className="diagnostics-warnings">
          {diagnostics.warnings.map((warning) => (
            <li key={warning}>{warning}</li>
          ))}
        </ul>
      ) : (
        <p className="muted">未发现明显的文档状态问题。</p>
      )}

      {diagnostics.inactive_related_documents.length > 0 ? (
        <div className="diagnostics-doc-list">
          {diagnostics.inactive_related_documents.map((document) => (
            <article className="diagnostics-doc" key={document.document_id}>
              <div>
                <strong>{document.name}</strong>
                <span>{document.match_reason}</span>
              </div>
              <div className="diagnostics-doc-meta">
                <span>{document.status}</span>
                <span>{document.version_status ?? "无当前版本"}</span>
                <span>{document.chunk_count ?? 0} chunks</span>
              </div>
            </article>
          ))}
        </div>
      ) : null}
    </section>
  );
}
