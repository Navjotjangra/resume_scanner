"""Data models for Resume Scanner & Ranker."""

from dataclasses import dataclass
from enum import Enum
from pathlib import Path


class MatchLevel(str, Enum):
    EXCELLENT = "Excellent"
    GOOD = "Good"
    FAIR = "Fair"
    LOW = "Low"


@dataclass(frozen=True)
class ExtractedResume:
    path: Path
    text: str


@dataclass(frozen=True)
class FileFailure:
    path: Path
    reason: str  # human-readable, shown in the Skipped tab


@dataclass(frozen=True)
class RankedResume:
    rank: int  # 1-based, sequential
    path: Path
    score: float  # cosine, 0..1, rounded to 6 dp
    percent: float  # score*100, 1 dp
    level: MatchLevel
    top_terms: tuple[str, ...]


@dataclass(frozen=True)
class ScanReport:
    ranked: list[RankedResume]
    failures: list[FileFailure]
    elapsed_s: float
