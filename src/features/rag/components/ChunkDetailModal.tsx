import { X } from "lucide-react";

import type { DebugCandidate } from "../types";

type ChunkDetailModalProps = {
  candidate: DebugCandidate | null;
  onClose: () => void;
};

export function ChunkDetailModal({ candidate, onClose }: ChunkDetailModalProps) {
  if (!candidate) {
    return null;
  }

  const dialogTitle = `Chunk 详情 #${candidate.chunk_id}`;
  const titlePath = cleanDisplayText(candidate.heading_path ?? candidate.section_title ?? "未分章节");
  const sectionTitle = cleanDisplayText(candidate.section_title ?? "未分章节");
  const location = formatLocation(candidate);

  return (
    <div className="modal-backdrop" onMouseDown={onClose}>
      <section
        className="modal-panel chunk-detail-modal"
        role="dialog"
        aria-modal="true"
        aria-labelledby="chunk-detail-title"
        onMouseDown={(event) => event.stopPropagation()}
      >
        <div className="modal-header">
          <div>
            <span className="runtime-pill">rank #{candidate.rank}</span>
            <h2 id="chunk-detail-title">{dialogTitle}</h2>
          </div>
          <button className="icon-button" type="button" aria-label="关闭详情" onClick={onClose}>
            <X size={16} />
          </button>
        </div>

        <dl className="chunk-detail-grid">
          <div>
            <dt>文档</dt>
            <dd>{candidate.document_name}</dd>
          </div>
          <div>
            <dt>章节</dt>
            <dd>{sectionTitle}</dd>
          </div>
          <div className="chunk-detail-wide">
            <dt>标题路径</dt>
            <dd>{titlePath}</dd>
          </div>
          <div>
            <dt>父 chunk</dt>
            <dd>{candidate.parent_chunk_id ? `父 chunk #${candidate.parent_chunk_id}` : "无父 chunk"}</dd>
          </div>
          <div>
            <dt>子 chunk</dt>
            <dd>{candidate.child_index != null ? `子 chunk #${candidate.child_index}` : "非子 chunk"}</dd>
          </div>
          <div>
            <dt>chunk index</dt>
            <dd>#{candidate.chunk_index}</dd>
          </div>
          <div>
            <dt>文档 / 版本</dt>
            <dd>
              #{candidate.document_id} / #{candidate.document_version_id}
            </dd>
          </div>
          <div>
            <dt>页码</dt>
            <dd>{candidate.page_number != null ? `第 ${candidate.page_number} 页` : "暂无页码信息"}</dd>
          </div>
          <div>
            <dt>位置</dt>
            <dd>{location}</dd>
          </div>
          <div>
            <dt>分数</dt>
            <dd>
              V {formatScore(candidate.vector_score)} · K {formatScore(candidate.keyword_score)} · T{" "}
              {formatScore(candidate.trgm_score)} · 总 {formatScore(candidate.final_score)}
            </dd>
          </div>
        </dl>

        <div className="chunk-detail-content-grid">
          <section>
            <h3>子 chunk 内容</h3>
            <pre className="chunk-content">{candidate.content}</pre>
          </section>
          <section>
            <h3>带上下文内容</h3>
            <pre className="chunk-content chunk-context">{candidate.content_with_context ?? candidate.content}</pre>
          </section>
        </div>
      </section>
    </div>
  );
}

export function cleanDisplayText(value: string) {
  return value
    .replace(/\\([\\`*_{}\[\]()#+\-.!|>])/g, "$1")
    .replace(/[`*_#>|]/g, "")
    .replace(/\s+/g, " ")
    .replace(/\s*\/\s*/g, " / ")
    .trim();
}

function formatLocation(candidate: DebugCandidate) {
  if (candidate.start_char != null && candidate.end_char != null) {
    return `字符 ${candidate.start_char}-${candidate.end_char}`;
  }
  return "暂无字符位置";
}

function formatScore(value: number) {
  return value.toFixed(2);
}
