from dataclasses import dataclass
from pathlib import Path
import re

from app.core.config import Settings
from app.services.document_parser import ParsedBlock

MEANINGLESS_DOCUMENT_NAMES = {
    "文档",
    "新建文档",
    "未命名",
    "document",
    "test",
    "扫描件",
    "副本",
}


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
    # 把解析出来的文档 blocks，切成「父 chunk」和「子 chunk」两级结构。
    # 注意⚠️：这里的*表示：* 后面的参数必须用关键字传参。，比如调用时必须：build_parent_child_chunks(blocks, document_name="产品说明书")
    def build_parent_child_chunks(self, blocks: list[ParsedBlock], *, document_name: str | None = None) -> list[ChunkGroup]:
        groups: list[ChunkGroup] = []
        parent_index = 0
        # 这是干啥的？？？？？
        absolute_start = 0

        for block in blocks:
            for parent_text, start_offset, end_offset in split_text(
                block.text,
                size=self.parent_size,
                overlap=self.parent_overlap,
            ):
                heading_path = " / ".join(block.heading_path) if block.heading_path else None
                # 最后一级标题
                section_title = block.heading_path[-1] if block.heading_path else None
                # 简单上下文拼接：标题+正文
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
                    search_text=build_search_text(
                        document_name=document_name,
                        heading_path=heading_path,
                        section_title=section_title,
                        content=parent_text,
                    ),
                )

                children: list[ChunkDraft] = []
                for child_index, (child_text, child_start, child_end) in enumerate(
                    split_text(parent_text, size=self.child_size, overlap=self.child_overlap)
                ):
                    child_context = with_context(child_text, heading_path)
                    children.append(
                        ChunkDraft(
                            chunk_type="CHILD",
                            # 这里的父子chunk_index貌似是一样的呀，todo:后续可以优化
                            chunk_index=parent_index,
                            child_index=child_index,
                            heading_path=heading_path,
                            section_title=section_title,
                            start_char=absolute_start + start_offset + child_start,
                            end_char=absolute_start + start_offset + child_end,
                            content=child_text,
                            content_with_context=child_context,
                            search_text=build_search_text(
                                document_name=document_name,
                                heading_path=heading_path,
                                section_title=section_title,
                                content=child_text,
                            ),
                        )
                    )

                groups.append(ChunkGroup(parent=parent, children=children))
                parent_index += 1
            # 当前 block 处理完后，更新 absolute_start，这里可能不准
            # 这里+2，大概率是因为原始文本里 block 和 block 之间有两个换行符，如果原文不是用两个换行分隔，则 absolute_start 就不准了。
            # 后续可以考虑在 ParsedBlock 里直接记录原文的 start_char 和 end_char，这样就不依赖 chunker 的切分逻辑了
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
    # 保证 overlap 小于 size。
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


def build_search_text(
    *,
    document_name: str | None,
    heading_path: str | None,
    section_title: str | None,
    content: str,
) -> str:
    parts: list[str] = []
    if document_name and is_meaningful_document_name(document_name):
        parts.append(f"[document_name] {normalize_file_stem(document_name)}")
    if heading_path:
        parts.append(f"[heading_path] {clean_structural_text(heading_path)}")
    if section_title:
        parts.append(f"[section_title] {clean_structural_text(section_title)}")
    parts.append("[content]")
    parts.append(content.strip())
    return "\n".join(part for part in parts if part)

# 文件名标准化
def normalize_file_stem(document_name: str) -> str:
    stem = Path(document_name).stem.strip()
    stem = re.sub(r"\s+", " ", stem)
    stem = re.sub(r"[\s_-]*(copy|副本)\s*\d*$", "", stem, flags=re.IGNORECASE).strip()
    return stem


def is_meaningful_document_name(document_name: str | None) -> bool:
    if not document_name:
        return False
    stem = normalize_file_stem(document_name)
    lowered = stem.lower()
    if not lowered or lowered in MEANINGLESS_DOCUMENT_NAMES:
        return False
    if re.fullmatch(r"\d+", lowered):
        return False
    if re.fullmatch(r"\d{4}[-_年]?\d{1,2}[-_月]?\d{1,2}日?", lowered):
        return False
    if len(lowered) <= 2:
        return False
    return True


def clean_structural_text(value: str) -> str:
    cleaned = value.replace("\\", "")
    cleaned = re.sub(r"[`*_#>\[\]()]+", " ", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned)
    return cleaned.strip()
