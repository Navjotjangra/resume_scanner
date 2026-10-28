"""Scan pipeline: extract resumes, rank them, collect failures.

The pipeline has no GUI imports. Extraction stays sequential (PyMuPDF is
not thread-safe). One bad file never stops the scan.
"""

from __future__ import annotations

import threading
import time
from collections.abc import Callable, Sequence
from pathlib import Path

from scanner.config import MIN_JD_CHARS
from scanner.errors import (
    InvalidJobDescriptionError,
    ScannerError,
    ScanCancelled,
)
from scanner.extractors import extract_text
from scanner.models import ExtractedResume, FileFailure, RankedResume, ScanReport
from scanner.preprocess import normalize_text
from scanner.ranker import rank_resumes

ProgressFn = Callable[[int, int, str], None]


def scan_and_rank(
    jd_text: str,
    paths: Sequence[Path],
    on_progress: ProgressFn | None = None,
    cancel: threading.Event | None = None,
) -> ScanReport:
    """Extract text from each resume, then rank against the JD.

    Steps:
    1. Validate JD: len(normalize_text(jd_text)) >= MIN_JD_CHARS, else
       InvalidJobDescriptionError.
    2. De-duplicate paths (resolved, keep order).
    3. For each path: if cancel is set -> raise ScanCancelled. Try
       extract_text. ScannerError -> FileFailure. Any other Exception ->
       log + FileFailure("Unexpected error while reading file").
       Call on_progress(i, total, name).
    4. If nothing was extracted, return report with ranked=[] and failures.
    5. Call rank_resumes. Return ScanReport with elapsed_s.
    """
    # Step 1 — validate JD.
    if len(normalize_text(jd_text)) < MIN_JD_CHARS:
        raise InvalidJobDescriptionError(
            "Job description has no meaningful keywords"
        )

    # Step 2 — de-duplicate resolved paths, keep order.
    seen: set[Path] = set()
    unique_paths: list[Path] = []
    for path in paths:
        resolved = path.resolve()
        if resolved not in seen:
            seen.add(resolved)
            unique_paths.append(resolved)

    total = len(unique_paths)
    extracted: list[ExtractedResume] = []
    failures: list[FileFailure] = []

    start = time.perf_counter()

    for i, path in enumerate(unique_paths, start=1):
        # Step 3 — cancel check before each file.
        if cancel is not None and cancel.is_set():
            raise ScanCancelled()

        name = path.name
        try:
            text = extract_text(path)
            extracted.append(ExtractedResume(path=path, text=text))
        except ScannerError as e:
            # UnsupportedFormatError, FileTooLargeError, ExtractionError,
            # EmptyTextError are all ScannerError subclasses.
            failures.append(FileFailure(path=path, reason=str(e)))
        except Exception:  # noqa: BLE001 - boundary; never crash the scan
            import logging

            logging.exception("Unexpected error reading %s", name)
            failures.append(
                FileFailure(path=path, reason="Unexpected error while reading file")
            )

        if on_progress is not None:
            on_progress(i, total, name)

    # Step 4 — nothing extracted -> no ranker call.
    if not extracted:
        elapsed = time.perf_counter() - start
        return ScanReport(ranked=[], failures=failures, elapsed_s=elapsed)

    # Step 5 — rank.
    ranked = rank_resumes(jd_text, extracted)
    elapsed = time.perf_counter() - start
    return ScanReport(ranked=ranked, failures=failures, elapsed_s=elapsed)
