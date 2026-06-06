from dataclasses import dataclass
from io import BytesIO
from pathlib import Path

from docx import Document
from pypdf import PdfReader


@dataclass(frozen=True)
class ParsedBlock:
    text: str
    heading_path: tuple[str, ...] = ()


class DocumentParser:
    version = "document-parser-v1"

    def config_snapshot(self) -> dict:
        return {
            "parser": "pypdf/python-docx/plaintext",
            "version": self.version,
            "split_paragraphs": True,
        }

    def parse(self, *, filename: str, file_bytes: bytes) -> list[ParsedBlock]:
        # 从文件名提取小写且不带前导点的扩展名，例如 Report.PDF -> pdf。
        extension = Path(filename).suffix.lower().lstrip(".")
        # 当前解析器按上传文件名扩展名选择；如需防止伪造扩展名，应单独增加内容嗅探校验。
        if extension == "pdf":
            text = self._parse_pdf(file_bytes)
            return self._paragraph_blocks(text)
        if extension == "docx":
            text = self._parse_docx(file_bytes)
            return self._paragraph_blocks(text)
        if extension == "md":
            return self._parse_markdown(file_bytes)
        if extension == "txt":
            return self._paragraph_blocks(file_bytes.decode("utf-8", errors="replace"))
        raise ValueError(f"unsupported file extension: {extension}")

    def _parse_pdf(self, file_bytes: bytes) -> str:
        reader = PdfReader(BytesIO(file_bytes))
        return "\n\n".join(page.extract_text() or "" for page in reader.pages)

    def _parse_docx(self, file_bytes: bytes) -> str:
        document = Document(BytesIO(file_bytes))
        return "\n\n".join(paragraph.text for paragraph in document.paragraphs if paragraph.text.strip())

    def _parse_markdown(self, file_bytes: bytes) -> list[ParsedBlock]:
        text = file_bytes.decode("utf-8", errors="replace")
        # 段落块列表保存解析结果，每个块携带当前 heading_path。
        blocks: list[ParsedBlock] = []
        heading_path: list[str] = []
        paragraph: list[str] = []

        def flush_paragraph() -> None:
            if paragraph:
                blocks.append(ParsedBlock(text="\n".join(paragraph).strip(), heading_path=tuple(heading_path)))
                paragraph.clear()
        # 按行解析 Markdown，splitlines 会识别不同平台的换行符。
        for raw_line in text.splitlines():
            line = raw_line.strip()
            if not line:
                flush_paragraph()
                continue
            if line.startswith("#"):
                flush_paragraph()
                # 标题层级由连续 # 数量决定。
                level = len(line) - len(line.lstrip("#"))
                # 标题文本进入 heading_path，不直接作为正文段落。
                title = line.lstrip("#").strip()
                # 原地截断 heading_path，保留父级标题并替换当前层级之后的路径。
                heading_path[:] = heading_path[: max(level - 1, 0)]
                if title:
                    heading_path.append(title)
                continue
            paragraph.append(raw_line)
        flush_paragraph()
        return blocks or [ParsedBlock(text=text.strip())] if text.strip() else []

    def _paragraph_blocks(self, text: str) -> list[ParsedBlock]:
        paragraphs = [item.strip() for item in text.split("\n\n") if item.strip()]
        if not paragraphs and text.strip():
            paragraphs = [text.strip()]
        return [ParsedBlock(text=paragraph) for paragraph in paragraphs]
