from pathlib import Path
from pypdf import PdfReader


def extract_text_from_pdf(path: Path) -> str:
    reader = PdfReader(str(path))

    pages = []
    for page in reader.pages:
        text = page.extract_text()
        if text:
            pages.append(text)

    return "\n\n".join(pages)