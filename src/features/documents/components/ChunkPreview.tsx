import type { DocumentChunk, DocumentDetail } from "../types";

type ChunkPreviewProps = {
  document: DocumentDetail;
  chunk?: DocumentChunk | null;
};

export function ChunkPreview({ document, chunk }: ChunkPreviewProps) {
  if (!chunk) {
    return (
      <section className="preview-panel">
        <h2>Chunk 内容</h2>
        <p className="muted">选择左侧 chunk 查看内容。</p>
      </section>
    );
  }

  const contextContent = chunk.content_with_context?.trim();

  return (
    <section className="preview-panel">
      <div className="preview-header">
        <h2>Chunk 内容</h2>
        <span className="mono">#{chunk.id}</span>
      </div>
      <dl className="meta-grid">
        <div>
          <dt>文档</dt>
          <dd>{document.name}</dd>
        </div>
        <div>
          <dt>章节</dt>
          <dd>{chunk.heading_path ?? "-"}</dd>
        </div>
        <div>
          <dt>Index</dt>
          <dd>
            {chunk.chunk_index}
            {chunk.child_index != null ? `.${chunk.child_index}` : ""}
          </dd>
        </div>
        <div>
          <dt>Parent</dt>
          <dd>{chunk.parent_chunk_id ?? "-"}</dd>
        </div>
        <div>
          <dt>字符范围</dt>
          <dd>{chunk.start_char != null && chunk.end_char != null ? `${chunk.start_char}-${chunk.end_char}` : "-"}</dd>
        </div>
        <div>
          <dt>类型</dt>
          <dd>{chunk.chunk_type}</dd>
        </div>
      </dl>
      {contextContent ? (
        <>
          <h3 className="preview-subtitle">Context 内容</h3>
          <pre className="chunk-content chunk-context">{contextContent}</pre>
        </>
      ) : null}
      <h3 className="preview-subtitle">原始内容</h3>
      <pre className="chunk-content">{chunk.content}</pre>
    </section>
  );
}
