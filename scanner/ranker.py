"""TF-IDF + cosine similarity ranker for Resume Scanner & Ranker.

Implements build_vectorizer, level_for, top_matching_terms and
rank_resumes exactly per TRD §5.5.
"""

from __future__ import annotations

from typing import Sequence

import numpy as np
from sklearn.feature_extraction.text import ENGLISH_STOP_WORDS, TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from scanner.config import (
    EXTRA_STOPWORDS,
    LEVEL_THRESHOLDS,
    TFIDF_NGRAM_RANGE,
    TFIDF_SUBLINEAR_TF,
    TOP_TERMS,
)
from scanner.errors import InvalidJobDescriptionError
from scanner.models import (
    ExtractedResume,
    MatchLevel,
    RankedResume,
)
from scanner.preprocess import normalize_text


def build_vectorizer() -> TfidfVectorizer:
    """Build a TfidfVectorizer with project settings (TRD §5.5).

    No max_df / min_df are set (defaults only).
    """
    stop_words = sorted(ENGLISH_STOP_WORDS | EXTRA_STOPWORDS)
    return TfidfVectorizer(
        stop_words=stop_words,
        ngram_range=TFIDF_NGRAM_RANGE,
        sublinear_tf=TFIDF_SUBLINEAR_TF,
    )


def level_for(percent: float) -> MatchLevel:
    """Map a Match % to a MatchLevel using LEVEL_THRESHOLDS (top to bottom).

    Falls back to LOW when below every threshold.
    """
    for threshold, name in LEVEL_THRESHOLDS:
        if percent >= threshold:
            return MatchLevel[name]
    return MatchLevel.LOW


def top_matching_terms(
    jd_row, resume_row, feature_names: list[str], k: int = TOP_TERMS
) -> tuple[str, ...]:
    """Top terms where both JD and resume have non-zero TF-IDF weight.

    Uses the element-wise product jd_row * resume_row, takes the largest
    non-zero entries and maps column indices to feature names. A unigram
    already contained in a listed bigram is skipped.
    """
    product = jd_row.multiply(resume_row)
    if product.nnz == 0:
        return ()

    indices = product.indices
    data = product.data
    order = np.argsort(-data, kind="stable")

    selected: list[str] = []
    for idx in indices[order]:
        term = feature_names[int(idx)]
        # Skip a unigram already contained in a listed bigram.
        if " " not in term:
            if any(term in bigram for bigram in selected if " " in bigram):
                continue
        selected.append(term)
        if len(selected) >= k:
            break
    return tuple(selected)


def rank_resumes(
    jd_text: str, resumes: Sequence[ExtractedResume]
) -> list[RankedResume]:
    """Rank resumes against a JD using TF-IDF + cosine similarity.

    Normalizes JD and each resume, fits the vectorizer on
    [jd, *resumes] together, computes cosine similarity, sorts by
    (-score, filename.lower()) and assigns sequential ranks.
    """
    jd_norm = normalize_text(jd_text)
    docs = [normalize_text(r.text) for r in resumes]

    vectorizer = build_vectorizer()
    try:
        matrix = vectorizer.fit_transform([jd_norm, *docs])
    except ValueError as e:
        raise InvalidJobDescriptionError("Empty vocabulary") from e

    jd_vec = matrix[0]
    if jd_vec.nnz == 0:
        raise InvalidJobDescriptionError(
            "Job description has no meaningful keywords"
        )

    resume_matrix = matrix[1:]
    scores = cosine_similarity(jd_vec, resume_matrix).ravel()
    scores = np.round(scores, 6)

    feature_names = vectorizer.get_feature_names_out().tolist()

    scored = []
    for i, resume in enumerate(resumes):
        row = resume_matrix.getrow(i)
        score = round(float(scores[i]), 6)
        percent = round(score * 100, 1)
        level = level_for(percent)
        top_terms = top_matching_terms(jd_vec, row, feature_names)
        scored.append(
            (score, resume.path.name.lower(), resume, percent, level, top_terms)
        )

    scored.sort(key=lambda item: (-item[0], item[1]))

    ranked: list[RankedResume] = []
    for rank, (score, _, resume, percent, level, top_terms) in enumerate(
        scored, start=1
    ):
        ranked.append(
            RankedResume(
                rank=rank,
                path=resume.path,
                score=score,
                percent=percent,
                level=level,
                top_terms=top_terms,
            )
        )
    return ranked
