"""Tests for scanner/exporter.py per TRD §5.7 and §7."""

from __future__ import annotations

from pathlib import Path

import pytest

from scanner.exporter import export_csv
from scanner.models import (
    ExtractedResume,
    FileFailure,
    MatchLevel,
    RankedResume,
    ScanReport,
)


def _report() -> ScanReport:
    ranked = [
        RankedResume(
            rank=1,
            path=Path("a.pdf"),
            score=0.8,
            percent=80.0,
            level=MatchLevel.EXCELLENT,
            top_terms=("python", "django"),
        ),
        RankedResume(
            rank=2,
            path=Path("b.pdf"),
            score=0.5,
            percent=50.0,
            level=MatchLevel.GOOD,
            top_terms=("sql",),
        ),
    ]
    failures = [
        FileFailure(path=Path("c.xyz"), reason="Unsupported file type: .xyz")
    ]
    return ScanReport(ranked=ranked, failures=failures, elapsed_s=1.5)


def test_csv_has_bom_header_and_row_count(tmp_path: Path) -> None:
    dest = tmp_path / "out.csv"
    export_csv(_report(), dest)

    raw = dest.read_bytes()
    assert raw.startswith(b"\xef\xbb\xbf"), "Missing UTF-8 BOM"

    text = dest.read_text(encoding="utf-8-sig")
    lines = text.splitlines()
    assert lines[0] == "Rank,File,Path,Match %,Level,Top keywords"
    # Header + 2 ranked rows (failures not exported)
    assert len(lines) == 3
    assert lines[1].startswith("1,a.pdf,")
    assert lines[2].startswith("2,b.pdf,")
