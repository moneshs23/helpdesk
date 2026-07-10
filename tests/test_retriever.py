from backend.models.enums import DocumentType
from backend.models.schemas import ChunkMetadata, RetrievedChunk
from backend.rag.retriever import (
    _cjk_bigrams,
    _keywords,
    _merge_hybrid,
    _prioritize_identifier_chunks,
)


def _chunk(id: str, text: str, score: float = 0.0) -> RetrievedChunk:
    return RetrievedChunk(
        id=id,
        text=text,
        score=score,
        metadata=ChunkMetadata(
            document_id="d", filename="f.xlsx", title="f",
            doc_type=DocumentType.XLSX, page=1, section="", chunk_index=0,
        ),
    )


def test_prioritize_keeps_all_same_vin_tickets_past_top_k():
    """One vehicle can have several tickets sharing a VIN — all of them must
    reach the LLM so the question text can pick the right Closed: answer,
    even when top_k is 1."""
    vin = "mec0463pcjp027764"
    chunks = [
        _chunk("t1", f"VIN: {vin.upper()}; Opened: brake question; Closed: A"),
        _chunk("t2", f"VIN: {vin.upper()}; Opened: seat question; Closed: B"),
        _chunk("other", "VIN: X; Opened: unrelated; Closed: C", score=0.9),
        _chunk("t3", f"VIN: {vin.upper()}; Opened: engine question; Closed: D"),
    ]
    kept = _prioritize_identifier_chunks(chunks, [vin], top_k=1)
    assert [c.id for c in kept] == ["t1", "t2", "t3"]


def test_prioritize_without_identifier_slices_to_top_k():
    chunks = [_chunk("a", "x", 0.9), _chunk("b", "y", 0.8)]
    assert [c.id for c in _prioritize_identifier_chunks(chunks, [], top_k=1)] == ["a"]


def test_prioritize_no_match_falls_back_to_top_k():
    chunks = [_chunk("a", "no vin here", 0.9), _chunk("b", "none here either", 0.8)]
    kept = _prioritize_identifier_chunks(chunks, ["mec9999999"], top_k=1)
    assert [c.id for c in kept] == ["a"]


def test_keywords_strips_stopwords_and_short_tokens():
    kws = _keywords("What is the part number for MX910051?")
    assert "mx910051" in kws
    assert "what" not in kws
    assert "is" not in kws


def test_keywords_keeps_trailing_vin_past_token_cap():
    """Users append the VIN at the end of long queries — it must survive the
    12-token cap, since it's the single most discriminative retrieval token."""
    long_query = (
        "customer reports rattling noise from rear suspension area during "
        "highway driving after recent service visit and requests replacement "
        "guidance for VIN MEC0463P1LP041029"
    )
    kws = _keywords(long_query)
    assert "mec0463p1lp041029" in kws


def test_keywords_extracts_cjk_bigrams_for_japanese_text():
    """A translated-to-English query loses the customer's exact original
    wording — Japanese ticket text needs bigram overlap on the *original*
    text to have any chance of an exact-match keyword hit."""
    kws = _keywords("シートベルトが年式で2種類あります")
    assert "シー" in kws
    assert "トベ" in kws


def test_cjk_bigrams_handles_half_width_katakana():
    bigrams = _cjk_bigrams("ｼｰﾄﾍﾞﾙﾄ")
    assert "ｼｰ" in bigrams
    assert all(len(b) == 2 for b in bigrams)


def test_cjk_bigrams_empty_for_pure_ascii():
    assert _cjk_bigrams("MX910051 seat belt") == []


def test_merge_hybrid_prefers_exact_keyword_match_on_tie():
    """A confirmed keyword hit (e.g. an exact part number) must not lose to a
    same-score keyword-less semantic hit just because of dict/insertion-order
    tie-breaking — this was a real bug that silently dropped exact matches
    whenever top_k was small (e.g. top_k=1)."""
    semantic = [{"id": "wrong-but-semantically-similar", "payload": {}, "score": 0.66}]
    keyword = [{"id": "right-exact-match", "payload": {}, "score": 1.0}]
    merged = _merge_hybrid(semantic, keyword)
    assert merged[0]["id"] == "right-exact-match"


def test_merge_hybrid_keeps_true_semantic_score_when_both_match():
    semantic = [{"id": "a", "payload": {}, "score": 0.9}]
    keyword = [{"id": "a", "payload": {}, "score": 1.0}]
    merged = _merge_hybrid(semantic, keyword)
    assert merged[0]["id"] == "a"
    assert merged[0]["score"] == 0.9  # true cosine preserved, not overwritten


def test_merge_hybrid_keyword_only_hit_reports_zero_score():
    keyword = [{"id": "kw-only", "payload": {}, "score": 1.0}]
    merged = _merge_hybrid([], keyword)
    assert merged[0]["id"] == "kw-only"
    assert merged[0]["score"] == 0.0


def test_extract_closed_returns_verbatim_answer_segment():
    from backend.rag.pipeline import _extract_closed

    text = (
        "VIN: JL5BHJ6S7SRP25072; Opened: need seat belt part number; "
        "Closed: The applicable part number is MK324092 - SEAT BELT,FR SEAT."
    )
    assert _extract_closed(text) == (
        "The applicable part number is MK324092 - SEAT BELT,FR SEAT."
    )
    assert _extract_closed("no ticket markers here") == ""
