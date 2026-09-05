"""Tests for OpenAI-compatible LLM structure review."""

from __future__ import annotations

import io
import json
import urllib.error
import urllib.request
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from mdook.core.llm import (
    HeadingCorrection,
    LLMClientError,
    LLMConfig,
    OpenAICompatibleClient,
    build_skeleton,
    extract_json_payload,
    parse_corrections,
    run_structure_review,
    validate_corrections,
)
from mdook.core.llm.client import normalize_chat_endpoint, normalize_models_endpoint
from mdook.core.llm.prompts import format_skeleton
from mdook.core.models import BookManifest, PageData, TextBlock
from mdook.core.pipeline import convert
from mdook.core.rules.headings import Heading
from mdook.core.stages.semantic import run_semantic

# ---------------------------------------------------------------------------
# Client & Endpoint Normalization Tests
# ---------------------------------------------------------------------------


def test_normalize_chat_endpoint() -> None:
    assert (
        normalize_chat_endpoint("https://api.openai.com/v1")
        == "https://api.openai.com/v1/chat/completions"
    )
    assert (
        normalize_chat_endpoint("http://localhost:11434")
        == "http://localhost:11434/v1/chat/completions"
    )
    assert (
        normalize_chat_endpoint("http://localhost:11434/v1/")
        == "http://localhost:11434/v1/chat/completions"
    )
    assert (
        normalize_chat_endpoint("https://openrouter.ai/api/v1")
        == "https://openrouter.ai/api/v1/chat/completions"
    )
    assert (
        normalize_chat_endpoint("http://localhost:8000/v1/chat/completions")
        == "http://localhost:8000/v1/chat/completions"
    )


def test_normalize_models_endpoint() -> None:
    assert (
        normalize_models_endpoint("https://api.openai.com/v1")
        == "https://api.openai.com/v1/models"
    )
    assert (
        normalize_models_endpoint("https://api.groq.com/openai/v1")
        == "https://api.groq.com/openai/v1/models"
    )
    assert (
        normalize_models_endpoint("http://localhost:11434")
        == "http://localhost:11434/v1/models"
    )
    assert (
        normalize_models_endpoint("http://localhost:11434/v1/")
        == "http://localhost:11434/v1/models"
    )
    assert (
        normalize_models_endpoint("https://openrouter.ai/api/v1")
        == "https://openrouter.ai/api/v1/models"
    )
    assert (
        normalize_models_endpoint("https://api.openai.com/v1/chat/completions")
        == "https://api.openai.com/v1/models"
    )



def test_llm_config_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MDOOK_LLM_ENABLED", "true")
    monkeypatch.setenv("MDOOK_LLM_BASE_URL", "http://localhost:11434/v1")
    monkeypatch.setenv("MDOOK_LLM_API_KEY", "secret-test-key")
    monkeypatch.setenv("MDOOK_LLM_MODEL", "llama3.2")
    monkeypatch.setenv("MDOOK_LLM_TIMEOUT", "15.0")

    cfg = LLMConfig.from_env()
    assert cfg.enabled is True
    assert cfg.base_url == "http://localhost:11434/v1"
    assert cfg.api_key == "secret-test-key"
    assert cfg.model == "llama3.2"
    assert cfg.timeout_seconds == 15.0


def test_client_chat_completion_success() -> None:
    config = LLMConfig(
        base_url="https://api.openai.com/v1",
        api_key="test-key",
        model="gpt-4o-mini",
    )
    client = OpenAICompatibleClient(config)

    fake_response = {
        "choices": [
            {
                "message": {
                    "role": "assistant",
                    "content": '{"corrections": []}',
                }
            }
        ]
    }
    response_bytes = json.dumps(fake_response).encode("utf-8")

    mock_resp = io.BytesIO(response_bytes)
    mock_resp.status = 200  # type: ignore[attr-defined]

    with patch.object(urllib.request, "urlopen", return_value=mock_resp) as mock_urlopen:
        result = client.chat_completion([{"role": "user", "content": "hello"}])
        assert result == '{"corrections": []}'

        req: urllib.request.Request = mock_urlopen.call_args[0][0]
        assert req.full_url == "https://api.openai.com/v1/chat/completions"
        assert req.headers["Authorization"] == "Bearer test-key"
        assert req.headers["Content-type"] == "application/json"


def test_client_chat_completion_no_auth_header_when_no_key() -> None:
    config = LLMConfig(
        base_url="http://localhost:11434/v1",
        api_key=None,
        model="llama3.2",
    )
    client = OpenAICompatibleClient(config)

    fake_response = {"choices": [{"message": {"content": "ok"}}]}
    mock_resp = io.BytesIO(json.dumps(fake_response).encode("utf-8"))
    mock_resp.status = 200  # type: ignore[attr-defined]

    with patch.object(urllib.request, "urlopen", return_value=mock_resp) as mock_urlopen:
        client.chat_completion([{"role": "user", "content": "hi"}])
        req: urllib.request.Request = mock_urlopen.call_args[0][0]
        assert "Authorization" not in req.headers


def test_client_chat_completion_http_error() -> None:
    config = LLMConfig(base_url="https://api.openai.com/v1", api_key="bad-key")
    client = OpenAICompatibleClient(config)

    http_error = urllib.error.HTTPError(
        url="https://api.openai.com/v1/chat/completions",
        code=401,
        msg="Unauthorized",
        hdrs={},  # type: ignore[arg-type]
        fp=io.BytesIO(b'{"error": "Invalid API key"}'),
    )

    with patch.object(urllib.request, "urlopen", side_effect=http_error):
        with pytest.raises(LLMClientError, match="HTTP 401"):
            client.chat_completion([{"role": "user", "content": "test"}])


def test_client_test_connection_success() -> None:
    config = LLMConfig(
        base_url="https://api.openai.com/v1", api_key="good-key", model="gpt-4o-mini"
    )
    client = OpenAICompatibleClient(config)

    fake_response = {"choices": [{"message": {"content": "pong"}}]}
    mock_resp = io.BytesIO(json.dumps(fake_response).encode("utf-8"))
    mock_resp.status = 200  # type: ignore[attr-defined]

    with patch.object(urllib.request, "urlopen", return_value=mock_resp):
        success, message = client.test_connection(timeout_seconds=5.0)
        assert success is True
        assert "Connected" in message
        assert "gpt-4o-mini" in message


def test_client_test_connection_failure() -> None:
    config = LLMConfig(
        base_url="https://api.openai.com/v1", api_key="bad-key", model="gpt-4o-mini"
    )
    client = OpenAICompatibleClient(config)

    http_error = urllib.error.HTTPError(
        url="https://api.openai.com/v1/chat/completions",
        code=401,
        msg="Unauthorized",
        hdrs={},  # type: ignore[arg-type]
        fp=io.BytesIO(b'{"error": "Unauthorized"}'),
    )

    with patch.object(urllib.request, "urlopen", side_effect=http_error):
        success, message = client.test_connection(timeout_seconds=5.0)
        assert success is False
        assert "HTTP 401" in message


def test_client_list_models_success() -> None:
    config = LLMConfig(
        base_url="https://api.groq.com/openai/v1",
        api_key="test-key",
        model="llama-3.3-70b-versatile",
    )
    client = OpenAICompatibleClient(config)

    fake_response = {
        "object": "list",
        "data": [
            {"id": "llama-3.3-70b-versatile"},
            {"id": "llama-3.1-8b-instant"},
            {"id": "mixtral-8x7b-32768"},
        ],
    }
    mock_resp = io.BytesIO(json.dumps(fake_response).encode("utf-8"))
    mock_resp.status = 200  # type: ignore[attr-defined]

    with patch.object(urllib.request, "urlopen", return_value=mock_resp):
        models = client.list_models(timeout_seconds=5.0)
        assert len(models) == 3
        assert "llama-3.3-70b-versatile" in models
        assert "llama-3.1-8b-instant" in models
        assert "mixtral-8x7b-32768" in models


def test_client_list_models_failure() -> None:
    config = LLMConfig(
        base_url="https://api.openai.com/v1", api_key="bad-key", model="gpt-4o-mini"
    )
    client = OpenAICompatibleClient(config)

    http_error = urllib.error.HTTPError(
        url="https://api.openai.com/v1/models",
        code=401,
        msg="Unauthorized",
        hdrs={},  # type: ignore[arg-type]
        fp=io.BytesIO(b'{"error": "Invalid API key"}'),
    )

    with patch.object(urllib.request, "urlopen", side_effect=http_error):
        with pytest.raises(LLMClientError, match="HTTP 401"):
            client.list_models(timeout_seconds=5.0)




# ---------------------------------------------------------------------------
# Skeleton & Serialization Tests
# ---------------------------------------------------------------------------


def test_build_skeleton_and_formatting() -> None:
    b1 = TextBlock(
        text="CHAPTER 1",
        font_name="Arial",
        font_size=18.0,
        bbox=(50, 50, 200, 70),
        page_number=1,
    )
    b2 = TextBlock(
        text="It was a dark and stormy night.",
        font_name="Arial",
        font_size=11.0,
        bbox=(50, 80, 400, 95),
        page_number=1,
    )
    page1 = PageData(page_number=1, width=600, height=800, blocks=[b1, b2])

    h1 = Heading(level=1, title="CHAPTER 1", page_number=1, block=b1)
    skeleton = build_skeleton([h1], [page1])

    assert len(skeleton) == 1
    assert skeleton[0].id == 0
    assert skeleton[0].title == "CHAPTER 1"
    assert skeleton[0].first_body_snippet == "It was a dark and stormy night."

    formatted = format_skeleton(skeleton, book_title="Moby Dick", author="Herman Melville")
    assert "Book Title: Moby Dick" in formatted
    assert "Author: Herman Melville" in formatted
    assert '[ID 0] L1 (p. 1): "CHAPTER 1"' in formatted
    assert '> "It was a dark and stormy night."' in formatted


# ---------------------------------------------------------------------------
# JSON Extraction & Validation Tests
# ---------------------------------------------------------------------------


def test_extract_json_payload() -> None:
    raw_clean = '{"corrections": []}'
    assert extract_json_payload(raw_clean) == '{"corrections": []}'

    raw_fenced = '```json\n{\n  "corrections": []\n}\n```'
    assert json.loads(extract_json_payload(raw_fenced)) == {"corrections": []}

    raw_conversational = 'Here is the review:\n{"corrections": []}\nHope this helps!'
    assert json.loads(extract_json_payload(raw_conversational)) == {"corrections": []}


def test_parse_and_validate_corrections() -> None:
    response = json.dumps(
        {
            "corrections": [
                {"id": 0, "action": "keep", "reason": "Looks good"},
                {"id": 1, "action": "demote_to_body", "reason": "Mid-sentence OCR junk"},
                {"id": 2, "action": "set_level", "new_level": 1, "reason": "Chapter 2 at level 1"},
                {"id": 99, "action": "demote_to_body", "reason": "Non-existent heading"},
                {"id": 3, "action": "set_level", "new_level": 0, "reason": "Invalid level"},
            ]
        }
    )

    parsed = parse_corrections(response)
    assert len(parsed) == 5

    # total_headings = 4 (valid IDs are 0, 1, 2, 3)
    validated = validate_corrections(parsed, total_headings=4)
    # id 99 (out of bounds) and id 3 (new_level 0 < 1) should be filtered
    assert len(validated) == 3
    assert [c.id for c in validated] == [0, 1, 2]


def test_guardrail_prevents_100_percent_demotion() -> None:
    # If LLM attempts to demote every single heading in the book:
    corrections = [
        HeadingCorrection(id=0, action="demote_to_body"),
        HeadingCorrection(id=1, action="demote_to_body"),
    ]
    validated = validate_corrections(corrections, total_headings=2)
    # Demotions targeting 100% of headings must be rejected
    assert validated == []


# ---------------------------------------------------------------------------
# Review Execution & Semantic Pipeline Integration Tests
# ---------------------------------------------------------------------------


def test_run_structure_review_applies_corrections() -> None:
    b1 = TextBlock(
        text="PART ONE", font_name="Arial", font_size=20.0, bbox=(50, 50, 200, 70), page_number=1
    )
    b2 = TextBlock(
        text="CHAPTER 1", font_name="Arial", font_size=16.0, bbox=(50, 100, 200, 120), page_number=2
    )
    b3 = TextBlock(
        text="jecting me to denunciations",
        font_name="Arial",
        font_size=15.0,
        bbox=(50, 50, 200, 65),
        page_number=3,
    )

    h1 = Heading(level=1, title="PART ONE", page_number=1, block=b1)
    h2 = Heading(level=2, title="CHAPTER 1", page_number=2, block=b2)
    h3 = Heading(level=2, title="jecting me to denunciations", page_number=3, block=b3)

    page1 = PageData(page_number=1, width=600, height=800, blocks=[b1])
    page2 = PageData(page_number=2, width=600, height=800, blocks=[b2])
    page3 = PageData(page_number=3, width=600, height=800, blocks=[b3])

    manifest = BookManifest(
        file_path="test.pdf",
        title="Test Book",
        author="Author",
        total_pages=3,
        needs_ocr=False,
        profile="literature",
    )

    mock_client = MagicMock(spec=OpenAICompatibleClient)
    mock_client.chat_completion.return_value = json.dumps(
        {
            "corrections": [
                {"id": 0, "action": "set_part", "reason": "Top level Part division"},
                {
                    "id": 1,
                    "action": "set_level",
                    "new_level": 1,
                    "reason": "Promote Chapter 1 to L1",
                },
                {"id": 2, "action": "demote_to_body", "reason": "OCR line noise"},
            ]
        }
    )

    config = LLMConfig(enabled=True)
    cleaned, parts, report = run_structure_review(
        [h1, h2, h3], [page1, page2, page3], manifest, config, client=mock_client
    )

    assert report.success is True
    assert len(report.corrections_applied) == 3
    # h1 set as part
    assert len(parts) == 1
    assert parts[0].title == "PART ONE"
    # h2 promoted to level 1
    assert len(cleaned) == 1
    assert cleaned[0].title == "CHAPTER 1"
    assert cleaned[0].level == 1
    # h3 demoted and removed from headings
    assert not any(h.title == "jecting me to denunciations" for h in cleaned)


def test_run_semantic_with_llm_review_end_to_end() -> None:
    # Page 1: Chapter 1
    b_ch1 = TextBlock(
        text="Chapter 1: The Beginning",
        font_name="Arial-Bold",
        font_size=18.0,
        is_bold=True,
        bbox=(50, 50, 300, 70),
        page_number=1,
    )
    b_p1 = TextBlock(
        text="Once upon a time in a distant land.",
        font_name="Arial",
        font_size=12.0,
        bbox=(50, 80, 400, 95),
        page_number=1,
    )
    # Page 2: Stray OCR garbage line that looks like a heading
    b_noise = TextBlock(
        text="denunciations in speeches",
        font_name="Arial-Bold",
        font_size=18.0,
        is_bold=True,
        bbox=(50, 50, 300, 70),
        page_number=2,
    )
    b_p2 = TextBlock(
        text="and resolutions that were adopted.",
        font_name="Arial",
        font_size=12.0,
        bbox=(50, 80, 400, 95),
        page_number=2,
    )
    # Page 3: Chapter 2
    b_ch2 = TextBlock(
        text="Chapter 2: The Journey",
        font_name="Arial-Bold",
        font_size=18.0,
        is_bold=True,
        bbox=(50, 50, 300, 70),
        page_number=3,
    )
    b_p3 = TextBlock(
        text="The journey was long and perilous.",
        font_name="Arial",
        font_size=12.0,
        bbox=(50, 80, 400, 95),
        page_number=3,
    )

    pages = [
        PageData(page_number=1, width=600, height=800, blocks=[b_ch1, b_p1]),
        PageData(page_number=2, width=600, height=800, blocks=[b_noise, b_p2]),
        PageData(page_number=3, width=600, height=800, blocks=[b_ch2, b_p3]),
    ]
    manifest = BookManifest(
        file_path="book.pdf",
        title="My Book",
        author="Author",
        total_pages=3,
        needs_ocr=False,
        profile="literature",
    )

    mock_client = MagicMock(spec=OpenAICompatibleClient)
    # Mock LLM demotes the OCR noise (id 1)
    mock_client.chat_completion.return_value = json.dumps(
        {
            "corrections": [
                {"id": 1, "action": "demote_to_body", "reason": "Mid-sentence OCR junk"},
            ]
        }
    )

    llm_cfg = LLMConfig(enabled=True)
    tree = run_semantic(manifest, pages, llm_config=llm_cfg, llm_client=mock_client)

    # There should only be 2 chapters: "Chapter 1: The Beginning" and "Chapter 2: The Journey"
    assert len(tree.chapters) == 2
    assert tree.chapters[0].title == "Chapter 1: The Beginning"
    assert tree.chapters[1].title == "Chapter 2: The Journey"

    # The noise block text was merged into the body prose of Chapter 1!
    ch1_text = " ".join(
        item.text
        for sec in tree.chapters[0].sections
        for item in sec.content
        if hasattr(item, "text")
    )
    assert "denunciations in speeches" in ch1_text

    # Review result is recorded in metadata extra
    assert "llm_review" in tree.metadata.extra
    assert tree.metadata.extra["llm_review"]["success"] is True


def test_convert_pipeline_with_llm_review(tmp_path: Path) -> None:
    pdf_path = tmp_path / "test.pdf"
    out_dir = tmp_path / "vault_out"

    # Create a small valid PDF using PyMuPDF
    import fitz

    doc = fitz.open()
    p1 = doc.new_page()
    p1.insert_text((50, 70), "Chapter 1: Dawn", fontsize=18)
    p1.insert_text((50, 110), "The sun rose over the horizon.", fontsize=11)
    p2 = doc.new_page()
    p2.insert_text((50, 70), "Chapter 2: Dusk", fontsize=18)
    p2.insert_text((50, 110), "The sun set over the sea.", fontsize=11)
    doc.save(str(pdf_path))
    doc.close()

    mock_client = MagicMock(spec=OpenAICompatibleClient)
    mock_client.chat_completion.return_value = '{"corrections": []}'

    cfg = LLMConfig(enabled=True)
    result = convert(pdf_path, out_dir, llm_config=cfg, llm_client=mock_client)

    assert result.success is True
    assert result.chapters == 2
    assert result.llm_review_applied is True
    assert result.validation_report is not None
    assert result.validation_report.llm_corrections == 0
