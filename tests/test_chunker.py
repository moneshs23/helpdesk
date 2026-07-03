from backend.rag.chunker import chunk_pages
from backend.rag.document_loader import PageText


def test_chunk_pages_basic():
    text = " ".join(f"Sentence number {i}." for i in range(200))
    pages = [PageText(page=1, section="Intro", text=text)]
    chunks = chunk_pages(pages, size=200, overlap=40)
    assert len(chunks) > 1
    assert all(c.page == 1 for c in chunks)
    assert all(c.section == "Intro" for c in chunks)
    assert all(len(c.text) <= 400 for c in chunks)


def test_chunk_pages_empty():
    assert chunk_pages([PageText(page=1, section="", text="")]) == []


def test_chunk_indices_increment():
    pages = [
        PageText(page=1, section="", text="A. " * 300),
        PageText(page=2, section="", text="B. " * 300),
    ]
    chunks = chunk_pages(pages, size=150, overlap=20)
    indices = [c.index for c in chunks]
    assert indices == sorted(indices)
    assert len(set(indices)) == len(indices)
