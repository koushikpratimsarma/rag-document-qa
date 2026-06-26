from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import List


@dataclass
class LoadedDocument:
    page_content: str
    metadata: dict | None = None


class OpenDataLoader:
    def __init__(self, path: str | Path):
        self.path = Path(path)

    def load(self) -> List[LoadedDocument]:
        if self.path.suffix.lower() == ".pdf":
            try:
                from pypdf import PdfReader
            except ImportError as exc:  # pragma: no cover
                raise RuntimeError("pypdf is required to read PDF files") from exc

            reader = PdfReader(str(self.path))
            pages = [page.extract_text() or "" for page in reader.pages]
            text = "\n\n".join(page for page in pages if page)
            return [LoadedDocument(page_content=text, metadata={"source": str(self.path)})]

        text = self.path.read_text(encoding="utf-8", errors="ignore")
        return [LoadedDocument(page_content=text, metadata={"source": str(self.path)})]
