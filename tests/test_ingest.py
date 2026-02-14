from __future__ import annotations

from app.ingest import _deep_get, _parse_preview, _safe_get


def test_safe_get_returns_first_present_value() -> None:
    data = {"a": "", "b": "value-b", "c": "value-c"}

    result = _safe_get(data, "a", "b", "c", default="fallback")

    assert result == "value-b"


def test_deep_get_resolves_nested_path() -> None:
    payload = {"outer": {"inner": {"name": "HiringCafe"}}}

    result = _deep_get(payload, ("outer", "inner", "name"), default="")

    assert result == "HiringCafe"


def test_parse_preview_strips_html() -> None:
    job = {"job_information": {"description_html": "<p>Hello <b>World</b></p>"}}

    preview = _parse_preview(job)

    assert "Hello" in preview
    assert "World" in preview
    assert "<" not in preview
