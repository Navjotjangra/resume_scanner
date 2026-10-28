"""Tests for scanner/ranker.py per TRD §5.5 and §7."""

from __future__ import annotations

from pathlib import Path

import pytest

from scanner.errors import InvalidJobDescriptionError
from scanner.models import ExtractedResume, MatchLevel
from scanner.preprocess import normalize_text
from scanner.ranker import (
    build_vectorizer,
    level_for,
    rank_resumes,
    top_matching_terms,
)


def _resume(name: str, text: str) -> ExtractedResume:
    return ExtractedResume(path=Path(name), text=text)


def test_relevant_outranks_irrelevant() -> None:
    jd = (
        "Python developer with Django and machine learning experience, "
        "building REST APIs and working with PostgreSQL."
    )
    relevant = _resume(
        "a.pdf",
        "Python developer experienced in Django and machine learning. "
        "Built REST APIs with PostgreSQL.",
    )
    irrelevant = _resume(
        "b.pdf",
        "Chef specializing in Italian cuisine, pasta and pizza making.",
    )
    ranked = rank_resumes(jd, [relevant, irrelevant])
    assert ranked[0].path.name == "a.pdf"
    assert ranked[1].path.name == "b.pdf"
    assert ranked[0].score > ranked[1].score


def test_identical_text_scores_near_100() -> None:
    jd = "Python developer with Django and machine learning experience."
    resume = _resume("x.pdf", jd)
    ranked = rank_resumes(jd, [resume])
    assert ranked[0].percent >= 99.0, ranked[0].percent


def test_deterministic_order() -> None:
    jd = "Python developer with Django and machine learning experience."
    resumes = [
        _resume("alpha.pdf", "Python developer with Django experience."),
        _resume("beta.pdf", "Machine learning engineer with Python skills."),
        _resume("gamma.pdf", "Chef making pasta and pizza."),
    ]
    first = rank_resumes(jd, resumes)
    second = rank_resumes(jd, resumes)
    assert [r.path.name for r in first] == [r.path.name for r in second]
    assert [r.score for r in first] == [r.score for r in second]


def test_tie_broken_by_filename() -> None:
    jd = "Python developer."
    # Two resumes with identical normalized content → same score.
    r1 = _resume("zebra.pdf", "Python developer.")
    r2 = _resume("apple.pdf", "Python developer.")
    ranked = rank_resumes(jd, [r1, r2])
    assert ranked[0].path.name == "apple.pdf"
    assert ranked[1].path.name == "zebra.pdf"
    assert ranked[0].rank == 1
    assert ranked[1].rank == 2


def test_jd_stop_words_only_raises() -> None:
    jd = "the and is a of to in it"
    resume = _resume("a.pdf", "Python developer.")
    with pytest.raises(InvalidJobDescriptionError):
        rank_resumes(jd, [resume])


def test_single_resume_works() -> None:
    jd = "Python developer with Django experience."
    resume = _resume("only.pdf", "Python developer with Django experience.")
    ranked = rank_resumes(jd, [resume])
    assert len(ranked) == 1
    assert ranked[0].rank == 1
    assert ranked[0].percent >= 99.0


def test_level_boundaries() -> None:
    assert level_for(40.0) == MatchLevel.EXCELLENT
    assert level_for(39.9) == MatchLevel.GOOD
    assert level_for(25.0) == MatchLevel.GOOD
    assert level_for(24.9) == MatchLevel.FAIR
    assert level_for(12.0) == MatchLevel.FAIR
    assert level_for(11.9) == MatchLevel.LOW
    assert level_for(0.0) == MatchLevel.LOW
    assert level_for(100.0) == MatchLevel.EXCELLENT


def test_top_terms_contain_expected_keyword() -> None:
    jd = "Python developer with Django and machine learning experience."
    resume = _resume(
        "a.pdf", "Python developer experienced in Django and machine learning."
    )
    ranked = rank_resumes(jd, [resume])
    terms = ranked[0].top_terms
    assert any("python" in t or "django" in t or "machine" in t for t in terms), terms


def test_top_matching_terms_direct() -> None:
    vectorizer = build_vectorizer()
    jd_text = normalize_text("Python developer with Django experience")
    resume_text = normalize_text("Python developer with Django experience")
    matrix = vectorizer.fit_transform([jd_text, resume_text])
    feature_names = vectorizer.get_feature_names_out().tolist()
    terms = top_matching_terms(matrix[0], matrix.getrow(1), feature_names)
    assert isinstance(terms, tuple)
    assert len(terms) <= 8
    # Identical texts share terms, so at least one term should appear.
    assert len(terms) > 0


def test_build_vectorizer_settings() -> None:
    vec = build_vectorizer()
    assert vec.ngram_range == (1, 2)
    assert vec.sublinear_tf is True
