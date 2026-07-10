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


def test_chunk_pages_row_data_splits_on_lines():
    """Excel/CSV-style rows (no sentence punctuation) must chunk on row
    boundaries instead of being hard-split mid-row."""
    rows = [f"SKU: {i:04d}; Name: Widget {i}; Price: {i * 10}" for i in range(100)]
    pages = [PageText(page=1, section="Sheet: Products", text="\n".join(rows))]
    chunks = chunk_pages(pages, size=200, overlap=40)
    assert len(chunks) > 1
    row_set = set(rows)
    for chunk in chunks:
        for line in chunk.text.splitlines():
            assert line in row_set  # every line is an intact row
    # every row survives chunking
    covered = {line for c in chunks for line in c.text.splitlines()}
    assert covered == row_set


def test_row_oriented_page_never_merges_or_splits_rows():
    """Tabular rows (row_oriented=True) must map 1:1 to chunks, regardless of
    the size budget — no packing several tickets into one chunk, no splitting
    a ticket's opened/closed pair across chunks."""
    rows = [f"Opened: issue {i} engine ENG-{i:04d}; Closed: resolution {i}" for i in range(500)]
    pages = [PageText(page=1, section="Sheet: Tickets", text="\n".join(rows), row_oriented=True)]
    chunks = chunk_pages(pages, size=800, overlap=120)
    assert len(chunks) == 500
    assert [c.text for c in chunks] == rows


def test_chunk_indices_increment():
    pages = [
        PageText(page=1, section="", text="A. " * 300),
        PageText(page=2, section="", text="B. " * 300),
    ]
    chunks = chunk_pages(pages, size=150, overlap=20)
    indices = [c.index for c in chunks]
    assert indices == sorted(indices)
    assert len(set(indices)) == len(indices)
