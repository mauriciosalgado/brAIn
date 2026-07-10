from langchain_text_splitters import MarkdownHeaderTextSplitter
from pathlib import Path


def split_markdown(text: str):
    headers_to_split_on = [("#", "Header 1"), ("##", "Header 2"), ("###", "Header 3")]
    splitter = MarkdownHeaderTextSplitter(
        headers_to_split_on=headers_to_split_on, strip_headers=False
    )
    return splitter.split_text(text)


def splitter(filepath: str | Path):
    if isinstance(filepath, str):
        filepath = Path(filepath)

    if not filepath.exists():
        raise FileNotFoundError(f"File not found: {filepath}")

    text = filepath.read_text()
    chunks = split_markdown(text)

    return chunks
