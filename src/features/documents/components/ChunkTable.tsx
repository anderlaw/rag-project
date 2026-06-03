import type { DocumentChunk } from "../types";

type ChunkTableProps = {
  chunks: DocumentChunk[];
  selectedId?: number | null;
  onSelect: (chunk: DocumentChunk) => void;
};

export function ChunkTable({ chunks, selectedId, onSelect }: ChunkTableProps) {
  return (
    <div className="table-shell">
      <table className="data-table">
        <thead>
          <tr>
            <th>Index</th>
            <th>类型</th>
            <th>章节</th>
            <th>Parent</th>
            <th>范围</th>
            <th>长度</th>
            <th>内容摘要</th>
          </tr>
        </thead>
        <tbody>
          {chunks.map((chunk) => (
            <tr
              className={selectedId === chunk.id ? "selected-row" : ""}
              key={chunk.id}
              onClick={() => onSelect(chunk)}
            >
              <td>
                {chunk.chunk_index}
                {chunk.child_index != null ? `.${chunk.child_index}` : ""}
              </td>
              <td>{chunk.chunk_type}</td>
              <td>{chunk.heading_path ?? chunk.section_title ?? "-"}</td>
              <td>{chunk.parent_chunk_id ?? "-"}</td>
              <td>
                {chunk.start_char != null && chunk.end_char != null ? `${chunk.start_char}-${chunk.end_char}` : "-"}
              </td>
              <td>{chunk.content.length}</td>
              <td>{chunk.content.slice(0, 96)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
