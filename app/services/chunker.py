from dataclasses import dataclass

from app.core.config import Settings
from app.services.document_parser import ParsedBlock


@dataclass
class ChunkDraft:
    chunk_type: str
    chunk_index: int
    child_index: int | None
    heading_path: str | None
    section_title: str | None
    start_char: int | None
    end_char: int | None
    content: str
    content_with_context: str
    search_text: str
    search_tsv: str | None = None
    embedding: list[float] | None = None


@dataclass
class ChunkGroup:
    parent: ChunkDraft
    children: list[ChunkDraft]


class Chunker:
    strategy_name = "parent_child_v1"

    def __init__(self, settings: Settings) -> None:
        self.parent_size = settings.parent_chunk_size
        self.parent_overlap = settings.parent_chunk_overlap
        self.child_size = settings.child_chunk_size
        self.child_overlap = settings.child_chunk_overlap

    def config_snapshot(self) -> dict:
        return {
            "strategy": self.strategy_name,
            "parent_chunk_size": self.parent_size,
            "parent_chunk_overlap": self.parent_overlap,
            "child_chunk_size": self.child_size,
            "child_chunk_overlap": self.child_overlap,
        }

    def build_parent_child_chunks(self, blocks: list[ParsedBlock]) -> list[ChunkGroup]:
        groups: list[ChunkGroup] = []
        parent_index = 0
        absolute_start = 0

        for block in blocks:
            for parent_text, start_offset, end_offset in split_text(
                block.text,
                size=self.parent_size,
                overlap=self.parent_overlap,
            ):
                heading_path = " / ".join(block.heading_path) if block.heading_path else None
                section_title = block.heading_path[-1] if block.heading_path else None
                content_with_context = with_context(parent_text, heading_path)
                parent = ChunkDraft(
                    chunk_type="PARENT",
                    chunk_index=parent_index,
                    child_index=None,
                    heading_path=heading_path,
                    section_title=section_title,
                    start_char=absolute_start + start_offset,
                    end_char=absolute_start + end_offset,
                    content=parent_text,
                    content_with_context=content_with_context,
                    search_text=content_with_context,
                )

                children: list[ChunkDraft] = []
                for child_index, (child_text, child_start, child_end) in enumerate(
                    split_text(parent_text, size=self.child_size, overlap=self.child_overlap)
                ):
                    child_context = with_context(child_text, heading_path)
                    children.append(
                        ChunkDraft(
                            chunk_type="CHILD",
                            chunk_index=parent_index,
                            child_index=child_index,
                            heading_path=heading_path,
                            section_title=section_title,
                            start_char=absolute_start + start_offset + child_start,
                            end_char=absolute_start + start_offset + child_end,
                            content=child_text,
                            content_with_context=child_context,
                            search_text=child_context,
                        )
                    )

                groups.append(ChunkGroup(parent=parent, children=children))
                parent_index += 1

            absolute_start += len(block.text) + 2

        return groups


def split_text(text: str, *, size: int, overlap: int) -> list[tuple[str, int, int]]:
    stripped = text.strip()
    if not stripped:
        return []
    if len(stripped) <= size:
        return [(stripped, 0, len(stripped))]

    chunks: list[tuple[str, int, int]] = []
    start = 0
    safe_overlap = min(max(overlap, 0), size - 1)
    while start < len(stripped):
        end = min(start + size, len(stripped))
        chunk = stripped[start:end].strip()
        if chunk:
            chunks.append((chunk, start, end))
        if end == len(stripped):
            break
        start = max(end - safe_overlap, start + 1)
    return chunks


def with_context(content: str, heading_path: str | None) -> str:
    if heading_path:
        return f"{heading_path}\n\n{content}"
    return content
