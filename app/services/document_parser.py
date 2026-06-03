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
        extension = Path(filename).suffix.lower().lstrip(".")
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
        heading_path: list[str] = []
        blocks: list[ParsedBlock] = []
        paragraph: list[str] = []

        def flush_paragraph() -> None:
            if paragraph:
                blocks.append(ParsedBlock(text="\n".join(paragraph).strip(), heading_path=tuple(heading_path)))
                paragraph.clear()

        for raw_line in text.splitlines():
            line = raw_line.strip()
            if not line:
                flush_paragraph()
                continue
            if line.startswith("#"):
                flush_paragraph()
                level = len(line) - len(line.lstrip("#"))
                title = line.lstrip("#").strip()
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
