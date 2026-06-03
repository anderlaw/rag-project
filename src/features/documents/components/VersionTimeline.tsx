import { formatDateTime } from "../../../lib/format";
import type { DocumentVersion } from "../types";
import { DocumentStatusBadge } from "./DocumentStatusBadge";

type VersionTimelineProps = {
  versions: DocumentVersion[];
  currentVersionId: number | null;
  selectedVersionId?: number | null;
  onSelect?: (version: DocumentVersion) => void;
};

export function VersionTimeline({ versions, currentVersionId, selectedVersionId, onSelect }: VersionTimelineProps) {
  return (
    <div className="version-list">
      {versions.map((version) => (
        <button
          className={`version-item version-button ${selectedVersionId === version.id ? "version-item-selected" : ""}`}
          key={version.id}
          type="button"
          onClick={() => onSelect?.(version)}
        >
          <div className="version-item-header">
            <strong>v{version.version_no}</strong>
            <DocumentStatusBadge status={version.status} />
            {version.id === currentVersionId ? <span className="current-pill">当前</span> : null}
          </div>
          <dl className="meta-grid">
            <div>
              <dt>Chunk</dt>
              <dd>{version.chunk_count}</dd>
            </div>
            <div>
              <dt>文件</dt>
              <dd>{version.original_filename ?? "-"}</dd>
            </div>
            <div>
              <dt>Hash</dt>
              <dd className="mono truncate">{version.file_hash ?? "-"}</dd>
            </div>
            <div>
              <dt>存储 Key</dt>
              <dd className="mono truncate">{version.storage_key ?? "-"}</dd>
            </div>
            <div>
              <dt>Parser</dt>
              <dd className="mono truncate">{version.parser_version ?? "-"}</dd>
            </div>
            <div>
              <dt>Chunk Strategy</dt>
              <dd className="mono truncate">{version.chunk_strategy_name ?? "-"}</dd>
            </div>
            <div>
              <dt>创建</dt>
              <dd>{formatDateTime(version.created_at)}</dd>
            </div>
            <div>
              <dt>完成</dt>
              <dd>{formatDateTime(version.processed_at)}</dd>
            </div>
          </dl>
          {version.error_message ? <p className="error-text">{version.error_message}</p> : null}
        </button>
      ))}
    </div>
  );
}
