from backend.llm.ollama_client import _extract_json
from backend.models.enums import Language
from backend.translation.translator import detect_language


def test_detect_japanese():
    assert detect_language("コンプレッサーの保証期間はどのくらいですか？") == Language.JA


def test_detect_english():
    assert detect_language("How long is the warranty on the compressor?") == Language.EN


def test_detect_empty():
    assert detect_language("   ") == Language.UNKNOWN


def test_extract_json_valid():
    assert _extract_json('{"a": 1}') == {"a": 1}


def test_extract_json_with_prefix():
    assert _extract_json('Here you go: {"a": 1} done') == {"a": 1}


def test_extract_json_repairs_truncation():
    truncated = '{"grounded": true, "suggestions": [{"answer": "5 years", "sources": [1]}'
    repaired = _extract_json(truncated)
    assert repaired is not None
    assert repaired["grounded"] is True
    assert repaired["suggestions"][0]["answer"] == "5 years"
