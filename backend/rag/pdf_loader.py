from pathlib import Path

try:
    from opendataloader import OpenDataLoader
except ImportError:  # pragma: no cover
    OpenDataLoader = None


def extract_text_from_pdf(path: Path) -> str:
    if OpenDataLoader is None:
        raise RuntimeError("opendataloader is not installed")

    loader = OpenDataLoader(str(path))
    documents = loader.load()
    parts = []
    for document in documents:
        content = getattr(document, "page_content", None) or getattr(document, "text", None) or ""
        if content:
            parts.append(str(content))
    return "\n\n".join(parts)
