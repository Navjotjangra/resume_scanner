"""Tests for scanner/pipeline.py per TRD §5.6 and §7."""

from __future__ import annotations

import threading
from pathlib import Path

import pytest

from scanner.errors import InvalidJobDescriptionError, ScanCancelled
from scanner.pipeline import scan_and_rank


def _write_txt(path: Path, text: str) -> None:
    path.write_text(text, encoding="utf-8")


def test_bad_file_in_failures_others_ranked(tmp_path: Path) -> None:
    good = tmp_path / "good.txt"
    _write_txt(
        good,
        "Python developer with Django and machine learning experience. "
        "Built REST APIs with PostgreSQL.",
    )
    bad = tmp_path / "bad.xyz"
    bad.write_bytes(b"garbage")

    jd = "Python developer with Django and machine learning experience."
    report = scan_and_rank(jd, [good, bad])

    assert len(report.ranked) == 1
    assert report.ranked[0].path.name == "good.txt"
    assert len(report.failures) == 1
    assert report.failures[0].path.name == "bad.xyz"
    assert "Unsupported" in report.failures[0].reason


def test_all_files_bad_empty_ranked(tmp_path: Path) -> None:
    bad1 = tmp_path / "a.xyz"
    bad1.write_bytes(b"garbage")
    bad2 = tmp_path / "b.txt"
    _write_txt(bad2, "hi")  # too short -> EmptyTextError

    jd = "Python developer with Django and machine learning experience."
    report = scan_and_rank(jd, [bad1, bad2])

    assert report.ranked == []
    assert len(report.failures) == 2


def test_scan_cancelled(tmp_path: Path) -> None:
    p = tmp_path / "good.txt"
    _write_txt(
        p,
        "Python developer with Django and machine learning experience. "
        "Built REST APIs with PostgreSQL.",
    )
    cancel = threading.Event()
    cancel.set()

    jd = "Python developer with Django and machine learning experience."
    with pytest.raises(ScanCancelled):
        scan_and_rank(jd, [p], cancel=cancel)


def test_progress_called_n_times(tmp_path: Path) -> None:
    calls: list[int] = []
    p1 = tmp_path / "a.txt"
    _write_txt(
        p1,
        "Python developer with Django and machine learning experience. "
        "Built REST APIs with PostgreSQL.",
    )
    p2 = tmp_path / "b.txt"
    _write_txt(p2, "Data analyst with SQL and Python skills.")

    def on_progress(done: int, total: int, name: str) -> None:
        calls.append(done)

    jd = "Python developer with Django and machine learning experience."
    scan_and_rank(jd, [p1, p2], on_progress=on_progress)

    assert calls == [1, 2]


def test_duplicate_paths_collapsed(tmp_path: Path) -> None:
    p = tmp_path / "good.txt"
    _write_txt(
        p,
        "Python developer with Django and machine learning experience. "
        "Built REST APIs with PostgreSQL.",
    )

    jd = "Python developer with Django and machine learning experience."
    report = scan_and_rank(jd, [p, p, p])

    assert len(report.ranked) == 1


def test_empty_jd_raises(tmp_path: Path) -> None:
    p = tmp_path / "good.txt"
    _write_txt(p, "Some resume text here with enough words.")

    with pytest.raises(InvalidJobDescriptionError):
        scan_and_rank("", [p])


def test_no_ranker_when_nothing_extracted(tmp_path: Path) -> None:
    bad = tmp_path / "bad.xyz"
    bad.write_bytes(b"garbage")
    report = scan_and_rank(
        "Python developer with Django and machine learning experience.", [bad]
    )
    assert report.ranked == []
    assert len(report.failures) == 1
