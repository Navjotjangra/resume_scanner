"""Tests for scanner/preprocess.py per TRD §5.4."""

from __future__ import annotations

import pytest

from scanner.preprocess import normalize_text


def test_tech_tokens_survive() -> None:
    """c++, c#, .net, node.js survive as single tokens."""
    assert normalize_text("c++") == "cplusplus"
    assert normalize_text("c#") == "csharp"
    assert normalize_text(".net") == "dotnet"
    assert normalize_text("node.js") == "nodejs"
    assert normalize_text("scikit-learn") == "scikitlearn"
    assert normalize_text("ci/cd") == "cicd"


def test_url_email_phone_removed() -> None:
    assert normalize_text("Visit https://example.com/page?q=1 today") == "visit today"
    assert normalize_text("Mail www.python.org now") == "mail now"
    assert normalize_text("Contact me at john.doe@example.com please") == "contact me at please"
    assert normalize_text("Call +1 (555) 123-4567 now") == "call now"
    assert normalize_text("Phone 555-123-4567 here") == "phone here"


def test_standalone_numbers_removed_python3_kept() -> None:
    assert normalize_text("I have 5 years of python3 experience") == "i have years of python3 experience"
    assert normalize_text("version 2.0 released in 2024") == "version released in"


def test_synonyms_expanded() -> None:
    assert normalize_text("ML engineer") == "machine learning engineer"
    assert normalize_text("NLP and AI") == "natural language processing and artificial intelligence"
    assert normalize_text("JS dev") == "javascript dev"


def test_lowercase_and_punctuation() -> None:
    assert normalize_text("Hello, World!") == "hello world"
    assert normalize_text("Python/Django; REST API") == "python django rest api"


def test_empty_and_whitespace() -> None:
    assert normalize_text("") == ""
    assert normalize_text("   ") == ""
    assert normalize_text("\t\n") == ""


def test_idempotent() -> None:
    samples = [
        "",
        "   ",
        "c++ and .net dev with ML skills",
        "Visit https://example.com or email a@b.com",
        "python3 version 2.0, call +1 (555) 123-4567",
        "  Mixed   CASE   with   spaces  ",
    ]
    for s in samples:
        assert normalize_text(normalize_text(s)) == normalize_text(s), s


def test_combined_pipeline() -> None:
    text = (
        "Senior c++ developer. ML/NLP experience. "
        "Email me at dev@company.com or call +1-555-000-1111. "
        "Visit www.example.com. 5 years, python3."
    )
    assert normalize_text(text) == (
        "senior cplusplus developer machine learning natural language "
        "processing experience email me at or call visit years python3"
    )
