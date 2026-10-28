"""Tests for scripts/evaluate.py pure helper functions."""

from __future__ import annotations

import math

import pytest

# Allow importing scripts/evaluate as a module.
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.evaluate import (  # noqa: E402
    keyword_overlap_score,
    load_labels,
    precision_at_5,
    rank_keyword_overlap,
    rank_random,
    rank_system,
    spearman_rho,
)
from scanner.models import ExtractedResume  # noqa: E402


def _resume(name: str, text: str) -> ExtractedResume:
    return ExtractedResume(path=Path(name), text=text)


def test_keyword_overlap_score() -> None:
    jd = "Python developer with SQL and Tableau experience."
    resume = "Python developer experienced in SQL, Tableau, and data cleaning."
    assert keyword_overlap_score(jd, resume) > 0

    unrelated = "Chef specializing in Italian cuisine, pizza, baking."
    assert keyword_overlap_score(jd, unrelated) == 0


def test_rank_random_deterministic() -> None:
    resumes = [_resume("a.txt", "text a"), _resume("b.txt", "text b")]
    r1 = rank_random(resumes, seed=42)
    r2 = rank_random(resumes, seed=42)
    assert r1 == r2
    assert set(r1) == {"a.txt", "b.txt"}


def test_rank_keyword_overlap() -> None:
    jd = "Python developer SQL Tableau"
    resumes = [
        _resume("a.txt", "Python developer with SQL experience."),
        _resume("b.txt", "Chef making pizza."),
    ]
    scores = rank_keyword_overlap(jd, resumes)
    assert scores["a.txt"] > scores["b.txt"]
    assert scores["b.txt"] == 0.0


def test_rank_system() -> None:
    jd = "Python developer with Django and machine learning experience."
    resumes = [
        _resume("a.txt", "Python developer experienced in Django and machine learning."),
        _resume("b.txt", "Chef specializing in Italian cuisine."),
    ]
    scores = rank_system(jd, resumes)
    assert scores["a.txt"] > scores["b.txt"]
    assert 0.0 <= scores["a.txt"] <= 1.0


def test_spearman_rho_perfect() -> None:
    scores = {"a.txt": 0.9, "b.txt": 0.5, "c.txt": 0.1}
    labels = {"a.txt": 3, "b.txt": 2, "c.txt": 0}
    rho = spearman_rho(scores, labels)
    assert rho == pytest.approx(1.0)


def test_spearman_rho_inverse() -> None:
    scores = {"a.txt": 0.1, "b.txt": 0.5, "c.txt": 0.9}
    labels = {"a.txt": 3, "b.txt": 2, "c.txt": 0}
    rho = spearman_rho(scores, labels)
    assert rho == pytest.approx(-1.0)


def test_spearman_rho_nan_when_no_overlap() -> None:
    scores = {"a.txt": 0.9, "b.txt": 0.5}
    labels = {"x.txt": 3, "y.txt": 2}
    rho = spearman_rho(scores, labels)
    assert math.isnan(rho)


def test_spearman_rho_nan_when_single_item() -> None:
    scores = {"a.txt": 0.9}
    labels = {"a.txt": 3}
    rho = spearman_rho(scores, labels)
    assert math.isnan(rho)


def test_precision_at_5() -> None:
    scores = {
        "a.txt": 0.9,
        "b.txt": 0.8,
        "c.txt": 0.7,
        "d.txt": 0.6,
        "e.txt": 0.5,
        "f.txt": 0.4,
    }
    # All top-5 are relevant (grade >= 2)
    labels = {"a.txt": 3, "b.txt": 3, "c.txt": 2, "d.txt": 2, "e.txt": 3}
    assert precision_at_5(scores, labels) == 1.0

    # None of top-5 relevant
    labels2 = {"a.txt": 0, "b.txt": 0, "c.txt": 1, "d.txt": 0, "e.txt": 1}
    assert precision_at_5(scores, labels2) == 0.0

    # Missing labels treated as not relevant
    labels3 = {"a.txt": 3, "b.txt": 3}
    assert precision_at_5(scores, labels3) == 0.4  # 2 relevant out of 5


def test_load_labels_skips_blank(tmp_path: Path) -> None:
    p = tmp_path / "labels.csv"
    p.write_text("filename,grade\n", encoding="utf-8")
    p.write_text(
        "filename,grade\na.txt,3\nb.txt,\nc.txt,1\n", encoding="utf-8"
    )
    labels = load_labels(p)
    assert labels == {"a.txt": 3, "c.txt": 1}
