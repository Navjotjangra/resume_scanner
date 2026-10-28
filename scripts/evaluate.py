"""Evaluation script per TRD §10.

Compares the system ranking (TF-IDF + cosine) against human labels using
Spearman ρ and Precision@5, with random (fixed seed) and keyword-overlap
count baselines. A --sweep flag prints the level distribution for candidate
thresholds to help calibrate LEVEL_THRESHOLDS in scanner/config.py.

Usage:
    python scripts/evaluate.py \
        --jd sample_data/job_descriptions/data_analyst.txt \
        --resumes-dir sample_data/resumes \
        --labels sample_data/eval/labels_data_analyst.csv

    python scripts/evaluate.py --sweep \
        --jd sample_data/job_descriptions/data_analyst.txt \
        --resumes-dir sample_data/resumes
"""

from __future__ import annotations

import argparse
import csv
import logging
import random
import sys
from pathlib import Path

from scipy.stats import spearmanr

# Allow running as `python scripts/evaluate.py` from the project root.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scanner.config import LEVEL_THRESHOLDS, MAX_RESUMES  # noqa: E402
from scanner.extractors import extract_text  # noqa: E402
from scanner.models import ExtractedResume  # noqa: E402
from scanner.preprocess import normalize_text  # noqa: E402
from scanner.ranker import rank_resumes  # noqa: E402

logger = logging.getLogger(__name__)

SUPPORTED = {".pdf", ".docx", ".doc", ".txt"}


def load_labels(path: Path) -> dict[str, int]:
    """Load filename -> grade from a labels CSV. Blank grades are skipped."""
    labels: dict[str, int] = {}
    with path.open("r", encoding="utf-8", newline="") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            name = (row.get("filename") or "").strip()
            grade = (row.get("grade") or "").strip()
            if not name:
                continue
            if grade == "":
                continue
            try:
                labels[name] = int(grade)
            except ValueError:
                logger.warning("Invalid grade %r for %s, skipping", grade, name)
    return labels


def load_resumes(resumes_dir: Path) -> list[ExtractedResume]:
    """Load and extract text from all supported resumes in a directory."""
    resumes: list[ExtractedResume] = []
    for path in sorted(resumes_dir.iterdir()):
        if not path.is_file() or path.suffix.lower() not in SUPPORTED:
            continue
        try:
            text = extract_text(path)
            resumes.append(ExtractedResume(path=path, text=text))
        except Exception as e:  # noqa: BLE001 - evaluation should not die on one file
            logger.warning("Skipping %s: %s", path.name, e)
    return resumes


def keyword_overlap_score(jd_text: str, resume_text: str) -> int:
    """Count unique JD keywords that appear in the resume (baseline)."""
    jd_words = set(normalize_text(jd_text).split())
    resume_words = set(normalize_text(resume_text).split())
    return len(jd_words & resume_words)


def rank_system(jd_text: str, resumes: list[ExtractedResume]) -> dict[str, float]:
    """Filename -> cosine score using the system ranker."""
    ranked = rank_resumes(jd_text, resumes)
    return {r.path.name: r.score for r in ranked}


def rank_random(resumes: list[ExtractedResume], seed: int = 42) -> dict[str, float]:
    """Filename -> random score (fixed-seed baseline)."""
    rng = random.Random(seed)
    return {r.path.name: rng.random() for r in resumes}


def rank_keyword_overlap(
    jd_text: str, resumes: list[ExtractedResume]
) -> dict[str, float]:
    """Filename -> keyword overlap count (baseline)."""
    return {
        r.path.name: float(keyword_overlap_score(jd_text, r.text))
        for r in resumes
    }


def spearman_rho(scores: dict[str, float], labels: dict[str, int]) -> float:
    """Spearman ρ between scores and labels for common filenames."""
    common = sorted(set(scores) & set(labels))
    if len(common) < 2:
        return float("nan")
    x = [scores[n] for n in common]
    y = [labels[n] for n in common]
    rho, _ = spearmanr(x, y)
    return float(rho)


def precision_at_5(scores: dict[str, float], labels: dict[str, int]) -> float:
    """Precision@5: fraction of top-5 by score with grade >= 2 (relevant)."""
    ranked = sorted(scores.items(), key=lambda kv: (-kv[1], kv[0]))
    top5 = [name for name, _ in ranked[:5]]
    if not top5:
        return 0.0
    relevant = sum(1 for name in top5 if labels.get(name, -1) >= 2)
    return relevant / len(top5)


def evaluate(jd_text: str, resumes: list[ExtractedResume], labels: dict[str, int]) -> None:
    """Print a markdown table comparing system vs baselines."""
    system = rank_system(jd_text, resumes)
    random_scores = rank_random(resumes)
    keyword = rank_keyword_overlap(jd_text, resumes)

    rows = [
        ("System (TF-IDF + cosine)", system),
        ("Random (seed=42)", random_scores),
        ("Keyword overlap", keyword),
    ]

    print("| Method | Spearman rho | Precision@5 |")
    print("|--------|--------------|-------------|")
    for name, scores in rows:
        rho = spearman_rho(scores, labels)
        p5 = precision_at_5(scores, labels)
        rho_str = "n/a" if rho != rho else f"{rho:.3f}"
        print(f"| {name} | {rho_str} | {p5:.3f} |")


def sweep_thresholds(jd_text: str, resumes: list[ExtractedResume]) -> None:
    """Print level distribution for candidate Excellent thresholds."""
    ranked = rank_resumes(jd_text, resumes)
    percents = [r.percent for r in ranked]
    print("\nLevel sweep (candidate Excellent thresholds):")
    print(
        f"{'Excellent >= ':>12} | {'Excellent':>9} | {'Good':>6} | {'Fair':>6} | {'Low':>6}"
    )
    print("-" * 52)
    for t in (10.0, 15.0, 20.0, 25.0, 30.0, 35.0, 40.0, 45.0, 50.0):
        good_t = t * 0.625  # keeps 25/40 ratio from LEVEL_THRESHOLDS
        fair_t = t * 0.30  # keeps 12/40 ratio from LEVEL_THRESHOLDS
        e = sum(1 for p in percents if p >= t)
        g = sum(1 for p in percents if good_t <= p < t)
        f = sum(1 for p in percents if fair_t <= p < good_t)
        l = sum(1 for p in percents if p < fair_t)
        print(f"{t:>12.1f} | {e:>9} | {g:>6} | {f:>6} | {l:>6}")
    print(
        f"\nCurrent LEVEL_THRESHOLDS: {LEVEL_THRESHOLDS} "
        f"(else LOW). MAX_RESUMES = {MAX_RESUMES}."
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Evaluate resume ranking against human labels (TRD §10)."
    )
    parser.add_argument("--jd", type=Path, help="Path to job description text file")
    parser.add_argument(
        "--resumes-dir", type=Path, help="Directory containing resume files"
    )
    parser.add_argument(
        "--labels", type=Path, help="CSV with filename,grade (0-3); blank grades skipped"
    )
    parser.add_argument(
        "--sweep",
        action="store_true",
        help="Print level distribution for candidate thresholds",
    )
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    if args.resumes_dir is None:
        print("Error: --resumes-dir is required.", file=sys.stderr)
        sys.exit(2)

    resumes = load_resumes(args.resumes_dir)
    if not resumes:
        print("No resumes could be extracted.", file=sys.stderr)
        sys.exit(1)

    jd_text = ""
    if args.jd is not None:
        jd_text = args.jd.read_text(encoding="utf-8")

    if args.sweep:
        if not jd_text:
            print("Error: --sweep requires --jd.", file=sys.stderr)
            sys.exit(2)
        sweep_thresholds(jd_text, resumes)
        return

    if args.labels is None:
        print("Error: --labels is required (unless --sweep).", file=sys.stderr)
        sys.exit(2)

    labels = load_labels(args.labels)
    if not labels:
        print(
            "Warning: no labeled grades found. Fill in the labels CSV and re-run.",
            file=sys.stderr,
        )

    evaluate(jd_text, resumes, labels)


if __name__ == "__main__":
    main()
