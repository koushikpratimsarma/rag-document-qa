from langchain_text_splitters import RecursiveCharacterTextSplitter

from backend.config import settings


def get_text_splitter():
    return RecursiveCharacterTextSplitter(
        chunk_size=settings.max_chunk_size,
        chunk_overlap=settings.chunk_overlap,
        separators=["\n\n", "\n", " ", ""],
    )


def chunk_text(text: str):
    splitter = get_text_splitter()
    return splitter.split_text(text)
