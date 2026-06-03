import { FileUp, Trash2 } from "lucide-react";
import { Link } from "react-router-dom";

import { ButtonSpinner } from "../../../components/common/ButtonSpinner";
import { formatBytes, formatDateTime } from "../../../lib/format";
import type { DocumentSummary } from "../types";
import { DocumentStatusBadge } from "./DocumentStatusBadge";

type DocumentTableProps = {
  documents: DocumentSummary[];
  deletingId?: number | null;
  updatingId?: number | null;
  onDelete: (document: DocumentSummary) => void;
  onUploadVersion: (document: DocumentSummary, file: File) => void;
};

export function DocumentTable({ documents, deletingId, updatingId, onDelete, onUploadVersion }: DocumentTableProps) {
  return (
    <div className="table-shell">
      <table className="data-table">
        <thead>
          <tr>
            <th>文档名</th>
            <th>类型</th>
            <th>大小</th>
            <th>当前版本</th>
            <th>状态</th>
            <th>更新时间</th>
            <th>操作</th>
          </tr>
        </thead>
        <tbody>
          {documents.map((document) => (
            <tr key={document.id}>
              <td>
                <div className="document-name">{document.name}</div>
              </td>
              <td>{document.file_type ?? "-"}</td>
              <td>{formatBytes(document.file_size)}</td>
              <td>{document.current_version_id ? `#${document.current_version_id}` : "-"}</td>
              <td>
                <DocumentStatusBadge status={document.status} />
              </td>
              <td>{formatDateTime(document.updated_at)}</td>
              <td>
                <div className="table-actions">
                  <Link className="button button-secondary" to={`/documents/${document.id}`}>
                    查看详情
                  </Link>
                  <label
                    className={`icon-button ${updatingId === document.id ? "button-disabled" : ""}`}
                    aria-label={updatingId === document.id ? `上传 ${document.name} 新版本中` : `上传 ${document.name} 新版本`}
                  >
                    {updatingId === document.id ? <ButtonSpinner label="上传新版本中" /> : <FileUp size={16} />}
                    <span className="visually-hidden">上传新版本</span>
                    <input
                      className="visually-hidden"
                      type="file"
                      accept=".txt,.md,.pdf,.docx"
                      disabled={updatingId === document.id}
                      onChange={(event) => {
                        const file = event.currentTarget.files?.[0];
                        if (file) {
                          onUploadVersion(document, file);
                        }
                        event.currentTarget.value = "";
                      }}
                    />
                  </label>
                  <button
                    className="icon-button icon-button-danger"
                    type="button"
                    disabled={deletingId === document.id}
                    onClick={() => onDelete(document)}
                    aria-label={`删除 ${document.name}`}
                  >
                    {deletingId === document.id ? <ButtonSpinner label="删除文档中" /> : <Trash2 size={16} />}
                  </button>
                </div>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
